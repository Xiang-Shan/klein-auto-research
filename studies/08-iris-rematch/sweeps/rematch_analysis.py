"""rematch_analysis.py — the FROZEN verdict computer (registered at METHOD gate).

Reads ONLY committed artifacts (rematch_arena_anchor.sidecar.tsv,
rematch_arena.sidecar.tsv, headroom.tsv, results.tsv, study.yaml) and computes
every registered verdict quantity. No fitting happens here; editing this file
after the METHOD gate breaks the frozen-analysis clause in method_card.md.

REGISTERED DECISION RULES (research_plan.md §5) — post-red-team wording:

Bar-1, the SELECTION GUARD (not a population-inference test): per cell (f, n),
paired improvement d = brier_anchor − brier_f per fold-eval; repeat summary
D̄_{f,n,j} = mean of that repeat's paired folds; t = mean_j(D̄)/(sd_j(D̄)/√J),
sd ddof=1; zero sd → t = ±inf by the sign of the mean. ONE joint guard:
Rademacher sign flips at the REPEAT level (ε ∈ {±1}^10, full enumeration 1024),
applied jointly to every guard cell; adjusted score
p(f,n) = #{ε : max_cells t*(·, ε) ≥ t_obs(f,n)} / 1024; the guard CLEARS iff
p ≤ 0.05. REGISTERED STATUS OF THIS QUANTITY: it is a randomization diagnostic
under the registered symmetry assumption — that when a family neither helps nor
hurts, its repeat-level mean gaps D̄_j are sign-symmetric about zero, jointly
with every other cell's. That assumption is NOT derivable from the partition
lottery alone (the anchor is shared across cells; fits are deterministic given
the partition), so the guard's output is never described as "exact", as "FWER
control", or as a p-value about irises in general. "Detectable" is ALWAYS
shorthand for "cleared this registered guard in this lottery" — a
selection-guarded description of these 80 rows under this procedure.

GUARD FAMILY IS FIXED: every (challenger, rung) cell allowed by the eligibility
matrix (families.MIN_RUNG) is a member — 113 cells. A cell with missing data
(crashed folds leaving <2 repeats, or an UNMEASURABLE rung) OCCUPIES its slot
as a never-firing placeholder (t_obs = −inf, excluded from the flip max only
because −inf never attains a max). Nothing is dropped, re-run, or substituted
after outcomes are visible.

Bar-2 (actionable): guard cleared AND mean_j(D̄) ≥ δ_n AND rung OPEN
(m_n ≥ δ_n, from headroom.tsv — δ_n includes the fixed 0.005 materiality floor,
which is a registered constant, not an estimated noise quantity).

Control (RQ5): per measurable rung, one-sided WORSENING sign-flip diagnostic on
lda_sepal (single-cell, 1024 flips), Bonferroni across measurable rungs at 0.05.

LDA-family adjustment capture (RQ4, NON-CAUSAL, observed ratio only): at any
rung with ≥1 guard-cleared cell, capture = max mean gain among the eligible
members of {lda_platt, lda_isotonic, lda_shrinkage} at that rung ÷ the best
guard-cleared challenger's mean gain (denominator must be > 0). Two calibration
maps + one covariance-shrinkage estimator; the ratio DESCRIBES how much of the
best gain an LDA-family adjustment also achieves — it does not decompose
mechanisms causally. Threshold 0.5 fires the registered downgrade wording.

Sealed-coda branch + manifest: Branch W iff ≥1 Bar-2 cell — (f*, n*) = largest
t among Bar-2 cells, ties → larger n, then registry order. Else Branch G
(anchor_lda4 / tabpfn at n=60). This script writes sweeps/coda_manifest.json:
families, baked train positions (Branch W: the registered quota scan of the
DECLARED train partition, seed 20260901999, ceiling class virginica, twins-last
rule — identical code path to the arena's scan; Branch G: all train rows),
position hashes, and the numeric bands. GAP SIGN CONVENTION (registered):
g_sealed = sealed_primary − sealed_challenger (positive = challenger better on
Brier), checked against the arena's [p10, p90] of fold-level g = anchor − f.
The manifest is DATA produced by this frozen rule — the confirmation phase
runs registry entries coda_primary / coda_challenger that read it; no code is
edited after selection. The coda band carries NO nominal coverage after
selection: an in-band result is a procedurally locked audit, not an 80%
predictive statement, and never upgrades the arena's evidence. klein's
finalize label `confirmed` records protocol completion (one successful sealed
run per track); it is not a scientific-evidence upgrade.

Sensitivity exhibit only (never a claim basis): fold-level max-t with 40 units,
10,000 Monte-Carlo sign flips, seed 20260901550.

Run:  uv run --locked python -u sweeps/rematch_analysis.py
"""

from __future__ import annotations

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

import families  # noqa: E402
import rematch_arena as arena  # noqa: E402  (frozen geometry code, same dir)

from kleinlib.data import three_way_split  # noqa: E402
from kleinlib.workflow import load_contract  # noqa: E402

RUNGS = (60, 45, 30, 20, 12, 8)
REPEATS = 10
ALPHA = 0.05
CODA_SUBSET_SEED = 20260901999
SENS_SEED = 20260901550
SENS_FLIPS = 10_000
NEVER = float("-inf")


def load_sidecar(name: str) -> pd.DataFrame:
    df = pd.read_csv(SWEEPS_DIR / name, sep="\t")
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


def declared_train_partition() -> pd.DataFrame:
    """The declared split's train rows, in train.py's exact positional order."""
    contract = load_contract(STUDY_DIR)
    split = contract["data"]["split"]
    prepared = pd.read_csv(STUDY_DIR / contract["data"]["prepared_path"]).reset_index(drop=True)
    prepared["_row"] = prepared.index
    X = prepared.drop(columns=[arena.TARGET])
    y = prepared[arena.TARGET]
    x_tr, *_ = three_way_split(
        X, y,
        task="classification",
        strategy="group",
        development_size=float(split["development_size"]),
        test_size=float(split["test_size"]),
        seed=int(split["seed"]),
        groups=prepared[split["group_column"]],
    )
    return prepared.loc[x_tr.index]  # order as delivered to train.py


def coda_positions(n_star: int) -> list[int]:
    """Quota-scan the declared train partition to n_star (registered rule)."""
    train = declared_train_partition().reset_index(drop=True)
    perms = arena.class_group_permutation(train, CODA_SUBSET_SEED)
    sub = arena.quota_subset(train, perms, n_star, ceil_class=1)  # virginica ceiling, registered
    return sorted(int(i) for i in sub.index)


def anchor_declared_dev() -> float:
    results = pd.read_csv(STUDY_DIR / "results.tsv", sep="\t")
    row = results[(results["experiment"] == "E0001")]
    return float(row.iloc[0]["primary_metric"])


def fold_gaps(anchor_vals: dict, other_vals: dict, fam: str, rung: int) -> list[float]:
    gaps = []
    for j in range(1, REPEATS + 1):
        for k in range(4):
            a = anchor_vals.get((families.ANCHOR, rung, j, k))
            f = other_vals.get((fam, rung, j, k))
            if a is not None and f is not None:
                gaps.append(a - f)
    return gaps


def band_p10_p90(gaps: list[float]) -> tuple[float, float]:
    arr = np.array(sorted(gaps))
    return float(np.quantile(arr, 0.10)), float(np.quantile(arr, 0.90))


def main() -> None:
    headroom = pd.read_csv(SWEEPS_DIR / "headroom.tsv", sep="\t")
    hr = {int(r["rung"]): r for _, r in headroom.iterrows()}
    measurable = [n for n in RUNGS if hr[n]["state"] != "UNMEASURABLE"]
    open_rungs = {n for n in measurable if hr[n]["state"] == "OPEN"}
    delta_n = {n: float(hr[n]["delta_n"]) for n in measurable}

    anchor_df = load_sidecar("rematch_arena_anchor.sidecar.tsv")
    full_df = load_sidecar("rematch_arena.sidecar.tsv")
    anchor_vals = cell_values(anchor_df[anchor_df["family"] == families.ANCHOR])
    control_vals = cell_values(anchor_df[anchor_df["family"] == families.CONTROL])
    chall_vals = cell_values(full_df)

    # ---- FIXED guard family: every eligibility-matrix cell, placeholders kept ----
    guard_cells = [
        (fam, n)
        for fam in families.CHALLENGERS
        for n in RUNGS
        if families.eligible(fam, n)
    ]
    live: dict[tuple[str, int], dict[int, float]] = {}
    placeholder: list[tuple[str, int, str]] = []
    for fam, n in guard_cells:
        if n not in measurable:
            placeholder.append((fam, n, "rung UNMEASURABLE"))
            continue
        dbar = {}
        for j in range(1, REPEATS + 1):
            ds = []
            for k in range(4):
                a = anchor_vals.get((families.ANCHOR, n, j, k))
                f = chall_vals.get((fam, n, j, k))
                if a is not None and f is not None:
                    ds.append(a - f)
            if ds:
                dbar[j] = statistics.fmean(ds)
        if len(dbar) >= 2:
            live[(fam, n)] = dbar
        else:
            placeholder.append((fam, n, f"only {len(dbar)} repeats with paired data"))
    print(f"guard family: {len(guard_cells)} cells fixed by the eligibility matrix; "
          f"{len(live)} live, {len(placeholder)} never-firing placeholders")
    for fam, n, why in placeholder:
        print(f"  placeholder: {fam}@n{n} — {why}")

    t_obs: dict[tuple[str, int], float] = {c: NEVER for c in guard_cells}
    t_obs.update({cell: t_stat(dbar) for cell, dbar in live.items()})

    # ---- joint sign-flip guard, full enumeration ----
    flips = list(itertools.product((1, -1), repeat=REPEATS))
    max_dist = np.array([
        max(t_under_flip(dbar, eps) for dbar in live.values()) for eps in flips
    ])
    p_adj = {cell: (float((max_dist >= t).sum()) / len(flips) if t != NEVER else 1.0)
             for cell, t in t_obs.items()}

    # ---- verdicts table ----
    rows = []
    for (fam, n) in sorted(guard_cells, key=lambda c: (c[1], c[0])):
        dbar = live.get((fam, n))
        mean_gain = statistics.fmean(dbar.values()) if dbar else float("nan")
        bar1 = p_adj[(fam, n)] <= ALPHA and t_obs[(fam, n)] != NEVER
        bar2 = bool(bar1 and n in measurable and n in open_rungs
                    and not np.isnan(mean_gain) and mean_gain >= delta_n[n])
        rows.append(
            {
                "family": fam, "rung": n, "era": families.ERA[fam],
                "n_repeats": len(dbar) if dbar else 0,
                "mean_gain": round(mean_gain, 6) if dbar else "",
                "t": round(t_obs[(fam, n)], 4) if t_obs[(fam, n)] != NEVER else "-inf",
                "p_guard": round(p_adj[(fam, n)], 4),
                "bar1_guard_cleared": bar1,
                "delta_n": delta_n.get(n, ""),
                "rung_open": n in open_rungs,
                "bar2_actionable": bar2,
            }
        )
    verdicts = pd.DataFrame(rows)
    out = SWEEPS_DIR / "rematch_verdicts.tsv"
    verdicts.to_csv(out, sep="\t", index=False)
    print(f"wrote {out}")

    bar1_cells = verdicts[verdicts["bar1_guard_cleared"] == True]  # noqa: E712
    bar2_cells = verdicts[verdicts["bar2_actionable"] == True]  # noqa: E712

    # ---- control diagnostic (RQ5) ----
    print("\n=== CONTROL (lda_sepal, one-sided WORSENING, Bonferroni) ===")
    bonf = ALPHA / len(measurable)
    control_results = {}
    for n in measurable:
        wbar = {}
        for j in range(1, REPEATS + 1):
            ds = []
            for k in range(4):
                a = anchor_vals.get((families.ANCHOR, n, j, k))
                c = control_vals.get((families.CONTROL, n, j, k))
                if a is not None and c is not None:
                    ds.append(c - a)  # worsening: control − anchor > 0
            if ds:
                wbar[j] = statistics.fmean(ds)
        t_c = t_stat(wbar)
        dist = np.array([t_under_flip(wbar, eps) for eps in flips])
        p_c = float((dist >= t_c).sum()) / len(flips)
        sep = p_c <= bonf
        control_results[n] = sep
        print(f"  rung {n:>2}: mean worsening {statistics.fmean(wbar.values()):+.4f}  "
              f"t={t_c:.2f}  p={p_c:.4f}  {'SEPARATES' if sep else 'FAILS'}")
    if all(control_results.values()):
        print("  -> control separated at every measurable rung (RQ5 verdict basis)")
    else:
        failed = [n for n, ok in control_results.items() if not ok]
        print(f"  -> INSTRUMENT DOWNGRADE at rungs {failed}: degradations of the "
              "registered size were not reliably visible there; open/closed and "
              "guard results at those rungs carry that caveat")

    # ---- LDA-family adjustment capture (RQ4, non-causal observed ratio) ----
    print("\n=== LDA-FAMILY ADJUSTMENT CAPTURE (observed ratio, non-causal) ===")
    if len(bar1_cells) == 0:
        print("  no guard-cleared cell — capture ratio not defined this study")
    for n in sorted({int(r) for r in bar1_cells["rung"]}):
        at_rung = bar1_cells[bar1_cells["rung"] == n]
        best = at_rung.loc[at_rung["mean_gain"].astype(float).idxmax()]
        best_gain = float(best["mean_gain"])
        adj = verdicts[
            (verdicts["rung"] == n)
            & (verdicts["family"].isin(families.RECALIBRATED_FISHER))
            & (verdicts["mean_gain"] != "")
        ]
        adj_gain = float(adj["mean_gain"].astype(float).max()) if len(adj) else float("nan")
        if best_gain <= 0 or np.isnan(adj_gain):
            print(f"  rung {n:>2}: ratio undefined (best gain {best_gain:+.4f})")
            continue
        frac = adj_gain / best_gain
        fires = frac >= 0.5
        print(f"  rung {n:>2}: best {best['family']} gain {best_gain:+.4f}; "
              f"LDA-family adjustment best {adj_gain:+.4f}; observed capture {frac:.2f}"
              f" -> {'downgrade wording fires (adjustment captures >= half)' if fires else 'below 0.5'}")

    # ---- sealed-coda branch + manifest ----
    print("\n=== SEALED-CODA BRANCH (registered rule) ===")
    contract = load_contract(STUDY_DIR)
    min_delta = float(contract["tracks"]["primary"]["metric"]["minimum_delta"])
    if len(bar2_cells):
        b2 = bar2_cells.copy()
        reg_order = {f: i for i, f in enumerate(families.CHALLENGERS)}
        b2["t_num"] = b2["t"].astype(float)
        b2["reg"] = b2["family"].map(reg_order)
        b2 = b2.sort_values(["t_num", "rung", "reg"], ascending=[False, False, True])
        f_star, n_star = str(b2.iloc[0]["family"]), int(b2.iloc[0]["rung"])
        positions = coda_positions(n_star)
        m_star, d_star = float(hr[n_star]["m_n"]), delta_n[n_star]
        gaps = fold_gaps(anchor_vals, chall_vals, f_star, n_star)
        lo, hi = band_p10_p90(gaps)
        manifest = {
            "branch": "W",
            "selection": {"f_star": f_star, "n_star": n_star,
                          "t": float(b2.iloc[0]["t_num"]),
                          "rule": "largest t among Bar-2 cells; ties larger n then registry order"},
            "primary": {"family": families.ANCHOR, "train_positions": positions,
                        "positions_sha256": families.positions_sha256(positions),
                        "band": {"kind": "abs", "center": m_star, "half_width": 2 * d_star,
                                 "note": f"|sealed − m_{n_star}| ≤ 2δ_{n_star}"}},
            "challenger": {"family": f_star, "train_positions": positions,
                           "positions_sha256": families.positions_sha256(positions),
                           "band": {"kind": "interval", "lo": lo, "hi": hi,
                                    "convention": "g_sealed = sealed_primary − sealed_challenger",
                                    "note": f"arena [p10,p90] of fold-level g for {f_star}@n{n_star}"}},
        }
        print(f"BRANCH W — winner exists: f*={f_star} at n*={n_star}; "
              f"coda trains on {len(positions)} baked positions")
    else:
        dev = anchor_declared_dev()
        gaps60 = fold_gaps(anchor_vals, chall_vals, "tabpfn", 60)
        lo, hi = band_p10_p90(gaps60)
        manifest = {
            "branch": "G",
            "selection": {"f_star": None, "n_star": None,
                          "rule": "no Bar-2 cell — registered Branch G"},
            "primary": {"family": families.ANCHOR, "train_positions": [],
                        "positions_sha256": families.positions_sha256([]),
                        "band": {"kind": "abs", "center": dev, "half_width": 2 * min_delta,
                                 "note": "|sealed − declared dev| ≤ 2×minimum_delta (07 convention)"}},
            "challenger": {"family": "tabpfn", "train_positions": [],
                           "positions_sha256": families.positions_sha256([]),
                           "band": {"kind": "interval", "lo": lo, "hi": hi,
                                    "convention": "g_sealed = sealed_primary − sealed_challenger",
                                    "note": "arena [p10,p90] of fold-level g for tabpfn@n60"}},
        }
        print("BRANCH G — no Bar-2 cell: seal anchor_lda4 (primary) and tabpfn "
              f"(challenger) at n=60; T2 gap band [{lo:+.4f}, {hi:+.4f}]")
    manifest_path = SWEEPS_DIR / "coda_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"wrote {manifest_path} (commit BEFORE the confirmation phase)")

    # ---- summary ----
    print("\n=== SUMMARY ===")
    print(f"Guard-cleared (Bar-1) cells: {len(bar1_cells)}"
          + (f" -> {[(r['family'], int(r['rung'])) for _, r in bar1_cells.iterrows()]}" if len(bar1_cells) else ""))
    print(f"Bar-2 actionable cells: {len(bar2_cells)}")
    print(f"Open rungs: {sorted(open_rungs) if open_rungs else 'NONE'}")

    # ---- sensitivity exhibit: fold-level max-t (Monte Carlo) ----
    rng = np.random.default_rng(SENS_SEED)
    fold_cells = {cell: np.array(fold_gaps(anchor_vals, chall_vals, cell[0], cell[1]))
                  for cell in live}
    t_fold = {}
    for cell, ds in fold_cells.items():
        sd = ds.std(ddof=1)
        t_fold[cell] = float("inf") if sd == 0 else ds.mean() / (sd / len(ds) ** 0.5)
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
    sens_fired = [c for c, t in t_fold.items()
                  if float((sens_max >= t).sum()) / SENS_FLIPS <= ALPHA]
    print(f"\nSensitivity (fold-level, exhibit only): {len(sens_fired)} cells"
          + (f" -> {sens_fired}" if sens_fired else ""))


if __name__ == "__main__":
    main()
