"""Execute load-bearing Python examples shipped in the Klein protocols."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[5]


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


def test_sweep_runner_markdown_example_executes(tmp_path, monkeypatch):
    protocol = REPO_ROOT / ".claude/skills/klein/references/sweep-rules.md"
    source = _marked_python(protocol, "sweep-runner")
    monkeypatch.chdir(tmp_path)

    exec(compile(source, str(protocol), "exec"), {"__name__": "__main__"})

    sidecar = tmp_path / "sweeps/swaprate.sidecar.tsv"
    assert sidecar.is_file()
    assert len(sidecar.read_text(encoding="utf-8").splitlines()) == 4
