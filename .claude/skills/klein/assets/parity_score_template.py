"""lib/parity_score.py — the study-local parity scorer (generation layer, opt-in).

Copy this into the study as the path `parity.yaml`'s `scorer.path` names, fill
the two TODOs, and call it from the entrypoint of the sealed comparison cell.

**It is study LIBRARY code, never the mutable surface.**  `klein generation
parity bind` pins its sha256 and `generation verify` re-reads it at the sealed
cell's candidate commit: a scorer edited between the bind and the comparison is a
checker tuned to the answer (R-INV-3, "the checker is never the searcher").

What it must produce, and why each piece is load-bearing
--------------------------------------------------------

1. `tables/parity_units.tsv` — one row per sampling unit: `unit`, `block`, then
   `ai_<key>` and `expert_<key>` for every locked metric.  Those columns are the
   metric's PER-UNIT CONTRIBUTIONS, so the metric is their mean; a metric that is
   not a unit mean is expressed through contributions here, and `parity.yaml`'s
   `estimand` says so.  This table is what `parity assess` and `generation
   verify` recompute the verdict FROM — the printed bounds are checked against
   it, never trusted.

2. The printed block, through `kleinlib.eval.evaluate_table`.  That evaluator is
   the one that pins an `artifact:` line, and the pin is what makes the table
   citable evidence (`references/registered-mode.md`).  `evaluate_test` prints a
   p-value as the primary metric and would say something this cell is not
   claiming; the comparison's summary scalar is a difference, not a test.

3. `defined_<key>` for EVERY metric.  An undefined metric (A4 §7's
   top-to-bottom ratio on a zero-loss bottom decile) prints `NA` for its numbers
   — a non-finite line aborts the notary's parser — and declares
   `defined_<key>: 0`.  Silence about a metric is not the same as saying it could
   not be computed, and `parity cell` FAILs on the difference.

Run it under the notary, never by hand:

    uv run --locked klein run-one --study studies/NN-slug --track comparison \\
        --final-test --dry-run                       # mandatory rehearsal
    uv run --locked klein generation check --study studies/NN-slug \\
        --action sealed --track comparison --tests P1 P2 P3
    uv run --locked klein run-one --study studies/NN-slug --track comparison \\
        --final-test --tests P1,P2,P3
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from kleinlib.eval import evaluate_table
from kleinlib.generation.stats import simultaneous_bounds

STUDY_DIR = Path(__file__).resolve().parents[1]
UNITS_TABLE = "tables/parity_units.tsv"


def locked_criteria() -> dict[str, Any]:
    """The metrics and the uncertainty rule, read from the LOCKED file.

    Reading them here rather than restating them keeps one copy: the file the
    lock hashed is the file the scorer obeys.
    """
    return yaml.safe_load((STUDY_DIR / "parity.yaml").read_text(encoding="utf-8"))


def score_units(criteria: dict[str, Any]) -> dict[str, Any]:
    """TODO: score BOTH pipelines on the SAME units, in the SAME order.

    Returns ``{"unit": [...], "block": [...], "columns": {"ai_<key>": array,
    "expert_<key>": array, ...}}``.  Load the frozen snapshots `parity bind`
    pinned — not a re-fit — and honour `parity.yaml`'s `budget_rule`.

    A metric that cannot be computed on this data yields a column of ``nan``;
    that is what makes it undefined, and undefined can never pass.
    """
    raise NotImplementedError("score both frozen pipelines at the declared sampling unit")


def write_units_table(units: dict[str, Any], keys: list[str]) -> Path:
    path = STUDY_DIR / UNITS_TABLE
    path.parent.mkdir(parents=True, exist_ok=True)
    header = ["unit", "block", *[f"{side}_{key}" for key in keys for side in ("ai", "expert")]]
    lines = ["\t".join(header)]
    for index in range(len(units["unit"])):
        cells = [str(units["unit"][index]), str(units["block"][index])]
        for key in keys:
            for side in ("ai", "expert"):
                cells.append(format(float(units["columns"][f"{side}_{key}"][index]), ".12g"))
        lines.append("\t".join(cells))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> None:
    criteria = locked_criteria()
    metrics = criteria["metrics"]
    keys = [str(row["key"]) for row in metrics]
    uncertainty = criteria["uncertainty"]

    units = score_units(criteria)
    write_units_table(units, keys)

    columns = {name: np.asarray(values, dtype=float) for name, values in units["columns"].items()}
    blocks = units["block"] if criteria.get("block_column") else None
    deltas = {}
    for row in metrics:
        key = str(row["key"])
        sign = 1.0 if str(row["direction"]) == "higher" else -1.0
        deltas[key] = sign * (columns[f"ai_{key}"] - columns[f"expert_{key}"])
    bounds = simultaneous_bounds(
        deltas,
        blocks,
        n_boot=int(uncertainty["n_boot"]),
        seed=int(uncertainty["seed"]),
        alpha=float(uncertainty["alpha"]),
    )

    extra: dict[str, Any] = {
        "n_units": len(units["unit"]),
        "n_blocks": len(set(map(str, units["block"]))) if blocks is not None else len(units["unit"]),
    }
    for key in keys:
        low, high = bounds[key]
        values = {
            f"ai_{key}": float(np.mean(columns[f"ai_{key}"])),
            f"expert_{key}": float(np.mean(columns[f"expert_{key}"])),
            f"d_{key}": float(np.mean(deltas[key])),
            f"L_{key}": low,
            f"U_{key}": high,
        }
        defined = all(math.isfinite(value) for value in values.values())
        # `NA` for an undefined metric: a non-finite line aborts the notary's
        # parser, and the declaration below is what says the omission is honest.
        extra.update({name: (value if defined else "NA") for name, value in values.items()})
        extra[f"defined_{key}"] = 1 if defined else 0

    # TODO: the summary scalar is the study's choice and must match the
    # comparison track's declared metric name and goal.  The primary metric's
    # direction-adjusted difference is the natural one — but the DECISION is made
    # on the printed L/U by `parity assess`, never on this scalar.
    primary = float(np.mean(deltas[keys[0]]))
    evaluate_table(
        STUDY_DIR / UNITS_TABLE,
        primary,
        exp_id=0,  # TODO: os.environ["KLEIN_EXPERIMENT_ID"]
        metric_name="TODO: the comparison track's metric name",
        metric_goal="higher",
        extra=extra,
        split_fingerprint=None,  # TODO: the contract's split fingerprint
        study_dir=STUDY_DIR,
    )


if __name__ == "__main__":
    main()
