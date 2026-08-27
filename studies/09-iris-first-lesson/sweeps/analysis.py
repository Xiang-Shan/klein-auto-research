"""analysis.py — the FROZEN verdict computer (registered at the METHOD gate).

Reads ONLY committed artifacts (arena_anchor.sidecar.tsv, arena.sidecar.tsv, the two
aux sidecars, headroom.tsv, candidate_floors.tsv, results.tsv, study.yaml) and
computes every registered verdict quantity. NO FITTING happens here; editing this
file after the METHOD gate breaks the frozen-analysis clause in method_card.md.

Port of study 08's `sweeps/rematch_analysis.py`. What carried over UNCHANGED is
listed first because that is the part that must not drift; the registered 09 deltas
follow.

CARRIED OVER FROM 08 (unchanged machinery)
------------------------------------------
Bar-1, the SELECTION GUARD (not a population-inference test): per cell (f, n),
paired improvement d = brier_anchor - brier_f per fold-eval; repeat summary
D_bar_{f,n,j} = mean of that repeat's paired folds; t = mean_j(D_bar)/(sd_j(D_bar)/sqrt(J)),
sd ddof=1; zero sd -> t = +/-inf by the sign of the mean. ONE joint guard: Rademacher
sign flips at the REPEAT level (eps in {+-1}^10, FULL ENUMERATION = 1024), applied
jointly to every guard cell; adjusted score
p(f,n) = #{eps : max_cells t*(., eps) >= t_obs(f,n)} / 1024; the guard CLEARS iff
p <= 0.05. The grid is 1/1024, so 0.05 is attainable and the comparison is `<=`.

REGISTERED STATUS OF THIS QUANTITY: a randomization DIAGNOSTIC under the registered
symmetry assumption — that when a family neither helps nor hurts, its repeat-level
mean gaps D_bar_j are sign-symmetric about zero, JOINTLY with every other cell's.
That assumption is NOT derivable from the partition lottery alone (the anchor is
shared across cells; fits are deterministic given the partition), so the guard's
output is never described as "exact", as "FWER control", or as a p-value about
irises in general. "Detectable" is ALWAYS shorthand for "cleared this registered
guard in this lottery".

GUARD FAMILY IS FIXED: every (challenger, rung) cell allowed by the eligibility
matrix is a member. A cell with missing data (crashed folds leaving <2 repeats, or an
UNMEASURABLE rung) OCCUPIES its slot as a NEVER-FIRING PLACEHOLDER (t_obs = -inf,
excluded from the flip max only because -inf never attains a max). Nothing is
dropped, re-run or substituted after outcomes are visible.

REGISTERED 09 DELTAS
--------------------
1. GUARD FAMILY SIZE: the FIXED 7 x 6 = 42 cells (`families.MIN_RUNG` = 8 for every
   challenger, so nothing is ineligible). 08's family was 113 ragged cells.
   `claims_discipline.banned`: comparing p_guard values across studies. A 09
   p_guard is NOT an 08 p_guard.
2. BAR-2 IS THE 09 KEEP RULE and it uses the CANDIDATE-SPECIFIC floor:
       Bar-1 cleared  AND  mean_gain >= floor_c  AND  rung OPEN (m_n >= delta_n)
   where `floor_c` is that challenger's own paired floor read from
   `sweeps/candidate_floors.tsv`. 08 compared the mean gain to delta_n. delta_n is
   STILL computed and STILL used — for the rung's OPEN/CLOSED state, which is a
   property of the RUNG, not of the candidate. The two are never swapped.
   SIGN NOTE: `mean_gain = brier_anchor - brier_f` (POSITIVE = challenger better).
   `candidate_floors.tsv`'s `mean_d = brier_c - brier_anchor` has the OPPOSITE sign.
   `floor_c` is a dispersion (std/range), so it is sign-free and crosses safely.
3. CODA BRANCH IS RUNG-60 ONLY: Branch A iff >= 1 Bar-2 cell AT RUNG 60 (08 fired on
   a Bar-2 cell at ANY rung). Winner = largest guard t among the rung-60 Bar-2
   qualifiers; ties -> registry order. Branch B otherwise: the challenger seal STAYS
   SHUT and finalize runs --allow-exploratory per the pre-registered rule.
4. CODA MANIFEST TRAINS ON EVERYTHING: `train_positions: []` in BOTH branches (08's
   Branch W baked a quota-scanned subset). `positions_sha256` is therefore the
   sha256 of the EMPTY STRING in both branches — 08's convention, and the reason
   `CODA_SUBSET_SEED` does not exist in this study.
5. CAPTURE-RATIO LANE DROPPED: 08's `RECALIBRATED_FISHER` LDA-family adjustment
   capture is NOT registered for 09 and is not computed here.
6. RQ4 SATURATION EXHIBIT ADDED: `sweeps/rq4_saturation.tsv` from the aux sidecars —
   per (rung, metric in {val_auc, val_pr_auc, val_f1}) the SHARE OF FOLD-EVALS AT
   THE CEILING (== 1.0 within 1e-12), per family and pooled, alongside the
   per-family mean val_brier / val_logloss at that rung. This is RQ4's evidence
   that ranking gauges saturate where probability gauges still separate.
7. SENSITIVITY SEED 2026101500 (08: 2026095000). See the disclosure below.

CONTROL (RQ3): per measurable rung, a ONE-SIDED WORSENING sign-flip diagnostic on
`lda_sepal` (single-cell, 1024 flips), Bonferroni across the measurable rungs at
0.05 — the registered 0.05/6 when all six rungs are measurable. A miss triggers
INSTRUMENT-DOWNGRADE language for that rung. `lda_petal` is reported as a purely
DESCRIPTIVE sufficiency exhibit: no test, no verdict.

SENSITIVITY EXHIBIT ONLY (never a claim basis): fold-level max-t with the 40 units
per cell, 10,000 Monte-Carlo sign flips, seed 2026101500. Fold-level units are NOT
exchangeable within a repeat (folds of one partition share the anchor's fit and
partition the same rows), which is exactly why the REPEAT level carries the
registered guard and this stays an exhibit.

REGISTERED-SEED NOTE: the originally drafted sensitivity seed 2026099500
collided with the arena subset seed at (repeat 2, fold 0) — disclosed at build
and RE-REGISTERED pre-consult as 2026101500 (outside the subset range
2026099400..2026100303; program.md Decisions 2026-08-27). Registry disjoint.

THE CODA BAND CARRIES NO NOMINAL COVERAGE AFTER SELECTION: an in-band result is a
procedurally locked audit, not an 80% predictive statement, and never upgrades the
arena's evidence. klein's finalize label `confirmed` records protocol completion; it
is not a scientific-evidence upgrade.

Run (from the study directory, under the logger — everything printed is evidence)::

    uv run --locked python ../../scripts/run_with_log.py \
      --timeout-seconds 900 --log sweeps/analysis.log -- \
      uv run --locked python -u sweeps/analysis.py --anchor-dev <E0001 val_brier>
"""

from __future__ import annotations

import argparse
import itertools
import json
import statistics
import sys
from pathlib import Path

import numpy as np
import pandas as pd

STUDY_DIR = Path(__file__).resolve().parent.parent
if str(STUDY_DIR) not in sys.path:
    sys.path.insert(0, str(STUDY_DIR))
SWEEPS_DIR = STUDY_DIR / "sweeps"
if str(SWEEPS_DIR) not in sys.path:
    sys.path.insert(0, str(SWEEPS_DIR))

import arena  # noqa: E402  (frozen geometry code + registered constants, same dir)
import families  # noqa: E402

from kleinlib.workflow import load_contract  # noqa: E402

RUNGS = arena.RUNGS
REPEATS = arena.REPEATS
FOLDS = arena.FOLDS
ALPHA = 0.05
#: Registered sensitivity Monte-Carlo seed. See the disclosure in the docstring.
SENS_SEED = 2026101500
SENS_FLIPS = 10_000
NEVER = float("-inf")
#: A ranking gauge is "at the ceiling" when it is 1.0 to within this tolerance.
CEILING_TOL = 1e-12
CEILING_METRICS = ("val_auc", "val_pr_auc", "val_f1")
#: The registered one-sided WORSENING positive control (RQ3).
CONTROL_WORSENING = "lda_sepal"
#: The registered DESCRIPTIVE sufficiency exhibit (RQ3). No test, no verdict.
CONTROL_SUFFICIENCY = "lda_petal"
CODA_BRANCH_RUNG = 60

#: Every table THIS pipeline writes carries full-precision `repr` floats, and
#: pandas' default CSV float parser is NOT round-trip exact (it can be 1-2 ULP
#: off — measured: 0.011844522841099736 came back as 0.0118445228410997). Every
#: read of one of our own tables therefore pins the round-trip parser. The
#: PREPARED DATA read is deliberately LEFT on pandas' default, so the sweeps
#: parse the study CSV byte-for-byte the way `train.py` and kleinlib do.
FLOAT_PRECISION = "round_trip"

SEED_DOMAIN = 2**32
assert SENS_SEED < SEED_DOMAIN, "sensitivity seed must be < 2**32"
assert 2**REPEATS == 1024, "the registered guard enumerates 1024 repeat-level flips"


# ---------------------------------------------------------------------------
# committed-artifact readers
# ---------------------------------------------------------------------------

def load_sidecar(name: str) -> pd.DataFrame:
    df = pd.read_csv(SWEEPS_DIR / name, sep="\t", float_precision=FLOAT_PRECISION)
    df["params"] = df["params_json"].apply(json.loads)
    for key in ("family", "rung", "repeat", "fold"):
        df[key] = df["params"].apply(lambda p, k=key: p[k])
    return df


def cell_values(df: pd.DataFrame) -> dict[tuple[str, int, int, int], float]:
    out: dict[tuple[str, int, int, int], float] = {}
    for _, row in df.iterrows():
        if row["status"] != "ok" or pd.isna(row["primary_metric"]):
            continue
        out[(row["family"], int(row["rung"]), int(row["repeat"]), int(row["fold"]))] = float(
            row["primary_metric"]
        )
    return out


def load_aux() -> pd.DataFrame:
    """Both stages' aux sidecars, concatenated. Missing files are reported, not fatal."""
    frames = []
    for name in ("arena_anchor_aux.sidecar.tsv", "arena_aux.sidecar.tsv"):
        path = SWEEPS_DIR / name
        if path.is_file():
            frames.append(
                pd.read_csv(path, sep="\t", keep_default_na=False,
                            float_precision=FLOAT_PRECISION)
            )
        else:
            print(f"  NOTE: {name} absent — its families are missing from the RQ4 exhibit")
    if not frames:
        return pd.DataFrame(columns=list(arena.AUX_COLUMNS))
    return pd.concat(frames, ignore_index=True)


def load_candidate_floors() -> dict[str, float]:
    """`family -> floor_c` for the CHALLENGERS. Bar-2 is undefined without it."""
    path = SWEEPS_DIR / "candidate_floors.tsv"
    if not path.is_file():
        raise SystemExit(
            f"missing {path} — Bar-2 uses the CANDIDATE-SPECIFIC floor and cannot be "
            "computed from delta_n. Run sweeps/candidate_floors.py first."
        )
    df = pd.read_csv(path, sep="\t", float_precision=FLOAT_PRECISION)
    floors = {
        str(r["family"]): float(r["floor_c"])
        for _, r in df.iterrows()
        if str(r["role"]) == "challenger"
    }
    missing = [f for f in families.CHALLENGERS if f not in floors]
    if missing:
        raise SystemExit(f"candidate_floors.tsv has no floor_c for {missing}")
    return floors


def anchor_declared_dev() -> float:
    results = pd.read_csv(STUDY_DIR / "results.tsv", sep="\t",
                          float_precision=FLOAT_PRECISION)
    row = results[results["experiment"] == "E0001"]
    if row.empty:
        raise SystemExit(
            "results.tsv has no E0001 row — pass the LEDGER numerator explicitly "
            "with --anchor-dev (it is E0001's declared-split val_brier, NEVER the "
            "metrology mean)"
        )
    return float(row.iloc[0]["primary_metric"])


# ---------------------------------------------------------------------------
# the guard (pure functions — tests_sweeps.py exercises these directly)
# ---------------------------------------------------------------------------

def t_stat(dbar: dict[int, float]) -> float:
    vals = list(dbar.values())
    if len(vals) < 2:
        return NEVER
    sd = statistics.stdev(vals)
    m = statistics.fmean(vals)
    if sd == 0.0:
        return float("inf") if m > 0 else (NEVER if m < 0 else 0.0)
    return m / (sd / len(vals) ** 0.5)


def t_under_flip(dbar: dict[int, float], eps: tuple[int, ...]) -> float:
    vals = [dbar[j] * eps[j - 1] for j in sorted(dbar)]
    if len(vals) < 2:
        return NEVER
    sd = statistics.stdev(vals)
    m = statistics.fmean(vals)
    if sd == 0.0:
        return float("inf") if m > 0 else (NEVER if m < 0 else 0.0)
    return m / (sd / len(vals) ** 0.5)


def enumerate_flips(repeats: int = REPEATS) -> list[tuple[int, ...]]:
    """The FULL Rademacher enumeration at the repeat level: 2**repeats sign vectors."""
    return list(itertools.product((1, -1), repeat=repeats))


def guard_cells() -> list[tuple[str, int]]:
    """The FIXED guard family: every eligibility-matrix cell. 09 registers 7 x 6 = 42."""
    return [
        (fam, n)
        for fam in families.CHALLENGERS
        for n in RUNGS
        if families.eligible(fam, n)
    ]


def sign_flip_guard(
    live: dict[tuple[str, int], dict[int, float]],
    t_obs: dict[tuple[str, int], float],
    flips: list[tuple[int, ...]],
) -> dict[tuple[str, int], float]:
    """ONE joint guard over every live cell; placeholders score 1.0 and never fire."""
    if not live:
        print("  NOTE: no live guard cell — every cell is a placeholder and the "
              "adjusted score is 1.0 by construction")
        return dict.fromkeys(t_obs, 1.0)
    max_dist = np.array(
        [max(t_under_flip(dbar, eps) for dbar in live.values()) for eps in flips]
    )
    return {
        cell: (float((max_dist >= t).sum()) / len(flips) if t != NEVER else 1.0)
        for cell, t in t_obs.items()
    }


def fold_gaps(anchor_vals: dict, other_vals: dict, fam: str, rung: int) -> list[float]:
    """Fold-level g = brier_anchor - brier_fam (POSITIVE = fam better)."""
    gaps = []
    for j in range(1, REPEATS + 1):
        for k in range(FOLDS):
            a = anchor_vals.get((families.ANCHOR, rung, j, k))
            f = other_vals.get((fam, rung, j, k))
            if a is not None and f is not None:
                gaps.append(a - f)
    return gaps


def repeat_means(anchor_vals: dict, other_vals: dict, fam: str, rung: int) -> dict[int, float]:
    """D_bar_j: the mean paired gap within each repeat (the guard's unit)."""
    dbar: dict[int, float] = {}
    for j in range(1, REPEATS + 1):
        ds = []
        for k in range(FOLDS):
            a = anchor_vals.get((families.ANCHOR, rung, j, k))
            f = other_vals.get((fam, rung, j, k))
            if a is not None and f is not None:
                ds.append(a - f)
        if ds:
            dbar[j] = statistics.fmean(ds)
    return dbar


def band_p10_p90(gaps: list[float]) -> tuple[float, float]:
    arr = np.array(sorted(gaps))
    return float(np.quantile(arr, 0.10)), float(np.quantile(arr, 0.90))


# ---------------------------------------------------------------------------
# RQ4 saturation exhibit (pure function — tests exercise it on a synthetic aux)
# ---------------------------------------------------------------------------

def rq4_saturation(
    aux: pd.DataFrame,
    brier: dict[tuple[str, int, int, int], float],
    rungs: tuple[int, ...] = RUNGS,
    metrics: tuple[str, ...] = CEILING_METRICS,
) -> pd.DataFrame:
    """Ceiling shares per (rung, metric, family) and pooled, + mean Brier/log loss.

    A fold-eval is AT THE CEILING when the metric is 1.0 to within `CEILING_TOL`.
    `NA` rows (undefined on a degenerate eval fold) are EXCLUDED from the share's
    denominator and counted separately — a share is never diluted by a value that
    does not exist.
    """
    rows: list[dict[str, object]] = []
    if aux.empty:
        return pd.DataFrame(rows, columns=[
            "rung", "metric", "scope", "family", "n_evals", "n_na", "n_ceiling",
            "ceiling_share", "mean_val_brier", "mean_val_logloss",
        ])
    aux = aux.copy()
    aux["rung"] = aux["rung"].astype(int)
    logloss = aux[aux["metric"] == "val_logloss"]

    def _means(rung: int, fam: str | None) -> tuple[str, str]:
        b = [v for (f, n, _j, _k), v in brier.items()
             if n == rung and (fam is None or f == fam)]
        sel = logloss[logloss["rung"] == rung]
        if fam is not None:
            sel = sel[sel["family"] == fam]
        ll = [float(v) for v in sel["value"] if str(v) != arena.NA]
        return (
            f"{statistics.fmean(b):.6f}" if b else "",
            f"{statistics.fmean(ll):.6f}" if ll else "",
        )

    for rung in rungs:
        at_rung = aux[aux["rung"] == rung]
        if at_rung.empty:
            continue
        fams = sorted(at_rung["family"].unique())
        for metric in metrics:
            block = at_rung[at_rung["metric"] == metric]
            for scope, fam in [("family", f) for f in fams] + [("pooled", None)]:
                sel = block if fam is None else block[block["family"] == fam]
                raw = list(sel["value"])
                na = sum(1 for v in raw if str(v) == arena.NA)
                vals = [float(v) for v in raw if str(v) != arena.NA]
                n_ceiling = sum(1 for v in vals if abs(v - 1.0) <= CEILING_TOL)
                mean_b, mean_ll = _means(rung, fam)
                rows.append(
                    {
                        "rung": rung,
                        "metric": metric,
                        "scope": scope,
                        "family": fam if fam is not None else "ALL",
                        "n_evals": len(vals),
                        "n_na": na,
                        "n_ceiling": n_ceiling,
                        "ceiling_share": (
                            round(n_ceiling / len(vals), 6) if vals else ""
                        ),
                        "mean_val_brier": mean_b,
                        "mean_val_logloss": mean_ll,
                    }
                )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# the mechanical coda branch (pure function — tests exercise BOTH branches)
# ---------------------------------------------------------------------------

def build_coda_manifest(
    verdicts: pd.DataFrame,
    anchor_dev: float,
    delta: float,
    gaps_at_60: dict[str, list[float]],
) -> dict:
    """Branch A iff >= 1 Bar-2 cell at rung 60. Winner = largest guard t; ties -> registry.

    `train_positions` is `[]` in BOTH branches (registered): the coda trains on the
    whole declared train partition, so `positions_sha256` is the sha256 of the empty
    string either way.
    """
    order = {f: i for i, f in enumerate(families.CHALLENGERS)}
    qualifiers = verdicts[
        (verdicts["bar2_actionable"] == True)  # noqa: E712
        & (verdicts["rung"] == CODA_BRANCH_RUNG)
    ].copy()
    positions: list[int] = []
    manifest: dict = {
        "branch": "B",
        "families": {"coda_primary": families.ANCHOR, "coda_challenger": None},
        "train_positions": positions,
        "positions_sha256": families.positions_sha256(positions),
        "bands": {
            "primary": {
                "kind": "abs",
                "center": anchor_dev,
                "half_width": 2.0 * delta,
                "note": "|sealed - E0001 declared dev| <= 2 x minimum_delta (07/08 convention)",
            },
            "challenger": None,
        },
        "selection": {
            "rule": (
                f"Branch A iff >=1 Bar-2 cell at rung {CODA_BRANCH_RUNG}; winner = "
                "largest guard t among those qualifiers, ties -> registry order"
            ),
            "winner": None,
            "t": None,
            "n_qualifiers_at_rung_60": int(len(qualifiers)),
        },
    }
    if qualifiers.empty:
        return manifest

    qualifiers["t_num"] = qualifiers["t"].astype(float)
    qualifiers["reg"] = qualifiers["family"].map(order)
    qualifiers = qualifiers.sort_values(["t_num", "reg"], ascending=[False, True])
    winner = str(qualifiers.iloc[0]["family"])
    lo, hi = band_p10_p90(gaps_at_60[winner])
    manifest["branch"] = "A"
    manifest["families"]["coda_challenger"] = winner
    manifest["bands"]["challenger"] = {
        "kind": "interval",
        "lo": lo,
        "hi": hi,
        "convention": "g_sealed = sealed_primary - sealed_challenger",
        "note": f"arena [p10,p90] of fold-level g for {winner}@n{CODA_BRANCH_RUNG}",
    }
    manifest["selection"]["winner"] = winner
    manifest["selection"]["t"] = float(qualifiers.iloc[0]["t_num"])
    return manifest


# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="09 frozen verdict computer")
    parser.add_argument(
        "--anchor-dev", type=float, default=None,
        help="E0001's declared-split val_brier (the LEDGER numerator). Default: "
             "read from results.tsv. NEVER the metrology mean.",
    )
    parser.add_argument(
        "--delta", type=float, default=None,
        help="SMOKE ONLY: override tracks.primary.metric.minimum_delta",
    )
    args = parser.parse_args()

    print("=" * 78)
    print("09 ANALYSIS — frozen at the METHOD gate. No fitting happens in this file.")
    print("=" * 78)
    print(f"SEED DISCLOSURE: sensitivity seed {SENS_SEED} also equals the arena subset "
          f"seed at (repeat 2, fold 0) = {arena.SUBSET_SEED_BASE} + 200. Two unrelated")
    print("RNG consumers, one integer; determinism unaffected, disjointness imperfect.")

    headroom = pd.read_csv(SWEEPS_DIR / "headroom.tsv", sep="\t",
                           float_precision=FLOAT_PRECISION)
    hr = {int(r["rung"]): r for _, r in headroom.iterrows()}
    present = [n for n in RUNGS if n in hr]
    measurable = [n for n in present if hr[n]["state"] != "UNMEASURABLE"]
    open_rungs = {n for n in measurable if hr[n]["state"] == "OPEN"}
    delta_n = {n: float(hr[n]["delta_n"]) for n in measurable}

    anchor_df = load_sidecar("arena_anchor.sidecar.tsv")
    full_df = load_sidecar("arena.sidecar.tsv")
    anchor_vals = cell_values(anchor_df[anchor_df["family"] == families.ANCHOR])
    control_vals = cell_values(anchor_df[anchor_df["family"].isin(families.CONTROLS)])
    chall_vals = cell_values(full_df)
    all_vals = {**anchor_vals, **control_vals, **chall_vals}
    floor_c = load_candidate_floors()

    # ---- FIXED guard family: every eligibility-matrix cell, placeholders kept ----
    cells = guard_cells()
    expected = len(families.CHALLENGERS) * len(RUNGS)
    if len(cells) != expected:
        print(f"  NOTE: eligibility matrix admits {len(cells)} of {expected} cells "
              "(09 registers MIN_RUNG = 8 for every challenger, i.e. all of them)")
    live: dict[tuple[str, int], dict[int, float]] = {}
    placeholder: list[tuple[str, int, str]] = []
    for fam, n in cells:
        if n not in measurable:
            placeholder.append((fam, n, "rung UNMEASURABLE or absent from headroom.tsv"))
            continue
        dbar = repeat_means(anchor_vals, chall_vals, fam, n)
        if len(dbar) >= 2:
            live[(fam, n)] = dbar
        else:
            placeholder.append((fam, n, f"only {len(dbar)} repeats with paired data"))
    print(f"\nguard family: {len(cells)} cells fixed by the eligibility matrix; "
          f"{len(live)} live, {len(placeholder)} never-firing placeholders")
    for fam, n, why in placeholder:
        print(f"  placeholder: {fam}@n{n} — {why}")

    t_obs: dict[tuple[str, int], float] = dict.fromkeys(cells, NEVER)
    t_obs.update({cell: t_stat(dbar) for cell, dbar in live.items()})

    flips = enumerate_flips(REPEATS)
    print(f"joint sign-flip guard: FULL enumeration of {len(flips)} repeat-level flips "
          f"(grid 1/{len(flips)}; Bar-1 clears at adjusted score <= {ALPHA})")
    p_adj = sign_flip_guard(live, t_obs, flips)

    # ---- verdicts table ----
    era = getattr(families, "ERA", {})
    rows = []
    for (fam, n) in sorted(cells, key=lambda c: (c[1], c[0])):
        dbar = live.get((fam, n))
        mean_gain = statistics.fmean(dbar.values()) if dbar else float("nan")
        bar1 = p_adj[(fam, n)] <= ALPHA and t_obs[(fam, n)] != NEVER
        bar2 = bool(
            bar1
            and n in measurable
            and n in open_rungs
            and not np.isnan(mean_gain)
            and mean_gain >= floor_c[fam]
        )
        rows.append(
            {
                "family": fam, "rung": n, "era": era.get(fam, ""),
                "n_repeats": len(dbar) if dbar else 0,
                "mean_gain": round(mean_gain, 6) if dbar else "",
                "t": round(t_obs[(fam, n)], 4) if t_obs[(fam, n)] != NEVER else "-inf",
                "p_guard": round(p_adj[(fam, n)], 4),
                "bar1_guard_cleared": bar1,
                "delta_n": delta_n.get(n, ""),
                "rung_open": n in open_rungs,
                "floor_c": repr(floor_c[fam]),
                "bar2_actionable": bar2,
            }
        )
    verdicts = pd.DataFrame(rows)
    out = SWEEPS_DIR / "arena_verdicts.tsv"
    verdicts.to_csv(out, sep="\t", index=False)
    print(f"wrote {out}")
    print("  Bar-2 = Bar-1 AND mean_gain >= floor_c (CANDIDATE-specific, from "
          "candidate_floors.tsv) AND rung OPEN (m_n >= delta_n).")
    print("  delta_n governs the RUNG's openness; floor_c governs the CANDIDATE's bar. "
          "Never swapped.")

    bar1_cells = verdicts[verdicts["bar1_guard_cleared"] == True]  # noqa: E712
    bar2_cells = verdicts[verdicts["bar2_actionable"] == True]  # noqa: E712

    # ---- control diagnostic: one-sided WORSENING (RQ3) ----
    print(f"\n=== CONTROL ({CONTROL_WORSENING}, one-sided WORSENING, Bonferroni) ===")
    if CONTROL_WORSENING not in families.CONTROLS:
        raise SystemExit(
            f"{CONTROL_WORSENING!r} is not in families.CONTROLS {families.CONTROLS}"
        )
    bonf = ALPHA / len(measurable) if measurable else float("nan")
    print(f"  Bonferroni across {len(measurable)} measurable rung(s): alpha = {bonf:.6g} "
          f"(registered 0.05/6 when all six are measurable)")
    control_results = {}
    for n in measurable:
        wbar = {}
        for j in range(1, REPEATS + 1):
            ds = []
            for k in range(FOLDS):
                a = anchor_vals.get((families.ANCHOR, n, j, k))
                c = control_vals.get((CONTROL_WORSENING, n, j, k))
                if a is not None and c is not None:
                    ds.append(c - a)  # worsening: control - anchor > 0
            if ds:
                wbar[j] = statistics.fmean(ds)
        if len(wbar) < 2:
            print(f"  rung {n:>2}: fewer than 2 repeats with paired data — NOT TESTED")
            control_results[n] = False
            continue
        t_c = t_stat(wbar)
        dist = np.array([t_under_flip(wbar, eps) for eps in flips])
        p_c = float((dist >= t_c).sum()) / len(flips)
        sep = p_c <= bonf
        control_results[n] = sep
        print(f"  rung {n:>2}: mean worsening {statistics.fmean(wbar.values()):+.4f}  "
              f"t={t_c:.2f}  p={p_c:.4f}  {'SEPARATES' if sep else 'FAILS'}")
    if control_results and all(control_results.values()):
        print("  -> control separated at every measurable rung (RQ3 verdict basis)")
    else:
        failed = [n for n, ok in control_results.items() if not ok]
        print(f"  -> INSTRUMENT DOWNGRADE at rungs {failed}: degradations of the "
              "registered size were not reliably visible there; open/closed and "
              "guard results at those rungs carry that caveat")

    # ---- sufficiency exhibit (RQ3, DESCRIPTIVE ONLY — no test, no verdict) ----
    print(f"\n=== SUFFICIENCY EXHIBIT ({CONTROL_SUFFICIENCY}, DESCRIPTIVE ONLY) ===")
    for n in measurable:
        gaps = fold_gaps(anchor_vals, control_vals, CONTROL_SUFFICIENCY, n)
        if not gaps:
            print(f"  rung {n:>2}: no paired fold-evals")
            continue
        mean_gap = statistics.fmean(gaps)
        ratio = -mean_gap / delta_n[n] if delta_n.get(n) else float("nan")
        print(f"  rung {n:>2}: mean petal-only WORSENING {-mean_gap:+.4f} "
              f"= {ratio:.2f} x delta_n  (no guard, no bar, no verdict)")

    # ---- RQ4 saturation exhibit ----
    print("\n=== RQ4 SATURATION (ranking gauges vs probability gauges) ===")
    aux = load_aux()
    sat = rq4_saturation(aux, all_vals, tuple(present))
    sat_path = SWEEPS_DIR / "rq4_saturation.tsv"
    sat.to_csv(sat_path, sep="\t", index=False)
    print(f"wrote {sat_path}  ({len(sat)} rows)")
    pooled = sat[sat["scope"] == "pooled"]
    for _, r in pooled.iterrows():
        share = r["ceiling_share"]
        print(f"  rung {int(r['rung']):>2} {str(r['metric']):<11} pooled ceiling share "
              f"{share if share == '' else f'{float(share):.3f}'}  "
              f"(n={int(r['n_evals'])}, NA={int(r['n_na'])})  "
              f"mean brier {r['mean_val_brier']}  mean logloss {r['mean_val_logloss']}")

    # ---- sealed-coda branch + manifest ----
    print("\n=== SEALED-CODA BRANCH (mechanical, registered) ===")
    contract = load_contract(STUDY_DIR)
    delta = (
        args.delta
        if args.delta is not None
        else float(contract["tracks"]["primary"]["metric"]["minimum_delta"])
    )
    if args.delta is not None:
        print(f"  WARNING: --delta {delta:.6g} OVERRIDES the contract's minimum_delta. "
              "Wiring smoke only; must never produce a committed manifest.")
    if delta <= 0:
        raise SystemExit(
            "tracks.primary.metric.minimum_delta is still 0 — paste the measured "
            "scalar and re-record the consult gate before running the analysis"
        )
    anchor_dev = args.anchor_dev if args.anchor_dev is not None else anchor_declared_dev()
    src = "--anchor-dev" if args.anchor_dev is not None else "results.tsv E0001"
    print(f"  LEDGER numerator anchor_declared_dev = {anchor_dev!r} (source: {src})")
    gaps_at_60 = {
        fam: fold_gaps(anchor_vals, chall_vals, fam, CODA_BRANCH_RUNG)
        for fam in families.CHALLENGERS
    }
    manifest = build_coda_manifest(verdicts, anchor_dev, delta, gaps_at_60)
    manifest_path = SWEEPS_DIR / "coda_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if manifest["branch"] == "A":
        band = manifest["bands"]["challenger"]
        print(f"BRANCH A — {manifest['families']['coda_challenger']} cleared Bar-2 at "
              f"rung {CODA_BRANCH_RUNG} (t={manifest['selection']['t']:.4f}). TWO sealed "
              "looks.")
        print(f"  challenger band [p10,p90] = [{band['lo']:+.6f}, {band['hi']:+.6f}]  "
              f"({band['convention']})")
    else:
        print(f"BRANCH B — no Bar-2 cell at rung {CODA_BRANCH_RUNG}. ONE sealed look "
              "(coda_primary only); the challenger seal STAYS SHUT and finalize runs "
              "--allow-exploratory per the pre-registered rule.")
    print(f"  primary band: |sealed - {anchor_dev:.6f}| <= {2.0 * delta:.6g}")
    print(f"  train_positions [] in both branches -> positions_sha256 "
          f"{manifest['positions_sha256']}")
    print(f"wrote {manifest_path} (commit BEFORE the confirmation phase)")
    print("  NO NOMINAL COVERAGE AFTER SELECTION: an in-band result is a procedurally")
    print("  locked audit, never an 80% predictive statement, and never an evidence")
    print("  upgrade for the arena.")

    # ---- summary ----
    print("\n=== SUMMARY ===")
    print(f"Guard-cleared (Bar-1) cells: {len(bar1_cells)}"
          + (f" -> {[(r['family'], int(r['rung'])) for _, r in bar1_cells.iterrows()]}"
             if len(bar1_cells) else ""))
    print(f"Bar-2 actionable cells: {len(bar2_cells)}"
          + (f" -> {[(r['family'], int(r['rung'])) for _, r in bar2_cells.iterrows()]}"
             if len(bar2_cells) else ""))
    print(f"Open rungs: {sorted(open_rungs) if open_rungs else 'NONE'}")
    print("Bar-1 without Bar-2 reads 'detectable but not actionable'; 'detectable' means "
          "ONLY 'cleared the registered guard in this lottery'.")

    # ---- SENSITIVITY exhibit: fold-level max-t (Monte Carlo) — NEVER a claim basis ----
    rng = np.random.default_rng(SENS_SEED)
    fold_cells = {
        cell: np.array(fold_gaps(anchor_vals, chall_vals, cell[0], cell[1]))
        for cell in live
    }
    fold_cells = {c: ds for c, ds in fold_cells.items() if len(ds) >= 2}
    t_fold = {}
    for cell, ds in fold_cells.items():
        sd = ds.std(ddof=1)
        t_fold[cell] = float("inf") if sd == 0 else ds.mean() / (sd / len(ds) ** 0.5)
    unit_counts = sorted({len(ds) for ds in fold_cells.values()})
    print(f"\n=== SENSITIVITY EXHIBIT (fold-level, seed {SENS_SEED}, {SENS_FLIPS} MC "
          f"flips, {unit_counts} units/cell) ===")
    print("  EXHIBIT ONLY. Fold-level units are NOT exchangeable within a repeat; the")
    print("  registered guard lives at the REPEAT level. Never a claim basis.")
    if not fold_cells:
        print("  no live cell with >= 2 fold-evals — exhibit empty")
        return
    sens_max = np.empty(SENS_FLIPS)
    for i in range(SENS_FLIPS):
        m = -np.inf
        for ds in fold_cells.values():
            eps = rng.choice((1.0, -1.0), size=len(ds))
            flipped = ds * eps
            sd = flipped.std(ddof=1)
            t = np.inf if sd == 0 else flipped.mean() / (sd / len(flipped) ** 0.5)
            m = max(m, t)
        sens_max[i] = m
    sens_fired = [
        c for c, t in t_fold.items()
        if float((sens_max >= t).sum()) / SENS_FLIPS <= ALPHA
    ]
    print(f"  {len(sens_fired)} cell(s) fire at the fold level"
          + (f" -> {sens_fired}" if sens_fired else ""))


if __name__ == "__main__":
    main()
