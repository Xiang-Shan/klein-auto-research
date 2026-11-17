"""``klein map`` — the study as a graph: question → predictions → evidence → claims → decisions.

Derived, read-only, and honest about what is still open.  The finalized Hubble
exhibit is the oracle; a fresh scaffold and a one-run ledger cover the open states.
"""

from __future__ import annotations

import contextlib
import io
import json
import re
import subprocess
from pathlib import Path

import pytest
from test_predictions import PREDICTIONS
from test_registered_mode import CELL_SOURCE, amend
from test_workflow_v3 import commit_all, metric_command

from kleinlib import api, cli
from kleinlib import study_map as sm
from kleinlib.workflow import run_one

REPO_ROOT = Path(__file__).resolve().parents[2]
HUBBLE = REPO_ROOT / "studies" / "10-hubble-1929-replication"


KIND_AXES = ("replicate", "tabular", "generic")


def _studies_status() -> str:
    result = subprocess.run(
        ["git", "status", "--porcelain", "--", "studies"], cwd=REPO_ROOT, text=True, capture_output=True, check=False
    )
    return result.stdout


def _main(argv: list[str]) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = cli.main(argv)
    return code, out.getvalue()


@pytest.fixture(scope="module")
def hubble() -> dict:
    return sm.build_map(HUBBLE)


@pytest.fixture
def ledger_study(ready_study):
    """A registered lane with three predictions (P1, P2 ruled; P3 manual), nothing run yet."""
    repo, study = ready_study
    (study / "train.py").write_text(CELL_SOURCE, encoding="utf-8")

    def register(contract: dict) -> None:
        contract["tracks"]["primary"]["mode"] = "registered"
        contract["entrypoint"]["command"] = ["python", "-u", "train.py"]
        contract["predictions"] = [dict(entry) for entry in PREDICTIONS]

    amend(study, register, note="three registered predictions")
    commit_all(repo, "a registered lane with a ledger")
    return repo, study


def _edges(data: dict, *, source: str | None = None, target: str | None = None) -> list[dict]:
    return [
        e for e in data["edges"] if (source is None or e["from"] == source) and (target is None or e["to"] == target)
    ]


# --------------------------------------------------------------------------
# the finalized exhibit
# --------------------------------------------------------------------------


def test_the_hubble_map_counts_what_the_study_holds(hubble) -> None:
    assert hubble["counts"] == {"question": 5, "prediction": 10, "run": 13, "probe": 0, "claim": 18, "decision": 7}
    assert (hubble["status"], hubble["label"]) == ("finalized", "confirmed")
    assert hubble["study"] == "10-hubble-1929-replication"
    assert (hubble["kind"], hubble["modality"], hubble["profile"]) == KIND_AXES
    assert len(hubble["nodes"]) == sum(hubble["counts"].values())


def test_every_edge_endpoint_is_a_node_and_every_node_id_is_unique(hubble) -> None:
    ids = [node["id"] for node in hubble["nodes"]]
    assert len(ids) == len(set(ids))
    for edge in hubble["edges"]:
        assert edge["from"] in ids and edge["to"] in ids, edge
        assert edge["type"]
    assert len({(e["from"], e["to"], e["type"]) for e in hubble["edges"]}) == len(hubble["edges"])


def test_claims_come_in_natural_order_not_text_order(hubble) -> None:
    claims = [node["id"] for node in hubble["nodes"] if node["type"] == "claim"]
    assert claims == [f"C{i}" for i in range(1, 19)]  # C10 after C9, never after C1


def test_a_finalized_study_has_nothing_open_and_names_its_inconclusive_leads(hubble) -> None:
    assert hubble["open"] == []
    lead_ids = {lead["id"] for lead in hubble["leads"] if lead["kind"] == "prediction-inconclusive"}
    assert lead_ids == {"P2", "P3"}
    assert {lead["kind"] for lead in hubble["leads"]} <= {"prediction-inconclusive", "claim-unconfirmed"}


def test_a_refuted_prediction_is_linked_to_its_run_and_to_the_decision_that_answered_it(hubble) -> None:
    nodes = {n["id"]: n for n in hubble["nodes"]}
    assert nodes["P9"]["verdict"] == "refuted"
    incoming = _edges(hubble, target="P9")
    refuted_from = [e["from"] for e in incoming if e["type"] == "refuted"]
    assert len(refuted_from) == 1 and nodes[refuted_from[0]]["type"] == "run"
    decided_by = [e["from"] for e in incoming if e["type"] == "decides"]
    assert decided_by and all(nodes[d]["type"] == "decision" for d in decided_by)


def test_claims_answer_questions_and_rest_on_runs(hubble) -> None:
    nodes = {n["id"]: n for n in hubble["nodes"]}
    answered = {e["to"] for e in hubble["edges"] if e["type"] == "answers"}
    assert answered == {n["id"] for n in hubble["nodes"] if n["type"] == "question"}
    supports = [e for e in hubble["edges"] if e["type"] == "supports"]
    assert supports and all(nodes[e["from"]]["type"] == "run" and nodes[e["to"]]["type"] == "claim" for e in supports)


def test_the_text_map_names_every_question_and_says_nothing_is_open(hubble) -> None:
    text = sm.format_map(hubble)
    for question in (n["id"] for n in hubble["nodes"] if n["type"] == "question"):
        assert f"{question}  " in text
    assert re.search(r"RQ\d", text)
    assert "still open: nothing" in text
    assert "5 question(s) · 10 prediction(s) · 13 run(s) · 18 claim(s) · 7 decision(s)" in text
    assert "leads for a follow-up study" in text and "P2" in text and "P3" in text


def test_the_html_map_is_one_document_with_no_script_and_no_network(hubble) -> None:
    page = sm.render_html(hubble)
    assert page.startswith("<!doctype html>")
    assert page.count("<html") == 1 and page.count("</html>") == 1 and page.count("<svg") == 1
    assert "<script" not in page.lower()
    assert "http://" not in page and "https://" not in page
    assert "<link" not in page and "src=" not in page
    assert hubble["study"] in page and "Nothing: every prediction is decided" in page


def test_the_html_escapes_what_the_records_say() -> None:
    data = {
        "study": "x<b>", "goal": "<script>alert(1)</script>", "kind": "test", "modality": "none", "profile": "generic",
        "status": "active", "label": None, "gates": {}, "tracks": [],
        "counts": dict.fromkeys(("question", "prediction", "run", "probe", "claim", "decision"), 0),
        "nodes": [], "edges": [], "open": [], "leads": [],
    }
    page = sm.render_html(data)
    assert "<script" not in page and "x<b>" not in page
    assert "&lt;script&gt;" in page


def test_klein_map_html_writes_one_file_and_leaves_the_exhibit_untouched(tmp_path: Path) -> None:
    before = _studies_status()
    target = tmp_path / "out" / "map.html"
    code, out = _main(["map", "--study", str(HUBBLE), "--html", str(target)])
    assert code == 0 and f"wrote {target}" in out
    assert target.read_text(encoding="utf-8").startswith("<!doctype html>")
    assert _studies_status() == before


def test_klein_map_json_is_the_graph_in_the_envelope(tmp_path: Path) -> None:
    code, out = _main(["map", "--study", str(HUBBLE), "--json"])
    env = json.loads(out)
    assert code == 0 and env["verb"] == "map" and env["ok"] is True
    assert env["data"]["counts"]["claim"] == 18 and env["data"]["open"] == []
    assert env["data"] == api.study_map(HUBBLE)["data"]
    code, out = _main(["map", "--study", str(HUBBLE), "--html", str(tmp_path / "m.html"), "--json"])
    assert json.loads(out)["data"]["html"] == str(tmp_path / "m.html")


def test_klein_map_text_prints_the_map() -> None:
    code, out = _main(["map", "--study", str(HUBBLE)])
    assert code == 0 and out.startswith("study: 10-hubble-1929-replication")


# --------------------------------------------------------------------------
# a study with nothing yet
# --------------------------------------------------------------------------


def test_a_fresh_study_builds_a_map_with_its_question_unanswered(ready_study) -> None:
    _repo, study = ready_study
    data = sm.build_map(study)
    assert data["counts"] == {"question": 1, "prediction": 0, "run": 0, "probe": 0, "claim": 0, "decision": 0}
    assert [(o["kind"], o["id"]) for o in data["open"]] == [("question-unanswered", "RQ1")]
    assert "still open (1):" in sm.format_map(data)
    assert sm.render_html(data).startswith("<!doctype html>")


def test_registered_but_unadjudicated_predictions_are_open(ledger_study) -> None:
    _repo, study = ledger_study
    data = sm.build_map(study)
    open_predictions = {o["id"] for o in data["open"] if o["kind"] == "prediction-open"}
    assert open_predictions == {"P1", "P2", "P3"}
    assert data["counts"]["prediction"] == 3
    # No run and no claim yet: the only links are the contract's own — a study with
    # one question has every prediction bear on it.
    questions = [n["id"] for n in data["nodes"] if n["type"] == "question"]
    assert len(questions) == 1
    assert sorted((e["from"], e["to"], e["type"]) for e in data["edges"]) == [
        (questions[0], pid, "predicts") for pid in ("P1", "P2", "P3")
    ]
    assert all(n["verdict"] == "open" for n in data["nodes"] if n["type"] == "prediction")


def test_a_run_that_adjudicates_a_prediction_closes_it_and_links_the_run(ledger_study) -> None:
    _repo, study = ledger_study
    run_one(study, command=metric_command(0.7), tests=["P1"], description="clears 0.6?", echo=False)
    data = sm.build_map(study)
    nodes = {n["id"]: n for n in data["nodes"]}
    assert nodes["E0001"]["type"] == "run" and nodes["E0001"]["disposition"] == "measured"
    assert nodes["P1"]["verdict"] == "supported"
    assert _edges(data, source="E0001", target="P1") == [{"from": "E0001", "to": "P1", "type": "supported"}]
    assert {o["id"] for o in data["open"] if o["kind"] == "prediction-open"} == {"P2", "P3"}


# --------------------------------------------------------------------------
# the Decision: parser
# --------------------------------------------------------------------------

PROGRAM = """\
# Program

## Decisions
- 2026-03-01 **Decision:** drop E0002 (see P1) because
  the surrogate leaked; rerun as E0003.
- 2026-03-02 Decision: keep the anchor.

Decision: GO
> **Decision:** **GO** (data card, undated)
2026-03-03 a very long way before we finally say Decision: too far from its date
"""


def test_decisions_parser_takes_dated_entries_and_their_continuation_lines() -> None:
    found = sm._decisions(PROGRAM)
    assert [d["id"] for d in found] == ["D1", "D2"]
    assert [d["date"] for d in found] == ["2026-03-01", "2026-03-02"]
    assert found[0]["text"] == "drop E0002 (see P1) because the surrogate leaked; rerun as E0003."
    assert found[0]["mentions"] == ["E0002", "E0003", "P1"]
    assert found[1]["text"] == "keep the anchor." and found[1]["mentions"] == []


def test_decisions_parser_ignores_an_undated_decision_line() -> None:
    assert sm._decisions("Decision: GO\n> **Decision:** **GO**\n") == []
    assert sm._decisions("") == []


def test_a_continuation_stops_at_a_blank_line_a_bullet_or_a_heading() -> None:
    text = "- 2026-01-01 Decision: first\nsecond line\n\nunrelated\n- 2026-01-02 Decision: next\n## Heading\n"
    found = sm._decisions(text)
    assert [d["text"] for d in found] == ["first second line", "next"]


def test_a_prediction_may_name_its_question_and_the_contract_checks_the_name() -> None:
    from kleinlib.contract import _predictions_problems

    contract = {
        "research_questions": [{"id": "RQ1", "question": "a?"}, {"id": "RQ2", "question": "b?"}],
        "tracks": {"primary": {}},
        "predictions": [
            {"id": "P1", "track": "primary", "statement": "s", "question": "RQ2",
             "rule": {"key": "primary_metric", "op": ">", "value": 0.5}},
        ],
    }
    assert not [p for p in _predictions_problems(contract) if "question" in p]
    contract["predictions"][0]["question"] = "RQ9"
    assert any("question must name a declared research question" in p for p in _predictions_problems(contract))
