"""Generate ``docs/cli.md`` — the one list of every ``klein`` verb.

The command line is the spec; this page is a rendering of it. Nothing else in the
repository restates the verb list (a hand-kept copy drifted more than once), and
``scripts/tests/test_cli_reference.py`` fails when this page is stale.

    uv run --locked python scripts/gen_cli_reference.py            # rewrite docs/cli.md
    uv run --locked python scripts/gen_cli_reference.py --check    # exit 1 if stale
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TARGET = REPO_ROOT / "docs" / "cli.md"

HEADER = """# `klein` — command reference

Generated from the command line itself by `scripts/gen_cli_reference.py`; do not edit.
Every verb accepts `--help` (the full text) and `--json` (one versioned envelope —
`docs/embedding.md`). Terms are defined in the glossary: `klein explain <term>`.

"""

GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Start", ("demo", "new", "doctor", "explain", "skill")),
    ("Look and plan", ("probe", "next", "status", "map")),
    ("Gates", ("gate", "promote", "headroom", "stop")),
    ("Run", ("preflight", "noise-floor", "run-one", "job", "recover", "sweep", "replicate")),
    ("Close", ("summarize", "predict", "claims", "refs", "report", "finalize", "verify")),
    ("Hosts", ("mcp", "notebook", "schema")),
    ("Plug-ins", ("generation",)),
)


def _subparsers(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    found: dict[str, argparse.ArgumentParser] = {}
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            found.update(action.choices)
    return found


def _help_of(parent: argparse.ArgumentParser, name: str) -> str:
    for action in parent._actions:
        if isinstance(action, argparse._SubParsersAction):
            for choice in action._choices_actions:
                if choice.dest == name:
                    return " ".join((choice.help or "").split())
    return ""


def _options(parser: argparse.ArgumentParser) -> str:
    flags = []
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction) or not action.option_strings:
            continue
        flag = action.option_strings[-1]
        if flag in {"--help", "--json"}:
            continue
        flags.append(f"`{flag}`")
    return " ".join(flags)


def _rows(parent: argparse.ArgumentParser, name: str, path: str) -> list[str]:
    parser = _subparsers(parent)[name]
    children = _subparsers(parser)
    summary = _help_of(parent, name) or " ".join((parser.description or "").split())
    rows = []
    if not children:
        rows.append(f"| `klein {path}` | {summary} | {_options(parser)} |")
    else:
        rows.append(f"| `klein {path} …` | {summary} | |")
        for child in children:
            rows.extend(_rows(parser, child, f"{path} {child}"))
    return rows


def render() -> str:
    # Only what ships with Klein: an installed third-party plug-in must not
    # change this page.
    os.environ["KLEIN_NO_PLUGINS"] = "1"
    from kleinlib import cli, plugins

    plugins.reset()
    root = cli.build_parser()
    verbs = _subparsers(root)
    grouped = {name for _title, names in GROUPS for name in names}
    missing = sorted(set(verbs) - grouped)
    out = [HEADER]
    for title, names in (*GROUPS, ("Other", tuple(missing))):
        present = [name for name in names if name in verbs]
        if not present:
            continue
        out.append(f"## {title}\n\n| Verb | What it does | Options |\n|---|---|---|\n")
        for name in present:
            out.append("\n".join(_rows(root, name, name)) + "\n")
        out.append("\n")
    return "".join(out).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    check = "--check" in (argv if argv is not None else sys.argv[1:])
    text = render()
    if check:
        if not TARGET.is_file() or TARGET.read_text(encoding="utf-8") != text:
            print("docs/cli.md is stale: run `uv run --locked python scripts/gen_cli_reference.py`", file=sys.stderr)
            return 1
        return 0
    TARGET.write_text(text, encoding="utf-8")
    print(f"wrote {TARGET.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
