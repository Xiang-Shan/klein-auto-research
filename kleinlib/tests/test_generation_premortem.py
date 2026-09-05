"""The slate-time pre-mortem (WP-03) — V-13 and the A3 §7 smallest exercise.

The exercise is the whole point and it is the first test: a four-row slate with a
planted denominator omission, a review that names it, an acceptance that produces
a NEW slate version, and a second — deliberately ignored — blocking mechanical
issue that must prevent admission until it is answered too.

Everything else here is a control on one clause of V-13: a review recorded after
the phase's first hypothesis admission FAILs; a reviewer who is the roster's
referee FAILs; an `accept` naming something that is not a slate version is
refused; a review edited after it was answered FAILs; and independence stays
`self-attested` until a session receipt is hashed into the record.

The fixtures reuse ``test_generation_spine``'s scaffolding and
``test_generation_slate``'s slate authoring, so a pre-mortem study is an ordinary
schema-3 generation study that declared two capabilities.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from test_generation_slate import (
    PHASE,
    PREDICTIONS,
    STUDY,
    V11_ROWS,
    _amend_contract,
    _check,
    _lock,
    _row,
)
from test_generation_spine import _bump, _gates, _gen, _receipt, _scaffold, _statuses
from test_workflow_v3 import commit_all, git, metric_command

from kleinlib.generation import premortem
from kleinlib.generation.ledger import read_events
from kleinlib.workflow import run_one

GENERATION_PKG = Path(__file__).resolve().parents[1] / "generation"
REVIEWER = "r-1 · a fresh session · not the driver"


# --------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------


@pytest.fixture
def premortem_study(tmp_path: Path) -> tuple[Path, Path]:
    """A study that declared ``slates`` AND ``premortem`` (the dependency is fixed)."""
    repo, study = _scaffold(tmp_path)
    _amend_contract(study, lambda c: c.update(predictions=[dict(p) for p in PREDICTIONS]))
    commit_all(repo, "five registered predictions")
    assert (
        _gen(
            "init",
            "--study",
            str(study),
            "--capability",
            "slates",
            "--capability",
            "premortem",
        )
        == 0
    )
    _gates(repo, study)
    return repo, study


def _slate_sha(study: Path, index: int = -1) -> str:
    from kleinlib.generation import slate

    return slate.slate_versions(study, read_events(study), PHASE)[index]["sha"]


def _issue(
    name: str,
    target: str,
    *,
    severity: str = "blocking",
    kind: str = "mechanical",
    text: str | None = None,
) -> dict[str, Any]:
    return {
        "id": name,
        "target": target,
        "severity": severity,
        "kind": kind,
        "text": text or f"{name}: the yield metric's denominator omits the failed batches",
    }


#: The A3 §7 planted defect, and the second blocker the driver is tempted to skip.
ISSUES = [
    _issue("I1", f"{STUDY}#H2", text="the denominator omitted in row H2 counts only successes"),
    _issue("I2", "slate", text="no row states the partition its measurement runs on"),
]


def _write_review(
    study: Path,
    *,
    slate_sha: str,
    issues: list[dict[str, Any]] | None = None,
    reviewer: dict[str, Any] | None = None,
    inputs: list[str] | None = None,
    responses: list[dict[str, Any]] | None = None,
    phase: str = PHASE,
) -> Path:
    payload: dict[str, Any] = {
        "type": "premortem",
        "study": STUDY,
        "phase": phase,
        "slate_object": slate_sha,
        "reviewer": reviewer
        or {"name": REVIEWER, "model": "opus", "tool": "pytest", "session_receipt": None},
        "inputs": inputs if inputs is not None else ["study.yaml", f"slates/{phase}.yaml"],
        "issues": [dict(issue) for issue in (issues if issues is not None else ISSUES)],
    }
    if responses is not None:
        payload["responses"] = [dict(row) for row in responses]
    path = study / "premortem" / f"{phase}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


def _record(study: Path, *extra: str, phase: str = PHASE) -> int:
    return _gen("premortem", "record", "--study", str(study), "--phase", phase, *extra)


def _respond(study: Path, phase: str = PHASE) -> int:
    return _gen("premortem", "respond", "--study", str(study), "--phase", phase)


def _answer(
    issue: str, disposition: str, *, changed: str | None = None, why: str = "recorded"
) -> dict[str, Any]:
    row: dict[str, Any] = {"issue": issue, "disposition": disposition, "rationale": why}
    if changed is not None:
        row["changed_artifact_hash"] = changed
    return row


def _fix_h2(study: Path) -> int:
    """Amend the slate: H2 is withdrawn and its corrected form gets a NEW id.

    A statement is frozen under an id (``slate.FROZEN_ROW_KEYS``), so "fix the
    denominator" is exactly what the slate protocol says it is — a new row with a
    new id, the old one retained in the cohort.
    """
    path = study / "slates" / f"{PHASE}.yaml"
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    rows = [row for row in payload["rows"] if row["id"] != f"{STUDY}#H2"]
    rows.insert(
        1,
        _row(
            5,
            p=0.3,
            success=("P2",),
            statement="candidate 2 moves val_auc, over every batch attempted",
        ),
    )
    payload["rows"] = rows
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return _gen("slate", "amend", "--study", str(study), "--phase", PHASE)


def _premortem_detail(study: Path) -> str:
    return " ".join(
        check["detail"]
        for check in _receipt(study)["checks"]
        if check["name"] == "generation premortem"
    )


def _set_roster(repo: Path, study: Path, role: str, who: str) -> None:
    path = study / "program.md"
    text = path.read_text(encoding="utf-8").replace(
        f"| {role} | | |", f"| {role} | {who} | 2026-09-05 |"
    )
    path.write_text(text, encoding="utf-8")
    commit_all(repo, f"roster: {role}")


# --------------------------------------------------------------------------
# V-13 — the A3 §7 smallest exercise
# --------------------------------------------------------------------------


def test_v13_the_planted_denominator_is_accepted_and_reaches_the_first_measurement(
    premortem_study,
) -> None:
    """A3 §7: the review names the defect, the fix is hashed, the run is admitted."""
    _repo, study = premortem_study
    assert _lock(study, V11_ROWS) == 0
    draft = _slate_sha(study)

    _write_review(study, slate_sha=draft)
    assert _record(study) == 0
    recorded = premortem.records(study, read_events(study), PHASE)[-1]["object"]
    assert [issue["id"] for issue in recorded["issues"]] == ["I1", "I2"]
    assert recorded["slate_object"] == draft
    assert recorded["independence"] == "self-attested"
    assert recorded["late"] is False
    assert "responses" not in recorded, "a record carries the issues, never the answers"

    # the review is recorded and unanswered: no hypothesis of the phase may run
    _bump(study, "too early")
    assert _check(study, f"{STUDY}#H1", "P1") == 2

    # the driver accepts I1 by producing a NEW slate version, and defers I2
    assert _fix_h2(study) == 0
    fixed = _slate_sha(study)
    assert fixed != draft
    _write_review(
        study,
        slate_sha=draft,
        responses=[
            _answer("I1", "accept", changed=fixed, why="the denominator now counts every batch"),
            _answer("I2", "defer", why="next phase"),
        ],
    )
    assert _respond(study) == 2, "a deferred blocking mechanical issue is not an answer"

    # …and then answers the second blocker too
    _write_review(
        study,
        slate_sha=draft,
        responses=[
            _answer("I1", "accept", changed=fixed, why="the denominator now counts every batch"),
            _answer("I2", "accept", changed=fixed, why="every row now names its partition"),
        ],
    )
    assert _respond(study) == 0
    answer = premortem.responses(study, read_events(study), PHASE)[-1]["object"]
    assert [row["issue"] for row in answer["responses"]] == ["I1", "I2"]
    assert {row["changed_artifact_hash"] for row in answer["responses"]} == {fixed}

    # the corrected slate is what runs
    _bump(study, "h1")
    assert _check(study, f"{STUDY}#H1", "P1") == 0
    assert run_one(study, command=metric_command(0.7), tests="P1", echo=False)["disposition"] in (
        "keep",
        "discard",
    )

    assert _gen("verify", "--study", str(study)) == 0
    receipt = _receipt(study)
    assert receipt["capabilities"]["premortem"] == {
        "integrity": "PASS",
        "outcome": "self-attested",
        "phases": {
            PHASE: {"reviews": 1, "issues": 2, "answered": True, "independence": "self-attested"}
        },
    }
    assert _statuses(receipt, "generation premortem") == ["PASS", "WARN"]
    assert "no session receipt" in _premortem_detail(study)


def test_v13_the_admission_receipt_pins_the_review_it_rests_on(premortem_study) -> None:
    """WP-00b's `receipt_inputs` hook: `inputs.premortem` is the record's object sha."""
    _repo, study = premortem_study
    assert _lock(study, V11_ROWS) == 0
    draft = _slate_sha(study)
    _write_review(study, slate_sha=draft, issues=[_issue("I1", "slate", severity="minor")])
    assert _record(study) == 0
    record_sha = premortem.records(study, read_events(study), PHASE)[-1]["sha"]
    _write_review(
        study,
        slate_sha=draft,
        issues=[_issue("I1", "slate", severity="minor")],
        responses=[_answer("I1", "reject", why="the axis is scored as authored")],
    )
    assert _respond(study) == 0

    _bump(study, "h1")
    assert _check(study, f"{STUDY}#H1", "P1") == 0
    events = read_events(study)
    receipt = json.loads(
        (
            study / "generation" / "objects" / f"{events[-1]['payload_sha256']}.json"
        ).read_text(encoding="utf-8")
    )
    assert receipt["inputs"]["premortem"] == record_sha
    assert receipt["inputs"]["slate"] == draft
    assert receipt["verdict"] == "admitted"


def test_v13_a_minor_scientific_objection_may_be_rejected_with_a_rationale(
    premortem_study,
) -> None:
    """The reviewer supplies arguments, not a veto: only mechanical blockers gate."""
    _repo, study = premortem_study
    assert _lock(study, V11_ROWS) == 0
    draft = _slate_sha(study)
    issues = [
        _issue("I1", "slate", severity="blocking", kind="scientific", text="the lever is a fad"),
        _issue("I2", f"{STUDY}#H3", severity="major", kind="mechanical", text="cost looks low"),
    ]
    _write_review(study, slate_sha=draft, issues=issues)
    assert _record(study) == 0
    _write_review(
        study,
        slate_sha=draft,
        issues=issues,
        responses=[
            _answer("I1", "reject", why="the method card's when-it-pays conditions hold here"),
            _answer("I2", "defer", why="the budget is re-derived at the phase boundary"),
        ],
    )
    assert _respond(study) == 0
    _bump(study, "h1")
    assert _check(study, f"{STUDY}#H1", "P1") == 0
    assert _gen("verify", "--study", str(study)) == 0
    assert _receipt(study)["capabilities"]["premortem"]["integrity"] == "PASS"


# --------------------------------------------------------------------------
# V-13 — the invalid controls
# --------------------------------------------------------------------------


def test_v13_a_review_recorded_after_a_hypothesis_run_fails_forever(premortem_study) -> None:
    """V-13: a pre-mortem written after the evidence started arriving criticised nothing."""
    _repo, study = premortem_study
    assert _lock(study, V11_ROWS) == 0
    draft = _slate_sha(study)

    # no premortem is recorded yet, so the admission rule must refuse …
    _bump(study, "h1")
    assert _check(study, f"{STUDY}#H1", "P1") == 2
    # … and the driver runs anyway, off the record's advice
    run_one(study, command=metric_command(0.7), tests="P1", echo=False)

    _write_review(study, slate_sha=draft)
    assert _record(study) == 2, "a late review is refused before it is recorded"
    assert _record(study, "--allow-late") == 0
    assert premortem.records(study, read_events(study), PHASE)[-1]["object"]["late"] is True

    assert _gen("verify", "--study", str(study)) == 2
    assert "FAIL" in _statuses(_receipt(study), "generation premortem")
    assert "after a hypothesis admission" in _premortem_detail(study)


def test_v13_the_reviewer_may_not_be_the_closing_referee(premortem_study) -> None:
    """RF-12 / R-PRE-3: the proposal critic is not the closing referee."""
    repo, study = premortem_study
    _set_roster(repo, study, "referee", REVIEWER)
    assert _lock(study, V11_ROWS) == 0
    draft = _slate_sha(study)
    _write_review(study, slate_sha=draft, issues=[_issue("I1", "slate", severity="minor")])
    assert _record(study) == 0

    assert _gen("verify", "--study", str(study)) == 2
    assert "FAIL" in _statuses(_receipt(study), "generation premortem")
    assert "closing referee" in _premortem_detail(study)


def test_v13_a_reviewer_who_is_the_experimenter_is_a_warning_not_a_failure(
    premortem_study,
) -> None:
    """A red team of one's own slate raises no rung — and fails nothing."""
    repo, study = premortem_study
    _set_roster(repo, study, "experimenter", REVIEWER)
    assert _lock(study, V11_ROWS) == 0
    draft = _slate_sha(study)
    issues = [_issue("I1", "slate", severity="minor")]
    _write_review(study, slate_sha=draft, issues=issues)
    assert _record(study) == 0
    _write_review(
        study, slate_sha=draft, issues=issues, responses=[_answer("I1", "reject", why="noted")]
    )
    assert _respond(study) == 0

    assert _gen("verify", "--study", str(study)) == 0
    assert _statuses(_receipt(study), "generation premortem") == ["PASS", "WARN", "WARN"]
    assert "matches the roster experimenter" in _premortem_detail(study)


def test_v13_an_accept_must_name_a_new_slate_version(premortem_study) -> None:
    """`accept` requires a changed artifact hash, and it must BE a later slate."""
    _repo, study = premortem_study
    assert _lock(study, V11_ROWS) == 0
    draft = _slate_sha(study)
    issues = [_issue("I1", f"{STUDY}#H2")]
    _write_review(study, slate_sha=draft, issues=issues)
    assert _record(study) == 0
    # the correction lands first: the answer names the version it produced
    assert _fix_h2(study) == 0

    # no hash at all; a hash that is not an object; the very draft under review
    for changed in (None, "0" * 64, draft):
        _write_review(
            study,
            slate_sha=draft,
            issues=issues,
            responses=[_answer("I1", "accept", changed=changed, why="fixed")],
        )
        assert _respond(study) == 2, changed

    _write_review(
        study,
        slate_sha=draft,
        issues=issues,
        responses=[_answer("I1", "accept", changed=_slate_sha(study), why="fixed")],
    )
    assert _respond(study) == 0


def test_v13_a_second_response_and_a_missing_one_are_both_refused(premortem_study) -> None:
    _repo, study = premortem_study
    assert _lock(study, V11_ROWS) == 0
    draft = _slate_sha(study)
    issues = [_issue("I1", "slate", severity="minor"), _issue("I2", "design", severity="minor")]
    _write_review(study, slate_sha=draft, issues=issues)
    assert _record(study) == 0

    _write_review(
        study, slate_sha=draft, issues=issues, responses=[_answer("I1", "reject", why="noted")]
    )
    assert _respond(study) == 2, "an unanswered issue is not a rejected one"
    _write_review(
        study,
        slate_sha=draft,
        issues=issues,
        responses=[
            _answer("I1", "reject", why="noted"),
            _answer("I1", "defer", why="twice"),
            _answer("I2", "defer", why="noted"),
        ],
    )
    assert _respond(study) == 2, "one response per issue, exactly"


def test_v13_the_issues_cannot_move_between_record_and_respond(premortem_study) -> None:
    """A recorded review is immutable — answering it may not rewrite what it said."""
    _repo, study = premortem_study
    assert _lock(study, V11_ROWS) == 0
    draft = _slate_sha(study)
    _write_review(study, slate_sha=draft, issues=[_issue("I1", f"{STUDY}#H2")])
    assert _record(study) == 0
    _write_review(
        study,
        slate_sha=draft,
        issues=[_issue("I1", f"{STUDY}#H2", severity="minor", text="never mind")],
        responses=[_answer("I1", "reject", why="downgraded on the way past")],
    )
    assert _respond(study) == 2


def test_v13_editing_the_review_after_the_answer_fails_verification(premortem_study) -> None:
    """The file is frozen from the moment a response is recorded."""
    _repo, study = premortem_study
    assert _lock(study, V11_ROWS) == 0
    draft = _slate_sha(study)
    issues = [_issue("I1", "slate", severity="minor")]
    _write_review(study, slate_sha=draft, issues=issues)
    assert _record(study) == 0
    _write_review(
        study, slate_sha=draft, issues=issues, responses=[_answer("I1", "reject", why="noted")]
    )
    assert _respond(study) == 0
    assert _gen("verify", "--study", str(study)) == 0

    path = study / "premortem" / f"{PHASE}.yaml"
    path.write_text(
        path.read_text(encoding="utf-8").replace("noted", "noted, and I was right"),
        encoding="utf-8",
    )
    assert _gen("verify", "--study", str(study)) == 2
    assert "FAIL" in _statuses(_receipt(study), "generation premortem")
    assert "immutable" in _premortem_detail(study)


def test_a_record_refuses_a_stale_draft_and_an_unanswered_predecessor(premortem_study) -> None:
    _repo, study = premortem_study
    assert _lock(study, V11_ROWS) == 0
    draft = _slate_sha(study)
    _write_review(study, slate_sha=draft, issues=[_issue("I1", "slate", severity="minor")])
    assert _record(study) == 0
    assert _record(study) == 1, "the open review must be answered before another is recorded"

    _write_review(
        study,
        slate_sha=draft,
        issues=[_issue("I1", "slate", severity="minor")],
        responses=[_answer("I1", "reject", why="noted")],
    )
    assert _respond(study) == 0
    assert _fix_h2(study) == 0
    # a second review must name the version now in force, not the superseded draft
    _write_review(study, slate_sha=draft, issues=[_issue("I2", "slate", severity="minor")])
    assert _record(study) == 2
    _write_review(
        study, slate_sha=_slate_sha(study), issues=[_issue("I2", "slate", severity="minor")]
    )
    assert _record(study) == 0


def test_a_record_refuses_an_input_bundle_that_omits_the_draft_slate(premortem_study) -> None:
    _repo, study = premortem_study
    assert _lock(study, V11_ROWS) == 0
    _write_review(study, slate_sha=_slate_sha(study), inputs=["study.yaml"])
    assert _record(study) == 2
    _write_review(
        study, slate_sha=_slate_sha(study), inputs=["study.yaml", "no_such_file.md",
                                                   f"slates/{PHASE}.yaml"]
    )
    assert _record(study) == 2


def test_a_session_receipt_lifts_the_outcome_to_receipted(premortem_study) -> None:
    """Independence is self-attested unless an artefact exists; the record says which."""
    repo, study = premortem_study
    (study / "review-session.md").write_text("the reviewer's transcript\n", encoding="utf-8")
    commit_all(repo, "the reviewer's session receipt")
    assert _lock(study, V11_ROWS) == 0
    draft = _slate_sha(study)
    issues = [_issue("I1", "slate", severity="minor")]
    _write_review(study, slate_sha=draft, issues=issues)
    assert _record(study, "--session-receipt", "review-session.md") == 0
    obj = premortem.records(study, read_events(study), PHASE)[-1]["object"]
    assert obj["independence"] == "receipted"
    assert obj["session_receipt_sha256"]
    assert obj["reviewer"]["session_receipt"] == "review-session.md"

    _write_review(
        study,
        slate_sha=draft,
        issues=issues,
        reviewer={
            "name": REVIEWER,
            "model": "opus",
            "tool": "pytest",
            "session_receipt": "review-session.md",
        },
        responses=[_answer("I1", "reject", why="noted")],
    )
    assert _respond(study) == 0
    assert _gen("verify", "--study", str(study)) == 0
    assert _receipt(study)["capabilities"]["premortem"]["outcome"] == "receipted"
    assert _statuses(_receipt(study), "generation premortem") == ["PASS"]


def test_a_receipt_that_is_not_a_file_is_refused(premortem_study) -> None:
    _repo, study = premortem_study
    assert _lock(study, V11_ROWS) == 0
    _write_review(study, slate_sha=_slate_sha(study), issues=[_issue("I1", "slate")])
    assert _record(study, "--session-receipt", "no-such-session.md") == 1


def test_an_input_whose_bytes_were_never_committed_fails_the_bundle_check(
    premortem_study,
) -> None:
    """The bundle is recomputed from the commit that introduced the record."""
    _repo, study = premortem_study
    assert _lock(study, V11_ROWS) == 0
    # train.py is the mutable surface: legitimately uncommitted, and therefore
    # not something a reviewer can be said to have been handed on the record.
    _bump(study, "an uncommitted candidate")
    _write_review(
        study,
        slate_sha=_slate_sha(study),
        issues=[_issue("I1", "slate", severity="minor")],
        inputs=["study.yaml", f"slates/{PHASE}.yaml", "train.py"],
    )
    assert _record(study) == 0
    assert _gen("verify", "--study", str(study)) == 2
    assert "input bundle recomputes" in _premortem_detail(study)


# --------------------------------------------------------------------------
# write ownership and the boundary
# --------------------------------------------------------------------------


def test_a_premortem_commit_files_the_review_and_the_ledger_and_nothing_else(
    premortem_study,
) -> None:
    repo, study = premortem_study
    assert _lock(study, V11_ROWS) == 0
    _bump(study, "operator edit that must survive")
    _write_review(study, slate_sha=_slate_sha(study), issues=[_issue("I1", "slate")])
    assert _record(study) == 0
    names = git(repo, "show", "--name-only", "--format=", "HEAD").split()
    assert names
    assert all(
        "/premortem/" in f"/{name}" or "/generation/" in f"/{name}" for name in names
    ), names
    assert "train.py" in git(repo, "status", "--porcelain"), "the candidate stayed the operator's"


BANNED_FUNCTION_PREFIXES = (
    "propose",
    "generate",
    "rank",
    "select",
    "suggest",
    "choose",
    "recommend",
    "invent",
    "score",
)


def test_the_premortem_module_never_proposes_ranks_or_selects() -> None:
    """R-PRE-3: the pre-mortem records issues and responses; it scores nothing."""
    text = (GENERATION_PKG / "premortem.py").read_text(encoding="utf-8")
    tree = ast.parse(text)
    offenders = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and node.name.lstrip("_").startswith(BANNED_FUNCTION_PREFIXES)
    ]
    assert not offenders, f"premortem.py defines {offenders} — the layer never generates"
    for banned in ("run_one", "subprocess", "requests", "httpx", "urllib", "socket"):
        assert f"import {banned}" not in text and f"from {banned}" not in text
    assert "run_one(" not in text


def test_the_capability_is_registered_in_both_lists() -> None:
    from kleinlib.generation.capabilities import load
    from kleinlib.generation.manifest import CAPABILITY_DEPENDENCIES, SUPPORTED_CAPABILITIES

    assert "premortem" in SUPPORTED_CAPABILITIES
    assert load()["premortem"] is premortem.CAPABILITY
    assert CAPABILITY_DEPENDENCIES["premortem"] == ("slates",)


def test_premortem_without_slates_is_refused_at_init(tmp_path: Path) -> None:
    """The dependency is enforced where it was always encoded."""
    repo, study = _scaffold(tmp_path)
    assert _gen("init", "--study", str(study), "--capability", "premortem") != 0
    assert not (study / "generation" / "manifest.yaml").exists()
    assert git(repo, "status", "--porcelain") == ""
