"""The JSON Schemas a host validates Klein's output against (``kleinlib/_schemas``).

Every schema is checked as a schema, and then against REAL output: each structured verb
runs through ``kleinlib.cli.main([..., "--json"])`` and/or ``kleinlib.api`` on a study the
existing fixtures build and, read-only, on shipped exhibits; the whole envelope is
validated against ``envelope.schema.json`` and its ``data`` against the schema
``index.json`` names for that verb.
"""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
from argparse import _SubParsersAction
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError
from test_workflow_v3 import metric_command

from kleinlib import api, cli, next_step
from kleinlib.resources import load_schema, schema_index, schema_names
from kleinlib.schema import VALID_STATUSES

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = REPO_ROOT / "kleinlib" / "_schemas"
ID_BASE = "https://github.com/Xiang-Shan/klein-auto-research/schemas/v1/"
EXHIBITS = [
    REPO_ROOT / "studies" / "10-hubble-1929-replication",
    REPO_ROOT / "studies" / "00-known-truth-quickstart",
]


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def _git_status() -> str:
    return subprocess.run(
        ["git", "status", "--porcelain"], cwd=REPO_ROOT, text=True, capture_output=True, check=False
    ).stdout


def _json_main(argv: list[str]) -> tuple[int, dict]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = cli.main(argv if "--json" in argv else [*argv, "--json"])
    return code, json.loads(out.getvalue())  # exactly one JSON document, or this raises


def _validate(schema_name: str, instance: object) -> None:
    Draft202012Validator(load_schema(schema_name)).validate(instance)


def assert_conforms(env: dict, *, data_schema: str | None = None) -> str:
    """The envelope fits ``envelope``; its data fits the schema the index names for its verb."""
    _validate("envelope", env)
    index = schema_index()
    name = data_schema or index.get(env["verb"], index["*"])
    _validate(name, env["data"])
    return name


def _leaves(parser, path=()):
    children = [a for a in parser._actions if isinstance(a, _SubParsersAction)]
    if not children:
        yield " ".join(path)
        return
    for action in children:
        for name, child in action.choices.items():
            yield from _leaves(child, (*path, name))


def _edit_candidate(study: Path, marker: str) -> None:
    train = study / "train.py"
    train.write_text(train.read_text(encoding="utf-8") + f"\n{marker} = True\n", encoding="utf-8")


# --------------------------------------------------------------------------
# the files themselves
# --------------------------------------------------------------------------


def test_every_schema_file_is_a_valid_draft_2020_12_schema_with_a_stable_id() -> None:
    files = sorted(SCHEMA_DIR.glob("*.schema.json"))
    assert files, "kleinlib/_schemas holds no schemas"
    for path in files:
        schema = json.loads(path.read_text(encoding="utf-8"))
        name = path.name.removesuffix(".schema.json")
        Draft202012Validator.check_schema(schema)
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema", name
        assert schema["$id"] == f"{ID_BASE}{name}.schema.json", name
        assert schema["title"].strip() and schema["description"].strip(), name
    assert [p.name.removesuffix(".schema.json") for p in files] == schema_names()
    # nothing but the schemas and the index lives there
    assert {p.name for p in SCHEMA_DIR.iterdir() if p.is_file()} == {p.name for p in files} | {"index.json"}


def test_the_index_names_only_schemas_that_exist_and_has_a_default() -> None:
    index = json.loads((SCHEMA_DIR / "index.json").read_text(encoding="utf-8"))
    assert index["*"] == "text"
    assert set(index.values()) <= set(schema_names())
    assert {"envelope"}.isdisjoint(index.values())  # the wrapper is not a data schema
    # every verb the index names is a real command (or an API-only verb name)
    api_only = {"gate", "run-one --final-test --dry-run"}
    verbs = set(_leaves(cli.build_parser()))
    assert {key for key in index if key != "*"} <= verbs | api_only
    # every structured verb the task names resolves to a specific schema
    for verb in ("next", "status", "map", "predict list", "explain", "run-one", "finalize", "probe", "doctor"):
        assert index[verb] == verb.replace("predict list", "predictions")
    assert {index[v] for v in ("verify", "preflight", "claims verify")} == {"checks"}
    assert index["gate record"] == index["gate override"] == "gate"


def test_the_schemas_are_package_data() -> None:
    from kleinlib import resources

    assert resources._SCHEMAS.is_dir() and resources._SCHEMAS.parent.name == "kleinlib"


def test_the_closed_vocabularies_in_the_schemas_match_the_code() -> None:
    nxt = load_schema("next")["properties"]["next"]["properties"]["stage_id"]["enum"]
    assert nxt == list(next_step.STAGE_IDS)
    run_dispositions = load_schema("run-one")["properties"]["run"]["properties"]["disposition"]["enum"]
    assert set(run_dispositions) == set(VALID_STATUSES)
    check_levels = load_schema("checks")["properties"]["checks"]["items"]["properties"]["level"]["enum"]
    assert check_levels == ["ok", "warn", "fail"]
    levels = load_schema("envelope")["properties"]["problems"]["items"]["properties"]["level"]["enum"]
    assert levels == ["error", "warn"]
    from kleinlib.decision import VALID_VERDICTS

    verdicts = load_schema("predictions")["properties"]["predictions"]["items"]["properties"]["verdict"]["enum"]
    assert set(verdicts) == set(VALID_VERDICTS) | {"open"}


def test_the_schemas_reject_what_they_should() -> None:
    good = api.envelope("verify", {"checks": [], "summary": {"total": 0, "failed": 0, "warned": 0}})
    _validate("envelope", good)
    for broken in (
        {**good, "extra": 1},  # the wrapper is closed
        {**good, "format": 2},
        {**good, "ok": "yes"},
        {**good, "data": []},
        {**good, "problems": [{"level": "fatal", "code": "x", "message": "m"}]},
        {k: v for k, v in good.items() if k != "problems"},
    ):
        with pytest.raises(ValidationError):
            _validate("envelope", broken)
    # a data schema is open to new keys, strict about the ones a host depends on
    _validate("checks", {**good["data"], "added_later": 1})
    with pytest.raises(ValidationError):
        _validate("checks", {"summary": good["data"]["summary"]})
    with pytest.raises(ValidationError):
        _validate("checks", {"checks": [{"name": "n", "ok": True, "level": "meh", "message": ""}], "summary": good["data"]["summary"]})
    _validate("checks", {})  # a refused verb's empty data
    with pytest.raises(ValidationError):
        _validate("text", {"text": 3})


# --------------------------------------------------------------------------
# real output: shipped exhibits, read-only
# --------------------------------------------------------------------------


@pytest.mark.parametrize("exhibit", EXHIBITS, ids=lambda p: p.name)
@pytest.mark.parametrize(
    ("argv", "verb", "schema_name"),
    [
        (["next"], "next", "next"),
        (["status"], "status", "status"),
        (["map"], "map", "map"),
        (["verify", "--no-receipt"], "verify", "checks"),
        (["claims", "verify"], "claims verify", "checks"),
        (["predict", "list"], "predict list", "predictions"),
        (["preflight", "--allow-dirty"], "preflight", "checks"),
    ],
    ids=lambda v: v if isinstance(v, str) else None,
)
def test_exhibit_output_conforms_and_nothing_is_written(exhibit, argv, verb, schema_name) -> None:
    before = _git_status()
    code, env = _json_main([*argv, "--study", str(exhibit)])
    assert env["verb"] == verb
    assert assert_conforms(env) == schema_name
    assert env["data"], "a read of a real study returns data"
    if verb == "preflight":  # an exhibit is not on its experiments branch: a failing check list is still data
        assert env["ok"] is (env["data"]["summary"]["failed"] == 0) and (code == 0) is env["ok"]
    else:
        assert code == 0 and env["ok"] is True
    assert _git_status() == before


@pytest.mark.parametrize("exhibit", EXHIBITS, ids=lambda p: p.name)
def test_the_api_functions_conform_on_exhibits(exhibit) -> None:
    before = _git_status()
    for env in (
        api.next_action(exhibit),
        api.status(exhibit),
        api.study_map(exhibit),
        api.verify(exhibit, receipt=False),
        api.claims_verify(exhibit),
        api.predictions(exhibit),
        api.preflight(exhibit, allow_dirty=True),
    ):
        assert_conforms(env)
        assert env["data"]
    assert _git_status() == before


def test_a_finalized_exhibit_reports_a_closed_study() -> None:
    env = api.status(EXHIBITS[0])
    assert_conforms(env)
    assert env["data"]["finalization"]["label"] in {"confirmed", "exploratory"}
    assert env["data"]["next"]["stage_id"] == "closed"
    graph = api.study_map(EXHIBITS[0])
    assert_conforms(graph)
    assert {node["type"] for node in graph["data"]["nodes"]} >= {"question", "run", "prediction", "claim", "decision"}


def test_explain_and_doctor_conform() -> None:
    for argv in (["explain", "gate"], ["explain", "consult"], ["explain"]):
        code, env = _json_main(argv)
        assert code == 0 and env["verb"] == "explain"
        assert assert_conforms(env) == "explain"
    kinds = {_json_main(["explain", t])[1]["data"]["kind"] for t in ("gate", "consult", "")}
    assert kinds == {"term", "protocol", "index"}
    code, env = _json_main(["doctor"])
    assert code == 0 and assert_conforms(env) == "doctor"
    # data.ok can be false while the envelope's ok is true: doctor is a report, not a gate
    assert env["ok"] is True and isinstance(env["data"]["ok"], bool)
    assert assert_conforms(api.explain("claims")) == "explain"


# --------------------------------------------------------------------------
# real output: a fixture study, through every writing verb
# --------------------------------------------------------------------------


def test_a_fresh_study_conforms(ready_study) -> None:
    _repo, study = ready_study
    for argv, name in (
        (["next"], "next"),
        (["status"], "status"),
        (["map"], "map"),
        (["preflight", "--allow-dirty"], "checks"),
        (["verify", "--no-receipt"], "checks"),
        (["predict", "list"], "predictions"),
    ):
        _code, env = _json_main([*argv, "--study", str(study)])
        assert assert_conforms(env) == name, argv
    env = api.status(study)
    assert_conforms(env)
    assert env["data"]["experiments"]["total"] == 0 and env["data"]["tracks"]["primary"]["incumbent"] is None
    assert env["data"]["finalization"] is None
    _code, env = _json_main(["map", "--study", str(study)])
    assert [item["kind"] for item in env["data"]["open"]] == ["question-unanswered"]


def test_a_development_run_conforms_and_so_does_a_crash(ready_study) -> None:
    _repo, study = ready_study
    _edit_candidate(study, "CANDIDATE_ONE")
    code, env = _json_main(
        ["run-one", "--json", "--study", str(study), "--description", "first", "--command", *metric_command(0.7)]
    )
    assert code == 0 and env["ok"] and assert_conforms(env) == "run-one"
    assert env["data"]["run"]["experiment"] == "E0001" and env["data"]["run"]["disposition"] == "keep"
    assert [p["code"] for p in env["problems"]] == ["notice"]  # the engine's note, kept as a warn problem

    _edit_candidate(study, "CANDIDATE_TWO")
    code, env = _json_main(
        [
            "run-one", "--json", "--study", str(study), "--description", "boom",
            "--command", sys.executable, "-c", "import sys; sys.exit(1)",
        ]
    )
    assert code == 1 and env["ok"] is False and assert_conforms(env) == "run-one"
    assert env["data"]["run"]["disposition"] == "crash" and env["data"]["run"]["primary_metric"] is None
    assert env["problems"] == []  # a crash is evidence, not a refusal

    status = api.status(study)
    assert assert_conforms(status) == "status"
    assert status["data"]["experiments"] == {"total": 2, "keep": 1, "discard": 0, "measured": 0, "crash": 1}
    assert status["data"]["tracks"]["primary"]["incumbent"]["experiment"] == "E0001"
    assert assert_conforms(api.predictions(study)) == "predictions"
    assert assert_conforms(api.study_map(study)) == "map"


def test_run_one_through_the_api_conforms(ready_study) -> None:
    _repo, study = ready_study
    _edit_candidate(study, "VIA_API")
    # the API runs the contract's own entrypoint, which a fresh scaffold has not implemented:
    # the notary records the crash, and that is a run summary too
    env = api.run_one(study, description="scaffold entrypoint")
    assert assert_conforms(env) == "run-one"
    assert env["data"]["run"]["disposition"] == "crash"


def test_a_refused_run_is_an_envelope_with_empty_data(ready_study) -> None:
    _repo, study = ready_study  # nothing changed in the mutable surface
    code, env = _json_main(["run-one", "--study", str(study), "--description", "unchanged"])
    assert code == 2 and env["ok"] is False and env["data"] == {}
    assert [p["code"] for p in env["problems"]] == ["refused"]
    assert assert_conforms(env) == "run-one"
    assert assert_conforms(api.run_one(study, description="unchanged")) == "run-one"


def test_refusals_conform_whichever_seam_they_come_from(tmp_path: Path) -> None:
    code, env = _json_main(["status", "--study", str(tmp_path / "missing")])
    assert code == 2 and env["ok"] is False and env["data"] == {}
    assert assert_conforms(env) == "status"
    for env in (api.status(tmp_path / "x"), api.verify(tmp_path / "x"), api.claims_verify(tmp_path / "x"),
                api.predictions(tmp_path / "x"), api.study_map(tmp_path / "x"), api.explain("no such topic")):
        assert env["ok"] is False
        assert_conforms(env)
    code, env = _json_main(["explain", "zzzz"])
    assert code == 2 and assert_conforms(env) == "explain" and env["problems"][0]["code"] == "refused"


def test_a_failed_check_list_is_data_not_a_refusal(ready_study) -> None:
    _repo, study = ready_study
    env = api.claims_verify(study)  # no claims.lock yet: refused
    assert env["ok"] is False and env["data"] == {} and assert_conforms(env) == "checks"
    env = api.preflight(study.parent)  # the studies/ folder is not a study: the contract check fails
    assert assert_conforms(env) == "checks"
    assert env["ok"] is False and env["data"]["summary"]["failed"] >= 1
    assert {p["code"] for p in env["problems"]} == {"check"} and all("name" in p for p in env["problems"])


def test_gate_conforms_through_both_seams(ready_study) -> None:
    _repo, study = ready_study
    env = api.gate(study, "consult", acknowledged_by="tester")
    assert assert_conforms(env) == "gate"
    assert env["data"]["status"] == "recorded" and env["data"]["gates"]["consult"] == "recorded"
    code, env = _json_main(["gate", "record", "data", "--study", str(study), "--acknowledged-by", "tester"])
    assert code == 0 and assert_conforms(env) == "gate"
    assert env["verb"] == "gate record" and env["data"] == {"gate": "data", "status": "recorded"}
    code, env = _json_main(
        ["gate", "override", "method", "--study", str(study), "--acknowledged-by", "tester", "--reason", "known"]
    )
    assert code == 0 and assert_conforms(env) == "gate" and env["data"]["status"] == "overridden"
    refused = api.gate(study, "consult", acknowledged_by="")
    assert refused["ok"] is False and assert_conforms(refused) == "gate"


def test_probe_conforms_and_so_does_the_list(ready_study) -> None:
    _repo, study = ready_study
    code, env = _json_main(["probe", "--json", "--study", str(study), "--", sys.executable, "-c", "print(1)"])
    assert code == 0 and assert_conforms(env) == "probe"
    first = env["data"]["probe"]
    assert first["id"] == "X0001" and first["previous_hash"] is None
    code, env = _json_main(["probe", "--json", "--study", str(study), "--", sys.executable, "-c", "raise SystemExit(3)"])
    assert code == 1 and env["ok"] is False and assert_conforms(env) == "probe"
    assert env["data"]["probe"]["exit_code"] == 3 and env["data"]["probe"]["previous_hash"] == first["hash"]
    code, env = _json_main(["probe", "--list", "--study", str(study)])
    assert code == 0 and assert_conforms(env) == "probe"
    assert [p["id"] for p in env["data"]["probes"]] == ["X0001", "X0002"] and env["data"]["problems"] == []
    assert assert_conforms(api.probe(study, [sys.executable, "-c", "print(2)"])) == "probe"
    assert_conforms(api.study_map(study))  # probes become nodes


def test_the_sealed_dry_run_conforms_through_both_seams(ready_study) -> None:
    _repo, study = ready_study
    code, env = _json_main(["run-one", "--study", str(study), "--final-test", "--dry-run"])
    # both seams return the same data: a host never reads prose to learn the outcome
    assert code != 0 and env["ok"] is False and env["verb"] == "run-one"
    assert assert_conforms(env) == "run-one"
    assert env["data"]["exit_code"] == code and env["data"]["passed"] is False
    env = api.sealed_dry_run(study)
    assert env["verb"] == "run-one --final-test --dry-run"
    assert assert_conforms(env) == "sealed-dry-run" and env["data"]["exit_code"] != 0 and env["ok"] is False
    assert env["data"]["passed"] is False


def test_finalize_conforms_refused_and_closed(ready_study) -> None:
    _repo, study = ready_study
    refused = api.finalize(study)
    assert refused["ok"] is False and refused["data"] == {} and assert_conforms(refused) == "finalize"
    (study / "findings.md").write_text("# Findings\n\nThis study is exploratory.\n", encoding="utf-8")
    env = api.finalize(study, allow_exploratory=True, no_referee=True, reason="a throwaway test study")
    assert env["ok"] is True and assert_conforms(env) == "finalize"
    assert env["data"] == {"label": "exploratory"}
    status = api.status(study)
    assert assert_conforms(status) == "status"
    assert status["data"]["status"] == "finalized" and status["data"]["finalization"]["label"] == "exploratory"
    assert status["data"]["next"]["stage_id"] == "tutorial"  # a closed study still owes its report
    assert_conforms(api.study_map(study))
    assert assert_conforms(api.verify(study)) == "checks"


def test_recover_and_skill_path_conform(ready_study) -> None:
    _repo, study = ready_study
    code, env = _json_main(["recover", "--study", str(study)])
    assert code == 0 and assert_conforms(env) == "recover" and env["data"] == {"recovered": []}
    code, env = _json_main(["skill", "path"])
    assert code == 0 and assert_conforms(env) == "skill-path"


def test_a_verb_without_structured_output_returns_the_text_schema(ready_study) -> None:
    _repo, study = ready_study
    code, env = _json_main(["generation", "status", "--study", str(study)])
    assert code == 0 and env["verb"] == "generation status"
    assert assert_conforms(env) == "text"
    assert set(env["data"]) == {"text"} and "not enabled" in env["data"]["text"]


# --------------------------------------------------------------------------
# klein schema
# --------------------------------------------------------------------------


def test_klein_schema_lists_the_schemas_and_the_verbs_that_use_them(capsys) -> None:
    assert cli.main(["schema"]) == 0
    listing = capsys.readouterr().out
    for name in schema_names():
        assert name in listing
    line = next(row for row in listing.splitlines() if row.startswith("checks"))
    assert "verify" in line and "preflight" in line and "claims verify" in line
    assert "every other verb" in next(row for row in listing.splitlines() if row.startswith("text"))


def test_klein_schema_name_prints_that_schema_as_json(capsys) -> None:
    assert cli.main(["schema", "envelope"]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed == load_schema("envelope")
    assert printed["$id"] == f"{ID_BASE}envelope.schema.json"


def test_klein_schema_json_is_the_envelope_of_the_api(capsys) -> None:
    code, env = _json_main(["schema"])
    assert code == 0 and env["verb"] == "schema" and env["ok"] is True
    assert assert_conforms(env) == "schema"
    assert env["data"]["schemas"] == schema_names() and env["data"]["verbs"] == schema_index()
    assert env["data"] == api.schema()["data"]
    code, env = _json_main(["schema", "checks"])
    assert code == 0 and assert_conforms(env) == "schema"
    assert env["data"] == {"name": "checks", "schema": load_schema("checks")}
    assert env["data"] == api.schema("checks")["data"]
    capsys.readouterr()


def test_an_unknown_schema_is_a_refusal(capsys) -> None:
    assert cli.main(["schema", "nope"]) == 2
    assert "no schema 'nope'" in capsys.readouterr().err
    code, env = _json_main(["schema", "nope"])
    assert code == 2 and env["ok"] is False and env["data"] == {}
    assert [p["code"] for p in env["problems"]] == ["refused"] and assert_conforms(env) == "schema"
    assert api.schema("nope")["ok"] is False
    with pytest.raises(Exception, match="no schema 'nope'"):
        load_schema("nope")
