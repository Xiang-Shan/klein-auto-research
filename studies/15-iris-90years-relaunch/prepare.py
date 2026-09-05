"""prepare.py -- the stable, reproducible data prep for 15-iris-90years-relaunch.

NOT the mutable experiment surface (`train.py` is). This file builds the
prepared table `study.yaml:data.prepared_path` declares from
`sklearn.datasets.load_iris`, restricted to the study's hard pair --
versicolor (sklearn target 1) and virginica (sklearn target 2). Setosa
(target 0) is trivially separable from the other two and is out of scope,
per `research_plan.md`.

What this file does NOT do
---------------------------
It does not draw a train/development/test partition, and it does not import
`kleinlib.data.contract_split` or `load_partition`. Partitioning is the
notary's job at run time, from `study.yaml:data.split` alone (war story 8: a
literal seed or a partition rule baked into a data-prep or evaluator script
is how a whole ledger lane ends up measuring the wrong rows). This file
writes the prepared table -- the hard-pair flowers, both raw species labels
folded into one binary target -- and never reads, computes, or prints
anything about which rows the DATA gate will later seal.

The DATA-gate duplicate-row finding (BLOCKER, fixed here)
-----------------------------------------------------------
`sklearn.datasets.load_iris`'s hard pair (versicolor + virginica, 100 rows)
contains exactly ONE exact-duplicate row pair: two virginica flowers, both
(5.8, 2.7, 5.1, 1.9) -- identical on all four measurements AND the label.
Under `study.yaml`'s declared `stratified` split (seed 20260904), that pair
lands on OPPOSITE sides of the train/development boundary (one copy in
train, the other in development) -- a mechanical split-contamination leak
(data-gate-protocol.md checklist row 3): a memorization-capable challenger
(`knn5` especially; `svm_rbf`/`hgbt` to a lesser degree) can score the
development copy correctly for free, off a byte-identical training copy, in
exactly the paired comparisons `study.yaml`'s `modern` track measures against
Fisher's LDA. This was caught and BLOCKS on an unmodified prepared table.

The fix applied HERE, entirely inside this file, requires no change to
`study.yaml` (the split stays `stratified`, same seed, same policy): exact
duplicate rows (all four measurements AND the label identical) are dropped,
keeping the first occurrence in sklearn's own fixed row order, before the
table is written. A true duplicate carries zero information beyond its
twin, so dropping the second copy costs nothing and removes the mechanism
by construction -- no duplicate feature vector can straddle a partition it
no longer has two copies to straddle. `study.yaml:predictions[].P0` checks
`raw_rows == 100` against `sklearn.datasets.load_iris` restricted to the
hard pair directly (the RAW loader, independent of this file's output) and
`partition_sum_matches` against whatever this file actually writes, so a
lawful drop here cannot manufacture a false P0 refutation -- the contract
was written anticipating exactly this class of DATA-gate decision.

Provenance and determinism
---------------------------
The loader name is READ FROM THE CONTRACT (`study.yaml:data.source`,
`sklearn:load_iris`) and appears nowhere here as a literal scheme, so this
file cannot silently model a different table than the one it declares.
`sklearn.datasets.load_iris` takes no seed and no network access -- it is a
bundled, offline, immutable toy dataset -- so nothing here is stochastic:
the same scikit-learn version always returns the same 150x4 table in the
same row order (50 setosa, 50 versicolor, 50 virginica).

Usage::

    uv run --locked python prepare.py
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pandas as pd
import sklearn

from kleinlib.contract import load_contract, prepared_data_path
from kleinlib.sources import parse_source, resolve

STUDY_DIR = Path(__file__).resolve().parent

# sklearn's own column names carry units in parentheses -- not CSV-header
# friendly and not what a value-pattern check wants to grep for. Renamed to
# plain snake_case; the VALUES are untouched.
COLUMN_RENAME = {
    "sepal length (cm)": "sepal_length_cm",
    "sepal width (cm)": "sepal_width_cm",
    "petal length (cm)": "petal_length_cm",
    "petal width (cm)": "petal_width_cm",
}

# sklearn.datasets.load_iris's own target encoding (`iris.target_names`):
# 0 = setosa (out of scope), 1 = versicolor, 2 = virginica.
VERSICOLOR_RAW = 1
VIRGINICA_RAW = 2


def build_prepared_table(
    loader_name: str, target_column: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """`(prepared, dropped)` -- the deduplicated table and the rows it cost.

    `dropped` is empty unless an exact duplicate (all four measurements AND
    the label) was found; see the module docstring's DATA-gate finding.
    """
    loader = getattr(importlib.import_module("sklearn.datasets"), loader_name)
    bunch = loader(as_frame=True)
    frame = bunch.frame.rename(columns=COLUMN_RENAME)

    hard_pair = frame[frame["target"].isin([VERSICOLOR_RAW, VIRGINICA_RAW])].copy()
    hard_pair = hard_pair.reset_index(drop=True)
    hard_pair[target_column] = (hard_pair["target"] == VIRGINICA_RAW).astype(int)
    hard_pair = hard_pair.drop(columns=["target"])

    measurement_cols = list(COLUMN_RENAME.values())
    hard_pair = hard_pair[measurement_cols + [target_column]]

    is_duplicate = hard_pair.duplicated(keep="first")
    dropped = hard_pair.loc[is_duplicate].copy()
    deduplicated = hard_pair.loc[~is_duplicate].reset_index(drop=True)
    return deduplicated, dropped


def main() -> None:
    contract = load_contract(STUDY_DIR)
    target_column = str(contract["target"])
    prepared_path = prepared_data_path(STUDY_DIR, contract)
    prepared_path.parent.mkdir(parents=True, exist_ok=True)

    source_tag = str(contract["data"]["source"])
    parsed = parse_source(source_tag)  # validates the '<scheme>:<value>' grammar
    resolved = resolve(source_tag, study_dir=STUDY_DIR, offline=True)  # prints provenance

    prepared_df, dropped_df = build_prepared_table(parsed.value, target_column)
    prepared_df.to_csv(prepared_path, index=False, lineterminator="\n")

    print("---")
    print(f"source:            {source_tag}  (sklearn.__version__={sklearn.__version__})")
    print(f"prepared_path:     {prepared_path}")
    print(f"rows:              {len(prepared_df)}")
    print(f"columns:           {prepared_df.shape[1]}")
    print(f"target_rate:       {prepared_df[target_column].mean():.6f}")
    print(f"target_counts:     {prepared_df[target_column].value_counts().sort_index().to_dict()}")
    print(f"exact_duplicates_dropped: {len(dropped_df)}")
    if len(dropped_df):
        for _, row in dropped_df.iterrows():
            print(f"  dropped (2nd copy, DATA-gate BLOCKER fix): {row.to_dict()}")
    print("status:            ok")
    assert resolved.kind.value == "sklearn"


if __name__ == "__main__":
    main()
