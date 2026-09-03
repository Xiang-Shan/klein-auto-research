"""``klein replicate`` — internal replication as convergent evidence.

The spec is ``.claude/skills/klein/references/replication-protocol.md``: a
development run is re-executed in a DETACHED WORKTREE at its candidate commit on
the same prepared data; the printed block is compared within the tolerance
ladder; the record is ``runs/E####/replications/<ts>.json`` with evidence id
``rep:E####@<ts>`` (``verify:`` for ``--verify-only``); sealed runs and crashes
are refused with no override; and the manifest is never touched.

The replicated ``train.py`` reads its metric from a file OUTSIDE the repository,
so a test can make the same commit print a different number — which is exactly
the nondeterminism a replication exists to catch — and writes an environment
marker there too, so the child's ``KLEIN_REPLICATION`` / cleared ``KLEIN_SMOKE``
are observed rather than assumed.
"""

from __future__ import annotations

import glob
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest
import yaml

from kleinlib import cli
from kleinlib.errors import WorkflowError
from kleinlib.events import read_events
from kleinlib.replicate import (
    confirmation_gaps,
    evidence_id,
    list_replications,
    load_replications,
    replicate_run,
    required_confirmation,
    tolerance_ladder,
)
from kleinlib.transaction import detached_worktree
from kleinlib.workflow import finalize, load_contract, load_state, record_gate, run_one

TRAIN = """\
import json
import os
from pathlib import Path

value = float(Path({value_file!r}).read_text(encoding="utf-8").strip())
Path({marker!r}).write_text(
    json.dumps(
        {{
            "replication": os.environ.get("KLEIN_REPLICATION", ""),
            "smoke": os.environ.get("KLEIN_SMOKE", ""),
            "sealed_dryrun": os.environ.get("KLEIN_SEALED_DRYRUN", ""),
            "experiment": os.environ.get("KLEIN_EXPERIMENT_ID", ""),
            "track": os.environ.get("KLEIN_TRACK", ""),
            "cwd": os.getcwd(),
        }}
    ),
    encoding="utf-8",
)
Path("models").mkdir(exist_ok=True)
Path("models/best.json").write_text(json.dumps({{"score": 0.7}}), encoding="utf-8")
print("artifact:          models/best.json")
print("primary_metric:    %.6f" % value)
print("metric_name:       val_auc")
print("metric_goal:       higher")
print("val_auc:           %.6f" % value)
"""

VERIFIER = """\
import json
import os
from pathlib import Path

artifact = Path(os.environ["KLEIN_ARTIFACT"])
score = json.loads(artifact.read_text(encoding="utf-8"))["score"]
drift = float(Path({drift_file!r}).read_text(encoding="utf-8").strip())
Path({marker!r}).write_text(
    json.dumps(
        {{
            "artifact": str(artifact),
            "replication": os.environ.get("KLEIN_REPLICATION", ""),
            "smoke": os.environ.get("KLEIN_SMOKE", ""),
        }}
    ),
    encoding="utf-8",
)
print("primary_metric:    %.6f" % (score + drift))
print("metric_name:       val_auc")
print("metric_goal:       higher")
"""


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, text=True, capture_output=True, check=False
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def commit_all(repo: Path, message: str) -> None:
    git(repo, "add", "-A")
    if git(repo, "status", "--porcelain") == "":
        return
    git(repo, "-c", "user.name=Test", "-c", "user.email=t@example.invalid",
        "commit", "-q", "-m", message)


def edit_contract(study: Path, mutate) -> None:
    path = study / "study.yaml"
    contract = yaml.safe_load(path.read_text(encoding="utf-8"))
    mutate(contract)
    path.write_text(yaml.safe_dump(contract, sort_keys=False), encoding="utf-8")


def leftover_worktrees() -> list[str]:
    return glob.glob(os.path.join(tempfile.gettempdir(), "klein-*worktree-*")) + glob.glob(
        os.path.join(tempfile.gettempdir(), "klein-replicate-*")
    )


@pytest.fixture
def replicable(ready_study, tmp_path: Path):
    """A study with one kept development run whose metric a test can move."""
    repo, study = ready_study
    value_file = tmp_path / "value.txt"
    value_file.write_text("0.700000\n", encoding="utf-8")
    marker = tmp_path / "marker.json"
    (study / "train.py").write_text(
        TRAIN.format(value_file=str(value_file), marker=str(marker)), encoding="utf-8"
    )
    manifest = run_one(
        study,
        description="baseline",
        command=[sys.executable, "-u", "train.py"],
        echo=False,
    )
    assert manifest["disposition"] == "keep"
    assert manifest["primary_metric"] == pytest.approx(0.7)
    return repo, study, value_file, marker, manifest


# ---------------------------------------------------------------------------
# 1. the happy path: a run reproduces, and the record says how
# ---------------------------------------------------------------------------


def test_a_development_run_reproduces_and_the_manifest_is_never_touched(
    replicable, monkeypatch
) -> None:
    repo, study, _value, marker, manifest = replicable
    manifest_path = study / "runs" / "E0001" / "manifest.json"
    before = manifest_path.read_bytes()
    marker.unlink()
    # ambient smoke mode in the driving shell must not reach the child
    monkeypatch.setenv("KLEIN_SMOKE", "1")

    record = replicate_run(study, "E0001", echo=False)

    assert record["reproduced"] is True
    assert record["mode"] == "replicate"
    assert record["difference"] == 0.0
    assert record["tolerance_source"] == "exact"
    assert record["evidence_id"] == evidence_id("E0001", record["stamp"], "replicate")
    assert record["evidence_id"].startswith("rep:E0001@")
    assert record["candidate_commit"] == manifest["candidate_commit"]
    assert record["original_block"]["primary_metric"] == pytest.approx(0.7)
    assert record["replicate_block"]["primary_metric"] == pytest.approx(0.7)
    assert record["block_differences"]["val_auc"]["difference"] == 0.0
    assert record["mismatched_keys"] == []

    # the manifest is evidence, not a scratchpad
    assert manifest_path.read_bytes() == before

    # the record and its log live beside the run
    stamp = record["stamp"]
    directory = study / "runs" / "E0001" / "replications"
    assert record["record"] == f"runs/E0001/replications/{stamp}.json"
    assert json.loads((study / record["record"]).read_text(encoding="utf-8")) == record
    assert "primary_metric:    0.700000" in (directory / f"{stamp}.log").read_text(
        encoding="utf-8"
    )

    # the child ran in the throwaway worktree, replication on, smoke cleared
    child = json.loads(marker.read_text(encoding="utf-8"))
    assert child["replication"] == "1"
    assert child["smoke"] == ""
    assert child["sealed_dryrun"] == ""
    assert child["experiment"] == "E0001"
    assert child["track"] == "primary"
    assert Path(child["cwd"]).name == "03-demo"
    assert not Path(child["cwd"]).is_relative_to(repo)

    # journal + rollup + a clean tree afterwards
    event = read_events(study)[-1]
    assert event["type"] == "run_replicated"
    assert event["reproduced"] is True
    assert event["evidence_id"] == record["evidence_id"]
    rollup = load_state(study, load_contract(study))["replications"]
    assert rollup["E0001"]["modes"]["replicate"] == {"attempts": 1, "reproduced": True}
    assert rollup["E0001"]["track"] == "primary"
    assert git(repo, "status", "--porcelain") == ""
    assert leftover_worktrees() == []
    assert git(repo, "worktree", "list").count("\n") == 0


def test_a_second_replication_appends_a_second_record(replicable) -> None:
    _repo, study, _value, _marker, _manifest = replicable
    first = replicate_run(study, "E0001", echo=False)
    second = replicate_run(study, "E0001", echo=False)
    assert first["stamp"] != second["stamp"]
    records = load_replications(study, "E0001")
    assert [r["evidence_id"] for r in records] == [
        first["evidence_id"],
        second["evidence_id"],
    ]
    assert load_state(study, load_contract(study))["replications"]["E0001"]["attempts"] == 2


# ---------------------------------------------------------------------------
# 2. the tolerance ladder
# ---------------------------------------------------------------------------


def test_tolerance_ladder_rungs() -> None:
    floor = {"metric": {"minimum_delta": 0.0, "noise_floor": {"std": 0.004}}}
    assert tolerance_ladder({"metric": {"minimum_delta": 0.01}}) == (0.01, "minimum_delta")
    assert tolerance_ladder(floor) == (0.004, "floor_std")
    assert tolerance_ladder({"metric": {}}) == (0.0, "exact")
    assert tolerance_ladder({"metric": {"exactness": "exact", "minimum_delta": 0.5}}) == (
        0.0,
        "exact",
    )
    # --tolerance is the top rung and beats every declaration below it
    assert tolerance_ladder(floor, override=0.5) == (0.5, "--tolerance")
    assert tolerance_ladder(
        {"metric": {"exactness": "exact"}}, override=0.5
    ) == (0.5, "--tolerance")
    # verify mode reads the verifier's own tolerance before the metric's
    verifier = {"metric": {"minimum_delta": 0.01}, "verifier": {"tolerance": 1e-9}}
    assert tolerance_ladder(verifier, mode="verify") == (1e-9, "verifier.tolerance")
    assert tolerance_ladder(verifier) == (0.01, "minimum_delta")
    with pytest.raises(WorkflowError, match="--tolerance"):
        tolerance_ladder({"metric": {}}, override=-1.0)


def test_the_chosen_tolerance_decides_the_verdict(replicable) -> None:
    """Same drift, three rungs: exact refuses it, --tolerance admits it, and a
    contract-declared minimum_delta admits it without a flag."""
    _repo, study, value_file, _marker, _manifest = replicable
    value_file.write_text("0.706000\n", encoding="utf-8")

    strict = replicate_run(study, "E0001", echo=False)
    assert strict["tolerance_source"] == "exact"
    assert strict["difference"] == pytest.approx(0.006)
    assert strict["reproduced"] is False
    assert strict["mismatched_keys"] == ["primary_metric", "val_auc"]

    wide = replicate_run(study, "E0001", tolerance=0.01, echo=False)
    assert wide["tolerance_source"] == "--tolerance"
    assert wide["reproduced"] is True

    edit_contract(
        study, lambda c: c["tracks"]["primary"]["metric"].update(minimum_delta=0.01)
    )
    declared = replicate_run(study, "E0001", echo=False)
    assert (declared["tolerance_source"], declared["tolerance"]) == ("minimum_delta", 0.01)
    assert declared["reproduced"] is True

    # every attempt is kept: the protocol forbids re-running until it passes
    assert [r["reproduced"] for r in load_replications(study, "E0001")] == [
        False,
        True,
        True,
    ]


def test_a_failed_replication_is_a_record_not_an_exception(replicable) -> None:
    _repo, study, value_file, _marker, _manifest = replicable
    value_file.write_text("not-a-number\n", encoding="utf-8")
    record = replicate_run(study, "E0001", echo=False)
    assert record["reproduced"] is False
    assert record["difference"] is None
    assert record["exit_code"] != 0
    assert "exit code" in record["failure_reason"]
    assert record["replicate_block"] == {}
    assert (study / "runs" / "E0001" / "replications" / f"{record['stamp']}.json").is_file()


# ---------------------------------------------------------------------------
# 3. the two refusals, with no override
# ---------------------------------------------------------------------------


def test_a_sealed_run_is_refused(replicable) -> None:
    repo, study, _value, _marker, _manifest = replicable
    record_gate(study, "phase", phase="adaptive-1", acknowledged_by="tester")
    commit_all(repo, "ack phase")
    sealed = run_one(
        study,
        description="confirmation",
        final_test=True,
        command=[sys.executable, "-u", "train.py"],
        echo=False,
    )
    assert sealed["evaluation_kind"] == "final_test"
    with pytest.raises(WorkflowError, match="second look"):
        replicate_run(study, sealed["experiment"], echo=False)
    assert not (study / "runs" / sealed["experiment"] / "replications").exists()


def test_a_crash_is_refused(replicable) -> None:
    _repo, study, _value, _marker, _manifest = replicable
    train = study / "train.py"
    train.write_text(train.read_text(encoding="utf-8") + "\nraise SystemExit(3)\n", encoding="utf-8")
    crashed = run_one(
        study, description="boom", command=[sys.executable, "-u", "train.py"], echo=False
    )
    assert crashed["disposition"] == "crash"
    with pytest.raises(WorkflowError, match="nothing to reproduce"):
        replicate_run(study, "E0002", echo=False)


def test_unknown_and_malformed_ids_are_refused(replicable) -> None:
    _repo, study, _value, _marker, _manifest = replicable
    with pytest.raises(WorkflowError, match="not an experiment id"):
        replicate_run(study, "banana", echo=False)
    with pytest.raises(WorkflowError, match="no run E0099"):
        replicate_run(study, "E0099", echo=False)


def test_a_changed_prepared_input_is_refused_before_anything_is_recorded(
    replicable,
) -> None:
    _repo, study, _value, _marker, _manifest = replicable
    (study / "data" / "prepared" / "fixture.csv").write_text("x,y\n9,1\n", encoding="utf-8")
    with pytest.raises(WorkflowError, match="prepared-data fingerprint differs"):
        replicate_run(study, "E0001", echo=False)
    assert list(load_replications(study, "E0001")) == []
    assert leftover_worktrees() == []


# ---------------------------------------------------------------------------
# 4. the worktree is always removed and pruned
# ---------------------------------------------------------------------------


def test_detached_worktree_lives_outside_the_repo_and_is_cleaned_on_failure(
    ready_study,
) -> None:
    repo, _study = ready_study
    head = git(repo, "rev-parse", "HEAD")
    before = git(repo, "worktree", "list")
    seen: dict[str, Path] = {}

    with pytest.raises(RuntimeError, match="simulated"):
        with detached_worktree(repo, head) as worktree:
            seen["path"] = worktree
            assert worktree.is_dir()
            assert (worktree / "uv.lock").is_file()
            assert not worktree.is_relative_to(repo.resolve())
            assert worktree.is_relative_to(Path(tempfile.gettempdir()).resolve())
            # a detached checkout, not a second branch on the same commit
            assert git(worktree, "rev-parse", "--abbrev-ref", "HEAD") == "HEAD"
            raise RuntimeError("simulated failure inside the worktree")

    assert not seen["path"].exists()
    assert not seen["path"].parent.exists()
    assert git(repo, "worktree", "list") == before
    assert leftover_worktrees() == []


def test_a_dirty_worktree_is_still_removed(ready_study) -> None:
    """`git worktree remove` refuses a modified checkout without --force."""
    repo, _study = ready_study
    head = git(repo, "rev-parse", "HEAD")
    with detached_worktree(repo, head) as worktree:
        (worktree / "uv.lock").write_text("version = 999\n", encoding="utf-8")
        (worktree / "untracked.bin").write_bytes(b"\x00\x01")
        path = worktree
    assert not path.exists()
    assert git(repo, "worktree", "list").count("\n") == 0


def test_a_crashing_runner_leaves_no_worktree_behind(replicable, monkeypatch) -> None:
    repo, study, _value, _marker, _manifest = replicable

    def explode(*_args, **_kwargs):
        raise RuntimeError("simulated runner failure")

    monkeypatch.setattr("kleinlib.replicate.run_logged", explode)
    with pytest.raises(RuntimeError, match="simulated runner failure"):
        replicate_run(study, "E0001", echo=False)
    assert git(repo, "worktree", "list").count("\n") == 0
    assert leftover_worktrees() == []
    # the study lock is released too, so the next operation is not blocked
    assert not (study / ".klein.lock").exists()
    monkeypatch.undo()
    assert replicate_run(study, "E0001", echo=False)["reproduced"] is True


# ---------------------------------------------------------------------------
# 5. --verify-only
# ---------------------------------------------------------------------------


@pytest.fixture
def verifier_study(ready_study, tmp_path: Path):
    """A track with a declared verifier and a run that pinned an artifact."""
    repo, study = ready_study
    value_file = tmp_path / "value.txt"
    value_file.write_text("0.700000\n", encoding="utf-8")
    drift_file = tmp_path / "drift.txt"
    drift_file.write_text("0.0\n", encoding="utf-8")
    marker = tmp_path / "marker.json"
    verifier_marker = tmp_path / "verifier.json"
    (study / "verify.py").write_text(
        VERIFIER.format(drift_file=str(drift_file), marker=str(verifier_marker)),
        encoding="utf-8",
    )
    edit_contract(
        study,
        lambda c: c["tracks"]["primary"].update(
            verifier={
                "command": [sys.executable, "-u", "verify.py"],
                "tolerance": 1e-6,
                # the KEY train.py prints the artifact path under (package A's
                # `run-one` resolves the artifact from that printed line)
                "artifact_key": "artifact",
            }
        ),
    )
    # study.yaml is a CONSULT gate artifact: re-record it after the edit
    record_gate(study, "consult", acknowledged_by="tester")
    commit_all(repo, "declare the verifier")
    (study / "train.py").write_text(
        TRAIN.format(value_file=str(value_file), marker=str(marker)), encoding="utf-8"
    )
    manifest = run_one(
        study, description="baseline", command=[sys.executable, "-u", "train.py"], echo=False
    )
    assert "models/best.json" in manifest["artifacts"]
    return repo, study, drift_file, verifier_marker, manifest


def test_verify_only_reruns_the_declared_verifier_on_the_pinned_artifact(
    verifier_study, monkeypatch
) -> None:
    repo, study, _drift, verifier_marker, manifest = verifier_study
    manifest_path = study / "runs" / "E0001" / "manifest.json"
    before = manifest_path.read_bytes()
    monkeypatch.setenv("KLEIN_SMOKE", "1")

    record = replicate_run(study, "E0001", verify_only=True, echo=False)

    assert record["mode"] == "verify"
    assert record["evidence_id"].startswith("verify:E0001@")
    assert record["reproduced"] is True
    assert record["tolerance_source"] == "verifier.tolerance"
    assert record["artifact"] == "models/best.json"
    assert record["artifact_sha256"] == manifest["artifacts"]["models/best.json"]["sha256"]
    # package A's run-one recorded the verified number; that is the baseline a
    # re-verification reproduces, not the searcher's own report
    assert record["baseline_source"] == "manifest.metric.verified"
    assert manifest["verifier"]["artifact"] == "models/best.json"
    # no worktree at all: the verifier judges the artifact where it lies
    assert record["worktree_prepared"] is False
    assert git(repo, "worktree", "list").count("\n") == 0
    assert leftover_worktrees() == []
    assert manifest_path.read_bytes() == before

    child = json.loads(verifier_marker.read_text(encoding="utf-8"))
    assert Path(child["artifact"]) == (study / "models" / "best.json")
    assert child["replication"] == "1"
    assert child["smoke"] == ""
    assert load_state(study, load_contract(study))["replications"]["E0001"]["modes"][
        "verify"
    ] == {"attempts": 1, "reproduced": True}


def test_verify_only_records_a_disagreement(verifier_study) -> None:
    _repo, study, drift_file, _marker, _manifest = verifier_study
    drift_file.write_text("0.05\n", encoding="utf-8")
    record = replicate_run(study, "E0001", verify_only=True, echo=False)
    assert record["reproduced"] is False
    assert record["difference"] == pytest.approx(0.05)
    assert record["tolerance"] == 1e-6


def test_verify_only_needs_a_declared_verifier(replicable) -> None:
    _repo, study, _value, _marker, _manifest = replicable
    with pytest.raises(WorkflowError, match="declare a `verifier:` block"):
        replicate_run(study, "E0001", verify_only=True, echo=False)


def test_verify_only_refuses_an_artifact_that_moved(verifier_study) -> None:
    _repo, study, _drift, _marker, _manifest = verifier_study
    (study / "models" / "best.json").write_text('{"score": 0.9}', encoding="utf-8")
    with pytest.raises(WorkflowError, match="changed since E0001"):
        replicate_run(study, "E0001", verify_only=True, echo=False)
    (study / "models" / "best.json").unlink()
    with pytest.raises(WorkflowError, match="absent from disk"):
        replicate_run(study, "E0001", verify_only=True, echo=False)


def test_verify_only_refuses_a_checker_that_changed(verifier_study) -> None:
    """A re-verification must run the SAME checker: `run-one` pins the verifier
    script's sha256, and a changed script is a new measurement, not a re-check."""
    _repo, study, _drift, _marker, manifest = verifier_study
    assert "verify.py" in manifest["verifier"]["sha256"]
    verify = study / "verify.py"
    verify.write_text(verify.read_text(encoding="utf-8") + "\n# tweaked\n", encoding="utf-8")
    with pytest.raises(WorkflowError, match="verifier script verify.py changed since E0001"):
        replicate_run(study, "E0001", verify_only=True, echo=False)
    verify.unlink()
    with pytest.raises(WorkflowError, match="verifier script verify.py .* is missing"):
        replicate_run(study, "E0001", verify_only=True, echo=False)


# ---------------------------------------------------------------------------
# 6. `klein finalize` degrades a track that did not pay for its confirmation
# ---------------------------------------------------------------------------


def _require(study: Path, *modes: str) -> None:
    edit_contract(
        study,
        lambda c: c["tracks"]["primary"].update(confirmation={"require": list(modes)}),
    )


def _findings(study: Path) -> None:
    (study / "findings.md").write_text(
        "# Findings\n\nThe study is labelled exploratory until every track is confirmed "
        "by the evidence its contract requires.\n",
        encoding="utf-8",
    )


@pytest.fixture
def sealed_study(replicable):
    repo, study, value_file, marker, manifest = replicable
    record_gate(study, "phase", phase="adaptive-1", acknowledged_by="tester")
    commit_all(repo, "ack phase")
    run_one(
        study,
        description="confirmation",
        final_test=True,
        command=[sys.executable, "-u", "train.py"],
        echo=False,
    )
    _findings(study)
    return repo, study, value_file, marker, manifest


def test_required_confirmation_reads_the_track_then_the_study_then_the_kind() -> None:
    # 1. the track's own declaration wins over the study-wide one
    assert required_confirmation({"confirmation": {"require": ["sealed", "replicate"]}}) == {
        "sealed",
        "replicate",
    }
    assert required_confirmation(
        {"confirmation": {"require": []}}, {"confirmation": {"require": ["verify"]}}
    ) == set()
    # 2. else the study-level block, read through package A's helper
    assert required_confirmation({}, {"confirmation": {"require": ["verify"]}}) == {"verify"}
    # 3. else the per-kind default, keyed by the TRACK's kind
    assert required_confirmation({}, {"kind": "optimize"}) == {"verify"}
    assert required_confirmation({}, {"kind": "predict"}) == {"sealed"}
    assert required_confirmation({"kind": "optimize"}, {"kind": "predict"}) == {"verify"}
    assert required_confirmation({}, {"kind": "discover"}) == set()
    # an untyped (schema-2) contract closes on sealed, so nothing here fires
    assert required_confirmation({}, {}) == {"sealed"}
    # a bare mapping with no contract carries no kind to default from
    assert required_confirmation({}) == set()


def test_a_schema_3_optimize_track_defaults_to_wanting_a_verify_record(replicable) -> None:
    """The inquiry model's kind table IS the default: an `optimize` track closes
    on `verify` with no confirmation block declared, and `predict` on `sealed`
    (which finalize enforces through the holdout counts, not here)."""
    _repo, study, _value, _marker, _manifest = replicable
    manifests = _manifests(study)
    tracks = {"primary": {"metric": {"name": "val_auc", "goal": "higher"}}}

    gaps = confirmation_gaps(study, {"kind": "optimize", "tracks": tracks}, manifests)
    assert len(gaps["primary"]) == 1
    assert gaps["primary"][0].startswith("verify:")
    assert "E0001" in gaps["primary"][0] and "--verify-only" in gaps["primary"][0]

    assert confirmation_gaps(study, {"kind": "predict", "tracks": tracks}, manifests) == {}
    assert confirmation_gaps(study, {"kind": "discover", "tracks": tracks}, manifests) == {}


def test_a_schema_2_study_declares_nothing_and_finalizes_unchanged(sealed_study) -> None:
    _repo, study, _value, _marker, _manifest = sealed_study
    assert confirmation_gaps(study, load_contract(study), []) == {}
    assert finalize(study) == "confirmed"
    receipt = load_state(study, load_contract(study))["finalization"]
    assert receipt["label"] == "confirmed"
    assert "confirmation_gaps" not in receipt


def test_finalize_degrades_a_track_missing_its_replication_and_names_the_record(
    sealed_study,
) -> None:
    _repo, study, _value, _marker, _manifest = sealed_study
    _require(study, "sealed", "replicate")

    with pytest.raises(WorkflowError, match="no `reproduced: true` replicate record for E0001"):
        finalize(study)

    label = finalize(study, allow_exploratory=True)
    assert label == "exploratory"
    receipt = load_state(study, load_contract(study))["finalization"]
    assert receipt["label"] == "exploratory"
    assert "E0001" in receipt["confirmation_gaps"]["primary"][0]
    assert read_events(study)[-1]["confirmation_gaps"]["primary"]

    # pay for it, and the same study confirms
    assert replicate_run(study, "E0001", echo=False)["reproduced"] is True
    assert finalize(study) == "confirmed"
    assert "confirmation_gaps" not in load_state(study, load_contract(study))["finalization"]


def test_a_failed_replication_does_not_satisfy_the_requirement(sealed_study) -> None:
    _repo, study, value_file, _marker, _manifest = sealed_study
    _require(study, "replicate")
    value_file.write_text("0.900000\n", encoding="utf-8")
    assert replicate_run(study, "E0001", echo=False)["reproduced"] is False
    assert finalize(study, allow_exploratory=True) == "exploratory"
    gaps = load_state(study, load_contract(study))["finalization"]["confirmation_gaps"]
    assert "E0001" in gaps["primary"][0]


def test_a_verify_requirement_wants_a_verify_record_not_a_replicate_one(
    sealed_study,
) -> None:
    _repo, study, _value, _marker, _manifest = sealed_study
    _require(study, "verify")
    assert replicate_run(study, "E0001", echo=False)["reproduced"] is True
    gaps = confirmation_gaps(study, load_contract(study), _manifests(study))
    assert gaps["primary"] == [
        gap for gap in gaps["primary"] if gap.startswith("verify:") and "--verify-only" in gap
    ]
    assert finalize(study, allow_exploratory=True) == "exploratory"


def test_a_registered_track_wants_every_measured_cell(sealed_study) -> None:
    """Frontier confirmation follows the incumbent; registered follows the cells."""
    _repo, study, value_file, _marker, _manifest = sealed_study
    _require(study, "replicate")
    contract = load_contract(study)
    manifests = _manifests(study)
    replicate_run(study, "E0001", echo=False)
    assert confirmation_gaps(study, contract, manifests) == {}

    edit_contract(study, lambda c: c["tracks"]["primary"].update(mode="registered"))
    contract = load_contract(study)
    # E0002 is the sealed run and is excluded from the development cells
    assert confirmation_gaps(study, contract, manifests) == {}
    assert [m["experiment"] for m in manifests if m["evaluation_kind"] == "development"] == [
        "E0001"
    ]


def test_a_registered_track_follows_the_cells_confirmed_claims_cite(sealed_study) -> None:
    """With a lock present the targets are the cells `confirmed` claims cite
    (claims-protocol.md); with no lock every measured cell is required, which
    can only under-confirm a study."""
    import json

    _repo, study, _value, _marker, _manifest = sealed_study
    _require(study, "replicate")
    edit_contract(study, lambda c: c["tracks"]["primary"].update(mode="registered"))
    contract = load_contract(study)
    manifests = _manifests(study)

    # No lock: the fallback wants E0001, the one measured development cell.
    gaps = confirmation_gaps(study, contract, manifests)
    assert "E0001" in gaps["primary"][0]

    lock = study / "claims.lock"
    # A lock whose only confirmed claim cites nothing from this track: the
    # registered track then needs no replication record at all.
    lock.write_text(
        json.dumps(
            {
                "lock_schema": 2,
                "claims": {
                    "C1": {"strength": "exploratory", "evidence": ["E0001"]},
                    "C2": {"strength": "confirmed", "evidence": ["sweep:floor"]},
                },
            }
        ),
        encoding="utf-8",
    )
    assert confirmation_gaps(study, contract, manifests) == {}

    # A confirmed claim that DOES cite the cell puts it back on the list.
    lock.write_text(
        json.dumps(
            {
                "lock_schema": 2,
                "claims": {"C2": {"strength": "confirmed", "evidence": ["E0001", "art:map"]}},
            }
        ),
        encoding="utf-8",
    )
    assert "E0001" in confirmation_gaps(study, contract, manifests)["primary"][0]

    # A legacy lock-schema-1 ledger carries no claim entries: fall back.
    lock.write_text(json.dumps({"claims": {"k": {"value": 1, "art": "a"}}}), encoding="utf-8")
    assert "E0001" in confirmation_gaps(study, contract, manifests)["primary"][0]


def _manifests(study: Path) -> list[dict[str, Any]]:
    from kleinlib.manifest import load_manifests

    return load_manifests(study)


# ---------------------------------------------------------------------------
# 7. the CLI surface
# ---------------------------------------------------------------------------


def test_cli_replicate_exit_codes_and_list(replicable, capsys) -> None:
    _repo, study, value_file, _marker, _manifest = replicable
    assert cli.main(["replicate", "E0001", "--study", str(study), "--quiet"]) == 0
    out = capsys.readouterr().out
    assert "E0001: reproduced (replicate)" in out
    assert "evidence=rep:E0001@" in out

    value_file.write_text("0.900000\n", encoding="utf-8")
    assert cli.main(["replicate", "E0001", "--study", str(study), "--quiet"]) == 1
    assert "NOT reproduced" in capsys.readouterr().out

    assert cli.main(["replicate", "--study", str(study), "--list"]) == 0
    listing = capsys.readouterr().out
    assert listing.count("rep:E0001@") == 2
    assert "summary: 2 records, 1 reproduced" in listing
    assert [row["reproduced"] for row in list_replications(study)] == [True, False]


def test_cli_replicate_refusals_are_exit_2(replicable, capsys) -> None:
    _repo, study, _value, _marker, _manifest = replicable
    assert cli.main(["replicate", "--study", str(study)]) == 2
    assert "an experiment id is required" in capsys.readouterr().err
    assert cli.main(["replicate", "E0001", "--study", str(study), "--list"]) == 2
    assert "drop the experiment id" in capsys.readouterr().err


def test_cli_replicate_help_names_the_documented_flags(capsys) -> None:
    parser = cli.build_parser()
    action = [a for a in parser._subparsers._group_actions if a.dest == "command_name"][0]
    help_text = action.choices["replicate"].format_help()
    for flag in ("--study", "--tolerance", "--verify-only", "--list"):
        assert flag in help_text, flag
    assert callable(parser.parse_args(["replicate", "E0001"]).handler)
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["replicate", "--help"])
    assert exit_info.value.code == 0
    assert "replication-protocol.md" in capsys.readouterr().out


def test_replicate_module_imports_alone_without_the_heavy_stacks() -> None:
    """It sits above `workflow` in the dependency order and stays light."""
    code = (
        "import json, sys, kleinlib.replicate\n"
        "print(json.dumps({n: n in sys.modules for n in ('torch', 'lightgbm', 'sklearn')}))"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code], check=True, capture_output=True, text=True
    )
    assert json.loads(completed.stdout) == {
        "torch": False,
        "lightgbm": False,
        "sklearn": False,
    }
