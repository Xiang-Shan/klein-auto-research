"""Host bridges (Klein 2.3): read-only MCP server, refs verify, notebook export, doctor --host."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from kleinlib.doctor import run_doctor
from kleinlib.errors import WorkflowError
from kleinlib.mcp_server import TOOLS, KleinMCP
from kleinlib.notebook import notebook_for_run, write_notebook
from kleinlib.refs_net import resolve_reference, title_match, verify_references

ROOT = Path(__file__).resolve().parents[2]
STUDY = "15-iris-90years-relaunch"


def _tree_state() -> str:
    return subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all", "studies"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout


# ------------------------------------------------------------------ MCP


def test_mcp_stdio_session_is_read_only() -> None:
    before = _tree_state()
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        *[
            {"jsonrpc": "2.0", "id": 10 + i, "method": "tools/call", "params": {"name": tool, "arguments": {"study": STUDY}}}
            for i, tool in enumerate(["next", "status", "preflight", "predictions", "claims_verify", "verify"])
        ],
        {"jsonrpc": "2.0", "id": 30, "method": "tools/call", "params": {"name": "explain", "arguments": {"topic": "referee"}}},
        {"jsonrpc": "2.0", "id": 31, "method": "tools/call", "params": {"name": "next", "arguments": {"study": "../.."}}},
        {"jsonrpc": "2.0", "id": 32, "method": "tools/call", "params": {"name": "gate", "arguments": {}}},
        {"jsonrpc": "2.0", "id": 33, "method": "resources/list"},
    ]
    stdin = "".join(json.dumps(m) + "\n" for m in messages) + "not json\n"
    out = subprocess.run(
        [sys.executable, "-m", "kleinlib.cli", "mcp", "--root", str(ROOT)],
        input=stdin, capture_output=True, text=True, timeout=600, check=True, cwd=ROOT,
    )
    replies = {r["id"]: r for r in map(json.loads, out.stdout.splitlines())}
    assert replies[1]["result"]["protocolVersion"] == "2025-06-18"
    assert {t["name"] for t in replies[2]["result"]["tools"]} == {t["name"] for t in TOOLS}
    assert all(t["annotations"]["readOnlyHint"] for t in replies[2]["result"]["tools"])
    for i in range(6):
        result = replies[10 + i]["result"]
        assert result["isError"] is False, result
        assert result["content"][0]["text"]
    assert replies[10]["result"]["structuredContent"]["study"] == STUDY
    assert "ten checks" in replies[30]["result"]["content"][0]["text"]
    assert replies[31]["result"]["isError"] is True  # no escape from --root
    assert replies[32]["result"]["isError"] is True  # no write tools exist
    assert replies[33]["error"]["code"] == -32601
    assert replies[None]["error"]["code"] == -32700
    assert _tree_state() == before


def test_mcp_has_no_write_tools() -> None:
    names = {t["name"] for t in TOOLS}
    assert not names & {"gate", "run_one", "run", "finalize", "claims", "record", "predict_adjudicate"}
    reply = KleinMCP(ROOT).handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "1999-01-01"}})
    assert reply["result"]["protocolVersion"] == "2025-11-25"


# ------------------------------------------------------------------ refs verify

CROSSREF = {"message": {"title": ["The Use of Multiple Measurements in <i>Taxonomic</i> Problems"],
                        "issued": {"date-parts": [[1936]]}}}
ARXIV = (
    b'<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><entry>'
    b"<id>http://arxiv.org/abs/2207.08815v1</id><title>Why do tree-based models still\n  outperform deep"
    b" learning on tabular data?</title><published>2022-07-18T00:00:00Z</published></entry></feed>"
)


def _fake_fetch(url: str) -> bytes:
    if "crossref" in url and "wrong" in url:
        return json.dumps({"message": {"title": ["Something else entirely about soil"], "issued": {"date-parts": [[2001]]}}}).encode()
    if "crossref" in url and "missing" in url:
        raise OSError("404")
    if "openalex" in url and "missing" in url:
        raise OSError("404")
    if "crossref" in url:
        return json.dumps(CROSSREF).encode()
    if "arxiv" in url:
        return ARXIV
    raise AssertionError(url)


REFS = """# a comment that must survive
references:
  fisher1936:
    title: "The use of multiple measurements in taxonomic problems"
    year: 1936
    doi: "10.1111/j.1469-1809.1936.tb02137.x"
    verified: true
    verified_by: >-
      a person who read
      the scan
  grinsztajn2022:
    # inline note
    title: "Why do tree-based models still outperform deep learning on tabular data?"
    arxiv: "2207.08815"
    verified: false
  wrong2001:
    title: "The use of multiple measurements in taxonomic problems"
    doi: "10.9999/wrong"
    verified: false
  urlonly:
    title: "A page"
    url: "https://example.org"
    verified: true
"""


def test_title_match_ignores_markup_and_case() -> None:
    assert title_match("The use of multiple measurements", "THE USE of <i>multiple</i> measurements.")
    assert title_match("Attention is all you need", "Attention Is All You Need")
    assert not title_match("Attention is all you need", "Deep residual learning for image recognition")


def test_resolution_flags_a_doi_pointing_elsewhere() -> None:
    bad = resolve_reference("w", {"title": "Iris", "doi": "10.9999/wrong"}, fetch=_fake_fetch)
    assert not bad.ok and "different title" in bad.message
    gone = resolve_reference("m", {"title": "Iris", "doi": "10.9/missing"}, fetch=_fake_fetch)
    assert not gone.ok


def test_record_keeps_comments_and_human_verification(tmp_path: Path) -> None:
    (tmp_path / "references.yaml").write_text(REFS, encoding="utf-8")
    results, recorded = verify_references(tmp_path, record=True, fetch=_fake_fetch, today="2026-11-03")
    by_key = {r.key: r for r in results}
    assert by_key["fisher1936"].ok and by_key["grinsztajn2022"].ok
    assert not by_key["wrong2001"].ok and by_key["urlonly"].ok
    assert recorded == ["fisher1936", "grinsztajn2022"]
    text = (tmp_path / "references.yaml").read_text(encoding="utf-8")
    assert "# a comment that must survive" in text and "# inline note" in text
    import yaml

    refs = yaml.safe_load(text)["references"]
    assert refs["fisher1936"]["verified_by"] == "a person who read the scan"  # human kept
    assert refs["fisher1936"]["resolved_by"] == "klein-refs (crossref)"
    assert refs["grinsztajn2022"]["verified"] is True
    assert refs["grinsztajn2022"]["verified_by"] == "klein-refs"
    assert refs["grinsztajn2022"]["verified_at"] == "2026-11-03"
    assert refs["wrong2001"]["verified"] is False and "resolved_by" not in refs["wrong2001"]


def test_refs_verify_refuses_offline(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "references.yaml").write_text(REFS, encoding="utf-8")
    monkeypatch.setenv("KLEIN_OFFLINE", "1")
    with pytest.raises(WorkflowError, match="KLEIN_OFFLINE"):
        verify_references(tmp_path)


def test_verify_never_imports_the_network_resolver() -> None:
    code = "import sys, kleinlib.cli, kleinlib.checks; print('kleinlib.refs_net' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True, cwd=ROOT)
    assert out.stdout.strip() == "False"


# ------------------------------------------------------------------ notebook


def test_notebook_holds_the_executed_source_and_is_deterministic(tmp_path: Path) -> None:
    study = ROOT / "studies" / STUDY
    manifest = json.loads((study / "runs" / "E0003" / "manifest.json").read_text())
    notebook = notebook_for_run(study, "E0003")
    assert notebook["nbformat"] == 4 and notebook["metadata"]["klein"]["derivative"] is True
    code = [c for c in notebook["cells"] if c["cell_type"] == "code"]
    executed = subprocess.run(
        ["git", "show", f"{manifest['candidate_commit']}:studies/{STUDY}/train.py"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout
    assert "".join(code[0]["source"]) == executed.rstrip("\n")
    assert all(c["outputs"] == [] for c in code)
    first = write_notebook(study, "E0003", tmp_path / "a.ipynb").read_bytes()
    second = write_notebook(study, "E0003", tmp_path / "b.ipynb").read_bytes()
    assert first == second


# ------------------------------------------------------------------ doctor --host


@pytest.mark.parametrize("host", ["claude-science", "claude-code", "generic"])
def test_doctor_host_probes_are_reported(host: str) -> None:
    report = run_doctor(host=host)
    names = [c["name"] for c in report["checks"]]
    assert "host" in names and "mcp server" in names and "gpu" in names
    if host == "claude-science":
        assert "uv environment" in names and "klein skill" in names


def test_doctor_flags_a_read_only_uv_override(tmp_path: Path, monkeypatch) -> None:
    locked = tmp_path / "ro"
    locked.mkdir()
    locked.chmod(0o500)
    try:
        monkeypatch.setenv("UV_PROJECT_ENVIRONMENT", str(locked))
        rows = {c["name"]: c for c in run_doctor(host="claude-science")["checks"]}
        import os

        if os.access(locked, os.W_OK):  # running as root: permissions are not enforced
            pytest.skip("root ignores directory permissions")
        assert rows["uv environment"]["ok"] is False
    finally:
        locked.chmod(0o700)
