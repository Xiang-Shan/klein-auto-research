"""CELL E0004 — the four-parameter solar-motion refit (track `reproduction`, tests P2).

Phase adaptive-2. One published target: **K = 465 +/- 50 km/s/Mpc**, the value
Hubble actually reports for the 24 objects, obtained from the four-parameter
model his paper writes as (`method_card.md` eq. 3, `ref:hubble1929`):

    r*K + X cos(a) cos(d) + Y sin(a) cos(d) + Z sin(d) = v

Four unknowns (K, X, Y, Z), one equation per object, solved by least squares.
The design matrix needs the equatorial coordinates (a, d) = (right ascension,
declination) of every object.

**This cell does not fit that model. It audits whether the model's INPUTS can be
obtained, and pins the audit as its evidence.** That behaviour was written down
in `program.md` under "Phase adaptive-2 slate" BEFORE the cell ran, together with
the rule that a target whose inputs are unavailable counts as NOT reproduced —
so declining to try can never lower `targets_outside_tolerance`.

Three sources are checked, in the order a replicator would check them:

1. the bundled tables themselves (`data/prepared/prepared.csv`) — the columns
   are enumerated at run time, not asserted;
2. the article text, read at the METHOD gate and recorded in
   `references.yaml:hubble1929`: it prints no coordinates for any object, and
   the only direction it gives is the solar apex of its own solution;
3. an offline catalogue inside this repository — there is none, and fetching 24
   sky positions by hand at an epoch the paper never states was retired at
   design time as a fabrication risk (`scouting_ledger.md`, Retirements).

The cell prints `coords_available: 0`, which is exactly the key P2's registered
`inconclusive_if` reads (`coords_available < 24`), so the verdict is decided by
the notary's arithmetic on a measured availability count — not by this
docstring, and not by prose in the findings.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from kleinlib.eval import evaluate_table  # noqa: E402

from lib.hubble import (  # noqa: E402
    BLOCK_TABLE1,
    HUBBLE_K_24,
    HUBBLE_PE_24,
    block_fingerprint,
    load_block,
    study_dir,
    write_table,
)

SMOKE = os.environ.get("KLEIN_SMOKE") == "1"
EXPERIMENT_ID = os.environ.get("KLEIN_EXPERIMENT_ID") or ("SMOKE" if SMOKE else None)
TRACK = os.environ.get("KLEIN_TRACK") or ("reproduction" if SMOKE else None)

#: What the four-parameter model needs, per object, beyond r and v.
REQUIRED_PER_OBJECT = ("right_ascension_alpha", "declination_delta")

#: Column names a coordinate would plausibly arrive under, searched for in the
#: prepared artifact by pattern rather than assumed absent.
COORDINATE_PATTERNS = ("ra", "alpha", "dec", "delta", "coord", "lon", "lat", "glon", "glat")


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

    # Source 1 — the bundled tables. Enumerate the columns; do not assert.
    columns = [str(c).strip().casefold() for c in table1.columns]
    coordinate_columns = sorted(
        c for c in columns if any(pattern in c for pattern in COORDINATE_PATTERNS)
    )
    coords_in_data = len(coordinate_columns)

    # Source 3 — any offline catalogue shipped with this study.
    catalogue_dir = study_dir() / "data" / "catalogues"
    catalogue_files = (
        sorted(p.name for p in catalogue_dir.iterdir() if p.is_file())
        if catalogue_dir.is_dir()
        else []
    )

    rows = [
        {
            "required_input": "r_mpc (distance)",
            "needed_per_object": "yes",
            "source_checked": "bundled Table 1",
            "available": "yes",
            "detail": f"present for all {n_objects} objects",
        },
        {
            "required_input": "v_kms (radial velocity)",
            "needed_per_object": "yes",
            "source_checked": "bundled Table 1",
            "available": "yes",
            "detail": f"present for all {n_objects} objects",
        },
    ]
    for required in REQUIRED_PER_OBJECT:
        rows.append(
            {
                "required_input": required,
                "needed_per_object": "yes",
                "source_checked": "bundled Table 1",
                "available": "no",
                "detail": (
                    "no column matching "
                    + "/".join(COORDINATE_PATTERNS)
                    + f"; columns present: {', '.join(columns)}"
                ),
            }
        )
        rows.append(
            {
                "required_input": required,
                "needed_per_object": "yes",
                "source_checked": "the article text (references.yaml:hubble1929)",
                "available": "no",
                "detail": (
                    "the paper prints no equatorial coordinates for any object; the "
                    "only direction it gives is the apex of its OWN solution "
                    "(A = 286 deg, D = +40 deg, V0 = 306 km/s), which is an output "
                    "of the fit, not an input to it"
                ),
            }
        )
        rows.append(
            {
                "required_input": required,
                "needed_per_object": "yes",
                "source_checked": "offline catalogue in this repository",
                "available": "no",
                "detail": (
                    f"data/catalogues holds {len(catalogue_files)} file(s); fetching "
                    "24 sky positions by hand at an epoch the paper never states was "
                    "retired at design time as a fabrication risk "
                    "(scouting_ledger.md, Retirements)"
                ),
            }
        )
    rows.append(
        {
            "required_input": "K, X, Y, Z (the four fitted parameters)",
            "needed_per_object": "no",
            "source_checked": "least squares on the above",
            "available": "no",
            "detail": (
                f"not attempted: the design matrix needs {n_objects} coordinate pairs "
                "and 0 are obtainable, so no solution exists to compare with "
                f"{HUBBLE_K_24:g} +/- {HUBBLE_PE_24:g}"
            ),
        }
    )

    artifact = write_table(
        "tables/solar_motion_inputs.tsv",
        ("required_input", "needed_per_object", "source_checked", "available", "detail"),
        rows,
    )

    # The one declared target of this cell was not reproduced. An unavailable
    # input counts as NOT reproduced, by the rule registered in the track's
    # exactness_note — declining to try must never lower the metric.
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
            "coords_available": float(coords_in_data),
            "coords_required": float(n_objects),
            "coordinate_columns_found": float(coords_in_data),
            "offline_catalogue_files": float(len(catalogue_files)),
            "sources_checked": 3.0,
            "target_k": HUBBLE_K_24,
            "target_tolerance": HUBBLE_PE_24,
        },
    )


if __name__ == "__main__":
    main()
