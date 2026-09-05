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


def test_capability_names_are_typed_before_they_are_available(tmp_path: Path) -> None:
    """Unknown and not-yet-supported are different problems for the driver."""
    from kleinlib.generation.manifest import (
        KNOWN_CAPABILITIES,
        SUPPORTED_CAPABILITIES,
        capability_problems,
    )

    assert set(SUPPORTED_CAPABILITIES) <= set(KNOWN_CAPABILITIES)
    assert "unknown capability" in "; ".join(capability_problems(["telepathy"]))
    # `escalation` is in the vocabulary and ships later — a different problem
    # from a typo, and it stays the example as each package lands.
    assert "escalation" not in SUPPORTED_CAPABILITIES
    assert "not available in this version" in "; ".join(capability_problems(["escalation"]))
    # the dependency table is encoded now, enforced as SUPPORTED grows
    assert "requires 'slates'" in "; ".join(capability_problems(["premortem"]))

    repo, study = _scaffold(tmp_path)
    assert _gen("init", "--study", str(study), "--capability", "telepathy") == 1
    assert _gen("init", "--study", str(study), "--capability", "escalation") == 1
    assert not (study / "generation" / "manifest.yaml").exists()


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
    # expert-parity one), so this is a subset check, not equality.
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
