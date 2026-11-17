"""Throwaway repositories never call a signer (root ``conftest.py``, ``klein demo``).

The suite commits thousands of times. Under a global ``commit.gpgsign = true`` each
commit calls the signing program; on a managed machine that exhausted the signing
agent and failed 84 tests that had nothing wrong with them.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from kleinlib.demo import _init_repo
from kleinlib.transaction import git_commit, unsigned_git_environment


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, check=True)
    return result.stdout.strip()


def test_the_suite_commits_unsigned_even_when_the_repository_demands_signing(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    # A repository that insists on signing with a program that cannot exist: any
    # attempt to sign fails the commit. The suite's environment outranks the file.
    _git(repo, "config", "commit.gpgsign", "true")
    _git(repo, "config", "gpg.program", str(tmp_path / "no-such-signer"))
    (repo / "note.txt").write_text("evidence of nothing\n", encoding="utf-8")
    _git(repo, "add", "note.txt")
    head = git_commit(repo, "a throwaway commit")
    assert _git(repo, "rev-parse", "HEAD") == head
    assert "gpgsig" not in _git(repo, "cat-file", "commit", "HEAD")


def test_unsigned_environment_appends_after_existing_pairs() -> None:
    env = {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.autocrlf", "GIT_CONFIG_VALUE_0": "false"}
    unsigned_git_environment(env)
    assert env["GIT_CONFIG_COUNT"] == "3"
    assert env["GIT_CONFIG_KEY_0"] == "core.autocrlf"
    assert (env["GIT_CONFIG_KEY_1"], env["GIT_CONFIG_VALUE_1"]) == ("commit.gpgsign", "false")
    assert (env["GIT_CONFIG_KEY_2"], env["GIT_CONFIG_VALUE_2"]) == ("tag.gpgsign", "false")
    assert unsigned_git_environment({"GIT_CONFIG_COUNT": "junk"})["GIT_CONFIG_COUNT"] == "2"


def test_the_demo_repository_is_unsigned_by_its_own_config(tmp_path: Path) -> None:
    repo = tmp_path / "klein-demo"
    _init_repo(repo)
    assert _git(repo, "config", "--local", "--get", "commit.gpgsign") == "false"
    assert _git(repo, "config", "--local", "--get", "tag.gpgsign") == "false"
