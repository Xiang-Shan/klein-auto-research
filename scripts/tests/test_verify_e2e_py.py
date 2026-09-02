"""Unit tests for the pure/small helpers in scripts/verify_e2e.py.

These exercise table rendering, branch-name refusal, and the temp-dir
containment guard in isolation -- none of them run the full three-experiment
proof (that is exercised by test_verify_e2e.py's subprocess-level tests and by
a manual `uv run --locked python scripts/verify_e2e.py` for the final table).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import verify_e2e  # noqa: E402


def _git(*args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=check, text=True, capture_output=True
    )


@pytest.fixture()
def tiny_repo(tmp_path: Path) -> Path:
    """A throwaway git repo, isolated from the real checkout, for tests that
    need SOME repository to run `git show-ref` / `git check-ref-format`
    against."""
    repo = tmp_path / "tiny-repo"
    repo.mkdir()
    _git("init", "-q", cwd=repo)
    _git("-c", "user.name=Test", "-c", "user.email=test@local", "commit", "-q", "--allow-empty", "-m", "root", cwd=repo)
    return repo


# ---------------------------------------------------------------------------
# Table rendering
# ---------------------------------------------------------------------------


def test_render_line_formats_status_and_description() -> None:
    result = verify_e2e.CheckResult("PASS", "example check")
    assert verify_e2e.render_line(result) == "[PASS] example check"


def test_render_summary_counts_and_result_all_pass() -> None:
    results = [
        verify_e2e.CheckResult("PASS", "check one"),
        verify_e2e.CheckResult("PASS", "check two"),
    ]
    table = verify_e2e.render_summary(results)
    assert "[PASS] check one" in table
    assert "[PASS] check two" in table
    assert "total: PASS=2  FAIL=0  (of 2 checks)" in table
    assert "RESULT: PASS" in table
    assert "RESULT: FAIL" not in table


def test_render_summary_counts_and_result_with_failure() -> None:
    results = [
        verify_e2e.CheckResult("PASS", "check one"),
        verify_e2e.CheckResult("FAIL", "check two broke"),
        verify_e2e.CheckResult("PASS", "check three"),
    ]
    table = verify_e2e.render_summary(results)
    assert "total: PASS=2  FAIL=1  (of 3 checks)" in table
    assert "RESULT: FAIL" in table


def test_render_summary_empty_results_is_a_clean_pass() -> None:
    table = verify_e2e.render_summary([])
    assert "total: PASS=0  FAIL=0  (of 0 checks)" in table
    assert "RESULT: PASS" in table


def test_record_appends_and_prints(capsys: pytest.CaptureFixture[str]) -> None:
    results: list[verify_e2e.CheckResult] = []
    verify_e2e.record(results, "PASS", "did the thing")
    assert results == [verify_e2e.CheckResult("PASS", "did the thing")]
    assert "[PASS] did the thing" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# results.tsv row validation (the awk VALIDATE block, ported)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "row",
    [
        ["1", "0.9123", "keep", "abc1234", "desc"],
        ["2", "NA", "crash", "-", "desc"],
        ["3", "-0.5", "discard", "-", "desc"],
        ["4", "1.2e-3", "keep", "0123456789abcdef", "desc"],
    ],
)
def test_validate_results_row_accepts_well_formed_rows(row: list[str]) -> None:
    ok, rendered = verify_e2e.validate_results_row(row)
    assert ok is True
    assert rendered.startswith("OK: ")


@pytest.mark.parametrize(
    "row",
    [
        ["x", "0.9", "keep", "abc1234", "desc"],  # non-numeric experiment id
        ["1", "0.9", "bogus", "abc1234", "desc"],  # bad status
        ["1", "0.5", "crash", "-", "desc"],  # crash must have metric NA
        ["1", "NA", "keep", "abc1234", "desc"],  # keep must have numeric metric
        ["1", "0.9", "keep", "zz", "desc"],  # commit not a hex short-hash
    ],
)
def test_validate_results_row_rejects_malformed_rows(row: list[str]) -> None:
    ok, rendered = verify_e2e.validate_results_row(row)
    assert ok is False
    assert rendered.startswith("ERROR: ")


def test_validate_results_row_rejects_wrong_column_count() -> None:
    ok, rendered = verify_e2e.validate_results_row(["1", "0.9", "keep"])
    assert ok is False
    assert rendered.startswith("ERROR: ")


# ---------------------------------------------------------------------------
# Branch-name refusal
# ---------------------------------------------------------------------------


def test_check_branch_available_accepts_a_fresh_valid_name(tiny_repo: Path) -> None:
    verify_e2e.check_branch_available(tiny_repo, "a-fresh-branch-name")  # must not raise


def test_check_branch_available_refuses_pre_existing_branch(tiny_repo: Path) -> None:
    _git("branch", "already-here", cwd=tiny_repo)
    with pytest.raises(verify_e2e.AbortE2E) as excinfo:
        verify_e2e.check_branch_available(tiny_repo, "already-here")
    assert excinfo.value.exit_code == 2
    assert "refusing to reuse or delete pre-existing branch" in (excinfo.value.message or "")


def test_check_branch_available_refuses_invalid_ref_name(tiny_repo: Path) -> None:
    with pytest.raises(verify_e2e.AbortE2E) as excinfo:
        verify_e2e.check_branch_available(tiny_repo, "not a valid ref name")
    assert excinfo.value.exit_code == 2
    assert "invalid temporary branch name" in (excinfo.value.message or "")


def test_check_branch_available_never_deletes_the_colliding_branch(tiny_repo: Path) -> None:
    _git("branch", "must-survive", cwd=tiny_repo)
    with pytest.raises(verify_e2e.AbortE2E):
        verify_e2e.check_branch_available(tiny_repo, "must-survive")
    assert _git("show-ref", "--verify", "--quiet", "refs/heads/must-survive", cwd=tiny_repo, check=False).returncode == 0


# ---------------------------------------------------------------------------
# Temp-dir containment guard
# ---------------------------------------------------------------------------


def test_safe_rmtree_removes_a_path_nested_inside_the_root(tmp_path: Path) -> None:
    root = tmp_path / "base"
    nested = root / "worktree"
    nested.mkdir(parents=True)
    (nested / "marker.txt").write_text("x", encoding="utf-8")

    verify_e2e.safe_rmtree(nested, containment_root=root)

    assert not nested.exists()
    assert root.exists()  # only the nested path was removed


def test_safe_rmtree_removes_the_root_itself(tmp_path: Path) -> None:
    root = tmp_path / "base"
    root.mkdir()

    verify_e2e.safe_rmtree(root, containment_root=root)

    assert not root.exists()


def test_safe_rmtree_refuses_a_path_outside_the_root(tmp_path: Path) -> None:
    root = tmp_path / "base"
    root.mkdir()
    outside = tmp_path / "unrelated-sibling"
    outside.mkdir()
    (outside / "do-not-delete-me.txt").write_text("precious", encoding="utf-8")

    with pytest.raises(ValueError, match="outside containment root"):
        verify_e2e.safe_rmtree(outside, containment_root=root)

    assert outside.exists()
    assert (outside / "do-not-delete-me.txt").exists()


def test_safe_rmtree_refuses_a_shallow_prefix_lookalike(tmp_path: Path) -> None:
    """A directory that merely shares a string prefix with the containment
    root (but is not actually nested under it) must be refused -- a naive
    `str(path).startswith(str(root))` guard would wrongly allow this."""
    root = tmp_path / "base"
    root.mkdir()
    lookalike = tmp_path / "base-but-not-really"
    lookalike.mkdir()

    with pytest.raises(ValueError, match="outside containment root"):
        verify_e2e.safe_rmtree(lookalike, containment_root=root)

    assert lookalike.exists()


def test_safe_rmtree_is_a_no_op_on_a_missing_path(tmp_path: Path) -> None:
    root = tmp_path / "base"
    root.mkdir()
    missing = root / "never-created"

    verify_e2e.safe_rmtree(missing, containment_root=root)  # must not raise


# ---------------------------------------------------------------------------
# Status-delta comparison (the "unrelated concurrent activity" heuristic)
# ---------------------------------------------------------------------------


def test_compare_status_passes_when_unchanged() -> None:
    results: list[verify_e2e.CheckResult] = []
    verify_e2e.compare_status(" M foo.py\n", " M foo.py\n", results)
    assert results == [
        verify_e2e.CheckResult("PASS", "real tree git status unchanged after the run")
    ]


def test_compare_status_fails_when_delta_names_own_artifacts() -> None:
    results: list[verify_e2e.CheckResult] = []
    verify_e2e.compare_status("", "?? studies/99-e2e/\n", results)
    assert results[0].status == "FAIL"
    assert "99-e2e" in results[0].description


def test_compare_status_passes_on_unrelated_concurrent_activity(capsys: pytest.CaptureFixture[str]) -> None:
    results: list[verify_e2e.CheckResult] = []
    verify_e2e.compare_status("", "?? studies/other-study/new_file.py\n", results)
    assert results[0].status == "PASS"
    assert "unrelated concurrent activity" in results[0].description
    assert "studies/other-study" in capsys.readouterr().out
