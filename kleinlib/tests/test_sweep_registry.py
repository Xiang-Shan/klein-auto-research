"""`klein sweep register` — a measurement sweep becomes citable, hashed evidence.

A measurement sweep promotes no winner and writes no `results.tsv` row
(`references/sweep-rules.md`, the carve-out), so its sidecar IS the evidence.
Registering hashes the sidecar and the script; `klein verify` re-hashes them,
and a sidecar edited afterwards fails.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_commit_state_writes import modified_paths, operator_edits, seed_tracked

from kleinlib import cli
from kleinlib.checks import sweep_registry_problems, verify_study
from kleinlib.cli_sweep import register_sweep, sidecar_row_counts
from kleinlib.errors import WorkflowError
from kleinlib.events import read_events
from kleinlib.state import load_state
from kleinlib.sweep import SIDECAR_COLUMNS
from kleinlib.workflow import load_contract

SIDECAR = (
    "\t".join(SIDECAR_COLUMNS) + "\n"
    '1\t{"seed": 1}\t0.500000\t1.0\tok\t\n'
    '2\t{"seed": 2}\t0.520000\t1.0\tok\t\n'
    '3\t{"seed": 3}\t0.480000\t1.0\tok\t\n'
    '4\t{"seed": 4}\tNA\t0.1\tcrash\tValueError: singular matrix\n'
)


@pytest.fixture
def study_with_sweep(ready_study) -> tuple[Path, Path]:
    repo, study = ready_study
    sweeps = study / "sweeps"
    sweeps.mkdir(exist_ok=True)
    (sweeps / "noise_floor.sidecar.tsv").write_text(SIDECAR, encoding="utf-8")
    (sweeps / "noise_floor.py").write_text("# the frozen measurement\n", encoding="utf-8")
    from test_workflow_v2 import commit_all

    commit_all(repo, "sweep evidence")
    return repo, study


def _register(study: Path) -> dict:
    return register_sweep(
        study,
        "noise_floor",
        sidecar=Path("sweeps/noise_floor.sidecar.tsv"),
        script=Path("sweeps/noise_floor.py"),
    )


def test_register_hashes_both_files_and_counts_ok_and_crash_rows(study_with_sweep) -> None:
    _repo, study = study_with_sweep
    record = _register(study)

    assert record["sidecar"] == "sweeps/noise_floor.sidecar.tsv"
    assert record["script"] == "sweeps/noise_floor.py"
    assert len(record["sidecar_sha256"]) == 64
    assert len(record["script_sha256"]) == 64
    # Crash rows are DATA: counted and kept, never filtered away.
    assert (record["rows_ok"], record["rows_crash"]) == (3, 1)
    assert record["registered_at"]

    state = load_state(study, load_contract(study))
    assert state["sweeps"]["noise_floor"] == record


def test_register_logs_the_event_and_files_its_own_state_commit(study_with_sweep) -> None:
    repo, study = study_with_sweep
    _register(study)

    events = [e for e in read_events(study) if e["type"] == "sweep_registered"]
    assert len(events) == 1
    assert events[0]["sweep"] == "noise_floor"
    assert events[0]["rows_crash"] == 1

    from test_workflow_v2 import git

    assert git(repo, "status", "--porcelain") == ""
    assert "measurement sweep registered" in git(repo, "log", "-1", "--pretty=%s")


def test_register_files_the_evidence_it_hashes_and_nothing_else(ready_study, capsys) -> None:
    """E15: the sidecar and the script ARE the measurement, so they must land.

    Everything else stays the operator's: a ``klein: measurement sweep
    registered`` commit that also swept a findings draft would put the digests
    and an unrelated sentence on the record under one subject line.
    """
    repo, study = ready_study
    seed_tracked(repo, study, "findings.md")
    sweeps = study / "sweeps"
    sweeps.mkdir(exist_ok=True)
    (sweeps / "noise_floor.sidecar.tsv").write_text(SIDECAR, encoding="utf-8")
    (sweeps / "noise_floor.py").write_text("# the frozen measurement\n", encoding="utf-8")
    operator_edits(study, "findings.md")

    _register(study)

    from test_workflow_v2 import git

    committed = set(git(repo, "show", "--name-only", "--format=", "HEAD").splitlines())
    assert committed == {
        "studies/03-demo/sweeps/noise_floor.sidecar.tsv",
        "studies/03-demo/sweeps/noise_floor.py",
        "studies/03-demo/study_state.json",
        "studies/03-demo/events.jsonl",
    }
    assert modified_paths(repo) == {"studies/03-demo/findings.md"}
    assert "note: 1 uncommitted edit(s) left in the tree (findings.md)" in capsys.readouterr().out


def test_verify_fails_when_a_registered_sidecar_changed(study_with_sweep) -> None:
    _repo, study = study_with_sweep
    _register(study)
    assert not [c for c in verify_study(study) if not c.ok]

    sidecar = study / "sweeps" / "noise_floor.sidecar.tsv"
    sidecar.write_text(SIDECAR.replace("0.520000", "0.999000"), encoding="utf-8")

    failures = [c for c in verify_study(study) if not c.ok]
    assert [c.name for c in failures] == ["registered sweeps"]
    assert "changed after registration" in failures[0].message
    assert "sweeps/noise_floor.sidecar.tsv" in failures[0].message


def test_verify_fails_when_the_registered_script_changed(study_with_sweep) -> None:
    """The rule that produced the rows must not change after the rows are quoted."""
    _repo, study = study_with_sweep
    _register(study)
    (study / "sweeps" / "noise_floor.py").write_text("# edited\n", encoding="utf-8")

    failures = [c for c in verify_study(study) if not c.ok]
    assert "script sweeps/noise_floor.py changed after registration" in failures[0].message


def test_verify_fails_when_a_registered_file_is_deleted(study_with_sweep) -> None:
    _repo, study = study_with_sweep
    _register(study)
    (study / "sweeps" / "noise_floor.sidecar.tsv").unlink()

    failures = [c for c in verify_study(study) if not c.ok]
    assert "sidecar is missing" in failures[0].message


def test_a_study_with_no_registered_sweep_gains_no_check_line(study_with_sweep) -> None:
    """Silent like the claims law without a lock — schema-2 output is unchanged."""
    _repo, study = study_with_sweep
    assert "registered sweeps" not in {c.name for c in verify_study(study)}
    _register(study)
    assert "registered sweeps" in {c.name for c in verify_study(study)}


def test_re_registering_replaces_the_record_and_keeps_both_events(study_with_sweep) -> None:
    _repo, study = study_with_sweep
    first = _register(study)
    sidecar = study / "sweeps" / "noise_floor.sidecar.tsv"
    sidecar.write_text(SIDECAR + '5\t{"seed": 5}\t0.510000\t1.0\tok\t\n', encoding="utf-8")
    second = _register(study)

    assert second["sidecar_sha256"] != first["sidecar_sha256"]
    assert second["rows_ok"] == 4
    assert len([e for e in read_events(study) if e["type"] == "sweep_registered"]) == 2
    assert not [c for c in verify_study(study) if not c.ok]


def test_paths_outside_the_study_are_refused(study_with_sweep, tmp_path) -> None:
    _repo, study = study_with_sweep
    stray = tmp_path / "stray.tsv"
    stray.write_text(SIDECAR, encoding="utf-8")
    with pytest.raises(WorkflowError, match="outside the study directory"):
        register_sweep(
            study, "stray", sidecar=stray, script=Path("sweeps/noise_floor.py")
        )


def test_a_missing_file_is_refused(study_with_sweep) -> None:
    _repo, study = study_with_sweep
    with pytest.raises(WorkflowError, match="--script does not exist"):
        register_sweep(
            study,
            "noise_floor",
            sidecar=Path("sweeps/noise_floor.sidecar.tsv"),
            script=Path("sweeps/absent.py"),
        )


def test_a_file_that_is_not_a_sidecar_is_refused(study_with_sweep) -> None:
    _repo, study = study_with_sweep
    bogus = study / "sweeps" / "bogus.tsv"
    bogus.write_text("a\tb\n1\t2\n", encoding="utf-8")
    with pytest.raises(WorkflowError, match="is not a sweep sidecar"):
        register_sweep(
            study, "bogus", sidecar=bogus, script=Path("sweeps/noise_floor.py")
        )


def test_a_hand_edited_status_is_refused(study_with_sweep) -> None:
    _repo, study = study_with_sweep
    doctored = study / "sweeps" / "doctored.sidecar.tsv"
    doctored.write_text(SIDECAR.replace("\tcrash\t", "\tretried\t"), encoding="utf-8")
    with pytest.raises(WorkflowError, match="neither 'ok' nor 'crash'"):
        register_sweep(
            study, "doctored", sidecar=doctored, script=Path("sweeps/noise_floor.py")
        )


def test_an_empty_sidecar_registers_nothing(study_with_sweep) -> None:
    _repo, study = study_with_sweep
    empty = study / "sweeps" / "empty.sidecar.tsv"
    empty.write_text("\t".join(SIDECAR_COLUMNS) + "\n", encoding="utf-8")
    with pytest.raises(WorkflowError, match="no trial rows"):
        register_sweep(
            study, "empty", sidecar=empty, script=Path("sweeps/noise_floor.py")
        )


def test_sidecar_row_counts_reads_the_canonical_columns(tmp_path) -> None:
    path = tmp_path / "s.tsv"
    path.write_text(SIDECAR, encoding="utf-8")
    assert sidecar_row_counts(path) == (3, 1)


def test_sweep_registry_problems_is_empty_without_a_registry(tmp_path) -> None:
    assert sweep_registry_problems(tmp_path, {}) == []
    assert sweep_registry_problems(tmp_path, {"sweeps": {}}) == []


def test_a_corrupt_registry_entry_is_reported_not_ignored(tmp_path) -> None:
    problems = sweep_registry_problems(tmp_path, {"sweeps": {"a": "not a mapping"}})
    assert problems == ["sweep:a record is not a mapping"]
    problems = sweep_registry_problems(tmp_path, {"sweeps": {"a": {"sidecar": "x"}}})
    assert any("no recorded sidecar path/hash" in p for p in problems)


def test_cli_registers_through_the_generic_handler(study_with_sweep, capsys) -> None:
    _repo, study = study_with_sweep
    rc = cli.main(
        [
            "sweep",
            "register",
            "--study",
            str(study),
            "noise_floor",
            "--sidecar",
            "sweeps/noise_floor.sidecar.tsv",
            "--script",
            "sweeps/noise_floor.py",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "registered sweep:noise_floor" in out
    assert "3 ok, 1 crash" in out
    assert "crash rows are retained evidence" in out
    state = json.loads((study / "study_state.json").read_text(encoding="utf-8"))
    assert "noise_floor" in state["sweeps"]
