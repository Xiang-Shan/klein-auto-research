"""analysis.py — the stable per-mode computation library for study 06.

`train.py` is the 5-15 line mutable surface; THIS file is the library it calls, and it
changes only deliberately (never as part of a per-experiment diff). Every mode has the
same shape::

    mode(...) -> (primary_value: float, extra: dict)

and the contract on ``extra`` is the load-bearing one:

**Every mode returns, in ``extra``, every guardrail key of its track's contract with the
value MEASURED on this run.** `klein run-one` classifies a candidate by regex-scraping
``key: value`` lines out of the run log (`kleinlib.workflow.parse_metric_log`), and a
guardrail whose key never appears is scored ``guardrail metric 'x' missing`` -> discard.
So the guardrails must be *printed*, not merely computed — the F1 lesson from study 05.
:func:`check_extra` enforces this before a mode can return, so the failure is a loud
``AssertionError`` in the study library rather than a silent discard on the ledger.

Track contracts (study.yaml, matched by KEY NAME exactly):

===============  ===============================  ==========================================
track            primary metric                   guardrail keys
===============  ===============================  ==========================================
``reproduction`` ``mean_abs_param_deviation``     ``max_abs_param_deviation`` (<= 0.02),
                                                  ``max_abs_w_deviation`` (<= 0.10),
                                                  ``max_abs_p_deviation`` (<= 0.02),
                                                  ``wall_seconds`` (<= 120)
``decision``     ``return_level_instability_pct`` ``w_pvalue`` (>= 0.10), ``wall_seconds``
===============  ===============================  ==========================================

(``wall_seconds`` is added by ``train.py``, which is the only place that knows ``t0``.)

The eight modes and what each is evidence FOR
---------------------------------------------
``anchor``           the data-identity cell + one gQLS fit vs Table 6.9 -- STOP-on-miss.
``grid``             RQ1: all 18 published gQLS cells, 36 parameters.
``gof_redundancy``   RQ2: is the thesis's B=1000 bootstrap for ``W_out`` distinguishable
                     from a chi2_{r-2} reference ON THIS DATA?
``oqls_mle_arms``    the Sigma-star falsifier (o2-vs-g2 log-Cauchy sigma-hat 0.23/0.49)
                     plus the MLE/oQLS arms of Table 6.10's ORIGINAL rows.
``sensitivity``      is k or the QUANTILE CONVENTION the dominant reproduction lever?
``decision``         RQ5/RQ6: 1-in-100 return-level instability under the adaptive stress
                     set, among fits that PASS the in-sample GoF guardrail.
``sealed_repro``     confirmation: the FULL Table 6.10 grid, 120 published parameters.
``sealed_decision``  confirmation: the incumbent decision config under the thesis's exact
                     10x modification.

Sealed-evidence discipline
--------------------------
The thesis's exact modification (72.303 -> 723.03) is PRE-REGISTERED SEALED EVIDENCE. It
is reachable from exactly two places in this module -- :func:`sealed_repro` and
:func:`sealed_decision` -- both of which `klein run-one --final-test` gates. The adaptive
stress set therefore inflates the maximum by **5x**, not 10x (`stress.default_stress_set`
defaults to ``inflate_factors=(10.0,)``, i.e. straight at the sealed point; every adaptive
caller here passes :data:`ADAPTIVE_INFLATE_FACTOR` instead). Table 6.10's ORIGINAL rows
are adaptive by the pre-registered ladder (study.yaml adaptive-2 / research_plan E0004);
its starred rows are not touched outside :func:`sealed_repro`.

Units
-----
Fitting is on LOG-DOLLARS, ``x = log(damage_bn_1995 * 1e9)`` -- the thesis's own scale, so
``mu ~ 22.8``. Return levels are reported in ``$bn`` (dollars / 1e9) because that is the
unit the decision is taken in.
"""

from __future__ import annotations

import json
import math
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import scipy.stats as st

STUDY_DIR = Path(__file__).resolve().parent
if str(STUDY_DIR) not in sys.path:
    sys.path.insert(0, str(STUDY_DIR))

import estimators as E  # noqa: E402
import stress as S  # noqa: E402

PREPARED_CSV = STUDY_DIR / "data" / "prepared" / "hurricane_top30.csv"
REFERENCE_CELL = STUDY_DIR / "data" / "prepared" / "reference_cell.json"
THESIS_TABLES = STUDY_DIR / "reference" / "thesis_tables.json"

#: study.yaml's reporting-resolution minimum_delta -- half the last published digit.
REPORTING_RESOLUTION = 0.005
#: prepare.py's identity tolerance; re-used here so the anchor cannot be looser.
IDENTITY_TOLERANCE = 1e-4
#: The five sample-quantile conventions the pre-registered floor sweep spans.
CONVENTIONS: tuple[str, ...] = (
    "inverted_cdf",  # THE THESIS'S OWN definition, Fhat^-1(p) = X_(ceil(np))
    "hazen",  # the DESCRIPTIVE table's convention (MATLAB default); registered default
    "weibull",
    "median_unbiased",
    "normal_unbiased",
)
#: Gross-error factor used in ADAPTIVE work. NOT 10x -- that is sealed evidence.
ADAPTIVE_INFLATE_FACTOR = 5.0
#: The thesis's own modification, reachable only from the two sealed modes.
SEALED_INFLATE_FACTOR = 10.0
#: Fixed so W_out's parametric bootstrap is reproducible run to run.
BOOTSTRAP_SEED = 20260731
BOOTSTRAP_B = 1000
#: Table 6.9's out-of-sample validation grid (its caption: r = 25).
R_OUT = 25
#: Table 6.9 / 6.10 fit every QLS cell at k = 8.
K_DEFAULT = 8
#: Return periods reported with every decision run: (label, p, years).
RETURN_PERIODS: tuple[tuple[str, float, int], ...] = (
    ("1in10", 0.90, 10),
    ("1in25", 0.96, 25),
    ("1in100", 0.99, 100),
)
#: n = 30 events: the empirical support tops out near a 1-in-30 event. Everything beyond
#: is MODEL, not data -- printed with every decision run so no reader forgets it.
SUPPORT_CAVEAT = (
    "n=30 events: empirical support tops out near 1-in-30; the 1-in-100 is extrapolation "
    "governed entirely by the fitted family's tail, not by the data"
)

#: The five Table-6.10 estimator arms: name -> (estimator, a, b). MLE has no grid.
ARMS: dict[str, tuple[str, float | None, float | None]] = {
    "MLE": ("mle", None, None),
    "o2": ("oqls", 0.05, 0.95),
    "o3": ("oqls", 0.10, 0.90),
    "g2": ("gqls", 0.05, 0.95),
    "g3": ("gqls", 0.10, 0.90),
}

#: track -> primary metric name (study.yaml). train.py asserts against this.
TRACK_METRIC: dict[str, str] = {
    "reproduction": "mean_abs_param_deviation",
    "decision": "return_level_instability_pct",
}
#: track -> the guardrail keys train.py must PRINT. `wall_seconds` is train.py's.
TRACK_GUARDRAILS: dict[str, tuple[str, ...]] = {
    "reproduction": (
        "max_abs_param_deviation",
        "max_abs_w_deviation",
        "max_abs_p_deviation",
    ),
    "decision": ("w_pvalue",),
}
#: mode -> the track it is valid for.
MODE_TRACK: dict[str, str] = {
    "anchor": "reproduction",
    "grid": "reproduction",
    "gof_redundancy": "reproduction",
    "oqls_mle_arms": "reproduction",
    "sensitivity": "reproduction",
    "sealed_repro": "reproduction",
    "decision": "decision",
    "sealed_decision": "decision",
}
#: modes that reach the sealed 10x modification / the full Table 6.10 grid.
SEALED_MODES: frozenset[str] = frozenset({"sealed_repro", "sealed_decision"})


# ======================================================================================
# Cached inputs -- loaded ONCE per process
# ======================================================================================
_CACHE: dict[str, Any] = {}


def sample() -> np.ndarray:
    """The 30-event LOG-DOLLAR fitting column, ``x = log(damage_bn_1995 * 1e9)``.

    Recomputed from the billions column so the unit chain is explicit at the point of
    use (the sealed modification is stated in billions), then cross-checked against the
    ``log_damage_usd`` column prepare.py wrote.
    """
    if "x" not in _CACHE:
        frame = pd.read_csv(PREPARED_CSV)
        billions = frame["damage_bn_1995"].to_numpy(float)
        x = np.log(billions * 1e9)
        stored = frame["log_damage_usd"].to_numpy(float)
        if not np.allclose(x, stored, atol=1e-12, rtol=0.0):
            raise RuntimeError(
                "prepared CSV inconsistent: log(damage_bn_1995 * 1e9) != log_damage_usd "
                f"(max |diff| {float(np.max(np.abs(x - stored))):.3e}) — re-run prepare.py"
            )
        _CACHE["x"] = x
    return _CACHE["x"]


def tables() -> dict:
    """The committed transcription of Tables 6.8 / 6.9 / 6.10."""
    if "tables" not in _CACHE:
        _CACHE["tables"] = json.loads(THESIS_TABLES.read_text())
    return _CACHE["tables"]


def reference_cell() -> dict:
    """prepare.py's data-identity cell (published stats, observed stats, sha256)."""
    if "reference_cell" not in _CACHE:
        _CACHE["reference_cell"] = json.loads(REFERENCE_CELL.read_text())
    return _CACHE["reference_cell"]


# ======================================================================================
# The identity gate -- re-verified on EVERY run, before any fitting
# ======================================================================================
def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_identity() -> dict:
    """Re-verify prepare.py's reference cell. RAISES on drift.

    Three independent things must still hold, in this order:

    1. every published Table-6.8 statistic (Hazen quartiles, ddof=1 sd -- the DESCRIPTIVE
       convention, never the run's fitting convention) within :data:`IDENTITY_TOLERANCE`;
    2. both MLE-lognormal anchors of Table 6.10 (clean 22.8002/0.8339 and 10x-modified
       22.8769/1.0975) -- these pin the *fitting column*, since a wrong 1e9 scaling would
       move mu by log(1000) = 6.9 while leaving every quartile in billions untouched;
    3. the prepared file's SHA-256.

    Returns a small summary dict for the run's ``extra``. This is study 05's
    split-identity-anchor pattern: an anchor that is not checked every run is not an
    anchor. Note (2) evaluates the sealed 10x modification, which is why it lives in the
    IDENTITY gate and not in an adaptive mode -- prepare.py already published both
    numbers at Gate 1, so nothing is learned adaptively by re-asserting them.
    """
    cell = reference_cell()
    frame = pd.read_csv(PREPARED_CSV)
    damages = frame["damage_bn_1995"].to_numpy(float)
    method = E.SUMMARY_QUANTILE_METHOD
    observed = {
        "n": float(damages.size),
        "min": float(damages.min()),
        "q1": float(np.quantile(damages, 0.25, method=method)),
        "q2": float(np.quantile(damages, 0.50, method=method)),
        "q3": float(np.quantile(damages, 0.75, method=method)),
        "max": float(damages.max()),
        "mean": float(damages.mean()),
        "std_dev": float(damages.std(ddof=1)),
    }
    failures: list[str] = []
    worst = 0.0
    for key, want in cell["table_6_8_published"].items():
        deviation = abs(observed[key] - float(want))
        worst = max(worst, deviation)
        if deviation > IDENTITY_TOLERANCE:
            failures.append(f"table_6_8.{key}: published {want}, observed {observed[key]!r}")

    x = np.log(damages * 1e9)
    anchors = {
        "mle_lognormal_original": E.mle(x, "lognormal"),
        "mle_lognormal_modified": E.mle(S.inflate_max(x, SEALED_INFLATE_FACTOR), "lognormal"),
    }
    for name, want in cell["mle_anchors_published"].items():
        got = anchors[name]
        for param in ("mu", "sigma"):
            deviation = abs(getattr(got, param) - float(want[param]))
            worst = max(worst, deviation)
            if deviation > IDENTITY_TOLERANCE:
                failures.append(
                    f"{name}.{param}: published {want[param]}, observed {getattr(got, param):.6f}"
                )

    digest = _sha256(PREPARED_CSV)
    if digest != cell["prepared_sha256"]:
        failures.append(
            f"prepared_sha256: recorded {cell['prepared_sha256']}, observed {digest}"
        )

    if failures:
        raise RuntimeError(
            "DATA-IDENTITY ANCHOR FAILED — this is no longer the sample Adjieteh (2024) "
            "§6.2.2 fitted, so every downstream number would be a confident answer to the "
            "wrong question. STOP and resolve provenance (see the dataset README's two "
            "provenance traps). Drift: " + "; ".join(failures)
        )
    return {
        "identity_stats_verified": len(cell["table_6_8_published"]) + 4,
        "identity_max_abs_deviation": float(worst),
        "identity_sha256_ok": True,
    }


# ======================================================================================
# extra-dict plumbing: the F1 lesson, enforced
# ======================================================================================
def _num(value: Any) -> Any:
    """Guard the metric-log parser: a non-finite float would abort classification.

    `parse_metric_log` raises `WorkflowError` on any ``key: value`` line whose value
    parses to a non-finite float. Rendering those as a non-numeric token keeps them
    visible in the log and the aux sidecar while making the parser skip them.
    """
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else f"non_finite({value!r})"
    return value


def _json(obj: Any) -> str:
    """Compact single-line JSON — the aux sidecar is TSV, so no tabs and no newlines."""
    return json.dumps(obj, separators=(",", ":"), sort_keys=True, default=float)


def check_extra(track: str, extra: dict) -> dict:
    """Assert every guardrail key of `track` is present and finite. Returns `extra`."""
    if track not in TRACK_GUARDRAILS:
        raise ValueError(f"unknown track {track!r}; expected one of {sorted(TRACK_METRIC)}")
    missing = [k for k in TRACK_GUARDRAILS[track] if k not in extra]
    if missing:
        raise AssertionError(
            f"track {track!r} guardrail key(s) {missing} absent from extra — `klein "
            "run-one` reads guardrails off the PRINTED block, so an unprinted guardrail "
            "is scored 'missing' and the candidate is discarded (study 05, lesson F1)"
        )
    bad = [
        k
        for k in TRACK_GUARDRAILS[track]
        if not isinstance(extra[k], (int, float)) or not math.isfinite(float(extra[k]))
    ]
    if bad:
        raise AssertionError(f"track {track!r} guardrail value(s) {bad} are not finite numbers")
    return {k: _num(v) for k, v in extra.items()}


# ======================================================================================
# Shared fitting helpers
# ======================================================================================
@dataclass(frozen=True)
class Cell:
    """One published Table-6.9 cell: our fit, the printed values, and the deviations."""

    trim: str
    a: float
    b: float
    family: str
    fit: E.Fit
    published: dict
    d_mu: float
    d_sigma: float
    w: dict
    d_w: float
    d_p: float


def _fit_arm(
    x: np.ndarray,
    arm: str,
    family: str,
    *,
    convention: str,
    k: int = K_DEFAULT,
) -> E.Fit:
    """Fit one Table-6.10 arm (`MLE`/`o2`/`o3`/`g2`/`g3`) on the given sample."""
    estimator, a, b = ARMS[arm]
    if estimator == "mle":
        return E.mle(x, family)
    fn = E.oqls if estimator == "oqls" else E.gqls
    return fn(x, a, b, k, family, method=convention)


def gqls_grid(convention: str, k: int = K_DEFAULT) -> list[Cell]:
    """The 18 published gQLS cells of Table 6.9 (3 trims x 6 families), fitted once.

    Each cell also carries OUR ``W`` (eq. 5.2) evaluated on the same estimation grid, so
    the reproduction track's ``max_abs_w_deviation`` / ``max_abs_p_deviation`` guardrails
    are measurements against the published ``W`` / ``p_W`` columns.
    """
    x = sample()
    cells: list[Cell] = []
    for trim_key, trim in tables()["table_6_9"]["trims"].items():
        a, b = float(trim["a"]), float(trim["b"])
        for family in E.FAMILIES:
            published = trim[family]
            fit = E.gqls(x, a, b, k, family, method=convention)
            w = E.W(x, fit)
            cells.append(
                Cell(
                    trim=trim_key,
                    a=a,
                    b=b,
                    family=family,
                    fit=fit,
                    published=published,
                    d_mu=abs(fit.mu - float(published["mu"])),
                    d_sigma=abs(fit.sigma - float(published["sigma"])),
                    w=w,
                    d_w=abs(w["W"] - float(published["W"])),
                    d_p=abs(w["p_value"] - float(published["p_W"])),
                )
            )
    return cells


def _grid_stats(cells: list[Cell]) -> tuple[float, dict]:
    """(primary, guardrail-and-aux extras) for a Table-6.9 grid of cells."""
    param_devs = np.array([d for c in cells for d in (c.d_mu, c.d_sigma)], float)
    w_devs = np.array([c.d_w for c in cells], float)
    p_devs = np.array([c.d_p for c in cells], float)
    primary = float(param_devs.mean())
    extra = {
        # --- the three reproduction guardrails, by exact key name ---
        "max_abs_param_deviation": float(param_devs.max()),
        "max_abs_w_deviation": float(w_devs.max()),
        "max_abs_p_deviation": float(p_devs.max()),
        # --- aux ---
        "n_cells": len(cells),
        "n_params": int(param_devs.size),
        "params_within_resolution": int(np.sum(param_devs <= REPORTING_RESOLUTION)),
        "worst_param_cell": max(
            cells, key=lambda c: max(c.d_mu, c.d_sigma)
        ).trim
        + "/"
        + max(cells, key=lambda c: max(c.d_mu, c.d_sigma)).family,
        "worst_w_cell": max(cells, key=lambda c: c.d_w).trim
        + "/"
        + max(cells, key=lambda c: c.d_w).family,
    }
    for trim_key in sorted({c.trim for c in cells}):
        block = np.array(
            [d for c in cells if c.trim == trim_key for d in (c.d_mu, c.d_sigma)], float
        )
        extra[f"mean_abs_dev_trim_{trim_key.replace('.', '')}"] = float(block.mean())
    return primary, extra


def _fit_table(cells: list[Cell]) -> str:
    """Compact JSON of the whole grid — one aux line, fully reconstructable."""
    return _json(
        {
            f"{c.trim}/{c.family}": {
                "mu": round(c.fit.mu, 6),
                "sigma": round(c.fit.sigma, 6),
                "pub_mu": c.published["mu"],
                "pub_sigma": c.published["sigma"],
                "W": round(c.w["W"], 6),
                "pub_W": c.published["W"],
                "p_W": round(c.w["p_value"], 6),
                "pub_p_W": c.published["p_W"],
            }
            for c in cells
        }
    )


# ======================================================================================
# MODE: anchor -- the adaptive-1 STOP-on-miss cell
# ======================================================================================
def anchor(convention: str, k: int = K_DEFAULT) -> tuple[float, dict]:
    """Data identity + ONE gQLS cell: lognormal, (0.05, 0.95), vs Table 6.9's 22.79/0.82.

    The cheapest possible falsifier of the whole pipeline. If this cell misses by more
    than the reporting resolution the ladder stops here, because nothing downstream can
    be trusted (study.yaml, phase adaptive-1: "STOP on miss").

    primary = mean |deviation| over this cell's two parameters.
    """
    identity = verify_identity()
    x = sample()
    published = tables()["table_6_9"]["trims"]["0.05_0.95"]["lognormal"]
    fit = E.gqls(x, 0.05, 0.95, k, "lognormal", method=convention)
    w = E.W(x, fit)

    d_mu = abs(fit.mu - float(published["mu"]))
    d_sigma = abs(fit.sigma - float(published["sigma"]))
    d_w = abs(w["W"] - float(published["W"]))
    d_p = abs(w["p_value"] - float(published["p_W"]))
    primary = float((d_mu + d_sigma) / 2.0)

    extra = {
        **identity,
        # the three reproduction guardrails, measured on this single cell
        "max_abs_param_deviation": float(max(d_mu, d_sigma)),
        "max_abs_w_deviation": float(d_w),
        "max_abs_p_deviation": float(d_p),
        # our fitted values and the published targets
        "cell": "0.05_0.95/lognormal",
        "mu_hat": float(fit.mu),
        "sigma_hat": float(fit.sigma),
        "published_mu": float(published["mu"]),
        "published_sigma": float(published["sigma"]),
        "d_mu": float(d_mu),
        "d_sigma": float(d_sigma),
        "w_statistic": float(w["W"]),
        "w_df": int(w["df"]),
        "w_pvalue": float(w["p_value"]),
        "published_w": float(published["W"]),
        "published_p_w": float(published["p_W"]),
        "sigma_star_cond": float(fit.sigma_star_cond or float("nan")),
        "within_reporting_resolution": int(max(d_mu, d_sigma) <= REPORTING_RESOLUTION),
        "k": int(k),
    }
    return primary, check_extra("reproduction", extra)


# ======================================================================================
# MODE: grid -- RQ1, the 18-cell / 36-parameter reproduction
# ======================================================================================
def grid(convention: str, k: int = K_DEFAULT) -> tuple[float, dict]:
    """RQ1: the full Table-6.9 gQLS grid. primary = mean |dtheta| over 36 parameters.

    Aux extras carry the two diagnostics the transcription flagged: the per-trim means
    (does one trim carry the error?) and the (0.10, 0.90) log-Gumbel mu, which Table 6.9
    prints as 22.34 and Table 6.10's g3 row prints as 22.36 for the SAME fit -- so the
    cell is scored against both, and the pair of deviations says which is the typo.
    """
    cells = gqls_grid(convention, k)
    primary, extra = _grid_stats(cells)

    gumbel = next(c for c in cells if c.trim == "0.10_0.90" and c.family == "log-gumbel")
    t610_g3_mu = float(tables()["table_6_10"]["estimators"]["g3"]["log-gumbel"]["mu"])
    conds = [c.fit.sigma_star_cond for c in cells if c.fit.sigma_star_cond is not None]

    extra |= {
        "gumbel_g3_mu_hat": float(gumbel.fit.mu),
        "gumbel_g3_dev_vs_table_6_9": float(gumbel.d_mu),
        "gumbel_g3_dev_vs_table_6_10": float(abs(gumbel.fit.mu - t610_g3_mu)),
        "gumbel_g3_typo_verdict": (
            "table_6_9_is_the_typo"
            if abs(gumbel.fit.mu - t610_g3_mu) < gumbel.d_mu
            else "table_6_10_is_the_outlier"
        ),
        "sigma_star_cond_max": float(max(conds)),
        "sigma_star_cond_max_family": max(
            (c for c in cells if c.fit.sigma_star_cond is not None),
            key=lambda c: c.fit.sigma_star_cond,
        ).family,
        "k": int(k),
        "fits": _fit_table(cells),
    }
    return primary, check_extra("reproduction", extra)


# ======================================================================================
# MODE: gof_redundancy -- RQ2, is the B=1000 bootstrap distinguishable from chi2_{r-2}?
# ======================================================================================
def gof_redundancy(convention: str, k: int = K_DEFAULT) -> tuple[float, dict]:
    """RQ2: ``W_out`` p-values under BOTH references, on the same 18 fits.

    The fits (and therefore the primary metric) are `grid`'s, unchanged -- this mode adds
    a second, independent measurement on top of them: for each cell, ``W_out`` priced by
    the thesis's parametric bootstrap (B=1000, fixed seed) AND by a chi2_{r-2} reference.
    If the two agree to well inside the reporting resolution, the bootstrap is redundant
    ON THIS DATA and the thesis's computational caution was unnecessary; if not, RQ2
    flips into a validation of their choice. Both outcomes are pre-registered.
    """
    cells = gqls_grid(convention, k)
    primary, extra = _grid_stats(cells)
    x = sample()

    rows: dict[str, dict] = {}
    gaps: list[float] = []
    match_ours = 0
    match_published_stat = 0
    for c in cells:
        chi2 = E.W_out(x, c.fit, r=R_OUT, mode="chi2")
        boot = E.W_out(
            x, c.fit, r=R_OUT, mode="bootstrap", B=BOOTSTRAP_B, seed=BOOTSTRAP_SEED
        )
        pub_p = float(c.published["p_Wout"])
        pub_stat = float(c.published["W_out"])
        # the transcription's own diagnostic: chi2_{r-2} survival of the PUBLISHED W_out
        p_of_published = float(st.chi2.sf(pub_stat, R_OUT - 2))
        gap = abs(boot["p_value"] - chi2["p_value"])
        gaps.append(gap)
        match_ours += int(abs(pub_p - chi2["p_value"]) <= REPORTING_RESOLUTION)
        match_published_stat += int(abs(pub_p - p_of_published) <= REPORTING_RESOLUTION)
        rows[f"{c.trim}/{c.family}"] = {
            "W_out": round(chi2["W_out"], 4),
            "pub_W_out": pub_stat,
            "p_chi2": round(chi2["p_value"], 4),
            "p_boot": round(boot["p_value"], 4),
            "pub_p": pub_p,
            "p_chi2_of_pub_W_out": round(p_of_published, 4),
        }

    gaps_arr = np.array(gaps, float)
    divergent = {
        "logistic_0.02_0.98": rows["0.02_0.98/log-logistic"],
        "laplace_0.10_0.90": rows["0.10_0.90/log-laplace"],
    }
    extra |= {
        "w_out_r": int(R_OUT),
        "w_out_bootstrap_B": int(BOOTSTRAP_B),
        "w_out_bootstrap_seed": int(BOOTSTRAP_SEED),
        "p_boot_vs_chi2_mean_abs": float(gaps_arr.mean()),
        "p_boot_vs_chi2_max_abs": float(gaps_arr.max()),
        "cells_pub_p_within_res_of_our_chi2": int(match_ours),
        "cells_pub_p_within_res_of_chi2_of_published_W": int(match_published_stat),
        # the two cells reference/thesis_tables.json flags as known divergences
        "divergent_logistic_02_98_pub_p": float(rows["0.02_0.98/log-logistic"]["pub_p"]),
        "divergent_logistic_02_98_p_chi2": float(rows["0.02_0.98/log-logistic"]["p_chi2"]),
        "divergent_logistic_02_98_p_boot": float(rows["0.02_0.98/log-logistic"]["p_boot"]),
        "divergent_laplace_10_90_pub_p": float(rows["0.10_0.90/log-laplace"]["pub_p"]),
        "divergent_laplace_10_90_p_chi2": float(rows["0.10_0.90/log-laplace"]["p_chi2"]),
        "divergent_laplace_10_90_p_boot": float(rows["0.10_0.90/log-laplace"]["p_boot"]),
        "divergent_cells": _json(divergent),
        "w_out_table": _json(rows),
    }
    return primary, check_extra("reproduction", extra)


# ======================================================================================
# MODE: oqls_mle_arms -- the Sigma-star falsifier
# ======================================================================================
def oqls_mle_arms(convention: str, k: int = K_DEFAULT) -> tuple[float, dict]:
    """Table 6.10's ORIGINAL rows: MLE, o2, o3 fitted here; g2, g3 read off `grid`.

    The single sharpest specification check in the study is the log-Cauchy sigma-hat at
    (0.05, 0.95): OLS on the quantile scale (which pretends Sigma_* = I) publishes 0.23,
    GLS through the true Sigma_* publishes 0.49. Reproducing BOTH sides of that 2.1x
    split is what proves eq. (2.1) is specified correctly; missing it means Sigma_* is
    wrong and the ladder stops (study.yaml predictions_to_falsify).

    primary stays `grid`'s -- the reproduction frontier is defined on Table 6.9 only.
    The starred (modified-data) rows of Table 6.10 are NOT touched here; they are sealed.
    """
    cells = gqls_grid(convention, k)
    primary, extra = _grid_stats(cells)
    x = sample()
    published = tables()["table_6_10"]["estimators"]

    grid_fits = {(c.a, c.b, c.family): c.fit for c in cells}
    arm_devs: dict[str, list[float]] = {}
    rows: dict[str, dict] = {}
    for arm, (_estimator, a, b) in ARMS.items():
        devs: list[float] = []
        for family in E.FAMILIES:
            fit = (
                grid_fits[(a, b, family)]
                if arm in {"g2", "g3"} and (a, b, family) in grid_fits
                else _fit_arm(x, arm, family, convention=convention, k=k)
            )
            pub = published[arm][family]
            d_mu = abs(fit.mu - float(pub["mu"]))
            d_sigma = abs(fit.sigma - float(pub["sigma"]))
            devs += [d_mu, d_sigma]
            rows[f"{arm}/{family}"] = {
                "mu": round(fit.mu, 6),
                "sigma": round(fit.sigma, 6),
                "pub_mu": pub["mu"],
                "pub_sigma": pub["sigma"],
            }
        arm_devs[arm] = devs

    all_devs = np.array([d for devs in arm_devs.values() for d in devs], float)
    o2_cauchy = _fit_arm(x, "o2", "log-cauchy", convention=convention, k=k)
    g2_cauchy = grid_fits[(0.05, 0.95, "log-cauchy")]
    pub_o2 = float(published["o2"]["log-cauchy"]["sigma"])
    pub_g2 = float(published["g2"]["log-cauchy"]["sigma"])

    extra |= {
        "t610_original_mean_abs_dev": float(all_devs.mean()),
        "t610_original_max_abs_dev": float(all_devs.max()),
        "t610_original_n_params": int(all_devs.size),
        **{
            f"t610_mean_abs_dev_arm_{arm.lower()}": float(np.mean(devs))
            for arm, devs in arm_devs.items()
        },
        # --- the Sigma-star falsifier pair ---
        "falsifier_o2_logcauchy_sigma": float(o2_cauchy.sigma),
        "falsifier_g2_logcauchy_sigma": float(g2_cauchy.sigma),
        "falsifier_published_o2_sigma": pub_o2,
        "falsifier_published_g2_sigma": pub_g2,
        "falsifier_o2_dev": float(abs(o2_cauchy.sigma - pub_o2)),
        "falsifier_g2_dev": float(abs(g2_cauchy.sigma - pub_g2)),
        "falsifier_ratio_ours": float(g2_cauchy.sigma / o2_cauchy.sigma),
        "falsifier_ratio_published": float(pub_g2 / pub_o2),
        "falsifier_verdict": (
            "sigma_star_reproduced"
            if max(abs(o2_cauchy.sigma - pub_o2), abs(g2_cauchy.sigma - pub_g2))
            <= REPORTING_RESOLUTION
            else "sigma_star_SUSPECT"
        ),
        "arm_table": _json(rows),
    }
    return primary, check_extra("reproduction", extra)


# ======================================================================================
# MODE: sensitivity -- which lever actually moves the estimates?
# ======================================================================================
def sensitivity(convention: str, k: int = K_DEFAULT) -> tuple[float, dict]:
    """Two nuisance levers, measured against the 0.005 reporting resolution.

    * ``k in {8, 10, 15, 25}`` at (0.05, 0.95): the number of quantile levels. Predicted
      to move estimates by LESS than the resolution -- k is a nuisance, not a finding.
    * the five sample-quantile CONVENTIONS at k = 8: predicted to move them by much MORE.
      At n = 30 the definition of "the empirical quantile" is the dominant reproduction
      uncertainty; that is the pre-registered claim this mode either confirms or kills.

    primary stays `grid`'s (this mode adds measurements, not a different fit target).
    """
    cells = gqls_grid(convention, k)
    primary, extra = _grid_stats(cells)
    x = sample()

    k_values = (8, 10, 15, 25)
    k_moves: dict[str, float] = {}
    k_moves_coarse: dict[str, float] = {}
    k_rows: dict[str, dict] = {}
    for family in E.FAMILIES:
        fits = {
            kk: E.gqls(x, 0.05, 0.95, kk, family, method=convention) for kk in k_values
        }
        base = fits[K_DEFAULT]
        def _move(f: E.Fit, base: E.Fit = base) -> float:
            return max(abs(f.mu - base.mu), abs(f.sigma - base.sigma))

        k_moves[family] = max(_move(f) for f in fits.values())
        # k = 25 on n = 30 asks for more distinct quantile levels than the sample can
        # resolve (levels collapse onto repeated order statistics), so it is reported
        # separately rather than allowed to speak for "k sensitivity" as a whole.
        k_moves_coarse[family] = max(_move(f) for kk, f in fits.items() if kk <= 15)
        k_rows[family] = {
            str(kk): [round(f.mu, 6), round(f.sigma, 6)] for kk, f in fits.items()
        }

    conv_moves: dict[str, float] = {}
    conv_rows: dict[str, dict] = {}
    # "linear" (numpy's default) is measured too — it is the convention a reimplementer
    # gets by accident, and research_plan.md names it in the convention list.
    all_conventions = (*CONVENTIONS, "linear")
    for family in E.FAMILIES:
        fits = {
            conv: E.gqls(x, 0.05, 0.95, K_DEFAULT, family, method=conv)
            for conv in all_conventions
        }
        mus = np.array([f.mu for f in fits.values()], float)
        sigmas = np.array([f.sigma for f in fits.values()], float)
        conv_moves[family] = float(max(np.ptp(mus), np.ptp(sigmas)))
        conv_rows[family] = {
            conv: [round(f.mu, 6), round(f.sigma, 6)] for conv, f in fits.items()
        }

    max_k = float(max(k_moves.values()))
    max_k_coarse = float(max(k_moves_coarse.values()))
    max_conv = float(max(conv_moves.values()))
    extra |= {
        "max_param_movement_across_k": max_k,
        "max_param_movement_across_k_family": max(k_moves, key=k_moves.get),
        "max_param_movement_across_k_le15": max_k_coarse,
        "max_param_movement_across_k_le15_family": max(k_moves_coarse, key=k_moves_coarse.get),
        "k_movement_within_resolution": int(max_k <= REPORTING_RESOLUTION),
        "k_le15_movement_within_resolution": int(max_k_coarse <= REPORTING_RESOLUTION),
        "max_param_movement_across_conventions": max_conv,
        "max_param_movement_across_conventions_family": max(conv_moves, key=conv_moves.get),
        "convention_movement_over_resolution_x": float(max_conv / REPORTING_RESOLUTION),
        "convention_dominates_k": int(max_conv > max_k),
        "k_values": _json(list(k_values)),
        "conventions": _json(list(all_conventions)),
        "k_table": _json(k_rows),
        "convention_table": _json(conv_rows),
    }
    return primary, check_extra("reproduction", extra)


# ======================================================================================
# The decision track
# ======================================================================================
def decision_fitter(
    estimator: str, family: str, trim: tuple[float, float], convention: str, k: int
) -> Callable[[np.ndarray], E.Fit]:
    a, b = trim
    if estimator == "mle":
        return lambda s: E.mle(s, family)
    if estimator == "gqls":
        return lambda s: E.gqls(s, a, b, k, family, method=convention)
    if estimator == "oqls":
        return lambda s: E.oqls(s, a, b, k, family, method=convention)
    raise ValueError(f"estimator must be mle|gqls|oqls, got {estimator!r}")


def _w_for(
    x: np.ndarray, fit: E.Fit, trim: tuple[float, float], convention: str, k: int
) -> dict:
    """``W`` on the estimation grid. MLE has no grid of its own, so the trim supplies it.

    The thesis derives W's chi2_{k-2} calibration for gQLS only; for an MLE or oQLS fit
    the statistic is still the study's declared GoF guardrail, and ``w_chi2_calibrated``
    records that the calibration is borrowed.
    """
    return E.W(x, fit, a=trim[0], b=trim[1], k=k, method=convention, quantile_space="log")


def _return_levels_bn(fit: E.Fit) -> dict[str, float]:
    return {label: E.return_level(fit, p) / 1e9 for label, p, _ in RETURN_PERIODS}


def decision(
    estimator: str,
    family: str,
    trim: tuple[float, float],
    convention: str = E.THESIS_QUANTILE_METHOD,
    k: int = K_DEFAULT,
) -> tuple[float, dict]:
    """RQ5/RQ6: how much does the fitted 1-in-100 event loss move under stress?

    primary = ``instability_pct`` = MAX over the adaptive stress set of the absolute
    percentage change in the 1-in-100 return level, relative to the clean fit. A max, not
    a mean: a reinsurance attachment point is set once, and it is the worst plausible
    perturbation that decides whether the layer is mispriced.

    Adaptive stress set (4 cases): leave-top-1/2/3-out plus a **5x** gross-error inflation
    of the maximum. The thesis's own 10x is sealed -- see :func:`sealed_decision`.

    Guardrail ``w_pvalue`` is the in-sample GoF p-value of the CLEAN fit: the question is
    "among models that FIT, which gives the most stable 1-in-100", so a model that
    predicts nothing may not win by being unfalsifiable.
    """
    x = sample()
    fits_fn = decision_fitter(estimator, family, trim, convention, k)
    clean = fits_fn(x)
    w = _w_for(x, clean, trim, convention, k)
    cases = S.default_stress_set(x, inflate_factors=(ADAPTIVE_INFLATE_FACTOR,))
    out = S.instability_pct(fits_fn, x, cases, p=0.99)

    levels = _return_levels_bn(clean)
    extra = {
        "w_pvalue": float(w["p_value"]),  # <- the decision track's guardrail
        "w_statistic": float(w["W"]),
        "w_df": int(w["df"]),
        "w_chi2_calibrated": int(bool(w["chi2_calibrated"])),
        "estimator": estimator,
        "family": family,
        "trim": f"{trim[0]}_{trim[1]}",
        "k": int(k),
        "breakdown_point": float(E.breakdown_point(*trim)),
        "mu_hat": float(clean.mu),
        "sigma_hat": float(clean.sigma),
        "return_level_1in10_bn": float(levels["1in10"]),
        "return_level_1in25_bn": float(levels["1in25"]),
        "return_level_1in100_bn": float(levels["1in100"]),
        "return_level_support_caveat": SUPPORT_CAVEAT,
        "baseline_return_level_bn": float(out["baseline_return_level"] / 1e9),
        "worst_case": out["worst_case"],
        "n_stress_cases": int(out["n_cases"]),
        "stress_inflate_factor": float(ADAPTIVE_INFLATE_FACTOR),
    }
    for label, row in out["per_case"].items():
        extra[f"pct_change_{label}"] = float(row["pct_change"])
        extra[f"rl_bn_{label}"] = float(row["return_level"] / 1e9)
    extra["stress_table"] = _json(
        {
            label: {
                "return_level_bn": round(row["return_level"] / 1e9, 6),
                "pct_change": round(row["pct_change"], 6),
            }
            for label, row in out["per_case"].items()
        }
    )
    if family in {"log-cauchy"}:
        extra["moment_note"] = (
            "log-Cauchy has NO finite moments: mean_loss() and cte() raise "
            "NotImplementedError by design, so this family can only ever be priced "
            "through QUANTILES — any mean/CTE/TVaR number for it is a truncation artifact"
        )
    return float(out["instability_pct"]), check_extra("decision", extra)


# ======================================================================================
# SEALED modes -- one access per track, via `klein run-one --final-test`
# ======================================================================================
def _sealed_sample() -> np.ndarray:
    """The thesis's exact modification: 72.303 -> 723.03 BILLIONS, i.e. +log(10) in logs.

    ``stress.inflate_max`` takes a DOLLAR-scale factor on a LOG-dollar sample, and the
    prepared column is ``log(damage_bn_1995 * 1e9)`` -- so a 10x factor lands the maximum
    exactly on ``log(723.03e9)``. Asserted here rather than assumed.
    """
    modified = S.inflate_max(sample(), SEALED_INFLATE_FACTOR)
    top_bn = float(np.exp(modified.max()) / 1e9)
    if abs(top_bn - 723.03) > 1e-6:
        raise RuntimeError(
            f"sealed modification landed at {top_bn:.6f}bn, not 723.03bn — unit drift "
            "between damage_bn_1995 and the log-dollar fitting column"
        )
    return modified


def sealed_repro(convention: str, k: int = K_DEFAULT) -> tuple[float, dict]:
    """CONFIRMATION: the FULL Table 6.10 grid -- 5 arms x 6 families x {original, 10x}.

    primary = mean |dtheta| over all 120 published parameters.

    Guardrail scope note: Table 6.10 publishes only ``(mu, sigma)`` -- no ``W``/``p_W``
    columns exist for its 60 cells. ``max_abs_w_deviation`` / ``max_abs_p_deviation`` are
    therefore measured where the thesis actually publishes them (Table 6.9's 18 gQLS
    cells, original data), and ``w_p_deviation_scope`` records that. Inventing a W
    comparison against unpublished quantities would be a fabricated guardrail.
    """
    x_original = sample()
    x_modified = _sealed_sample()
    published = tables()["table_6_10"]["estimators"]

    devs: list[float] = []
    per_arm: dict[str, list[float]] = {}
    rows: dict[str, dict] = {}
    for arm in ARMS:
        for suffix, data in (("", x_original), ("*", x_modified)):
            key = arm + suffix
            block: list[float] = []
            for family in E.FAMILIES:
                fit = _fit_arm(data, arm, family, convention=convention, k=k)
                pub = published[key][family]
                d_mu = abs(fit.mu - float(pub["mu"]))
                d_sigma = abs(fit.sigma - float(pub["sigma"]))
                block += [d_mu, d_sigma]
                rows[f"{key}/{family}"] = {
                    "mu": round(fit.mu, 6),
                    "sigma": round(fit.sigma, 6),
                    "pub_mu": pub["mu"],
                    "pub_sigma": pub["sigma"],
                }
            per_arm[key] = block
            devs += block

    dev_arr = np.array(devs, float)
    cells = gqls_grid(convention, k)
    w_devs = np.array([c.d_w for c in cells], float)
    p_devs = np.array([c.d_p for c in cells], float)

    worst_key = max(rows, key=lambda kk: max(
        abs(rows[kk]["mu"] - rows[kk]["pub_mu"]), abs(rows[kk]["sigma"] - rows[kk]["pub_sigma"])
    ))
    extra = {
        "max_abs_param_deviation": float(dev_arr.max()),
        "max_abs_w_deviation": float(w_devs.max()),
        "max_abs_p_deviation": float(p_devs.max()),
        "w_p_deviation_scope": (
            "Table 6.9's 18 gQLS cells on ORIGINAL data — Table 6.10 publishes no W/p_W "
            "columns, so no 60-cell W comparison exists to measure"
        ),
        "n_cells": len(rows),
        "n_params": int(dev_arr.size),
        "params_within_resolution": int(np.sum(dev_arr <= REPORTING_RESOLUTION)),
        "worst_cell": worst_key,
        **{
            f"mean_abs_dev_arm_{kk.replace('*', '_star').lower()}": float(np.mean(v))
            for kk, v in per_arm.items()
        },
        "sealed_modification": "72.303bn -> 723.03bn (single largest observation x10)",
        "sealed_top_bn": float(np.exp(x_modified.max()) / 1e9),
        "k": int(k),
        "grid_table": _json(rows),
    }
    return float(dev_arr.mean()), check_extra("reproduction", extra)


def sealed_decision(
    estimator: str,
    family: str,
    trim: tuple[float, float],
    convention: str = E.THESIS_QUANTILE_METHOD,
    k: int = K_DEFAULT,
) -> tuple[float, dict]:
    """CONFIRMATION: the incumbent decision config under ONLY the exact 10x modification.

    primary = |%delta| of the 1-in-100 return level, modified vs clean. One perturbation,
    the thesis's own, pre-registered before any adaptive decision run.
    """
    x = sample()
    x_modified = _sealed_sample()
    fits_fn = decision_fitter(estimator, family, trim, convention, k)
    clean = fits_fn(x)
    modified = fits_fn(x_modified)
    w = _w_for(x, clean, trim, convention, k)

    rl_clean = E.return_level(clean, 0.99)
    rl_modified = E.return_level(modified, 0.99)
    pct = float(100.0 * abs(rl_modified - rl_clean) / rl_clean)

    levels_clean = _return_levels_bn(clean)
    levels_modified = _return_levels_bn(modified)
    extra = {
        "w_pvalue": float(w["p_value"]),  # <- guardrail, from the CLEAN fit
        "w_statistic": float(w["W"]),
        "w_chi2_calibrated": int(bool(w["chi2_calibrated"])),
        "estimator": estimator,
        "family": family,
        "trim": f"{trim[0]}_{trim[1]}",
        "k": int(k),
        "return_level_1in100_clean_bn": float(rl_clean / 1e9),
        "return_level_1in100_modified_bn": float(rl_modified / 1e9),
        "return_level_1in10_clean_bn": float(levels_clean["1in10"]),
        "return_level_1in10_modified_bn": float(levels_modified["1in10"]),
        "return_level_1in25_clean_bn": float(levels_clean["1in25"]),
        "return_level_1in25_modified_bn": float(levels_modified["1in25"]),
        "return_level_support_caveat": SUPPORT_CAVEAT,
        "mu_hat_clean": float(clean.mu),
        "sigma_hat_clean": float(clean.sigma),
        "mu_hat_modified": float(modified.mu),
        "sigma_hat_modified": float(modified.sigma),
        "sealed_modification": "72.303bn -> 723.03bn (single largest observation x10)",
    }
    if family in {"log-cauchy"}:
        extra["moment_note"] = (
            "log-Cauchy has NO finite moments: mean_loss()/cte() raise by design; this "
            "family is priced through QUANTILES only"
        )
    return pct, check_extra("decision", extra)


#: mode name -> callable. train.py dispatches through this, so an unknown MODE is a
#: loud KeyError before any fitting rather than a silent no-op.
MODES: dict[str, Callable[..., tuple[float, dict]]] = {
    "anchor": anchor,
    "grid": grid,
    "gof_redundancy": gof_redundancy,
    "oqls_mle_arms": oqls_mle_arms,
    "sensitivity": sensitivity,
    "decision": decision,
    "sealed_repro": sealed_repro,
    "sealed_decision": sealed_decision,
}
