"""prepare.py — reference-cell emitter for the RQLS synthetic lab.

This is a KNOWN-TRUTH synthetic study: there is no external dataset to download. The
"data" is generated on the fly by `generator.py` inside each experiment (train.py). What
`prepare.py` does is emit ONE reproducible reference cell — a realistic mixture sample
(ε=5% contamination + deductible truncation + limit censoring) — plus the generator's
EXACT truth functionals, so the DATA gate can profile a concrete artifact and the tutorial
has a data story to tell. It is stable and deterministic (seed-pinned); it is NOT the
mutable experiment surface (train.py is).

Run:  uv run python studies/02-rqls-pv-severity/prepare.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_STUDY_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_STUDY_DIR))
from generator import STD_DEDUCTIBLE, STD_LIMIT, PVLossGenerator, dollar_concentration  # noqa: E402

PREPARED_DIR = _STUDY_DIR / "data" / "prepared"
REFCELL_PATH = PREPARED_DIR / "pv_losses_v1_refcell.csv"   # keep in sync with study.yaml:data.path
TRUTH_PATH = PREPARED_DIR / "pv_losses_v1_truth.json"
REF_SEED = 42
REF_N = 20_000


def main() -> None:
    PREPARED_DIR.mkdir(parents=True, exist_ok=True)
    # Realistic reference cell: full peril mixture, ε=5% contamination, incomplete (d, u).
    gen = PVLossGenerator(contam_eps=0.05, deductible=STD_DEDUCTIBLE, limit=STD_LIMIT)
    s = gen.sample(REF_N, seed=REF_SEED, incomplete=True, contaminate=True)
    df = pd.DataFrame(
        {"recorded_loss": s.losses, "censored": s.censored, "contaminated": s.contaminated}
    )
    df.to_csv(REFCELL_PATH, index=False)

    truth = gen.truth_functionals(STD_DEDUCTIBLE, STD_LIMIT)
    truth_out = {
        "deductible": STD_DEDUCTIBLE,
        "limit": STD_LIMIT,
        "loading": gen.loading,
        "truth_functionals": truth,
        "dollar_concentration": dollar_concentration(gen),  # the hail-share story
        "reference_cell": {"n_observed": int(len(s.losses)), "n_drawn": REF_N,
                           "censored_frac": float(np.mean(s.censored)),
                           "contaminated_frac": float(np.mean(s.contaminated))},
    }
    TRUTH_PATH.write_text(json.dumps(truth_out, indent=2), encoding="utf-8")

    print("---")
    print(f"prepared_path:     {REFCELL_PATH}")
    print(f"truth_path:        {TRUTH_PATH}")
    print(f"n_observed:        {len(s.losses)} of {REF_N} drawn "
          f"(deductible truncation removes below-${STD_DEDUCTIBLE:,.0f})")
    print(f"truth_premium:     ${truth['premium']:,.2f}  "
          f"(E[payout]=${truth['mean_payout']:,.2f}, TVaR99=${truth['tvar99']:,.2f})")
    print("status:            ok")


if __name__ == "__main__":
    main()
