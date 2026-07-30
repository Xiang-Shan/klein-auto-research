#!/usr/bin/env python3
"""Regenerate a Klein study's figures from results.tsv + saved predictions.

Usage:
    uv run python .claude/skills/klein/scripts/make_figures.py <study_dir> \
        [--kind binary|regression]

Run from the klein-auto-research repo root so `uv run` resolves this
project's environment (kleinlib is importable directly, no path hacking).

`kleinlib.eval.evaluate()`/`evaluate_regression()` already print every
number these figures visualize and write `aux_metrics.tsv` during the normal
experiment loop, so regenerating figures is normally unnecessary — reach for
this script only for a synthesis/tutorial pass, or if a PNG was deleted or
edited by hand outside the loop.

Schema-v2 studies (`runs/*/manifest.json` present) additionally get one
decision trajectory per study.yaml track
(`figures/plot_decision_trajectory__<track>.png`); v1 studies keep the plain
metric trajectory only.

Predictions contract (optional, beyond the always-available trajectory):
`<study_dir>/models/latest_val_preds.npz` with keys `y_true` + `proba`
(binary) or `y_true` + `y_pred` (regression) — a train.py can `np.savez`
this itself if it wants the standard figure set regenerated later.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np

from kleinlib import figures, workflow


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("study_dir", type=Path)
    parser.add_argument("--kind", choices=["binary", "regression"], default=None)
    args = parser.parse_args()

    results_path = args.study_dir / "results.tsv"
    if results_path.exists():
        with results_path.open(newline="") as f:
            rows = list(csv.DictReader(f, delimiter="\t"))
        if rows:
            path = figures.plot_metric_trajectory(rows, args.study_dir)
            print(f"wrote {path}")
    else:
        print(f"no results.tsv under {args.study_dir}, skipping trajectory")

    try:
        manifests = workflow.load_manifests(args.study_dir)
        tracks = workflow.normalize_tracks(workflow.load_contract(args.study_dir)) if manifests else {}
    except workflow.WorkflowError as exc:
        manifests, tracks = [], {}
        print(f"skipping decision trajectories: {exc}")
    for track, spec in tracks.items():
        metric = spec.get("metric", {})
        path = figures.plot_decision_trajectory(
            manifests,
            args.study_dir,
            track=track,
            metric_goal=str(metric.get("goal") or "higher"),
            metric_name=metric.get("name"),
            minimum_delta=metric.get("minimum_delta") or None,
            name=f"plot_decision_trajectory__{track}",
        )
        print(f"wrote {path}")

    preds_path = args.study_dir / "models" / "latest_val_preds.npz"
    if not preds_path.exists():
        print(f"no {preds_path} found, skipping standard figure set")
        return

    saved = np.load(preds_path)
    y_true = saved["y_true"]
    is_regression = args.kind == "regression" or (args.kind is None and "y_pred" in saved)
    if is_regression:
        paths = figures.standard_regression_report(y_true, saved["y_pred"], args.study_dir)
    else:
        paths = figures.standard_binary_report(y_true, saved["proba"], args.study_dir)
    for name, path in paths.items():
        print(f"wrote {name} -> {path}")


if __name__ == "__main__":
    main()
