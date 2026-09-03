"""E6b — Gate 3: the referee, and the two lines a machine reads from the report.

A study's author cannot audit their own conclusions, and neither can the model
that ran the loop.  REFEREE (`references/referee-protocol.md`) puts a fresh,
independent reader between SYNTHESIZE and `klein finalize`; the report's first
two lines carry the three facts the engine records:

    Verdict: PASS | PASS-WITH-NOTES | FAIL
    Referee: <actor> (<tool / model>) · fresh context · independent-of-experimenter: yes|no

Pinned here: both lines parse, a FAIL is refused rather than softened, a missing
line is refused, `finalize` requires the gate, and `--no-referee --reason` is
recorded and shows as `unrefereed` on the receipt and in `klein status`.
"""

from __future__ import annotations

import pytest
from test_registered_mode import amend
from test_workflow_v3 import commit_all

from kleinlib import cli
from kleinlib.contract import GATE_ARTIFACTS, MODELING_GATES
from kleinlib.state import referee_report_facts
from kleinlib.workflow import (
    WorkflowError,
    finalize,
    load_contract,
    load_state,
    read_events,
    record_gate,
    status_summary,
    verify_study,
)

REPORT = """\
Verdict: {verdict}
Referee: {referee} · fresh context · independent-of-experimenter: {independent}

# Referee report — 03-demo

## The ten checks

All ten pass.
"""

FINDINGS = """\
# Findings

The study is exploratory.

## ② Registered predictions (from the ledger)

| P# | Statement | Rule | Observed | Verdict (ledger) | Evidence | Decision |
|---|---|---|---|---|---|---|
| P1 | … | … | … | supported | E0001 | program.md 2026-09-03 |
"""


@pytest.fixture
def refereed_study(ready_study_v3):
    """A schema-3 study with one registered prediction and findings written."""
    repo, study = ready_study_v3
    amend(
        study,
        lambda c: c.update(
            predictions=[
                {
                    "id": "P1",
                    "statement": "the frontier clears 0.6",
                    "rule": {"key": "primary_metric", "op": ">", "value": 0.6},
                }
            ]
        ),
        note="one registered prediction",
    )
    (study / "findings.md").write_text(FINDINGS, encoding="utf-8")
    commit_all(repo, "findings written, awaiting the referee")
    return repo, study


def write_report(study, *, verdict="PASS", referee="A. Referee (opus)", independent="yes") -> None:
    (study / "referee_report.md").write_text(
        REPORT.format(verdict=verdict, referee=referee, independent=independent),
        encoding="utf-8",
    )


def close(study, **kwargs):
    """finalize with the ledger's own refusals already answered."""
    return finalize(
        study,
        allow_exploratory=True,
        allow_open_predictions=True,
        open_predictions_reason="adjudicated in a follow-up study",
        **kwargs,
    )


# ---------------------------------------------------------------------------
# 1. the two machine-read lines
# ---------------------------------------------------------------------------


def test_the_gate_registry_knows_the_report_and_the_modeling_gates_do_not() -> None:
    assert GATE_ARTIFACTS["referee"] == ("referee_report.md",)
    # A study cannot be refereed before it has run: Gate 3 never blocks a run.
    assert "referee" not in MODELING_GATES
    assert MODELING_GATES == ("consult", "data", "method")


@pytest.mark.parametrize("verdict", ["PASS", "PASS-WITH-NOTES"])
def test_both_passing_verdicts_parse(verdict: str) -> None:
    facts = referee_report_facts(
        REPORT.format(verdict=verdict, referee="R (sonnet)", independent="no")
    )
    assert facts == {
        "verdict": verdict,
        "referee": "R (sonnet)",
        "independent_of_experimenter": False,
    }


def test_the_referee_line_carries_actor_tool_and_the_independence_rung() -> None:
    facts = referee_report_facts(
        REPORT.format(
            verdict="PASS",
            referee="Klein referee (claude-opus-5, fresh session)",
            independent="yes",
        )
    )
    assert facts["referee"] == "Klein referee (claude-opus-5, fresh session)"
    assert facts["independent_of_experimenter"] is True


def test_a_fail_is_refused_never_softened_into_a_note() -> None:
    with pytest.raises(WorkflowError, match="a FAIL is never softened into a note"):
        referee_report_facts(
            REPORT.format(verdict="FAIL", referee="R (opus)", independent="yes")
        )


@pytest.mark.parametrize(
    ("text", "missing"),
    [
        ("Referee: R (opus) · fresh context · independent-of-experimenter: yes\n", "Verdict:"),
        ("Verdict: PASS\n\n# report\n", "Referee:"),
        ("# report with neither line\n", "Verdict:"),
    ],
)
def test_a_missing_machine_read_line_is_refused(text: str, missing: str) -> None:
    with pytest.raises(WorkflowError, match=missing):
        referee_report_facts(text)


def test_a_referee_line_without_the_independence_flag_is_refused() -> None:
    with pytest.raises(WorkflowError, match="Referee:"):
        referee_report_facts("Verdict: PASS\nReferee: R (opus) · fresh context\n")


def test_a_verdict_the_protocol_does_not_define_is_refused() -> None:
    with pytest.raises(WorkflowError, match="Verdict:"):
        referee_report_facts(
            REPORT.format(verdict="ACCEPTED", referee="R (opus)", independent="yes")
        )


# ---------------------------------------------------------------------------
# 2. recording the gate
# ---------------------------------------------------------------------------


def test_recording_the_gate_stores_verdict_referee_and_independence(refereed_study) -> None:
    _, study = refereed_study
    write_report(study, verdict="PASS-WITH-NOTES", referee="R (opus)", independent="no")
    record_gate(study, "referee", acknowledged_by="orchestrator", note="two notes answered")

    entry = load_state(study, load_contract(study))["gates"]["referee"]
    assert entry["status"] == "recorded"
    assert entry["verdict"] == "PASS-WITH-NOTES"
    assert entry["referee"] == "R (opus)"
    assert entry["independent_of_experimenter"] is False
    assert entry["artifacts"]["referee_report.md"]

    event = [e for e in read_events(study) if e["type"] == "gate_recorded"][-1]
    assert (event["gate"], event["verdict"], event["independent_of_experimenter"]) == (
        "referee",
        "PASS-WITH-NOTES",
        False,
    )


def test_the_gate_refuses_a_failed_report(refereed_study) -> None:
    _, study = refereed_study
    write_report(study, verdict="FAIL")
    with pytest.raises(WorkflowError, match="a FAIL is never softened"):
        record_gate(study, "referee", acknowledged_by="orchestrator")
    assert "referee" not in load_state(study, load_contract(study))["gates"]


def test_the_gate_refuses_a_missing_report(refereed_study) -> None:
    _, study = refereed_study
    with pytest.raises(WorkflowError, match="missing referee_report.md"):
        record_gate(study, "referee", acknowledged_by="orchestrator")


def test_recording_the_gate_commits_the_report(refereed_study) -> None:
    """The next clean-tree check must not trip over the receipt Klein wrote."""
    import subprocess

    repo, study = refereed_study
    write_report(study)
    record_gate(study, "referee", acknowledged_by="orchestrator")
    porcelain = subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True
    ).stdout
    assert porcelain.strip() == ""


def test_the_referee_gate_is_schema_3_only(ready_study) -> None:
    _, study = ready_study
    (study / "referee_report.md").write_text(
        REPORT.format(verdict="PASS", referee="R (opus)", independent="yes"), encoding="utf-8"
    )
    with pytest.raises(WorkflowError, match="schema-3 stage"):
        record_gate(study, "referee", acknowledged_by="orchestrator")


def test_a_schema_2_study_still_verifies_with_no_referee_gate(ready_study) -> None:
    """The gate registry grew; the schema-2 check list did not."""
    _, study = ready_study
    names = [check.name for check in verify_study(study)]
    assert "gate referee" not in names
    assert {"gate consult", "gate data", "gate method"} <= set(names)


# ---------------------------------------------------------------------------
# 3. finalize requires the gate
# ---------------------------------------------------------------------------


def test_finalize_refuses_an_unrefereed_study(refereed_study) -> None:
    _, study = refereed_study
    with pytest.raises(WorkflowError, match="the referee gate is not recorded"):
        close(study)


def test_finalize_runs_once_the_gate_is_recorded(refereed_study) -> None:
    _, study = refereed_study
    write_report(study, referee="R (opus)", independent="yes")
    record_gate(study, "referee", acknowledged_by="orchestrator")

    assert close(study) == "exploratory"
    finalization = load_state(study, load_contract(study))["finalization"]
    assert finalization["referee"] == {
        "status": "refereed",
        "verdict": "PASS",
        "referee": "R (opus)",
        "independent_of_experimenter": True,
    }
    assert "referee: PASS — R (opus), independent-of-experimenter: yes" in status_summary(study)


def test_no_referee_needs_a_reason_and_is_recorded_as_unrefereed(refereed_study) -> None:
    _, study = refereed_study
    with pytest.raises(WorkflowError, match="--no-referee requires --reason"):
        close(study, no_referee=True)

    assert close(study, no_referee=True, referee_reason="solo run, no second model available")
    finalization = load_state(study, load_contract(study))["finalization"]
    assert finalization["referee"] == {
        "status": "unrefereed",
        "reason": "solo run, no second model available",
    }
    assert "referee: unrefereed" in status_summary(study)


def test_status_says_the_gate_is_still_open_before_it_is_recorded(refereed_study) -> None:
    _, study = refereed_study
    assert "referee: not recorded (Gate 3 runs before finalize)" in status_summary(study)


def test_a_schema_2_finalize_never_asks_for_a_referee(ready_study) -> None:
    _, study = ready_study
    (study / "findings.md").write_text(
        "# Findings\n\nThis study is exploratory.\n", encoding="utf-8"
    )
    assert finalize(study, allow_exploratory=True) == "exploratory"


# ---------------------------------------------------------------------------
# 4. the CLI surface
# ---------------------------------------------------------------------------


def test_gate_record_referee_is_a_cli_verb_and_override_is_not(refereed_study, capsys) -> None:
    _, study = refereed_study
    write_report(study)
    assert (
        cli.main(
            ["gate", "record", "referee", "--study", str(study), "--acknowledged-by", "orch"]
        )
        == 0
    )
    assert "recorded gate referee" in capsys.readouterr().out

    # A FAIL is never softened, so there is no `gate override referee`.
    parser = cli.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(
            ["gate", "override", "referee", "--acknowledged-by", "o", "--reason", "r"]
        )
    capsys.readouterr()


def test_finalize_carries_the_no_referee_override() -> None:
    args = cli.build_parser().parse_args(["finalize", "--no-referee", "--reason", "solo"])
    assert (args.no_referee, args.reason) == (True, "solo")
