"""Derive the two summary tables findings.md quotes, from the registered sidecars.

Nothing here measures anything new: it reads the sweep sidecars that
``klein sweep register`` already hashed, and the run manifests the notary already
wrote, and reduces them to the two tables the numbers law wants a home in.

* ``tables/pair_floors.tsv`` — one row per registered floor sweep: the pair, the
  replicate count, and the spread statistics, including the schema-3 bar
  ``max(2*std, range/2)`` each would imply.
* ``tables/verdict_arithmetic.tsv`` — one row per comparison the ladder made: the
  observed paired lift, and that lift expressed in units of the DECLARED bar, of the
  stricter 1000-replicate bar, and of the comparison's OWN pair-specific floor. The
  declared column is the one every registered verdict was adjudicated on; the other
  two are the pre-committed disclosure.

Run from the study directory::

    uv run --locked python -m lib.summarize_floors
"""

from __future__ import annotations

import csv
import statistics
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parent.parent
SWEEPS = STUDY_DIR / "sweeps"
TABLES = STUDY_DIR / "tables"

#: sweep name -> (what the pair was, what the sweep is for)
FLOOR_SWEEPS = (
    ("paired_bootstrap", "glm_ohe_balanced|hgbt_balanced", "the declared bar"),
    ("paired_bootstrap_b1000", "glm_ohe_balanced|hgbt_balanced", "precision check"),
    ("pair_anchor_splines", "glm_ohe_balanced|glm_splines_isotonic", "pair-specific"),
    ("pair_splines_hgbt", "glm_splines_isotonic|hgbt_balanced", "pair-specific"),
    ("pair_anchor_doctrine", "glm_ohe_balanced|glm_ohe_none_isotonic", "pair-specific"),
    ("split_lottery", "glm_ohe_balanced (marginal)", "reported, never a rule"),
    ("fit_noise", "glm_ohe_balanced (fit seeds)", "provenance, never a bar"),
)

#: the ladder's three comparisons: (label, run, observed lift, which pair sweep prices it)
COMPARISONS = (
    ("E0002_vs_anchor", "E0002", 0.035956, "pair_anchor_splines", "P3"),
    ("E0003_vs_splines", "E0003", 0.013956, "pair_splines_hgbt", "P5"),
    ("E0004_vs_anchor", "E0004", -0.001465, "pair_anchor_doctrine", "P6"),
    ("E0003_vs_incumbent", "E0003", 0.049911, "paired_bootstrap", "frontier keep"),
)

DECLARED_BAR = "paired_bootstrap"
STRICT_BAR = "paired_bootstrap_b1000"


def _values(name: str) -> list[float]:
    path = SWEEPS / f"{name}.sidecar.tsv"
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    return [
        float(row["primary_metric"])
        for row in rows
        if row.get("status") == "ok" and row.get("primary_metric") not in (None, "", "NA")
    ]


def _summary(values: list[float]) -> dict[str, float]:
    std = statistics.stdev(values)
    value_range = max(values) - min(values)
    return {
        "k": len(values),
        "mean": statistics.fmean(values),
        "std": std,
        "range": value_range,
        "bar": max(2.0 * std, value_range / 2.0),
    }


def main() -> int:
    TABLES.mkdir(parents=True, exist_ok=True)
    summaries = {name: _summary(_values(name)) for name, _, _ in FLOOR_SWEEPS}

    floor_rows = [("sweep", "pair", "role", "k", "mean", "std", "range", "bar")]
    for name, pair, role in FLOOR_SWEEPS:
        s = summaries[name]
        floor_rows.append(
            (
                name,
                pair,
                role,
                str(int(s["k"])),
                f"{s['mean']:.6f}",
                f"{s['std']:.6f}",
                f"{s['range']:.6f}",
                f"{s['bar']:.6f}",
            )
        )
    (TABLES / "pair_floors.tsv").write_text(
        "\n".join("\t".join(r) for r in floor_rows) + "\n", encoding="utf-8"
    )

    declared = summaries[DECLARED_BAR]["bar"]
    strict = summaries[STRICT_BAR]["bar"]
    verdict_rows = [
        (
            "comparison",
            "experiment",
            "prediction",
            "observed_lift",
            "in_declared_floors",
            "in_strict_floors",
            "own_pair_bar",
            "in_own_pair_floors",
            "abs_in_declared_floors",
            "abs_in_own_pair_floors",
        )
    ]
    for label, run, lift, own, prediction in COMPARISONS:
        own_bar = summaries[own]["bar"]
        verdict_rows.append(
            (
                label,
                run,
                prediction,
                f"{lift:.6f}",
                f"{lift / declared:.4f}",
                f"{lift / strict:.4f}",
                f"{own_bar:.6f}",
                f"{lift / own_bar:.4f}",
                f"{abs(lift) / declared:.4f}",
                f"{abs(lift) / own_bar:.4f}",
            )
        )
    (TABLES / "verdict_arithmetic.tsv").write_text(
        "\n".join("\t".join(r) for r in verdict_rows) + "\n", encoding="utf-8"
    )

    # --- the handful of ratios findings quotes, given a home ---------------
    aux: dict[tuple[str, str], float] = {}
    with (STUDY_DIR / "aux_metrics.tsv").open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            try:
                aux[(row["experiment"], row["metric"])] = float(row["value"])
            except (KeyError, ValueError):
                continue

    v1_anchor = 0.625462                              # scouting_ledger.md S1
    v1_hgbt, v1_sweep = 0.662897, 0.664322            # scouting_ledger.md S1
    spread = v1_hgbt - v1_anchor
    sweep_lift = v1_sweep - v1_hgbt
    derived = [
        ("quantity", "value", "from"),
        ("v1_ledger_spread", f"{v1_sweep - v1_anchor:.6f}",
         "scouting_ledger S1: row 6 minus row 1"),
        ("v1_anchor_to_hgbt_spread", f"{spread:.6f}", "scouting_ledger S1: row 3 minus row 1"),
        ("bar_over_v1_spread", f"{declared / (v1_sweep - v1_anchor):.4f}",
         "minimum_delta / v1_ledger_spread"),
        ("v1_sweep_lift", f"{sweep_lift:.6f}", "scouting_ledger S1: row 6 minus row 3"),
        ("v1_sweep_lift_in_declared_floors", f"{sweep_lift / declared:.4f}", "P8's arithmetic"),
        ("v1_sweep_lift_in_strict_floors", f"{sweep_lift / strict:.4f}", "P8's arithmetic"),
        ("brier_ratio_doctrine", f"{aux[('E0004', 'reference_brier')] / aux[('E0004', 'val_brier')]:.3f}",
         "E0004 reference_brier / val_brier"),
        ("brier_ratio_splines", f"{aux[('E0002', 'reference_brier')] / aux[('E0002', 'val_brier')]:.3f}",
         "E0002 reference_brier / val_brier"),
        ("brier_ratio_tree_vs_splines", f"{aux[('E0003', 'val_brier')] / aux[('E0003', 'reference_brier')]:.3f}",
         "E0003 val_brier / reference_brier"),
        ("anchor_residual_margin", f"{abs(aux[('E0002', 'anchor_gap')]) - abs(aux[('E0003', 'anchor_gap')]):.6f}",
         "|E0002 anchor_gap| - |E0003 anchor_gap|"),
        ("lift10_dev_minus_sealed",
         f"{aux[('E0003', 'val_lift_top10')] - aux[('E0005', 'val_lift_top10')]:.4f}",
         "E0003 val_lift_top10 - E0005 val_lift_top10"),
        ("paired_std_ratio_max_over_min",
         f"{summaries['paired_bootstrap_b1000']['std'] / summaries['pair_anchor_doctrine']['std']:.2f}",
         "widest pair std / narrowest pair std"),
    ]
    # Magnitudes: findings speaks of residuals and costs as sizes, and a scan that
    # looks for 0.011322 must find 0.011322 somewhere, not only its signed twin.
    for alias, key in (
        ("anchor_residual_glm_abs", ("E0001", "anchor_gap")),
        ("anchor_residual_splines_abs", ("E0002", "anchor_gap")),
        ("doctrine_auc_cost_abs", ("E0004", "delta_vs_reference")),
        ("doctrine_in_floors_abs", ("E0004", "delta_in_floors")),
        ("max_twin_gap_abs", ("E0002", "twin_free_gap")),
        ("sealed_shift_in_floors_abs", ("E0005", "sealed_shift_in_floors")),
    ):
        derived.append((alias, f"{abs(aux[key]):.6f}", f"|{key[0]} {key[1]}|"))
    derived.append(
        ("doctrine_in_own_floors_abs",
         f"{abs(aux[('E0004', 'delta_vs_reference')]) / summaries['pair_anchor_doctrine']['bar']:.4f}",
         "|E0004 delta_vs_reference| / pair_anchor_doctrine bar")
    )
    derived.append(
        ("portfolio_claim_rate", "0.063968", "data_card.md: 3,748 of 58,592 policies")
    )
    (TABLES / "derived_ratios.tsv").write_text(
        "\n".join("\t".join(r) for r in derived) + "\n", encoding="utf-8"
    )

    for path in (TABLES / "pair_floors.tsv", TABLES / "verdict_arithmetic.tsv",
                 TABLES / "derived_ratios.tsv"):
        print(f"--- {path.relative_to(STUDY_DIR)}")
        print(path.read_text(encoding="utf-8").rstrip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
