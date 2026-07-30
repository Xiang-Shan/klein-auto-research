"""Tests for kleinlib.leakage: the clean-room split & eval-harness audit."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from kleinlib.data import three_way_split
from kleinlib.leakage import audit_split, main

STUDY_YAML = """\
schema_version: 2
study_id: "99-audit-fixture"
task_type: classification
max_run_seconds: 60
tracks:
  primary:
    metric: {name: val_auc, goal: higher, minimum_delta: 0.002}
    guardrails: {}
data:
  source: "csv:prepared.csv"
  prepared_path: "prepared.csv"
  split:
    kind: stratified
    seed: 42
    development_size: 0.2
    test_size: 0.2
phases:
  - {id: adaptive-1, budget_seconds: 600, max_experiments: 4}
  - {id: confirmation, budget_seconds: 600, max_experiments: 1}
"""

STRATIFIED_SPLIT = """\
    kind: stratified
    seed: 42
    development_size: 0.2
    test_size: 0.2
"""

GROUP_SPLIT = """\
    kind: group
    seed: 42
    development_size: 0.25
    test_size: 0.25
    group_column: account
"""


def _make_frame(n: int = 600, seed: int = 7) -> pd.DataFrame:
    """Tiny deterministic binary-classification frame with unique float rows."""
    rng = np.random.default_rng(seed)
    x1 = rng.normal(size=n).round(6)
    x2 = rng.normal(size=n).round(6)
    y = (rng.random(n) < 1.0 / (1.0 + np.exp(-(0.8 * x1 - 0.5 * x2)))).astype(int)
    return pd.DataFrame({"x1": x1, "x2": x2, "claim": y})


def _write_fixture(tmp_path, df: pd.DataFrame, yaml_text: str = STUDY_YAML):
    study = tmp_path / "99-audit-fixture"
    study.mkdir()
    (study / "study.yaml").write_text(yaml_text, encoding="utf-8")
    prepared = tmp_path / "prepared.csv"
    df.to_csv(prepared, index=False)
    return prepared, study


def _plant_dev_test_duplicate(df: pd.DataFrame) -> pd.DataFrame:
    """Copy one development row's features over a same-label test row.

    The split depends only on y and the seed, so the plant cannot move the
    partitions it is meant to contaminate.
    """
    X, y = df.drop(columns=["claim"]), df["claim"]
    _, X_dev, X_te, _, _, _ = three_way_split(
        X, y, task="classification", strategy="stratified",
        development_size=0.2, test_size=0.2, seed=42,
    )
    dev_pos = int(X_dev.index[0])
    label = int(y.iloc[dev_pos])
    te_pos = next(int(p) for p in X_te.index if int(y.iloc[int(p)]) == label)
    df.loc[te_pos, ["x1", "x2"]] = df.loc[dev_pos, ["x1", "x2"]].to_numpy()
    return df


def test_clean_fixture_passes(tmp_path):
    prepared, study = _write_fixture(tmp_path, _make_frame())
    checks = audit_split(prepared, target="claim", study_dir=study)
    assert all(c.ok for c in checks), [(c.name, c.message) for c in checks]
    names = {c.name for c in checks}
    assert {"split-reproduces", "duplicate-rows", "group-overlap",
            "metric-direction[primary]", "constant-chance[primary]",
            "shuffled-chance[primary]"} == names


def test_planted_duplicate_straddling_dev_test_detected_with_count(tmp_path):
    prepared, study = _write_fixture(tmp_path, _plant_dev_test_duplicate(_make_frame()))
    checks = {c.name: c for c in audit_split(prepared, target="claim", study_dir=study)}
    assert checks["split-reproduces"].ok  # the plant must not disturb the split itself
    duplicate = checks["duplicate-rows"]
    assert not duplicate.ok
    assert duplicate.message.startswith("1 duplicated row-content hash")
    assert "development/test=1" in duplicate.message


def test_group_overlap_detected_for_dirty_twin_ids(tmp_path):
    rng = np.random.default_rng(3)
    rows = []
    for g in range(8):  # every group id has a dirty twin: "g3" vs "G3 "
        rows.extend((f"g{g}", round(rng.normal(), 6), i % 2) for i in range(6))
        rows.extend((f"G{g} ", round(rng.normal(), 6), (i + 1) % 2) for i in range(6))
    df = pd.DataFrame(rows, columns=["account", "x1", "claim"])
    prepared, study = _write_fixture(
        tmp_path, df, STUDY_YAML.replace(STRATIFIED_SPLIT, GROUP_SPLIT)
    )
    checks = {c.name: c for c in audit_split(prepared, target="claim", study_dir=study)}
    assert checks["split-reproduces"].ok  # raw ids split cleanly by construction
    overlap = checks["group-overlap"]
    assert not overlap.ok
    assert "normalized group id(s) cross partitions" in overlap.message
    assert "'g0'" in overlap.message  # names the colliding entity


def test_chance_check_flags_leaky_shuffled_predictor(tmp_path):
    df = _make_frame()
    prepared, study = _write_fixture(tmp_path, df)

    def leaky_predictor(X_tr, y_shuffled, X_dev):
        # A broken harness: "predictions" are the true development labels.
        return df.loc[X_dev.index, "claim"].to_numpy(dtype=float)

    checks = {
        c.name: c
        for c in audit_split(
            prepared, target="claim", study_dir=study, shuffled_predictor=leaky_predictor
        )
    }
    assert checks["constant-chance[primary]"].ok  # the constant anchor stays at 0.5
    leaked = checks["shuffled-chance[primary]"]
    assert not leaked.ok
    assert "val_auc=1.0000" in leaked.message
    assert "leaking labels" in leaked.message


def test_missing_split_column_is_a_single_reproduce_failure(tmp_path):
    df = _make_frame(n=60)  # no "account" column in the artifact
    prepared, study = _write_fixture(
        tmp_path, df, STUDY_YAML.replace(STRATIFIED_SPLIT, GROUP_SPLIT)
    )
    checks = audit_split(prepared, target="claim", study_dir=study)
    assert [c.name for c in checks] == ["split-reproduces"]
    assert not checks[0].ok
    assert "group_column" in checks[0].message


def test_cli_marker_lines_and_exit_codes(tmp_path, capsys):
    prepared, study = _write_fixture(tmp_path, _make_frame())
    assert main([str(prepared), "--target", "claim", "--study", str(study)]) == 0
    out = capsys.readouterr().out
    assert "[OK]   split-reproduces:" in out
    assert "[FAIL]" not in out
    assert "6/6 checks passed: clean" in out

    dirty = tmp_path / "dirty"
    dirty.mkdir()
    prepared2, study2 = _write_fixture(dirty, _plant_dev_test_duplicate(_make_frame()))
    assert main([str(prepared2), "--target", "claim", "--study", str(study2)]) == 1
    out = capsys.readouterr().out
    assert "[FAIL] duplicate-rows:" in out
    assert "BLOCKER at the DATA gate" in out


def test_bad_chance_margin_raises(tmp_path):
    prepared, study = _write_fixture(tmp_path, _make_frame(n=60))
    with pytest.raises(ValueError, match="chance_margin"):
        audit_split(prepared, target="claim", study_dir=study, chance_margin=1.5)
