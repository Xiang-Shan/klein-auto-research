"""CELL E0012 — SEALED (track `estimate`, tests P4 and P7). One access.

Confirmation phase. For kind `estimate`, "sealed" means **an external reference
value, compared once** (`inquiry-model.md`) — not a held-out partition. There is
no more data: 24 objects is all Hubble printed, and carving a "holdout" out of
them would be theatre. What is spent here is the study's one licensed comparison
of its estimate against a value from outside the study.

The external reference is the modern Hubble constant. Two current determinations
bracket it: **67.4 ± 0.5** from the CMB (`ref:planck2018`) and **73.04 ± 1.04**
from the local distance ladder (`ref:riess2022`). This study compares against
the round **70** registered in `study.yaml:predictions`, and the ~5.6 km/s/Mpc
disagreement between those two — the "Hubble tension" — is an order of magnitude
smaller than the gap under test, which is why a round figure is adequate here
and would not be in a cosmology paper.

**P4** — does the 95 % interval's lower bound clear 70? The estimator is the one
E0006 fixed and did not choose afterwards: free-intercept OLS, 2000 case
resamples, seed block A, percentile interval. Rerunning it here rather than
quoting E0006 keeps the sealed comparison self-contained in one printed block.

**P7** — is the 1929-to-today gap a pure distance-SCALE error? Take the single
factor that would carry the through-origin fit to 70,

    f = k_origin / 70

apply that ONE factor to every distance, and ask where BOTH two-parameter fits
land. A pure scale error means both arrive near 70; a shape disagreement means
the free-intercept fit does not. The registered tolerance is ±15, and the
printed key P7's rule reads is `max_abs_gap_70`.

**Disclosed, because it is arithmetic and not a discovery.** `scouting_ledger.md`
records P7 as foreseeable: with f defined from `k_origin`, the free-intercept fit
lands at 70·k_free/k_origin, which the scouted anchors already fix. It is
registered anyway so the implication is auditable rather than asserted, and
findings §② repeats the disclosure. P4's direction was likewise foreseeable; its
*width* was not, and the width is what the claim rests on.

The rehearsal (`--final-test --dry-run`) computes the same numbers, because for
this shape of seal there is no held-out data to substitute. What it proves is
that the cell runs to completion before the one access is recorded as spent —
see `lib.hubble.acknowledge_sealed_dryrun`.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from kleinlib.eval import evaluate_estimate  # noqa: E402

from lib.hubble import (  # noqa: E402
    BLOCK_TABLE1,
    MODERN_H0,
    acknowledge_sealed_dryrun,
    block_fingerprint,
    bootstrap_k,
    load_block,
    ols_free_intercept,
    ols_through_origin,
    percentile_ci,
    simulation_spec,
    write_table,
)

SMOKE = os.environ.get("KLEIN_SMOKE") == "1"
EXPERIMENT_ID = os.environ.get("KLEIN_EXPERIMENT_ID") or ("SMOKE" if SMOKE else None)
TRACK = os.environ.get("KLEIN_TRACK") or ("estimate" if SMOKE else None)

N_BOOT = 2000
CI_LEVEL = 0.95

#: The two modern determinations that bracket the registered reference value.
PLANCK_H0 = 67.4
SHOES_H0 = 73.04


def main() -> None:
    t0 = time.time()
    evaluation_kind = os.environ.get("KLEIN_EVALUATION_KIND")
    if SMOKE:
        evaluation_kind = evaluation_kind or "development"
    missing = [
        name
        for name, value in (
            ("KLEIN_EVALUATION_KIND", evaluation_kind),
            ("KLEIN_EXPERIMENT_ID", EXPERIMENT_ID),
            ("KLEIN_TRACK", TRACK),
        )
        if value is None
    ]
    if missing:
        raise RuntimeError(
            "analyze.py must be invoked through `klein run-one`. For a pre-run "
            "syntax/shape check use `KLEIN_SMOKE=1 python analyze.py`. "
            "Missing: " + ", ".join(missing)
        )

    # This track's seal is a comparison, not a partition, so the cell owns the
    # rehearsal acknowledgement.
    acknowledge_sealed_dryrun()

    seed_a = int(simulation_spec()["seed_blocks"]["A"])
    table1 = load_block(BLOCK_TABLE1, echo=False)
    r = table1["r_mpc"].to_numpy(dtype=float)
    v = table1["v_kms"].to_numpy(dtype=float)

    k_free, _intercept = ols_free_intercept(r, v)
    k_origin = ols_through_origin(r, v)
    draws = bootstrap_k(r, v, n_boot=N_BOOT, seed=seed_a, estimator="free")
    low, high = percentile_ci(draws, CI_LEVEL)

    # P7: one factor, applied to every distance. Hubble's distances were too
    # SMALL — correcting the ladder MULTIPLIES them by f, which divides the
    # slope by f, because v = K r = (K/f)(f r). Writing `r / factor` inverts it
    # and sends the fits to ~2570 instead of ~70; the mandatory dry-run caught
    # exactly that, before the access was spent.
    factor = k_origin / MODERN_H0
    r_rescaled = r * factor
    k_origin_rescaled = ols_through_origin(r_rescaled, v)
    k_free_rescaled, intercept_rescaled = ols_free_intercept(r_rescaled, v)
    gap_origin = abs(k_origin_rescaled - MODERN_H0)
    gap_free = abs(k_free_rescaled - MODERN_H0)
    max_abs_gap_70 = max(gap_origin, gap_free)

    rows = [
        {
            "comparison": "P4_interval_vs_modern_H0",
            "value": k_free,
            "ci_low": low,
            "ci_high": high,
            "reference": MODERN_H0,
            "detail": (
                f"95% percentile bootstrap, {N_BOOT} resamples, seed block {seed_a}; "
                f"modern determinations bracket it: Planck {PLANCK_H0}, SH0ES {SHOES_H0}"
            ),
        },
        {
            "comparison": "P7_rescale_factor",
            "value": factor,
            "ci_low": float("nan"),
            "ci_high": float("nan"),
            "reference": MODERN_H0,
            "detail": "f = k_origin / 70, the single factor applied to every distance",
        },
        {
            "comparison": "P7_origin_fit_rescaled",
            "value": k_origin_rescaled,
            "ci_low": float("nan"),
            "ci_high": float("nan"),
            "reference": MODERN_H0,
            "detail": f"gap to 70 = {gap_origin:.6f} (zero by construction of f)",
        },
        {
            "comparison": "P7_free_intercept_fit_rescaled",
            "value": k_free_rescaled,
            "ci_low": float("nan"),
            "ci_high": float("nan"),
            "reference": MODERN_H0,
            "detail": (
                f"gap to 70 = {gap_free:.6f}; intercept {intercept_rescaled:.6f} km/s "
                "is unchanged by a distance rescale"
            ),
        },
    ]
    write_table(
        "tables/sealed_modern_comparison.tsv",
        ("comparison", "value", "ci_low", "ci_high", "reference", "detail"),
        rows,
    )

    evaluate_estimate(
        k_free,
        low,
        high,
        int(r.size),
        exp_id=EXPERIMENT_ID,
        study_dir=".",
        t0=t0,
        metric_name="k_kms_per_mpc",
        metric_goal="lower",
        split_fingerprint=block_fingerprint(table1),
        extra={
            "artifact": "tables/sealed_modern_comparison.tsv",
            "n_boot": float(N_BOOT),
            "modern_h0": MODERN_H0,
            "planck_h0": PLANCK_H0,
            "shoes_h0": SHOES_H0,
            "ci_width": high - low,
            "ratio_estimate_over_modern": k_free / MODERN_H0,
            "rescale_factor": factor,
            "k_origin": k_origin,
            "k_origin_rescaled": k_origin_rescaled,
            "k_free_rescaled": k_free_rescaled,
            "gap_70_origin": gap_origin,
            "gap_70_free": gap_free,
            "max_abs_gap_70": max_abs_gap_70,
            "bootstrap_se": float(np.std(draws, ddof=1)),
        },
    )


if __name__ == "__main__":
    main()
