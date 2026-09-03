"""Stable machinery for study 10 — NOT the per-experiment mutable surface.

`study.yaml:entrypoint.mutable` names `analyze.py` and nothing else. This module
is library code: it is written once, complete, before E0001, and it changes only
rarely and deliberately (never as part of a cell's diff). Each cell composes the
primitives below and prints its own block, so the per-experiment diff is always a
MEASUREMENT and never a new method.

What lives here, and why it is here rather than in `analyze.py`:

* **Block access and the seal.** `load_block()` is the single door to the data.
  It resolves the two bundled members from the CONTRACT (never a hardcoded
  path), refuses the sealed block outside a `--final-test` run, honours
  `KLEIN_SEALED_DRYRUN`, drops Table 2's forbidden derived columns, and prints
  the `split_fingerprint:` line the notary reads. One door means the seal and
  the column exclusion cannot be forgotten by a cell.
* **The four estimators** of K, written from scratch on numpy normal equations
  (`method_card.md` §3), plus the bootstrap, the jackknife and the analytic
  slope standard error.
* **The distance modulus**, used by the Table-1 magnitude cell and by the sealed
  Table-2 cell — the same function, so the sealed run rehearses on development
  data exactly what it will do on the sealed rows.
* **The declared DGP** and the two coverage experiments.
* **`write_table()`**, so every pinned `artifact:` is written the same way
  (deterministic column order, fixed float formatting, LF endings) and a
  re-run hashes identically.

Nothing here reads `program.md`, `playbook.md` or any run's result.
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from kleinlib.contract import load_contract
from kleinlib.data import SEALED_DRYRUN_KEY, SPLIT_FINGERPRINT_KEY, split_fingerprint
from kleinlib.sources import resolve

# --------------------------------------------------------------------------
# Published quantities this study aims at. Every one of them is a number the
# 1929 paper (or the modern literature) PRINTS; none is a measurement of ours.
# Sources are in `references.yaml`; the tolerances are registered in
# `study.yaml:predictions`.
# --------------------------------------------------------------------------

#: Hubble's constant from the 24 individual objects, with his probable error.
HUBBLE_K_24: float = 465.0
HUBBLE_PE_24: float = 50.0

#: Hubble's constant from the same objects aggregated into nine groups.
HUBBLE_K_9GROUP: float = 513.0
HUBBLE_PE_9GROUP: float = 60.0

#: The value Hubble ADOPTED when he turned Table 2's velocities into distances.
HUBBLE_ADOPTED_K: float = 500.0

#: The modern Hubble constant, to the round figure this study compares against.
MODERN_H0: float = 70.0

#: The mean absolute magnitude Hubble printed under Table 2.
TABLE2_MEAN_ABS_MAG: float = -15.3

#: Table 1's published column sums and both row counts — the identity anchor.
ANCHOR_SUM_R: float = 21.873
ANCHOR_SUM_V: float = 8955.0
ANCHOR_N_TABLE1: int = 24
ANCHOR_N_TABLE2: int = 22

#: Table 2 columns no cell of this study may read, sealed or not.
#: `r_mpc` there was computed FROM the velocity with `HUBBLE_ADOPTED_K`, so it
#: cannot be evidence about K; `vs_kms` is tied to it by an exact identity; and
#: `M_t` is the printed answer itself. `load_block("table2")` drops all three.
TABLE2_FORBIDDEN_COLUMNS: tuple[str, ...] = ("r_mpc", "vs_kms", "M_t")

BLOCK_TABLE1 = "table1"
BLOCK_TABLE2 = "table2"


# --------------------------------------------------------------------------
# Study location and contract
# --------------------------------------------------------------------------


def study_dir() -> Path:
    """This study's directory — the parent of `lib/`."""
    return Path(__file__).resolve().parent.parent


def contract() -> Mapping[str, Any]:
    """`study.yaml`, loaded. Every constant a cell needs comes from here."""
    return load_contract(study_dir())


def simulation_spec() -> Mapping[str, Any]:
    """The declared DGP block of the contract (`study.yaml:simulation`)."""
    spec = contract().get("simulation")
    if not isinstance(spec, Mapping):
        raise RuntimeError("study.yaml:simulation is required for the simulate track")
    return spec


def sealed_lock() -> Mapping[str, Any]:
    """The prospective analysis lock (`study.yaml:sealed_lock`)."""
    lock = contract().get("sealed_lock")
    if not isinstance(lock, Mapping):
        raise RuntimeError("study.yaml:sealed_lock is required")
    return lock


# --------------------------------------------------------------------------
# Data: prepare-time resolution, run-time block access, the seal
# --------------------------------------------------------------------------


def resolve_table(which: str) -> tuple[Path, str]:
    """Resolve one bundled member from the contract; return (path, sha256).

    `which` is "table1" or "table2". Reads `data.source` / `data.source_table2`
    — the tags are in the hashed contract, so no path is hardcoded anywhere in
    this study. Prints the engine's `data source:` provenance line.
    """
    data = contract().get("data")
    if not isinstance(data, Mapping):
        raise RuntimeError("study.yaml:data is required")
    key = {"table1": "source", "table2": "source_table2"}[which]
    tag = data.get(key)
    if not isinstance(tag, str) or not tag:
        raise RuntimeError(f"study.yaml:data.{key} is required")
    resolved = resolve(
        tag,
        study_dir=study_dir(),
        offline=os.environ.get("KLEIN_OFFLINE") == "1",
    )
    if resolved.path is None or resolved.digest is None:
        raise RuntimeError(f"{tag!r} did not resolve to a file with a digest")
    return resolved.path, resolved.digest


def prepared_frame() -> pd.DataFrame:
    """The prepared artifact `prepare.py` wrote, as a faithful union of both tables."""
    path = study_dir() / str(contract()["data"]["prepared_path"])
    frame = pd.read_csv(path)
    return frame


def block_fingerprint(frame: pd.DataFrame) -> str:
    """The realized-membership fingerprint of one block, from its `object_id`s.

    Uses `kleinlib.data.split_fingerprint`, the same order-insensitive hash the
    engine uses for a row partition, over the block's stable object ids rather
    than over a positional index — so it survives a re-read in any row order and
    a stranger recomputes it from the contract plus the bytes.
    """
    return split_fingerprint(np.asarray(frame["object_id"], dtype=object))


def load_block(
    name: str,
    *,
    echo: bool = True,
) -> pd.DataFrame:
    """THE single door to this study's data. Returns one block; enforces the seal.

    * `name="table1"` — the development block, Hubble's 24 objects. Always
      readable.
    * `name="table2"` — the SEALED block, Hubble's 22 nebulae. Readable only
      when `klein run-one --final-test` set `KLEIN_EVALUATION_KIND=final_test`;
      any other context raises. `TABLE2_FORBIDDEN_COLUMNS` are dropped before
      the frame is returned, so a cell cannot read a column derived from K.

    Under `KLEIN_SEALED_DRYRUN=1` a request for the sealed block is answered
    with the DEVELOPMENT block and a printed `sealed_dryrun: 1` line — the same
    contract `kleinlib.data.load_partition` implements. The rehearsal therefore
    exercises the whole path (Table 1 carries `v_kms` and `m_t` too, the only
    two columns the sealed statistic uses) and spends nothing. The forbidden
    columns are dropped on a dry run as well, because they are dropped by what
    was REQUESTED rather than by what was served: the rehearsal must hand the
    cell the same SHAPE the real run will.

    Prints `split_fingerprint:` for the block actually returned.
    """
    if name not in (BLOCK_TABLE1, BLOCK_TABLE2):
        raise ValueError(f"unknown block {name!r} — use {BLOCK_TABLE1!r} or {BLOCK_TABLE2!r}")

    dry_run = name == BLOCK_TABLE2 and os.environ.get("KLEIN_SEALED_DRYRUN") == "1"
    if name == BLOCK_TABLE2 and not dry_run:
        evaluation_kind = os.environ.get("KLEIN_EVALUATION_KIND")
        if evaluation_kind != "final_test":
            raise RuntimeError(
                "the sealed block (Table 2) is readable only inside "
                "`klein run-one --final-test`; this run has "
                f"KLEIN_EVALUATION_KIND={evaluation_kind!r}. The seal is a "
                "prospective analysis lock (study.yaml:sealed_lock) and it is "
                "spent exactly once."
            )

    served = BLOCK_TABLE1 if dry_run else name
    frame = prepared_frame()
    block = frame[frame["block"] == served].reset_index(drop=True)
    if block.empty:
        raise RuntimeError(f"the prepared artifact carries no rows for block {served!r}")
    # Drop by what was REQUESTED, not by what was served. Under a dry run the
    # rows come from Table 1, but the cell being rehearsed is the sealed one and
    # its column contract must be rehearsed too: a frame with different columns
    # is a different code path, and the rehearsal exists to exercise the real
    # one. (The mandatory dry-run caught exactly this: Table 1's rows carry
    # r_mpc / vs_kms / M_t in the prepared union, so the sealed cell's own guard
    # fired during the rehearsal and the seal stayed intact.)
    if name == BLOCK_TABLE2:
        block = block.drop(columns=[c for c in TABLE2_FORBIDDEN_COLUMNS if c in block.columns])
    if echo:
        print(f"{SPLIT_FINGERPRINT_KEY}: {block_fingerprint(block)}")
    if dry_run:
        # Never silenced by `echo`: `klein run-one --final-test --dry-run` reads
        # the ABSENCE of this line as "the entrypoint would have read the sealed
        # rows" and exits 3.
        print(f"{SEALED_DRYRUN_KEY}: 1")
    return block


# --------------------------------------------------------------------------
# The estimators — from scratch on normal equations (method_card.md §3)
# --------------------------------------------------------------------------


def ols_through_origin(r: np.ndarray, v: np.ndarray) -> float:
    """K0 = sum(r*v) / sum(r*r) — the one-parameter fit v = K r."""
    r = np.asarray(r, dtype=float)
    v = np.asarray(v, dtype=float)
    return float(np.dot(r, v) / np.dot(r, r))


def ols_free_intercept(r: np.ndarray, v: np.ndarray) -> tuple[float, float]:
    """(K1, c) for the two-parameter fit v = K r + c, by normal equations."""
    r = np.asarray(r, dtype=float)
    v = np.asarray(v, dtype=float)
    n = r.size
    design = np.column_stack([r, np.ones(n)])
    gram = design.T @ design
    moment = design.T @ v
    slope, intercept = np.linalg.solve(gram, moment)
    return float(slope), float(intercept)


def inverse_regression_k(r: np.ndarray, v: np.ndarray) -> float:
    """K from regressing r on v and inverting: 1 / slope(r ~ v).

    The forward fit v ~ r assumes the DISTANCES are error-free; the inverse fit
    assumes the VELOCITIES are. Real data has error in both, so the two bracket
    the truth and their gap measures how much the choice of response matters.
    """
    r = np.asarray(r, dtype=float)
    v = np.asarray(v, dtype=float)
    n = v.size
    design = np.column_stack([v, np.ones(n)])
    slope, _intercept = np.linalg.solve(design.T @ design, design.T @ r)
    return float(1.0 / slope)


def r_squared(r: np.ndarray, v: np.ndarray, predicted: np.ndarray) -> float:
    """Ordinary R^2 of a prediction of v."""
    v = np.asarray(v, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    residual = float(np.sum((v - predicted) ** 2))
    total = float(np.sum((v - v.mean()) ** 2))
    return float(1.0 - residual / total)


def residual_sd_free_intercept(r: np.ndarray, v: np.ndarray) -> float:
    """Residual standard deviation of the free-intercept fit (n - 2 degrees of freedom)."""
    r = np.asarray(r, dtype=float)
    v = np.asarray(v, dtype=float)
    slope, intercept = ols_free_intercept(r, v)
    residual = v - (slope * r + intercept)
    return float(np.sqrt(np.sum(residual**2) / (r.size - 2)))


def analytic_slope_se(r: np.ndarray, v: np.ndarray) -> float:
    """Textbook standard error of the free-intercept OLS slope."""
    r = np.asarray(r, dtype=float)
    sigma = residual_sd_free_intercept(r, v)
    return float(sigma / np.sqrt(np.sum((r - r.mean()) ** 2)))


def probable_error(standard_error: float) -> float:
    """The 1929 convention: probable error = 0.6745 x standard error."""
    return float(0.6745 * standard_error)


# --------------------------------------------------------------------------
# Uncertainty — bootstrap and jackknife
# --------------------------------------------------------------------------


def bootstrap_k(
    r: np.ndarray,
    v: np.ndarray,
    *,
    n_boot: int,
    seed: int,
    estimator: str = "free",
) -> np.ndarray:
    """`n_boot` resampled values of K, by case resampling of the (r, v) pairs.

    `estimator` is "free" (free-intercept OLS), "origin" (through the origin) or
    "inverse" (inverse regression). Case resampling is the honest bootstrap here:
    the design points are a SAMPLE of galaxies, not a fixed grid the observer
    chose, so resampling galaxies is resampling the thing that varies.
    """
    r = np.asarray(r, dtype=float)
    v = np.asarray(v, dtype=float)
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, r.size, size=(int(n_boot), r.size))
    return k_of_batch(r[draws], v[draws], estimator)


def paired_bootstrap_k(
    r: np.ndarray,
    v: np.ndarray,
    *,
    n_boot: int,
    seed: int,
    estimators: Sequence[str],
) -> dict[str, np.ndarray]:
    """Several estimators on the SAME resamples — common random numbers.

    A paired comparison needs both estimators to see identical rows on every
    draw; drawing twice would add independent noise to the difference and
    inflate its standard error.
    """
    r = np.asarray(r, dtype=float)
    v = np.asarray(v, dtype=float)
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, r.size, size=(int(n_boot), r.size))
    R, V = r[draws], v[draws]
    return {name: k_of_batch(R, V, name) for name in estimators}


def k_of(r: np.ndarray, v: np.ndarray, estimator: str) -> float:
    """One estimator by name — the single dispatch every bootstrap goes through."""
    if estimator == "origin":
        return ols_through_origin(r, v)
    if estimator == "free":
        return ols_free_intercept(r, v)[0]
    if estimator == "inverse":
        return inverse_regression_k(r, v)
    raise ValueError(f"unknown estimator {estimator!r}")


def k_of_batch(R: np.ndarray, V: np.ndarray, estimator: str) -> np.ndarray:
    """`k_of` for a whole stack of resamples at once — the SAME normal equations.

    `R` and `V` are `(B, n)`: one resampled dataset per row. Solving a 2x2
    system per row in a Python loop costs a second per thousand resamples, and
    the simulate track needs a million of them, so the closed form of the same
    normal equations is written out here:

        free     slope = (n*Srv - Sr*Sv) / (n*Srr - Sr^2)
        origin   slope = Srv / Srr
        inverse  1 / [(n*Srv - Sr*Sv) / (n*Svv - Sv^2)]     (r on v, inverted)

    Identical algebra to `ols_free_intercept` / `ols_through_origin` /
    `inverse_regression_k`, so a cell can use either path; the batch one exists
    only so a 1000-replicate coverage study fits inside `max_run_seconds`.
    """
    R = np.asarray(R, dtype=float)
    V = np.asarray(V, dtype=float)
    n = R.shape[1]
    sr = R.sum(axis=1)
    sv = V.sum(axis=1)
    srv = (R * V).sum(axis=1)
    if estimator == "origin":
        return srv / (R * R).sum(axis=1)
    if estimator == "free":
        return (n * srv - sr * sv) / (n * (R * R).sum(axis=1) - sr * sr)
    if estimator == "inverse":
        return 1.0 / ((n * srv - sr * sv) / (n * (V * V).sum(axis=1) - sv * sv))
    raise ValueError(f"unknown estimator {estimator!r}")


def percentile_ci(values: np.ndarray, level: float = 0.95) -> tuple[float, float]:
    """The percentile-bootstrap interval at `level`."""
    values = np.asarray(values, dtype=float)
    alpha = (1.0 - float(level)) / 2.0
    low, high = np.quantile(values, [alpha, 1.0 - alpha])
    return float(low), float(high)


def jackknife_k(r: np.ndarray, v: np.ndarray, estimator: str = "free") -> np.ndarray:
    """Leave-one-out values of K — one per object."""
    r = np.asarray(r, dtype=float)
    v = np.asarray(v, dtype=float)
    n = r.size
    out = np.empty(n, dtype=float)
    for i in range(n):
        keep = np.ones(n, dtype=bool)
        keep[i] = False
        out[i] = k_of(r[keep], v[keep], estimator)
    return out


def jackknife_se(values: np.ndarray) -> float:
    """Standard error from leave-one-out values."""
    values = np.asarray(values, dtype=float)
    n = values.size
    return float(np.sqrt((n - 1) / n * np.sum((values - values.mean()) ** 2)))


# --------------------------------------------------------------------------
# Photometry — the distance modulus, used on both blocks
# --------------------------------------------------------------------------


def absolute_magnitude(apparent: np.ndarray, distance_mpc: np.ndarray) -> np.ndarray:
    """M = m - 5 log10(r) - 25, with r in Mpc (the standard modulus in megaparsecs).

    The same function serves the Table-1 reproduction cell (against the paper's
    printed `M_t`) and the sealed Table-2 cell (against the paper's printed
    mean). Sharing it is what makes the development cell a genuine rehearsal of
    the sealed one.
    """
    apparent = np.asarray(apparent, dtype=float)
    distance_mpc = np.asarray(distance_mpc, dtype=float)
    return apparent - 5.0 * np.log10(distance_mpc) - 25.0


# --------------------------------------------------------------------------
# The declared DGP and the coverage experiments (simulate track)
# --------------------------------------------------------------------------


def simulate_velocities(
    r: np.ndarray, *, k_true: float, sigma: float, rng: np.random.Generator
) -> np.ndarray:
    """One synthetic dataset: v = k_true * r + Normal(0, sigma) at the given design points."""
    r = np.asarray(r, dtype=float)
    return k_true * r + rng.normal(0.0, sigma, size=r.size)


def coverage_experiment(
    r: np.ndarray,
    *,
    k_true: float,
    sigma: float,
    n_rep: int,
    seed: int,
    method: str,
    n_boot: int = 0,
    level: float = 0.95,
) -> dict[str, float]:
    """Coverage of an interval for K under the declared DGP.

    `method` is "analytic" (the textbook slope interval, normal quantiles) or
    "bootstrap" (the percentile bootstrap the estimate track actually uses).
    Returns coverage, the mean estimate, the bias and the mean interval width.
    """
    r = np.asarray(r, dtype=float)
    rng = np.random.default_rng(seed)
    z = 1.959963984540054  # the two-sided 95% normal quantile
    covered = 0
    estimates = np.empty(int(n_rep), dtype=float)
    widths = np.empty(int(n_rep), dtype=float)
    for i in range(int(n_rep)):
        v = simulate_velocities(r, k_true=k_true, sigma=sigma, rng=rng)
        slope, _intercept = ols_free_intercept(r, v)
        estimates[i] = slope
        if method == "analytic":
            se = analytic_slope_se(r, v)
            low, high = slope - z * se, slope + z * se
        elif method == "bootstrap":
            draws = rng.integers(0, r.size, size=(int(n_boot), r.size))
            values = k_of_batch(r[draws], v[draws], "free")
            low, high = percentile_ci(values, level)
        else:
            raise ValueError(f"unknown interval method {method!r}")
        widths[i] = high - low
        if low <= k_true <= high:
            covered += 1
    n = float(n_rep)
    return {
        "coverage": covered / n,
        "mean_k_hat": float(estimates.mean()),
        "bias": float(estimates.mean() - k_true),
        "mean_ci_width": float(widths.mean()),
        "n_rep": float(n_rep),
    }


# --------------------------------------------------------------------------
# Artifacts — one writer, so every pinned table re-hashes identically
# --------------------------------------------------------------------------


def write_table(
    relative_path: str,
    columns: Sequence[str],
    rows: Iterable[Mapping[str, Any]],
    *,
    float_format: str = "%.6f",
) -> Path:
    """Write a pinned `artifact:` table deterministically; return its path.

    Fixed column order, fixed float formatting, LF endings, no index — so a
    re-execution in a detached worktree produces byte-identical bytes and
    `klein replicate` can compare hashes rather than hope.

    Under ``KLEIN_SMOKE=1`` the text is still BUILT (so a formatting bug is
    caught by the sanctioned pre-run check) but not written: a smoke run writes
    no sidecars or snapshots, and `evaluate_table` treats the absent artifact as
    a notice rather than an error. That also keeps the working tree clean, which
    `klein run-one` requires.
    """
    path = study_dir() / relative_path
    frame = pd.DataFrame(list(rows), columns=list(columns))
    text = frame.to_csv(index=False, sep="\t", float_format=float_format, lineterminator="\n")
    if os.environ.get("KLEIN_SMOKE") == "1":
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="")
    return path
