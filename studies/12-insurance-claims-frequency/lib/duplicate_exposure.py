"""How much of each partition is a byte-identical twin of a training row.

The DATA gate's mechanized audit FAILED this study on row 3: 615 row-content hashes
straddle the contract's partitions. This module is the study's answer to "how big is
that, exactly" — it quantifies the accepted risk rather than asserting it is small.

Two surfaces:

* :func:`duplicate_free_mask` — used by ``train.py`` on EVERY run, so each rung reports
  its AUC on the subset of evaluation rows that has no twin in the rows it was fitted
  on. That is the number a generalisation claim is entitled to; the contract's
  ``primary_metric`` stays the full-partition AUC because the registered anchors
  (P1, P2, P4) compare against v1 values measured the same contaminated way, and
  changing the measurement would make that comparison meaningless.
* ``python -m lib.duplicate_exposure`` (from the study directory) — writes
  ``tables/duplicate_exposure.tsv``, the partition-level table, including the v1
  study's own train/validation partition, which this contract reproduces exactly and
  which therefore carried the same contamination unmeasured.

Row content is hashed exactly as ``kleinlib.leakage`` hashes it —
``pd.util.hash_pandas_object(frame, index=False)`` over the full prepared frame,
features AND target — so the numbers here and the gate's FAIL describe the same object.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

STUDY_DIR = Path(__file__).resolve().parent.parent
TABLE_PATH = STUDY_DIR / "tables" / "duplicate_exposure.tsv"


def row_hashes(X: pd.DataFrame, y: pd.Series) -> np.ndarray:
    """The kleinlib.leakage row-content hash of (features + target), row by row."""
    frame = X.copy()
    frame[y.name] = y
    return pd.util.hash_pandas_object(frame, index=False).to_numpy()


def duplicate_free_mask(
    X_fit: pd.DataFrame, y_fit: pd.Series, X_eval: pd.DataFrame, y_eval: pd.Series
) -> np.ndarray:
    """Boolean mask over the EVALUATION rows: True where the row has no twin in the fit rows."""
    fit = set(row_hashes(X_fit, y_fit).tolist())
    return np.array([h not in fit for h in row_hashes(X_eval, y_eval).tolist()], dtype=bool)


def main() -> int:
    from kleinlib.contract import load_contract, prepared_data_path
    from kleinlib.data import contract_split, load_prepared

    contract = load_contract(STUDY_DIR)
    target = str(contract["target"])
    frame = load_prepared(prepared_data_path(STUDY_DIR, contract))
    hashes = pd.util.hash_pandas_object(frame, index=False).to_numpy()

    X_train, X_dev, X_test, y_train, y_dev, y_test = contract_split(STUDY_DIR)
    positions = {
        "train": np.asarray(X_train.index),
        "development": np.asarray(X_dev.index),
        "final_test": np.asarray(X_test.index),
    }
    # The v1 quickstart's two-way partition: its train side IS this contract's train
    # partition, and its validation side IS development + final_test (scouting_ledger S4).
    positions["v1_validation"] = np.concatenate(
        [positions["development"], positions["final_test"]]
    )
    train_hashes = set(hashes[positions["train"]].tolist())
    labels = frame[target].to_numpy()

    TABLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        (
            "partition",
            "rows",
            "rows_with_train_twin",
            "share_with_train_twin",
            "positives",
            "positive_rows_with_train_twin",
        )
    ]
    for name in ("development", "final_test", "v1_validation"):
        pos = positions[name]
        twin = np.array([h in train_hashes for h in hashes[pos].tolist()], dtype=bool)
        y = labels[pos]
        rows.append(
            (
                name,
                str(len(pos)),
                str(int(twin.sum())),
                f"{twin.mean():.6f}",
                str(int(y.sum())),
                str(int((twin & (y == 1)).sum())),
            )
        )
    # The last row measures a different thing and says so in its label: how many rows
    # of the whole table sit in a duplicated-content group at all, partitions aside.
    _, counts = np.unique(hashes, return_counts=True)
    duplicated_rows = int(counts[counts > 1].sum())
    rows.append(
        (
            "whole_table(rows_in_a_duplicate_group)",
            str(len(frame)),
            str(duplicated_rows),
            f"{duplicated_rows / len(frame):.6f}",
            str(int(labels.sum())),
            "NA",
        )
    )
    TABLE_PATH.write_text("\n".join("\t".join(r) for r in rows) + "\n", encoding="utf-8")
    for r in rows:
        print("\t".join(r))
    print(f"\nwrote {TABLE_PATH.relative_to(STUDY_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
