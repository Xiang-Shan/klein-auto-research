"""rq0_headroom.py — RQ0 measurement permission (deterministic reducer).

Answers, BEFORE any arena challenger number exists: *is this comparison
arithmetically capable of being won at all?*

Brier's ideal is 0.0 (`study.yaml tracks.*.metric.bound.ideal`). The largest
improvement any candidate could ever post is therefore the anchor's entire score.
Divide that by the bar it must clear:

    h_c = anchor_metrology_mean / floor_c        per CHALLENGER (candidate scale)
    h   = anchor_declared_dev   / minimum_delta  once           (ledger scale)

`h < 1` means not even a PERFECT score clears the bar: the comparison is
MEASUREMENT-CLOSED at that scale, and the pre-committed acknowledgement branch fires
(`on_infeasible: ack`). `h >= 1` means only "NOT ARITHMETICALLY EXCLUDED" — never
"plausible", never "likely" (klein v1.3 wording law).

THE TWO NUMERATORS ARE DIFFERENT NUMBERS AND MAY NEVER BE CONFLATED
------------------------------------------------------------------
`claims_discipline.banned` lists it explicitly: "conflating the two headroom
numerators (ledger h uses E0001's declared-split score; h_c uses the anchor
metrology mean — name which, every time)". This script therefore refuses to emit a
bare `h` column without its companions: every row carries `numerator_name` and
`denominator_name`, and the two scales occupy SEPARATE ROWS with a `scope` column.
Copy a row, never a number.

  * `anchor_metrology_mean` — the anchor's MEAN Brier over the 20 paired redraws
    (`sweeps/candidate_floors.tsv`, the anchor row, stat_kind `marginal-resplit`).
    A SCOUTING quantity, and the right numerator for a candidate-scale bar because
    `floor_c` was measured on that same redraw geometry.
  * `anchor_declared_dev` — E0001's val_brier on the DECLARED split (seed 20260909).
    One number, one split; the right numerator for the LEDGER scale because
    `minimum_delta` judges declared-split transactions.

RAISE-ONLY ESCALATION (`noise_floor_protocol.cross_check`): `--delta` is checked
against `ceil3dp(max challenger floor_c)` recomputed from the table. Equal is the
expected case; LARGER is lawful and reported as a documented raise; SMALLER is a
hard stop — "a floor may be raised by a documented rule, never lowered after seeing
data."

Deterministic: no seeds, no RNG, no wall-clock. Nothing is fitted.

Run (from the study directory, AFTER sweeps/candidate_floors.py and AFTER the
noise_floor paste + consult re-record)::

    uv run --locked python -u sweeps/rq0_headroom.py \
      --delta <registered minimum_delta> --anchor-dev <E0001 val_brier>

MEASUREMENT-SWEEP REDUCER: promotes no winner and writes no `results.tsv` row
(`references/sweep-rules.md` carve-out).
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import pandas as pd

STUDY_DIR = Path(__file__).resolve().parent.parent
if str(STUDY_DIR) not in sys.path:
    sys.path.insert(0, str(STUDY_DIR))
SWEEPS_DIR = STUDY_DIR / "sweeps"

import families  # noqa: E402  (needs STUDY_DIR on sys.path)

IN_NAME = "candidate_floors.tsv"
OUT_NAME = "rq0_headroom.tsv"
#: `study.yaml tracks.*.metric.bound.ideal` — Brier's ideal. Restated here ONLY to
#: make the arithmetic legible; `--ideal` overrides it for a contract change.
IDEAL = 0.0
NUM_CANDIDATE = "anchor_metrology_mean"
NUM_LEDGER = "anchor_declared_dev"

#: Every table THIS pipeline writes carries full-precision `repr` floats, and
#: pandas' default CSV float parser is NOT round-trip exact (it can be 1-2 ULP
#: off — measured: 0.011844522841099736 came back as 0.0118445228410997). Every
#: read of one of our own tables therefore pins the round-trip parser. The
#: PREPARED DATA read is deliberately LEFT on pandas' default, so the sweeps
#: parse the study CSV byte-for-byte the way `train.py` and kleinlib do.
FLOAT_PRECISION = "round_trip"


def ceil_3dp(value: float) -> float:
    """Round UP to 3 decimal places. Exact-boundary values are NOT bumped."""
    return math.ceil(value * 1000.0 - 1e-12) / 1000.0


def load_floors(path: Path) -> pd.DataFrame:
    if not path.is_file():
        raise SystemExit(f"missing {path} — run sweeps/candidate_floors.py first")
    df = pd.read_csv(path, sep="\t", float_precision=FLOAT_PRECISION)
    needed = {"family", "role", "stat_kind", "k", "mean_d", "floor_c"}
    missing = needed - set(df.columns)
    if missing:
        raise SystemExit(f"{path}: missing column(s) {sorted(missing)}")
    return df


def anchor_metrology_mean(floors: pd.DataFrame) -> tuple[float, int]:
    """`(mean, k)` from the anchor's MARGINAL row — the CANDIDATE-scale numerator."""
    rows = floors[(floors["role"] == "anchor") & (floors["stat_kind"] == "marginal-resplit")]
    if len(rows) != 1:
        raise SystemExit(
            f"expected exactly 1 anchor marginal-resplit row, found {len(rows)} — "
            "the RQ0 numerator is undefined"
        )
    return float(rows.iloc[0]["mean_d"]), int(rows.iloc[0]["k"])


def headroom(numerator: float, denominator: float, ideal: float = IDEAL) -> float:
    """(numerator - ideal) / denominator. Ideal 0.0 makes this numerator/denominator."""
    if denominator <= 0.0:
        raise SystemExit(f"headroom denominator must be > 0, got {denominator!r}")
    return (numerator - ideal) / denominator


def check_delta(floors: pd.DataFrame, delta: float) -> str:
    """RAISE-ONLY escalation check against the recomputed challenger max."""
    chall = floors[floors["role"] == "challenger"]
    if chall.empty:
        raise SystemExit("candidate_floors.tsv has no challenger rows")
    recomputed = ceil_3dp(float(chall["floor_c"].astype(float).max()))
    if math.isclose(delta, recomputed, rel_tol=0.0, abs_tol=1e-12):
        return f"AGREES with ceil3dp(max challenger floor_c) = {recomputed:.6g}"
    if delta > recomputed:
        return (
            f"RAISED above the measured scalar {recomputed:.6g} (raise-only "
            "escalation — lawful, and must be documented in the study record)"
        )
    raise SystemExit(
        f"REFUSING: --delta {delta:.6g} is BELOW ceil3dp(max challenger floor_c) "
        f"= {recomputed:.6g}. A floor may be raised by a documented rule; it may "
        "never be lowered after seeing data (noise_floor_protocol.cross_check)."
    )


def build_rows(
    floors: pd.DataFrame, anchor_mean: float, anchor_dev: float, delta: float
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    order = {f: i for i, f in enumerate(families.CHALLENGERS)}
    chall = floors[floors["role"] == "challenger"].copy()
    chall["_order"] = chall["family"].map(order)
    if chall["_order"].isna().any():
        unknown = sorted(chall.loc[chall["_order"].isna(), "family"])
        raise SystemExit(f"challenger(s) not in families.CHALLENGERS: {unknown}")
    for _, r in chall.sort_values("_order").iterrows():
        floor_c = float(r["floor_c"])
        h_c = headroom(anchor_mean, floor_c)
        rows.append(
            {
                "scope": "candidate",
                "family": str(r["family"]),
                "numerator_name": NUM_CANDIDATE,
                "numerator": repr(anchor_mean),
                "denominator_name": "floor_c",
                "denominator": repr(floor_c),
                "ideal": IDEAL,
                "h": repr(h_c),
                "measurement_closed": bool(h_c < 1.0),
            }
        )
    h_ledger = headroom(anchor_dev, delta)
    rows.append(
        {
            "scope": "ledger",
            "family": families.ANCHOR,
            "numerator_name": NUM_LEDGER,
            "numerator": repr(anchor_dev),
            "denominator_name": "minimum_delta",
            "denominator": repr(delta),
            "ideal": IDEAL,
            "h": repr(h_ledger),
            "measurement_closed": bool(h_ledger < 1.0),
        }
    )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="RQ0 headroom (deterministic reducer)")
    parser.add_argument(
        "--delta", type=float, required=True,
        help="the REGISTERED minimum_delta scalar now pasted into study.yaml",
    )
    parser.add_argument(
        "--anchor-dev", type=float, required=True,
        help="E0001's val_brier on the DECLARED split (the LEDGER numerator)",
    )
    parser.add_argument("--ideal", type=float, default=IDEAL, help="metric ideal (Brier: 0.0)")
    parser.add_argument("--in-table", default=IN_NAME, help=f"default: {IN_NAME}")
    parser.add_argument("--out", default=OUT_NAME, help=f"default: {OUT_NAME}")
    args = parser.parse_args()

    floors = load_floors(SWEEPS_DIR / args.in_table)
    verdict = check_delta(floors, args.delta)
    anchor_mean, anchor_k = anchor_metrology_mean(floors)
    rows = build_rows(floors, anchor_mean, args.anchor_dev, args.delta)

    out_path = SWEEPS_DIR / args.out
    pd.DataFrame(rows).to_csv(out_path, sep="\t", index=False)
    print(f"wrote {out_path}")

    print()
    print("=" * 78)
    print(f"RQ0 — MEASUREMENT PERMISSION (ideal = {args.ideal:.6g}; "
          "h = (numerator - ideal) / bar)")
    print("=" * 78)
    print(f"--delta check: {verdict}")
    print()
    print("CANDIDATE SCALE — numerator: anchor_metrology_mean = "
          f"{anchor_mean!r}")
    print(f"  (the anchor's MEAN Brier over the k={anchor_k} paired redraws — a "
          "SCOUTING quantity)")
    print(f"  {'challenger':<18} {'floor_c':>11} {'h_c':>9}  verdict")
    for r in rows:
        if r["scope"] != "candidate":
            continue
        h_c = float(str(r["h"]))
        verdict_c = "MEASUREMENT-CLOSED" if r["measurement_closed"] else "not arithmetically excluded"
        print(f"  {str(r['family']):<18} {float(str(r['denominator'])):>11.6f} "
              f"{h_c:>9.3f}  {verdict_c}")
    closed = [str(r["family"]) for r in rows if r["scope"] == "candidate" and r["measurement_closed"]]
    open_c = [str(r["family"]) for r in rows if r["scope"] == "candidate" and not r["measurement_closed"]]
    print(f"  -> measurement-closed: {closed if closed else 'NONE'}")
    print(f"  -> not arithmetically excluded: {open_c if open_c else 'NONE'}")

    ledger = [r for r in rows if r["scope"] == "ledger"][0]
    h = float(str(ledger["h"]))
    print()
    print(f"LEDGER SCALE — numerator: anchor_declared_dev = {args.anchor_dev!r} "
          "(E0001, declared split)")
    print(f"  minimum_delta {args.delta:.6g}   h = {h:.3f}")
    if h < 1.0:
        print("  -> DOOR-CLOSED branch FIRES: h < 1. The ledger comparison is")
        print("     MEASUREMENT-CLOSED — not even a perfect Brier clears the scalar.")
        print("     Record the PRE-COMMITTED headroom acknowledgement (bound.on_infeasible:")
        print("     ack) and run the parade anyway as a DESCRIPTIVE exhibit. Per-candidate")
        print("     h_c keeps the tight-floor comparisons honestly open.")
    else:
        print("  -> DOOR-AJAR branch FIRES: h >= 1. A scalar-delta keep is NOT")
        print("     ARITHMETICALLY EXCLUDED (never 'plausible'). The parade is a live")
        print("     contest and the ledger judges normally. No redraw, no re-registration.")

    print()
    print("NEVER conflate the two numerators. anchor_metrology_mean (20 redraws, "
          "scouting)")
    print("and anchor_declared_dev (E0001, one declared split) are different numbers on")
    print("different scales; every row above names its own.")
    print()
    print("MEASUREMENT SWEEP: no winner promoted, no results.tsv row (sweep-rules.md carve-out)")


if __name__ == "__main__":
    main()
