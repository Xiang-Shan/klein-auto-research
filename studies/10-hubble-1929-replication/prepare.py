"""Prepare the immutable local artifact declared by study.yaml:data.prepared_path.

Both members of the bundled `hubble1929` dataset are resolved FROM THE CONTRACT
(`data.source` and `data.source_table2`) — no path is hardcoded — and written
into one faithful union frame with a `block` column taken solely from which file
each row came from. There is no seed here and no rule an argument could change:
this study's partition is the paper's own two tables.

Faithful means faithful. The prepared artifact carries every column of both
tables exactly as transcribed, including Table 2's `r_mpc`, `vs_kms` and `M_t` —
so a stranger can diff it against `datasets/hubble1929/*.csv`. Those three
columns are unreachable to the study because `lib/hubble.py:load_block()`, the
single door every cell goes through, drops them. Access control at the door
beats reshaping the evidence at the source (the dataset README refused to reshape
Table 2 to match a brief, and neither does this).

Also emits `data/prepared/index.csv` (`id, group, split`), the modality-agnostic
split index table, so the DATA gate's row-3 contamination checks can be
MECHANIZED with `python -m kleinlib.leakage --index ...` instead of reporting
N/A — which is what `data.split.kind: none` would otherwise force.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.hubble import (  # noqa: E402
    ANCHOR_N_TABLE1,
    ANCHOR_N_TABLE2,
    BLOCK_TABLE1,
    BLOCK_TABLE2,
    contract,
    resolve_table,
    study_dir,
)

#: Column order of the prepared union. Table 1 has no `vs_kms`; Table 2 has no
#: `m_s`. The union carries both, blank where the source table did not print it.
PREPARED_COLUMNS = (
    "block",
    "object_id",
    "object",
    "m_s",
    "r_mpc",
    "v_kms",
    "vs_kms",
    "m_t",
    "M_t",
)


def _object_key(name: str) -> str:
    """A normalized identity for one astronomical object, for the overlap check.

    `N.G.C.6822`, `6822` and `NGC 6822` all name the same object; the two tables
    use bare NGC numbers for most rows and the `N.G.C.` prefix for a few, so the
    key strips the prefix, punctuation and case.
    """
    key = str(name).strip().casefold()
    for prefix in ("n.g.c.", "ngc.", "ngc"):
        if key.startswith(prefix):
            key = key[len(prefix) :]
            break
    return "".join(ch for ch in key if ch.isalnum())


def main() -> None:
    root = study_dir()
    spec = contract()

    path1, digest1 = resolve_table("table1")
    path2, digest2 = resolve_table("table2")
    print(f"table1 sha256: {digest1}")
    print(f"table2 sha256: {digest2}")

    t1 = pd.read_csv(path1)
    t2 = pd.read_csv(path2)
    if len(t1) != ANCHOR_N_TABLE1 or len(t2) != ANCHOR_N_TABLE2:
        raise RuntimeError(
            f"row counts changed: table1={len(t1)} (expected {ANCHOR_N_TABLE1}), "
            f"table2={len(t2)} (expected {ANCHOR_N_TABLE2}) — the identity anchor "
            "is the point of a replication; STOP rather than proceed on new bytes"
        )

    t1 = t1.assign(block=BLOCK_TABLE1)
    t2 = t2.assign(block=BLOCK_TABLE2)
    frame = pd.concat([t1, t2], ignore_index=True)
    frame["object_id"] = [
        f"{block}:{_object_key(name)}"
        for block, name in zip(frame["block"], frame["object"], strict=True)
    ]
    for column in PREPARED_COLUMNS:
        if column not in frame.columns:
            frame[column] = pd.NA
    frame = frame[list(PREPARED_COLUMNS)]

    # No object may appear in BOTH tables: a shared galaxy would put the same
    # measurement on both sides of the seal. Hubble in fact drew them from
    # disjoint sets, and this asserts it rather than assuming it.
    keys1 = {_object_key(n) for n in t1["object"]}
    keys2 = {_object_key(n) for n in t2["object"]}
    shared = sorted(keys1 & keys2)
    if shared:
        raise RuntimeError(
            f"{len(shared)} object(s) appear in BOTH tables: {shared} — the sealed "
            "block would share rows with the development block"
        )
    print(f"objects table1: {len(keys1)}")
    print(f"objects table2: {len(keys2)}")
    print(f"objects shared: {len(shared)}")

    prepared = root / str(spec["data"]["prepared_path"])
    prepared.parent.mkdir(parents=True, exist_ok=True)
    prepared.write_text(
        frame.to_csv(index=False, lineterminator="\n"), encoding="utf-8", newline=""
    )
    print(f"prepared: {prepared.relative_to(root).as_posix()}  rows={len(frame)}")

    # The split index table: `split` names the realized partition, so the
    # mechanized row-3 audit has something concrete to check. Table 1 is this
    # study's whole adaptive block (nothing is fit-and-selected here — every
    # cell is a closed-form measurement over all 24 rows), so it maps to
    # `train`; Table 2 is the sealed block and maps to `test`.
    index = pd.DataFrame(
        {
            "id": frame["object_id"],
            "group": [key.split(":", 1)[1] for key in frame["object_id"]],
            "split": ["train" if b == BLOCK_TABLE1 else "test" for b in frame["block"]],
        }
    )
    index_path = prepared.parent / "index.csv"
    index_path.write_text(
        index.to_csv(index=False, lineterminator="\n"), encoding="utf-8", newline=""
    )
    print(f"index: {index_path.relative_to(root).as_posix()}  rows={len(index)}")


if __name__ == "__main__":
    main()
