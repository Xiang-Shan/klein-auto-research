"""Execute the load-bearing Python examples shipped in the Klein protocols.

A protocol example is documentation FIRST — short, honest, and readable without
running it — but a code block nobody executes rots into a lie the moment an API
moves. Each `<!-- test:<name>:start/end -->` block below is compiled and run in a
temporary directory, so the protocols cannot drift from the engine they describe.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[5]
REFERENCES = REPO_ROOT / ".claude/skills/klein/references"


def _marked_python(path: Path, marker: str) -> str:
    text = path.read_text(encoding="utf-8")
    match = re.search(
        rf"<!-- test:{re.escape(marker)}:start -->\s*```python\n(.*?)\n```\s*"
        rf"<!-- test:{re.escape(marker)}:end -->",
        text,
        flags=re.DOTALL,
    )
    assert match is not None, f"missing executable {marker!r} block in {path}"
    return match.group(1)


def _run(protocol: str, marker: str, tmp_path: Path, monkeypatch) -> Path:
    """Compile and execute one marked block with the temp dir as its cwd."""
    path = REFERENCES / protocol
    source = _marked_python(path, marker)
    monkeypatch.chdir(tmp_path)
    exec(compile(source, str(path), "exec"), {"__name__": "__main__"})
    return path


def test_sweep_runner_markdown_example_executes(tmp_path, monkeypatch):
    _run("sweep-rules.md", "sweep-runner", tmp_path, monkeypatch)

    sidecar = tmp_path / "sweeps/swaprate.sidecar.tsv"
    assert sidecar.is_file()
    assert len(sidecar.read_text(encoding="utf-8").splitlines()) == 4


def test_prediction_rule_markdown_example_executes(tmp_path, monkeypatch):
    """consult-protocol.md: a rule is decided by arithmetic on the printed block."""
    _run("consult-protocol.md", "prediction-rule", tmp_path, monkeypatch)


def test_registered_block_markdown_example_executes(tmp_path, monkeypatch):
    """registered-mode.md: the cell block parses back into metrics and pinned paths."""
    _run("registered-mode.md", "registered-block", tmp_path, monkeypatch)
    assert (tmp_path / "cell.log").is_file()


def test_claims_verify_markdown_example_executes(tmp_path, monkeypatch):
    """claims-protocol.md: the smallest lock that passes the law, end to end."""
    _run("claims-protocol.md", "claims-verify", tmp_path, monkeypatch)
    assert (tmp_path / "studies/99-lock-demo/claims.lock").is_file()


def test_contract_split_markdown_example_executes(tmp_path, monkeypatch):
    """data-gate-protocol.md: the split comes from the contract, and is stable."""
    _run("data-gate-protocol.md", "contract-split", tmp_path, monkeypatch)


def test_referee_verdict_parse_markdown_example_executes(tmp_path, monkeypatch):
    """referee-protocol.md: the two machine-read lines, and the refused FAIL."""
    _run("referee-protocol.md", "referee-verdict-parse", tmp_path, monkeypatch)


def test_every_marked_block_in_the_protocols_has_a_test():
    """A marker with no test is a code block nobody runs — the thing this module
    exists to prevent."""
    covered = {
        "sweep-runner",
        "prediction-rule",
        "registered-block",
        "claims-verify",
        "contract-split",
        "referee-verdict-parse",
    }
    found = set()
    for path in sorted(REFERENCES.glob("*.md")):
        found |= set(re.findall(r"<!-- test:([a-z0-9-]+):start -->", path.read_text("utf-8")))
    assert found == covered, f"uncovered: {found - covered}; stale: {covered - found}"
