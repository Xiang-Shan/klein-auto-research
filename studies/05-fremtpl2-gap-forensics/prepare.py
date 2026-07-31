"""Prepare the immutable local artifact declared by study.yaml:data.prepared_path.

Byte-for-byte the study-04 prep (12 raw canonical columns, ClaimNb capped at 4,
Exposure clipped to (0, 1], null-model reference cell) — comparability with study
04's anchors is the point of this study, so the prep is FROZEN to it. Additions on
top, none of which touch the data: the prepared-file SHA-256 (recorded for the data
card), study 04's two published anchor values recorded as identity targets for
E0001/E0002, and an IDpol/duplicate-profile audit re-verified by value rather than
trusted from study 04's card.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

RAW_KEEP = [
    "IDpol", "ClaimNb", "Exposure",
    "VehPower", "VehAge", "DrivAge", "BonusMalus", "Density",
    "Area", "VehBrand", "VehGas", "Region",
]
OUT = Path("data/prepared/fremtpl2_frequency.csv")

# Study 04's published anchors (tag v1.0.0, results.tsv E0001/E0003) — E0001/E0002
# here must reproduce these through the v0.4.0 registry path to 1e-9 or STOP.
ANCHOR_TARGETS = {"glm_ohe_dev": 0.454861, "hgbt_ohe_dev": 0.444689}


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

    # Value-level audit (never trust a prior card): IDpol uniqueness and duplicate
    # FEATURE profiles (identical 9-feature rows) — recorded, deliberately not fixed.
    idpol_dupes = int(df["IDpol"].duplicated().sum())
    feature_cols = [c for c in RAW_KEEP if c not in ("IDpol", "ClaimNb", "Exposure")]
    dup_profiles = int(df.duplicated(subset=feature_cols).sum())

    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    sha = hashlib.sha256(OUT.read_bytes()).hexdigest()

    import pipeline

    null_dev = pipeline.null_dev_deviance()
    reference = {
        "null_dev_deviance": null_dev,
        "anchor_targets": ANCHOR_TARGETS,
        "prepared_sha256": sha,
        "rows": int(len(df)),
        "total_claims": int(df["ClaimNb"].sum()),
        "total_exposure": float(df["Exposure"].sum()),
        "capped_claim_rows": capped_claims,
        "clipped_exposure_rows": clipped_exposure,
        "dropped_columns": len(dropped_cols),
        "idpol_duplicate_rows": idpol_dupes,
        "duplicate_feature_profiles": dup_profiles,
    }
    pipeline.REFERENCE.write_text(json.dumps(reference, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT}: {len(df)} rows, {df['ClaimNb'].sum()} claims, "
          f"{df['Exposure'].sum():.1f} exposure-years")
    print(f"hygiene: {capped_claims} claim counts capped at 4; "
          f"{clipped_exposure} exposures clipped to (0, 1]; "
          f"{len(dropped_cols)} derived/leakage/dummy columns dropped")
    print(f"audit: {idpol_dupes} duplicated IDpol rows; "
          f"{dup_profiles} duplicate feature profiles (recorded, not removed)")
    print(f"prepared sha256: {sha}")
    print(f"reference cell: null-model dev deviance {null_dev:.6f}")
    print(f"anchor targets: {ANCHOR_TARGETS}")


if __name__ == "__main__":
    main()
