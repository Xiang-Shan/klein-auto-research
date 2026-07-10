"""Tests for kleinlib.snapshot: best-model manifest bookkeeping."""

from __future__ import annotations

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
