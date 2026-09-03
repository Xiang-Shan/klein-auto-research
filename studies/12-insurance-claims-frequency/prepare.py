"""prepare.py — the stable, reproducible data prep for 12-insurance-claims-frequency.

NOT the mutable experiment surface (`train.py` is). This file exists to make one
thing true: the prepared table this study models is BYTE-IDENTICAL to the table
the v1 quickstart (`studies/00-glm-claims-quickstart` at tag `v1.3.0`) modelled,
so that the anchors quoted in `scouting_ledger.md` are anchors of the same
columns and the same rows, and any difference a run reports is a difference of
the CONTRACT, not of the data.

The transformation order is the v1 file's order, kept verbatim:

1. `max_torque` / `max_power` text specs (`"113Nm@4400rpm"`) -> four numeric columns;
2. Yes/No -> 1/0 by VALUE PATTERN, never by `dtype == "object"` (war story 1 — this
   dataset now loads with pandas' `str` dtype, which is exactly what broke the naive
   check in the ancestor campaign);
3. two more binary categoricals (`rear_brakes_type`, `transmission_type`);
4. three deterministic ratio features;
5. drop `policy_id`; cast the target to int.

Provenance and determinism
--------------------------
The source tag is READ FROM THE CONTRACT (`study.yaml:data.source`) and appears
nowhere here as a literal, so the study cannot silently model a different table
than the one it declares. Nothing in this file draws a partition or writes a
seed: the partitions come from `kleinlib.data.contract_split`, which reads
`data.split` (war story 8).

Usage::

    uv run --locked python prepare.py            # the declared source (bundled)
    uv run --locked python prepare.py --sample   # the committed 2k CI fixture
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

import kleinlib
from kleinlib.contract import load_contract, prepared_data_path
from kleinlib.sources import resolve

STUDY_DIR = Path(__file__).resolve().parent
DROP_COLUMNS = ["policy_id"]
FIXTURE_PATH = STUDY_DIR / "fixtures" / "insurance_claims_sample_2k.csv"


def extract_first_float(series: pd.Series) -> pd.Series:
    """Pull the leading numeric value out of a text spec like '113Nm@4400rpm'."""
    extracted = series.astype(str).str.extract(r"([0-9]+(?:\.[0-9]+)?)", expand=False)
    return pd.to_numeric(extracted, errors="coerce")


def extract_rpm(series: pd.Series) -> pd.Series:
    """Pull the '@Nrpm' suffix out of a text spec like '113Nm@4400rpm'."""
    extracted = series.astype(str).str.extract(r"@([0-9]+(?:\.[0-9]+)?)rpm", expand=False)
    return pd.to_numeric(extracted, errors="coerce")


def preprocess(df: pd.DataFrame, target_column: str) -> pd.DataFrame:
    """Deterministic preprocessing, in the v1 study's exact order."""
    prepared = df.copy()

    # --- max_torque / max_power text specs -> 4 numeric cols ---
    prepared["max_torque_nm"] = extract_first_float(prepared["max_torque"])
    prepared["max_torque_rpm"] = extract_rpm(prepared["max_torque"])
    prepared["max_power_bhp"] = extract_first_float(prepared["max_power"])
    prepared["max_power_rpm"] = extract_rpm(prepared["max_power"])
    prepared = prepared.drop(columns=["max_torque", "max_power"], errors="ignore")

    # --- Yes/No -> 1/0 by VALUE PATTERN, never by dtype (war story 1) ---
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

    # --- 3 deterministic ratio features (kept from v1) ---
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
    prepared[target_column] = prepared[target_column].astype(int)
    return prepared


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sample",
        action="store_true",
        help="use the committed CI fixture (fixtures/insurance_claims_sample_2k.csv), "
        "which is already a PREPARED sample — no network, no bundled dataset needed.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    contract = load_contract(STUDY_DIR)
    target_column = str(contract["target"])
    prepared_path = prepared_data_path(STUDY_DIR, contract)
    prepared_path.parent.mkdir(parents=True, exist_ok=True)

    if args.sample:
        prepared_df = pd.read_csv(FIXTURE_PATH)
        source_note = f"CI fixture ({FIXTURE_PATH.relative_to(STUDY_DIR)}), no network"
    else:
        resolved = resolve(
            str(contract["data"]["source"]), study_dir=STUDY_DIR, offline=True
        )
        raw_df = pd.read_csv(resolved.path)
        prepared_df = preprocess(raw_df, target_column)
        source_note = f"{contract['data']['source']} sha256={resolved.digest}"

    prepared_df.to_csv(prepared_path, index=False)

    print("---")
    print(f"source:            {source_note}")
    print(f"prepared_path:     {prepared_path}")
    print(f"rows:              {len(prepared_df)}")
    print(f"columns:           {prepared_df.shape[1]}")
    print(f"target_rate:       {prepared_df[target_column].mean():.6f}")
    print("status:            ok")


if __name__ == "__main__":
    main()
