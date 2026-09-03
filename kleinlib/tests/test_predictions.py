"""E6 — the predictions ledger: mechanized belief revision.

A registered prediction is a belief written down BEFORE the evidence, with the
arithmetic that will decide it.  What is pinned here:

1. every operator of the rule grammar decides correctly, three-valued;
2. a missing printed key is `inconclusive`, never a refutation — and NOTHING on
   this path executes contract text (a grep test, because the whole point of a
   closed operator set is that it is closed);
3. `run-one --tests` writes the verdict into the manifest, the state and the
   event chain, INSIDE the transaction;
4. `klein predict adjudicate` records what the notary cannot read, pinning
   every path it is given;
5. `finalize` refuses to close over an open or unreported prediction.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest
import yaml
from test_registered_mode import CELL_SOURCE, amend, edit_cell
from test_workflow_v3 import commit_all, metric_command

from kleinlib import cli
from kleinlib.decision import adjudicate, evaluate_rule
from kleinlib.predictions import (
    counts,
    findings_prediction_ids,
    ledger,
    open_predictions,
)
from kleinlib.workflow import (
    WorkflowError,
    finalize,
    load_contract,
    load_state,
    read_events,
    run_one,
    status_summary,
)

PRINTED = {"primary_metric": 454.16, "ci_low": 336.4, "ci_high": 571.9, "n": 24.0}


# ---------------------------------------------------------------------------
# 1. the operator set, one row per operator
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("rule", "expected"),
    [
        ({"key": "ci_low", "op": ">", "value": 70}, "supported"),
        ({"key": "ci_low", "op": ">", "value": 700}, "refuted"),
        ({"key": "ci_low", "op": "gt", "value": 70}, "supported"),
        ({"key": "n", "op": "ge", "value": 24}, "supported"),
        ({"key": "n", "op": "lt", "value": 24}, "refuted"),
        ({"key": "n", "op": "le", "value": 24}, "supported"),
        ({"key": "n", "op": "ne", "value": 24}, "refuted"),
        ({"key": "n", "op": "!=", "value": 25}, "supported"),
        ({"key": "n", "op": "eq", "value": 24, "tol": 0}, "supported"),
        ({"key": "n", "op": "==", "value": 24.4, "tol": 0.5}, "supported"),
        ({"key": "n", "op": "eq", "value": 24.4, "tol": 0.1}, "refuted"),
        ({"key": "n", "op": "abs_lt", "value": 25}, "supported"),
        ({"key": "n", "op": "abs_le", "value": 24}, "supported"),
        ({"key": "n", "op": "abs_lt", "value": 24}, "refuted"),
        ({"key": "primary_metric", "op": "within", "target": 450, "tol": 10}, "supported"),
        ({"key": "primary_metric", "op": "within", "target": 450, "tol": 1}, "refuted"),
        (
            {"key": "primary_metric", "op": "within", "value": {"target": 450, "tol": 10}},
            "supported",
        ),
        ({"key": "primary_metric", "op": "between", "value": [400, 500]}, "supported"),
        ({"key": "primary_metric", "op": "between", "low": 400, "high": 500}, "supported"),
        ({"key": "primary_metric", "op": "between", "value": [0, 100]}, "refuted"),
    ],
)
def test_every_operator_decides_the_printed_block(rule: dict, expected: str) -> None:
    verdict, explanation = evaluate_rule(rule, PRINTED)
    assert verdict == expected
    assert explanation.endswith(f"→ {expected}")


def test_the_explanation_is_arithmetic_on_the_record() -> None:
    """A reader re-checks the decision without re-running anything."""
    _, explanation = evaluate_rule({"key": "ci_low", "op": ">", "value": 70}, PRINTED)
    assert explanation == "ci_low 336.4 > 70 → supported"


def test_a_missing_key_is_inconclusive_never_a_refutation() -> None:
    verdict, explanation = evaluate_rule({"key": "bootstrap_se", "op": "<", "value": 1}, PRINTED)
    assert verdict == "inconclusive"
    assert "was not printed" in explanation


def test_a_non_numeric_printed_value_is_inconclusive() -> None:
    verdict, _ = evaluate_rule(
        {"key": "label", "op": "<", "value": 1}, {"label": "not-a-number"}
    )
    assert verdict == "inconclusive"


# --- combinators, three-valued ---------------------------------------------


def test_all_of_is_refuted_by_one_refuted_child() -> None:
    verdict, explanation = evaluate_rule(
        {
            "all_of": [
                {"key": "ci_low", "op": ">", "value": 70},
                {"key": "n", "op": ">", "value": 1000},
            ]
        },
        PRINTED,
    )
    assert verdict == "refuted"
    assert "ci_low 336.4 > 70 → supported" in explanation


def test_all_of_is_inconclusive_when_a_child_could_not_be_decided() -> None:
    verdict, _ = evaluate_rule(
        {
            "all_of": [
                {"key": "ci_low", "op": ">", "value": 70},
                {"key": "absent", "op": ">", "value": 1},
            ]
        },
        PRINTED,
    )
    assert verdict == "inconclusive"


def test_any_of_is_supported_by_one_supported_child() -> None:
    verdict, _ = evaluate_rule(
        {
            "any_of": [
                {"key": "absent", "op": ">", "value": 1},
                {"key": "ci_low", "op": ">", "value": 70},
            ]
        },
        PRINTED,
    )
    assert verdict == "supported"


def test_any_of_refutes_only_when_every_child_was_decided_against() -> None:
    assert evaluate_rule(
        {
            "any_of": [
                {"key": "ci_low", "op": ">", "value": 1e9},
                {"key": "n", "op": ">", "value": 1e9},
            ]
        },
        PRINTED,
    )[0] == "refuted"


def test_not_swaps_supported_and_refuted_and_leaves_inconclusive_alone() -> None:
    assert evaluate_rule({"not": {"key": "n", "op": ">", "value": 1000}}, PRINTED)[0] == "supported"
    assert evaluate_rule({"not": {"key": "n", "op": ">", "value": 1}}, PRINTED)[0] == "refuted"
    assert (
        evaluate_rule({"not": {"key": "absent", "op": ">", "value": 1}}, PRINTED)[0]
        == "inconclusive"
    )


def test_nesting_past_the_declared_depth_is_inconclusive_not_a_crash() -> None:
    deep = {"all_of": [{"any_of": [{"not": {"key": "n", "op": ">", "value": 1}}]}]}
    assert evaluate_rule(deep, PRINTED)[0] == "inconclusive"


# --- inconclusive_if --------------------------------------------------------


def test_inconclusive_if_is_applied_before_the_rule() -> None:
    prediction = {
        "id": "P1",
        "statement": "the interval clears 70",
        "rule": {"key": "ci_low", "op": ">", "value": 70},
        "inconclusive_if": {"key": "n", "op": "<", "value": 30},
    }
    verdict, explanation = adjudicate(prediction, PRINTED)
    assert verdict == "inconclusive"
    assert explanation.startswith("inconclusive_if fired:")


def test_a_sentence_inconclusive_if_documents_but_never_fires() -> None:
    prediction = {
        "id": "P1",
        "statement": "…",
        "rule": {"key": "ci_low", "op": ">", "value": 70},
        "inconclusive_if": "the bootstrap did not converge",
    }
    assert adjudicate(prediction, PRINTED)[0] == "supported"


def test_a_manual_prediction_is_never_decided_by_arithmetic() -> None:
    verdict, explanation = adjudicate({"id": "P9", "manual": True}, PRINTED)
    assert verdict == "inconclusive"
    assert "klein predict adjudicate" in explanation


# ---------------------------------------------------------------------------
# 2. the closed operator set is CLOSED
# ---------------------------------------------------------------------------


#: A bare `eval(`/`exec(`/`compile(` call — `re.compile(...)` is a method on a
#: module object and is not what this test is about.
DYNAMIC_EXECUTION_RE = re.compile(r"(?<![\w.])(?:eval|exec|compile|__import__)\s*\(")


def test_no_eval_exec_or_compile_anywhere_on_the_adjudication_path() -> None:
    """Contract text is data.  A rule is never executed, however it is spelled."""
    root = Path(__file__).resolve().parents[1]
    for name in ("decision.py", "predictions.py", "cli_predict.py"):
        source = (root / name).read_text(encoding="utf-8")
        found = DYNAMIC_EXECUTION_RE.findall(source)
        assert not found, f"{name} reaches for dynamic execution: {found}"


# ---------------------------------------------------------------------------
# 3. --tests, end to end on a measured cell
# ---------------------------------------------------------------------------


PREDICTIONS = [
    {
        "id": "P1",
        "track": "primary",
        "statement": "the measured value clears 0.6",
        "rule": {"key": "primary_metric", "op": ">", "value": 0.6},
    },
    {
        "id": "P2",
        "track": "primary",
        "statement": "the spread stays under 0.01",
        "rule": {"key": "spread", "op": "<", "value": 0.01},
    },
    {"id": "P3", "track": "primary", "statement": "the referee finds the table readable", "manual": True},
]


@pytest.fixture
def ledger_study(ready_study_v3) -> tuple[Path, Path]:
    """A registered track with three predictions: two ruled, one manual."""
    repo, study = ready_study_v3
    (study / "train.py").write_text(CELL_SOURCE, encoding="utf-8")

    def _register(contract: dict) -> None:
        contract["tracks"]["primary"]["mode"] = "registered"
        contract["entrypoint"]["command"] = ["python", "-u", "train.py"]
        contract["predictions"] = [dict(entry) for entry in PREDICTIONS]

    amend(study, _register, note="three registered predictions")
    commit_all(repo, "a registered lane with a ledger")
    return repo, study


def test_tests_writes_the_verdict_to_manifest_state_and_events(ledger_study) -> None:
    _, study = ledger_study
    edit_cell(study, "adjudicating")
    manifest = run_one(study, command=metric_command(0.7), tests="P1", echo=False)

    assert manifest["disposition"] == "measured"
    assert manifest["predictions"] == {
        "P1": {"verdict": "supported", "explanation": "primary_metric 0.7 > 0.6 → supported"}
    }
    on_disk = json.loads((study / "runs" / "E0001" / "manifest.json").read_text(encoding="utf-8"))
    assert on_disk["predictions"]["P1"]["verdict"] == "supported"

    contract = load_contract(study)
    entry = load_state(study, contract)["predictions"]["P1"]
    assert entry["verdict"] == "supported"
    assert entry["source"] == "run"
    assert entry["evidence"] == ["E0001"]
    assert len(entry["history"]) == 1

    adjudications = [e for e in read_events(study) if e["type"] == "prediction_adjudicated"]
    assert [(e["prediction"], e["verdict"], e["source"]) for e in adjudications] == [
        ("P1", "supported", "run")
    ]


def test_a_rule_whose_key_the_cell_did_not_print_is_recorded_inconclusive(
    ledger_study,
) -> None:
    _, study = ledger_study
    edit_cell(study, "no-spread")
    manifest = run_one(study, command=metric_command(0.7), tests="P2", echo=False)
    assert manifest["predictions"]["P2"]["verdict"] == "inconclusive"
    assert "was not printed" in manifest["predictions"]["P2"]["explanation"]


def test_the_history_is_append_only_across_reruns(ledger_study) -> None:
    """A belief that changed says so, with BOTH records intact."""
    _, study = ledger_study
    edit_cell(study, "high")
    run_one(study, command=metric_command(0.7), tests="P1", echo=False)
    edit_cell(study, "low")
    run_one(study, command=metric_command(0.4), tests="P1", echo=False)

    entry = load_state(study, load_contract(study))["predictions"]["P1"]
    assert entry["verdict"] == "refuted"
    assert [record["verdict"] for record in entry["history"]] == ["supported", "refuted"]
    assert [record["evidence"] for record in entry["history"]] == [["E0001"], ["E0002"]]


def test_tests_is_validated_before_the_lock_so_a_typo_costs_nothing(ledger_study) -> None:
    _, study = ledger_study
    edit_cell(study, "typo")
    with pytest.raises(WorkflowError, match="unknown prediction 'P9'"):
        run_one(study, command=metric_command(0.7), tests="P9", echo=False)
    # No id allocated, no run dir, no candidate commit — the refusal burns nothing.
    assert list((study / "runs").glob("E*/manifest.json")) == []


def test_tests_refuses_a_manual_prediction(ledger_study) -> None:
    _, study = ledger_study
    edit_cell(study, "manual")
    with pytest.raises(WorkflowError, match="has no rule"):
        run_one(study, command=metric_command(0.7), tests="P3", echo=False)


def test_tests_refuses_a_schema_2_study(ready_study) -> None:
    _, study = ready_study
    (study / "train.py").write_text(
        (study / "train.py").read_text(encoding="utf-8") + "\nX = 1\n", encoding="utf-8"
    )
    with pytest.raises(WorkflowError, match="schema-3 contract key"):
        run_one(study, tests="P1", echo=False)


# ---------------------------------------------------------------------------
# 4. hand adjudication, with the evidence pinned
# ---------------------------------------------------------------------------


def test_manual_adjudication_pins_a_path_by_sha256(ledger_study, capsys) -> None:
    repo, study = ledger_study
    sidecar = study / "sweeps" / "rq0_headroom.tsv"
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text("cell\theadroom\nA\t0.4\n", encoding="utf-8")
    commit_all(repo, "a sidecar the notary cannot read")

    rc = cli.main(
        [
            "predict", "adjudicate", "P3",
            "--study", str(study),
            "--verdict", "refuted",
            "--evidence", "sweeps/rq0_headroom.tsv,E0001",
            "--note", "the table shows no cell with permission",
            "--acknowledged-by", "referee",
        ]
    )
    assert rc == 0
    assert "P3: refuted" in capsys.readouterr().out

    entry = load_state(study, load_contract(study))["predictions"]["P3"]
    assert entry["verdict"] == "refuted"
    assert entry["source"] == "manual"
    assert entry["evidence"] == ["sweeps/rq0_headroom.tsv", "E0001"]
    assert len(entry["artifacts"]["sweeps/rq0_headroom.tsv"]["sha256"]) == 64
    assert entry["acknowledged_by"] == "referee"
    # …and it self-committed, so the loop never dead-ends on its own receipt.
    assert subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True
    ).stdout.strip() == ""


def test_a_machine_ruled_prediction_needs_force(ledger_study, capsys) -> None:
    """A rule the notary can decide is never closed by hand by accident."""
    _, study = ledger_study
    base = ["predict", "adjudicate", "P1", "--study", str(study), "--verdict", "supported",
            "--evidence", "E0001", "--acknowledged-by", "me"]
    assert cli.main(base) == 2
    assert "carries an arithmetic rule" in capsys.readouterr().err

    assert cli.main([*base, "--force"]) == 2
    assert "--force requires --reason" in capsys.readouterr().err
    assert "P1" not in load_state(study, load_contract(study)).get("predictions", {})


def test_force_records_the_reason_on_the_ledger(ledger_study) -> None:
    _, study = ledger_study
    rc = cli.main(
        ["predict", "adjudicate", "P1", "--study", str(study), "--verdict", "inconclusive",
         "--evidence", "E0001", "--acknowledged-by", "me", "--force",
         "--reason", "the printed key was renamed mid-study"]
    )
    assert rc == 0
    entry = load_state(study, load_contract(study))["predictions"]["P1"]
    assert entry["reason"] == "the printed key was renamed mid-study"


def test_evidence_that_is_neither_an_id_nor_a_file_is_refused(ledger_study, capsys) -> None:
    _, study = ledger_study
    rc = cli.main(
        ["predict", "adjudicate", "P3", "--study", str(study), "--verdict", "supported",
         "--evidence", "trust me", "--acknowledged-by", "me"]
    )
    assert rc == 2
    assert "neither an evidence id" in capsys.readouterr().err


def test_predict_list_prints_the_four_numbers_and_json(ledger_study, capsys) -> None:
    _, study = ledger_study
    edit_cell(study, "listing")
    run_one(study, command=metric_command(0.7), tests="P1", echo=False)

    assert cli.main(["predict", "list", "--study", str(study)]) == 0
    out = capsys.readouterr().out
    assert "summary: 1 supported, 0 refuted, 0 inconclusive, 2 open" in out
    assert "primary_metric 0.7 > 0.6 → supported" in out

    assert cli.main(["predict", "list", "--study", str(study), "--open"]) == 0
    open_out = capsys.readouterr().out
    assert "P2" in open_out and "P3" in open_out and "P1 " not in open_out

    assert cli.main(["predict", "list", "--study", str(study), "--json"]) == 0
    rows = json.loads(capsys.readouterr().out)
    assert [row["id"] for row in rows] == ["P1", "P2", "P3"]
    assert rows[0]["rule"] == "primary_metric > 0.6"
    assert rows[2]["manual"] is True


def test_status_reports_the_prediction_counts(ledger_study) -> None:
    _, study = ledger_study
    assert "predictions: 0 supported, 0 refuted, 0 inconclusive, 3 open" in status_summary(study)


# ---------------------------------------------------------------------------
# 5. finalize will not close over an open or unreported prediction
# ---------------------------------------------------------------------------


FINDINGS = """\
# Findings

The study is exploratory.

## ② Registered predictions (from the ledger)

| P# | Statement | Rule | Observed | Verdict (ledger) | Evidence | Decision |
|---|---|---|---|---|---|---|
{rows}
"""

ROW = "| {pid} | … | … | … | {verdict} | E0001 | program.md 2026-09-03 |"


def _write_findings(study: Path, ids: list[str]) -> None:
    (study / "findings.md").write_text(
        FINDINGS.format(rows="\n".join(ROW.format(pid=pid, verdict="supported") for pid in ids)),
        encoding="utf-8",
    )


def test_finalize_refuses_while_a_prediction_is_open(ledger_study) -> None:
    _, study = ledger_study
    _write_findings(study, ["P1", "P2", "P3"])
    with pytest.raises(WorkflowError, match="cannot finalize with open predictions: P1, P2, P3"):
        finalize(study, allow_exploratory=True)


def test_allow_open_predictions_needs_a_reason_and_records_it(ledger_study) -> None:
    _, study = ledger_study
    _write_findings(study, ["P1", "P2", "P3"])
    with pytest.raises(WorkflowError, match="--allow-open-predictions requires --reason"):
        finalize(study, allow_exploratory=True, allow_open_predictions=True)

    label = finalize(
        study,
        allow_exploratory=True,
        allow_open_predictions=True,
        open_predictions_reason="the wet-lab wave has not returned",
        # Gate 3 is E6b's business; this test is about the ledger.
        no_referee=True,
        referee_reason="the wet-lab wave has not returned",
    )
    assert label == "exploratory"
    finalization = load_state(study, load_contract(study))["finalization"]
    assert finalization["open_predictions"] == {
        "ids": ["P1", "P2", "P3"],
        "reason": "the wet-lab wave has not returned",
    }


def test_finalize_refuses_findings_that_do_not_report_every_prediction(ledger_study) -> None:
    _, study = ledger_study
    _write_findings(study, ["P1"])
    with pytest.raises(WorkflowError, match=r"§② does not report P2, P3"):
        finalize(
            study,
            allow_exploratory=True,
            allow_open_predictions=True,
            open_predictions_reason="still open",
        )


def test_finalize_refuses_findings_with_no_section_two(ledger_study) -> None:
    _, study = ledger_study
    (study / "findings.md").write_text("# Findings\n\nexploratory.\n", encoding="utf-8")
    with pytest.raises(WorkflowError, match="no `## ② Registered predictions` section"):
        finalize(
            study,
            allow_exploratory=True,
            allow_open_predictions=True,
            open_predictions_reason="still open",
        )


def test_a_schema_2_finalize_is_untouched_by_the_ledger(ready_study) -> None:
    _, study = ready_study
    (study / "findings.md").write_text(
        "# Findings\n\nThis study is exploratory.\n", encoding="utf-8"
    )
    assert finalize(study, allow_exploratory=True) == "exploratory"


# --- findings §② parsing ----------------------------------------------------


def test_section_two_ids_come_from_table_rows_not_prose() -> None:
    text = (
        "## ① Verdicts\n\n| C1 | P9 mentioned in prose |\n\n"
        "## ② Registered predictions (from the ledger)\n\n"
        "P4 is discussed here but not tabled.\n"
        "| P1 | … | supported |\n| P2 | … | refuted |\n\n"
        "## ③ Surprises\n\n| P8 | later section |\n"
    )
    assert findings_prediction_ids(text) == {"P1", "P2"}


def test_the_ledger_lists_the_contract_register_in_order(ledger_study) -> None:
    _, study = ledger_study
    contract = load_contract(study)
    rows = ledger(contract, load_state(study, contract))
    assert [row["id"] for row in rows] == ["P1", "P2", "P3"]
    assert counts(rows)["open"] == 3
    assert open_predictions(contract, load_state(study, contract)) == ["P1", "P2", "P3"]


def test_a_verdict_outside_the_three_is_refused(ledger_study) -> None:
    from kleinlib.predictions import record_verdict

    _, study = ledger_study
    with pytest.raises(WorkflowError, match="there is no 'open' verdict"):
        record_verdict(
            study, {}, "P1", verdict="open", explanation="", source="manual"
        )


def test_yaml_round_trips_the_register(ledger_study) -> None:
    """The register in study.yaml is what the ledger reads — no second source."""
    _, study = ledger_study
    contract = yaml.safe_load((study / "study.yaml").read_text(encoding="utf-8"))
    assert [entry["id"] for entry in contract["predictions"]] == ["P1", "P2", "P3"]
