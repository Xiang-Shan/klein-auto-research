"""A discovery cell's entrypoint — adapter → template → pinned table → block.

Copy into the study as the cell's entrypoint (the file `entrypoint.mutable`
names, or a small runner it calls) and fill the four TODOs. One cell per run:

    klein generation surprise register --study studies/NN-slug
    klein generation check --study studies/NN-slug \
        --action cell --track <track> --cell cell_<name> --tests P<n>
    klein run-one --study studies/NN-slug --track <track> --tests P<n> \
        --description "<what this cell measures>"
    klein generation surprise record --study studies/NN-slug --run E####

What this file is responsible for, and nothing else:

1. call the ADAPTER (`lib/<adapter>.py`, hashed at registration, outside the
   mutable surface) to read the rows the cell declared as its `input_refs`;
2. call ONE template producer from `kleinlib.generation.templates`;
3. write the per-unit table to `tables/<cell_id>.tsv` and print its
   `artifact:` line, so the notary hashes it into the manifest;
4. print `printed_summary`, so the registered `expectation_P` is adjudicated by
   the notary on THIS run's printed block.

It computes no verdicts and applies no multiplicity rule. Those belong to
`klein generation surprise record`, once, afterwards, from the pinned bytes —
`.claude/skills/klein/references/surprise-protocol.md`.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True  # keep the study tree clean for the notary
sys.path.insert(0, str(Path(__file__).resolve().parent))

from kleinlib.eval import evaluate_table  # noqa: E402
from kleinlib.generation import templates  # noqa: E402

# TODO(1): the registered cell this entrypoint runs, and its declared statistic.
CELL_ID = "cell_<lowercase_name>"
STATISTIC = "mean_signed_residual"
INPUT = Path("data/prepared/<observations>.csv")


def main() -> None:
    started = time.time()

    # TODO(2): the adapter. It maps field measurements into the template's
    # arguments and lives outside entrypoint.mutable, hashed at registration.
    from lib.adapter import observations  # noqa: PLC0415

    rows = observations(INPUT)

    # TODO(3): ONE template producer. The segment column is the one the cell's
    # frozen inventory partitions; every registered segment must appear.
    units = templates.residual_by_segment(
        rows,
        segment_column="<segment column>",
        observed_column="<observed column>",
        expected_column="<model expectation column>",
        unit_column="<unit id column>",
    )
    # units = templates.error_slices(rows, segment_column=..., loss_column=...)
    # units = templates.family_disagreement(
    #     rows, segment_column=..., left_column=..., right_column=...
    # )

    table = Path("tables") / f"{CELL_ID}.tsv"
    table.parent.mkdir(parents=True, exist_ok=True)
    table.write_text(templates.render_table(units), encoding="utf-8")

    printed = templates.printed_summary(units, statistic=STATISTIC)
    # TODO(4): the cell's own primary metric for the ledger — often the largest
    # absolute deviation, which is also what a "no segment deviates" expectation
    # rule reads. The table is the measurement; this scalar is its ledger row.
    evaluate_table(
        table,
        printed["cell_max_abs_deviation"],
        exp_id=os.environ.get("KLEIN_EXPERIMENT_ID", "SMOKE"),
        metric_name="<metric>",
        metric_goal="lower",
        extra=printed,
        study_dir=Path.cwd(),
        t0=started,
    )


if __name__ == "__main__":
    main()
