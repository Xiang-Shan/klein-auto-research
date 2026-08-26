"""prepare.py — stable, reproducible data prep for 07-iris-90years.

Keep this file STABLE. It is NOT the mutable experiment surface (train.py is).

What it builds
--------------
Fisher's iris (as shipped by scikit-learn's ``load_iris``), restricted to the
HARD PAIR — versicolor vs virginica, the two species Fisher's 1936 paper treats
as the interesting discrimination. Setosa is dropped: it is linearly separable
from both and would make every method look perfect.

Prepared columns (7), in this order:

===================  ==========================================================
sepal_length_cm      the four 1936 measurements, 0.1 cm resolution
sepal_width_cm
petal_length_cm
petal_width_cm
species              sklearn's ORIGINAL 3-class code (0 setosa / 1 versicolor /
                     2 virginica).  KEPT ON PURPOSE and from the very first
                     write: the pre-registered crash rung (E0002) hands this
                     multiclass column to ``kleinlib.eval.evaluate`` to
                     evidence the framework's binary-only boundary.  Adding it
                     later would change the prepared-artifact fingerprint the
                     DATA gate freezes.  It is a PERFECT PROXY for the target
                     and is never a model feature — see data_card.md.
is_virginica         the binary target, 1 = virginica, 0 = versicolor
group_id             split-group identity (see below)
===================  ==========================================================

The twin rows
-------------
Hard-pair positional rows 51 and 92 (rows 102 and 143 of the full 150-row iris
table, both virginica) carry identical measurements (5.8, 2.7, 5.1, 1.9). They
are the ONLY duplicated row-content in the hard pair (asserted below).

At 0.1 cm resolution identical measurements do NOT prove duplicated record
entry — two distinct flowers can round to the same four numbers, and no
provenance evidence has been found either way. We therefore do NOT delete
historical data. Instead both rows are given ONE ``group_id``
(``twins102-143``) and ``study.yaml`` declares a group-aware split, so the two
rows always travel into the same partition. The leakage mechanism (a memorized
twin scored on the other side of a split) is removed regardless of which
explanation is true; n stays 100.

Every other row is its own group, named for its 1-based row number in the full
150-row iris table (``row051`` … ``row150``) — 99 groups over 100 rows.

Usage
-----
    uv run --locked python prepare.py            # write prepared + fixture
    uv run --locked python prepare.py --check    # verify fixture == rebuild

Scaffolding contract: .claude/skills/klein/references/defaults-and-scaffolding.md
DATA gate (run before modeling): .claude/skills/klein/references/data-gate-protocol.md
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.datasets import load_iris

HERE = Path(__file__).resolve().parent
PREPARED_PATH = HERE / "data" / "prepared" / "iris_hard_pair.csv"  # matches study.yaml
FIXTURE_PATH = HERE / "fixtures" / "iris_hard_pair.csv"

FEATURE_COLUMNS = [
    "sepal_length_cm",
    "sepal_width_cm",
    "petal_length_cm",
    "petal_width_cm",
]
PETAL_COLUMNS = ["petal_length_cm", "petal_width_cm"]
SEPAL_COLUMNS = ["sepal_length_cm", "sepal_width_cm"]
TARGET_COLUMN = "is_virginica"
GROUP_COLUMN = "group_id"
SPECIES_COLUMN = "species"

#: sklearn column name -> prepared column name.
_RENAME = {
    "sepal length (cm)": "sepal_length_cm",
    "sepal width (cm)": "sepal_width_cm",
    "petal length (cm)": "petal_length_cm",
    "petal width (cm)": "petal_width_cm",
}

#: 1-based row numbers in the full 150-row iris table of the twin pair.
TWIN_ROWS_1BASED = (102, 143)
TWIN_GROUP_ID = "twins102-143"


def build() -> pd.DataFrame:
    """Return the prepared hard-pair frame. Deterministic; no randomness."""
    bunch = load_iris(as_frame=True)
    frame = bunch.frame.copy()
    frame["_row_1based"] = np.arange(1, len(frame) + 1)

    hard_pair = frame.loc[frame["target"] != 0].reset_index(drop=True)

    prepared = hard_pair.rename(columns=_RENAME)[
        [*FEATURE_COLUMNS, "target", "_row_1based"]
    ].copy()
    prepared = prepared.rename(columns={"target": SPECIES_COLUMN})
    prepared[TARGET_COLUMN] = (prepared[SPECIES_COLUMN] == 2).astype(int)

    row_ids = prepared.pop("_row_1based").to_numpy()
    groups = [f"row{int(row):03d}" for row in row_ids]
    for position, row in enumerate(row_ids):
        if int(row) in TWIN_ROWS_1BASED:
            groups[position] = TWIN_GROUP_ID
    prepared[GROUP_COLUMN] = groups

    return prepared[[*FEATURE_COLUMNS, SPECIES_COLUMN, TARGET_COLUMN, GROUP_COLUMN]]


def assert_contract(prepared: pd.DataFrame) -> None:
    """Fail loudly if the artifact is not the one study.yaml was written for."""
    assert list(prepared.columns) == [
        *FEATURE_COLUMNS,
        SPECIES_COLUMN,
        TARGET_COLUMN,
        GROUP_COLUMN,
    ], f"unexpected column order: {list(prepared.columns)}"
    assert len(prepared) == 100, f"hard pair must be 100 rows, got {len(prepared)}"
    assert int(prepared[TARGET_COLUMN].sum()) == 50, "hard pair must be 50/50"
    assert set(prepared[SPECIES_COLUMN].unique()) == {1, 2}, "setosa must be dropped"
    assert not prepared.isna().any().any(), "no missing values are expected"

    # species is a perfect proxy for the target — asserted, documented, never a feature.
    assert (prepared[SPECIES_COLUMN].map({1: 0, 2: 1}) == prepared[TARGET_COLUMN]).all()

    # The twin ruling: exactly one duplicated row-content group, and it is grouped.
    duplicated = prepared.duplicated(subset=FEATURE_COLUMNS, keep=False)
    twin_positions = sorted(np.flatnonzero(duplicated.to_numpy()).tolist())
    assert twin_positions == [51, 92], (
        f"expected the only duplicate row-content at hard-pair positions 51/92, "
        f"got {twin_positions}"
    )
    twins = prepared.loc[duplicated]
    assert set(twins[GROUP_COLUMN]) == {TWIN_GROUP_ID}, "twins must share one group id"
    assert set(twins[TARGET_COLUMN]) == {1}, "both twins are virginica"

    # 99 groups over 100 rows: row identity everywhere except the twin pair.
    counts = prepared[GROUP_COLUMN].value_counts()
    assert counts.max() == 2 and int((counts == 2).sum()) == 1, "only the twins share a group"
    assert len(counts) == 99, f"expected 99 groups, got {len(counts)}"


def write(prepared: pd.DataFrame) -> None:
    for path in (PREPARED_PATH, FIXTURE_PATH):
        path.parent.mkdir(parents=True, exist_ok=True)
        prepared.to_csv(path, index=False, float_format="%.1f")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="prepare 07-iris-90years hard-pair data")
    parser.add_argument(
        "--check",
        action="store_true",
        help="rebuild in memory and compare with the committed fixture; write nothing",
    )
    args = parser.parse_args()

    prepared = build()
    assert_contract(prepared)

    if args.check:
        if not FIXTURE_PATH.is_file():
            raise SystemExit(f"missing fixture: {FIXTURE_PATH}")
        rebuilt = prepared.to_csv(index=False, float_format="%.1f")
        committed = FIXTURE_PATH.read_text(encoding="utf-8")
        if rebuilt != committed:
            raise SystemExit(f"fixture drift: {FIXTURE_PATH} != freshly built frame")
        print(f"[OK] fixture matches a fresh build: {FIXTURE_PATH}")
        return

    write(prepared)
    twins = prepared.loc[prepared[GROUP_COLUMN] == TWIN_GROUP_ID, FEATURE_COLUMNS]
    print("data source: sklearn.datasets.load_iris (scikit-learn's bundled iris.csv)")
    print(f"rows x cols: {prepared.shape[0]} x {prepared.shape[1]}")
    print(
        f"target {TARGET_COLUMN}: {int(prepared[TARGET_COLUMN].sum())} / {len(prepared)} positive"
    )
    print(
        f"groups: {prepared[GROUP_COLUMN].nunique()} "
        f"(rows {TWIN_ROWS_1BASED[0]}/{TWIN_ROWS_1BASED[1]} share {TWIN_GROUP_ID!r})"
    )
    print(f"twin measurements: {twins.iloc[0].tolist()}")
    print(f"wrote {PREPARED_PATH}  sha256={sha256(PREPARED_PATH)}")
    print(f"wrote {FIXTURE_PATH}  sha256={sha256(FIXTURE_PATH)}")


if __name__ == "__main__":
    main()
