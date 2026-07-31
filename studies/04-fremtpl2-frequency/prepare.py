"""Prepare the immutable local artifact declared by study.yaml:data.prepared_path.

Resolves freMTPL2 through the data-hub seam ($DATA_HUB -> loaders.python.hub),
keeps only the 12 raw canonical columns (the hub table ships pre-baked dummy
encodings, duplicate features, and five leakage/derived columns incl.
``Frequency`` — the target itself), applies the standard freMTPL2 hygiene from
the literature (ClaimNb capped at 4; Exposure clipped to (0, 1]), and records
the null-model development deviance as the split-identity reference cell.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

RAW_KEEP = [
    "IDpol", "ClaimNb", "Exposure",
    "VehPower", "VehAge", "DrivAge", "BonusMalus", "Density",
    "Area", "VehBrand", "VehGas", "Region",
]
OUT = Path("data/prepared/fremtpl2_frequency.csv")


def main() -> None:
    if not os.environ.get("DATA_HUB"):
        raise SystemExit(
            "prepare.py needs $DATA_HUB pointing at the data-hub repo, e.g.\n"
            "  DATA_HUB=~/data_hub uv run --no-sync python prepare.py"
        )
    from kleinlib.data import load_data_hub

    df = load_data_hub("freMTPL2")
    if isinstance(df, dict):  # multi-table datasets return a dict
        df = df[next(iter(df))]
    dropped_cols = [c for c in df.columns if c not in RAW_KEEP]
    df = df[RAW_KEEP].copy()

    capped_claims = int((df["ClaimNb"] > 4).sum())
    df["ClaimNb"] = df["ClaimNb"].clip(upper=4).astype(int)
    clipped_exposure = int(((df["Exposure"] <= 0) | (df["Exposure"] > 1)).sum())
    df["Exposure"] = df["Exposure"].clip(lower=1.0 / 365.25, upper=1.0)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)

    import pipeline

    null_dev = pipeline.null_dev_deviance()
    reference = {
        "null_dev_deviance": null_dev,
        "rows": int(len(df)),
        "total_claims": int(df["ClaimNb"].sum()),
        "total_exposure": float(df["Exposure"].sum()),
        "capped_claim_rows": capped_claims,
        "clipped_exposure_rows": clipped_exposure,
        "dropped_columns": len(dropped_cols),
    }
    pipeline.REFERENCE.write_text(json.dumps(reference, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT}: {len(df)} rows, {df['ClaimNb'].sum()} claims, "
          f"{df['Exposure'].sum():.1f} exposure-years")
    print(f"hygiene: {capped_claims} claim counts capped at 4; "
          f"{clipped_exposure} exposures clipped to (0, 1]; "
          f"{len(dropped_cols)} derived/leakage/dummy columns dropped")
    print(f"reference cell: null-model dev deviance {null_dev:.6f}")


if __name__ == "__main__":
    main()
