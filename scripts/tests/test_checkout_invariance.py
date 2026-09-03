"""Checkout invariance guard.

Klein pins the sha256 of tracked text files into its evidence chain — claims
locks, results ledgers, the append-only event log, the schema module the
ledger columns derive from. A checkout that rewrites line endings (e.g.
Windows with ``core.autocrlf=true``) would silently corrupt every one of
those pinned hashes without touching a single byte of *content*.

``.gitattributes`` disables line-ending conversion repo-wide (``* -text``) as
the first rule precisely to prevent that class of failure. This module
asserts the rule is in force and spot-checks that a sample of pinned
artifacts is byte-identical between the git object store and the working
tree — i.e. that no conversion actually happened on this checkout.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GITATTRIBUTES = REPO_ROOT / ".gitattributes"

# A representative sample of the sha256-pinned artifacts a line-ending
# rewrite would corrupt: a claims lock, a results ledger, an append-only
# event log, and the single-sourced schema module the ledger columns derive
# from (kleinlib/schema.py — read-only reference here, never edited by this
# test).
PINNED_FILES = (
    "studies/09-iris-first-lesson/claims.lock",
    "studies/09-iris-first-lesson/results.tsv",
    "studies/09-iris-first-lesson/events.jsonl",
    "kleinlib/schema.py",
)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _require_git_checkout() -> None:
    """Skip when not run from inside a git checkout (e.g. a wheel install)."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=REPO_ROOT,
            check=False,
            text=True,
            capture_output=True,
        )
    except OSError:
        pytest.skip("git unavailable — checkout-invariance guard needs git")
    if result.returncode != 0 or result.stdout.strip() != "true":
        pytest.skip("not a git checkout (e.g. a wheel install) — nothing to verify")


def test_gitattributes_first_rule_disables_text_conversion() -> None:
    lines = GITATTRIBUTES.read_text(encoding="utf-8").splitlines()
    rules = [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]
    assert rules, ".gitattributes has no rules at all"
    assert rules[0] == "* -text", (
        "the first .gitattributes rule must be '* -text' so no checkout can "
        f"ever rewrite tracked bytes; found {rules[0]!r} instead"
    )


def test_pinned_files_are_byte_identical_between_worktree_and_git_object() -> None:
    _require_git_checkout()
    mismatches: list[str] = []
    for rel_path in PINNED_FILES:
        worktree_path = REPO_ROOT / rel_path
        assert worktree_path.is_file(), f"pinned fixture missing from worktree: {rel_path}"
        worktree_hash = _sha256_bytes(worktree_path.read_bytes())

        blob = subprocess.run(
            ["git", "cat-file", "blob", f"HEAD:{rel_path}"],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
        )
        assert blob.returncode == 0, (
            f"git cat-file blob HEAD:{rel_path} failed: {blob.stderr.decode(errors='replace')!r}"
        )
        committed_hash = _sha256_bytes(blob.stdout)

        if worktree_hash != committed_hash:
            mismatches.append(
                f"{rel_path}: worktree sha256={worktree_hash} != "
                f"HEAD blob sha256={committed_hash}"
            )
    assert not mismatches, "checkout rewrote tracked bytes:\n" + "\n".join(mismatches)


def test_no_tracked_file_reports_crlf_line_endings() -> None:
    _require_git_checkout()
    result = subprocess.run(
        ["git", "ls-files", "--eol"],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, f"git ls-files --eol failed: {result.stderr!r}"
    crlf_lines = [
        line
        for line in result.stdout.splitlines()
        if "w/crlf" in line or "i/crlf" in line
    ]
    assert not crlf_lines, "tracked files report crlf line endings:\n" + "\n".join(crlf_lines)
