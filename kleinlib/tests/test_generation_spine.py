"""The generation spine (WP-00): admission before action, verified afterwards.

Test names carry their validation-plan id (V-01 … V-23).  Each material
behaviour gets one valid control and one invalid control, exactly as the
existing loop tests do; the fixtures reuse ``scaffold_study`` + ``record_gate``
+ ``test_workflow_v3``'s ``metric_command`` so a generation study is an ordinary
schema-3 study with one extra step BEFORE the consult gate.

The isolation guards at the bottom are the ones that keep the whole package
optional: core imports nothing from ``kleinlib.generation``, ``kleinlib.cli``
does not import it at module load, and nothing under it reaches the network or
a model SDK.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from test_workflow_v3 import _fill, commit_all, git, metric_command

from kleinlib import cli
from kleinlib.generation import ledger
from kleinlib.scaffold import scaffold_study
from kleinlib.workflow import record_gate, run_one

REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATION_PKG = REPO_ROOT / "kleinlib" / "generation"


# --------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------


def _gen(*argv: str) -> int:
    return cli.main(["generation", *argv])


def _scaffold(tmp_path: Path) -> tuple[Path, Path]:
    """A schema-3 study, committed, with the three gates still UNRECORDED."""
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    (repo / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    study = scaffold_study(
        repo / "studies",
        "03-demo",
        goal="compare a candidate",
        domain="test",
        target="y",
        task_type="classification",
        method_depth="brief",
        family="linear",
        metric_name="val_auc",
        metric_goal="higher",
        data_source="csv:fixture.csv",
        data_path="data/prepared/fixture.csv",
        max_run_seconds=5,
        schema_version=3,
        kind="predict",
        modality="tabular",
        profile="generic",
        audience="the maintainers of this test suite",
    )
    _fill(study)
    data = study / "data" / "prepared"
    data.mkdir(parents=True)
    (data / "fixture.csv").write_text("x,y\n1,0\n2,1\n", encoding="utf-8")
    (study / "data_card.md").write_text(
        "# Data card\n\n> **Decision:** **GO**\n", encoding="utf-8"
    )
    (study / "method_card.md").write_text("# Method card\n\nBrief method.\n", encoding="utf-8")
    commit_all(repo, "scaffolded schema-3 study")
    return repo, study


def _gates(repo: Path, study: Path) -> None:
    record_gate(study, "consult", acknowledged_by="tester")
    record_gate(study, "data", acknowledged_by="tester")
    record_gate(study, "method", acknowledged_by="tester")
    commit_all(repo, "gates recorded")
    git(repo, "switch", "-q", "-c", "experiments/03-demo")


@pytest.fixture
def enabled_study(tmp_path: Path) -> tuple[Path, Path]:
    """A generation-enabled study: ``init`` anchored BEFORE the consult gate."""
    repo, study = _scaffold(tmp_path)
    assert _gen("init", "--study", str(study), "--actor", "tester", "--tool", "pytest") == 0
    _gates(repo, study)
    return repo, study


def _bump(study: Path, marker: str) -> None:
    """One candidate edit to the declared mutable surface."""
    train = study / "train.py"
    train.write_text(train.read_text(encoding="utf-8") + f"\nCANDIDATE = {marker!r}\n", "utf-8")


def _receipt(study: Path) -> dict:
    return json.loads((study / "generation" / "verify_receipt.json").read_text(encoding="utf-8"))


def _statuses(receipt: dict, name: str) -> list[str]:
    return [check["status"] for check in receipt["checks"] if check["name"] == name]


# --------------------------------------------------------------------------
# V-01 — the valid control
# --------------------------------------------------------------------------


def test_v01_valid_control_two_admitted_runs_and_a_deterministic_receipt(enabled_study) -> None:
    """V-01: check → run → check → run → verify PASS, both runs admitted."""
    repo, study = enabled_study
    _bump(study, "one")
    assert _gen("check", "--study", str(study), "--action", "calibration", "--track", "primary") == 0
    assert run_one(study, command=metric_command(0.7), echo=False)["experiment"] == "E0001"
    _bump(study, "two")
    assert _gen("check", "--study", str(study), "--action", "run", "--track", "primary") == 0
    assert run_one(study, command=metric_command(0.9), echo=False)["experiment"] == "E0002"

    assert _gen("verify", "--study", str(study)) == 0
    receipt = _receipt(study)
    assert receipt["runs"] == {"E0001": "admitted", "E0002": "admitted"}
    assert receipt["summary"]["failed"] == 0
    assert receipt["scope"]["capabilities"] == []
    # every receipt was consumed by exactly one run
    assert sorted(entry["consumed_by"] for entry in receipt["receipts"].values()) == [
        "E0001",
        "E0002",
    ]

    # Determinism: at the same HEAD the receipt is a pure function of the study,
    # so a second verify neither rewrites it nor files a commit.
    before = (study / "generation" / "verify_receipt.json").read_bytes()
    head = git(repo, "rev-parse", "HEAD")
    assert _gen("verify", "--study", str(study)) == 0
    assert (study / "generation" / "verify_receipt.json").read_bytes() == before
    assert git(repo, "rev-parse", "HEAD") == head


def test_v01_a_generation_commit_touches_only_generation_paths(enabled_study) -> None:
    """Write ownership: `scope="own"` never sweeps up the operator's tree."""
    repo, study = enabled_study
    _bump(study, "one")
    assert _gen("check", "--study", str(study), "--action", "run", "--track", "primary") == 0
    subject = git(repo, "log", "-1", "--format=%s")
    assert subject.startswith("klein: generation admitted")
    names = git(repo, "show", "--name-only", "--format=", "HEAD").split()
    assert names, "the check filed no paths"
    assert all("/generation/" in f"/{name}" for name in names), names
    # and the candidate edit is still the operator's, uncommitted
    assert "train.py" in git(repo, "status", "--porcelain")


# --------------------------------------------------------------------------
# V-02 — the invalid control: a late opt-in
# --------------------------------------------------------------------------


def test_v02_late_opt_in_is_refused_and_forced_late_fails_forever(tmp_path: Path) -> None:
    """V-02: registration after CONSULT cannot establish the scope freeze."""
    repo, study = _scaffold(tmp_path)
    _gates(repo, study)
    assert _gen("init", "--study", str(study)) != 0
    assert not (study / "generation" / "manifest.yaml").exists()

    assert _gen("init", "--study", str(study), "--allow-late") == 0
    assert (study / "generation" / "manifest.yaml").is_file()
    assert _gen("verify", "--study", str(study)) == 2
    receipt = _receipt(study)
    assert "FAIL" in _statuses(receipt, "generation manifest")
    detail = " ".join(
        check["detail"] for check in receipt["checks"] if check["name"] == "generation manifest"
    )
    assert "late" in detail


def test_v02_an_edited_manifest_fails_the_immutability_check(enabled_study) -> None:
    """Invalid control for R-ADM-1's other half: the opt-in is immutable."""
    repo, study = enabled_study
    path = study / "generation" / "manifest.yaml"
    path.write_text(path.read_text(encoding="utf-8") + "custody: tampered\n", encoding="utf-8")
    commit_all(repo, "tamper with the opt-in")
    assert _gen("verify", "--study", str(study)) == 2
    assert "FAIL" in _statuses(_receipt(study), "generation manifest")


# --------------------------------------------------------------------------
# V-03 / V-04 — isolation from the core, and admission omission
# --------------------------------------------------------------------------


def test_v03a_schema_2_studies_are_refused(ready_study) -> None:
    """V-03(a): nothing schema-2 is ever read for generation checks."""
    _repo, study = ready_study
    assert _gen("init", "--study", str(study)) == 1
    assert not (study / "generation").exists()


def test_v03b_core_verify_never_mentions_generation(ready_study_v3) -> None:
    """V-03(b): installing the package changes no core check name or status."""
    _repo, study = ready_study_v3
    assert cli.main(["verify", "--study", str(study)]) == 0
    receipt = json.loads((study / "verify_receipt.json").read_text(encoding="utf-8"))
    assert not [c for c in receipt["checks"] if c["name"].startswith("generation")]


def _core_check_names(study: Path) -> list[str]:
    receipt = json.loads((study / "verify_receipt.json").read_text(encoding="utf-8"))
    return [check["name"] for check in receipt["checks"]]


def test_v03b_the_core_receipt_shape_is_pinned_with_and_without_a_manifest(
    ready_study_v3,
) -> None:
    """V-03(b), the other half: a DECLARED capability changes no core check.

    A snapshot, not a property: the whole point of R-INV-8 is that the core
    receipt a stranger reads is the same list of checks whether or not the study
    opted in, so the list is written down here and a core check added or renamed
    by the generation layer breaks this test on purpose.
    """
    repo, study = ready_study_v3
    assert cli.main(["verify", "--study", str(study)]) == 0
    before = _core_check_names(study)
    assert before, "the core receipt has no checks"

    # `ready_study_v3` already recorded CONSULT, so this opt-in is a late one —
    # which the GENERATION audit fails and the CORE audit knows nothing about.
    assert _gen("init", "--study", str(study), "--capability", "expertise", "--allow-late") == 0
    assert _gen("verify", "--study", str(study)) == 2

    assert cli.main(["verify", "--study", str(study)]) == 0
    assert _core_check_names(study) == before
    assert not [name for name in before if name.startswith("generation")]
    assert git(repo, "status", "--porcelain") == ""


# --------------------------------------------------------------------------
# D-2 — a study that never opted in is never touched
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("argv", "code"),
    [
        (("verify",), 1),
        (("status",), 0),
        (("recover",), 0),
        (("label",), 2),
        (("check", "--action", "run", "--track", "primary"), 1),
    ],
)
def test_a_non_opted_study_is_left_byte_identical_by_every_verb(
    tmp_path: Path, argv: tuple[str, ...], code: int
) -> None:
    """Not opting in is not a failure, so no verb may manufacture evidence of one.

    `verify` used to CREATE `generation/` and file a FAIL receipt here, which
    turned "this study never opted in" into a permanent failing audit of a study
    that had promised nothing.
    """
    repo, study = _scaffold(tmp_path)
    _gates(repo, study)
    head = git(repo, "rev-parse", "HEAD")
    assert _gen(*argv, "--study", str(study)) == code
    assert not (study / "generation").exists()
    assert git(repo, "rev-parse", "HEAD") == head
    assert git(repo, "status", "--porcelain") == ""


# --------------------------------------------------------------------------
# A-1 / D-1 — a generation commit never sweeps core state
# --------------------------------------------------------------------------


def test_a_dirty_core_state_is_never_swept_into_a_generation_commit(enabled_study) -> None:
    """`scope="own"` prepends study_state.json and events.jsonl; this must not.

    The invalid control is the sweep itself: with the operator's edit to
    `study_state.json` uncommitted, `generation verify` must either refuse or
    file a commit touching only `generation/**`. What it may never do is carry
    somebody else's hand-edit of core state into a generation transaction and
    leave the tree looking clean.
    """
    repo, study = enabled_study
    state = study / "study_state.json"
    state.write_text(state.read_text(encoding="utf-8").rstrip("\n") + "\n\n", encoding="utf-8")
    dirty_before = git(repo, "status", "--porcelain")
    assert "study_state.json" in dirty_before
    head = git(repo, "rev-parse", "HEAD")

    code = _gen("verify", "--study", str(study))
    if code == 1:  # refused: nothing written, nothing filed
        assert git(repo, "rev-parse", "HEAD") == head
        assert git(repo, "status", "--porcelain") == dirty_before
    else:  # filed a receipt: the commit carries generation/** and nothing else
        names = git(repo, "show", "--name-only", "--format=", "HEAD").split()
        assert all("/generation/" in f"/{name}" for name in names), names
    assert "study_state.json" in git(repo, "status", "--porcelain")


def test_the_expert_verbs_file_only_their_own_artifact_and_the_ledger(tmp_path: Path) -> None:
    """A-10: write ownership for a capability verb, read off the commit itself."""
    repo, study = _scaffold(tmp_path)
    assert _gen("init", "--study", str(study), "--capability", "expertise") == 0
    names = git(repo, "show", "--name-only", "--format=", "HEAD").split()
    assert names and all("/generation/" in f"/{name}" for name in names), names


# --------------------------------------------------------------------------
# D-4 — the object store is write-once, and a rewrite is the operator's to undo
# --------------------------------------------------------------------------


def test_a_rewritten_object_blocks_every_writing_verb(enabled_study) -> None:
    """The store is content-addressed: a file that is not its own hash is a tamper."""
    repo, study = enabled_study
    _bump(study, "one")
    assert _gen("check", "--study", str(study), "--action", "run", "--track", "primary") == 0
    objects = sorted((study / "generation" / "objects").glob("*.json"))
    assert objects
    original = objects[-1].read_bytes()
    forged = json.loads(objects[-1].read_text(encoding="utf-8"))
    forged["verdict"] = "admitted"
    forged["reasons"] = ["nothing to see here"]
    objects[-1].write_text(json.dumps(forged, indent=1) + "\n", encoding="utf-8")
    commit_all(repo, "rewrite a stored object in place")

    # every writing verb refuses, and `recover` does NOT undo it
    assert _gen("check", "--study", str(study), "--action", "run", "--track", "primary") == 1
    assert _gen("label", "--study", str(study)) == 1
    head = git(repo, "rev-parse", "HEAD")
    assert _gen("recover", "--study", str(study)) == 0
    assert git(repo, "rev-parse", "HEAD") == head
    assert json.loads(objects[-1].read_text(encoding="utf-8"))["verdict"] == "admitted"

    # and the audit says so out loud rather than raising
    assert _gen("verify", "--study", str(study)) == 2
    detail = " ".join(
        check["detail"] for check in _receipt(study)["checks"] if check["name"] == (
            "generation orphans"
        )
    )
    assert "does not hash to its file name" in detail

    # the valid control: restoring the bytes by hand puts the store back
    objects[-1].write_bytes(original)
    commit_all(repo, "restore the rewritten object")
    assert _gen("check", "--study", str(study), "--action", "run", "--track", "primary") == 0


def test_write_object_refuses_to_complete_a_rewrite(enabled_study) -> None:
    """Invalid control at the API: re-writing an object never overwrites bytes."""
    from kleinlib.errors import WorkflowError

    _repo, study = enabled_study
    payload = {"kind": "probe", "n": 1}
    sha = ledger.write_object(study, payload)
    assert ledger.write_object(study, payload) == sha  # identical bytes are a no-op
    ledger.object_path(study, sha).write_text("{}\n", encoding="utf-8")
    with pytest.raises(WorkflowError, match="write-once"):
        ledger.write_object(study, payload)


# --------------------------------------------------------------------------
# D-7 / D-8 — the checkpoint vocabulary, and an unreadable state
# --------------------------------------------------------------------------


def test_the_check_action_choices_are_the_admission_checkpoints() -> None:
    """The argparse tuple is a duplicate of `admission.CHECKPOINTS`; keep it one."""
    from kleinlib.cli_generation import CHECKPOINT_CHOICES
    from kleinlib.generation.admission import CHECKPOINTS

    assert CHECKPOINT_CHOICES == CHECKPOINTS
    parser = cli.build_parser()
    actions = [a for a in parser._subparsers._group_actions if a.dest == "command_name"]
    sub = [
        a
        for a in actions[0].choices["generation"]._subparsers._group_actions
        if a.dest == "generation_action"
    ][0]
    with pytest.raises(SystemExit):
        cli.main(["generation", "check", "--action", "telepathy", "--track", "primary"])
    assert "cell" in sub.choices["check"].format_help()


def test_an_unreadable_state_is_a_refusal_reason_not_an_empty_state(enabled_study) -> None:
    """D-8: `final_holdout_access` lives in study_state.json — `{}` would admit a seal."""
    repo, study = enabled_study
    _bump(study, "one")
    # valid control: a readable state admits the sealed check
    assert _gen("check", "--study", str(study), "--action", "sealed", "--track", "primary") == 0

    (study / "study_state.json").write_text("{not json", encoding="utf-8")
    commit_all(repo, "study_state.json is unreadable")
    _bump(study, "two")
    assert _gen("check", "--study", str(study), "--action", "sealed", "--track", "primary") == 2
    reasons = " ".join(_last_spine_object(study)["reasons"])
    assert "study_state.json is unreadable" in reasons
    assert "not an empty one" in reasons


def _last_spine_object(study: Path) -> dict:
    events = ledger.read_events(study)
    return ledger.read_object(study, events[-1]["payload_sha256"])


def test_v03c_and_v04_an_unadmitted_run_is_lawful_to_the_core_and_fails_here(
    enabled_study,
) -> None:
    """V-03(c)/V-04: core PASSes and keeps its disposition; the extension FAILs."""
    _repo, study = enabled_study
    _bump(study, "unadmitted")
    manifest = run_one(study, command=metric_command(0.7), echo=False)
    assert manifest["disposition"] == "keep"

    assert cli.main(["verify", "--study", str(study)]) == 0
    core = json.loads((study / "verify_receipt.json").read_text(encoding="utf-8"))
    assert core["summary"]["failed"] == 0
    assert json.loads((study / "runs" / "E0001" / "manifest.json").read_text())["disposition"] == (
        "keep"
    )

    assert _gen("verify", "--study", str(study)) == 2
    receipt = _receipt(study)
    assert receipt["runs"] == {"E0001": "unadmitted"}
    assert "FAIL" in _statuses(receipt, "generation admission")


# --------------------------------------------------------------------------
# V-05 — a receipt written after the action it claims to admit
# --------------------------------------------------------------------------


def test_v05_a_late_admission_does_not_admit_the_run_it_follows(enabled_study) -> None:
    """V-05: the anchor and the ancestry both put the receipt after the run."""
    _repo, study = enabled_study
    _bump(study, "one")
    run_one(study, command=metric_command(0.7), echo=False)
    assert _gen("check", "--study", str(study), "--action", "run", "--track", "primary") == 0
    assert _gen("verify", "--study", str(study)) == 2
    assert _receipt(study)["runs"] == {"E0001": "unadmitted"}


# --------------------------------------------------------------------------
# V-06 — replay
# --------------------------------------------------------------------------


def test_v06_one_receipt_cannot_admit_two_runs(enabled_study) -> None:
    """V-06: `--allow-rerun` twins share one receipt; the second is `replayed`."""
    _repo, study = enabled_study
    _bump(study, "one")
    assert _gen("check", "--study", str(study), "--action", "run", "--track", "primary") == 0
    run_one(study, command=metric_command(0.7), echo=False)
    run_one(study, command=metric_command(0.7), echo=False, allow_rerun=True)

    assert _gen("verify", "--study", str(study)) == 2
    receipt = _receipt(study)
    assert receipt["runs"] == {"E0001": "admitted", "E0002": "replayed"}
    assert "FAIL" in _statuses(receipt, "generation replay")


# --------------------------------------------------------------------------
# V-07 — the receipt bound a surface that is not the one that ran
# --------------------------------------------------------------------------


def test_v07_editing_the_surface_after_the_check_is_a_mismatch(enabled_study) -> None:
    """V-07: a check binds the surface AS ON DISK; editing after it invalidates it."""
    _repo, study = enabled_study
    _bump(study, "one")
    assert _gen("check", "--study", str(study), "--action", "run", "--track", "primary") == 0
    _bump(study, "two")  # the driver changed their mind after being admitted
    run_one(study, command=metric_command(0.7), echo=False)

    assert _gen("verify", "--study", str(study)) == 2
    assert _receipt(study)["runs"] == {"E0001": "mismatched"}


def test_v07_a_second_check_supersedes_the_first_and_the_run_is_admitted(enabled_study) -> None:
    """The lawful path out of a mismatch: re-check the surface you will run."""
    _repo, study = enabled_study
    _bump(study, "one")
    assert _gen("check", "--study", str(study), "--action", "run", "--track", "primary") == 0
    _bump(study, "two")
    assert _gen("check", "--study", str(study), "--action", "run", "--track", "primary") == 0
    run_one(study, command=metric_command(0.7), echo=False)

    assert _gen("verify", "--study", str(study)) == 0
    receipt = _receipt(study)
    assert receipt["runs"] == {"E0001": "admitted"}
    # the superseded receipt was never matched
    consumed = [entry["consumed_by"] for entry in receipt["receipts"].values()]
    assert sorted(consumed, key=lambda value: (value is not None, value)) == [None, "E0001"]
    events = ledger.read_events(study)
    superseding = [e for e in events if e.get("supersedes")]
    assert len(superseding) == 1 and superseding[0]["parent_ids"] == ["G0002"]


# --------------------------------------------------------------------------
# V-08 — a refusal is evidence
# --------------------------------------------------------------------------


def test_v08_running_after_a_refusal_is_recorded_as_refused_but_run(enabled_study) -> None:
    """V-08: the refusal is written first, so ignoring it is detectable."""
    _repo, study = enabled_study
    _bump(study, "one")
    assert (
        _gen(
            "check",
            "--study",
            str(study),
            "--action",
            "run",
            "--track",
            "primary",
            "--hypothesis",
            "H1",
        )
        == 2
    )
    run_one(study, command=metric_command(0.7), echo=False)

    assert _gen("verify", "--study", str(study)) == 2
    receipt = _receipt(study)
    assert receipt["runs"] == {"E0001": "refused-but-run"}
    sha = next(iter(receipt["receipts"]))
    obj = json.loads((study / "generation" / "objects" / f"{sha}.json").read_text(encoding="utf-8"))
    assert obj["verdict"] == "refused"
    assert any("slates capability" in reason for reason in obj["reasons"])


def test_v08_an_undeclared_track_is_refused(enabled_study) -> None:
    """The other spine rule: a receipt cannot admit a track that does not exist."""
    _repo, study = enabled_study
    assert _gen("check", "--study", str(study), "--action", "run", "--track", "ghost") == 2


# --------------------------------------------------------------------------
# V-22 — interrupted writes
# --------------------------------------------------------------------------


def test_v22_an_orphan_object_blocks_check_until_recover_voids_it(enabled_study) -> None:
    """V-22(a): a verb that died after writing its object, before its event."""
    repo, study = enabled_study
    sha = ledger.write_object(study, {"kind": "admission", "interrupted": True})
    path = study / "generation" / "objects" / f"{sha}.json"
    assert path.is_file()

    assert _gen("check", "--study", str(study), "--action", "run", "--track", "primary") == 1
    assert _gen("recover", "--study", str(study)) == 0
    assert path.is_file(), "recover must never delete evidence"
    voided = [e for e in ledger.read_events(study) if e["type"] == "recovered"]
    assert voided and voided[0]["voided_objects"] == [sha]

    assert _gen("verify", "--study", str(study)) == 0
    assert "WARN" in _statuses(_receipt(study), "generation orphans")
    assert git(repo, "status", "--porcelain") == ""


# ---- content addressing (WP-03) ------------------------------------------
def test_an_object_rewritten_in_place_fails_the_content_address_check(enabled_study) -> None:
    """The store is content-addressed: a file that stopped hashing to its name lies."""
    _repo, study = enabled_study
    _bump(study, "one")
    assert _gen("check", "--study", str(study), "--action", "run", "--track", "primary") == 0
    assert _gen("verify", "--study", str(study)) == 0
    assert "PASS" in _statuses(_receipt(study), "generation orphans")

    sha = json.loads(
        (study / "generation" / "events.jsonl").read_text(encoding="utf-8").splitlines()[-1]
    )["payload_sha256"]
    path = study / "generation" / "objects" / f"{sha}.json"
    obj = json.loads(path.read_text(encoding="utf-8"))
    obj["verdict"] = "admitted"  # it already was; the BYTES are what changed
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")

    assert _gen("verify", "--study", str(study)) == 2
    receipt = _receipt(study)
    assert "FAIL" in _statuses(receipt, "generation orphans")
    detail = " ".join(
        check["detail"] for check in receipt["checks"] if check["name"] == "generation orphans"
    )
    assert sha[:12] in detail and "content-addressed" in detail


def test_v22_an_uncommitted_ledger_blocks_check_until_recover_files_it(enabled_study) -> None:
    """V-22(b): a verb that died after its event, before its commit."""
    repo, study = enabled_study
    from kleinlib.generation.admission import core_anchor

    ledger.append_event(
        study,
        "note",
        study="03-demo",
        core_anchor=core_anchor(study),
        git_head=git(repo, "rev-parse", "HEAD"),
    )
    assert git(repo, "status", "--porcelain") != ""
    assert _gen("check", "--study", str(study), "--action", "run", "--track", "primary") == 1
    assert _gen("recover", "--study", str(study)) == 0
    assert git(repo, "status", "--porcelain") == ""
    assert _gen("check", "--study", str(study), "--action", "run", "--track", "primary") == 0


# --------------------------------------------------------------------------
# V-23 — the dual-pass label
# --------------------------------------------------------------------------


def test_v23_the_label_needs_both_audits_and_then_the_findings_line(enabled_study) -> None:
    """V-23: refused without a core pass; issued with both; quoted in findings."""
    repo, study = enabled_study
    _bump(study, "one")
    assert _gen("check", "--study", str(study), "--action", "run", "--track", "primary") == 0
    run_one(study, command=metric_command(0.7), echo=False)

    # no core receipt yet
    assert _gen("label", "--study", str(study)) == 2
    assert not (study / "generation" / "label.json").exists()

    assert cli.main(["verify", "--study", str(study)]) == 0
    assert _gen("verify", "--study", str(study)) == 0
    assert _gen("label", "--study", str(study)) == 0
    label = json.loads((study / "generation" / "label.json").read_text(encoding="utf-8"))
    assert label["label"] == "generation-verified"
    assert label["rung"] == "local-order"
    assert set(label["capabilities"].values()) == {"n/a"}

    # the label exists but findings does not quote it
    assert _gen("verify", "--study", str(study)) == 2
    assert "FAIL" in _statuses(_receipt(study), "generation findings label")

    line = f"Generation label: generation-verified @ {label['git_head'][:12]}"
    (study / "findings.md").write_text(f"# Findings\n\n{line}\n", encoding="utf-8")
    commit_all(repo, "findings quote the label")
    assert _gen("verify", "--study", str(study)) == 0
    assert _statuses(_receipt(study), "generation findings label") == ["PASS"]


def test_v23_c_relabel_after_unrelated_commit(enabled_study) -> None:
    """F-1: an unrelated commit makes the receipt stale — and re-verify un-stales it.

    The receipt is a pure function of the study at one HEAD, so a commit that
    touched only `program.md` leaves the payload identical apart from
    `git_head`. Skipping the rewrite on that ground alone stranded the study:
    the receipt stayed stale, `label` refused forever, and re-running `verify`
    changed nothing. Both properties are asserted here — the refresh, and the
    byte-stability it must not cost.
    """
    repo, study = enabled_study
    _bump(study, "one")
    assert _gen("check", "--study", str(study), "--action", "run", "--track", "primary") == 0
    run_one(study, command=metric_command(0.7), echo=False)
    assert cli.main(["verify", "--study", str(study)]) == 0
    assert _gen("verify", "--study", str(study)) == 0

    # the byte-stability property, at one HEAD: nothing written, nothing filed
    before = (study / "generation" / "verify_receipt.json").read_bytes()
    head = git(repo, "rev-parse", "HEAD")
    assert _gen("verify", "--study", str(study)) == 0
    assert (study / "generation" / "verify_receipt.json").read_bytes() == before
    assert git(repo, "rev-parse", "HEAD") == head
    stale_head = _receipt(study)["git_head"]

    # an ORDINARY, unrelated commit: the lab notebook moved on
    (study / "program.md").write_text(
        (study / "program.md").read_text(encoding="utf-8") + "\nDecision: keep going\n", "utf-8"
    )
    commit_all(repo, "program.md: a later thought")
    assert _gen("label", "--study", str(study)) == 2  # both receipts are stale now

    assert cli.main(["verify", "--study", str(study)]) == 0
    assert _gen("verify", "--study", str(study)) == 0
    # the payload is identical apart from `git_head` — and it was REWRITTEN anyway
    assert _receipt(study)["git_head"] != stale_head
    assert _gen("label", "--study", str(study)) == 0


# --------------------------------------------------------------------------
# F-2 — a run after a refusal is `refused-but-run`, not `replayed`
# --------------------------------------------------------------------------


def test_a_run_after_a_refusal_is_reported_as_refused_but_run(enabled_study) -> None:
    """The NEWEST preceding receipt decides; an older consumed one is not the fact.

    Both classifications FAIL, so the disposition was never wrong — the LABEL
    was: "re-used a spent receipt" is the milder story, and reporting it for a
    driver who was told no and ran anyway understates what happened.
    """
    _repo, study = enabled_study
    _bump(study, "one")
    assert _gen("check", "--study", str(study), "--action", "run", "--track", "primary") == 0
    run_one(study, command=metric_command(0.7), echo=False)

    # a refusal on the SAME track: a hypothesis needs the `slates` capability
    _bump(study, "two")
    assert (
        _gen(
            "check", "--study", str(study), "--action", "run", "--track", "primary",
            "--hypothesis", "03-demo#H1",
        )
        == 2
    )

    # …and the driver ran anyway
    run_one(study, command=metric_command(0.9), echo=False)
    assert _gen("verify", "--study", str(study)) == 2
    assert _receipt(study)["runs"] == {"E0001": "admitted", "E0002": "refused-but-run"}


def test_a_run_re_using_a_spent_receipt_is_still_replayed(enabled_study) -> None:
    """The valid control for the same branch: no refusal, so the fact is replay."""
    _repo, study = enabled_study
    _bump(study, "one")
    assert _gen("check", "--study", str(study), "--action", "run", "--track", "primary") == 0
    run_one(study, command=metric_command(0.7), echo=False)
    _bump(study, "two")
    run_one(study, command=metric_command(0.8), echo=False)
    assert _gen("verify", "--study", str(study)) == 2
    assert _receipt(study)["runs"] == {"E0001": "admitted", "E0002": "replayed"}


def test_v23_a_stale_core_receipt_refuses_the_label(enabled_study) -> None:
    """Invalid control: the study changed under the audit that vouched for it."""
    repo, study = enabled_study
    assert cli.main(["verify", "--study", str(study)]) == 0
    assert _gen("verify", "--study", str(study)) == 0
    (study / "program.md").write_text(
        (study / "program.md").read_text(encoding="utf-8") + "\nlater thought\n", encoding="utf-8"
    )
    commit_all(repo, "the study moved on")
    assert _gen("label", "--study", str(study)) == 2


# --------------------------------------------------------------------------
# the capability registry
# --------------------------------------------------------------------------


def test_capability_names_are_typed_before_they_are_available(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unknown and not-yet-supported are different problems for the driver.

    The not-yet-supported half is SIMULATED rather than borrowed from a name
    that happens not to have shipped: every capability package lands eventually,
    and a test whose meaning depends on one of them still being absent stops
    testing anything the day it arrives.  Dropping a real supported name from
    both registries reproduces the situation exactly — a study carried to an
    older Klein, or to a build that omits a module.
    """
    from kleinlib.generation import manifest as gm

    assert set(gm.SUPPORTED_CAPABILITIES) <= set(gm.KNOWN_CAPABILITIES)
    assert "unknown capability" in "; ".join(gm.capability_problems(["telepathy"]))

    absent = gm.SUPPORTED_CAPABILITIES[-1]
    monkeypatch.setattr(gm, "SUPPORTED_CAPABILITIES", tuple(gm.SUPPORTED_CAPABILITIES[:-1]))
    assert absent in gm.KNOWN_CAPABILITIES and absent not in gm.SUPPORTED_CAPABILITIES
    assert "not available in this version" in "; ".join(gm.capability_problems([absent]))
    # the dependency table is encoded independently of availability
    assert "requires 'slates'" in "; ".join(gm.capability_problems(["premortem"]))

    repo, study = _scaffold(tmp_path)
    assert _gen("init", "--study", str(study), "--capability", "telepathy") == 1
    assert _gen("init", "--study", str(study), "--capability", absent) == 1
    assert not (study / "generation" / "manifest.yaml").exists()


def test_c12_a_receipt_pins_the_declared_capabilities_protocols(tmp_path: Path) -> None:
    """C-12: pinning only the spine's protocol left nine documents unhashed.

    A receipt says which RULES it was taken under.  A surprise study's rules are
    mostly in `surprise-protocol.md`, and hashing only `generation-protocol.md`
    meant that file could be rewritten under a live study without the drift
    warning ever firing.
    """
    import yaml

    from kleinlib.generation import manifest as gm

    assert gm.protocol_keys() == (gm.SPINE_PROTOCOL,)
    assert gm.protocol_keys(["design", "surprise"]) == (
        gm.SPINE_PROTOCOL,
        "references/surprise-protocol.md",
    )
    # parity and contribution share one document, and it is listed once
    assert gm.protocol_keys(["parity", "contribution"]) == (
        gm.SPINE_PROTOCOL,
        "references/expert-parity-protocol.md",
    )
    # every declarable capability's protocol, where it has one, is a real file
    root = REPO_ROOT / gm.SKILL_ROOT
    for key in gm.protocol_keys(gm.SUPPORTED_CAPABILITIES):
        assert (root / key).is_file(), key

    repo, study = _scaffold(tmp_path)
    assert _gen(
        "init", "--study", str(study), "--capability", "design", "--capability", "surprise"
    ) == 0
    manifest = yaml.safe_load((study / "generation" / "manifest.yaml").read_text("utf-8"))
    assert set(manifest["protocol_hashes"]) == {
        "references/generation-protocol.md",
        "references/surprise-protocol.md",
    }
    # the fixture repo has no .claude/skills tree, so every hash is null and
    # drift simply cannot be observed — the KEY SET is what this pins
    assert set(manifest["protocol_hashes"].values()) == {None}
    assert set(gm.protocol_hashes(REPO_ROOT, ["surprise"])) == set(manifest["protocol_hashes"])

    _gates(repo, study)
    _bump(study, "one")
    assert _gen("check", "--study", str(study), "--action", "run", "--track", "primary") == 0
    receipt = _receipt_object(study)
    assert set(receipt["protocol_hashes"]) == set(manifest["protocol_hashes"])

    # and the drift WARN compares like with like — this is the comparison
    # `generation manifest` makes, and it must not fire on an untouched tree
    assert gm.protocol_hashes(repo, ["design", "surprise"]) == manifest["protocol_hashes"]
    _gen("verify", "--study", str(study))
    assert [
        check
        for check in _receipt(study)["checks"]
        if check["name"] == "generation manifest" and check["status"] == "WARN"
    ] == []


def _receipt_object(study: Path) -> dict:
    """The newest admission receipt object in the study's ledger."""
    from kleinlib.generation.admission import load_receipts
    from kleinlib.generation.ledger import read_events, read_object

    receipts = load_receipts(study, read_events(study))
    return read_object(study, receipts[-1].sha)


def test_the_run_classification_vocabulary_has_no_unreachable_values() -> None:
    """Every classification the matcher can emit is exercised by a test above.

    Two candidate values from the design were dropped rather than shipped as
    dead code.  ``stale`` ("another run intervened between the receipt and this
    one") and ``superseded-consumed`` ("the newest receipt preceding the run had
    already been superseded") are both unreachable: a superseding receipt is
    committed before the run that follows it, so it is itself the newest
    preceding receipt and is either eligible (``admitted`` / ``mismatched``) or
    already consumed (``replayed``).  The SAFETY property they protected is
    still enforced — a superseded receipt is never matched to a run — it simply
    reports as ``unadmitted`` when nothing else remains.
    """
    from kleinlib.generation.admission import CLASSIFICATIONS

    assert set(CLASSIFICATIONS) == {
        "admitted",
        "unadmitted",
        "refused-but-run",
        "replayed",
        "mismatched",
    }


def test_init_refuses_a_second_opt_in(enabled_study) -> None:
    _repo, study = enabled_study
    assert _gen("init", "--study", str(study)) == 1


def test_status_is_read_only(enabled_study, capsys) -> None:
    repo, study = enabled_study
    head = git(repo, "rev-parse", "HEAD")
    assert _gen("status", "--study", str(study)) == 0
    assert git(repo, "rev-parse", "HEAD") == head
    assert git(repo, "status", "--porcelain") == ""
    out = capsys.readouterr().out
    assert "generation: enabled for 03-demo" in out
    assert "label: not issued" in out


# --------------------------------------------------------------------------
# isolation guards
# --------------------------------------------------------------------------


def _core_modules() -> list[Path]:
    return [
        path
        for path in sorted((REPO_ROOT / "kleinlib").rglob("*.py"))
        if GENERATION_PKG not in path.parents
        and path.name != "cli_generation.py"
        and "tests" not in path.parts
    ]


def test_no_core_module_imports_the_generation_package() -> None:
    """R-INV-8: legacy execution never depends on the extension."""
    offenders = [
        path.relative_to(REPO_ROOT).as_posix()
        for path in _core_modules()
        if "kleinlib.generation" in path.read_text(encoding="utf-8")
        or "from .generation" in path.read_text(encoding="utf-8")
    ]
    assert not offenders, f"core modules importing the extension: {offenders}"


def test_the_generation_package_reaches_no_network_and_no_model_api() -> None:
    """R-INV-2: no model API call anywhere in kleinlib."""
    banned = ("requests", "httpx", "urllib.request", "anthropic", "openai", "socket")
    offenders: list[str] = []
    files = [*sorted(GENERATION_PKG.rglob("*.py")), REPO_ROOT / "kleinlib" / "cli_generation.py"]
    for path in files:
        text = path.read_text(encoding="utf-8")
        for name in banned:
            if f"import {name}" in text or f"from {name}" in text:
                offenders.append(f"{path.name}: {name}")
    assert not offenders, offenders


def test_importing_the_cli_does_not_import_the_generation_package() -> None:
    """The handlers import lazily, so a defect here cannot break `run-one`."""
    code = (
        "import sys; import kleinlib.cli; "
        "print([m for m in sys.modules if m.startswith('kleinlib.generation')])"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=REPO_ROOT, text=True, capture_output=True, check=False
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "[]", result.stdout


def test_the_generation_verbs_are_registered_with_help(capsys) -> None:
    """`klein generation <verb>` exists with the spelling the protocol documents."""
    parser = cli.build_parser()
    actions = [a for a in parser._subparsers._group_actions if a.dest == "command_name"]
    generation = actions[0].choices["generation"]
    sub = [a for a in generation._subparsers._group_actions if a.dest == "generation_action"][0]
    # The spine's six verbs are permanent; each capability package registers its
    # own sub-group beside them (`expert`/`reference` from the expertise package,
    # `slate` from the slates one, `design` from the evidence-design one,
    # `premortem` from the pre-mortem one, `parity` and `contribution` from the
    # expert-parity one, `escalate` from the escalation one, `knowledge` from the
    # cross-study one, `surprise` from the surprise-mining one, `benchmark` and
    # `custody` from the planted-truth one), so this is a subset check, not
    # equality.
    spine = {"init", "check", "verify", "label", "status", "recover"}
    assert spine <= set(sub.choices)
    assert {
        "expert",
        "reference",
        "slate",
        "design",
        "premortem",
        "parity",
        "contribution",
        "escalate",
        "knowledge",
        "surprise",
        "benchmark",
        "custody",
    } <= set(sub.choices)
    for verb in sorted(spine):
        assert "--study" in sub.choices[verb].format_help(), verb
    for flag in ("--capability", "--predecessor", "--custody-holder", "--allow-late"):
        assert flag in sub.choices["init"].format_help(), flag
    for flag in ("--action", "--track", "--tests", "--hypothesis", "--cell", "--obligation"):
        assert flag in sub.choices["check"].format_help(), flag
    for flag in ("--actor", "--tool", "--model", "--session"):
        assert flag in sub.choices["check"].format_help(), flag

    with pytest.raises(SystemExit) as exit_info:
        cli.main(["generation", "--help"])
    assert exit_info.value.code == 0
    assert "never proposes, ranks, selects, schedules, or retries" in capsys.readouterr().out
