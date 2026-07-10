"""Tests for preflight.py: a tmp git repo fixture (see conftest.git_repo)
gives a clean-pass baseline, then each test mutates exactly one thing to
exercise one failure mode and asserts the resulting FAIL count — preflight's
exit code IS the FAIL count (see main()'s docstring contract), so these
tests check the return value precisely, not just "nonzero".
"""

from __future__ import annotations

from pathlib import Path

from _helpers import run_git

RESULTS_HEADER = "experiment\tprimary_metric\tstatus\tcommit\tdescription"


def _commit_all(repo: Path, message: str = "data") -> None:
    add = run_git(["add", "-A"], repo)
    assert add.returncode == 0, add.stderr
    commit = run_git(["commit", "-q", "-m", message], repo)
    assert commit.returncode == 0, commit.stderr


# --------------------------------------------------------------------------
# Clean baseline
# --------------------------------------------------------------------------


def test_clean_repo_with_no_results_yet_passes(git_repo, preflight_module, monkeypatch):
    monkeypatch.chdir(git_repo)
    code = preflight_module.main([])
    assert code == 0


def test_valid_results_tsv_passes(git_repo, preflight_module, monkeypatch):
    (git_repo / "results.tsv").write_text(
        RESULTS_HEADER + "\n"
        "1\t0.625464\tkeep\tabc1234\tbaseline logistic\n"
        "2\tNA\tcrash\t-\ttimeout at budget\n"
        "3\t0.669402\tkeep\tdef5678a\thgb blend\n",
        encoding="utf-8",
    )
    _commit_all(git_repo)
    monkeypatch.chdir(git_repo)
    code = preflight_module.main([])
    assert code == 0


# --------------------------------------------------------------------------
# One failure mode at a time
# --------------------------------------------------------------------------


def test_main_branch_fails(git_repo, preflight_module, monkeypatch, capsys):
    checkout = run_git(["checkout", "-q", "main"], git_repo)
    assert checkout.returncode == 0, checkout.stderr
    monkeypatch.chdir(git_repo)
    code = preflight_module.main([])
    assert code == 1
    out = capsys.readouterr().out
    assert "[FAIL]" in out
    assert "git branch" in out
    assert "main" in out


def test_master_branch_fails(git_repo, preflight_module, monkeypatch):
    run_git(["checkout", "-q", "-b", "master"], git_repo)
    monkeypatch.chdir(git_repo)
    code = preflight_module.main([])
    assert code == 1


def test_dirty_tree_fails(git_repo, preflight_module, monkeypatch, capsys):
    (git_repo / "scratch.txt").write_text("uncommitted\n", encoding="utf-8")
    monkeypatch.chdir(git_repo)
    code = preflight_module.main([])
    assert code == 1
    out = capsys.readouterr().out
    assert "[FAIL]" in out
    assert "working tree clean" in out


def test_bad_header_fails(git_repo, preflight_module, monkeypatch, capsys):
    # Missing the "description" column.
    (git_repo / "results.tsv").write_text(
        "experiment\tprimary_metric\tstatus\tcommit\n" "1\t0.5\tkeep\tabc1234\n",
        encoding="utf-8",
    )
    _commit_all(git_repo)
    monkeypatch.chdir(git_repo)
    code = preflight_module.main([])
    assert code == 1
    out = capsys.readouterr().out
    assert "[FAIL] results.tsv header" in out
    assert "[SKIP] results.tsv rows" in out
    assert "[SKIP] results.tsv sequence" in out


def test_bad_row_fails(git_repo, preflight_module, monkeypatch, capsys):
    # Header valid, experiment numbers sequential — but row 2 has an
    # illegal status value. This must fail the *rows* check only; the
    # sequence check must stay OK (isolating "bad row" from "gap in
    # numbering" as distinct failure modes).
    (git_repo / "results.tsv").write_text(
        RESULTS_HEADER + "\n"
        "1\t0.5\tkeep\tabc1234\tbaseline\n"
        "2\t0.6\tmaybe\tdef5678\tsomething\n",
        encoding="utf-8",
    )
    _commit_all(git_repo)
    monkeypatch.chdir(git_repo)
    code = preflight_module.main([])
    assert code == 1
    out = capsys.readouterr().out
    assert "[FAIL] results.tsv rows" in out
    assert "status" in out
    assert "[OK]   results.tsv sequence" in out


def test_gap_in_numbering_fails(git_repo, preflight_module, monkeypatch, capsys):
    # Every row is individually valid, but experiment numbers skip 2 —
    # must fail the *sequence* check only.
    (git_repo / "results.tsv").write_text(
        RESULTS_HEADER + "\n"
        "1\t0.5\tkeep\tabc1234\tbaseline\n"
        "3\t0.6\tkeep\tdef5678\tsomething\n",
        encoding="utf-8",
    )
    _commit_all(git_repo)
    monkeypatch.chdir(git_repo)
    code = preflight_module.main([])
    assert code == 1
    out = capsys.readouterr().out
    assert "[OK]   results.tsv rows" in out
    assert "[FAIL] results.tsv sequence" in out
    assert "not strictly sequential" in out


def test_duplicate_experiment_number_fails(git_repo, preflight_module, monkeypatch):
    (git_repo / "results.tsv").write_text(
        RESULTS_HEADER + "\n"
        "1\t0.5\tkeep\tabc1234\tbaseline\n"
        "1\t0.6\tkeep\tdef5678\tduplicate\n",
        encoding="utf-8",
    )
    _commit_all(git_repo)
    monkeypatch.chdir(git_repo)
    code = preflight_module.main([])
    assert code == 1


def test_aux_metrics_bad_header_fails(git_repo, preflight_module, monkeypatch, capsys):
    (git_repo / "aux_metrics.tsv").write_text("experiment\tmetric\n1\twall_seconds\n", encoding="utf-8")
    _commit_all(git_repo)
    monkeypatch.chdir(git_repo)
    code = preflight_module.main([])
    assert code == 1
    out = capsys.readouterr().out
    assert "[FAIL] aux_metrics.tsv" in out


def test_mutable_syntax_error_fails(git_repo, preflight_module, monkeypatch, capsys):
    (git_repo / "train.py").write_text("def broken(:\n    pass\n", encoding="utf-8")
    _commit_all(git_repo)
    monkeypatch.chdir(git_repo)
    code = preflight_module.main(["--mutable", "train.py"])
    assert code == 1
    out = capsys.readouterr().out
    assert "[FAIL] syntax: train.py" in out


def test_prepared_data_missing_fails(git_repo, preflight_module, monkeypatch):
    monkeypatch.chdir(git_repo)
    code = preflight_module.main(["--prepared-data", "data/prepared/nope.csv"])
    assert code == 1


def test_prepared_data_present_passes(git_repo, preflight_module, monkeypatch):
    prepared = git_repo / "data" / "prepared"
    prepared.mkdir(parents=True)
    (prepared / "shard.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    _commit_all(git_repo)
    monkeypatch.chdir(git_repo)
    code = preflight_module.main(["--prepared-data", "data/prepared"])
    assert code == 0


def test_exit_code_counts_multiple_independent_fails(git_repo, preflight_module, monkeypatch):
    # main branch AND a dirty tree together: exit code must be the *count*
    # of FAILs (2), not merely a nonzero/boolean signal.
    run_git(["checkout", "-q", "main"], git_repo)
    (git_repo / "scratch.txt").write_text("uncommitted\n", encoding="utf-8")
    monkeypatch.chdir(git_repo)
    code = preflight_module.main([])
    assert code == 2


# --------------------------------------------------------------------------
# --study convenience expansion
# --------------------------------------------------------------------------


def test_study_flag_expands_conventional_paths(git_repo, preflight_module, monkeypatch, capsys):
    study = git_repo / "studies" / "00-demo"
    (study / "data" / "prepared").mkdir(parents=True)
    (study / "data" / "prepared" / "shard.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (study / "train.py").write_text("x = 1\n", encoding="utf-8")
    (study / "prepare.py").write_text("y = 2\n", encoding="utf-8")
    (study / "results.tsv").write_text(
        RESULTS_HEADER + "\n1\t0.5\tkeep\tabc1234\tbaseline\n", encoding="utf-8"
    )
    _commit_all(git_repo)
    monkeypatch.chdir(git_repo)
    code = preflight_module.main(["--study", "studies/00-demo"])
    out = capsys.readouterr().out
    assert code == 0
    assert "studies/00-demo/train.py" in out
    assert "studies/00-demo/prepare.py" in out
    assert "studies/00-demo/data/prepared" in out


def test_study_flag_yields_same_paths_as_manual_flags(git_repo, preflight_module, monkeypatch):
    study = git_repo / "studies" / "00-demo"
    (study / "data" / "prepared").mkdir(parents=True)
    resolved = preflight_module.resolve_paths(
        preflight_module.parse_args(["--study", str(study)])
    )
    results_path, aux_path, mutable, prepared_data = resolved
    assert results_path == study / "results.tsv"
    assert aux_path == study / "aux_metrics.tsv"
    assert mutable == [study / "train.py", study / "prepare.py"]
    assert prepared_data == [study / "data" / "prepared"]


def test_study_flag_overridden_by_explicit_flags(preflight_module):
    study = Path("studies/00-demo")
    args = preflight_module.parse_args(
        ["--study", str(study), "--mutable", "custom_train.py", "--results-path", "custom_results.tsv"]
    )
    results_path, aux_path, mutable, prepared_data = preflight_module.resolve_paths(args)
    assert results_path == Path("custom_results.tsv")
    assert mutable == [Path("custom_train.py")]
    # aux-path and prepared-data were not overridden, so they still expand from --study.
    assert aux_path == study / "aux_metrics.tsv"
    assert prepared_data == [study / "data" / "prepared"]
