"""Tests for kleinlib.snapshot: best-model manifest bookkeeping."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from kleinlib import snapshot


class _TinyModel:
    def __init__(self, tag: str) -> None:
        self.tag = tag


def test_manifest_created_on_first_save(tmp_path):
    assert snapshot.read_current_best(tmp_path) is None

    path = snapshot.maybe_save_best(
        _TinyModel("a"),
        exp_id=1,
        metric_value=0.60,
        metric_goal="higher",
        study_dir=tmp_path,
        primary_name="val_auc",
    )
    assert path is not None

    manifest = tmp_path / "models" / snapshot.MANIFEST_NAME
    assert manifest.exists()
    header = manifest.read_text().splitlines()[0]
    assert header == "\t".join(snapshot.MANIFEST_COLUMNS)

    current = snapshot.read_current_best(tmp_path)
    assert current is not None
    assert current.metric == 0.60
    assert current.experiment == "1"
    assert current.primary_name == "val_auc"
    assert current.metric_goal == "higher"
    assert len(current.sha256) == 64
    assert not Path(current.path).is_absolute()


def test_better_metric_replaces_best(tmp_path):
    snapshot.maybe_save_best(
        _TinyModel("a"), exp_id=1, metric_value=0.60, metric_goal="higher",
        study_dir=tmp_path, primary_name="val_auc",
    )
    path2 = snapshot.maybe_save_best(
        _TinyModel("b"), exp_id=2, metric_value=0.65, metric_goal="higher",
        study_dir=tmp_path, primary_name="val_auc",
    )
    assert path2 is not None

    current = snapshot.read_current_best(tmp_path)
    assert current.metric == 0.65
    assert current.experiment == "2"

    loaded = snapshot.load_best(tmp_path)
    assert loaded.tag == "b"


def test_worse_metric_does_not_replace_best(tmp_path):
    snapshot.maybe_save_best(
        _TinyModel("a"), exp_id=1, metric_value=0.60, metric_goal="higher",
        study_dir=tmp_path, primary_name="val_auc",
    )
    path3 = snapshot.maybe_save_best(
        _TinyModel("c"), exp_id=3, metric_value=0.55, metric_goal="higher",
        study_dir=tmp_path, primary_name="val_auc",
    )
    assert path3 is None

    current = snapshot.read_current_best(tmp_path)
    assert current.metric == 0.60
    assert current.experiment == "1"

    loaded = snapshot.load_best(tmp_path)
    assert loaded.tag == "a"


def test_lower_goal_prefers_smaller_metric(tmp_path):
    snapshot.maybe_save_best(
        _TinyModel("a"), exp_id=1, metric_value=10.0, metric_goal="lower",
        study_dir=tmp_path, primary_name="val_rmse",
    )
    better = snapshot.maybe_save_best(
        _TinyModel("b"), exp_id=2, metric_value=5.0, metric_goal="lower",
        study_dir=tmp_path, primary_name="val_rmse",
    )
    worse = snapshot.maybe_save_best(
        _TinyModel("c"), exp_id=3, metric_value=8.0, metric_goal="lower",
        study_dir=tmp_path, primary_name="val_rmse",
    )
    assert better is not None
    assert worse is None
    assert snapshot.read_current_best(tmp_path).metric == 5.0


def test_snapshot_names_do_not_collide_at_four_decimal_places(tmp_path):
    first = snapshot.maybe_save_best(
        _TinyModel("a"), exp_id=1, metric_value=0.60001, metric_goal="higher",
        study_dir=tmp_path, primary_name="val_auc",
    )
    second = snapshot.maybe_save_best(
        _TinyModel("b"), exp_id=1, metric_value=0.60002, metric_goal="higher",
        study_dir=tmp_path, primary_name="val_auc",
    )
    assert first != second
    assert snapshot._resolve_path(tmp_path, first).exists()
    assert snapshot._resolve_path(tmp_path, second).exists()


def test_snapshot_manifest_is_relocatable(tmp_path):
    original = tmp_path / "original"
    moved = tmp_path / "moved"
    snapshot.maybe_save_best(
        _TinyModel("portable"), exp_id=1, metric_value=0.7, metric_goal="higher",
        study_dir=original, primary_name="val_auc",
    )
    shutil.copytree(original, moved)
    assert snapshot.load_best(moved).tag == "portable"


def test_missing_snapshot_can_be_reported_and_rebuilt(tmp_path):
    recorded = snapshot.maybe_save_best(
        _TinyModel("a"), exp_id=1, metric_value=0.7, metric_goal="higher",
        study_dir=tmp_path, primary_name="val_auc",
    )
    snapshot._resolve_path(tmp_path, recorded).unlink()
    status = snapshot.snapshot_status(tmp_path)
    assert status.available is False
    assert "missing" in status.reason
    with pytest.raises(FileNotFoundError, match="rebuild_missing"):
        snapshot.load_best(tmp_path)

    rebuilt = snapshot.rebuild_missing(_TinyModel("rebuilt"), tmp_path)
    assert snapshot._resolve_path(tmp_path, rebuilt).exists()
    assert snapshot.load_best(tmp_path).tag == "rebuilt"


def test_snapshot_detects_hash_mismatch(tmp_path):
    recorded = snapshot.maybe_save_best(
        _TinyModel("a"), exp_id=1, metric_value=0.7, metric_goal="higher",
        study_dir=tmp_path, primary_name="val_auc",
    )
    snapshot._resolve_path(tmp_path, recorded).write_bytes(b"not a joblib model")
    status = snapshot.snapshot_status(tmp_path)
    assert status.hash_matches is False
    with pytest.raises(OSError, match="SHA-256"):
        snapshot.load_best(tmp_path)


def test_snapshot_rejects_metric_contract_changes_and_nonfinite_values(tmp_path):
    snapshot.maybe_save_best(
        _TinyModel("a"), exp_id=1, metric_value=0.7, metric_goal="higher",
        study_dir=tmp_path, primary_name="val_auc",
    )
    with pytest.raises(ValueError, match="metric changed"):
        snapshot.maybe_save_best(
            _TinyModel("b"), exp_id=2, metric_value=0.2, metric_goal="lower",
            study_dir=tmp_path, primary_name="val_logloss",
        )
    with pytest.raises(ValueError, match="finite"):
        snapshot.maybe_save_best(
            _TinyModel("c"), exp_id=3, metric_value=float("nan"),
            metric_goal="higher", study_dir=tmp_path, primary_name="val_auc",
        )


def test_snapshot_frontiers_are_track_specific(tmp_path):
    snapshot.maybe_save_best(
        _TinyModel("rank-a"), exp_id="E0001", metric_value=0.7,
        metric_goal="higher", study_dir=tmp_path, primary_name="val_auc",
        track="ranking",
    )
    snapshot.maybe_save_best(
        _TinyModel("loss-a"), exp_id="E0002", metric_value=12.0,
        metric_goal="lower", study_dir=tmp_path, primary_name="val_rmse",
        track="severity",
    )
    rank_b = snapshot.maybe_save_best(
        _TinyModel("rank-b"), exp_id="E0003", metric_value=0.8,
        metric_goal="higher", study_dir=tmp_path, primary_name="val_auc",
        track="ranking",
    )

    assert rank_b is not None
    assert snapshot.read_current_best(tmp_path, track="ranking").metric == 0.8
    assert snapshot.read_current_best(tmp_path, track="severity").metric == 12.0
    assert snapshot.load_best(tmp_path, track="ranking").tag == "rank-b"
    assert snapshot.load_best(tmp_path, track="severity").tag == "loss-a"
