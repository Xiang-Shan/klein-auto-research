"""The stable Python surface (``kleinlib.api``) and its command-line twin (``--json``).

One envelope — ``{"klein","format","verb","ok","data","problems"}`` — for every
read, every write, and every refusal; a refusal is data, never a traceback.
"""

from __future__ import annotations

import ast
import contextlib
import io
import json
import subprocess
from pathlib import Path

import pytest

from kleinlib import __version__, api, cli, next_step
from kleinlib import workflow as workflow_module
from kleinlib.scaffold import scaffold_study

REPO_ROOT = Path(__file__).resolve().parents[2]
HUBBLE = REPO_ROOT / "studies" / "10-hubble-1929-replication"
ENVELOPE_KEYS = {"klein", "format", "verb", "ok", "data", "problems"}


def _studies_status() -> str:
    result = subprocess.run(
        ["git", "status", "--porcelain", "--", "studies"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return result.stdout


def _main(argv: list[str]) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = cli.main(argv)
    return code, out.getvalue()


def _json_main(argv: list[str]) -> tuple[int, dict]:
    code, text = _main([*argv, "--json"])
    return code, json.loads(text)  # exactly one JSON document, or this raises


# --------------------------------------------------------------------------
# The envelope itself
# --------------------------------------------------------------------------


def test_the_envelope_has_one_shape_and_a_format_version() -> None:
    assert api.FORMAT == 1
    env = api.envelope("verify", {"a": 1}, problems=[{"level": "warn", "code": "check"}])
    assert set(env) == ENVELOPE_KEYS
    assert (env["klein"], env["format"], env["verb"], env["ok"]) == (__version__, 1, "verify", True)
    assert env["data"] == {"a": 1}
    assert env["problems"] == [{"level": "warn", "code": "check"}]
    bare = api.envelope("x", ok=False)
    assert bare["data"] == {} and bare["problems"] == [] and bare["ok"] is False
    json.dumps(env)  # JSON-able


def test_a_refusal_is_one_error_problem_coded_refused() -> None:
    env = api.refusal("gate", ValueError("nope"), data={"gate": "consult"})
    assert env["ok"] is False and env["verb"] == "gate"
    assert env["data"] == {"gate": "consult"}
    assert env["problems"] == [{"level": "error", "code": "refused", "message": "nope"}]


def test_emit_is_a_no_op_outside_json_mode() -> None:
    assert api._SINK is None
    api.emit({"x": 1})  # must not raise nor leak
    assert api._SINK is None


# --------------------------------------------------------------------------
# Reads, on a shipped exhibit
# --------------------------------------------------------------------------


def test_next_action_names_the_one_next_action() -> None:
    env = api.next_action(HUBBLE)
    assert env["ok"] and env["verb"] == "next"
    assert {"study", "done", "notes", "schema", "next"} <= set(env["data"])
    assert env["data"]["schema"] == 3
    assert {"stage", "stage_id", "action", "command", "argv", "protocol", "why"} <= set(env["data"]["next"])


def test_status_carries_gates_tracks_predictions_and_the_next_action() -> None:
    env = api.status(HUBBLE)
    assert env["ok"] and env["verb"] == "status"
    for key in ("gates", "tracks", "predictions", "finalization", "next", "kind", "modality", "profile"):
        assert key in env["data"], key
    assert env["data"]["kind"] and env["data"]["modality"] and env["data"]["profile"]


def test_preflight_is_a_checks_envelope_whose_ok_follows_its_failures() -> None:
    env = api.preflight(HUBBLE, allow_dirty=True)
    assert env["verb"] == "preflight"
    summary = env["data"]["summary"]
    assert summary["total"] == len(env["data"]["checks"])
    assert env["ok"] is (summary["failed"] == 0)
    errors = [p for p in env["problems"] if p["level"] == "error"]
    assert len(errors) == summary["failed"]


def test_verify_without_a_receipt_is_clean_and_writes_nothing() -> None:
    before = _studies_status()
    env = api.verify(HUBBLE, receipt=False)
    assert env["ok"] and env["verb"] == "verify"
    assert env["data"]["summary"]["failed"] == 0
    assert env["data"]["summary"]["total"] == len(env["data"]["checks"]) > 0
    assert _studies_status() == before


def test_warnings_surface_as_warn_problems_with_the_check_name() -> None:
    env = api.verify(HUBBLE)
    warned = [row for row in env["data"]["checks"] if row["level"] == "warn"]
    assert warned and len(warned) == env["data"]["summary"]["warned"]
    problems = [p for p in env["problems"] if p["level"] == "warn"]
    assert [p["name"] for p in problems] == [row["name"] for row in warned]
    assert all(p["code"] == "check" and p["message"].startswith("[WARN]") for p in problems)


def test_claims_verify_runs_the_seven_check_law() -> None:
    env = api.claims_verify(HUBBLE)
    assert env["ok"] and env["verb"] == "claims verify"
    assert env["data"]["summary"] == {"total": 7, "failed": 0, "warned": 0}


def test_predictions_lists_the_ledger_with_counts() -> None:
    env = api.predictions(HUBBLE)
    assert env["ok"] and env["verb"] == "predict list"
    rows = env["data"]["predictions"]
    assert len(rows) == 10 and {row["id"] for row in rows} == {f"P{i}" for i in range(10)}
    assert env["data"]["counts"]


def test_study_map_envelope_holds_the_graph() -> None:
    env = api.study_map(HUBBLE)
    assert env["ok"] and env["verb"] == "map"
    for key in ("nodes", "edges", "open", "leads", "counts"):
        assert key in env["data"]


# --------------------------------------------------------------------------
# Refusals never raise
# --------------------------------------------------------------------------


def test_a_missing_study_is_a_refusal_not_a_traceback(tmp_path: Path) -> None:
    for call in (api.status, api.verify, api.claims_verify, api.predictions, api.study_map):
        env = call(tmp_path / "nowhere")
        assert env["ok"] is False
        assert [p["code"] for p in env["problems"]] == ["refused"], call.__name__
    # `next` on nothing is not a refusal: its answer is "scaffold the contract"
    env = api.next_action(tmp_path / "nowhere")
    assert env["ok"] and env["data"]["next"]["stage_id"] == "scaffold"
    # preflight reports the same absence as a failed check
    env = api.preflight(tmp_path / "nowhere")
    assert env["ok"] is False and env["problems"][0]["name"] == "study contract"


def test_a_gate_without_a_named_person_is_refused(ready_study) -> None:
    _repo, study = ready_study
    env = api.gate(study, "consult", acknowledged_by="")
    assert env["ok"] is False and env["verb"] == "gate"
    assert [p["code"] for p in env["problems"]] == ["refused"]
    assert "acknowledged-by" in env["problems"][0]["message"]


def test_a_gate_on_a_fresh_scaffold_refuses_its_unresolved_placeholders(tmp_path: Path) -> None:
    study = scaffold_study(
        tmp_path / "studies",
        "01-fresh",
        goal="g",
        domain="d",
        target="y",
        data_source="csv:x.csv",
        data_path="data/prepared/x.csv",
        schema_version=3,
        kind="predict",
        modality="tabular",
        profile="generic",
        audience="a",
    )
    env = api.gate(study, "consult", acknowledged_by="tester")
    assert env["ok"] is False
    assert [p["code"] for p in env["problems"]] == ["refused"]
    assert "placeholder" in env["problems"][0]["message"].lower()


# --------------------------------------------------------------------------
# Writes go through the notary
# --------------------------------------------------------------------------


def test_run_one_forwards_its_arguments_and_summarizes_the_manifest(ready_study, monkeypatch) -> None:
    _repo, study = ready_study
    seen: dict = {}

    def fake(study_dir, **kwargs):
        seen.update(kwargs, study=study_dir)
        return {
            "experiment": "E0001",
            "track": "primary",
            "disposition": "keep",
            "primary_metric": 0.7,
            "metric_name": "val_auc",
            "exit_code": 0,
            "description": "d",
            "not_a_summary_key": "dropped",
            "predictions": [{"id": "P1"}],
        }

    monkeypatch.setattr(workflow_module, "run_one", fake)
    env = api.run_one(study, description="d", track="primary", tests=["P1"], allow_rerun=True, timeout_seconds=3)
    assert env["ok"] and env["verb"] == "run-one"
    assert seen["study"] == study
    assert (seen["track"], seen["description"], seen["tests"]) == ("primary", "d", ["P1"])
    assert (seen["final_test"], seen["allow_rerun"], seen["timeout_seconds"], seen["echo"]) == (False, True, 3, False)
    run = env["data"]["run"]
    assert run["experiment"] == "E0001" and run["predictions"] == [{"id": "P1"}]
    assert "not_a_summary_key" not in run


def test_run_one_is_not_ok_when_the_run_crashed(ready_study, monkeypatch) -> None:
    _repo, study = ready_study
    monkeypatch.setattr(
        workflow_module,
        "run_one",
        lambda *a, **k: {"experiment": "E0002", "disposition": "crash", "exit_code": 1},
    )
    env = api.run_one(study, description="boom")
    assert env["ok"] is False and env["data"]["run"]["disposition"] == "crash"
    assert env["problems"] == []  # a crash is evidence, not a refusal


def test_run_one_turns_an_engine_refusal_into_an_envelope(ready_study) -> None:
    _repo, study = ready_study  # the mutable surface is unchanged: the notary refuses
    env = api.run_one(study, description="nothing changed")
    assert env["ok"] is False and env["problems"][0]["code"] == "refused"
    assert "unchanged" in env["problems"][0]["message"]


# --------------------------------------------------------------------------
# The command line: --json on every leaf
# --------------------------------------------------------------------------


def _leaves(parser, path=()):
    from argparse import _SubParsersAction

    children = [a for a in parser._actions if isinstance(a, _SubParsersAction)]
    if not children:
        yield path, parser
        return
    for action in children:
        for name, child in action.choices.items():
            yield from _leaves(child, (*path, name))


def test_every_leaf_verb_accepts_json_and_knows_its_name() -> None:
    leaves = list(_leaves(cli.build_parser()))
    assert len(leaves) > 30
    for path, parser in leaves:
        assert "--json" in parser._option_string_actions, path
        assert parser.get_default("_verb") == " ".join(path), path


@pytest.mark.parametrize(
    ("argv", "verb"),
    [
        (["next", "--study", str(HUBBLE)], "next"),
        (["status", "--study", str(HUBBLE)], "status"),
        (["verify", "--study", str(HUBBLE), "--no-receipt"], "verify"),
        (["claims", "verify", "--study", str(HUBBLE)], "claims verify"),
        (["map", "--study", str(HUBBLE)], "map"),
        (["doctor"], "doctor"),
    ],
)
def test_json_mode_prints_exactly_one_envelope(argv: list[str], verb: str) -> None:
    before = _studies_status()
    code, env = _json_main(argv)
    assert code == 0 and set(env) == ENVELOPE_KEYS
    assert env["verb"] == verb and env["ok"] is True and env["format"] == 1
    assert env["data"]
    assert _studies_status() == before


def test_a_refused_verb_in_json_mode_is_an_envelope_with_exit_code_two(tmp_path: Path) -> None:
    code, env = _json_main(["status", "--study", str(tmp_path / "missing")])
    assert code == 2 and env["ok"] is False and env["verb"] == "status"
    assert [p["code"] for p in env["problems"]] == ["refused"]
    assert "study directory not found" in env["problems"][0]["message"]


def test_text_mode_output_is_not_wrapped() -> None:
    code, text = _main(["next", "--study", str(HUBBLE)])
    assert code == 0
    with pytest.raises(ValueError):
        json.loads(text)
    assert text.strip()
    code2, text2 = _main(["next", "--study", str(HUBBLE)])
    assert (code2, text2) == (code, text)  # deterministic, and the wrapper left no state behind
    assert api._SINK is None


# --------------------------------------------------------------------------
# next_step vocabulary
# --------------------------------------------------------------------------


def _emitted_stage_labels() -> set[str]:
    tree = ast.parse((REPO_ROOT / "kleinlib" / "next_step.py").read_text(encoding="utf-8"))
    labels: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "_action":
            first = node.args[0]
            if isinstance(first, ast.Constant):
                labels.add(first.value)
            else:  # an f-string: its literal head is the stage
                assert isinstance(first, ast.JoinedStr)
                labels.add(first.values[0].value)
    return labels


def test_every_stage_label_next_step_can_emit_maps_into_the_closed_vocabulary() -> None:
    labels = _emitted_stage_labels()
    assert len(labels) >= 10
    for label in labels:
        assert next_step.stage_id(label) in next_step.STAGE_IDS, label
    # the head, not the detail, decides — and nothing real falls through to the default
    assert next_step.stage_id("EXPERIMENT · sealed") == "experiment"
    assert next_step.stage_id("CONSULT") == "consult"
    assert next_step.stage_id("closed") == "closed"
    assert next_step.stage_id("legacy") == "legacy"
    # and the vocabulary has no id the engine never emits
    assert {next_step.stage_id(label) for label in labels} == set(next_step.STAGE_IDS)


def test_command_argv_is_a_list_only_when_the_command_can_run_as_written() -> None:
    assert next_step.command_argv("klein verify --study studies/x") == ["klein", "verify", "--study", "studies/x"]
    assert next_step.command_argv("klein gate record data --acknowledged-by 'A B'") == [
        "klein", "gate", "record", "data", "--acknowledged-by", "A B",
    ]
    assert next_step.command_argv(None) is None and next_step.command_argv("") is None
    assert next_step.command_argv("klein new x --kind … --modality …") is None
    assert next_step.command_argv("klein run-one --description <what you changed>") is None
    assert next_step.command_argv("klein new x --recipe ...") is None
    # a continuation after "  #" is not part of the argv; an incomplete first part is not runnable
    assert next_step.command_argv("klein verify --study s  # then: klein finalize") == ["klein", "verify", "--study", "s"]
    assert next_step.command_argv("klein run-one --track <t>  # then: klein verify") is None
    assert next_step.command_argv("klein a && klein b") is None
    assert next_step.command_argv("klein 'unterminated") is None
