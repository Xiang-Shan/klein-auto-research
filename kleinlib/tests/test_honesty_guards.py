"""Guards added after the independent review of Klein 3.0.

Each test here pins a way a study could have claimed more than its record
supports, or a way a plug-in could have broken the kernel — found by review,
reproduced, then closed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from test_claims import locked_study  # noqa: F401  (fixture)
from test_workflow_v3 import git, metric_command

from kleinlib import api, cli, plugins
from kleinlib.checks import verify_study
from kleinlib.claims import init_lock, pin_artifact, verify_lock
from kleinlib.errors import WorkflowError
from kleinlib.probe import PROBE_ENV_KEYS, PROBES_FILE, probe_chain_problems, run_probe
from kleinlib.runner import run_logged
from kleinlib.study_map import write_html
from kleinlib.workflow import record_gate, run_one

PY = sys.executable
PRINT_ENV = [PY, "-c", "import os; print('PROBE=' + os.environ.get('KLEIN_PROBE', ''))"]


# --------------------------------------------------------------------------
# An exported KLEIN_PROBE never reaches a run, a rehearsal, or a gate
# --------------------------------------------------------------------------


def test_an_ambient_probe_variable_never_reaches_an_engine_child(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("KLEIN_PROBE", "1")
    monkeypatch.setenv("KLEIN_PROBE_DIR", str(tmp_path))
    log = tmp_path / "run.log"
    run_logged(PRINT_ENV, cwd=tmp_path, log_path=log, timeout_seconds=30, echo=False)
    assert "PROBE=\n" in log.read_text(encoding="utf-8")
    # ...while a probe, which sets it deliberately, still fences its own child
    run_logged(PRINT_ENV, cwd=tmp_path, log_path=log, timeout_seconds=30, echo=False,
               env_overrides={"KLEIN_PROBE": "1"})
    assert "PROBE=1" in log.read_text(encoding="utf-8")


def test_run_one_runs_its_child_without_the_probe_variable(ready_study, monkeypatch) -> None:
    _repo, study = ready_study
    monkeypatch.setenv("KLEIN_PROBE", "1")
    command = [
        PY, "-c",
        "import os; assert os.environ.get('KLEIN_PROBE', '') == '', 'the fence leaked into a run'; "
        "print('primary_metric:    0.7'); print('metric_name:       val_auc'); "
        "print('metric_goal:       higher')",
    ]
    manifest = run_one(study, command=command, description="a real run", echo=False)
    assert manifest["disposition"] != "crash", manifest.get("decision_reason")


def test_the_command_line_and_the_api_clear_the_probe_variable(ready_study, monkeypatch, capsys) -> None:
    _repo, study = ready_study
    import os

    for key in PROBE_ENV_KEYS:
        monkeypatch.setenv(key, "1")
    assert cli.main(["status", "--study", str(study)]) == 0
    assert not any(key in os.environ for key in PROBE_ENV_KEYS)
    capsys.readouterr()

    monkeypatch.setenv("KLEIN_PROBE", "1")
    seen: list[str] = []
    reply = api._guard("x", lambda: (seen.append(os.environ.get("KLEIN_PROBE", "")), api.envelope("x"))[1])
    assert reply["ok"] and seen == [""]
    assert os.environ["KLEIN_PROBE"] == "1"  # restored: the API changes nothing in its host


# --------------------------------------------------------------------------
# The probe ledger cannot be truncated, deleted or relabelled unnoticed
# --------------------------------------------------------------------------


def _probe_check(study: Path):
    return [c for c in verify_study(study, receipt=False) if c.name == "probe ledger"]


def test_a_truncated_probe_ledger_is_reported(ready_study) -> None:
    _repo, study = ready_study
    for note in ("one", "two", "three"):
        run_probe(study, [PY, "-c", f"print('{note}')"], note=note, echo=False)
    ledger = study / PROBES_FILE
    lines = ledger.read_text(encoding="utf-8").splitlines(keepends=True)
    ledger.write_text("".join(lines[:2]), encoding="utf-8")
    (study / "probes" / "X0003.log").unlink()
    problems = probe_chain_problems(study)
    assert any("missing from probes.jsonl (X0003)" in p for p in problems), problems
    check = _probe_check(study)
    assert len(check) == 1 and not check[0].ok


def test_a_deleted_probe_ledger_is_reported(ready_study) -> None:
    _repo, study = ready_study
    run_probe(study, [PY, "-c", "print('look')"], echo=False)
    (study / PROBES_FILE).unlink()
    (study / "probes" / "X0001.log").unlink()
    (study / "probes").rmdir()
    check = _probe_check(study)
    assert len(check) == 1 and not check[0].ok, "a study that probed cannot lose its ledger silently"
    assert "missing from probes.jsonl" in check[0].message


def test_an_orphan_probe_file_is_reported(ready_study) -> None:
    _repo, study = ready_study
    run_probe(study, [PY, "-c", "print('look')"], echo=False)
    (study / "probes" / "X0009.log").write_text("smuggled\n", encoding="utf-8")
    assert any("no ledger entry names: X0009.log" in p for p in probe_chain_problems(study))


def test_re_recording_consult_does_not_relabel_a_later_look(tmp_path: Path) -> None:
    from test_probe import ungated_study as build  # the fixture's function

    repo, study = build.__wrapped__(tmp_path)
    run_probe(study, [PY, "-c", "print('before')"], echo=False)
    first = record_gate(study, "consult", acknowledged_by="tester")["gates"]["consult"]["probes"]
    assert first["count"] == 1
    run_probe(study, [PY, "-c", "print('after the question was fixed')"], echo=False)
    again = record_gate(study, "consult", acknowledged_by="tester", note="re-recorded")
    assert again["gates"]["consult"]["probes"] == first, "the first consult record is the anchor"
    assert git(repo, "status", "--porcelain") == ""


def test_a_probe_that_rewrites_the_study_state_is_undone_and_said_on_the_record(ready_study) -> None:
    repo, study = ready_study
    before = (study / "study_state.json").read_bytes()
    record = run_probe(
        study,
        [PY, "-c", "open('study_state.json', 'w').write('{}'); print('tampered')"],
        echo=False,
    )
    assert (study / "study_state.json").read_bytes() == before
    assert record["restored_state"] == ["study_state.json"]
    assert git(repo, "status", "--porcelain") == ""
    changed = git(repo, "show", "--name-only", "--format=", "HEAD").split()
    assert not any(name.endswith("study_state.json") for name in changed)
    assert probe_chain_problems(study) == []


def test_a_probe_whose_command_does_not_exist_is_a_refusal_and_leaves_nothing(ready_study, capsys) -> None:
    repo, study = ready_study
    with pytest.raises(WorkflowError, match="could not start"):
        run_probe(study, ["no-such-command-anywhere-xyz"], echo=False)
    assert not (study / "probes").exists() and not (study / PROBES_FILE).exists()
    assert git(repo, "status", "--porcelain") == ""
    reply = api.probe(study, ["no-such-command-anywhere-xyz"])
    assert reply["ok"] is False and reply["problems"][0]["code"] == "refused"
    assert cli.main(["probe", "--study", str(study), "--json", "--", "no-such-command-anywhere-xyz"]) == 2
    assert json.loads(capsys.readouterr().out)["ok"] is False


def test_a_probe_is_never_the_root_commit(tmp_path: Path) -> None:
    from test_probe import ungated_study as build

    repo = tmp_path / "fresh"
    repo.mkdir()
    git(repo, "init", "-q")
    (tmp_path / "donor").mkdir()
    other, study = build.__wrapped__(tmp_path / "donor")
    import shutil

    shutil.copytree(other / "studies", repo / "studies")
    with pytest.raises(WorkflowError, match="no commit yet"):
        run_probe(repo / "studies" / study.name, [PY, "-c", "print(1)"], echo=False)


def test_a_probe_records_what_it_could_not_pin(ready_study, tmp_path: Path) -> None:
    _repo, study = ready_study
    inside = study / "look.py"
    inside.write_text("print('in')\n", encoding="utf-8")
    outside = tmp_path / "elsewhere.py"
    outside.write_text("print('out')\n", encoding="utf-8")
    record = run_probe(study, [PY, str(outside), "look.py"], echo=False, commit=False)
    assert list(record["files"]) == ["look.py"]
    assert record["unpinned"] == [str(outside)]


# --------------------------------------------------------------------------
# Nothing a probe produced can be claim evidence
# --------------------------------------------------------------------------


def test_a_probe_output_cannot_be_pinned_as_an_artifact(locked_study) -> None:  # noqa: F811
    _repo, study = locked_study
    run_probe(study, [PY, "-c", "print('auc 0.91')"], echo=False)
    for path in ("probes/X0001.log", PROBES_FILE):
        with pytest.raises(WorkflowError, match="a lead, never evidence"):
            pin_artifact(study, "look", path, commit=False)


# --------------------------------------------------------------------------
# The claims verbs refuse a study this engine does not judge
# --------------------------------------------------------------------------


def test_claims_verbs_refuse_a_schema_2_study(tmp_path: Path, capsys) -> None:
    study = tmp_path / "02-old"
    study.mkdir()
    (study / "study.yaml").write_text('schema_version: 2\nstudy_id: "02-old"\n', encoding="utf-8")
    (study / "findings.md").write_text("- **[C1]** A sentence.\n", encoding="utf-8")
    with pytest.raises(WorkflowError, match="tag v2.3.1"):
        init_lock(study, commit=False)
    assert not (study / "claims.lock").exists()
    (study / "claims.lock").write_text('{"lock_schema": 2, "claims": {}, "numbers": {}}', encoding="utf-8")
    with pytest.raises(WorkflowError, match="tag v2.3.1"):
        verify_lock(study)
    assert cli.main(["claims", "verify", "--study", str(study)]) == 2
    assert "tag v2.3.1" in capsys.readouterr().err
    assert api.claims_verify(study)["problems"][0]["code"] == "refused"


# --------------------------------------------------------------------------
# A plug-in cannot break or take over a core verb
# --------------------------------------------------------------------------


@pytest.fixture
def clean_plugins(monkeypatch):
    plugins.reset()
    monkeypatch.setattr(plugins, "BUILTIN", ())
    monkeypatch.setenv("KLEIN_NO_PLUGINS", "1")
    plugins.ensure_loaded()
    yield
    monkeypatch.undo()
    plugins.reset()


def _verbs(parser) -> dict:
    return [a for a in parser._subparsers._group_actions if a.dest == "command_name"][0].choices


def test_a_plug_in_that_claims_a_core_verb_is_refused_and_reported(clean_plugins, capsys) -> None:
    def greedy(sub) -> None:
        sub.add_parser("friendly").set_defaults(handler=lambda args: 0)
        sub.add_parser("run-one")  # argparse refuses the duplicate

    plugins.register_plugin("greedy", lambda plugin_api: plugin_api.add_cli(greedy))
    verbs = _verbs(cli.build_parser())
    assert "run-one" in verbs and "verify" in verbs
    assert "friendly" not in verbs, "everything a failed registrar added is removed"
    assert any("verbs" in name for name in plugins.load_errors())
    assert cli.main(["explain", "gate"]) == 0  # the kernel still works
    capsys.readouterr()


def test_a_plug_in_cannot_rebind_a_core_verbs_handler(clean_plugins, capsys) -> None:
    def hijack(sub) -> None:
        sub.choices["verify"].set_defaults(handler=lambda args: 0)

    plugins.register_plugin("hijack", lambda plugin_api: plugin_api.add_cli(hijack))
    verbs = _verbs(cli.build_parser())
    assert verbs["verify"].get_default("handler") is cli._cmd_verify  # the core verb's own handler is restored
    assert any("may not replace an existing verb: verify" in reason for reason in plugins.load_errors().values())


def test_a_receipt_names_third_party_plug_ins_and_only_those(clean_plugins) -> None:
    from kleinlib.checks import _third_party_plugins

    assert _third_party_plugins() == {}
    plugins.register_plugin("my_pack", lambda plugin_api: None)
    assert _third_party_plugins() == {"plugins": ["my_pack"]}


# --------------------------------------------------------------------------
# --json is one document, for every verb; the API never prints
# --------------------------------------------------------------------------


def test_json_mode_of_a_script_verb_is_one_envelope(capsys) -> None:
    assert cli.main(["summarize", "--help", "--json"]) == 0
    reply = json.loads(capsys.readouterr().out)
    assert reply["verb"] == "summarize" and reply["ok"] and "usage:" in reply["data"]["text"]


def test_the_mcp_server_has_no_json_mode(capsys) -> None:
    assert cli.main(["mcp", "--json"]) == 2
    assert "no --json mode" in capsys.readouterr().err


def test_the_api_returns_what_the_engine_printed_as_a_notice(capsys) -> None:
    def chatty():
        print("note: 1 uncommitted edit(s) left in the tree (study.yaml)")
        return api.envelope("x")

    reply = api._guard("x", chatty)
    assert capsys.readouterr().out == ""
    assert reply["problems"] == [
        {"level": "warn", "code": "notice", "message": "note: 1 uncommitted edit(s) left in the tree (study.yaml)"}
    ]


def test_the_api_offers_the_mandatory_sealed_rehearsal(ready_study, monkeypatch) -> None:
    _repo, study = ready_study
    seen: dict = {}

    def fake(study_dir, **kwargs):
        seen.update(kwargs, study=study_dir)
        return 0

    monkeypatch.setattr("kleinlib.workflow.sealed_dry_run", fake)
    reply = api.sealed_dry_run(study, track="primary")
    assert reply["ok"] and reply["data"] == {"exit_code": 0}
    assert seen["track"] == "primary" and seen["echo"] is False


# --------------------------------------------------------------------------
# Derived files never dirty a study
# --------------------------------------------------------------------------


def test_the_html_map_is_written_outside_the_study_by_default(ready_study, tmp_path, monkeypatch) -> None:
    repo, study = ready_study
    monkeypatch.chdir(tmp_path)
    target = write_html(study)
    assert target == tmp_path / "03-demo-map.html" and target.is_file()
    assert git(repo, "status", "--porcelain") == ""


def test_skill_install_writes_nothing_when_any_file_differs(tmp_path: Path) -> None:
    from kleinlib.resources import install_skill

    install_skill(tmp_path)
    marker = tmp_path / ".claude" / "skills" / "klein" / "SKILL.md"
    marker.write_text("edited\n", encoding="utf-8")
    victim = tmp_path / ".claude" / "skills" / "klein" / "references" / "glossary.md"
    victim.unlink()
    with pytest.raises(WorkflowError, match="nothing was written"):
        install_skill(tmp_path)
    assert not victim.exists(), "a refused install must not have copied anything"
    install_skill(tmp_path, force=True)
    assert victim.is_file() and marker.read_text(encoding="utf-8") != "edited\n"


def test_metric_command_helper_is_importable() -> None:
    assert metric_command(0.5)[0] == sys.executable
