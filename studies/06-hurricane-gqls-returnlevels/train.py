"""The only per-candidate mutable surface in a Klein v2 study.

Study 06 — hurricane gQLS reproduction and return levels. Every computation lives in
`analysis.py` (the stable study library); this file selects ONE mode and its arguments,
re-verifies the data-identity anchor, and hands the result to the v2 evaluator.

Two tracks, two primary metric names — the printed name MUST match the track being run
or `klein run-one` refuses the result:

    KLEIN_TRACK=reproduction  ->  mean_abs_param_deviation      (lower)
    KLEIN_TRACK=decision      ->  return_level_instability_pct  (lower)

Guardrails are read by the runner off the PRINTED block, so `extra` carries every
guardrail key of the running track with its measured value — `analysis.check_extra`
asserts that before a mode may return (study 05, lesson F1). Guardrail `wall_seconds`
is added here, the only place that knows `t0`.

Sealed evidence: `sealed_repro` / `sealed_decision` read pre-registered published truth
(the full Table 6.10 grid; the exact 72.303 -> 723.03 modification) and may run ONLY
under `klein run-one --final-test`, once per track. The guard below is what enforces it.
"""

from __future__ import annotations

import os
import time

import analysis

from kleinlib.eval import evaluate_scalar

SMOKE = os.environ.get("KLEIN_SMOKE") == "1"

# ---- CONFIG: the per-experiment surface (keep diffs 5-15 lines) ----
MODE = "grid"          # anchor | grid | gof_redundancy | oqls_mle_arms | sensitivity
                         # | decision | sealed_repro | sealed_decision
CONVENTION = "inverted_cdf"     # inverted_cdf | hazen | weibull | median_unbiased | normal_unbiased
K = 8                    # quantile levels per fit; Tables 6.9/6.10 use k = 8
ESTIMATOR = "mle"        # decision modes only: mle | gqls | oqls
FAMILY = "lognormal"     # decision modes only: any of estimators.FAMILIES
TRIM = (0.05, 0.95)      # decision modes only: the (a, b) quantile trim
# -------------------------------------------------------------------

EXPERIMENT_ID = os.environ.get("KLEIN_EXPERIMENT_ID") or ("SMOKE" if SMOKE else None)
TRACK = os.environ.get("KLEIN_TRACK") or (
    analysis.MODE_TRACK.get(MODE) if SMOKE else None
)

DECISION_MODES = {"decision", "sealed_decision"}


def main() -> None:
    t0 = time.time()
    evaluation_kind = os.environ.get("KLEIN_EVALUATION_KIND") or (
        "development" if SMOKE else None
    )
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
            "train.py must be invoked through `klein run-one`. For a pre-run "
            "syntax/shape check use `KLEIN_SMOKE=1 python train.py` — it prints the "
            "canonical block, writes no sidecars or snapshots, and is not evidence. "
            "Missing: " + ", ".join(missing)
        )
    if evaluation_kind not in {"development", "final_test"}:
        raise RuntimeError(f"invalid KLEIN_EVALUATION_KIND={evaluation_kind!r}")

    # ---- contract checks: mode, track, and sealed access must agree ----
    if MODE not in analysis.MODES:
        raise RuntimeError(
            f"unknown MODE={MODE!r}; expected one of {sorted(analysis.MODES)}"
        )
    if TRACK not in analysis.TRACK_METRIC:
        raise RuntimeError(
            f"invalid KLEIN_TRACK={TRACK!r}; expected one of {sorted(analysis.TRACK_METRIC)}"
        )
    if analysis.MODE_TRACK[MODE] != TRACK:
        raise RuntimeError(
            f"MODE={MODE!r} belongs to track {analysis.MODE_TRACK[MODE]!r}, but this run "
            f"is on track {TRACK!r} — the primary metric name would not match the contract"
        )
    sealed = MODE in analysis.SEALED_MODES
    if evaluation_kind == "final_test" and not sealed:
        raise RuntimeError(
            f"--final-test spends a track's one sealed access, but MODE={MODE!r} is an "
            f"adaptive mode; sealed modes are {sorted(analysis.SEALED_MODES)}"
        )
    if sealed and evaluation_kind != "final_test":
        message = (
            f"MODE={MODE!r} reads PRE-REGISTERED SEALED evidence and must run through "
            "`klein run-one --final-test`, once per track"
        )
        if not SMOKE:
            raise RuntimeError(message)
        print(f"[smoke] {message} — shape check only, not evidence")

    # ---- data-identity anchor: re-verified on EVERY run, before any fitting ----
    identity = analysis.verify_identity()
    print(
        f"identity anchor OK: {identity['identity_stats_verified']} statistics, "
        f"max |deviation| {identity['identity_max_abs_deviation']:.2e}"
    )

    if MODE in DECISION_MODES:
        primary, extra = analysis.MODES[MODE](ESTIMATOR, FAMILY, TRIM, CONVENTION, K)
    else:
        primary, extra = analysis.MODES[MODE](CONVENTION, K)

    evaluate_scalar(
        primary,
        exp_id=EXPERIMENT_ID,
        metric_name=analysis.TRACK_METRIC[TRACK],
        metric_goal="lower",
        study_dir=".",
        t0=t0,
        extra={
            **extra,
            "wall_seconds": time.time() - t0,
            "mode": MODE,
            "convention": CONVENTION,
        },
    )


if __name__ == "__main__":
    main()
