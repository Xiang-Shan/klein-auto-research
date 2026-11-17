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
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from kleinlib import cli
from kleinlib.contract import load_contract
from kleinlib.data import load_partition, partition_fingerprints
from kleinlib.events import append_event
from kleinlib.next_step import next_step
from kleinlib.rehearsal import rehearsal_problem
from kleinlib.workflow import (
    SEALED_DRYRUN_UNACKNOWLEDGED,
    WorkflowError,
    load_manifests,
    read_events,
    record_gate,
    run_one,
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


def test_echo_false_silences_the_fingerprint_but_never_the_acknowledgement(
    dryrun_study, capsys, monkeypatch
) -> None:
    """A registered cell prints its partition through the evaluator's
    `split_fingerprint=` kwarg and passes `echo=False`. That must not silence the
    dry-run acknowledgement: the notary reads its ABSENCE as "the entrypoint
    ignored the flag" and fails the rehearsal (exit 3)."""
    _, study = dryrun_study
    monkeypatch.setenv("KLEIN_EVALUATION_KIND", "final_test")
    monkeypatch.setenv("KLEIN_SEALED_DRYRUN", "1")
    load_partition(study_dir=study, echo=False)
    printed = capsys.readouterr().out
    assert printed.strip() == "sealed_dryrun: 1"
    assert "split_fingerprint" not in printed


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


#: An entrypoint that writes the aux sidecar, the way every real one does.
EVALUATING_ENTRYPOINT = """\
import os

from kleinlib.data import load_partition
from kleinlib.eval import evaluate_scalar

fit_X, eval_X, fit_y, eval_y = load_partition()
evaluate_scalar(
    0.71,
    exp_id=os.environ["KLEIN_EXPERIMENT_ID"],
    metric_name="val_auc",
    metric_goal="higher",
    study_dir=".",
)
"""


def test_a_rehearsal_files_the_aux_rows_it_wrote_and_leaves_a_clean_tree(
    dryrun_study,
) -> None:
    """The rehearsal is mandatory before the sealed run, so it must not leave the
    tree in a state `assert_run_worktree` refuses: the real entrypoint runs (smoke
    is force-cleared), its evaluator appends DRYRUN rows to aux_metrics.tsv, and
    those go into the rehearsal's own state commit."""
    repo, study = dryrun_study
    command = _entrypoint_command(study, EVALUATING_ENTRYPOINT)
    _commit(repo, "an entrypoint that writes aux rows")

    assert sealed_dry_run(study, command=command, echo=False) == 0
    aux = (study / "aux_metrics.tsv").read_text(encoding="utf-8")
    assert any(line.startswith("DRYRUN\t") for line in aux.splitlines())
    assert _git(repo, "status", "--porcelain") == ""

    # A second rehearsal only moves wall_seconds — it must still land clean, or
    # the mandatory step blocks the step it is mandatory for.
    assert sealed_dry_run(study, command=command, echo=False) == 0
    assert _git(repo, "status", "--porcelain") == ""


#: An entrypoint whose evaluator also writes a DRYRUN-keyed table (study 21's
#: multiclass evaluator writes tables/confusion_<id>.tsv).
TABLE_WRITING_ENTRYPOINT = EVALUATING_ENTRYPOINT + """
from pathlib import Path

Path("tables").mkdir(exist_ok=True)
Path("tables/confusion_" + os.environ["KLEIN_EXPERIMENT_ID"] + ".tsv").write_text("a\\tb\\n")
"""


def test_a_rehearsal_files_the_tables_it_wrote_but_nothing_else(dryrun_study) -> None:
    """Found at study 21: the rehearsal's confusion table stayed untracked and the
    dirty tree refused the sealed run. Files the rehearsal created are filed in its
    own commit; an untracked file that predates it is left alone."""
    repo, study = dryrun_study
    command = _entrypoint_command(study, TABLE_WRITING_ENTRYPOINT)
    _commit(repo, "an entrypoint that writes a table")
    (study / "scratch_notes.txt").write_text("mine\n", encoding="utf-8")

    assert sealed_dry_run(study, command=command, echo=False) == 0
    tracked = _git(repo, "ls-files", "--", str(study / "tables"))
    assert tracked.endswith("tables/confusion_DRYRUN.tsv")
    assert _git(repo, "status", "--porcelain") == "?? studies/03-demo/scratch_notes.txt"


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


# ---------------------------------------------------------------------------
# The rule: a sealed run is refused unless the track's latest rehearsal passed,
# on the same command, over the same mutable surface (kleinlib/rehearsal.py)
# ---------------------------------------------------------------------------


@pytest.fixture
def sealed_ready(dryrun_study) -> tuple[Path, Path]:
    """A study one step from its sealed look: ``train.py`` is an honest entrypoint
    (the contract's own command runs it), one development run is on the ledger, the
    adaptive phase is acknowledged, and the tree is clean."""
    repo, study = dryrun_study
    train = study / "train.py"
    train.write_text(HONEST_ENTRYPOINT, encoding="utf-8")
    _commit(repo, "an honest entrypoint")
    train.write_text(HONEST_ENTRYPOINT + "# the one development candidate\n", encoding="utf-8")
    run_one(study, description="baseline", echo=False)
    record_gate(study, "phase", phase="adaptive-1", acknowledged_by="tester")
    _commit(repo, "acknowledge the adaptive phase")
    assert _git(repo, "status", "--porcelain") == ""
    return repo, study


def _rehearsal_command(study: Path) -> str:
    return f"klein run-one --study {study} --track primary --final-test --dry-run"


def _assert_refused(study: Path, reason: str, *, command: list[str] | None = None) -> str:
    with pytest.raises(WorkflowError, match="is not rehearsed") as raised:
        run_one(study, final_test=True, command=command, echo=False)
    message = str(raised.value)
    assert reason in message
    return message


def test_a_sealed_run_with_no_rehearsal_is_refused_and_spends_nothing(sealed_ready) -> None:
    repo, study = sealed_ready
    head = _git(repo, "rev-parse", "HEAD")
    runs = sorted(p.name for p in (study / "runs").glob("E*"))
    events = len(read_events(study))

    message = _assert_refused(study, "no rehearsal is on record")

    assert "track 'primary'" in message
    assert _rehearsal_command(study) in message
    assert sorted(p.name for p in (study / "runs").glob("E*")) == runs
    assert _state(study)["final_holdout_access"]["primary"]["count"] == 0
    assert len(read_events(study)) == events
    assert [e["type"] for e in read_events(study)].count("run_started") == 1  # the baseline only
    assert _git(repo, "rev-parse", "HEAD") == head
    assert _git(repo, "status", "--porcelain") == ""


def test_a_rehearsal_that_crashed_does_not_count(sealed_ready) -> None:
    _, study = sealed_ready
    crash = _entrypoint_command(study, "raise SystemExit(9)\n")
    assert sealed_dry_run(study, command=crash, echo=False) == 9
    _assert_refused(study, "failed with exit code 9", command=crash)


def test_a_rehearsal_without_the_acknowledgement_does_not_count(sealed_ready) -> None:
    _, study = sealed_ready
    blind = _entrypoint_command(study, BLIND_ENTRYPOINT)
    assert sealed_dry_run(study, command=blind, echo=False) == SEALED_DRYRUN_UNACKNOWLEDGED
    _assert_refused(study, "never printed `sealed_dryrun: 1`", command=blind)


def test_a_rehearsal_that_timed_out_does_not_count_even_if_it_acknowledged(sealed_ready) -> None:
    _, study = sealed_ready
    slow = _entrypoint_command(
        study,
        "import time\nprint('sealed_dryrun: 1', flush=True)\ntime.sleep(30)\n",
    )
    assert sealed_dry_run(study, command=slow, timeout_seconds=1, echo=False) != 0
    event = read_events(study)[-1]
    assert (event["timed_out"], event["acknowledged"]) == (True, True)
    _assert_refused(study, "timed out", command=slow)


def test_editing_the_mutable_surface_after_a_rehearsal_refuses_the_sealed_run(
    sealed_ready,
) -> None:
    repo, study = sealed_ready
    assert sealed_dry_run(study, echo=False) == 0

    train = study / "train.py"
    train.write_text(train.read_text(encoding="utf-8") + "# edited after the rehearsal\n",
                     encoding="utf-8")
    _commit(repo, "edit the entrypoint after rehearsing")
    assert _git(repo, "status", "--porcelain") == ""  # clean: only the rehearsal rule objects
    _assert_refused(study, "the code changed")

    assert sealed_dry_run(study, echo=False) == 0
    assert run_one(study, final_test=True, echo=False)["evaluation_kind"] == "final_test"


def test_a_failing_rehearsal_after_a_passing_one_is_a_refusal(sealed_ready, tmp_path) -> None:
    _, study = sealed_ready
    flag = tmp_path / "fail.flag"
    command = _entrypoint_command(
        study,
        "import pathlib, sys\n"
        "print('sealed_dryrun: 1')\n"
        f"sys.exit(5 if pathlib.Path({str(flag)!r}).exists() else 0)\n",
    )
    assert sealed_dry_run(study, command=command, echo=False) == 0
    assert rehearsal_problem(study, load_contract(study), "primary", command=command) is None

    flag.write_text("fail the next rehearsal\n", encoding="utf-8")
    assert sealed_dry_run(study, command=command, echo=False) == 5
    _assert_refused(study, "failed with exit code 5", command=command)


def test_a_rehearsal_of_a_different_command_does_not_cover_the_sealed_run(sealed_ready) -> None:
    _, study = sealed_ready
    rehearsed = [sys.executable, "train.py"]
    assert sealed_dry_run(study, command=rehearsed, echo=False) == 0
    _assert_refused(study, "ran a different command", command=[sys.executable, "-u", "train.py"])


def test_a_rehearsal_event_without_a_surface_digest_predates_the_rule(sealed_ready) -> None:
    repo, study = sealed_ready
    command = [sys.executable, "-u", "train.py"]
    # Exactly what an older engine wrote: no surface_digest.
    append_event(
        study, "sealed_dryrun", track="primary", command=command, log="x",
        exit_code=0, timed_out=False, acknowledged=True, wall_seconds=0.1,
    )
    _commit(repo, "an old-style rehearsal event")
    _assert_refused(study, "predates the surface digest", command=command)


def test_rehearse_then_seal_succeeds_and_the_event_pins_the_surface(sealed_ready) -> None:
    repo, study = sealed_ready
    assert sealed_dry_run(study, echo=False) == 0
    event = read_events(study)[-1]
    assert event["type"] == "sealed_dryrun"
    assert re.fullmatch(r"[0-9a-f]{64}", event["surface_digest"])

    manifest = run_one(study, final_test=True, echo=False)

    assert manifest["evaluation_kind"] == "final_test"
    assert _state(study)["final_holdout_access"]["primary"]["count"] == 1
    assert _git(repo, "status", "--porcelain") == ""


def test_next_step_names_the_rehearsal_until_the_latest_one_passes(sealed_ready) -> None:
    _, study = sealed_ready

    def argv() -> list[str]:
        return next_step(study)["next"]["argv"]

    assert argv()[-2:] == ["--final-test", "--dry-run"]  # no rehearsal yet

    slow = _entrypoint_command(
        study, "import time\nprint('sealed_dryrun: 1', flush=True)\ntime.sleep(30)\n"
    )
    sealed_dry_run(study, command=slow, timeout_seconds=1, echo=False)
    assert argv()[-2:] == ["--final-test", "--dry-run"]  # timed out

    sealed_dry_run(study, command=_entrypoint_command(study, "raise SystemExit(9)\n"), echo=False)
    assert argv()[-2:] == ["--final-test", "--dry-run"]  # failed

    assert sealed_dry_run(study, echo=False) == 0
    after = argv()
    assert "--final-test" in after and "--dry-run" not in after  # the real sealed run


def test_rehearsal_problem_is_none_only_after_a_passing_rehearsal(sealed_ready) -> None:
    _, study = sealed_ready
    contract = load_contract(study)
    assert rehearsal_problem(study, contract, "primary") == "no rehearsal is on record"

    assert sealed_dry_run(study, echo=False) == 0
    assert rehearsal_problem(study, contract, "primary") is None
    assert "different command" in (
        rehearsal_problem(study, contract, "primary", command=["python", "other.py"]) or ""
    )
    assert rehearsal_problem(study, contract, "other-track") == "no rehearsal is on record"
