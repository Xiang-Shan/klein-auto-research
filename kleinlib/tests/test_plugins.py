"""A new domain is data, not surgery: a plug-in adds a profile, a modality, a verb, an MCP tool.

``inquiry`` registrations are process-global and ``plugins.reset()`` does not
remove them, so every test here runs inside ``clean_plugins``, which restores
both registries on teardown.
"""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path

import pytest
import yaml
from test_workflow_v3 import _fill

from kleinlib import api, checks, cli, inquiry, plugins
from kleinlib.contract import validate_contract
from kleinlib.inquiry import ModalitySpec, ProfileSpec

SPECTRA = ("Source & shape", "Ranked go / no-go issues", "Go / no-go", "Calibration audit")
GENERATION_PLUGIN = "kleinlib.generation.plugin"


@pytest.fixture
def clean_plugins(monkeypatch):
    modalities, profiles = dict(inquiry._MODALITIES), dict(inquiry._PROFILES)
    monkeypatch.delenv("KLEIN_NO_PLUGINS", raising=False)
    plugins.reset()
    yield
    plugins.reset()
    inquiry._MODALITIES.clear()
    inquiry._MODALITIES.update(modalities)
    inquiry._PROFILES.clear()
    inquiry._PROFILES.update(profiles)


def _hello(args) -> int:
    api.emit({"greeting": "hello"})
    print("hello")
    return 0


def _climate_tool(root, arguments):
    return "stations: 3", {"stations": 3, "asked": dict(arguments)}


CLIMATE_TOOL = {
    "name": "climate_stations",
    "description": "count the stations of a study",
    "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
}


@pytest.fixture
def climate(clean_plugins, tmp_path):
    doc = tmp_path / "climate.md"
    doc.write_text("# Climate profile\n\nFor a station-network reader.\n", encoding="utf-8")

    def register(plugin_api: plugins.PluginAPI) -> None:
        plugin_api.add_profile(ProfileSpec("climate", doc=doc, card_sections=("Station audit",)))
        plugin_api.add_modality(ModalitySpec("spectra", card_sections=SPECTRA))
        plugin_api.add_cli(lambda sub: sub.add_parser("hello", help="say hello").set_defaults(handler=_hello))
        plugin_api.add_mcp_tool(CLIMATE_TOOL, _climate_tool)

    plugins.register_plugin("fake", register)
    return doc


def _new_climate_study(root: Path) -> Path:
    code = cli.main(
        [
            "new", "01-x", "--kind", "test", "--modality", "spectra", "--profile", "climate",
            "--metric", "val_auc", "--goal-direction", "higher", "--minimum-delta", "0.01",
            "--goal", "read the spectra", "--domain", "climate", "--target", "y", "--family", "linear",
            "--audience", "station operators", "--data", "csv:x.csv", "--prepared-path", "data/prepared/x.csv", "--root", str(root),
        ]
    )
    assert code == 0
    return root / "01-x"


def _json_main(argv: list[str]) -> tuple[int, dict]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = cli.main([*argv, "--json"])
    return code, json.loads(out.getvalue())


# --------------------------------------------------------------------------
# a plug-in that adds a domain
# --------------------------------------------------------------------------


def test_a_plugin_is_loaded_alongside_the_builtin_generation_layer(climate) -> None:
    assert "fake" in plugins.loaded_plugins()
    assert GENERATION_PLUGIN in plugins.loaded_plugins()
    assert plugins.load_errors() == {}


def test_the_new_axes_values_are_visible_to_the_registry(climate) -> None:
    assert "climate" in inquiry.profile_names() and "spectra" in inquiry.modality_names()
    assert inquiry.required_card_sections("spectra", "climate") == (*SPECTRA, "Station audit")


def test_klein_new_scaffolds_a_study_typed_with_the_new_domain(climate, tmp_path) -> None:
    study = _new_climate_study(tmp_path / "studies")
    contract = yaml.safe_load((study / "study.yaml").read_text(encoding="utf-8"))
    assert (contract["kind"], contract["profile"], contract["data"]["modality"]) == ("test", "climate", "spectra")
    assert contract["schema_version"] == 3


def test_a_filled_contract_with_the_new_domain_validates_and_resolves_its_profile_doc(
    climate, tmp_path
) -> None:
    study = _new_climate_study(tmp_path / "studies")
    _fill(study)
    contract = yaml.safe_load((study / "study.yaml").read_text(encoding="utf-8"))
    assert validate_contract(contract, study) == []
    assert checks._profile_path(study, contract) == climate


def test_the_core_still_refuses_a_domain_no_plugin_registered(clean_plugins, tmp_path) -> None:
    root = tmp_path / "studies"
    with pytest.raises(SystemExit) as exc:  # argparse choices are the registry, at build time
        cli.main(["new", "01-x", "--modality", "spectra", "--root", str(root)])
    assert exc.value.code == 2
    assert not (root / "01-x").exists()


def test_a_plugin_verb_runs_and_speaks_the_envelope(climate, capsys) -> None:
    assert cli.main(["hello"]) == 0
    assert capsys.readouterr().out.strip() == "hello"
    code, env = _json_main(["hello"])
    assert code == 0 and env["ok"] is True and env["verb"] == "hello"
    assert env["data"] == {"greeting": "hello"} and env["problems"] == []


def test_a_plugin_verb_that_returns_zero_without_output_still_gets_an_envelope(clean_plugins) -> None:
    plugins.register_plugin(
        "quiet",
        lambda a: a.add_cli(lambda sub: sub.add_parser("hello").set_defaults(handler=lambda args: 0)),
    )
    code, env = _json_main(["hello"])
    assert code == 0 and env["ok"] is True and env["data"] == {}


def test_a_plugin_mcp_tool_is_held_by_the_seam(climate) -> None:
    tools = plugins.mcp_tools()
    assert tools["climate_stations"] == (CLIMATE_TOOL, _climate_tool)
    assert tools["climate_stations"][1](Path("."), {"a": 1}) == ("stations: 3", {"stations": 3, "asked": {"a": 1}})


def test_the_mcp_server_serves_a_plugin_tool(climate, tmp_path) -> None:
    """Intended behaviour (plugins.py: 'a read-only MCP tool'): `tools/list` names it and `tools/call` runs it."""
    from kleinlib.mcp_server import KleinMCP

    server = KleinMCP(tmp_path)
    listed = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})["result"]["tools"]
    assert "climate_stations" in {tool["name"] for tool in listed}
    called = server.handle(
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "climate_stations", "arguments": {}}}
    )["result"]
    assert called["isError"] is False and called["structuredContent"]["stations"] == 3


def test_an_mcp_tool_needs_a_unique_name(clean_plugins) -> None:
    plugins.register_plugin("a", lambda api_: api_.add_mcp_tool(CLIMATE_TOOL, _climate_tool))
    plugins.register_plugin("b", lambda api_: api_.add_mcp_tool(CLIMATE_TOOL, _climate_tool))
    plugins.register_plugin("c", lambda api_: api_.add_mcp_tool({"description": "nameless"}, _climate_tool))
    errors = plugins.load_errors()
    assert set(errors) == {"b", "c"}
    assert "already registered" in errors["b"] and "needs a name" in errors["c"]
    assert list(plugins.mcp_tools()) == ["climate_stations"]


# --------------------------------------------------------------------------
# failure and opt-out
# --------------------------------------------------------------------------


def test_a_plugin_that_raises_is_recorded_and_core_verbs_still_parse(clean_plugins) -> None:
    def explode(plugin_api) -> None:
        raise RuntimeError("boom")

    plugins.register_plugin("broken", explode)
    assert plugins.load_errors() == {"broken": "RuntimeError: boom"}
    assert "broken" not in plugins.loaded_plugins()
    verbs = _verbs()
    assert {"run-one", "verify", "status", "next", "generation"} <= set(verbs)


def test_klein_no_plugins_loads_only_the_builtins(clean_plugins, monkeypatch) -> None:
    monkeypatch.setenv("KLEIN_NO_PLUGINS", "1")
    plugins.reset()
    assert plugins.loaded_plugins() == (GENERATION_PLUGIN,)
    assert plugins.load_errors() == {}


def test_without_the_builtin_the_generation_verbs_are_absent_but_the_kernel_is_not(
    clean_plugins, monkeypatch
) -> None:
    monkeypatch.setenv("KLEIN_NO_PLUGINS", "1")
    monkeypatch.setattr(plugins, "BUILTIN", ())
    plugins.reset()
    assert plugins.loaded_plugins() == ()
    verbs = _verbs()
    assert "generation" not in verbs
    assert {"run-one", "verify", "probe", "map"} <= set(verbs)


def test_reset_forgets_verbs_and_tools_but_not_registered_domains(climate) -> None:
    assert plugins.mcp_tools() and "fake" in plugins.loaded_plugins()
    plugins.reset()
    assert plugins._STATE.loaded is False
    assert "fake" not in plugins.loaded_plugins()  # re-loading finds only builtins and entry points
    assert "climate_stations" not in plugins.mcp_tools()
    assert "climate" in inquiry._PROFILES  # profiles stay registered: documented in plugins.reset


def _verbs() -> dict:
    parser = cli.build_parser()
    return [a for a in parser._subparsers._group_actions if a.dest == "command_name"][0].choices
