"""The `stop:` rule — a losing phase ends on the record, not on a hunch.

`knowledge/research-discipline.md` lesson 7: pre-script the branch you think
will not fire. The count is pre-registered in the contract; `run-one` refuses
before allocating an experiment id; `klein stop ack` records which branch the
study takes, and covers that count only.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from kleinlib import cli
from kleinlib.errors import WorkflowError
from kleinlib.events import read_events
from kleinlib.state import load_state
from kleinlib.stop import (
    acknowledge_stop,
    consecutive_discards,
    refuse_if_tripped,
    stop_scope_key,
    stop_spec,
)
from kleinlib.workflow import load_contract, record_gate, run_one


def _m(disposition: str, *, track: str = "primary", phase: str = "p1",
       kind: str = "development") -> dict:
    return {
        "disposition": disposition,
        "track": track,
        "phase": phase,
        "evaluation_kind": kind,
    }


# --------------------------------------------------------------------------
# the counter
# --------------------------------------------------------------------------


def test_discards_accumulate_and_a_keep_resets() -> None:
    runs = [_m("discard"), _m("discard"), _m("keep"), _m("discard")]
    assert consecutive_discards(runs, track="primary") == 1
    assert consecutive_discards(runs[:2], track="primary") == 2
    assert consecutive_discards(runs[:3], track="primary") == 0


def test_a_measured_cell_resets_the_run_like_a_keep() -> None:
    """Registered mode has no keeps; a cell that measured something is progress."""
    runs = [_m("discard"), _m("discard"), _m("measured")]
    assert consecutive_discards(runs, track="primary") == 0


def test_a_crash_neither_counts_nor_resets() -> None:
    """Lesson 8: a crash is evidence, not a verdict about the direction."""
    runs = [_m("discard"), _m("crash"), _m("discard")]
    assert consecutive_discards(runs, track="primary") == 2
    assert consecutive_discards([_m("keep"), _m("crash")], track="primary") == 0


def test_a_sealed_final_test_is_not_an_adaptive_attempt() -> None:
    """It is recorded as a discard by law; it is confirmation evidence."""
    runs = [_m("discard"), _m("discard", kind="final_test"), _m("discard")]
    assert consecutive_discards(runs, track="primary") == 2


def test_track_scope_ignores_other_tracks() -> None:
    runs = [_m("discard"), _m("discard", track="secondary"), _m("discard")]
    assert consecutive_discards(runs, scope="track", track="primary") == 2
    assert consecutive_discards(runs, scope="track", track="secondary") == 1
    assert consecutive_discards(runs, scope="study", track="primary") == 3


def test_phase_scope_counts_only_the_current_phase() -> None:
    runs = [_m("discard", phase="p1"), _m("discard", phase="p2"), _m("discard", phase="p2")]
    assert consecutive_discards(runs, scope="phase", track="primary", phase="p2") == 2
    assert consecutive_discards(runs, scope="phase", track="primary", phase="p1") == 1


def test_scope_keys_do_not_collide_across_scopes() -> None:
    assert stop_scope_key("track", track="primary", phase="p1") == "track:primary"
    assert stop_scope_key("phase", track="primary", phase="p1") == "phase:p1"
    assert stop_scope_key("study", track="primary", phase="p1") == "study"


# --------------------------------------------------------------------------
# the contract block
# --------------------------------------------------------------------------


def test_schema_two_never_grows_a_stop_rule() -> None:
    contract = {"schema_version": 2, "stop": {"max_consecutive_discards": 2}}
    assert stop_spec(contract) is None


def test_schema_three_reads_the_block_and_defaults_the_scope() -> None:
    contract = {"schema_version": 3, "stop": {"max_consecutive_discards": 4}}
    assert stop_spec(contract) == {"max_consecutive_discards": 4, "scope": "track"}
    assert stop_spec({"schema_version": 3}) is None


def test_a_malformed_block_is_left_to_the_contract_check() -> None:
    assert stop_spec({"schema_version": 3, "stop": {"max_consecutive_discards": "many"}}) is None
    assert stop_spec({"schema_version": 3, "stop": []}) is None


# --------------------------------------------------------------------------
# the refusal
# --------------------------------------------------------------------------


CONTRACT3 = {"schema_version": 3, "stop": {"max_consecutive_discards": 2}}


def test_refuse_is_silent_below_the_registered_number() -> None:
    refuse_if_tripped(CONTRACT3, {}, [_m("discard")], track="primary", phase="p1")


def test_refuse_fires_at_the_registered_number() -> None:
    with pytest.raises(WorkflowError, match="stop rule: 2 consecutive discards"):
        refuse_if_tripped(
            CONTRACT3, {}, [_m("discard"), _m("discard")], track="primary", phase="p1"
        )


def test_the_refusal_names_the_verb_and_the_branch_vocabulary() -> None:
    with pytest.raises(WorkflowError) as info:
        refuse_if_tripped(
            CONTRACT3, {}, [_m("discard")] * 3, track="primary", phase="p1"
        )
    message = str(info.value)
    assert "klein stop ack --track primary" in message
    assert "continue:" in message and "stop:" in message
    assert "covers this count only" in message


def test_an_acknowledgement_covers_exactly_the_count_it_was_taken_at(capsys) -> None:
    state = {"stop": {"track:primary": {"count": 2, "acknowledged_at": "now",
                                        "acknowledged_by": "tester", "note": "continue: x"}}}
    refuse_if_tripped(
        CONTRACT3, state, [_m("discard")] * 2, track="primary", phase="p1"
    )
    assert "acknowledged by tester" in capsys.readouterr().out

    # One more discard and the pre-scripted question is asked again.
    with pytest.raises(WorkflowError, match="3 consecutive discards"):
        refuse_if_tripped(
            CONTRACT3, state, [_m("discard")] * 3, track="primary", phase="p1"
        )


def test_a_study_without_a_stop_block_is_never_refused() -> None:
    refuse_if_tripped(
        {"schema_version": 3}, {}, [_m("discard")] * 9, track="primary", phase="p1"
    )


# --------------------------------------------------------------------------
# end to end, through run_one and the CLI
# --------------------------------------------------------------------------


def _declare_stop(study: Path, maximum: int = 1, scope: str | None = None) -> None:
    path = study / "study.yaml"
    contract = yaml.safe_load(path.read_text(encoding="utf-8"))
    contract["stop"] = {"max_consecutive_discards": maximum}
    if scope is not None:
        contract["stop"]["scope"] = scope
    path.write_text(yaml.safe_dump(contract, sort_keys=False), encoding="utf-8")


def _edit(study: Path, marker: str) -> None:
    train = study / "train.py"
    train.write_text(train.read_text(encoding="utf-8") + f"\n# {marker}\n", encoding="utf-8")


@pytest.fixture
def losing_study(ready_study_v3):
    """A schema-3 study with one keep and then one discard, stop limit 1."""
    from test_workflow_v3 import commit_all, metric_command

    repo, study = ready_study_v3
    _declare_stop(study, maximum=1)
    commit_all(repo, "declare the stop rule")
    # study.yaml is a consult-gate artifact: re-record so its hash matches.
    record_gate(study, "consult", acknowledged_by="tester")

    _edit(study, "first")
    assert run_one(study, command=metric_command(0.70), echo=False)["disposition"] == "keep"
    _edit(study, "second")
    assert run_one(study, command=metric_command(0.60), echo=False)["disposition"] == "discard"
    return repo, study


def test_run_one_refuses_once_the_rule_fires(losing_study) -> None:
    from test_workflow_v3 import metric_command

    _repo, study = losing_study
    _edit(study, "third")
    with pytest.raises(WorkflowError, match="stop rule: 1 consecutive discards"):
        run_one(study, command=metric_command(0.65), echo=False)


def test_the_refusal_spends_no_experiment_id_and_no_commit(losing_study) -> None:
    from test_workflow_v3 import git, metric_command

    _repo, study = losing_study
    from kleinlib.manifest import load_manifests

    before = [m["experiment"] for m in load_manifests(study)]
    head_before = git(study, "rev-parse", "HEAD")

    _edit(study, "third")
    with pytest.raises(WorkflowError):
        run_one(study, command=metric_command(0.65), echo=False)

    assert [m["experiment"] for m in load_manifests(study)] == before
    assert git(study, "rev-parse", "HEAD") == head_before
    assert not (study / "runs" / f"E{len(before) + 1:04d}").exists()


def test_ack_unlocks_exactly_one_more_run(losing_study) -> None:
    from test_workflow_v3 import metric_command

    _repo, study = losing_study
    acknowledge_stop(
        study, track="primary", acknowledged_by="tester", note="continue: one more idea"
    )
    _edit(study, "third")
    manifest = run_one(study, command=metric_command(0.65), echo=False)
    assert manifest["disposition"] == "discard"

    # The run of discards is now 2; the pre-scripted question is asked again.
    _edit(study, "fourth")
    with pytest.raises(WorkflowError, match="stop rule: 2 consecutive discards"):
        run_one(study, command=metric_command(0.66), echo=False)


def test_a_keep_clears_the_rule_without_an_ack(losing_study) -> None:
    from test_workflow_v3 import metric_command

    _repo, study = losing_study
    acknowledge_stop(study, track="primary", acknowledged_by="tester", note="continue: x")
    _edit(study, "third")
    assert run_one(study, command=metric_command(0.90), echo=False)["disposition"] == "keep"
    _edit(study, "fourth")
    # Count is back to 0; one discard is below the limit of 1... it reaches it.
    assert run_one(study, command=metric_command(0.10), echo=False)["disposition"] == "discard"


def test_ack_records_the_event_and_files_its_own_state_commit(losing_study) -> None:
    from test_workflow_v3 import git

    repo, study = losing_study
    entry = acknowledge_stop(
        study, track="primary", acknowledged_by="tester", note="continue: one more idea"
    )
    assert entry["count"] == 1
    assert entry["scope"] == "track"

    state = load_state(study, load_contract(study))
    assert state["stop"]["track:primary"] == entry

    events = [e for e in read_events(study) if e["type"] == "stop_acknowledged"]
    assert len(events) == 1 and events[0]["key"] == "track:primary"
    assert git(repo, "status", "--porcelain") == ""
    assert "stop rule acknowledged" in git(repo, "log", "-1", "--pretty=%s")


def test_ack_commits_only_the_record_it_wrote(losing_study, capsys) -> None:
    """E15: an acknowledgement puts a branch on the record, not the whole tree."""
    from test_commit_state_writes import modified_paths, operator_edits, seed_tracked
    from test_workflow_v3 import git

    repo, study = losing_study
    seed_tracked(repo, study, "findings.md")
    operator_edits(study, "findings.md")

    acknowledge_stop(
        study, track="primary", acknowledged_by="tester", note="continue: one more idea"
    )

    committed = set(git(repo, "show", "--name-only", "--format=", "HEAD").splitlines())
    assert committed == {
        "studies/03-demo/study_state.json",
        "studies/03-demo/events.jsonl",
    }
    assert modified_paths(repo) == {"studies/03-demo/findings.md"}
    assert "note: 1 uncommitted edit(s) left in the tree (findings.md)" in capsys.readouterr().out


def test_ack_refuses_before_the_rule_has_fired(ready_study_v3) -> None:
    from test_workflow_v3 import commit_all

    repo, study = ready_study_v3
    _declare_stop(study, maximum=3)
    commit_all(repo, "declare the stop rule")
    with pytest.raises(WorkflowError, match="has not fired"):
        acknowledge_stop(study, track="primary", acknowledged_by="t", note="continue: x")


def test_ack_refuses_a_study_with_no_stop_block(ready_study_v3) -> None:
    _repo, study = ready_study_v3
    with pytest.raises(WorkflowError, match="declares no schema-3 stop: block"):
        acknowledge_stop(study, track="primary", acknowledged_by="t", note="continue: x")


def test_ack_requires_a_branch_note_and_an_actor(losing_study) -> None:
    _repo, study = losing_study
    with pytest.raises(WorkflowError, match="--note is required"):
        acknowledge_stop(study, track="primary", acknowledged_by="t", note="  ")
    with pytest.raises(WorkflowError, match="--acknowledged-by is required"):
        acknowledge_stop(study, track="primary", acknowledged_by=" ", note="continue: x")


def test_ack_refuses_an_unknown_track(losing_study) -> None:
    _repo, study = losing_study
    with pytest.raises(WorkflowError, match="unknown track"):
        acknowledge_stop(study, track="ghost", acknowledged_by="t", note="continue: x")


def test_cli_stop_ack_dispatches_and_reports(losing_study, capsys) -> None:
    _repo, study = losing_study
    rc = cli.main(
        [
            "stop",
            "ack",
            "--study",
            str(study),
            "--track",
            "primary",
            "--acknowledged-by",
            "tester",
            "--note",
            "continue: one more idea",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "acknowledged: 1 consecutive discards" in out
    assert "the next discard asks again" in out
