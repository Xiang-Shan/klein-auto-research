"""``commit_state_writes`` — the default path, the injectable committer, ``paths=``.

The extraction of :mod:`kleinlib.transaction` gave this helper two optional
keywords.  Both must be invisible when unused: the same files are staged, the
same commit is made, and the same ``None`` comes back when nothing changed.

E15 added a third, ``scope=``.  ``scope="state"`` is that same behaviour, kept
for the verbs that deliberately file the study's artifacts (gate records,
``run-one``, ``finalize``, ``recover``).  ``scope="own"`` commits ONLY what the
verb wrote — its ``paths`` plus ``study_state.json``/``events.jsonl`` — through
``git commit --only``, and names on stdout the operator edits it declined to
take.  The helpers at the bottom of this module (``seed_tracked``,
``operator_edits``, ``modified_paths``) are imported by every verb's own test
module, so the promise is pinned once and reused.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from kleinlib.errors import WorkflowError
from kleinlib.state import record_gate
from kleinlib.transaction import STATE_WRITE_PATHS, commit_state_writes, git_commit


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


# --------------------------------------------------------------------------
# E15 — scope="own": a verb commits only what it wrote
# --------------------------------------------------------------------------

#: What an "operator edit" appends, so a test can tell a file the verb rewrote
#: from one the operator was in the middle of editing when the verb ran.
OPERATOR_MARK = b"\nan operator edit no verb wrote\n"


def status_lines(repo: Path) -> list[str]:
    """Raw porcelain status lines for TRACKED files.

    Deliberately not routed through :func:`git`, which strips: the porcelain
    format puts the unstaged flag in column 2, so a leading space is
    load-bearing and ``line[3:]`` only finds the path if nothing trimmed it.
    """
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return [line for line in result.stdout.splitlines() if line.strip()]


def modified_paths(repo: Path) -> set[str]:
    """Repo-relative tracked paths that still carry uncommitted changes."""
    return {line[3:].split(" -> ")[-1] for line in status_lines(repo)}


def seed_tracked(repo: Path, study: Path, *names: str) -> None:
    """Create and COMMIT ``names`` under the study, so a later write is a modification."""
    for name in names:
        path = study / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(b"seed\n")
    git(repo, "add", "-A")
    git(repo, "-c", "user.name=T", "-c", "user.email=t@x.invalid", "commit", "-q",
        "-m", "seed the operator's files")


def operator_edits(study: Path, *names: str) -> None:
    """Leave already-tracked study files modified in the working tree."""
    for name in names:
        path = study / name
        path.write_bytes(path.read_bytes() + OPERATOR_MARK)


def test_own_scope_commits_its_paths_plus_state_and_events_only(study: Path) -> None:
    repo = study.parents[1]
    seed_tracked(repo, study, "findings.md", "program.md")
    operator_edits(study, "findings.md", "program.md")
    (study / "verify_receipt.json").write_text('{"ok": true}\n', encoding="utf-8")
    (study / "study_state.json").write_text("{}\n", encoding="utf-8")

    head = commit_state_writes(
        study, "klein: verify receipt", paths=["verify_receipt.json"], scope="own"
    )
    assert head == git(repo, "rev-parse", "HEAD")
    assert committed_files(repo) == {
        "studies/03-demo/verify_receipt.json",
        "studies/03-demo/study_state.json",
    }
    # the operator's edits are still exactly where the operator left them
    assert modified_paths(repo) == {
        "studies/03-demo/findings.md",
        "studies/03-demo/program.md",
    }
    assert (study / "findings.md").read_bytes().endswith(OPERATOR_MARK)


def test_own_scope_names_the_edits_it_left_behind(study: Path, capsys) -> None:
    repo = study.parents[1]
    seed_tracked(repo, study, "findings.md", "program.md")
    operator_edits(study, "findings.md", "program.md")
    (study / "claims.lock").write_text("{}\n", encoding="utf-8")

    commit_state_writes(study, "klein: claims", paths=["claims.lock"], scope="own")
    assert (
        "note: 2 uncommitted edit(s) left in the tree "
        "(findings.md, program.md) — not part of this commit"
    ) in capsys.readouterr().out


def test_the_notice_sorts_and_elides_past_five_names(study: Path, capsys) -> None:
    repo = study.parents[1]
    names = [f"n{index}.md" for index in range(6)]
    seed_tracked(repo, study, *names)
    operator_edits(study, *names)
    (study / "claims.lock").write_text("{}\n", encoding="utf-8")

    commit_state_writes(study, "klein: claims", paths=["claims.lock"], scope="own")
    out = capsys.readouterr().out
    assert "note: 6 uncommitted edit(s) left in the tree" in out
    assert "(n0.md, n1.md, n2.md, n3.md, n4.md, …)" in out
    assert "n5.md" not in out


def test_own_scope_says_nothing_when_the_tree_was_clean(study: Path, capsys) -> None:
    repo = study.parents[1]
    seed_tracked(repo, study, "findings.md")
    (study / "claims.lock").write_text("{}\n", encoding="utf-8")
    commit_state_writes(study, "klein: claims", paths=["claims.lock"], scope="own")
    assert "uncommitted edit" not in capsys.readouterr().out
    assert modified_paths(repo) == set()


def test_own_scope_never_takes_a_narrative_file_it_did_not_write(study: Path) -> None:
    """The whole defect: a verify receipt used to carry findings.md with it."""
    repo = study.parents[1]
    seed_tracked(repo, study, "findings.md", "playbook.md", "results_summary.md")
    operator_edits(study, "findings.md", "playbook.md", "results_summary.md")
    (study / "verify_receipt.json").write_text("{}\n", encoding="utf-8")

    commit_state_writes(
        study, "klein: verify receipt", paths=["verify_receipt.json"], scope="own"
    )
    assert committed_files(repo) == {"studies/03-demo/verify_receipt.json"}


def test_own_scope_is_decided_by_its_own_paths_not_a_pre_staged_file(study: Path) -> None:
    """A file the operator staged can neither trigger nor join an own-scope commit."""
    repo = study.parents[1]
    seed_tracked(repo, study, "findings.md", "verify_receipt.json")
    operator_edits(study, "findings.md")
    git(repo, "add", "--", "studies/03-demo/findings.md")
    before = git(repo, "rev-parse", "HEAD")

    # nothing of OURS changed -> no commit at all, and the staged file stays staged
    assert (
        commit_state_writes(
            study, "klein: verify receipt", paths=["verify_receipt.json"], scope="own"
        )
        is None
    )
    assert git(repo, "rev-parse", "HEAD") == before
    assert "studies/03-demo/findings.md" in git(repo, "diff", "--cached", "--name-only")


def test_own_scope_leaves_a_staged_unrelated_file_out_of_its_commit(study: Path) -> None:
    repo = study.parents[1]
    seed_tracked(repo, study, "findings.md", "verify_receipt.json")
    operator_edits(study, "findings.md")
    git(repo, "add", "--", "studies/03-demo/findings.md")
    (study / "verify_receipt.json").write_text("{}\n", encoding="utf-8")

    commit_state_writes(
        study, "klein: verify receipt", paths=["verify_receipt.json"], scope="own"
    )
    assert committed_files(repo) == {"studies/03-demo/verify_receipt.json"}
    assert "studies/03-demo/findings.md" in git(repo, "diff", "--cached", "--name-only")


def test_a_leftover_outside_the_study_is_named_repo_relative(study: Path, capsys) -> None:
    repo = study.parents[1]
    (repo / "AGENTS.md").write_text("manual\n", encoding="utf-8")
    seed_tracked(repo, study, "findings.md")
    (repo / "AGENTS.md").write_text("manual, edited\n", encoding="utf-8")
    (study / "claims.lock").write_text("{}\n", encoding="utf-8")

    commit_state_writes(study, "klein: claims", paths=["claims.lock"], scope="own")
    assert "(AGENTS.md)" in capsys.readouterr().out


def test_state_scope_is_the_unchanged_default(study: Path, capsys) -> None:
    """``scope="state"`` still sweeps the whole STATE_WRITE_PATHS list, silently."""
    repo = study.parents[1]
    seed_tracked(repo, study, "findings.md", "program.md")
    operator_edits(study, "findings.md", "program.md")
    (study / "referee_report.md").write_text("Verdict: PASS\n", encoding="utf-8")

    commit_state_writes(study, "klein: referee gate recorded", paths=["referee_report.md"])
    assert committed_files(repo) == {
        "studies/03-demo/findings.md",
        "studies/03-demo/program.md",
        "studies/03-demo/referee_report.md",
    }
    assert modified_paths(repo) == set()
    assert "uncommitted edit" not in capsys.readouterr().out


def test_an_unknown_scope_is_refused(study: Path) -> None:
    (study / "program.md").write_text("notes\n", encoding="utf-8")
    with pytest.raises(WorkflowError, match="unknown commit scope 'everything'"):
        commit_state_writes(study, "klein: bad scope", scope="everything")


def test_own_scope_state_and_events_ride_along_only_when_they_changed(study: Path) -> None:
    repo = study.parents[1]
    seed_tracked(repo, study, "study_state.json", "events.jsonl")
    (study / "events.jsonl").write_text('{"e": 1}\n', encoding="utf-8")
    (study / "claims.lock").write_text("{}\n", encoding="utf-8")

    commit_state_writes(study, "klein: claims", paths=["claims.lock"], scope="own")
    assert committed_files(repo) == {
        "studies/03-demo/claims.lock",
        "studies/03-demo/events.jsonl",
    }


def test_gate_record_consult_still_files_an_uncommitted_research_plan(ready_study) -> None:
    """``scope="state"`` is untouched: a gate files the artifacts it hashes.

    "Commit before the gate" is made mechanical by the gate record itself — the
    hash on the record must name bytes that are in the repository, so a plan the
    operator has only just written is exactly what the record is FOR.  This is
    the boundary of E15: reading verbs let the tree be, recording gates do not.
    """
    repo, study = ready_study
    plan = study / "research_plan.md"
    plan.write_text(
        plan.read_text(encoding="utf-8") + "\n- a paragraph the operator just wrote\n",
        encoding="utf-8",
    )
    assert modified_paths(repo) == {"studies/03-demo/research_plan.md"}

    record_gate(study, "consult", acknowledged_by="tester")

    assert "studies/03-demo/research_plan.md" in git(
        repo, "show", "--name-only", "--format=", "HEAD"
    )
    assert modified_paths(repo) == set()


def test_git_commit_only_leaves_a_staged_unnamed_file_staged_and_uncommitted(
    study: Path,
) -> None:
    """The primitive under ``scope="own"``: ``--only`` ignores the rest of the index."""
    repo = study.parents[1]
    seed_tracked(repo, study, "findings.md", "claims.lock")
    operator_edits(study, "findings.md")
    (study / "claims.lock").write_text('{"claims": []}\n', encoding="utf-8")
    git(repo, "add", "--", "studies/03-demo/findings.md", "studies/03-demo/claims.lock")

    head = git_commit(repo, "klein: only the lock", only=["studies/03-demo/claims.lock"])
    assert head == git(repo, "rev-parse", "HEAD")
    assert committed_files(repo) == {"studies/03-demo/claims.lock"}
    # findings.md is STILL staged, and still not in any commit
    assert git(repo, "diff", "--cached", "--name-only") == "studies/03-demo/findings.md"
    assert modified_paths(repo) == {"studies/03-demo/findings.md"}
