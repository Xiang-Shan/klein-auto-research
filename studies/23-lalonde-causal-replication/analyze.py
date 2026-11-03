"""One registered cell (the mutable surface of study 23).

A cell CHOOSES — the library (lib/lalonde.py) computes. Two tracks:

* `reproduction` — recompute Dehejia & Wahba's Table 3 columns (1)-(2) for the
  lane being evaluated and count the published targets missed by more than the
  registered tolerance. The table of every target is pinned.
* `att` — one propensity-score estimate of the effect of NSW on 1978 earnings,
  using the NSW treated men against the lane's NON-experimental comparison group,
  with a percentile-bootstrap interval; `att_gap_usd` is its distance from the
  experimental estimate computed in the same run from the NSW controls.

Lanes come from the contract's predefined split: development = PSID-1, the sealed
final test = CPS-1. The notary sets KLEIN_EVALUATION_KIND; a cell never picks it.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import lalonde  # noqa: E402

from kleinlib.data import load_partition  # noqa: E402
from kleinlib.eval import evaluate_estimate, evaluate_table  # noqa: E402

SMOKE = os.environ.get("KLEIN_SMOKE") == "1"
EXPERIMENT_ID = os.environ.get("KLEIN_EXPERIMENT_ID") or ("SMOKE" if SMOKE else None)
TRACK = os.environ.get("KLEIN_TRACK") or ("reproduction" if SMOKE else None)

# ---- the cell -----------------------------------------------------------------
CELL = {
    "estimator": "aipw",   # att track: ipw | aipw | match
    "spec": "dw_psid",    # att track: a key of lalonde.PROPENSITY
    "reps": 500,          # att track: bootstrap draws (each re-fits the propensity model)
}
# -------------------------------------------------------------------------------


def main() -> None:
    if EXPERIMENT_ID is None or TRACK is None:
        raise SystemExit("run through `klein run-one` (or KLEIN_SMOKE=1 for a shape check)")
    t0 = time.time()
    fit, comparison, fit_y, comparison_y = load_partition(target="re78")
    fit = lalonde.features(fit.assign(re78=fit_y))
    comparison = lalonde.features(comparison.assign(re78=comparison_y))
    nsw = fit[fit["sample"] == "nsw"]
    treated, controls = nsw[nsw["treat"] == 1], nsw[nsw["treat"] == 0]
    lane = str(comparison["sample"].iloc[0])  # psid1 on development, cps1 when sealed
    experimental = float(treated["re78"].mean() - controls["re78"].mean())

    if TRACK == "reproduction":
        targets = lalonde.TARGETS["development" if lane == "psid1" else "final_test"]
        measured: dict[str, float] = {}
        if lane == "psid1":
            measured.update({f"nsw_{k}": v for k, v in lalonde.contrast(treated, controls).items()})
            measured.update({"n_nsw_treated": len(treated), "n_nsw_control": len(controls)})
        measured.update({f"{lane}_{k}": v for k, v in lalonde.contrast(treated, comparison).items()})
        measured[f"n_{lane}"] = len(comparison)
        rows = []
        for name, printed in targets.items():
            value = measured.get(name)
            ok = value is not None and abs(value - printed) <= lalonde.TOLERANCE
            rows.append({"target": name, "published": printed, "reproduced": value,
                         "abs_diff": None if value is None else abs(value - printed),
                         "tolerance": lalonde.TOLERANCE, "status": "ok" if ok else "missed"})
        missed = sum(r["status"] == "missed" for r in rows)
        # Diagnostic rows (never counted): which Table 2 Panel C column each lane's
        # published "adjusted" value actually is (lib/lalonde.py:ADJUSTMENT_ALL).
        lanes = [("nsw", controls), (lane, comparison)] if lane == "psid1" else [(lane, comparison)]
        for name, group in lanes:
            panel = lalonde.PANEL_C[name]
            values = {"col4_note_a": lalonde.contrast(treated, group)["adjusted"],
                      **lalonde.diagnostics(treated, group)}
            for spec, value in values.items():
                for column, printed in panel.items():
                    rows.append({"target": f"diag_{name}_{spec}_vs_{column}", "published": printed,
                                 "reproduced": value, "abs_diff": abs(value - printed),
                                 "tolerance": lalonde.TOLERANCE,
                                 "status": "diagnostic"})
        path = lalonde.write_table(f"tables/reproduction_{lane}.tsv", list(rows[0]), rows)
        evaluate_table(
            path, missed, exp_id=EXPERIMENT_ID, metric_name="targets_outside_tolerance",
            metric_goal="lower", rows=len(rows), study_dir=".", t0=t0,
            extra={"targets": sum(r["status"] != "diagnostic" for r in rows), "experimental_att": experimental},
        )
        return

    if TRACK == "att":
        estimate = lalonde.att(treated, comparison, estimator=CELL["estimator"], spec=CELL["spec"])
        reps = 20 if SMOKE else int(CELL["reps"])
        draws = lalonde.bootstrap(treated, comparison, estimator=CELL["estimator"], spec=CELL["spec"], reps=reps)
        low, high = (float(q) for q in np.quantile(draws, [0.025, 0.975]))
        path = lalonde.write_table(
            f"tables/att_{EXPERIMENT_ID}.tsv",
            ["lane", "estimator", "spec", "att", "ci_low", "ci_high", "experimental_att", "gap",
             "n_treated", "n_controls_used", "max_weight_share", "reps", "bootstrap_seed"],
            [{"lane": lane, "estimator": CELL["estimator"], "spec": CELL["spec"], "att": estimate.att,
              "ci_low": low, "ci_high": high, "experimental_att": experimental,
              "gap": estimate.att - experimental, "n_treated": estimate.n_treated,
              "n_controls_used": estimate.n_controls_used, "max_weight_share": estimate.max_weight_share,
              "reps": reps, "bootstrap_seed": lalonde.BOOTSTRAP_SEED}],
        )
        if not SMOKE:
            print(f"artifact: {path.relative_to(lalonde.study_dir()).as_posix()}")
        evaluate_estimate(
            estimate.att, min(low, estimate.att), max(high, estimate.att), estimate.n_treated,
            exp_id=EXPERIMENT_ID, metric_name="att_usd", metric_goal="higher", study_dir=".", t0=t0,
            extra={"att_gap_usd": estimate.att - experimental, "experimental_att": experimental,
                   "n_controls_used": estimate.n_controls_used,
                   "max_weight_share": estimate.max_weight_share},
        )
        return
    raise SystemExit(f"unknown track {TRACK!r}")


if __name__ == "__main__":
    main()
