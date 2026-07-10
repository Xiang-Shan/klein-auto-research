"""prepare.py — stable, reproducible data prep for 01-dae-claims.

Keep this file STABLE. It is NOT the mutable experiment surface (train.py is). It
faithfully replicates the OUTPUT of the model-survey campaign's prepare.py
(the ancestor model-survey campaign's private lab, its commit 5a70203) so that this study's E1
reproduces the campaign's split-identity anchor (val_auc 0.6255) EXACTLY — the anchors,
and every DAE comparison against them, depend on EXACT preprocessing, not just the same
raw columns. This is byte-identical in output to study 00's prepare.py (same 58,592 x 45
prepared frame), so both studies share one prepared artifact contract.

Scaffolding contract: .claude/skills/klein/references/defaults-and-scaffolding.md
DATA gate (run before modeling): .claude/skills/klein/references/data-gate-protocol.md

Usage:
    uv run prepare.py             # data_hub:insurance-claims (needs data_hub on disk)
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

import kleinlib  # engine; kleinlib.data owns the value-pattern-safe Yes/No detection

TARGET_COLUMN = "claim_status"
DROP_COLUMNS = ["policy_id"]

PREPARED_DIR = Path("data/prepared")
PREPARED_PATH = PREPARED_DIR / "insurance_claims_prepared.csv"  # matches study.yaml:data.path


def extract_first_float(series: pd.Series) -> pd.Series:
    """Pull the leading numeric value out of a text spec like '113Nm@4400rpm'."""
    extracted = series.astype(str).str.extract(r"([0-9]+(?:\.[0-9]+)?)", expand=False)
    return pd.to_numeric(extracted, errors="coerce")


def extract_rpm(series: pd.Series) -> pd.Series:
    """Pull the '@Nrpm' suffix out of a text spec like '113Nm@4400rpm'."""
    extracted = series.astype(str).str.extract(r"@([0-9]+(?:\.[0-9]+)?)rpm", expand=False)
    return pd.to_numeric(extracted, errors="coerce")


def preprocess(df: pd.DataFrame) -> pd.DataFrame:
    """Deterministic preprocessing, replicating the campaign's prepare.py output.

    Order matches the campaign exactly: torque/power text-spec parsing -> Yes/No ->
    int (by VALUE PATTERN, never dtype — the string-dtype war story) -> two more
    binary-categorical mappings -> three derived ratio features -> column drops ->
    target dtype. The 17 ``is_*`` columns land as int 0/1; ``prepare.py`` never renames
    them, so the DAE can identify them by the ``is_`` prefix (passthrough, excluded from
    swap noise — see method_card.md / dae.py).
    """
    prepared = df.copy()

    # --- max_torque / max_power text specs ("113Nm@4400rpm") -> 4 numeric cols ---
    prepared["max_torque_nm"] = extract_first_float(prepared["max_torque"])
    prepared["max_torque_rpm"] = extract_rpm(prepared["max_torque"])
    prepared["max_power_bhp"] = extract_first_float(prepared["max_power"])
    prepared["max_power_rpm"] = extract_rpm(prepared["max_power"])
    prepared = prepared.drop(columns=["max_torque", "max_power"], errors="ignore")

    # --- Yes/No -> 1/0: VALUE-PATTERN detection, never `dtype == "object"` ---
    # (the war story: pandas string dtype broke a naive dtype check and silently
    # skipped these columns for a stretch of the campaign — see war-stories.md)
    yes_no_cols = kleinlib.data.detect_yes_no_columns(prepared)
    prepared = kleinlib.data.yes_no_to_int(prepared, columns=yes_no_cols)
    prepared[yes_no_cols] = prepared[yes_no_cols].astype(int)

    # --- two more binary categoricals, same value-pattern discipline ---
    if "rear_brakes_type" in prepared.columns and set(
        prepared["rear_brakes_type"].dropna().unique()
    ) <= {"Drum", "Disc"}:
        prepared["rear_brakes_type"] = (
            prepared["rear_brakes_type"].map({"Drum": 0, "Disc": 1}).astype(int)
        )
    if "transmission_type" in prepared.columns and set(
        prepared["transmission_type"].dropna().unique()
    ) <= {"Manual", "Automatic"}:
        prepared["transmission_type"] = (
            prepared["transmission_type"].map({"Manual": 0, "Automatic": 1}).astype(int)
        )

    # --- 3 deterministic ratio features (kept from the campaign; ablated in its
    #     Phase 5 Q4/Q5 experiments and found to help GBDT marginally) ---
    if {"max_power_bhp", "gross_weight"}.issubset(prepared.columns):
        prepared["power_to_weight"] = prepared["max_power_bhp"] / prepared["gross_weight"]
    if {"max_torque_nm", "displacement"}.issubset(prepared.columns):
        prepared["torque_per_litre"] = prepared["max_torque_nm"] / (
            prepared["displacement"] / 1000.0
        )
    if yes_no_cols and "airbags" in prepared.columns:
        prepared["safety_features_count"] = (
            prepared[yes_no_cols].sum(axis=1) + prepared["airbags"].astype(int)
        )

    prepared = prepared.drop(columns=DROP_COLUMNS, errors="ignore")
    prepared[TARGET_COLUMN] = prepared[TARGET_COLUMN].astype(int)
    return prepared


def main() -> None:
    PREPARED_DIR.mkdir(parents=True, exist_ok=True)

    raw = kleinlib.data.load_data_hub("insurance-claims")
    # data_hub returns a DataFrame for single-table datasets; be defensive if a dict
    # of tables ever comes back (pick the sole table).
    if isinstance(raw, dict):
        (raw,) = raw.values()  # single-table dataset — exactly one value expected
    prepared_df = preprocess(raw)
    prepared_df.to_csv(PREPARED_PATH, index=False)

    print("---")
    print("source:            data_hub:insurance-claims")
    print(f"prepared_path:     {PREPARED_PATH}")
    print(f"rows:              {len(prepared_df)}")
    print(f"columns:           {prepared_df.shape[1]}")
    print(f"target_rate:       {prepared_df[TARGET_COLUMN].mean():.6f}")
    print("status:            ok")


if __name__ == "__main__":
    main()
