"""The ``escalation`` capability (WP-07): getting unstuck, on the record.

Test names carry their requirement id (R-ESC-1…3) and, where the plan names one,
its validation row (V-21).  The spine's fixtures are reused verbatim — a
generation-enabled study with one extra capability declared — so what these
exercise is the REGISTRATION path plus the three requirements the ladder exists
for:

R-ESC-1  ``escalation_plan.yaml`` is frozen at CONSULT, its triggers are
         reconstructed from the manifests, and once one trips no ``run`` or
         ``--hypothesis`` admission is granted until a decision is recorded
         after it.  Editing the threshold afterwards cannot discharge the stall.
R-ESC-2  A decision records rung, evidence, action, the concrete changed
         resource, rationale, status, estimated and actual costs (unit vectors,
         ``unknown`` allowed) and a next condition; a skipped rung costs a
         reason; ``stop`` is a rung; a budget is not passed without a prior
         extension.
R-ESC-3  ``pivot`` creates a successor carrying both contract hashes and the
         exposure it inherits, and the predecessor's contract is unchanged.

The last two tests are A3 §4's smallest exercise: five rungs accounted for in
one episode, a human-advised successor, and the successor's own manifest
pointing back at the receipt that created it.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from test_generation_spine import _gen, _receipt, _scaffold
from test_workflow_v3 import commit_all, git, metric_command

from kleinlib.generation import escalate as ge
from kleinlib.generation import manifest as gm
from kleinlib.primitives import sha256_file
from kleinlib.workflow import record_gate, run_one

STUDY = "03-demo"

BASE_PLAN: dict[str, Any] = {
    "type": "escalation-plan",
    "study": STUDY,
    "triggers": [
        {"id": "T1", "kind": "consecutive_discards", "max": 3, "scope": "track",
         "track": "primary"},
        {"id": "T2", "kind": "headroom_closed"},
        {"id": "T3", "kind": "budget_exhausted", "phase": "confirmation"},
    ],
    "evidence_window": {"runs": 5},
    "rungs": list(ge.RUNGS),
    "budgets": {"compute": 100, "person_time": 8, "money": 0, "samples": "unknown"},
    "terminal_actions": ["stop", "pivot"],
}

COST = (
    "--estimated-cost", "compute=1",
    "--estimated-cost", "person_time=0.5",
    "--estimated-cost", "money=0",
    "--estimated-cost", "samples=0",
)
ACTUAL = (
    "--actual-cost", "compute=1",
    "--actual-cost", "person_time=1",
    "--actual-cost", "money=0",
    "--actual-cost", "samples=0",
)


# --------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------


def _plan(**overrides: Any) -> dict[str, Any]:
    document = copy.deepcopy(BASE_PLAN)
    document.update(copy.deepcopy(overrides))
    return document


def _write_plan(study: Path, document: dict[str, Any]) -> None:
    (study / ge.PLAN_NAME).write_text(yaml.safe_dump(document, sort_keys=True), encoding="utf-8")


def _enable(
    tmp_path: Path,
    document: dict[str, Any] | None = None,
    *,
    lock: bool = True,
    name: str = "repo",
) -> tuple[Path, Path]:
    """A schema-3 study that declared `escalation`, with the plan locked at CONSULT."""
    repo, study = _scaffold(tmp_path)
    assert _gen("init", "--study", str(study), "--capability", "escalation") == 0
    if lock:
        _write_plan(study, document if document is not None else _plan())
        assert _gen("escalate", "lock", "--study", str(study), "--actor", "tester") == 0
    record_gate(study, "consult", acknowledged_by="tester")
    record_gate(study, "data", acknowledged_by="tester")
    record_gate(study, "method", acknowledged_by="tester")
    commit_all(repo, "gates recorded")
    git(repo, "switch", "-q", "-c", f"experiments/{STUDY}")
    return repo, study


def _bump(study: Path, marker: str) -> None:
    train = study / "train.py"
    train.write_text(train.read_text(encoding="utf-8") + f"\nCANDIDATE = {marker!r}\n", "utf-8")


def _admitted_run(study: Path, marker: str, value: float) -> dict[str, Any]:
    """One candidate: edit the surface, take the admission, run it."""
    _bump(study, marker)
    assert _gen("check", "--study", str(study), "--action", "run", "--track", "primary") == 0
    return run_one(study, command=metric_command(value), echo=False)


def _stall(study: Path) -> None:
    """One keep, then exactly three discards — trigger T1's registered limit."""
    _admitted_run(study, "keep", 0.9)
    for index, marker in enumerate(("a", "b", "c"), start=1):
        result = _admitted_run(study, marker, 0.5 - index * 0.01)
        assert result["disposition"] == "discard", result


def _events(study: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in (study / "generation" / "events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _checks(study: Path, name: str) -> list[dict[str, Any]]:
    return [check for check in _receipt(study)["checks"] if check["name"] == name]


def _detail(study: Path, name: str) -> str:
    return " ".join(check["detail"] for check in _checks(study, name))


def _outcome(study: Path) -> dict[str, Any]:
    return _receipt(study)["capabilities"][ge.CAPABILITY_NAME]


def _said(capsys) -> str:
    """Everything the verb printed — a refusal goes to stderr, its reasons to stdout."""
    captured = capsys.readouterr()
    return captured.out + captured.err


def _forge(study: Path, event_type: str, obj: dict[str, Any], **summary: Any) -> str:
    """Append an object nobody's verb would have written — the invalid controls.

    The chain stays valid (this is the ledger's own writer); only the CONTENT is
    doctored, which is exactly what verification has to catch on its own.
    """
    from kleinlib.generation.admission import core_anchor
    from kleinlib.generation.chronology import git_head, repo_for
    from kleinlib.generation.ledger import append_event, commit_generation, write_object

    sha = write_object(study, obj)
    append_event(
        study,
        event_type,
        study=STUDY,
        core_anchor=core_anchor(study),
        git_head=git_head(repo_for(study)),
        payload_sha256=sha,
        **summary,
    )
    commit_generation(study, f"test: forged {event_type}")
    return sha


# --------------------------------------------------------------------------
# R-ESC-1 — the plan, its anchor, and the refusal it buys
# --------------------------------------------------------------------------


def test_r_esc_1_valid_control_a_plan_locked_before_consult(tmp_path: Path) -> None:
    """R-ESC-1: lock before the consult gate, run under it → every check PASSes."""
    _repo, study = _enable(tmp_path)
    _admitted_run(study, "one", 0.7)
    _admitted_run(study, "two", 0.9)

    assert _gen("verify", "--study", str(study)) == 0
    receipt = _receipt(study)
    assert receipt["summary"]["failed"] == 0
    assert receipt["runs"] == {"E0001": "admitted", "E0002": "admitted"}
    assert [check["status"] for check in _checks(study, ge.PLAN_CHECK)] == ["PASS"]
    assert _outcome(study) == {
        "integrity": "PASS",
        "outcome": "none",
        "episodes": 0,
        "open": 0,
    }


def test_r_esc_1_a_plan_locked_after_consult_fails_forever(tmp_path: Path) -> None:
    """A stall rule written once the study is running cannot constrain it."""
    repo, study = _enable(tmp_path, lock=False)
    _write_plan(study, _plan())
    assert _gen("escalate", "lock", "--study", str(study)) == 2  # refused: consult is recorded
    assert _gen("escalate", "lock", "--study", str(study), "--allow-late") == 0
    commit_all(repo, "plan locked late")

    assert _gen("verify", "--study", str(study)) == 2
    assert [check["status"] for check in _checks(study, ge.PLAN_CHECK)] == ["FAIL"]
    # the FAIL is re-derived from the anchor, not read off the lock's own flag
    assert "at or after the consult gate record" in _detail(study, ge.PLAN_CHECK)


def test_c4_a_lock_that_reports_itself_early_is_still_ordered_by_the_witnesses(
    tmp_path: Path,
) -> None:
    """C-4: `late: false` is testimony; the anchor and git ancestry are not.

    A hand-written ledger can say anything about itself.  This one files a
    perfectly formed lock object with `late: false` AFTER the consult gate — the
    exact shape `--allow-late` produces, minus the confession — and the family
    still refuses it.
    """
    from kleinlib.generation.admission import core_anchor
    from kleinlib.generation.chronology import git_head
    from kleinlib.generation.ledger import append_event, commit_generation, write_object

    repo, study = _enable(tmp_path, lock=False)
    _write_plan(study, _plan())
    document = ge.parse_plan(ge.plan_path(study))
    obj = ge.lock_object(
        study="03-demo",
        document=document,
        plan_sha256=sha256_file(ge.plan_path(study)),
        late=False,  # the lie
    )
    sha = write_object(study, obj)
    append_event(
        study,
        ge.LOCK_TYPE,
        study="03-demo",
        core_anchor=core_anchor(study),  # after the consult gate, in truth
        git_head=git_head(repo),
        payload_sha256=sha,
        plan_sha256=obj["plan_sha256"],
        triggers=len(document.get("triggers") or []),
    )
    commit_generation(
        study, "klein: a hand-written escalation lock", paths=("generation/events.jsonl", "generation/objects")
    )
    commit_all(repo, "the plan file beside it")

    assert _gen("verify", "--study", str(study)) == 2
    assert [check["status"] for check in _checks(study, ge.PLAN_CHECK)] == ["FAIL"]
    detail = _detail(study, ge.PLAN_CHECK)
    assert "at or after the consult gate record" in detail
    assert "not an ancestor of the consult gate commit" in detail


def test_r_esc_1_the_plan_is_validated_before_it_is_locked(tmp_path: Path) -> None:
    """A plan the arithmetic cannot read is refused, one problem per line."""
    repo, study = _scaffold(tmp_path)
    assert _gen("init", "--study", str(study), "--capability", "escalation") == 0
    _write_plan(
        study,
        _plan(
            triggers=[{"id": "nope", "kind": "vibes"}],
            rungs=["metric_diagnosis", "human_expert"],
            budgets={"compute": 1},
            terminal_actions=["pivot"],
        ),
    )
    assert _gen("escalate", "lock", "--study", str(study)) == 2
    assert not ge.locks(study, _events(study))
    commit_all(repo, "unlocked plan left in the tree")


def test_v21_three_discards_refuse_the_next_candidate(tmp_path: Path, capsys) -> None:
    """V-21: `max: 3` → three discards → no run admission until a decision exists."""
    _repo, study = _enable(tmp_path)
    _stall(study)

    _bump(study, "fifth")
    assert _gen("check", "--study", str(study), "--action", "run", "--track", "primary") == 2
    refusal = _said(capsys)
    assert "trigger T1 (consecutive_discards) is tripped" in refusal
    assert "3 consecutive discards" in refusal
    assert "E0002, E0003, E0004" in refusal

    # a hypothesis admission is refused by the same rule (and by the spine, for slates)
    assert (
        _gen(
            "check", "--study", str(study), "--action", "run", "--track", "primary",
            "--hypothesis", "H1",
        )
        == 2
    )
    assert "trigger T1" in _said(capsys)

    assert (
        _gen(
            "escalate", "record", "--study", str(study),
            "--trigger", "T1", "--rung", "metric_diagnosis",
            "--action", "re-read the estimand and the floor before another candidate",
            "--changed", "the metric's resolution assumption, not the model",
            "--rationale", "three discards at this delta may be a floor problem",
            "--next", "a re-measured floor, or a candidate that clears the new one",
            *COST,
        )
        == 0
    )
    assert _gen("check", "--study", str(study), "--action", "run", "--track", "primary") == 0
    assert _gen("verify", "--study", str(study)) == 0
    assert _outcome(study)["outcome"] == "escalated"
    assert _outcome(study)["episodes"] == 1


def test_v21_editing_the_threshold_after_the_lock_cannot_discharge_the_stall(
    tmp_path: Path, capsys
) -> None:
    """V-21's invalid control: the file moved, the lock did not, the stall stands."""
    repo, study = _enable(tmp_path)
    _stall(study)

    document = _plan()
    document["triggers"][0]["max"] = 99
    _write_plan(study, document)
    commit_all(repo, "threshold quietly widened")

    _bump(study, "fifth")
    assert _gen("check", "--study", str(study), "--action", "run", "--track", "primary") == 2
    assert "trigger T1 (consecutive_discards) is tripped" in _said(capsys)

    assert _gen("verify", "--study", str(study)) == 2
    assert [check["status"] for check in _checks(study, ge.PLAN_CHECK)] == ["FAIL"]
    assert "does not match the lock" in _detail(study, ge.PLAN_CHECK)


def test_a_decision_whose_reconstructed_count_is_wrong_fails(tmp_path: Path) -> None:
    """The count in a receipt is recomputed from the manifests, never believed."""
    _repo, study = _enable(tmp_path)
    _stall(study)
    events = _events(study)
    trip = ge.trips(
        ge.plan_document(study, events),
        contract={"tracks": {"primary": {}}, "phases": []},
        state={},
        manifests=[],
        started={},
        track="primary",
    )
    assert trip  # the plan declares T1 for this track

    doctored = ge.decision_object(
        study=STUDY,
        identifier=f"{STUDY}#D1",
        episode=1,
        trip=ge.Trip(
            trigger="T1",
            kind="consecutive_discards",
            count=99,
            threshold=3,
            evidence=("E0002",),
            anchor_sequence=1,
            detail="doctored",
            subject="primary",
        ),
        rung="metric_diagnosis",
        skipped={},
        considered_action="pretend the stall was bigger than it was",
        changed="nothing at all",
        rationale="an invalid control",
        estimated_cost={"compute": 0, "person_time": 0, "money": 0, "samples": 0},
        next_condition=None,
        successor_study=None,
        human_advice=None,
    )
    _forge(study, ge.RECORD_TYPE, doctored, decision=f"{STUDY}#D1", rung="metric_diagnosis")

    assert _gen("verify", "--study", str(study)) == 2
    assert "reconstructed_count" in _detail(study, ge.TRIGGER_CHECK)


def test_the_trigger_evidence_is_exactly_the_counter_stop_uses(tmp_path: Path) -> None:
    """The ids in a receipt and the number in the stop rule cannot drift apart."""
    from kleinlib.manifest import load_manifests
    from kleinlib.stop import consecutive_discards

    _repo, study = _enable(tmp_path)
    _stall(study)
    manifests = load_manifests(study)
    evidence = ge._trailing_discards(manifests, "track", track="primary", phase=None)
    assert len(evidence) == consecutive_discards(manifests, scope="track", track="primary")
    assert evidence == ["E0002", "E0003", "E0004"]


def test_a_run_admission_before_the_plan_is_locked_is_refused(tmp_path: Path, capsys) -> None:
    """A capability declared and never locked blocks the discipline it promised."""
    _repo, study = _enable(tmp_path, lock=False)
    _bump(study, "one")
    assert _gen("check", "--study", str(study), "--action", "run", "--track", "primary") == 2
    assert "is not locked" in _said(capsys)


# --------------------------------------------------------------------------
# R-ESC-2 — the rungs and the costs
# --------------------------------------------------------------------------


def _record(study: Path, rung: str, *extra: str, trigger: str = "T1") -> int:
    return _gen(
        "escalate", "record", "--study", str(study),
        "--trigger", trigger, "--rung", rung,
        "--action", f"take the {rung} rung",
        "--changed", f"the concrete thing {rung} changes",
        "--rationale", f"why {rung}, now",
        "--next", "the condition that would close this",
        *COST,
        *extra,
    )


def test_r_esc_2_a_rung_reached_over_silent_ones_is_refused(tmp_path: Path, capsys) -> None:
    """R-ESC-2: skipping is allowed; skipping SILENTLY is the gaming this stops."""
    _repo, study = _enable(tmp_path)
    _stall(study)

    assert _record(study, "data_leverage") == 2
    assert "unaccounted rung(s) metric_diagnosis, method_family" in _said(capsys)

    assert _record(study, "data_leverage", "--skip", "metric_diagnosis=") == 2
    assert "needs a recorded reason" in _said(capsys)

    assert (
        _record(
            study,
            "data_leverage",
            "--skip", "metric_diagnosis=the floor was re-measured at E0002 and holds",
            "--skip", "method_family=only one family is licensed for this estimand",
        )
        == 0
    )
    assert _gen("verify", "--study", str(study)) == 0
    assert [check["status"] for check in _checks(study, ge.RECEIPT_CHECK)] == ["PASS"]


def test_r_esc_2_an_unknown_actual_needs_its_evidence(tmp_path: Path, capsys) -> None:
    """A cost that cannot be measured is recorded as unknown, with a reason."""
    _repo, study = _enable(tmp_path)
    _stall(study)
    assert _record(study, "metric_diagnosis") == 0

    identifier = f"{STUDY}#D1"
    assert (
        _gen(
            "escalate", "close", "--study", str(study), "--decision", identifier,
            "--actual-cost", "compute=2", "--actual-cost", "person_time=unknown",
            "--actual-cost", "money=0", "--actual-cost", "samples=0",
            "--outcome", "the floor was re-measured and the delta stands",
        )
        == 2
    )
    assert "person_time recorded as unknown" in _said(capsys)

    assert (
        _gen(
            "escalate", "close", "--study", str(study), "--decision", identifier,
            "--actual-cost", "compute=2", "--actual-cost", "person_time=unknown",
            "--actual-cost", "money=0", "--actual-cost", "samples=0",
            "--cost-evidence", "the diagnosis ran inside another task; no timer was kept",
            "--outcome", "the floor was re-measured and the delta stands",
        )
        == 0
    )
    assert _gen("verify", "--study", str(study)) == 0
    assert [check["status"] for check in _checks(study, ge.COST_CHECK)] == ["PASS"]
    assert _outcome(study)["open"] == 0


def test_r_esc_2_a_missing_cost_unit_is_not_a_zero_cost(tmp_path: Path, capsys) -> None:
    """The vector is always four units; silence is not free."""
    _repo, study = _enable(tmp_path)
    _stall(study)
    assert (
        _gen(
            "escalate", "record", "--study", str(study),
            "--trigger", "T1", "--rung", "metric_diagnosis",
            "--action", "diagnose", "--changed", "the estimand's resolution",
            "--rationale", "three discards", "--estimated-cost", "compute=1",
        )
        == 2
    )
    output = _said(capsys)
    assert "person_time is missing" in output and "money is missing" in output


def test_r_esc_2_stop_is_a_rung_from_anywhere(tmp_path: Path) -> None:
    """Stopping is always available and always recorded — never a silent fade-out."""
    _repo, study = _enable(tmp_path)
    _stall(study)
    assert _record(study, "stop") == 0
    assert (
        _gen(
            "escalate", "close", "--study", str(study), "--decision", f"{STUDY}#D1",
            *ACTUAL, "--outcome", "the phase is closed; the question does not survive it",
        )
        == 0
    )
    assert _gen("verify", "--study", str(study)) == 0
    assert _outcome(study)["outcome"] == "stopped"


def test_r_esc_2_a_budget_is_not_passed_without_a_prior_extension(tmp_path: Path) -> None:
    """Work beyond the registered budget needs a receipt that said so first."""
    _repo, study = _enable(tmp_path, _plan(budgets={"compute": 1, "person_time": 8, "money": 0,
                                                    "samples": "unknown"}))
    _stall(study)
    assert (
        _gen(
            "escalate", "record", "--study", str(study),
            "--trigger", "T1", "--rung", "metric_diagnosis",
            "--action", "rerun the whole floor recipe",
            "--changed", "the floor's resampling budget",
            "--rationale", "an invalid control: this costs five times the registered budget",
            "--estimated-cost", "compute=5", "--estimated-cost", "person_time=1",
            "--estimated-cost", "money=0", "--estimated-cost", "samples=0",
        )
        == 0
    )
    assert _gen("verify", "--study", str(study)) == 2
    assert "compute budget 1 exceeded" in _detail(study, ge.COST_CHECK)


def test_r_esc_2_a_declared_extension_licenses_the_overrun(tmp_path: Path) -> None:
    """The valid control for the same rule: say it first, then spend it."""
    _repo, study = _enable(tmp_path, _plan(budgets={"compute": 1, "person_time": 8, "money": 0,
                                                    "samples": "unknown"}))
    _stall(study)
    assert (
        _gen(
            "escalate", "record", "--study", str(study),
            "--trigger", "T1", "--rung", "metric_diagnosis",
            "--action", "extend-budget: the floor recipe needs five compute units",
            "--changed", "the registered compute budget for this phase",
            "--rationale", "the diagnosis is worth more than the cap it was scoped under",
            "--estimated-cost", "compute=0", "--estimated-cost", "person_time=0",
            "--estimated-cost", "money=0", "--estimated-cost", "samples=0",
        )
        == 0
    )
    assert (
        _gen(
            "escalate", "record", "--study", str(study),
            "--trigger", "T1", "--rung", "method_family",
            "--action", "fit the second licensed family",
            "--changed", "the model family, from linear to trees",
            "--rationale", "the diagnosis exonerated the metric",
            "--estimated-cost", "compute=5", "--estimated-cost", "person_time=1",
            "--estimated-cost", "money=0", "--estimated-cost", "samples=0",
        )
        == 0
    )
    assert _gen("verify", "--study", str(study)) == 0
    assert [check["status"] for check in _checks(study, ge.COST_CHECK)] == ["PASS"]


def test_r_esc_2_a_decision_that_outlives_its_window_is_not_prospective(tmp_path: Path) -> None:
    """An open receipt with more runs after it than the window allows is post-hoc."""
    _repo, study = _enable(tmp_path, _plan(evidence_window={"runs": 1}))
    _admitted_run(study, "keep", 0.9)
    assert _record(study, "metric_diagnosis") == 0
    _admitted_run(study, "a", 0.4)
    _admitted_run(study, "b", 0.3)

    assert _gen("verify", "--study", str(study)) == 2
    assert "decision recorded after its action" in _detail(study, ge.RECEIPT_CHECK)


# --------------------------------------------------------------------------
# R-ESC-3 and A3 §4's smallest exercise
# --------------------------------------------------------------------------


def _climb(study: Path) -> None:
    """All five rungs, in order, inside one episode — the acceptance exercise."""
    assert _record(study, "metric_diagnosis") == 0
    assert _record(study, "method_family") == 0
    assert _record(study, "data_leverage") == 0
    assert _record(study, "adjacent_field_analogy") == 0
    assert (
        _record(
            study,
            "human_expert",
            "--advisor", "a domain practitioner outside this study",
            "--advice", "the estimand cannot be answered on this partition; take fresh samples",
            "--advice-accepted",
            "--advice-cost", "money=200",
            "--successor", "04-successor",
        )
        == 0
    )


def test_the_smallest_exercise_five_rungs_then_a_human_advised_successor(
    tmp_path: Path,
) -> None:
    """A3 §4: the stall trips, all five rungs are accounted, a successor is linked."""
    repo, study = _enable(tmp_path)
    _stall(study)
    _climb(study)

    identifier = f"{STUDY}#D5"
    assert (
        _gen(
            "escalate", "close", "--study", str(study), "--decision", identifier,
            *ACTUAL, "--outcome", "the advice was taken; the question moves to a successor",
        )
        == 0
    )
    successor = study.parent / "04-successor"
    successor.mkdir()
    (successor / "study.yaml").write_text("schema_version: 3\nid: 04-successor\n", encoding="utf-8")
    commit_all(repo, "successor contract drafted")

    assert (
        _gen(
            "escalate", "pivot", "--study", str(study), "--decision", identifier,
            "--successor", "04-successor",
            "--new-contract", str(successor / "study.yaml"),
            "--inherited", "scouted=the practitioner already saw the 2019 season",
        )
        == 0
    )
    assert _gen("verify", "--study", str(study)) == 0
    outcome = _outcome(study)
    assert outcome["outcome"] == "pivoted"
    assert outcome["episodes"] == 1

    pivot = ge.pivots(study, _events(study))[0][1]
    assert pivot["successor_study"] == "04-successor"
    assert pivot["old_contract_sha256"] != pivot["new_contract_sha256"]
    assert {row["kind"] for row in pivot["inherited_exposure"]} >= {"held-out", "scouted"}

    # every rung is on the record, and the human advice is pinned with its cost
    rungs = [row.rung for row in ge.decisions(study, _events(study))]
    assert rungs == list(ge.RUNGS)
    advice = ge.decisions(study, _events(study))[-1].recorded["human_advice"]
    assert advice["accepted"] is True and advice["cost"] == {"money": 200}


def test_r_esc_3_a_pivot_that_misreports_the_old_contract_fails(tmp_path: Path) -> None:
    """R-ESC-3's invalid control: the predecessor's contract is re-read, not trusted."""
    _repo, study = _enable(tmp_path)
    _stall(study)
    assert _record(study, "metric_diagnosis") == 0
    _forge(
        study,
        ge.PIVOT_TYPE,
        ge.pivot_object(
            study=STUDY,
            decision=f"{STUDY}#D1",
            successor_study="04-successor",
            old_contract_sha256="0" * 64,
            new_contract_sha256="1" * 64,
            exposure=[],
            ids=[],
        ),
        decision=f"{STUDY}#D1",
        successor_study="04-successor",
    )
    assert _gen("verify", "--study", str(study)) == 2
    assert "the predecessor's contract was rewritten" in _detail(study, ge.PIVOT_CHECK)


def _successor(tmp_path: Path, repo: Path, receipt: str | None) -> Path:
    """A second generation-enabled study in the same repo, succeeding the first."""
    from test_workflow_v3 import _fill

    from kleinlib.scaffold import scaffold_study

    successor = scaffold_study(
        repo / "studies",
        "04-successor",
        goal="ask the question the predecessor could not",
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
    _fill(successor)
    data = successor / "data" / "prepared"
    data.mkdir(parents=True)
    (data / "fixture.csv").write_text("x,y\n1,0\n2,1\n", encoding="utf-8")
    (successor / "data_card.md").write_text("# Data card\n\n> **Decision:** **GO**\n", "utf-8")
    (successor / "method_card.md").write_text("# Method card\n\nBrief.\n", encoding="utf-8")
    commit_all(repo, "successor study scaffolded")

    argv = ["init", "--study", str(successor), "--capability", "escalation",
            "--predecessor", STUDY]
    if receipt is not None:
        argv += ["--successor-receipt", receipt]
    assert _gen(*argv) == 0
    plan = _plan(study="04-successor")
    plan["triggers"] = [plan["triggers"][0]]
    _write_plan(successor, plan)
    assert _gen("escalate", "lock", "--study", str(successor)) == 0
    record_gate(successor, "consult", acknowledged_by="tester")
    commit_all(repo, "successor consult gate")
    return successor


def test_the_successor_manifest_points_back_at_the_receipt(tmp_path: Path) -> None:
    """A3 §4: the link is checked from BOTH ends — and restores no blindness."""
    repo, study = _enable(tmp_path)
    _stall(study)
    assert _record(study, "metric_diagnosis", "--successor", "04-successor") == 0
    contract = study.parent / "04-successor-contract.yaml"
    contract.write_text("schema_version: 3\nid: 04-successor\n", encoding="utf-8")
    commit_all(repo, "successor contract drafted")
    assert (
        _gen(
            "escalate", "pivot", "--study", str(study), "--decision", f"{STUDY}#D1",
            "--successor", "04-successor", "--new-contract", str(contract),
        )
        == 0
    )
    receipt = [
        event["payload_sha256"] for event in _events(study) if event["type"] == ge.PIVOT_TYPE
    ][0]

    successor = _successor(tmp_path, repo, receipt)
    assert _gen("verify", "--study", str(successor)) == 0
    detail = _detail(successor, ge.PREDECESSOR_CHECK)
    assert "successor of '03-demo'" in detail
    assert "restores no blindness" in detail
    assert gm.load_manifest(successor)["predecessor"]["successor_receipt"] == receipt


def test_a_successor_naming_no_receipt_fails(tmp_path: Path) -> None:
    """The invalid control: a predecessor claimed without the receipt that made it."""
    repo, study = _enable(tmp_path)
    _stall(study)
    successor = _successor(tmp_path, repo, None)
    assert _gen("verify", "--study", str(successor)) == 2
    assert "no successor_receipt" in _detail(successor, ge.PREDECESSOR_CHECK)
    assert _receipt(successor)["capabilities"][ge.CAPABILITY_NAME]["integrity"] == "FAIL"
    assert study.is_dir()  # the predecessor is untouched by the successor's failure


# --------------------------------------------------------------------------
# registration and write ownership
# --------------------------------------------------------------------------


def test_the_capability_is_registered_and_declared_before_it_is_used(tmp_path: Path) -> None:
    """`escalation` is loadable, and an undeclared study cannot use its verbs."""
    from kleinlib.generation.capabilities import load
    from kleinlib.generation.manifest import SUPPORTED_CAPABILITIES

    assert "escalation" in SUPPORTED_CAPABILITIES
    assert load()["escalation"].verify_family is not None

    repo, study = _scaffold(tmp_path)
    assert _gen("init", "--study", str(study)) == 0
    _write_plan(study, _plan())
    commit_all(repo, "a plan nobody declared")
    assert _gen("escalate", "lock", "--study", str(study)) == 1
    assert _gen("escalate", "show", "--study", str(study)) == 1


def test_an_escalation_verb_commits_only_generation_paths(tmp_path: Path) -> None:
    """Write ownership: a decision touches the ledger and nothing else."""
    repo, study = _enable(tmp_path)
    _stall(study)
    assert _record(study, "metric_diagnosis") == 0
    changed = git(repo, "show", "--name-only", "--format=", "HEAD").split()
    assert changed, changed
    assert all("/generation/" in path for path in changed), changed


@pytest.mark.parametrize("verb", ["show"])
def test_read_only_verbs_write_nothing(tmp_path: Path, verb: str) -> None:
    repo, study = _enable(tmp_path)
    before = git(repo, "rev-parse", "HEAD")
    assert _gen("escalate", verb, "--study", str(study)) == 0
    assert git(repo, "rev-parse", "HEAD") == before
    assert git(repo, "status", "--porcelain") == ""
