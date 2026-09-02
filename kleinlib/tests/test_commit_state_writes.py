"""``commit_state_writes`` — the default path, the injectable committer, ``paths=``.

The extraction of :mod:`kleinlib.transaction` gave this helper two optional
keywords.  Both must be invisible when unused: the same files are staged, the
same commit is made, and the same ``None`` comes back when nothing changed.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from kleinlib.transaction import STATE_WRITE_PATHS, commit_state_writes


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, text=True, capture_output=True, check=False
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


@pytest.fixture
def study(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "studies" / "03-demo").mkdir(parents=True)
    git(repo, "init", "-q")
    git(repo, "-c", "user.name=T", "-c", "user.email=t@x.invalid", "commit", "-q",
        "--allow-empty", "-m", "root")
    return repo / "studies" / "03-demo"


def committed_files(repo: Path) -> set[str]:
    return set(git(repo, "show", "--name-only", "--format=", "HEAD").splitlines())


def test_default_call_stages_exactly_the_state_write_paths(study: Path) -> None:
    repo = study.parents[1]
    (study / "program.md").write_text("notes\n", encoding="utf-8")
    (study / "study_state.json").write_text("{}\n", encoding="utf-8")
    (study / "train.py").write_text("print('x')\n", encoding="utf-8")  # never staged

    head = commit_state_writes(study, "klein: state writes filed")
    assert head == git(repo, "rev-parse", "HEAD")
    assert committed_files(repo) == {
        "studies/03-demo/program.md",
        "studies/03-demo/study_state.json",
    }
    assert git(repo, "log", "-1", "--format=%s") == "klein: state writes filed"
    # train.py is deliberately absent from STATE_WRITE_PATHS: committing it would
    # move run-one's restore anchor.
    assert "train.py" not in STATE_WRITE_PATHS


def test_nothing_to_commit_returns_none_and_leaves_head_alone(study: Path) -> None:
    repo = study.parents[1]
    before = git(repo, "rev-parse", "HEAD")
    assert commit_state_writes(study, "klein: nothing") is None
    (study / "program.md").write_text("notes\n", encoding="utf-8")
    commit_state_writes(study, "klein: first")
    assert commit_state_writes(study, "klein: again") is None
    assert git(repo, "rev-parse", "HEAD") != before
    assert git(repo, "log", "-1", "--format=%s") == "klein: first"


def test_outside_a_git_repository_it_is_a_no_op(tmp_path: Path) -> None:
    bare = tmp_path / "loose"
    bare.mkdir()
    (bare / "program.md").write_text("notes\n", encoding="utf-8")
    assert commit_state_writes(bare, "klein: nowhere") is None


def test_paths_adds_extra_study_relative_files(study: Path) -> None:
    repo = study.parents[1]
    (study / "program.md").write_text("notes\n", encoding="utf-8")
    (study / "report").mkdir()
    (study / "report" / "index.html").write_text("<p>hi</p>\n", encoding="utf-8")
    (study / "claims.lock").write_text("{}\n", encoding="utf-8")

    commit_state_writes(study, "klein: with extras", paths=("report", "claims.lock"))
    assert committed_files(repo) == {
        "studies/03-demo/program.md",
        "studies/03-demo/report/index.html",
        "studies/03-demo/claims.lock",
    }


def test_paths_entries_that_do_not_exist_are_skipped(study: Path) -> None:
    repo = study.parents[1]
    (study / "program.md").write_text("notes\n", encoding="utf-8")
    commit_state_writes(study, "klein: absent extras", paths=("nope", "also/missing"))
    assert committed_files(repo) == {"studies/03-demo/program.md"}


def test_paths_never_duplicates_a_default_entry(study: Path) -> None:
    repo = study.parents[1]
    (study / "program.md").write_text("notes\n", encoding="utf-8")
    commit_state_writes(study, "klein: dup", paths=("program.md", "program.md"))
    assert committed_files(repo) == {"studies/03-demo/program.md"}


def test_commit_keyword_substitutes_the_committer(study: Path) -> None:
    (study / "program.md").write_text("notes\n", encoding="utf-8")
    seen: list[tuple[Path, str]] = []

    def fake_commit(repo: Path, message: str, **_kwargs) -> str:
        seen.append((repo, message))
        return "deadbeef"

    assert commit_state_writes(study, "klein: injected", commit=fake_commit) == "deadbeef"
    assert [message for _, message in seen] == ["klein: injected"]
    # the files were still staged; only the commit itself was substituted
    repo = study.parents[1]
    assert "studies/03-demo/program.md" in git(repo, "diff", "--cached", "--name-only")
