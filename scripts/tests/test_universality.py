"""Universality guard: normative text stays machine-agnostic.

Klein's evidence doctrine distinguishes two kinds of text:

- NORMATIVE text — the ``.md``/``.py`` files a reader or agent follows today.
  These must contain no machine-local strings: the repo must clone and run
  identically for anyone, anywhere.
- FROZEN EVIDENCE — the hash-chained study ledgers (``study_state.json``,
  ``events.jsonl``, ``runs/*/run.log``) and the ``docs/lineage/`` archives.
  Ledgers legitimately embed author-machine paths captured at execution time
  (rewriting them would break the append-only event chain and candidate-commit
  resolvability), and ``docs/lineage/README.md`` declares its archives'
  machine paths "historical, not normative". Neither is ever edited.

The guard therefore scans TRACKED ``*.md``/``*.py`` only (ledgers are
``.json``/``.jsonl``/``.log`` — out of scope by extension) and exempts
``docs/lineage/``. Deliberately allowed and out of pattern reach:
``$DATA_HUB`` / ``~/data_hub`` (the documented env seam — any user's hub),
the repo's own ``.claude/`` tree, and capitalized attribution (the GitHub
owner URLs, the CITATION author) — the username pattern below is lowercase
and matching is case-sensitive.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# Each entry: (case-sensitive regex, why it must not appear in normative text).
FORBIDDEN = [
    (re.compile(r"/Users/"), "absolute macOS home path"),
    (re.compile(r"/home/\w"), "absolute Linux home path"),
    (re.compile(r"xiang"), "author machine username (capitalized attribution is fine)"),
    (re.compile(r"my_venv"), "author-local virtualenv name"),
    (re.compile(r"llms_hub"), "author-local model-hub name"),
    (re.compile(r"~/Codex"), "author-local workspace path"),
    (re.compile(r"/private/tmp"), "machine-local temp path"),
    (re.compile(r"Auto_research"), "author workspace directory name"),
]

EXEMPT = (
    "docs/lineage/",  # verbatim historical archives — disclaimed in docs/lineage/README.md
    "scripts/tests/test_universality.py",  # this file names the strings it hunts
)


def test_normative_text_is_machine_agnostic() -> None:
    try:
        listing = subprocess.run(
            ["git", "ls-files"],
            cwd=REPO_ROOT,
            check=False,
            text=True,
            capture_output=True,
        )
    except OSError:
        pytest.skip("git unavailable — guard needs the tracked-file list")
    if listing.returncode != 0:
        pytest.skip("not a git checkout (e.g. an isolated verify_e2e copy omits .git)")

    files = [
        name
        for name in listing.stdout.splitlines()
        if name.endswith((".md", ".py")) and not name.startswith(EXEMPT)
    ]
    assert files, "git ls-files returned no normative files — scope filter is broken"

    hits: list[str] = []
    for name in files:
        for lineno, line in enumerate(
            (REPO_ROOT / name).read_text(encoding="utf-8").splitlines(), start=1
        ):
            for regex, reason in FORBIDDEN:
                if regex.search(line):
                    hits.append(f"{name}:{lineno}: {regex.pattern!r} — {reason}")
    assert not hits, "machine-local strings in normative text:\n" + "\n".join(hits)
