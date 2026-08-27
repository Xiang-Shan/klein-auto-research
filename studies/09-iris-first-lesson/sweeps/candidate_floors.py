"""candidate_floors.py — the per-candidate PAIRED floors (deterministic reducer).

Reads ONE committed artifact — `sweeps/metrology_paired.sidecar.tsv` — and writes
`sweeps/candidate_floors.tsv`. **Nothing is fitted here.** Splitting the reduction
from the fitting is deliberate: the study's ruler can be recomputed, audited and
re-derived by a reviewer without re-running a single model, and the reduction has no
seed, no RNG and no wall-clock dependence (claim 08#C11's discipline extended: a
reducer with no seeds cannot overflow one).

THE REGISTERED STATISTIC (study.yaml `noise_floor_protocol.statistic`)
----------------------------------------------------------------------
Per candidate c (the 7 challengers and the 2 controls), over the 20 registered
paired redraws:

    d_c(draw) = brier_c(draw) - brier_anchor(draw)      # SAME rows, SAME draw
    floor_c   = max( 2 * std(d_c, ddof=1) , range(d_c) / 2 )     FULL precision

and the single ledger scalar pasted into BOTH tracks:

    minimum_delta = ceil3dp( max over the 7 CHALLENGER floors )

CONTROLS ARE EXCLUDED FROM THE MAX, by registration: "a deliberately
information-destroyed control may not set the ruler". Their floors are still
computed, published and printed — as an exhibit, never as an input to the scalar.

SIGN CONVENTION: POSITIVE `mean_d` means the candidate is WORSE than the anchor
(d = candidate - anchor). The ARENA's `mean_gain = brier_anchor - brier_f` has the
OPPOSITE sign. `floor_c` itself is sign-free: std and range are dispersion
functionals, so this file's sign convention cannot leak into the bar.

DIRECTION RATIONALE (study.yaml, quoted because it is the whole ethics of the rule):
"a per-candidate floor here is a CLEARANCE bar the candidate must beat — a wide band
penalizes that candidate's own case. This is the opposite failure mode from study
07's banned per-method tie-buying floors (there a wide band bought a tie)."

BLINDNESS CLAUSE: `floor_c` is a LOCATION-INVARIANT dispersion functional of `d_c`
(std and range ignore the mean), so no observed gain can tune it; and the verdict
rule was frozen at the METHOD gate before the metrology ran.

CROSS-CHECK (registered): `kleinlib.noise_floor.summarize_noise` computes exactly
this study's conventions (`statistics.stdev` ddof=1, `max - min`, and
`suggested_minimum_delta = max(2*std, range/2)` — which IS `floor_c`, so study 09 has
no ceil-then-compare gap the way 07/08 did). This script computes both paths and
REFUSES TO WRITE if they disagree.

PRECISION NOTE (disclosure, not a defect): `kleinlib.sweep` serializes
`primary_metric` with `f"{metric:.6f}"`, so every `d_c` is a difference of two
6-decimal numbers. "FULL precision" below means full float precision of the value
derived from those inputs (`repr`, round-trip exact) — it does not manufacture
resolution the sidecar never had. At Brier ~1e-2 that is >= 4 significant digits.

OUTPUT — `sweeps/candidate_floors.tsv`
--------------------------------------
One row per NON-ANCHOR family (role challenger|control, stat_kind
`paired-comparison`) plus ONE anchor row carrying the anchor's MARGINAL spread
(stat_kind `marginal-resplit`, floor_c = the marginal 2*std) for the RQ0 exhibit.
The `mean_d/std_d/range_d` column NAMES are shared by both stat_kinds; `stat_kind`
is the column that says which quantity they hold. Never read a row without it.

Run (from the study directory, AFTER sweeps/metrology_paired.py)::

    uv run --locked python -u sweeps/candidate_floors.py

MEASUREMENT-SWEEP REDUCER: promotes no winner and writes no `results.tsv` row
(`references/sweep-rules.md` carve-out).
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from pathlib import Path

import pandas as pd

STUDY_DIR = Path(__file__).resolve().parent.parent
if str(STUDY_DIR) not in sys.path:
    sys.path.insert(0, str(STUDY_DIR))
SWEEPS_DIR = STUDY_DIR / "sweeps"

import families  # noqa: E402  (needs STUDY_DIR on sys.path)

from kleinlib.noise_floor import summarize_noise  # noqa: E402

SIDECAR = "metrology_paired.sidecar.tsv"
OUT_NAME = "candidate_floors.tsv"
MEASURED_AFTER = "E0001"
METHOD = "paired-redraw"
ESTIMAND = "paired-comparison"
MARGINAL_ESTIMAND = "marginal-resplit"
#: Agreement tolerance for the two independent computation paths. Both use
#: `statistics.stdev`/`max-min`, so exact equality is the expectation; the
#: tolerance exists so a future kleinlib refactor fails LOUDLY, not silently.
CROSS_CHECK_TOL = 1e-15

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


def paired_stats(values: list[float]) -> dict[str, float]:
    """k / mean / std(ddof=1) / range / floor = max(2*std, range/2), no rounding."""
    if len(values) < 2:
        raise ValueError(f"a paired floor needs k >= 2 values, got {len(values)}")
    std = statistics.stdev(values)
    value_range = max(values) - min(values)
    return {
        "k": len(values),
        "mean": statistics.fmean(values),
        "std": std,
        "range": value_range,
        "floor": max(2.0 * std, value_range / 2.0),
    }


def cross_check(values: list[float], mine: dict[str, float]) -> None:
    """Refuse to write if kleinlib's conventions and ours disagree."""
    theirs = summarize_noise(values)
    pairs = (
        ("std", mine["std"], theirs.std),
        ("range", mine["range"], theirs.value_range),
        ("mean", mine["mean"], theirs.mean),
        ("floor", mine["floor"], theirs.suggested_minimum_delta),
        ("k", float(mine["k"]), float(theirs.k)),
    )
    bad = [
        f"{name}: local {a!r} vs kleinlib {b!r}"
        for name, a, b in pairs
        if not math.isclose(a, b, rel_tol=0.0, abs_tol=CROSS_CHECK_TOL)
    ]
    if bad:
        raise SystemExit(
            "REFUSING TO WRITE — the local reduction and kleinlib.noise_floor "
            "disagree:\n  " + "\n  ".join(bad)
        )


def load_series(path: Path) -> tuple[dict[str, dict[int, float]], dict[str, str]]:
    """`(family -> {draw: brier}, family -> role)` from the metrology sidecar.

    Only `status == ok` rows count; a crashed cell is simply absent from that
    family's series and shrinks its k — recorded honestly, never re-run.
    """
    df = pd.read_csv(path, sep="\t", float_precision=FLOAT_PRECISION)
    missing = [c for c in ("params_json", "primary_metric", "status") if c not in df.columns]
    if missing:
        raise SystemExit(f"{path}: not a sweep sidecar (missing {missing})")
    series: dict[str, dict[int, float]] = {}
    roles: dict[str, str] = {}
    for _, row in df.iterrows():
        params = json.loads(row["params_json"])
        family = str(params["family"])
        roles.setdefault(family, str(params.get("role", "unknown")))
        if row["status"] != "ok" or pd.isna(row["primary_metric"]):
            continue
        series.setdefault(family, {})[int(params["draw"])] = float(row["primary_metric"])
    return series, roles


def check_roster(roles: dict[str, str]) -> None:
    """The sidecar's roster must be the registered roster — no drift, either way."""
    sidecar_chall = {f for f, r in roles.items() if r == "challenger"}
    sidecar_ctrl = {f for f, r in roles.items() if r == "control"}
    problems = []
    if families.ANCHOR not in roles:
        problems.append(f"anchor {families.ANCHOR!r} missing from the sidecar")
    if sidecar_chall != set(families.CHALLENGERS):
        problems.append(
            f"challenger set drift: sidecar {sorted(sidecar_chall)} vs "
            f"families.CHALLENGERS {sorted(families.CHALLENGERS)}"
        )
    if sidecar_ctrl != set(families.CONTROLS):
        problems.append(
            f"control set drift: sidecar {sorted(sidecar_ctrl)} vs "
            f"families.CONTROLS {sorted(families.CONTROLS)}"
        )
    if problems:
        raise SystemExit(
            "REFUSING TO STATE A FLOOR — roster drift between the sidecar and "
            "families.py:\n  " + "\n  ".join(problems)
        )


def build_rows(
    series: dict[str, dict[int, float]], roles: dict[str, str]
) -> tuple[list[dict[str, object]], dict[str, list[float]]]:
    """The candidate_floors.tsv rows, plus each candidate's raw `d_c` series."""
    anchor = series.get(families.ANCHOR, {})
    if len(anchor) < 3:
        raise SystemExit(
            f"need >= 3 successful anchor draws to state a floor, got {len(anchor)}"
        )
    anchor_draws = sorted(anchor)
    anchor_values = [anchor[d] for d in anchor_draws]

    rows: list[dict[str, object]] = []
    d_series: dict[str, list[float]] = {}

    # --- the anchor's MARGINAL exhibit (RQ0): NOT a clearance bar for anyone ---
    marginal = paired_stats(anchor_values)
    cross_check(anchor_values, marginal)
    rows.append(
        {
            "family": families.ANCHOR,
            "role": "anchor",
            "stat_kind": MARGINAL_ESTIMAND,
            "k": marginal["k"],
            "mean_d": repr(marginal["mean"]),
            "std_d": repr(marginal["std"]),
            "range_d": repr(marginal["range"]),
            "floor_c": repr(2.0 * marginal["std"]),
            "floor_rule": "2*std (MARGINAL; RQ0 exhibit only — never a clearance bar)",
        }
    )

    ordered = [(f, "challenger") for f in families.CHALLENGERS]
    ordered += [(f, "control") for f in families.CONTROLS]
    for family, role in ordered:
        got = series.get(family, {})
        draws = [d for d in anchor_draws if d in got]
        if len(draws) < 2:
            raise SystemExit(
                f"{family}: only {len(draws)} paired draw(s) survived — a floor "
                "cannot be stated and the cell may NOT be silently dropped; "
                "re-record the metrology or register the omission"
            )
        d = [got[dd] - anchor[dd] for dd in draws]
        stats = paired_stats(d)
        cross_check(d, stats)
        d_series[family] = d
        rows.append(
            {
                "family": family,
                "role": role,
                "stat_kind": ESTIMAND,
                "k": stats["k"],
                "mean_d": repr(stats["mean"]),
                "std_d": repr(stats["std"]),
                "range_d": repr(stats["range"]),
                "floor_c": repr(stats["floor"]),
                "floor_rule": "max(2*std, range/2)",
            }
        )
    return rows, d_series


def binding_challenger(rows: list[dict[str, object]]) -> tuple[str, float]:
    """Largest `floor_c` among CHALLENGERS; ties broken by registry order."""
    order = {f: i for i, f in enumerate(families.CHALLENGERS)}
    candidates = [r for r in rows if r["role"] == "challenger"]
    if not candidates:
        raise SystemExit("no challenger rows — the ledger scalar is undefined")
    best = min(
        candidates,
        key=lambda r: (-float(str(r["floor_c"])), order[str(r["family"])]),
    )
    return str(best["family"]), float(str(best["floor_c"]))


def print_paste_block(
    scalar: float, family: str, d: list[float], draws: int | None = None
) -> None:
    """The paste-ready study.yaml block, built from the BINDING challenger's series."""
    stats = paired_stats(d)
    print()
    print("--- paste into study.yaml under BOTH tracks' metric (primary AND challenger) ---")
    print(f"      minimum_delta: {scalar:.6g}   # ceil3dp(max challenger floor_c); "
          f"binding: {family}")
    print("      noise_floor:")
    print(f"        k: {stats['k']}")
    print(f"        std: {stats['std']:.6g}")
    print(f"        range: {stats['range']:.6g}")
    print(f"        mean: {stats['mean']:.6g}")
    print(f"        values: [{', '.join(f'{v:.6g}' for v in d)}]")
    print(f'        source: "sweeps/{SIDECAR}"')
    print(f'        measured_after: "{MEASURED_AFTER}"')
    print(f'        method: "{METHOD}"')
    print(f'        estimand: "{ESTIMAND}"   # hand-added; klein noise-floor does not emit it')
    print("--- end block ---")
    print()
    print("  values above are the BINDING CHALLENGER's d_c series (candidate - anchor;")
    print("  POSITIVE = candidate worse). Full-precision per-candidate floors — including")
    print(f"  every non-binding one — live in sweeps/{OUT_NAME}.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="per-candidate paired floors (deterministic reducer, no fitting)"
    )
    parser.add_argument(
        "--sidecar", default=SIDECAR, help=f"metrology sidecar name (default: {SIDECAR})"
    )
    parser.add_argument(
        "--out", default=OUT_NAME, help=f"output table name (default: {OUT_NAME})"
    )
    args = parser.parse_args()

    path = SWEEPS_DIR / args.sidecar
    if not path.is_file():
        raise SystemExit(f"missing {path} — run sweeps/metrology_paired.py first")
    series, roles = load_series(path)
    check_roster(roles)
    rows, d_series = build_rows(series, roles)

    out_path = SWEEPS_DIR / args.out
    pd.DataFrame(rows).to_csv(out_path, sep="\t", index=False)
    print(f"wrote {out_path}  ({len(rows)} rows: 1 anchor-marginal + "
          f"{len(families.CHALLENGERS)} challengers + {len(families.CONTROLS)} controls)")

    print()
    print("=" * 78)
    print("PER-CANDIDATE PAIRED FLOORS  (estimand: paired-comparison)")
    print("=" * 78)
    print(f"{'family':<18} {'role':<11} {'k':>3} {'mean_d':>11} {'std_d':>11} "
          f"{'range_d':>11} {'floor_c':>11}")
    for r in rows:
        marker = "  <- RQ0 marginal exhibit" if r["role"] == "anchor" else ""
        print(f"{str(r['family']):<18} {str(r['role']):<11} {int(r['k']):>3} "
              f"{float(str(r['mean_d'])):>+11.6f} {float(str(r['std_d'])):>11.6f} "
              f"{float(str(r['range_d'])):>11.6f} {float(str(r['floor_c'])):>11.6f}"
              f"{marker}")
    print()
    print("d_c = brier_c - brier_anchor; POSITIVE = candidate WORSE than the anchor.")
    print("(The arena's mean_gain = brier_anchor - brier_f has the OPPOSITE sign.)")
    print("The anchor row's mean/std/range are its own MARGINAL Brier spread — read the")
    print("stat_kind column, never the column names alone.")

    family, raw_floor = binding_challenger(rows)
    scalar = ceil_3dp(raw_floor)
    control_floors = {
        str(r["family"]): float(str(r["floor_c"])) for r in rows if r["role"] == "control"
    }
    widest_control = max(control_floors.values()) if control_floors else float("nan")

    print()
    print("LEDGER SCALAR (controls EXCLUDED from the max, per noise_floor_protocol):")
    print(f"  binding challenger        {family}")
    print(f"  its floor_c (full)        {raw_floor!r}")
    print(f"  minimum_delta = ceil3dp   {scalar:.6g}")
    if control_floors:
        print(f"  widest CONTROL floor      {widest_control:.6g} "
              f"({max(control_floors, key=lambda k: control_floors[k])}) — EXCLUDED "
              "by registration")
        if widest_control > raw_floor:
            print("  NOTE: a control's floor exceeds every challenger's. That is exactly")
            print("        the case the exclusion rule was written for: the ruler stays")
            print("        set by the widest CHALLENGER. No re-registration.")

    print_paste_block(scalar, family, d_series[family])
    print()
    print("NEXT: paste, commit, re-record the CONSULT gate, then")
    print(f"  uv run --locked python -u sweeps/rq0_headroom.py --delta {scalar:.6g} \\")
    print("      --anchor-dev <E0001 val_brier>")
    print("  (publish the RQ0 headroom sidecar BEFORE any arena challenger number exists)")
    print()
    print("MEASUREMENT SWEEP: no winner promoted, no results.tsv row (sweep-rules.md carve-out)")


if __name__ == "__main__":
    main()
