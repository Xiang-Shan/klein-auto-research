"""DATA-gate measurements the bundled profiler does not make — re-runnable.

Not the mutable surface and not a cell: this is Gate-1 work, run once before the
gate is recorded and re-runnable by anyone auditing `data_card.md`. It prints
five things the card quotes verbatim:

1. **Block fingerprints.** `split.kind: none` means `contract_split` cannot
   realize partitions, so the DATA gate registers none and `run-one` prints
   `note: partition not verified`. These two digests are what a stranger
   recomputes instead, from the contract plus the bytes.
2. **The value-pattern check** (war story 1): what every column REALLY holds,
   read off the values, never off `dtype`.
3. **The Table-2 derived-column identity** — leakage row 1's mechanized
   evidence that `r_mpc` there was computed FROM the velocity with Hubble's
   adopted K, and is therefore forbidden to every cell.
4. **The DGP calibration**: the residual scatter of Table 1 around its
   free-intercept fit, which is `sigma` on the DGP card.
5. **Leakage row 4 by hand** — the audit reports N/A for a study with no
   scorable development partition and asks for row 4 "from the study's own
   evaluation path". Here it is: a no-information control that permutes the
   velocities against the distances and checks the fitted K collapses.

    uv run --locked python -u data_gate_profile.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.hubble import (  # noqa: E402
    BLOCK_TABLE1,
    BLOCK_TABLE2,
    HUBBLE_ADOPTED_K,
    block_fingerprint,
    ols_free_intercept,
    prepared_frame,
    residual_sd_free_intercept,
)

#: The RNG seed of the no-information control below. It is NOT a split seed —
#: this study has no row partition to draw — and nothing downstream reads it.
CONTROL_SEED = 20260903


def value_pattern(series: pd.Series) -> str:
    """What a column REALLY holds, read off the values (never off `dtype`)."""
    present = series.dropna()
    if present.empty:
        return "all missing"
    values = present.tolist()
    if all(isinstance(v, str) for v in values):
        yes_no = {str(v).strip().casefold() for v in values} <= {"yes", "no", "true", "false"}
        numeric_in_string = all(
            str(v).strip().replace("-", "").replace(".", "").isdigit() for v in values
        )
        kind = (
            "STRING-ENCODED BOOLEAN"
            if yes_no
            else "NUMBERS-IN-STRINGS"
            if numeric_in_string
            else "free text"
        )
        return f"{kind}; e.g. {values[:3]}"
    numbers = np.asarray(values, dtype=float)
    integral = bool(np.all(numbers == np.round(numbers)))
    sentinels = sorted({v for v in numbers.tolist() if v in (-999.0, -1.0, 9999.0)})
    return (
        f"{'integral' if integral else 'continuous'} numeric, "
        f"min={numbers.min():g} max={numbers.max():g}"
        + (f"; SENTINEL-LIKE values present: {sentinels}" if sentinels else "; no sentinels")
    )


def main() -> None:
    frame = prepared_frame()
    t1 = frame[frame["block"] == BLOCK_TABLE1].reset_index(drop=True)
    t2 = frame[frame["block"] == BLOCK_TABLE2].reset_index(drop=True)

    print("== 1. block fingerprints (what a stranger recomputes) ==")
    print(f"development (table1, n={len(t1)}): {block_fingerprint(t1)}")
    print(f"sealed      (table2, n={len(t2)}): {block_fingerprint(t2)}")

    print("\n== 2. value-pattern check (war story 1: never trust dtype) ==")
    for column in frame.columns:
        missing = float(frame[column].isna().mean()) * 100.0
        print(f"{column:>10}  missing={missing:5.1f}%  {value_pattern(frame[column])}")

    print("\n== 3. Table 2's r_mpc is DERIVED — leakage row 1 evidence ==")
    have = t2.dropna(subset=["r_mpc", "vs_kms"])
    implied = (have["v_kms"].to_numpy(float) - have["vs_kms"].to_numpy(float)) / HUBBLE_ADOPTED_K
    residual = np.abs(implied - have["r_mpc"].to_numpy(float))
    print(f"rows with r_mpc and vs_kms printed: {len(have)} of {len(t2)}")
    print(f"identity r_mpc == (v_kms - vs_kms) / {HUBBLE_ADOPTED_K:g}")
    print(f"max |deviation| = {residual.max():.10f} Mpc over {len(have)} rows")
    print(f"rows satisfying it exactly (< 1e-9): {int((residual < 1e-9).sum())} of {len(have)}")
    print(
        "=> r_mpc and vs_kms are two spellings of one derived quantity: Hubble's "
        "adopted K applied to the velocity. Neither can be evidence about K."
    )

    print("\n== 4. DGP calibration (sigma on the DGP card) ==")
    r = t1["r_mpc"].to_numpy(float)
    v = t1["v_kms"].to_numpy(float)
    slope, intercept = ols_free_intercept(r, v)
    sigma = residual_sd_free_intercept(r, v)
    print(f"free-intercept fit of Table 1: slope={slope:.6f}  intercept={intercept:.6f}")
    print(f"residual sd (n-2 dof) = {sigma:.6f} km/s   -> DGP sigma")
    print(f"design points r_mpc: min={r.min():g} max={r.max():g} n={r.size}")

    print("\n== 5. leakage row 4 by hand — the no-information control ==")
    rng = np.random.default_rng(CONTROL_SEED)
    shuffled = np.array([ols_free_intercept(r, rng.permutation(v))[0] for _ in range(2000)])
    print(f"K on the real pairing:            {slope:.6f}")
    print(f"K under 2000 velocity permutations: mean={shuffled.mean():.6f} sd={shuffled.std(ddof=1):.6f}")
    print(f"share of permutations at least as large as the real K: {float((shuffled >= slope).mean()):.6f}")
    print(
        "=> breaking the pairing destroys the relation, so the evaluation path "
        "carries no answer of its own; metric direction is checked by "
        "kleinlib.leakage."
    )


if __name__ == "__main__":
    main()
