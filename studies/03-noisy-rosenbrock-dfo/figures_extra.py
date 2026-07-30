"""Zoomed decision trajectory: the frontier story without the divergence dots.

The full-range figure (log scale) is the honest record; this companion zooms to
gaps < 10 so the anchor→restarts step and the bands are readable. Both appear
in the tutorial, cross-referenced — never the zoom alone.
"""

from __future__ import annotations

from pathlib import Path

from kleinlib.figures import plot_decision_trajectory
from kleinlib.workflow import load_contract, load_manifests, normalize_tracks

STUDY = Path(".")


def main() -> None:
    manifests = [
        m for m in load_manifests(STUDY)
        if m.get("primary_metric") is None or float(m["primary_metric"]) < 10.0
    ]
    metric = normalize_tracks(load_contract(STUDY))["primary"]["metric"]
    path = plot_decision_trajectory(
        manifests, ".", track="primary", metric_goal="lower",
        metric_name=f"{metric['name']} (zoom < 10; divergent discards excluded — see full-range figure)",
        minimum_delta=metric.get("minimum_delta"),
        noise_floor_std=(metric.get("noise_floor") or {}).get("std"),
        name="plot_decision_trajectory_zoom",
    )
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
