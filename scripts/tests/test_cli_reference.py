"""docs/cli.md is generated from the command line; a stale page fails here."""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _generator():
    spec = importlib.util.spec_from_file_location(
        "gen_cli_reference", REPO_ROOT / "scripts" / "gen_cli_reference.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_cli_reference_page_is_current(monkeypatch) -> None:
    monkeypatch.setenv("KLEIN_NO_PLUGINS", "1")
    generator = _generator()
    from kleinlib import plugins

    try:
        expected = generator.render()
    finally:
        plugins.reset()
    assert (REPO_ROOT / "docs" / "cli.md").read_text(encoding="utf-8") == expected, (
        "docs/cli.md is stale: run `uv run --locked python scripts/gen_cli_reference.py`"
    )


def test_every_top_level_verb_is_grouped() -> None:
    generator = _generator()
    page = (REPO_ROOT / "docs" / "cli.md").read_text(encoding="utf-8")
    assert "## Other" not in page, "a new verb needs a home in gen_cli_reference.GROUPS"
    assert len({name for _title, names in generator.GROUPS for name in names}) == sum(
        len(names) for _title, names in generator.GROUPS
    )
