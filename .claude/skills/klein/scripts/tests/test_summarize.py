"""Ported unit tests for summarize_results.py (source: agent-smith /
the ancestor skill's scripts/tests/test_summarize.py, identical in both).

The shuffled-header case is the load-bearing one: results.tsv parsing must
follow header names, never column positions, so a future schema change can
never silently mis-assign fields. Adapted from unittest to pytest with
tmp_path fixtures per this repo's test conventions.
"""

from __future__ import annotations

from pathlib import Path

import pytest

CANONICAL = (
    "experiment\tval_auc\tstatus\tcommit\tdescription\n"
    "1\t0.625464\tkeep\tabc1234\tbaseline logistic\n"
    "2\t0.610000\tdiscard\t\tweaker family probe\n"
    "3\t\tcrash\t\ttimeout at budget\n"
    "4\t0.669402\tkeep\tdef5678\thgb blend\n"
)

# Same rows with the columns deliberately reordered: values must land in the
# same fields regardless.
SHUFFLED = (
    "description\tcommit\tstatus\tval_auc\texperiment\n"
    "baseline logistic\tabc1234\tkeep\t0.625464\t1\n"
    "weaker family probe\t\tdiscard\t0.610000\t2\n"
    "timeout at budget\t\tcrash\t\t3\n"
    "hgb blend\tdef5678\tkeep\t0.669402\t4\n"
)


def write_tsv(tmp_path: Path, content: str, name: str = "results.tsv") -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


class TestMetricDetection:
    def test_known_metric_column_found_by_name(self, summarize_module):
        header = ["experiment", "val_auc", "status", "commit", "description"]
        assert summarize_module.pick_metric_column(header, None) == "val_auc"

    def test_explicit_metric_column_must_exist(self, summarize_module):
        with pytest.raises(ValueError):
            summarize_module.pick_metric_column(["experiment", "val_auc", "status"], "val_gini")

    def test_fallback_never_picks_experiment_column(self, summarize_module):
        # An unlisted metric name in the canonical schema must win the
        # fallback — not the experiment counter.
        header = ["experiment", "val_gini", "status", "commit", "description"]
        assert summarize_module.pick_metric_column(header, None) == "val_gini"

    def test_goal_inference(self, summarize_module):
        assert summarize_module.infer_goal("val_auc", None) == "higher"
        assert summarize_module.infer_goal("val_loss", None) == "lower"
        assert summarize_module.infer_goal("rmse", None) == "lower"
        assert summarize_module.infer_goal("anything", "lower") == "lower"

    def test_goal_inference_recognizes_brier_and_logloss(self, summarize_module):
        # Restoring rigor: brier/logloss are lower-is-better aux metrics
        # this project's eval.py sidecar writes (see kleinlib/schema.py
        # docstring); the generic heuristic must get these right too, not
        # just the results.tsv metric-column names the source list covered.
        assert summarize_module.infer_goal("val_brier", None) == "lower"
        assert summarize_module.infer_goal("val_logloss", None) == "lower"
        assert summarize_module.infer_goal("log_loss", None) == "lower"


class TestHeaderBasedParsing:
    def test_canonical_and_shuffled_parse_identically(self, summarize_module, tmp_path):
        for i, content in enumerate((CANONICAL, SHUFFLED)):
            path = write_tsv(tmp_path, content, name=f"results_{i}.tsv")
            _, rows = summarize_module.read_results(path, "val_auc")
            assert [r.metric for r in rows] == [0.625464, 0.61, None, 0.669402]
            assert [r.status for r in rows] == ["keep", "discard", "crash", "keep"]
            assert [r.commit for r in rows] == ["abc1234", "", "", "def5678"]
            assert [r.experiment_num for r in rows] == [1, 2, 3, 4]


class TestSummary:
    def test_frontier_baseline_best_improvement(self, summarize_module, tmp_path):
        path = write_tsv(tmp_path, CANONICAL)
        _, rows = summarize_module.read_results(path, "val_auc")
        frontier = summarize_module.running_frontier(rows, "higher")
        # crash row and the non-improving discard are excluded
        assert [r.row_number for r in frontier] == [1, 4]
        summary = summarize_module.build_summary(path, "val_auc", "higher", rows)
        assert "- keep: 2" in summary
        assert "- discard: 1" in summary
        assert "- crash: 1" in summary
        assert "- baseline metric: 0.625464" in summary
        assert "- best metric: 0.669402" in summary
        assert "- total improvement: 0.043938" in summary

    def test_lower_is_better_frontier(self, summarize_module, tmp_path):
        content = (
            "experiment\tval_rmse\tstatus\tcommit\tdescription\n"
            "1\t55.0\tkeep\taaa1111\tbaseline linear\n"
            "2\t58.2\tdiscard\t\tworse probe\n"
            "3\t52.7\tkeep\tbbb2222\tridge sweep\n"
        )
        path = write_tsv(tmp_path, content)
        _, rows = summarize_module.read_results(path, "val_rmse")
        frontier = summarize_module.running_frontier(rows, "lower")
        assert [r.row_number for r in frontier] == [1, 3]
