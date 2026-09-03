"""Round-trip tests for kleinlib.schema: the results.tsv contract.

The schema-drift bug (a 4-column vs 5-column doc mismatch corrupting
appends) is why this module exists at all — these tests exercise its
happy and sad paths directly against the single source of truth.
"""

from __future__ import annotations

import pytest

from kleinlib import schema


def test_header_line_matches_columns():
    assert schema.header_line() == "\t".join(schema.RESULTS_COLUMNS)
    assert "\n" not in schema.header_line()


def test_is_valid_header_happy_paths():
    assert schema.is_valid_header(schema.header_line())
    assert schema.is_valid_header(schema.header_line() + "\n")
    assert schema.is_valid_header(schema.header_line() + "\tstudy_id")


def test_is_valid_header_sad_paths():
    # missing a column
    assert not schema.is_valid_header("experiment\tprimary_metric\tstatus\tcommit")
    # reordered columns
    assert not schema.is_valid_header(
        "primary_metric\texperiment\tstatus\tcommit\tdescription"
    )
    # unknown trailing column
    assert not schema.is_valid_header(schema.header_line() + "\tbogus_column")


def test_validate_row_happy_path():
    row = ["1", "0.6528", "keep", "abc1234", "baseline LR"]
    assert schema.validate_row(row, n_columns=5) == []


def test_validate_row_crash_na_metric_is_valid():
    row = ["2", schema.NA_METRIC, "crash", schema.NO_COMMIT, "OOM"]
    assert schema.validate_row(row, n_columns=5) == []


def test_validate_row_sad_paths():
    problems = schema.validate_row(["1", "0.5", "keep", "abc1234"], n_columns=5)
    assert any("expected 5 fields" in p for p in problems)

    problems = schema.validate_row(["x", "0.5", "keep", "abc1234", "d"], n_columns=5)
    assert any("experiment must be an integer" in p for p in problems)

    problems = schema.validate_row(["1", "0.5", "maybe", "abc1234", "d"], n_columns=5)
    assert any("status must be one of" in p for p in problems)

    problems = schema.validate_row(
        ["1", schema.NA_METRIC, "keep", "abc1234", "d"], n_columns=5
    )
    assert any("may be 'NA' only when status is 'crash'" in p for p in problems)

    problems = schema.validate_row(
        ["1", "not-a-number", "keep", "abc1234", "d"], n_columns=5
    )
    assert any("primary_metric must be a float" in p for p in problems)

    problems = schema.validate_row(["1", "0.5", "keep", "zzz", "d"], n_columns=5)
    assert any("commit must be" in p for p in problems)


@pytest.mark.parametrize("metric", ["nan", "inf", "-inf"])
def test_validate_row_rejects_nonfinite_metrics(metric):
    problems = schema.validate_row(
        ["1", metric, "keep", "abc1234", "invalid metric"], n_columns=5
    )
    assert any("finite" in problem for problem in problems)


# ---------------------------------------------------------------------------
# C5: a Windows-style path never enters a ledger
# ---------------------------------------------------------------------------


def test_every_path_a_ledger_stores_is_posix(tmp_path, monkeypatch) -> None:
    """`study_state.json`, `verify_receipt.json` and `results_summary.md` are all
    committed, so a separator that differs by platform is a diff that differs by
    platform. Simulated by pretending PurePath renders like Windows."""
    import ntpath
    import posixpath
    from pathlib import PurePath, PureWindowsPath

    # The property under test, stated directly: as_posix() is stable across the
    # two separators, str() is not.
    windows = PureWindowsPath(r"studies\09\data\prepared\x.csv")
    assert windows.as_posix() == "studies/09/data/prepared/x.csv"
    assert str(windows) != windows.as_posix()
    assert PurePath("studies/09/x.csv").as_posix() == "studies/09/x.csv"
    assert ntpath.sep != posixpath.sep  # the reason this test exists

    # And the writers use it: no ledger writer renders a path with str().
    import inspect

    from kleinlib import checks, state

    for module, function in (
        (state, "initial_state"),
        (state, "record_gate"),
        (checks, "_study_python_sources"),
    ):
        source = inspect.getsource(getattr(module, function))
        assert "str(prepared_data_path" not in source
        assert "str(data_path)" not in source
        assert "str(path.relative_to" not in source
