"""prepare.py — stable, reproducible data prep for 09-iris-first-lesson.

Keep this file STABLE. It is NOT the mutable experiment surface (train.py is).

What it builds
--------------
Fisher's iris (as shipped by scikit-learn's ``load_iris``), restricted to the
HARD PAIR — versicolor vs virginica, the two species Fisher's 1936 paper treats
as the interesting discrimination. Setosa is dropped: it is linearly separable
from both and would make every method look perfect. (``--audit`` MEASURES that
sentence instead of asserting it — see below.)

Prepared columns (7), in this order:

===================  ==========================================================
sepal_length_cm      the four 1936 measurements, 0.1 cm resolution
sepal_width_cm
petal_length_cm
petal_width_cm
species              sklearn's ORIGINAL 3-class code (0 setosa / 1 versicolor /
                     2 virginica).  KEPT ON PURPOSE and from the very first
                     write: study 07's pre-registered crash rung (E0002) handed
                     this multiclass column to ``kleinlib.eval.evaluate`` to
                     evidence the framework's binary-only boundary.  Removing it
                     now would change the prepared-artifact fingerprint that
                     studies 07 and 08 already froze.  It is a PERFECT PROXY for
                     the target and is never a model feature — see data_card.md.
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

STUDY 09 NOTE: the prepared artifact is inherited BYTE-IDENTICALLY from studies
07 and 08 (same data contract, same twins ruling, sha256
``9d67302e…f23f05`` — asserted, not hoped for). The split itself lives in
train.py/study.yaml (fresh seed 20260909), not here.

STUDY 09 REGISTRATION — ``--audit`` (new in 09)
-----------------------------------------------
The talk's first lesson is "look at your data before you model it", so 09
registers the looking as a script instead of a paragraph. ``--audit`` writes
``fixtures/full150_audit.json``: a deterministic, timestamp-free census of the
FULL 150 rows — hash, class counts, per-feature range and resolution, the
exact-duplicate row groups (this is where the twins ruling comes from), the
one-feature/0.1 cm near-duplicates, a cell-level diff against the committed UCI
bytes (the two known errata rows), and the setosa petal-length gap that is the
audit FACT behind "setosa is trivial". It reads
``../07-iris-90years/reference/uci_iris.data`` READ-ONLY and writes nothing
outside this study's ``fixtures/``. No modelling decision may cite the audit
after the fact: it is committed at the DATA gate, before the METHOD gate.

Usage
-----
    uv run --locked python prepare.py            # write prepared + fixture
    uv run --locked python prepare.py --check    # verify fixture == rebuild
    uv run --locked python prepare.py --audit    # write the full-150 audit JSON

``--out-dir <path>`` redirects every output (``data/prepared/…``,
``fixtures/…``) for smoke runs; the UCI reference is always read from the
study directory, read-only.

Scaffolding contract: .claude/skills/klein/references/defaults-and-scaffolding.md
DATA gate (run before modeling): .claude/skills/klein/references/data-gate-protocol.md
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.datasets import load_iris

HERE = Path(__file__).resolve().parent
PREPARED_REL = Path("data") / "prepared" / "iris_hard_pair.csv"  # matches study.yaml
FIXTURE_REL = Path("fixtures") / "iris_hard_pair.csv"
AUDIT_REL = Path("fixtures") / "full150_audit.json"

PREPARED_PATH = HERE / PREPARED_REL
FIXTURE_PATH = HERE / FIXTURE_REL
AUDIT_PATH = HERE / AUDIT_REL

#: Read-only third-party evidence committed under study 07 (reference/PROVENANCE.md).
#: Path is relative to THIS study dir; prepare.py never writes there.
UCI_REFERENCE = HERE.parent / "07-iris-90years" / "reference" / "uci_iris.data"

#: The frozen prepared-artifact fingerprint — identical in 07, 08 and 09.
EXPECTED_SHA256 = "9d67302e0fcd71bcfeb0d4cbeb739c5612f0b7d97c488842d1f8903c35f23f05"

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

#: sklearn target code -> species name (audit reporting only).
SPECIES_NAMES = {0: "setosa", 1: "versicolor", 2: "virginica"}

#: UCI label text -> sklearn target code (audit reporting only).
UCI_LABELS = {"Iris-setosa": 0, "Iris-versicolor": 1, "Iris-virginica": 2}

#: The canonical full-150 serialization the audit hashes. Stated in the JSON so
#: the number is reproducible from the file alone.
FULL150_CSV_CONVENTION = (
    "pandas.DataFrame[sepal_length_cm,sepal_width_cm,petal_length_cm,"
    "petal_width_cm,species].to_csv(index=False, float_format='%.1f'), "
    "sklearn row order, LF line endings, utf-8"
)

#: The UCI errata this study expects to find (0-based rows in the 150-row table);
#: iris.names' own note: samples 35 and 38 (1-based) differ from Fisher's paper.
EXPECTED_UCI_DIFF_ROWS_0BASED = [34, 37]
EXPECTED_UCI_DIFF_CELLS = 3


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


def serialize(prepared: pd.DataFrame) -> str:
    """The one serialization the fixture, the artifact and the hash all share."""
    return prepared.to_csv(index=False, float_format="%.1f")


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

    # 09 addition: the prepared bytes are the SAME bytes studies 07 and 08 froze.
    # A drift here means sklearn's bundled iris.csv moved under us — STOP, do not
    # publish a "third study on the same 100 flowers" claim on different numbers.
    digest = hashlib.sha256(serialize(prepared).encode("utf-8")).hexdigest()
    assert digest == EXPECTED_SHA256, (
        f"prepared artifact fingerprint drifted: {digest} != {EXPECTED_SHA256} "
        "(studies 07/08 froze these exact bytes)"
    )


def write(prepared: pd.DataFrame, out_dir: Path) -> tuple[Path, Path]:
    prepared_path = out_dir / PREPARED_REL
    fixture_path = out_dir / FIXTURE_REL
    for path in (prepared_path, fixture_path):
        path.parent.mkdir(parents=True, exist_ok=True)
        prepared.to_csv(path, index=False, float_format="%.1f")
        # The written BYTES, not just the in-memory frame, are the frozen artifact.
        digest = sha256(path)
        assert digest == EXPECTED_SHA256, (
            f"written artifact fingerprint drifted: {path} -> {digest} != {EXPECTED_SHA256}"
        )
    return prepared_path, fixture_path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# --audit — the registered full-150 census (deterministic, no timestamps)
# ---------------------------------------------------------------------------

def _tenths(values: np.ndarray) -> np.ndarray:
    """Measurements at 0.1 cm resolution as EXACT integers (no float compares)."""
    scaled = np.asarray(values, dtype=float) * 10.0
    rounded = np.rint(scaled)
    assert np.all(np.abs(scaled - rounded) < 1e-9), "a measurement is not a whole tenth"
    return rounded.astype(int)


def _full150() -> pd.DataFrame:
    """The full 150-row table, prepared-artifact column names, sklearn row order."""
    frame = load_iris(as_frame=True).frame.copy()
    frame = frame.rename(columns=_RENAME).rename(columns={"target": SPECIES_COLUMN})
    return frame[[*FEATURE_COLUMNS, SPECIES_COLUMN]]


def _duplicate_groups(tenths: np.ndarray, index: list[int]) -> list[list[int]]:
    """Exact-duplicate row groups over the integer-tenths matrix, as index lists."""
    seen: dict[tuple[int, ...], list[int]] = {}
    for position, row in enumerate(tenths):
        seen.setdefault(tuple(row.tolist()), []).append(index[position])
    return sorted(group for group in seen.values() if len(group) > 1)


def _near_duplicates(tenths: np.ndarray, index: list[int]) -> list[dict[str, object]]:
    """Pairs differing in EXACTLY one feature by EXACTLY 0.1 cm (one tenth)."""
    pairs: list[dict[str, object]] = []
    for a, b in combinations(range(len(tenths)), 2):
        delta = tenths[a] - tenths[b]
        changed = np.flatnonzero(delta)
        if len(changed) == 1 and abs(int(delta[changed[0]])) == 1:
            pairs.append(
                {
                    "a": index[a],
                    "b": index[b],
                    "feature": FEATURE_COLUMNS[int(changed[0])],
                }
            )
    return sorted(pairs, key=lambda row: (row["a"], row["b"], row["feature"]))


def _per_feature(frame: pd.DataFrame) -> dict[str, dict[str, float | int]]:
    return {
        column: {
            "min": float(frame[column].min()),
            "max": float(frame[column].max()),
            "n_distinct": int(frame[column].nunique()),
        }
        for column in FEATURE_COLUMNS
    }


def _decimal_profile(frame: pd.DataFrame) -> dict[str, object]:
    """Is every measurement a whole tenth? (The 1936 recording resolution.)"""
    per_feature: dict[str, dict[str, object]] = {}
    all_one_decimal = True
    for column in FEATURE_COLUMNS:
        scaled = frame[column].to_numpy(dtype=float) * 10.0
        one_decimal = bool(np.all(np.abs(scaled - np.rint(scaled)) < 1e-9))
        all_one_decimal = all_one_decimal and one_decimal
        tenths = np.rint(scaled).astype(int)
        per_feature[column] = {
            "all_values_one_decimal": one_decimal,
            "n_ending_in_zero_tenth": int(np.count_nonzero(tenths % 10 == 0)),
            "distinct_tenths": int(np.unique(tenths).size),
        }
    return {
        "all_values_one_decimal": all_one_decimal,
        "resolution_cm": 0.1,
        "per_feature": per_feature,
    }


def _read_uci(path: Path) -> tuple[np.ndarray, list[int]]:
    """Parse the committed UCI bytes: (150x4 float matrix, species codes)."""
    text = path.read_text(encoding="utf-8")
    rows = [line for line in text.splitlines() if line.strip()]
    measurements: list[list[float]] = []
    labels: list[int] = []
    for line in rows:
        fields = line.split(",")
        if len(fields) != 5:
            raise SystemExit(f"malformed UCI row in {path}: {line!r}")
        measurements.append([float(value) for value in fields[:4]])
        label = fields[4].strip()
        if label not in UCI_LABELS:
            raise SystemExit(f"unknown UCI species label in {path}: {label!r}")
        labels.append(UCI_LABELS[label])
    return np.asarray(measurements, dtype=float), labels


def _uci_comparison(frame: pd.DataFrame) -> dict[str, object]:
    """Cell-level diff of the 150x4 measurement matrix, sklearn vs committed UCI.

    Deliberately narrow (07 reference/PROVENANCE.md §Scope of the diff): this is
    NOT a transcription of Fisher's 1936 Table I, and no claim rests on one.
    """
    if not UCI_REFERENCE.is_file():
        raise SystemExit(
            f"missing read-only UCI reference: {UCI_REFERENCE} "
            "(committed under study 07; the audit diffs committed bytes, never a live fetch)"
        )
    uci_values, uci_labels = _read_uci(UCI_REFERENCE)
    sk_values = frame[FEATURE_COLUMNS].to_numpy(dtype=float)
    if uci_values.shape != sk_values.shape:
        raise SystemExit(
            f"UCI reference is {uci_values.shape}, sklearn is {sk_values.shape}"
        )
    uci_tenths, sk_tenths = _tenths(uci_values), _tenths(sk_values)
    cell_diffs: list[dict[str, object]] = []
    for row, column in zip(*np.nonzero(uci_tenths != sk_tenths), strict=True):
        cell_diffs.append(
            {
                "row_0based": int(row),
                "row_1based": int(row) + 1,
                "feature": FEATURE_COLUMNS[int(column)],
                "uci": round(float(uci_values[row, column]), 1),
                "sklearn": round(float(sk_values[row, column]), 1),
            }
        )
    differing_rows = sorted({int(diff["row_0based"]) for diff in cell_diffs})

    # The registered expectation (07 data_card §errata, iris.names' own note):
    # exactly the two setosa samples 35 and 38 (1-based), three cells in all.
    assert differing_rows == EXPECTED_UCI_DIFF_ROWS_0BASED, (
        f"UCI diff moved: expected rows {EXPECTED_UCI_DIFF_ROWS_0BASED} (0-based), "
        f"got {differing_rows}"
    )
    assert len(cell_diffs) == EXPECTED_UCI_DIFF_CELLS, (
        f"UCI diff moved: expected {EXPECTED_UCI_DIFF_CELLS} differing cells, "
        f"got {len(cell_diffs)}"
    )

    return {
        "reference_path": "../07-iris-90years/reference/uci_iris.data",
        "reference_sha256": sha256(UCI_REFERENCE),
        "rows": int(len(uci_values)),
        "rows_in_agreement": int(len(uci_values) - len(differing_rows)),
        "rows_differing_0based": differing_rows,
        "cell_diff_count": len(cell_diffs),
        "cell_diffs": cell_diffs,
        "species_labels_agree": bool(uci_labels == frame[SPECIES_COLUMN].tolist()),
        "note": (
            "cell-level diff of the 150x4 measurement matrix only; sklearn's DESCR: "
            "'the same as in R, but not as in the UCI Machine Learning Repository, "
            "which has two wrong data points'"
        ),
    }


def _setosa_separability(frame: pd.DataFrame) -> dict[str, object]:
    """The audit fact behind 'setosa is trivial' — the petal-length gap.

    Setosa carries the SMALL petals, so the separating fact is
    max(petal_length | setosa) < min(petal_length | versicolor+virginica): one
    threshold on one feature classifies setosa with zero errors, which is why
    every method looks perfect until setosa is dropped.
    """
    setosa = frame.loc[frame[SPECIES_COLUMN] == 0, "petal_length_cm"]
    others = frame.loc[frame[SPECIES_COLUMN] != 0, "petal_length_cm"]
    gap = float(others.min()) - float(setosa.max())
    return {
        "feature": "petal_length_cm",
        "setosa_min": float(setosa.min()),
        "setosa_max": float(setosa.max()),
        "others_min": float(others.min()),
        "others_max": float(others.max()),
        "gap_others_min_minus_setosa_max": round(gap, 10),
        "separable_by_one_threshold": bool(gap > 0),
        "note": (
            "one-feature, one-threshold separation of setosa from the hard pair; "
            "descriptive census of these 150 rows, not a claim about new irises"
        ),
    }


def audit() -> dict[str, object]:
    """Build the deterministic full-150 census. Sorted keys, no timestamps."""
    frame = _full150()
    hard_pair = frame.loc[frame[SPECIES_COLUMN] != 0]

    full_tenths = _tenths(frame[FEATURE_COLUMNS].to_numpy())
    full_index = list(range(len(frame)))
    pair_tenths = _tenths(hard_pair[FEATURE_COLUMNS].to_numpy())
    pair_positions = list(range(len(hard_pair)))
    pair_full_index = [int(value) for value in hard_pair.index]

    payload_csv = frame.to_csv(index=False, float_format="%.1f")
    duplicates_full = _duplicate_groups(full_tenths, full_index)
    duplicates_pair = _duplicate_groups(pair_tenths, pair_positions)

    return {
        "class_counts": {
            "full150": {
                SPECIES_NAMES[code]: int(count)
                for code, count in sorted(Counter(frame[SPECIES_COLUMN]).items())
            },
            "hard_pair": {
                SPECIES_NAMES[code]: int(count)
                for code, count in sorted(Counter(hard_pair[SPECIES_COLUMN]).items())
            },
        },
        "decimal_precision": _decimal_profile(frame),
        "duplicate_row_groups": {
            "full150_indices_0based": duplicates_full,
            "hard_pair_positions_0based": duplicates_pair,
            "hard_pair_full150_indices_0based": _duplicate_groups(
                pair_tenths, pair_full_index
            ),
            "note": (
                "identical at 0.1 cm resolution is NOT proof of duplicated record "
                "entry; the twins ruling groups rows 102/143 (1-based) rather than "
                "deleting historical data"
            ),
        },
        "full150_csv_convention": FULL150_CSV_CONVENTION,
        "full150_sha256": hashlib.sha256(payload_csv.encode("utf-8")).hexdigest(),
        "near_duplicates_one_feature_0p1cm": {
            "definition": (
                "unordered row pairs identical in three features and differing by "
                "exactly one tenth (0.1 cm) in the fourth"
            ),
            "full150_count": len(_near_duplicates(full_tenths, full_index)),
            "full150_pairs_0based": _near_duplicates(full_tenths, full_index),
            "hard_pair_count": len(_near_duplicates(pair_tenths, pair_positions)),
            "hard_pair_pairs_positions_0based": _near_duplicates(
                pair_tenths, pair_positions
            ),
        },
        "per_feature": {
            "full150": _per_feature(frame),
            "hard_pair": _per_feature(hard_pair),
        },
        "rows": {"full150": int(len(frame)), "hard_pair": int(len(hard_pair))},
        "setosa_separability": _setosa_separability(frame),
        "sklearn_version": sklearn.__version__,
        "uci_comparison": _uci_comparison(frame),
    }


def write_audit(payload: dict[str, object], out_dir: Path) -> Path:
    path = out_dir / AUDIT_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="",
    )
    return path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="prepare 09-iris-first-lesson hard-pair data (+ the full-150 audit)"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="rebuild in memory and compare with the committed fixture; write nothing",
    )
    parser.add_argument(
        "--audit",
        action="store_true",
        help="write the deterministic full-150 audit JSON to fixtures/full150_audit.json",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=HERE,
        help="redirect outputs (default: the study directory)",
    )
    args = parser.parse_args()
    out_dir = args.out_dir.resolve()

    prepared = build()
    assert_contract(prepared)

    if args.check:
        fixture_path = out_dir / FIXTURE_REL
        if not fixture_path.is_file():
            raise SystemExit(f"missing fixture: {fixture_path}")
        rebuilt = serialize(prepared)
        committed = fixture_path.read_text(encoding="utf-8")
        if rebuilt != committed:
            raise SystemExit(f"fixture drift: {fixture_path} != freshly built frame")
        print(f"[OK] fixture matches a fresh build: {fixture_path}")
        print(f"[OK] prepared fingerprint: sha256={EXPECTED_SHA256}")
        return

    if args.audit:
        payload = audit()
        path = write_audit(payload, out_dir)
        uci = payload["uci_comparison"]
        separability = payload["setosa_separability"]
        print(f"sklearn: {payload['sklearn_version']}")
        print(f"full 150 rows: sha256={payload['full150_sha256']}")
        print(f"class counts: {payload['class_counts']['full150']}")
        print(
            "duplicate row groups (full 150, 0-based): "
            f"{payload['duplicate_row_groups']['full150_indices_0based']}"
        )
        print(
            "near-duplicates (one feature, 0.1 cm): "
            f"{payload['near_duplicates_one_feature_0p1cm']['full150_count']} full-150 pairs, "
            f"{payload['near_duplicates_one_feature_0p1cm']['hard_pair_count']} hard-pair pairs"
        )
        print(
            f"UCI diff: {uci['cell_diff_count']} cells on rows "
            f"{uci['rows_differing_0based']} (0-based), "
            f"{uci['rows_in_agreement']}/{uci['rows']} rows in agreement"
        )
        print(
            "setosa separability (petal_length_cm): setosa max "
            f"{separability['setosa_max']} < others min {separability['others_min']} "
            f"(gap {separability['gap_others_min_minus_setosa_max']} cm)"
        )
        print(f"wrote {path}  sha256={sha256(path)}")
        return

    prepared_path, fixture_path = write(prepared, out_dir)
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
    print(f"wrote {prepared_path}  sha256={sha256(prepared_path)}")
    print(f"wrote {fixture_path}  sha256={sha256(fixture_path)}")


if __name__ == "__main__":
    main()
