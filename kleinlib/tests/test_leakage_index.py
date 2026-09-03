"""`python -m kleinlib.leakage --index` — checklist row 3 on a split index table.

A tabular study hashes its whole prepared frame; an image, sequence, graph or
text study cannot, so its DATA gate audits the index its `prepare.py` wrote
(`references/data-gate-protocol.md` §5).  The index IS the realized split, so
the audit checks the two contaminations a realized split can still carry: an
item that straddles partitions, and an entity whose parts do.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from kleinlib.leakage import audit_index, main


@pytest.fixture
def study(tmp_path: Path) -> Path:
    path = tmp_path / "12-index"
    path.mkdir()
    (path / "study.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 2,
                "study_id": "12-index",
                "task_type": "classification",
                "tracks": {"primary": {"metric": {"name": "val_auc", "goal": "higher"}}},
                "data": {"split": {"kind": "group", "group_column": "group"}},
            }
        ),
        encoding="utf-8",
    )
    return path


def _index(study: Path, rows: list[str], header: str = "id,group,split") -> Path:
    path = study / "index.csv"
    path.write_text(header + "\n" + "\n".join(rows) + "\n", encoding="utf-8")
    return path


def _by_name(checks) -> dict:
    return {c.name: c for c in checks}


CLEAN = [
    "img001,patient_a,train",
    "img002,patient_a,train",
    "img003,patient_b,train",
    "img004,patient_c,development",
    "img005,patient_c,development",
    "img006,patient_d,test",
]


def test_a_clean_index_passes_the_row_three_checks(study: Path) -> None:
    checks = _by_name(audit_index(_index(study, CLEAN), study_dir=study))
    assert all(c.ok for c in checks.values()), [
        (c.name, c.message) for c in checks.values() if not c.ok
    ]
    assert "train=3 development=2 test=1" in checks["index-table"].message
    assert "the index IS the realized split" in checks["index-table"].message
    assert "no id straddles partitions" in checks["duplicate-rows"].message
    assert "4 normalized group ids" in checks["group-overlap"].message


def test_an_id_that_straddles_partitions_is_a_blocker(study: Path) -> None:
    rows = [*CLEAN, "img001,patient_e,test"]
    check = _by_name(audit_index(_index(study, rows), study_dir=study))["duplicate-rows"]
    assert not check.ok
    assert "'img001'" in check.message
    assert "train/test=1" in check.message
    assert "contamination, not skill" in check.message


def test_a_dirty_key_still_counts_as_the_same_item(study: Path) -> None:
    """`strip().casefold()` — the leak a by-construction split cannot see."""
    rows = [*CLEAN, " IMG001 ,patient_e,test"]
    check = _by_name(audit_index(_index(study, rows), study_dir=study))["duplicate-rows"]
    assert not check.ok
    assert "'img001'" in check.message


def test_a_group_crossing_partitions_is_a_blocker(study: Path) -> None:
    rows = [*CLEAN, "img007,PATIENT_A ,test"]
    check = _by_name(audit_index(_index(study, rows), study_dir=study))["group-overlap"]
    assert not check.ok
    assert "'patient_a'" in check.message
    assert "leaks across the split" in check.message


def test_a_repeat_inside_one_partition_is_reported_but_not_a_blocker(study: Path) -> None:
    rows = [*CLEAN, "img001,patient_a,train"]
    check = _by_name(audit_index(_index(study, rows), study_dir=study))["duplicate-rows"]
    assert check.ok
    assert "1 repeated id(s) inside a single partition" in check.message


def test_an_index_without_a_group_column_reports_group_overlap_na(study: Path) -> None:
    rows = ["a,train", "b,train", "c,development", "d,test"]
    checks = _by_name(
        audit_index(_index(study, rows, header="id,split"), study_dir=study)
    )
    assert checks["group-overlap"].ok
    assert "declares no group column" in checks["group-overlap"].message


# --------------------------------------------------------------------------
# structure
# --------------------------------------------------------------------------


def test_a_missing_required_column_stops_the_audit(study: Path) -> None:
    checks = audit_index(
        _index(study, ["a,train", "b,test"], header="item,split"), study_dir=study
    )
    assert len(checks) == 1
    assert not checks[0].ok
    assert "missing required column(s) ['id']" in checks[0].message
    assert "['group', 'time']" in checks[0].message


def test_an_unknown_split_label_is_refused(study: Path) -> None:
    checks = audit_index(
        _index(study, ["a,g,train", "b,g,valid", "c,g,test"]), study_dir=study
    )
    assert not checks[0].ok
    assert "unknown split label(s) ['valid']" in checks[0].message
    assert "['train', 'development', 'test']" in checks[0].message


def test_a_single_partition_index_cannot_show_contamination(study: Path) -> None:
    checks = audit_index(_index(study, ["a,g,train", "b,g,train"]), study_dir=study)
    assert not checks[0].ok
    assert "cannot show contamination" in checks[0].message


def test_an_empty_id_is_refused(study: Path) -> None:
    checks = audit_index(
        _index(study, ["a,g,train", " ,g,development", "c,g,test"]), study_dir=study
    )
    assert not checks[0].ok
    assert "empty id" in checks[0].message


# --------------------------------------------------------------------------
# time
# --------------------------------------------------------------------------


def _time_study(study: Path, kind: str) -> Path:
    contract = yaml.safe_load((study / "study.yaml").read_text(encoding="utf-8"))
    contract["data"]["split"] = {"kind": kind, "time_column": "time"}
    (study / "study.yaml").write_text(yaml.safe_dump(contract), encoding="utf-8")
    return study


ORDERED = [
    "a,g1,2020-01-01,train",
    "b,g2,2020-02-01,train",
    "c,g3,2020-06-01,development",
    "d,g4,2020-12-01,test",
]


def test_a_time_split_whose_partitions_are_ordered_passes(study: Path) -> None:
    _time_study(study, "time")
    checks = _by_name(
        audit_index(
            _index(study, ORDERED, header="id,group,time,split"), study_dir=study
        )
    )
    assert checks["time-order"].ok
    assert "partitions are ordered in time" in checks["time-order"].message


def test_a_time_split_that_looks_ahead_is_a_blocker(study: Path) -> None:
    _time_study(study, "time")
    rows = list(ORDERED)
    rows[1] = "b,g2,2020-09-01,train"  # train now ends after development starts
    check = _by_name(
        audit_index(_index(study, rows, header="id,group,time,split"), study_dir=study)
    )["time-order"]
    assert not check.ok
    assert "must not look ahead" in check.message


def test_a_non_time_split_only_reports_the_ranges(study: Path) -> None:
    """A random or stratified split legitimately interleaves times."""
    rows = list(ORDERED)
    rows[1] = "b,g2,2020-09-01,train"
    check = _by_name(
        audit_index(_index(study, rows, header="id,group,time,split"), study_dir=study)
    )["time-order"]
    assert check.ok
    assert "observed time ranges" in check.message
    assert "does not require ordering" in check.message


def test_numeric_time_values_work_too(study: Path) -> None:
    _time_study(study, "time")
    rows = ["a,g1,1,train", "b,g2,2,train", "c,g3,3,development", "d,g4,4,test"]
    check = _by_name(
        audit_index(_index(study, rows, header="id,group,time,split"), study_dir=study)
    )["time-order"]
    assert check.ok


def test_an_unparseable_time_column_fails_the_lookahead_row(study: Path) -> None:
    _time_study(study, "time")
    rows = ["a,g1,soon,train", "b,g2,later,train", "c,g3,3,development", "d,g4,4,test"]
    check = _by_name(
        audit_index(_index(study, rows, header="id,group,time,split"), study_dir=study)
    )["time-order"]
    assert not check.ok
    assert "neither numeric nor parseable timestamps" in check.message


def test_no_time_column_reports_na(study: Path) -> None:
    check = _by_name(audit_index(_index(study, CLEAN), study_dir=study))["time-order"]
    assert check.ok
    assert "declares no time column" in check.message


# --------------------------------------------------------------------------
# row 4 and the CLI
# --------------------------------------------------------------------------


def test_row_four_reports_na_with_the_index_reason_but_metric_direction_runs(
    study: Path,
) -> None:
    checks = _by_name(audit_index(_index(study, CLEAN), study_dir=study))
    assert checks["metric-direction[primary]"].ok
    assert "matches the canonical registry" in checks["metric-direction[primary]"].message
    chance = checks["chance-level[primary]"]
    assert chance.ok
    assert "index-table mode carries no target or features" in chance.message


def test_cli_index_mode_prints_the_lines_and_exits_zero(study: Path, capsys) -> None:
    index = _index(study, CLEAN)
    assert main(["--index", str(index), "--study", str(study)]) == 0
    out = capsys.readouterr().out
    assert "[OK]   duplicate-rows:" in out
    assert "[OK]   group-overlap:" in out
    assert "checks passed: clean" in out


def test_cli_index_mode_exits_one_on_a_blocker(study: Path, capsys) -> None:
    index = _index(study, [*CLEAN, "img001,patient_e,test"])
    assert main(["--index", str(index), "--study", str(study)]) == 1
    out = capsys.readouterr().out
    assert "[FAIL] duplicate-rows:" in out
    assert "BLOCKER at the DATA gate" in out


def test_cli_refuses_both_modes_at_once(study: Path) -> None:
    index = _index(study, CLEAN)
    with pytest.raises(SystemExit):
        main([str(index), "--index", str(index), "--study", str(study)])


def test_cli_refuses_neither_mode(study: Path) -> None:
    with pytest.raises(SystemExit):
        main(["--study", str(study)])


def test_cli_dataframe_mode_still_requires_a_target(study: Path) -> None:
    with pytest.raises(SystemExit):
        main(["prepared.csv", "--study", str(study)])
