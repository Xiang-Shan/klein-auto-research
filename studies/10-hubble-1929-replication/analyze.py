"""CELL E0005 — the nine-group solution (track `reproduction`, tests P3).

Phase adaptive-2. One published target: **K = 513 +/- 60 km/s/Mpc**, Hubble's
second solution, obtained by "combining them into 9 groups according to
proximity in direction and in distance" (`ref:hubble1929`, read at the METHOD
gate) and re-solving the same four-parameter model.

The textbook value 500 is usually attributed to this study. The article text
says something more specific, and this cell records it: 500 is neither of the
two solutions. It is the **intermediate value Hubble adopted** after noting that
the difference between 465 and 513 comes largely from the four Virgo-cluster
nebulae — "K = 500, A = 277 deg, D = +36 deg, V0 = 280 km/s".

**This cell does not fit that model either. It audits whether the nine groups
can be reconstructed, and pins the audit.** The behaviour was written down in
`program.md` under "Phase adaptive-2 slate" BEFORE the cell ran, with the rule
that an unavailable input counts as NOT reproduced.

Two things are required and neither is available:

1. the GROUPING — which of the 24 objects fall in each of the nine groups. The
   paper states the criterion ("proximity in direction and in distance") but
   never lists the membership. "Direction" is a sky position, which brings back
   E0004's missing coordinates; a grouping invented from `r_mpc` alone would be
   a different aggregation wearing the paper's name;
2. the same per-object coordinates the four-parameter model needs, since the
   nine-group solution is that same model applied to nine aggregated points.

The cell counts how many of the nine groups it can reconstruct from what the
paper prints — zero — and prints `groups_reconstructed`, which is exactly the
key P3's registered `inconclusive_if` reads.

The cell does compute one thing, because it costs nothing and the paper's own
sentence invites it: **how many of the 24 objects share a distance**, the only
grouping axis the tables carry. That number goes in the pinned table as
context — it is not a reconstruction, and it is not counted as one.
"""

from __future__ import annotations

import os
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from kleinlib.eval import evaluate_table  # noqa: E402

from lib.hubble import (  # noqa: E402
    BLOCK_TABLE1,
    HUBBLE_ADOPTED_K,
    HUBBLE_K_9GROUP,
    HUBBLE_PE_9GROUP,
    block_fingerprint,
    load_block,
    write_table,
)

SMOKE = os.environ.get("KLEIN_SMOKE") == "1"
EXPERIMENT_ID = os.environ.get("KLEIN_EXPERIMENT_ID") or ("SMOKE" if SMOKE else None)
TRACK = os.environ.get("KLEIN_TRACK") or ("reproduction" if SMOKE else None)

#: The paper's stated criterion, quoted so the audit is checkable against it.
GROUPING_CRITERION = "proximity in direction and in distance"

#: How many groups the paper reports.
GROUPS_REQUIRED = 9


def main() -> None:
    t0 = time.time()
    evaluation_kind = os.environ.get("KLEIN_EVALUATION_KIND")
    if SMOKE:
        evaluation_kind = evaluation_kind or "development"
    missing = [
        name
        for name, value in (
            ("KLEIN_EVALUATION_KIND", evaluation_kind),
            ("KLEIN_EXPERIMENT_ID", EXPERIMENT_ID),
            ("KLEIN_TRACK", TRACK),
        )
        if value is None
    ]
    if missing:
        raise RuntimeError(
            "analyze.py must be invoked through `klein run-one`. For a pre-run "
            "syntax/shape check use `KLEIN_SMOKE=1 python analyze.py`. "
            "Missing: " + ", ".join(missing)
        )

    table1 = load_block(BLOCK_TABLE1, echo=False)
    n_objects = len(table1)

    # Context only: the one grouping axis the printed table actually carries.
    distance_counts = Counter(float(x) for x in table1["r_mpc"])
    shared_distances = {d: n for d, n in distance_counts.items() if n > 1}
    objects_sharing = sum(shared_distances.values())
    distinct_distances = len(distance_counts)

    rows = [
        {
            "required_input": "group membership (which objects form each of the 9 groups)",
            "source_checked": "the article text (references.yaml:hubble1929)",
            "available": "no",
            "detail": (
                f'the paper states the criterion — "{GROUPING_CRITERION}" — but never '
                "lists the membership of any group"
            ),
        },
        {
            "required_input": "group membership",
            "source_checked": "bundled Table 1",
            "available": "no",
            "detail": (
                f"{distinct_distances} distinct r_mpc values among {n_objects} objects; "
                f"{objects_sharing} objects share a distance with at least one other "
                f"({len(shared_distances)} shared values). Distance alone cannot "
                "reproduce a grouping whose stated criterion is direction AND distance"
            ),
        },
        {
            "required_input": "direction (per-object equatorial coordinates)",
            "source_checked": "bundled Table 1 / the article text",
            "available": "no",
            "detail": (
                "the same inputs E0004 audited as unavailable; 'proximity in "
                "direction' cannot be evaluated without them"
            ),
        },
        {
            "required_input": "the four-parameter model on 9 aggregated points",
            "source_checked": "least squares on the above",
            "available": "no",
            "detail": (
                f"not attempted: 0 of {GROUPS_REQUIRED} groups are reconstructible, so "
                f"no solution exists to compare with {HUBBLE_K_9GROUP:g} +/- "
                f"{HUBBLE_PE_9GROUP:g}. Inventing a grouping would produce a number "
                "that is not the paper's"
            ),
        },
        {
            "required_input": "provenance of the textbook value 500",
            "source_checked": "the article text (references.yaml:hubble1929)",
            "available": "yes",
            "detail": (
                f"{HUBBLE_ADOPTED_K:g} is NEITHER published solution: the paper adopts "
                "it as an intermediate value after attributing the 465-vs-513 "
                "difference largely to the four Virgo-cluster nebulae "
                "(K = 500, A = 277 deg, D = +36 deg, V0 = 280 km/s)"
            ),
        },
    ]

    artifact = write_table(
        "tables/nine_group_inputs.tsv",
        ("required_input", "source_checked", "available", "detail"),
        rows,
    )

    evaluate_table(
        artifact,
        1,
        exp_id=EXPERIMENT_ID,
        study_dir=".",
        t0=t0,
        metric_name="targets_outside_tolerance",
        metric_goal="lower",
        split_fingerprint=block_fingerprint(table1),
        extra={
            "groups_reconstructed": 0.0,
            "groups_required": float(GROUPS_REQUIRED),
            "distinct_distances": float(distinct_distances),
            "objects_sharing_a_distance": float(objects_sharing),
            "n_objects": float(n_objects),
            "target_k": HUBBLE_K_9GROUP,
            "target_tolerance": HUBBLE_PE_9GROUP,
            "textbook_value": HUBBLE_ADOPTED_K,
        },
    )


if __name__ == "__main__":
    main()
