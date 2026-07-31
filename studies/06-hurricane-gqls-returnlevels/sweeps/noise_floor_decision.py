"""Phase-0 measurement: the decision track's paired-bootstrap floor (sweep-rules carve-out).

Study 04's metrology finding — three defensible floors differ 25x, and the PAIRED
difference bootstrap is the one that matches a two-model comparison — applied to the
decision track. Promotes no winner and writes no `results.tsv` row.

What is resampled, and why that is the right thing
--------------------------------------------------
The decision metric is ``return_level_instability_pct``: a MAX over a fixed, deterministic
stress set. Given the sample, it has no sampling distribution of its own — the stress set
is not random. What IS random is the 30-event sample itself. So the floor resamples the
**events**, and per replicate refits BOTH candidate configurations on the SAME resampled
30 events (common random numbers, by construction — one index draw feeds both), then
records the PAIRED difference of the log 1-in-100 return levels:

    d_b = log RL_A(x*_b) - log RL_B(x*_b)

Logs, not dollars: the log-Cauchy 1-in-100 is ``exp(mu + 31.82 sigma)``, so on the dollar
scale a handful of replicates would dominate any standard deviation. On the log scale the
paired difference is the ratio the comparison actually cares about.

    SE = std(d_b, ddof=1) over B = 1000 replicates, in 5 blocks of 200
    (block SEs printed — they show whether the bootstrap itself has settled)

The two configs are the study's sharpest disagreement (RQ5): the conventional
MLE-lognormal 1-in-100 versus the best-FITTING but transform-amplified gQLS log-Cauchy.

Mapping the floor onto the metric's unit — stated honestly
----------------------------------------------------------
The SE above is in log-return-level units. The track's metric is a PERCENTAGE change, so
a log difference ``d`` maps to ``100 (exp(d) - 1)`` percent. The recommendation is
therefore ``minimum_delta = 100 (exp(2 SE) - 1)`` percentage points. What that number
bounds precisely: **resample noise in the return-level RATIO between two configurations**.
What it does not do: propagate through the max-over-stress-set operator exactly, since the
metric is a max of several such ratios. It is a defensible LOWER bound on a meaningful
difference between two configs' instability, not an exact sampling s.e. of the metric —
both the log-scale SE and its percent equivalent are printed so a reader can see the
conversion instead of taking it on trust.

Run from the study directory:  uv run --no-sync python sweeps/noise_floor_decision.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import analysis as A
import estimators as E
import numpy as np

B_BLOCKS, B_PER_BLOCK = 5, 200
SEED = 20260731
P_RETURN = 0.99  # the 1-in-100 event — the decision track's unit
CONVENTION = E.THESIS_QUANTILE_METHOD  # the decision modes' registered convention

CONFIG_A = ("mle", "lognormal", (0.05, 0.95))
CONFIG_B = ("gqls", "log-cauchy", (0.05, 0.95))


def _fitter(config: tuple[str, str, tuple[float, float]]):
    estimator, family, trim = config
    return A.decision_fitter(estimator, family, trim, CONVENTION, A.K_DEFAULT)


def _log_return_level(fit: E.Fit) -> float:
    """``log RL = mu + sigma F_*^-1(p)`` — computed in logs, never via exp/log round-trip."""
    member = E.STANDARD_MEMBERS[fit.family]
    return float(fit.mu + fit.sigma * float(member.ppf(np.array([P_RETURN]))[0]))


def paired_bootstrap() -> dict:
    """Run the CRN bootstrap; return the paired differences AND each config's own draws.

    The per-config log-RL arrays cost nothing extra (they are the two terms of every
    paired difference) and they are what makes the paired SE interpretable: if the pair's
    SE is essentially one config's SE, the "floor" is that config's tail amplification
    rather than a property of the comparison.
    """
    x = A.sample()
    fit_a, fit_b = _fitter(CONFIG_A), _fitter(CONFIG_B)
    rng = np.random.default_rng(SEED)
    n = x.size

    diffs: list[float] = []
    a_draws: list[float] = []
    b_draws: list[float] = []
    block_ses: list[float] = []
    dropped = 0
    for _ in range(B_BLOCKS):
        block: list[float] = []
        for _ in range(B_PER_BLOCK):
            idx = rng.integers(0, n, n)  # ONE draw -> both configs see identical events
            resample = x[idx]
            try:
                log_a = _log_return_level(fit_a(resample))
                log_b = _log_return_level(fit_b(resample))
            except Exception:  # a degenerate resample is dropped, and counted
                dropped += 1
                continue
            if not (np.isfinite(log_a) and np.isfinite(log_b)):
                dropped += 1
                continue
            block.append(float(log_a - log_b))
            a_draws.append(float(log_a))
            b_draws.append(float(log_b))
        if len(block) > 1:
            block_ses.append(float(np.std(block, ddof=1)))
        diffs.extend(block)
    return {
        "se": float(np.std(diffs, ddof=1)),
        "block_ses": block_ses,
        "diffs": np.asarray(diffs, float),
        "se_a": float(np.std(a_draws, ddof=1)),
        "se_b": float(np.std(b_draws, ddof=1)),
        "dropped": dropped,
    }


def main() -> None:
    x = A.sample()
    fit_a, fit_b = _fitter(CONFIG_A), _fitter(CONFIG_B)
    clean_a, clean_b = fit_a(x), fit_b(x)
    point = _log_return_level(clean_a) - _log_return_level(clean_b)

    print(f"=== paired-bootstrap decision floor (convention = {CONVENTION}) ===")
    print(f"  config A: {CONFIG_A[0]:>4s} / {CONFIG_A[1]:<12s} 1-in-100 = "
          f"{E.return_level(clean_a, P_RETURN) / 1e9:,.4f} $bn")
    print(f"  config B: {CONFIG_B[0]:>4s} / {CONFIG_B[1]:<12s} 1-in-100 = "
          f"{E.return_level(clean_b, P_RETURN) / 1e9:,.4f} $bn")
    print(f"  point estimate of the paired log-RL difference: {point:+.6f} "
          f"(ratio {np.exp(point):.4g}x)")
    print(f"  {A.SUPPORT_CAVEAT}")

    out = paired_bootstrap()
    se, block_ses, diffs = out["se"], out["block_ses"], out["diffs"]
    print(f"\n  B = {B_BLOCKS} x {B_PER_BLOCK} = {B_BLOCKS * B_PER_BLOCK} replicates, "
          f"CRN (one index draw per replicate feeds both configs); {diffs.size} usable, "
          f"{out['dropped']} dropped")
    print(f"  block SEs (log-RL): {[f'{s:.4f}' for s in block_ses]}")
    print(f"  paired SE (log-RL): {se:.6f}      2 x SE = {2 * se:.6f}")
    print(f"  decomposition — config A alone: {out['se_a']:.6f}   "
          f"config B alone: {out['se_b']:.6f}")

    pct_1se = 100.0 * (np.exp(se) - 1.0)
    pct_2se = 100.0 * (np.exp(2.0 * se) - 1.0)
    pct_2se_down = 100.0 * (1.0 - np.exp(-2.0 * se))
    print("\n=== mapping the log-scale floor onto the metric's percent unit ===")
    print(f"  1 x SE  ->  {pct_1se:12.3f} pp")
    print(f"  2 x SE  ->  {pct_2se:12.3f} pp  upward   [100 (exp(d) - 1)]")
    print(f"  2 x SE  ->  {pct_2se_down:12.3f} pp  downward [100 (1 - exp(-d))], "
          "bounded by 100pp by construction")
    print(
        f"\nRECOMMENDATION  minimum_delta = {pct_2se:.1f} percentage points, i.e. "
        f"2 x SE = {2 * se:.4f} on the log-return-level scale. It bounds RESAMPLE noise "
        "of the RATIO between the two configurations' 1-in-100 return levels; it is not "
        "an exact sampling s.e. of the max-over-stress-set metric, which is a max of "
        "several such ratios."
    )
    if pct_2se > 100.0:
        print(
            "\n  READ THIS BEFORE RECORDING THE DELTA. The percent-unit floor exceeds "
            "100pp, i.e. it is larger than the metric's own natural scale, so taking it "
            "literally would make the decision track undecidable (every candidate would "
            f"discard). Cause is visible in the decomposition: config B's own log-RL SE "
            f"({out['se_b']:.2f}) carries essentially the whole paired SE ({se:.2f}) — "
            "the log-Cauchy 1-in-100 multiplies sigma-hat by tan(0.49 pi) = 31.82, so a "
            "resampled 30-event set moves it by orders of magnitude. That is RQ5's "
            "punchline arriving early as a METROLOGY result: at n = 30 the log-Cauchy "
            "1-in-100 is not estimable to any useful precision.\n"
            "  Two honest resolutions for the CONSULT re-record, in order of preference:\n"
            "   (1) keep minimum_delta at study.yaml's provisional 1.0pp and treat this "
            "floor as the track's stated uncertainty band — every decision-track claim "
            "then carries 'differences below the resample noise of the log-Cauchy arm "
            "are not evidence';\n"
            "   (2) re-measure the floor over the GoF-passing families the track will "
            "actually adjudicate between, excluding the moment-free log-Cauchy, and "
            "record THAT as minimum_delta — the log-Cauchy stays in the study as a "
            "reported finding rather than as a frontier competitor.\n"
            "  Do NOT quietly shrink the number: the size of this floor IS evidence."
        )


if __name__ == "__main__":
    main()
