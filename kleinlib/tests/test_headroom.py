"""Detection-limit (headroom) audit: schema, disclosure, ack, and run gating.

Study 07's lesson: a measured floor can honestly outgrow the incumbent's whole
distance to perfection (anchor Brier 0.026744 vs minimum_delta 0.033 put the
keep bar below zero) and nothing in the harness said so — the impossibility
was discovered by hand between rounds. These tests pin the fix: klein now
computes h = (incumbent - ideal) / minimum_delta the moment both exist,
discloses it at preflight/verify, and (by default) refuses to spend further
development transactions until the closed door is acknowledged on the record.
"""

from __future__ import annotations

import pytest
import yaml
from test_workflow_v2 import commit_all, metric_command

from kleinlib import cli
from kleinlib.workflow import (
    WorkflowError,
    acknowledge_headroom,
    load_state,
    preflight_checks,
    record_gate,
    run_one,
    track_headroom,
    validate_contract,
    verify_event_chain,
    verify_study,
)


def headroom_checks(study):
    return [
        c
        for c in preflight_checks(study, require_clean=False, require_branch=False)
        if c.name == "headroom"
    ]


def set_metric(repo, study, **fields):
    """Rewrite the primary track's metric block, re-record consult, commit."""
    contract = yaml.safe_load((study / "study.yaml").read_text(encoding="utf-8"))
    contract["tracks"]["primary"]["metric"].update(fields)
    (study / "study.yaml").write_text(
        yaml.safe_dump(contract, sort_keys=False), encoding="utf-8"
    )
    record_gate(study, "consult", acknowledged_by="tester", note="metric amended")
    commit_all(repo, "metric amended")


def seed_keep(study, value=0.9):
    manifest = run_one(study, command=metric_command(value), echo=False)
    assert manifest["disposition"] == "keep"
    return manifest


def test_track_headroom_math() -> None:
    # goal lower, ideal 0: h = incumbent / delta (the study-07 arithmetic)
    assert track_headroom(0.026744, ideal=0.0, minimum_delta=0.033, goal="lower") == pytest.approx(0.8104, abs=1e-4)
    # goal higher, ideal 1
    assert track_headroom(0.9, ideal=1.0, minimum_delta=0.05, goal="higher") == pytest.approx(2.0)
    # undefined without an incumbent or a measured delta
    assert track_headroom(None, ideal=0.0, minimum_delta=0.033, goal="lower") is None
    assert track_headroom(0.5, ideal=0.0, minimum_delta=0.0, goal="lower") is None
    # signed: an incumbent past the declared ideal reads infeasible, not spare room
    assert track_headroom(1.2, ideal=1.0, minimum_delta=0.1, goal="higher") < 0


def test_contract_bound_validation(ready_study) -> None:
    _, study = ready_study
    contract = yaml.safe_load((study / "study.yaml").read_text(encoding="utf-8"))
    metric = contract["tracks"]["primary"]["metric"]

    metric["bound"] = {"ideal": "not-a-number", "on_infeasible": "explode", "bogus": 1}
    problems = " ".join(validate_contract(contract, study))
    assert "metric.bound.ideal must be a finite number" in problems
    assert "on_infeasible must be ack, warn, or block" in problems
    assert "unknown keys" in problems

    # a declared bound demands a named floor estimand once a floor exists
    metric["bound"] = {"ideal": 1.0}
    metric["noise_floor"] = {"k": 5, "std": 0.002, "range": 0.005}
    problems = " ".join(validate_contract(contract, study))
    assert "requires noise_floor.estimand" in problems

    metric["noise_floor"]["estimand"] = "sharpest"
    problems = " ".join(validate_contract(contract, study))
    assert "estimand must be marginal-resplit or paired-comparison" in problems

    metric["noise_floor"]["estimand"] = "marginal-resplit"
    metric["minimum_delta"] = 0.004
    assert not any("bound" in p or "estimand" in p for p in validate_contract(contract, study))

    # bound without any floor is legal (delta may still be unmeasured)
    del metric["noise_floor"]
    assert not any("bound" in p for p in validate_contract(contract, study))


def test_preflight_hints_without_bound_and_stays_green(ready_study) -> None:
    _, study = ready_study
    checks = headroom_checks(study)
    assert len(checks) == 1 and checks[0].ok
    assert "HINT: declare metric.bound.ideal" in checks[0].message  # val_auc has a known ideal
    # regression: the new check never fails a bound-less study
    assert sum(not c.ok for c in verify_study(study)) == 0


def test_disclosure_ack_flow_and_run_gating(ready_study) -> None:
    repo, study = ready_study
    seed_keep(study, 0.9)

    # arm the audit with an infeasible delta: h = (1.0 - 0.9) / 0.2 = 0.5
    set_metric(repo, study, minimum_delta=0.2, bound={"ideal": 1.0})

    checks = headroom_checks(study)
    assert len(checks) == 1 and checks[0].ok
    assert "[WARN]" in checks[0].message
    assert "NO keep is arithmetically possible" in checks[0].message
    assert "= 0.500" in checks[0].message

    # default posture (ack): development runs refuse until acknowledged
    with pytest.raises(WorkflowError, match="register awareness first"):
        run_one(study, command=metric_command(0.95), echo=False)

    with pytest.raises(WorkflowError, match="--note is required"):
        acknowledge_headroom(study, track="primary", acknowledged_by="tester", note="  ")

    entry = acknowledge_headroom(
        study,
        track="primary",
        acknowledged_by="tester",
        note="run-anyway: arithmetic closed the door; we run the parade and publish where each lands",
    )
    assert entry["h"] == pytest.approx(0.5)
    assert entry["infeasible"] is True

    checks = headroom_checks(study)
    assert "acknowledged by tester" in checks[0].message
    assert "[WARN]" not in checks[0].message

    # the ack is on the tamper-evident record
    assert verify_event_chain(study) == []
    events = (study / "events.jsonl").read_text(encoding="utf-8")
    assert "headroom_acknowledged" in events

    # acknowledged: the parade may run (and honestly discards)
    manifest = run_one(study, command=metric_command(0.95), echo=False)
    assert manifest["disposition"] == "discard"
    assert sum(not c.ok for c in verify_study(study)) == 0


def test_ack_commits_only_the_record_it_wrote(ready_study, capsys) -> None:
    """E15: a closed door goes on the record without filing the tree around it."""
    from test_commit_state_writes import modified_paths, operator_edits, seed_tracked
    from test_workflow_v2 import git

    repo, study = ready_study
    seed_keep(study, 0.9)
    set_metric(repo, study, minimum_delta=0.2, bound={"ideal": 1.0})
    seed_tracked(repo, study, "findings.md")
    operator_edits(study, "findings.md")

    acknowledge_headroom(
        study,
        track="primary",
        acknowledged_by="tester",
        note="run-anyway: the arithmetic closed the door and we publish where each lands",
    )

    committed = set(git(repo, "show", "--name-only", "--format=", "HEAD").splitlines())
    assert committed == {
        "studies/03-demo/study_state.json",
        "studies/03-demo/events.jsonl",
    }
    assert modified_paths(repo) == {"studies/03-demo/findings.md"}
    assert "note: 1 uncommitted edit(s) left in the tree (findings.md)" in capsys.readouterr().out


def test_block_posture_refuses_even_after_ack(ready_study) -> None:
    repo, study = ready_study
    seed_keep(study, 0.9)
    set_metric(repo, study, minimum_delta=0.2, bound={"ideal": 1.0, "on_infeasible": "block"})
    with pytest.raises(WorkflowError, match="on_infeasible: block"):
        run_one(study, command=metric_command(0.95), echo=False)
    acknowledge_headroom(
        study, track="primary", acknowledged_by="tester", note="re-scope: pending"
    )
    with pytest.raises(WorkflowError, match="on_infeasible: block"):
        run_one(study, command=metric_command(0.95), echo=False)


def test_warn_posture_proceeds_unacked(ready_study) -> None:
    repo, study = ready_study
    seed_keep(study, 0.9)
    set_metric(repo, study, minimum_delta=0.2, bound={"ideal": 1.0, "on_infeasible": "warn"})
    manifest = run_one(study, command=metric_command(0.95), echo=False)
    assert manifest["disposition"] == "discard"


def test_feasible_frontier_needs_no_ack(ready_study) -> None:
    repo, study = ready_study
    seed_keep(study, 0.9)
    set_metric(repo, study, minimum_delta=0.05, bound={"ideal": 1.0})  # h = 2.0
    checks = headroom_checks(study)
    assert "a keep is arithmetically possible" in checks[0].message
    assert "NOT plausible" in checks[0].message  # the Bayes-risk caveat ships with the OK
    with pytest.raises(WorkflowError, match="nothing to acknowledge"):
        acknowledge_headroom(
            study, track="primary", acknowledged_by="tester", note="re-scope: n/a"
        )
    manifest = run_one(study, command=metric_command(0.96), echo=False)
    assert manifest["disposition"] == "keep"  # 0.96 >= 0.9 + 0.05


def test_ack_refusals(ready_study) -> None:
    repo, study = ready_study
    # no bound declared
    with pytest.raises(WorkflowError, match="declares no metric.bound"):
        acknowledge_headroom(
            study, track="primary", acknowledged_by="tester", note="re-scope: x"
        )
    # bound declared but no incumbent yet
    set_metric(repo, study, minimum_delta=0.2, bound={"ideal": 1.0})
    with pytest.raises(WorkflowError, match="needs a first keep"):
        acknowledge_headroom(
            study, track="primary", acknowledged_by="tester", note="re-scope: x"
        )
    checks = headroom_checks(study)
    assert "no incumbent yet" in checks[0].message


def test_cli_headroom_ack_surface(ready_study, capsys) -> None:
    repo, study = ready_study
    seed_keep(study, 0.9)
    set_metric(repo, study, minimum_delta=0.2, bound={"ideal": 1.0})
    rc = cli.main(
        [
            "headroom",
            "ack",
            "--study",
            str(study),
            "--track",
            "primary",
            "--acknowledged-by",
            "tester",
            "--note",
            "run-anyway: door-closed sentence",
        ]
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert "h=0.500 < 1" in out
    assert "on the record" in out
    state = load_state(study, yaml.safe_load((study / "study.yaml").read_text(encoding="utf-8")))
    assert state["headroom"]["primary"]["acknowledged_by"] == "tester"
