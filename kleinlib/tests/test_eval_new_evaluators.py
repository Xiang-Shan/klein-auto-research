"""The three registered-cell evaluators: estimate, test, and table.

`references/registered-mode.md` fixes what a cell prints; the notary parses
that block and a registered prediction's rule reads a key out of it, so these
tests pin the LINES, not just the return values.
"""

from __future__ import annotations

import re

import pytest

from kleinlib import eval as klein_eval
from kleinlib import schema
from kleinlib.decision import parse_metric_log


def _block(capsys) -> str:
    return capsys.readouterr().out


def _parsed(tmp_path, text: str):
    """Run the printed block through the notary's own parser."""
    log = tmp_path / "run.log"
    log.write_text(text, encoding="utf-8")
    return parse_metric_log(log)


# --------------------------------------------------------------------------
# evaluate_estimate
# --------------------------------------------------------------------------


def test_estimate_prints_the_cell_block_from_the_protocol(capsys) -> None:
    result = klein_eval.evaluate_estimate(
        454.16,
        336.4,
        571.9,
        24,
        exp_id=2,
        metric_name="k_kms_per_mpc",
        metric_goal="lower",
    )
    assert result == 454.16
    out = _block(capsys)
    assert out.splitlines()[0] == "---"
    assert "primary_metric:    454.160000" in out
    assert "ci_low:            336.400000" in out
    assert "ci_high:           571.900000" in out
    assert "n:                 24" in out
    assert "--- aux_metrics ---" in out


def test_estimate_keys_reach_a_registered_rule_through_the_notary(tmp_path, capsys) -> None:
    klein_eval.evaluate_estimate(
        454.16, 336.4, 571.9, 24, exp_id=2, metric_name="k", metric_goal="lower"
    )
    primary, name, goal, metrics = _parsed(tmp_path, _block(capsys))
    assert (primary, name, goal) == (454.16, "k", "lower")
    # P4 of the protocol's worked example: "ci_low exceeds 70".
    assert metrics["ci_low"] == 336.4
    assert metrics["ci_high"] == 571.9
    assert metrics["n"] == 24.0


def test_estimate_refuses_an_interval_that_excludes_its_own_point() -> None:
    with pytest.raises(ValueError, match="outside its own interval"):
        klein_eval.evaluate_estimate(
            1.0, 2.0, 3.0, 10, exp_id=1, metric_name="m", metric_goal="lower"
        )


def test_estimate_refuses_an_inverted_interval() -> None:
    with pytest.raises(ValueError, match="must not exceed"):
        klein_eval.evaluate_estimate(
            2.0, 3.0, 1.0, 10, exp_id=1, metric_name="m", metric_goal="lower"
        )


def test_estimate_refuses_a_non_finite_bound() -> None:
    with pytest.raises(ValueError, match="ci_high must be finite"):
        klein_eval.evaluate_estimate(
            1.0, 0.0, float("inf"), 10, exp_id=1, metric_name="m", metric_goal="lower"
        )


# --------------------------------------------------------------------------
# evaluate_test
# --------------------------------------------------------------------------


def test_test_cell_makes_the_p_value_the_ledger_scalar(capsys) -> None:
    result = klein_eval.evaluate_test(
        2.31, 0.021, 0.043, 150, 42, exp_id=3, metric_name="p_adj", metric_goal="lower"
    )
    assert result == 0.021
    out = _block(capsys)
    assert "primary_metric:    0.021000" in out
    assert "stat:              2.310000" in out
    assert "effect:            0.043000" in out
    assert "n_comparisons:     42" in out


def test_bonferroni_alpha_is_printed_from_the_declared_family_size(capsys) -> None:
    klein_eval.evaluate_test(
        1.0, 0.5, 0.1, 20, 4, exp_id=3, metric_name="p", metric_goal="lower"
    )
    assert "bonferroni_alpha:  0.0125" in _block(capsys)

    klein_eval.evaluate_test(
        1.0, 0.5, 0.1, 20, 4, alpha=0.01, exp_id=3, metric_name="p", metric_goal="lower"
    )
    assert "bonferroni_alpha:  0.0025" in _block(capsys)


def test_a_family_above_one_names_the_sharper_instrument(capsys) -> None:
    """Lesson 6: Bonferroni is the crude bar; the max-t guard is the instrument."""
    klein_eval.evaluate_test(
        1.0, 0.5, 0.1, 20, 42, exp_id=3, metric_name="p", metric_goal="lower"
    )
    out = _block(capsys)
    assert "family_maxt" in out
    assert "selection guard, not a significance test" in out
    # A comment line, so the notary's parser never sees it as a metric.
    assert [line for line in out.splitlines() if "family_maxt" in line][0].startswith("#")

    klein_eval.evaluate_test(
        1.0, 0.5, 0.1, 20, 1, exp_id=3, metric_name="p", metric_goal="lower"
    )
    assert "family_maxt" not in _block(capsys)


def test_a_non_finite_statistic_prints_NA_instead_of_aborting_the_run(
    tmp_path, capsys
) -> None:
    """An infinite t on a zero-spread cell is real; a non-finite line is fatal."""
    klein_eval.evaluate_test(
        float("inf"), 0.0, None, 8, 1, exp_id=3, metric_name="p", metric_goal="lower"
    )
    out = _block(capsys)
    assert "stat:              NA" in out
    assert "effect:            NA" in out
    _, _, _, metrics = _parsed(tmp_path, out)  # would raise on a non-finite line
    assert "stat" not in metrics and "effect" not in metrics


def test_test_cell_refuses_an_impossible_p_value_or_family() -> None:
    with pytest.raises(ValueError, match=r"p_value must lie in \[0, 1\]"):
        klein_eval.evaluate_test(
            1.0, 1.5, 0.1, 10, 1, exp_id=3, metric_name="p", metric_goal="lower"
        )
    with pytest.raises(ValueError, match="n_comparisons must be >= 1"):
        klein_eval.evaluate_test(
            1.0, 0.5, 0.1, 10, 0, exp_id=3, metric_name="p", metric_goal="lower"
        )
    with pytest.raises(ValueError, match=r"alpha must lie in \(0, 1\)"):
        klein_eval.evaluate_test(
            1.0, 0.5, 0.1, 10, 1, alpha=1.0, exp_id=3, metric_name="p", metric_goal="lower"
        )


# --------------------------------------------------------------------------
# evaluate_table
# --------------------------------------------------------------------------


def _table(study, rows: int = 3):
    path = study / "sweeps" / "rq0_map.tsv"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("family\trung\n" + "".join(f"f{i}\t{i}\n" for i in range(rows)))
    return path


def test_table_cell_pins_its_artifact_with_rows_and_sha256(tmp_path, capsys) -> None:
    _table(tmp_path, rows=42)
    result = klein_eval.evaluate_table(
        "sweeps/rq0_map.tsv",
        3,
        exp_id=2,
        metric_name="cells_with_permission",
        metric_goal="lower",
        study_dir=tmp_path,
    )
    assert result == 3.0
    out = _block(capsys)
    assert "artifact: sweeps/rq0_map.tsv" in out
    assert "rows:              42" in out
    assert re.search(r"^sha256:            [0-9a-f]{64}$", out, re.MULTILINE)


def test_table_path_is_printed_study_relative_and_posix(tmp_path, capsys) -> None:
    table = _table(tmp_path)
    klein_eval.evaluate_table(
        table, 1, exp_id=2, metric_name="m", metric_goal="lower", study_dir=tmp_path
    )
    assert "artifact: sweeps/rq0_map.tsv" in _block(capsys)


def test_table_refuses_an_artifact_outside_the_study(tmp_path) -> None:
    outside = tmp_path.parent / "elsewhere.tsv"
    outside.write_text("a\n1\n")
    study = tmp_path / "study"
    study.mkdir()
    with pytest.raises(ValueError, match="escapes the study directory"):
        klein_eval.evaluate_table(
            outside, 1, exp_id=2, metric_name="m", metric_goal="lower", study_dir=study
        )


def test_a_cell_that_never_wrote_its_table_has_not_measured_anything(tmp_path) -> None:
    with pytest.raises(FileNotFoundError, match="has not measured anything"):
        klein_eval.evaluate_table(
            "sweeps/missing.tsv",
            1,
            exp_id=2,
            metric_name="m",
            metric_goal="lower",
            study_dir=tmp_path,
        )


def test_rows_may_be_declared_for_a_non_delimited_artifact(tmp_path, capsys) -> None:
    blob = tmp_path / "figures" / "map.png"
    blob.parent.mkdir()
    blob.write_bytes(b"\x89PNG not really")
    klein_eval.evaluate_table(
        "figures/map.png",
        1,
        rows=7,
        exp_id=2,
        metric_name="m",
        metric_goal="lower",
        study_dir=tmp_path,
    )
    out = _block(capsys)
    assert "rows:              7" in out
    assert "artifact: figures/map.png" in out


def test_an_undeclared_non_delimited_artifact_reports_NA_rows(tmp_path, capsys) -> None:
    blob = tmp_path / "notes.md"
    blob.write_text("# hi\n")
    klein_eval.evaluate_table(
        "notes.md", 1, exp_id=2, metric_name="m", metric_goal="lower", study_dir=tmp_path
    )
    assert "rows:              NA" in _block(capsys)


# --------------------------------------------------------------------------
# shared contracts: sidecar, smoke, registry
# --------------------------------------------------------------------------


@pytest.mark.parametrize("evaluator", ["estimate", "test", "table"])
def test_every_cell_evaluator_writes_the_aux_sidecar(tmp_path, evaluator) -> None:
    _call(evaluator, tmp_path)
    lines = (tmp_path / schema.AUX_SIDECAR).read_text().strip().splitlines()
    assert lines[0] == "\t".join(schema.AUX_COLUMNS)
    assert all(line.startswith("9\t") for line in lines[1:])
    assert any(line.split("\t")[1] == "wall_seconds" for line in lines[1:])


@pytest.mark.parametrize("evaluator", ["estimate", "test", "table"])
def test_smoke_mode_prints_the_block_and_writes_nothing(
    tmp_path, monkeypatch, capsys, evaluator
) -> None:
    monkeypatch.setenv("KLEIN_SMOKE", "1")
    _call(evaluator, tmp_path)
    out = _block(capsys)
    assert "primary_metric:" in out
    assert "smoke mode: no sidecar/snapshot writes" in out
    assert not (tmp_path / schema.AUX_SIDECAR).exists()


def test_a_missing_table_under_smoke_is_a_notice_not_a_crash(
    tmp_path, monkeypatch, capsys
) -> None:
    """A smoke run does no work, so it has no table; run-one clears the flag."""
    monkeypatch.setenv("KLEIN_SMOKE", "1")
    klein_eval.evaluate_table(
        "sweeps/missing.tsv",
        1,
        exp_id=9,
        metric_name="m",
        metric_goal="lower",
        study_dir=tmp_path,
    )
    out = _block(capsys)
    assert "sha256:            NA" in out
    assert "rows:              NA" in out


def test_every_printed_key_is_declared_in_the_schema_registry(tmp_path, capsys) -> None:
    """`klein preflight` reads this registry to decide guardrail visibility."""
    for evaluator in ("estimate", "test", "table"):
        _call(evaluator, tmp_path)
        _, _, _, metrics = _parsed(tmp_path, _block(capsys))
        declared = schema.EVALUATOR_PRINTED_KEYS[f"evaluate_{evaluator}"]
        # Every blessed key really is parsed as a number on this evaluator's run.
        assert declared <= set(metrics), (evaluator, declared - set(metrics))
        # And nothing that can print NA or text is blessed: a key that is
        # sometimes missing would make the visibility check a false all-clear.
        assert not declared & {"stat", "effect", "artifact", "sha256"}


def _call(evaluator: str, study):
    if evaluator == "estimate":
        return klein_eval.evaluate_estimate(
            1.0, 0.5, 1.5, 12, exp_id=9, metric_name="m", metric_goal="lower",
            study_dir=study,
        )
    if evaluator == "test":
        return klein_eval.evaluate_test(
            2.0, 0.03, 0.4, 12, 3, exp_id=9, metric_name="m", metric_goal="lower",
            study_dir=study,
        )
    _table(study)
    return klein_eval.evaluate_table(
        "sweeps/rq0_map.tsv", 1.0, exp_id=9, metric_name="m", metric_goal="lower",
        study_dir=study,
    )
