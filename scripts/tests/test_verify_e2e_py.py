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


# ---------------------------------------------------------------------------
# The schema-3 lane's pure helpers
# ---------------------------------------------------------------------------

_FLOOR_REPORT = """\
estimand=marginal-resplit  recipe=split-lottery  k=5  mean=0.809846  std=0.0317834  \
range=0.089231  suggested minimum_delta=0.0635668

# tracks.primary.metric \u2014 set minimum_delta from the measured floor:
      minimum_delta: 0.0635668   # = max(2*std, range/2), std 0.0317834
      noise_floor:
        k: 5
        std: 0.0317834
        source: "sweeps/split_lottery.sidecar.tsv"
        estimand: "marginal-resplit"

next: edit study.yaml, then re-record the consult gate
"""


def test_contract_block_keeps_only_the_pasteable_lines() -> None:
    """The lane pastes the ENGINE's own printed block into study.yaml, so the
    header, the comment and the `next:` footer must all be dropped."""
    block = verify_e2e.contract_block(_FLOOR_REPORT)
    assert block.startswith("      minimum_delta: 0.0635668")
    assert block.endswith('        estimand: "marginal-resplit"\n')
    assert "next:" not in block and "estimand=marginal-resplit" not in block
    assert "# tracks.primary.metric" not in block


def test_contract_block_aborts_when_the_report_carries_no_block() -> None:
    with pytest.raises(verify_e2e.AbortE2E) as excinfo:
        verify_e2e.contract_block("k=5  mean=1  std=0\n")
    assert excinfo.value.exit_code == 1


def test_yaml_scalar_reads_the_value_as_written() -> None:
    """Never re-formatted through float(): the numbers law compares the bytes a
    reader sees against the bytes on disk."""
    block = verify_e2e.contract_block(_FLOOR_REPORT)
    assert verify_e2e._yaml_scalar(block, "minimum_delta") == "0.0635668"
    assert verify_e2e._yaml_scalar(block, "std") == "0.0317834"
    with pytest.raises(verify_e2e.AbortE2E):
        verify_e2e._yaml_scalar(block, "range")


@pytest.mark.parametrize(
    ("token", "expected"),
    [("0.95", "2"), ("0.0635668", "7"), ("1", "0"), ("42", "0"), ("-0.07", "2")],
)
def test_precision_of_counts_the_decimals_as_written(token: str, expected: str) -> None:
    assert verify_e2e._precision_of(token) == expected


def test_replace_once_refuses_zero_or_many_matches() -> None:
    assert verify_e2e.replace_once("a b a", "b", "c", what="thing") == "a c a"
    for text in ("a a", "nothing here"):
        with pytest.raises(verify_e2e.AbortE2E, match="exactly one thing"):
            verify_e2e.replace_once(text, "a a a" if text == "a a" else "b", "c", what="thing")


def test_lane_branch_override_suffixes_only_when_lanes_share_a_run() -> None:
    """Each lane owns its own branch, and a name that already exists is refused —
    so a two-lane run cannot hand both lanes the same override."""
    assert verify_e2e.lane_branch_override(None, "legacy", verify_e2e.LANES) is None
    assert verify_e2e.lane_branch_override("b", "schema3", ("schema3",)) == "b"
    # the first lane keeps the exact name, so a collision is refused before any
    # lane does work
    assert verify_e2e.lane_branch_override("b", "legacy", verify_e2e.LANES) == "b"
    assert verify_e2e.lane_branch_override("b", "schema3", verify_e2e.LANES) == "b-schema3"


def test_the_lane_reads_artifact_values_as_raw_strings(tmp_path: Path) -> None:
    results = tmp_path / "results.tsv"
    results.write_text(
        "experiment\ttrack\tprimary_metric\tstatus\n"
        "E0001\tprimary\t0.87\tkeep\n"
        "E0004\tcells\t1\tmeasured\n",
        encoding="utf-8",
    )
    rows = verify_e2e.tsv_rows(results)
    assert verify_e2e.results_metric(rows, "E0001") == "0.87"
    assert verify_e2e.results_metric(rows, "E0004") == "1"  # not 1.0
    with pytest.raises(verify_e2e.AbortE2E):
        verify_e2e.results_metric(rows, "E9999")

    aux = tmp_path / "aux_metrics.tsv"
    aux.write_text("experiment\tmetric\tvalue\nE0004\tbar\t0.933567\n", encoding="utf-8")
    assert verify_e2e.aux_value(verify_e2e.tsv_rows(aux), "E0004", "bar") == "0.933567"
    with pytest.raises(verify_e2e.AbortE2E):
        verify_e2e.aux_value(verify_e2e.tsv_rows(aux), "E0004", "nope")

    table = tmp_path / "family_map.tsv"
    table.write_text(
        "family\tval_auc\tdelta_vs_logreg\ntree_d2\t0.95\t0.08\n", encoding="utf-8"
    )
    rows = verify_e2e.tsv_rows(table)
    assert verify_e2e.family_value(rows, "tree_d2", "delta_vs_logreg") == "0.08"
    with pytest.raises(verify_e2e.AbortE2E):
        verify_e2e.family_value(rows, "tree_d9", "val_auc")


def test_the_lane_fixture_never_hardcodes_a_measured_number() -> None:
    """Every number the lane writes into a document comes from an artifact at run
    time; a literal in the fixture would be a number with no home the moment the
    data or the library moves."""
    for name, text in (
        ("findings", verify_e2e._V3_FINDINGS),
        ("program", verify_e2e._V3_PROGRAM_APPEND),
        ("playbook", verify_e2e._V3_PLAYBOOK),
    ):
        assert "0.95" not in text and "0.0635668" not in text, name
    assert "${best}" in verify_e2e._V3_FINDINGS
    # ...and the entrypoint reads its floor from the contract, never a literal.
    assert 'load_contract(".")["tracks"]["primary"]["metric"]["minimum_delta"]' in (
        verify_e2e._V3_TRAIN_PY
    )


def test_the_lane_declares_the_seven_tutorial_fragments() -> None:
    assert sorted(verify_e2e._V3_FRAGMENTS) == [
        "01-question.html", "02-method.html", "03-data.html", "04-journey.html",
        "05-findings.html", "06-coding-advice.html", "07-next-steps.html",
    ]
    joined = "".join(verify_e2e._V3_FRAGMENTS.values())
    assert "<!--LEDGER-->" in joined  # the auto-generated experiment ledger
    assert 'data-code="train.py"' in joined  # the entrypoint by reference
    assert "data-fig=" in joined and "data-math-display=" in joined


def test_the_referee_report_carries_the_two_machine_read_lines() -> None:
    first, second = verify_e2e._V3_REFEREE_REPORT.splitlines()[:2]
    assert first == "Verdict: PASS"
    assert second.startswith("Referee: ") and "independent-of-experimenter: yes" in second


def test_main_parses_the_lane_option() -> None:
    parser = verify_e2e.build_parser()
    assert parser.parse_args([]).lane == "all"
    assert parser.parse_args(["--lane", "schema3"]).lane == "schema3"
    with pytest.raises(SystemExit):
        parser.parse_args(["--lane", "nope"])
