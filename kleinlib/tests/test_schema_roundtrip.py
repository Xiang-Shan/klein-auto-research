"""Round-trip tests for kleinlib.schema: the results.tsv contract.

The schema-drift bug (a 4-column vs 5-column doc mismatch corrupting
appends) is why this module exists at all — these tests exercise its
happy and sad paths directly against the single source of truth.
"""

from __future__ import annotations

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
