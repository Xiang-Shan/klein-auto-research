"""Shared fixtures for the klein skill scripts test suite.

Scripts under ``.claude/skills/klein/scripts/`` are deliberately not a
package (no ``__init__.py``) — the skill must remain usable by copying the
directory alone into a foreign repo — so tests load ``preflight.py`` and
``summarize_results.py`` directly via ``importlib.util`` rather than a normal
``import``.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

from _helpers import REPO_ROOT, SCRIPTS_DIR, run_git  # noqa: F401 — shared helpers live there, not here


def _load_module(name: str, filename: str) -> types.ModuleType:
    path = SCRIPTS_DIR / filename
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def preflight_module() -> types.ModuleType:
    return _load_module("klein_preflight", "preflight.py")


@pytest.fixture(scope="session")
def summarize_module() -> types.ModuleType:
    return _load_module("klein_summarize", "summarize_results.py")


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """A minimal, isolated git repo: one commit on ``main``, then switched to
    a non-protected ``experiments/demo`` branch with a clean working tree.

    This is the "everything should pass" baseline that individual preflight
    tests mutate one check at a time (dirty tree, back on main, bad header,
    ...).
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git(["init", "-q"], repo)
    # Force a known initial branch name regardless of the host's
    # init.defaultBranch config, then commit, then move to a scratch branch.
    run_git(["symbolic-ref", "HEAD", "refs/heads/main"], repo)
    run_git(["config", "user.email", "test@example.com"], repo)
    run_git(["config", "user.name", "Test"], repo)
    (repo / "README.md").write_text("placeholder\n", encoding="utf-8")
    run_git(["add", "README.md"], repo)
    commit = run_git(["commit", "-q", "-m", "init"], repo)
    assert commit.returncode == 0, commit.stderr
    switch = run_git(["checkout", "-q", "-b", "experiments/demo"], repo)
    assert switch.returncode == 0, switch.stderr
    return repo
