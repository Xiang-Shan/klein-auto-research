"""rematch_arena.py — the study's PRIMARY EVIDENCE (measurement sweep, two stages).

Registered estimand (study.yaml `estimand:`): under the registered lottery — 10
seeded repeats of stratified group 4-fold over the 80 NON-SEALED rows, nested
quota subsampling to rung n — the mean paired dev-Brier improvement of family f
over the 1936 anchor, both deterministic seeded fits on IDENTICAL train subsets.
Conditional on these 100 flowers and this procedure; not a statement about new
irises.

Two stages, two sidecars, committed in ORDER (research_plan.md §4):

  --stage anchor   anchor_lda4 + lda_sepal only, all 6 rungs, 240 fold-evals each
                   -> sweeps/rematch_arena_anchor.sidecar.tsv
                   -> sweeps/headroom.tsv        (m_n, sd_n, delta_n, OPEN iff m_n >= delta_n)
                   -> sweeps/arena_partitions.tsv (per-cell geometry + disclosure)
                   COMMITTED BEFORE any challenger fit is summarized.
  --stage full     the 21 challenger families, eligibility-filtered (113 cells)
                   -> sweeps/rematch_arena.sidecar.tsv

Geometry (identical in both stages, deterministic):
  repeats j=1..10: StratifiedGroupKFold(n_splits=4, shuffle=True,
                   random_state=20260901100+j) over the 80 non-sealed rows.
  Every row is scored in development exactly 10 times.
  rungs n in {60, 45, 30, 20, 12, 8}: the fold's train pool (~60 rows) is
  subsampled by the NESTED QUOTA SCAN, seed 20260901000 + 100*j + k:
    - per class, a seeded permutation of that class's groups, with the size-2
      twins group PINNED LAST in its (virginica) permutation — a registered
      deviation from a pure shuffle: it makes the accepted sets provably nested
      across rungs (a mid-permutation skip-then-fill at a quota boundary breaks
      nesting) at the documented cost of under-sampling the twins at small rungs
      (they are two identical rows; a small rung spending 2 of 12 slots on a
      duplicate would be the stranger choice).
    - class quotas ceil(n/2)/floor(n/2), ceiling class = virginica iff (j+k)
      even (only matters at n=45); quota_c capped at availability, remainder
      shifted to the other class; whole groups only.
  The subset for (j,k,n) is computed ONCE and served IDENTICALLY to every
  family — exact pairing by construction. Dev = the fold, identical for all
  families and rungs. Rung 60 = the full pool (n_actual recorded, 58-62).

The guard family (research_plan §5) is FIXED by the eligibility matrix —
crashed or short cells occupy their slots as never-firing entries in the
analysis; nothing is silently dropped or re-run. Sealed rows (seed-20260907
test partition, procedurally fresh only) are FROZEN OUT of every draw — not
re-drawn, not scored, not seen. Max Jaccard overlap between any fold's dev set
and the DECLARED dev set is published in arena_partitions.tsv (disclosure only,
no exclusions — exclusion rules are their own selection bias; study 07 claim C6).

MEASUREMENT sweep: promotes no winner, writes no results.tsv row (sweep-rules.md
carve-out). Verdicts are computed ONLY by the frozen sweeps/rematch_analysis.py.

Run (from the study directory, AFTER the gates, E0001 and the ledger floor)::

    uv run --locked python ../../scripts/run_with_log.py \
      --timeout-seconds 1200 --log sweep_arena_anchor.log -- \
      uv run --locked python -u sweeps/rematch_arena.py --stage anchor

    uv run --locked python ../../scripts/run_with_log.py \
      --timeout-seconds 3600 --log sweep_arena_full.log -- \
      uv run --locked python -u sweeps/rematch_arena.py --stage full

Smoke the wiring without spending the sweep: `--repeats 1` (prints a WARNING and
must never feed study.yaml or the analysis).
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold

STUDY_DIR = Path(__file__).resolve().parent.parent
if str(STUDY_DIR) not in sys.path:
    sys.path.insert(0, str(STUDY_DIR))

import families  # noqa: E402  (needs STUDY_DIR on sys.path)

from kleinlib.data import three_way_split  # noqa: E402
from kleinlib.sweep import SweepRunner  # noqa: E402
from kleinlib.workflow import load_contract  # noqa: E402

RUNGS = (60, 45, 30, 20, 12, 8)
REPEATS = 10
FOLDS = 4
REPEAT_SEED_BASE = 20260901100          # + j
SUBSET_SEED_BASE = 20260901000          # + 100*j + k
TARGET = "is_virginica"
GROUP = "group_id"
DELTA_FLOOR = 0.005                      # registered floor-of-the-floor
CEILING_CLOSED_M = 0.06                  # closure-reason threshold (07 sealed 0.055 ceil)
UNMEASURABLE_FAIL_FRACTION = 0.10


def load_declared(study_dir: Path):
    """(non_sealed, declared_dev_row_ids, sealed_n) from the contract split."""
    contract = load_contract(study_dir)
    split = contract["data"]["split"]
    prepared = pd.read_csv(study_dir / contract["data"]["prepared_path"]).reset_index(drop=True)
    prepared["_row"] = prepared.index
    X = prepared.drop(columns=[TARGET])
    y = prepared[TARGET]
    x_tr, x_dev, x_te, *_ = three_way_split(
        X, y,
        task="classification",
        strategy="group",
        development_size=float(split["development_size"]),
        test_size=float(split["test_size"]),
        seed=int(split["seed"]),
        groups=prepared[split["group_column"]],
    )
    non_sealed = prepared.loc[sorted([*x_tr.index, *x_dev.index])].reset_index(drop=True)
    declared_dev_rows = set(prepared.loc[sorted(x_dev.index), "_row"])
    if set(non_sealed[GROUP]) & set(prepared.loc[sorted(x_te.index), GROUP]):
        raise SystemExit("a group straddles the sealed boundary — refusing to measure")
    return non_sealed, declared_dev_rows, len(x_te)


def class_group_permutation(pool: pd.DataFrame, seed: int) -> dict[int, list[tuple[str, int]]]:
    """Per class: seeded permutation of (group_id, size), twins pinned last."""
    rng = np.random.default_rng(seed)
    out: dict[int, list[tuple[str, int]]] = {}
    for cls in (0, 1):
        sub = pool[pool[TARGET] == cls]
        sizes = sub.groupby(GROUP).size()
        groups = list(sizes.index)
        order = list(rng.permutation(len(groups)))
        perm = [(groups[i], int(sizes.iloc[i])) for i in order]
        perm.sort(key=lambda gs: gs[1] > 1)  # stable: size-1 keep order, twins last
        out[cls] = perm
    return out


def quota_subset(
    pool: pd.DataFrame,
    perms: dict[int, list[tuple[str, int]]],
    n: int,
    ceil_class: int,
) -> pd.DataFrame:
    """Nested quota scan: whole groups, per-class quotas, twins-last permutation."""
    avail = {cls: int((pool[TARGET] == cls).sum()) for cls in (0, 1)}
    other = 1 - ceil_class
    quota = {ceil_class: math.ceil(n / 2), other: n // 2}
    # cap by availability, shift remainder to the other class (both directions)
    for a, b in ((ceil_class, other), (other, ceil_class)):
        overshoot = quota[a] - min(quota[a], avail[a])
        quota[a] -= overshoot
        quota[b] = min(quota[b] + overshoot, avail[b])
    keep_groups: list[str] = []
    for cls in (0, 1):
        taken = 0
        for gid, size in perms[cls]:
            if taken + size <= quota[cls]:
                keep_groups.append(gid)
                taken += size
    return pool[pool[GROUP].isin(keep_groups)]


def build_geometry(non_sealed: pd.DataFrame, declared_dev_rows: set, repeats: int):
    """All (j,k) partitions + per-rung subsets + the geometry/disclosure table."""
    partitions: dict[tuple[int, int], dict] = {}
    geometry_rows: list[dict] = []
    y = non_sealed[TARGET]
    for j in range(1, repeats + 1):
        skf = StratifiedGroupKFold(n_splits=FOLDS, shuffle=True, random_state=REPEAT_SEED_BASE + j)
        for k, (pool_idx, dev_idx) in enumerate(
            skf.split(non_sealed, y, groups=non_sealed[GROUP])
        ):
            pool = non_sealed.iloc[pool_idx]
            dev = non_sealed.iloc[dev_idx]
            perms = class_group_permutation(pool, SUBSET_SEED_BASE + 100 * j + k)
            ceil_class = 1 if (j + k) % 2 == 0 else 0
            subsets = {}
            for n in RUNGS:
                sub = quota_subset(pool, perms, n, ceil_class)
                subsets[n] = sub
                dev_rows = set(dev["_row"])
                inter = len(dev_rows & declared_dev_rows)
                union = len(dev_rows | declared_dev_rows)
                row_ids = sorted(int(r) for r in sub["_row"])
                geometry_rows.append(
                    {
                        "repeat": j, "fold": k, "rung": n,
                        "n_actual": len(sub),
                        "n_virginica": int((sub[TARGET] == 1).sum()),
                        "n_versicolor": int((sub[TARGET] == 0).sum()),
                        "dev_n": len(dev),
                        "jaccard_dev_vs_declared": round(inter / union, 4),
                        "rows_sha256": families.positions_sha256(row_ids),
                        "row_ids": ";".join(str(r) for r in row_ids),
                    }
                )
            partitions[(j, k)] = {"dev": dev, "subsets": subsets}
    return partitions, pd.DataFrame(geometry_rows)


def stage_families(stage: str) -> list[str]:
    if stage == "anchor":
        return [families.ANCHOR, families.CONTROL]
    return [f for f in families.CHALLENGERS]


def build_params(stage: str, repeats: int) -> list[dict[str, object]]:
    params: list[dict[str, object]] = []
    for family in stage_families(stage):
        for n in RUNGS:
            if stage == "full" and not families.eligible(family, n):
                continue
            for j in range(1, repeats + 1):
                for k in range(FOLDS):
                    params.append({"family": family, "rung": n, "repeat": j, "fold": k})
    return params


def make_trial_fn(partitions):
    def trial_fn(params: dict) -> dict:
        part = partitions[(int(params["repeat"]), int(params["fold"]))]
        train = part["subsets"][int(params["rung"])]
        dev = part["dev"]
        brier = families.dev_brier(str(params["family"]), train, dev, target=TARGET)
        return {"primary_metric": brier, "status": "ok"}

    return trial_fn


def ceil_3dp(value: float) -> float:
    return math.ceil(value * 1000.0 - 1e-12) / 1000.0


def write_headroom(trials, geometry: pd.DataFrame, out_path: Path) -> None:
    """Stage-A ONLY: per-rung anchor floor + OPEN/CLOSED, before any challenger."""
    anchor_vals: dict[int, list[float]] = {n: [] for n in RUNGS}
    anchor_fail: dict[int, int] = {n: 0 for n in RUNGS}
    for t in trials:
        if str(t.params["family"]) != families.ANCHOR:
            continue
        n = int(t.params["rung"])
        if t.status == "ok" and t.primary_metric is not None:
            anchor_vals[n].append(float(t.primary_metric))
        else:
            anchor_fail[n] += 1
    rows = []
    for n in RUNGS:
        vals, fails = anchor_vals[n], anchor_fail[n]
        total = len(vals) + fails
        if total == 0 or fails / total > UNMEASURABLE_FAIL_FRACTION:
            rows.append({"rung": n, "n_folds_ok": len(vals), "anchor_failures": fails,
                         "m_n": "", "sd_n": "", "delta_n": "", "state": "UNMEASURABLE",
                         "reason": f">{UNMEASURABLE_FAIL_FRACTION:.0%} anchor fit failures"})
            continue
        m = statistics.fmean(vals)
        sd = statistics.stdev(vals)
        delta = max(ceil_3dp(2.0 * sd), DELTA_FLOOR)
        is_open = m >= delta
        reason = ("open" if is_open
                  else ("ceiling-closed" if m < CEILING_CLOSED_M else "fog-closed"))
        rows.append({"rung": n, "n_folds_ok": len(vals), "anchor_failures": fails,
                     "m_n": f"{m:.6f}", "sd_n": f"{sd:.6f}", "delta_n": f"{delta:.3f}",
                     "state": "OPEN" if is_open else "CLOSED", "reason": reason})
    pd.DataFrame(rows).to_csv(out_path, sep="\t", index=False)
    print(f"wrote {out_path}")
    for r in rows:
        print(f"  rung {r['rung']:>2}: {r['state']:<12} {r['reason']:<15} "
              f"m={r['m_n']} sd={r['sd_n']} delta={r['delta_n']}")


def require_gates(study_dir: Path) -> None:
    state_path = study_dir / "study_state.json"
    gates = json.loads(state_path.read_text(encoding="utf-8")).get("gates", {})
    pending = [g for g in ("consult", "data", "method")
               if gates.get(g, {}).get("status") not in {"recorded", "overridden"}]
    if pending:
        raise SystemExit(
            "refusing to run: the arena is MEASUREMENT and runs only after the "
            f"gates. Pending: {', '.join(pending)}."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="rematch arena (measurement sweep)")
    parser.add_argument("--stage", choices=["anchor", "full"], required=True)
    parser.add_argument("--repeats", type=int, default=REPEATS)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    require_gates(STUDY_DIR)
    if args.stage == "full":
        anchor_sidecar = STUDY_DIR / "sweeps" / "rematch_arena_anchor.sidecar.tsv"
        if not anchor_sidecar.is_file():
            raise SystemExit("stage full refuses to run before the Stage-A sidecar is committed")

    non_sealed, declared_dev_rows, sealed_n = load_declared(STUDY_DIR)
    print(f"non-sealed rows: {len(non_sealed)}  sealed (frozen out): {sealed_n}")
    partitions, geometry = build_geometry(non_sealed, declared_dev_rows, args.repeats)

    name = "rematch_arena_anchor" if args.stage == "anchor" else "rematch_arena"
    summary = SweepRunner(
        name,
        study_dir=STUDY_DIR,
        trial_fn=make_trial_fn(partitions),
        params_list=build_params(args.stage, args.repeats),
        metric_goal="lower",
        resume=args.resume,
        overwrite=args.overwrite,
    ).run()

    crashed = [t for t in summary.trials if t.status != "ok"]
    if crashed:
        print(f"NOTE: {len(crashed)} trial(s) crashed — recorded honestly in the sidecar")

    if args.stage == "anchor":
        geometry.to_csv(STUDY_DIR / "sweeps" / "arena_partitions.tsv", sep="\t", index=False)
        print(f"wrote sweeps/arena_partitions.tsv  "
              f"(max jaccard dev-vs-declared: {geometry['jaccard_dev_vs_declared'].max():.4f})")
        write_headroom(summary.trials, geometry, STUDY_DIR / "sweeps" / "headroom.tsv")
        print("STAGE A COMPLETE — commit the three sweeps/ files BEFORE any challenger fit.")
    else:
        print("STAGE B COMPLETE — verdicts come ONLY from sweeps/rematch_analysis.py.")

    if args.repeats != REPEATS:
        print(f"WARNING: ran {args.repeats} repeats, not the registered {REPEATS}; "
              "wiring smoke only — must never feed the analysis.")
    print("MEASUREMENT SWEEP: no winner promoted, no results.tsv row (sweep-rules.md carve-out)")


if __name__ == "__main__":
    main()
