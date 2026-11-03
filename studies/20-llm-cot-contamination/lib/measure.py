"""The measurement machinery every cell of study 20 composes — NOT the mutable surface.

* **The index and the lanes.** :func:`read_index` reads the split index the
  CONTRACT names (``data.split.index`` under ``data.prepared_path``);
  item ids come only from ``kleinlib.data.load_items()``, which prints the
  ``split_fingerprint:`` line and honours the sealed dry run. A lane is a
  ``block`` of the index, intersected with the partition ``load_items`` handed
  back — so a cell can narrow what it was given, never widen it.
* **The intervals.** Percentile bootstrap, ``N_BOOT`` replicates, fixed
  ``BOOT_SEED``, ``CI_LEVEL``: a paired item bootstrap on independent GSM8K
  items, a paired CLUSTER bootstrap (whole templates resampled) on twin blocks,
  whose four instances of one template are not independent.
* **The table writer.** Fixed column order, ``%.6f`` floats, LF endings, no
  index; built but NOT written under ``KLEIN_SMOKE=1`` or a sealed dry run
  (either would leave an untracked file that blocks the next ``run-one``).
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from kleinlib.contract import load_contract
from kleinlib.data import index_path
from kleinlib.metrology import item_bootstrap, paired_bootstrap

#: Bootstrap replicates, seed and interval level — declared once, for every cell.
N_BOOT: int = 10_000
BOOT_SEED: int = 20261103
CI_LEVEL: float = 0.95

#: Blocks of the index (prepare.py writes exactly these).
BLOCK_ORIGINAL = "original"  # train: the 50 template-source GSM8K items
BLOCK_GSM8K = "gsm8k"  # development: 300 further GSM8K test items
BLOCK_TWIN_DEV = "twin_dev"  # development: twins, seed 20261104
BLOCK_TWIN_SEALED = "twin_sealed"  # test: twins, seed 20261105 — SEALED
TWIN_BLOCKS: tuple[str, ...] = (BLOCK_TWIN_DEV, BLOCK_TWIN_SEALED)

#: Under KLEIN_SMOKE=1 a cell looks at this many items / templates only.
SMOKE_ITEMS: int = 8
SMOKE_TEMPLATES: int = 3


def study_dir() -> Path:
    """This study's directory — the parent of `lib/`."""
    return Path(__file__).resolve().parent.parent


def smoke() -> bool:
    return os.environ.get("KLEIN_SMOKE") == "1"


def sealed_dry_run() -> bool:
    """True inside `klein run-one --final-test --dry-run` (served development data)."""
    return (
        os.environ.get("KLEIN_EVALUATION_KIND") == "final_test"
        and os.environ.get("KLEIN_SEALED_DRYRUN") == "1"
    )


def evaluation_kind() -> str:
    """``development`` or ``final_test`` — set by `klein run-one`, never chosen here."""
    return os.environ.get("KLEIN_EVALUATION_KIND") or "development"


def read_index() -> pd.DataFrame:
    """The split index (`data/prepared/index.csv`), indexed by item id, all text.

    ``answer`` is parsed to int; ``template`` is ``""`` for GSM8K-only items.
    """
    path = index_path(study_dir(), load_contract(study_dir()))
    if path is None or not path.is_file():
        raise FileNotFoundError(f"no split index at {path} — run prepare.py first")
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    frame["answer"] = frame["answer"].astype(int)
    return frame.set_index("id", drop=True)


def lane(index: pd.DataFrame, ids: Sequence[str], blocks: Iterable[str]) -> list[str]:
    """The ids of ``ids`` (a partition from ``load_items``) whose block is in ``blocks``."""
    wanted = set(blocks)
    return [item for item in ids if index.at[item, "block"] in wanted]


def twin_lane(index: pd.DataFrame, eval_ids: Sequence[str]) -> tuple[list[str], str]:
    """The twin block of the evaluation partition, and its name.

    twin_dev on development and on a sealed DRY RUN (which is served the
    development partition); twin_sealed on the one real sealed run, whose
    partition must then hold nothing else.
    """
    ids = lane(index, eval_ids, TWIN_BLOCKS)
    names = sorted({index.at[item, "block"] for item in ids})
    if len(names) != 1:
        raise RuntimeError(f"expected exactly one twin block in the evaluation partition, got {names}")
    if evaluation_kind() == "final_test" and not sealed_dry_run():
        if names != [BLOCK_TWIN_SEALED] or len(ids) != len(eval_ids):
            raise RuntimeError("the sealed partition must be exactly the twin_sealed block")
    return ids, names[0]


# --------------------------------------------------------------------------
# Intervals
# --------------------------------------------------------------------------


def _percentile_interval(values: Sequence[float]) -> tuple[float, float]:
    tail = (1.0 - CI_LEVEL) / 2.0
    low, high = np.quantile(np.asarray(values, dtype=float), [tail, 1.0 - tail])
    return float(low), float(high)


def paired_difference_ci(
    a: Sequence[float], b: Sequence[float], clusters: Sequence[str] | None = None
) -> tuple[float, float]:
    """Percentile CI of ``mean(a) - mean(b)`` on the same rows, in the same order.

    ``clusters=None`` resamples rows (``metrology.paired_bootstrap``: one index
    vector drawn per replicate and applied to both series). With ``clusters``
    whole clusters are resampled (``metrology.item_bootstrap`` with ``groups=``
    on the per-row differences, a ratio estimator, so unequal cluster sizes are
    handled): the paired cluster bootstrap a twin block needs.
    """
    left = np.asarray(a, dtype=float)
    right = np.asarray(b, dtype=float)
    if clusters is None:
        estimate = paired_bootstrap(left, right, n_boot=N_BOOT, seed=BOOT_SEED)
    else:
        estimate = item_bootstrap(left - right, n_boot=N_BOOT, seed=BOOT_SEED, groups=list(clusters))
    return _percentile_interval(estimate.values)


# --------------------------------------------------------------------------
# The deterministic table writer
# --------------------------------------------------------------------------


def table_text(columns: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> str:
    """The exact bytes of a pinned table: fixed columns, ``%.6f``, tab-separated, LF."""
    frame = pd.DataFrame(list(rows), columns=list(columns))
    return frame.to_csv(index=False, sep="\t", float_format="%.6f", lineterminator="\n")


def write_table(
    relative_path: str, columns: Sequence[str], rows: Iterable[Mapping[str, Any]]
) -> str | None:
    """Write a pinned ``artifact:`` table; return its study-relative path, or None.

    The text is always BUILT, so a formatting bug surfaces in the smoke check. It
    is WRITTEN only on a real run: under ``KLEIN_SMOKE=1`` nothing may be
    written, and a sealed dry run that left an untracked table behind would make
    the real sealed run refuse its dirty tree.
    """
    text = table_text(columns, rows)
    if smoke() or sealed_dry_run():
        return None
    path = study_dir() / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="")
    return Path(relative_path).as_posix()
