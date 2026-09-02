"""E4 — ``klein run-one --final-test --dry-run``: rehearse, spend nothing.

War story 9: a study's only sealed access was spent by a crash before any data
was read. The seal was gone and the study could never confirm anything. The dry
run is the fix and it is mandatory before every real sealed run — so the one
property this module pins hardest is that a dry run leaves the study exactly as
it found it: no experiment id, no candidate commit, no manifest, no results row,
and above all no spent seal.

The second property is that the rehearsal cannot succeed by accident. An
entrypoint that ignores ``KLEIN_SEALED_DRYRUN`` would have read the sealed rows;
exiting 0 without printing the acknowledgement is therefore a FAILURE (exit 3),
not a pass.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from kleinlib import cli
from kleinlib.data import load_partition, partition_fingerprints
from kleinlib.workflow import (
    SEALED_DRYRUN_UNACKNOWLEDGED,
    WorkflowError,
    load_manifests,
    read_events,
    record_gate,
    sealed_dry_run,
)


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def _commit(repo: Path, message: str) -> None:
    _git(repo, "add", "-A")
    if _git(repo, "status", "--porcelain") == "":
        return
    _git(repo, "-c", "user.name=T", "-c", "user.email=t@e.invalid", "commit", "-q", "-m", message)


#: An entrypoint that routes its partition through the contract — so the dry-run
#: flag reaches it the only way it ever does in a real study.
HONEST_ENTRYPOINT = """\
from kleinlib.data import load_partition

fit_X, eval_X, fit_y, eval_y = load_partition()
print("primary_metric:    0.71")
print("metric_name:       val_auc")
print("metric_goal:       higher")
"""

#: An entrypoint that builds its own partition and ignores the flag entirely.
BLIND_ENTRYPOINT = """\
print("primary_metric:    0.71")
print("metric_name:       val_auc")
print("metric_goal:       higher")
"""


@pytest.fixture
def dryrun_study(ready_study_v3) -> tuple[Path, Path]:
    repo, study = ready_study_v3
    frame = pd.DataFrame({"x": range(60), "y": [i % 2 for i in range(60)]})
    frame.to_csv(study / "data" / "prepared" / "fixture.csv", index=False)
    record_gate(study, "data", acknowledged_by="tester")
    _commit(repo, "sixty rows, split frozen")
    return repo, study


def _state(study: Path) -> dict:
    return json.loads((study / "study_state.json").read_text(encoding="utf-8"))


def _entrypoint_command(study: Path, source: str) -> list[str]:
    (study / "dryrun_entry.py").write_text(source, encoding="utf-8")
    return [sys.executable, "-u", "dryrun_entry.py"]


# ---------------------------------------------------------------------------
# The substitution itself
# ---------------------------------------------------------------------------


def test_load_partition_substitutes_development_and_says_so(
    dryrun_study, capsys, monkeypatch
) -> None:
    _, study = dryrun_study
    monkeypatch.setenv("KLEIN_EVALUATION_KIND", "final_test")
    monkeypatch.setenv("KLEIN_SEALED_DRYRUN", "1")
    _, eval_X, _, _ = load_partition(study_dir=study)
    printed = capsys.readouterr().out

    fingerprints = partition_fingerprints(study)
    assert f"split_fingerprint: {fingerprints['development']}" in printed
    assert fingerprints["final_test"] not in printed
    assert "sealed_dryrun: 1" in printed
    assert len(eval_X) == len(load_partition("development", study_dir=study, echo=False)[1])


# ---------------------------------------------------------------------------
# The rehearsal spends nothing
# ---------------------------------------------------------------------------


def test_a_dry_run_spends_no_id_commit_manifest_row_or_seal(dryrun_study, capsys) -> None:
    repo, study = dryrun_study
    command = _entrypoint_command(study, HONEST_ENTRYPOINT)
    _commit(repo, "a rehearsable entrypoint")
    head_before = _git(repo, "rev-parse", "HEAD")
    results_before = (study / "results.tsv").read_text(encoding="utf-8")
    seal_before = _state(study)["final_holdout_access"]["primary"]

    assert sealed_dry_run(study, command=command, echo=True) == 0
    assert "sealed dry-run OK" in capsys.readouterr().out

    assert load_manifests(study) == []
    assert not list((study / "runs").glob("E*"))
    assert (study / "results.tsv").read_text(encoding="utf-8") == results_before
    assert _state(study)["final_holdout_access"]["primary"] == seal_before
    assert _state(study)["last_experiment"] == 0
    # The only trace is a log and an event — filed in ONE state commit.
    logs = sorted((study / "sweeps").glob("sealed_dryrun.*.log"))
    assert len(logs) == 1
    event = read_events(study)[-1]
    assert event["type"] == "sealed_dryrun"
    assert event["acknowledged"] is True
    assert event["log"] == f"sweeps/{logs[0].name}"
    assert _git(repo, "rev-parse", "HEAD") != head_before  # the receipt is committed
    assert _git(repo, "status", "--porcelain") == ""


def test_the_real_sealed_run_is_still_available_after_a_rehearsal(dryrun_study) -> None:
    """The whole point: rehearsing does not consume the one look."""
    repo, study = dryrun_study
    command = _entrypoint_command(study, HONEST_ENTRYPOINT)
    _commit(repo, "a rehearsable entrypoint")
    assert sealed_dry_run(study, command=command, echo=False) == 0
    assert sealed_dry_run(study, command=command, echo=False) == 0  # and again
    assert _state(study)["final_holdout_access"]["primary"]["count"] == 0


# ---------------------------------------------------------------------------
# The rehearsal cannot succeed by accident
# ---------------------------------------------------------------------------


def test_an_entrypoint_that_ignores_the_flag_fails_with_exit_3(dryrun_study, capsys) -> None:
    repo, study = dryrun_study
    command = _entrypoint_command(study, BLIND_ENTRYPOINT)
    _commit(repo, "an entrypoint that would have read the sealed rows")

    assert sealed_dry_run(study, command=command, echo=True) == SEALED_DRYRUN_UNACKNOWLEDGED
    out = capsys.readouterr().out
    assert "sealed dry-run FAILED" in out
    assert "never printed `sealed_dryrun: 1`" in out
    assert read_events(study)[-1]["acknowledged"] is False
    assert _state(study)["final_holdout_access"]["primary"]["count"] == 0


def test_a_crashing_rehearsal_reports_the_real_exit_code(dryrun_study, capsys) -> None:
    repo, study = dryrun_study
    command = _entrypoint_command(study, "raise SystemExit(9)\n")
    _commit(repo, "a rehearsal that crashes")
    assert sealed_dry_run(study, command=command, echo=True) == 9
    assert "the seal is intact" in capsys.readouterr().out
    assert _state(study)["final_holdout_access"]["primary"]["count"] == 0


# ---------------------------------------------------------------------------
# The CLI surface
# ---------------------------------------------------------------------------


def test_cli_routes_final_test_dry_run_and_returns_its_exit_code(
    dryrun_study, capsys
) -> None:
    repo, study = dryrun_study
    _entrypoint_command(study, HONEST_ENTRYPOINT)
    _commit(repo, "a rehearsable entrypoint")
    argv = [
        "run-one", "--study", str(study), "--final-test", "--dry-run",
        "--command", sys.executable, "-u", "dryrun_entry.py",
    ]
    assert cli.main(argv) == 0
    assert "sealed dry-run OK" in capsys.readouterr().out


def test_dry_run_without_final_test_is_refused(dryrun_study, capsys) -> None:
    _, study = dryrun_study
    assert cli.main(["run-one", "--study", str(study), "--dry-run"]) != 0
    assert "--dry-run rehearses a sealed run" in capsys.readouterr().err


def test_a_rehearsal_adjudicates_nothing(dryrun_study, capsys) -> None:
    """Development data cannot decide a registered prediction."""
    _, study = dryrun_study
    rc = cli.main(
        ["run-one", "--study", str(study), "--final-test", "--dry-run", "--tests", "P1"]
    )
    assert rc != 0
    assert "--dry-run adjudicates nothing" in capsys.readouterr().err


def test_dry_run_refuses_an_unknown_track(dryrun_study) -> None:
    _, study = dryrun_study
    with pytest.raises(WorkflowError, match="unknown track"):
        sealed_dry_run(study, track="ghost", echo=False)
