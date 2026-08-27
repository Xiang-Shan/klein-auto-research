"""arena.py — the study's PRIMARY EVIDENCE (measurement sweep, two stages).

Port of study 08's frozen `sweeps/rematch_arena.py` onto study 09's registered
constants and 10-family roster. The GEOMETRY is unchanged, deliberately: the same
nested whole-group quota scan, the same twins-last pin, the same partitions
disclosure. What changed is registered below.

Registered estimand (study.yaml `estimand:`): under the registered lottery — 10
seeded repeats of stratified group 4-fold over the ~80 NON-SEALED rows, nested
whole-group quota subsampling to NOMINAL rung n (realized `n_actual <= nominal`;
the distribution is published) — the mean paired dev-Brier improvement of family f
over the 1936 anchor, both deterministic seeded fits on IDENTICAL train subsets.
Mean across repeats = conditional average predictive risk under this procedure on
these flowers; across-repeat SD = RESAMPLING INSTABILITY (training variation + eval
composition + model sensitivity — NEVER "model variance"). Not a statement about
new irises.

Two stages, two sidecars, committed in ORDER:

  --stage anchor   anchor_lda4 + BOTH controls (lda_petal, lda_sepal), all 6 rungs
                   -> sweeps/arena_anchor.sidecar.tsv
                   -> sweeps/arena_anchor_aux.sidecar.tsv
                   -> sweeps/headroom.tsv        (m_n, sd_n, delta_n, OPEN iff m_n >= delta_n)
                   -> sweeps/arena_partitions.tsv (per-cell geometry + disclosure)
                   COMMITTED BEFORE any challenger fit is summarized.
  --stage full     the 7 registered challengers, 6 rungs -> the FIXED 42-cell family
                   -> sweeps/arena.sidecar.tsv
                   -> sweeps/arena_aux.sidecar.tsv

Geometry (identical in both stages, deterministic):
  repeats j=1..10: StratifiedGroupKFold(n_splits=4, shuffle=True,
                   random_state=2026099200+j) over the non-sealed rows.
  Every row is scored in evaluation exactly 10 times; 10 x 4 = 40 fold-evals per cell.
  rungs n in {60, 45, 30, 20, 12, 8}: the fold's train pool (~60 rows) is subsampled
  by the NESTED QUOTA SCAN, seed 2026099300 + 100*j + k (EXACTLY 08's formula):
    - per class, a seeded permutation of that class's groups, with the size-2 twins
      group PINNED LAST in its (virginica) permutation — a registered deviation from
      a pure shuffle: it makes the accepted sets provably NESTED across rungs (a
      mid-permutation skip-then-fill at a quota boundary breaks nesting) at the
      documented cost of under-sampling the twins at small rungs (they are two
      identical rows; a small rung spending 2 of 12 slots on a duplicate would be
      the stranger choice).
    - class quotas ceil(n/2)/floor(n/2), ceiling class = virginica iff (j+k) even
      (only matters at n=45); quota_c capped at availability, remainder shifted to
      the other class; whole groups only.
  The subset for (j,k,n) is computed ONCE and served IDENTICALLY to every family —
  exact pairing by construction. Eval = the fold, identical for all families and
  rungs. Rung 60 = the full pool (n_actual recorded).

REGISTERED DELTAS FROM STUDY 08 (all committed at the METHOD gate):
  1. 09 CONSTANTS: REPEAT_SEED_BASE 2026099200 (was 2026092000), SUBSET_SEED_BASE
     2026099300 (was 2026093000). RUNGS/REPEATS/FOLDS/DELTA_FLOOR unchanged.
  2. ROSTER: 7 challengers, `families.MIN_RUNG` = 8 for ALL of them, so the
     eligibility matrix admits every cell and the guard family is the FIXED
     7 x 6 = 42. 08's 113-cell, ragged-eligibility family is gone. A `p_guard`
     from this study is NOT comparable to one from 08 (banned claim).
  3. TWO CONTROLS ride Stage A (08 had one): lda_petal answers RQ3's sufficiency
     half, lda_sepal is the registered one-sided WORSENING positive control.
  4. RQ4 AUX SIDECAR (new): a companion LONG-FORMAT table with the registered
     auxiliary metrics per (family, rung, repeat, fold) — see below.
  5. ONE FIT PER CELL: 08 called `families.dev_brier` (fit -> proba -> Brier).
     09 calls `families.fit_predict_proba` ONCE and derives Brier AND every
     auxiliary metric from that single probability vector — arithmetically
     identical Brier, half the fits, and the aux metrics are guaranteed to
     describe the very same fit the primary metric came from. `main()` runs an
     IDENTITY PREFLIGHT that re-derives one cell through `families.dev_brier`
     and refuses to start if the two paths disagree.

AUXILIARY METRICS (study.yaml `auxiliary_metrics.registered`), long format
`family, rung, repeat, fold, metric, value, note`:
    val_logloss, val_auc, val_pr_auc, val_accuracy, val_f1, cal_intercept, cal_slope
  * EPS CLIP 1e-6 applies ONLY to the log/logit transforms (log loss, and the logit
    feature of the calibration fit). It NEVER touches a Brier term — the primary
    metric is computed from RAW probabilities. This is a registered restriction.
  * cal_intercept / cal_slope: logit-scale (Cox) recalibration — logistic regression
    of the eval labels on logit(clip(p)), unpenalized, fit ON THE EVAL PREDICTIONS.
    A slope of 1 and intercept of 0 mean "already calibrated on these rows".
  * DEGENERATE EVAL FOLDS: a group-quota fold can carry a single class. AUC-family
    metrics (val_auc, val_pr_auc) and the calibration pair are then written as `NA`
    with `note=single-class-eval` — they are UNDEFINED, not zero, and the sweep does
    NOT crash. val_accuracy and val_f1 remain defined (f1 with zero_division=0).

SEED DOMAIN (claim 08#C11 — the `2**32-1` overflow trap bit BOTH prior studies):
every literal AND every derived seed (max j, max k) is asserted `< 2**32` at import
time, and `build_geometry` re-asserts per draw.

REGISTERED-SEED DISCLOSURE (not a defect, disclosed because the study.yaml seed
registry claims disjointness): SUBSET_SEED_BASE + 100*j + k spans
2026099400..2026100303, which CONTAINS 2026099500 — the analysis's sensitivity
Monte-Carlo seed — at (j=2, k=0). Two unrelated RNG consumers (a class-group
permutation vs. a sign-flip stream) share one integer. Determinism and validity are
unaffected; the "disjoint namespace" discipline is not perfectly held. Recorded
here so no one discovers it in the audit.

The guard family is FIXED by the eligibility matrix — crashed or short cells occupy
their slots as never-firing entries in the analysis; nothing is silently dropped or
re-run. Sealed rows (seed-20260909 test partition, PROCEDURALLY FRESH ONLY — all 100
values are public in the 07/08 ledgers) are FROZEN OUT of every draw: not re-drawn,
not scored, not seen. Max Jaccard overlap between any fold's eval set and the
DECLARED dev set is published in arena_partitions.tsv (disclosure only, no
exclusions — exclusion rules are their own selection bias; study 07 claim C6).

MEASUREMENT sweep: promotes no winner, writes no results.tsv row (sweep-rules.md
carve-out). Verdicts are computed ONLY by the frozen sweeps/analysis.py.

Run (from the study directory, AFTER the gates, E0001, the metrology and the RQ0
headroom publication)::

    uv run --locked python ../../scripts/run_with_log.py \
      --timeout-seconds 1200 --log sweep_arena_anchor.log -- \
      uv run --locked python -u sweeps/arena.py --stage anchor

    uv run --locked python ../../scripts/run_with_log.py \
      --timeout-seconds 3600 --log sweep_arena_full.log -- \
      uv run --locked python -u sweeps/arena.py --stage full

Smoke the wiring without spending the sweep: `--repeats 1` and/or `--rungs 60,12`
(both print a WARNING and must never feed study.yaml or the analysis).
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    f1_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedGroupKFold

STUDY_DIR = Path(__file__).resolve().parent.parent
if str(STUDY_DIR) not in sys.path:
    sys.path.insert(0, str(STUDY_DIR))

import families  # noqa: E402  (needs STUDY_DIR on sys.path)

from kleinlib.data import three_way_split  # noqa: E402
from kleinlib.sweep import SIDECAR_COLUMNS, SweepRunner  # noqa: E402
from kleinlib.workflow import load_contract  # noqa: E402

RUNGS = (60, 45, 30, 20, 12, 8)
REPEATS = 10
FOLDS = 4
REPEAT_SEED_BASE = 2026099200            # + j  -> 2026099201..2026099210
SUBSET_SEED_BASE = 2026099300            # + 100*j + k (EXACTLY 08's formula)
TARGET = "is_virginica"
GROUP = "group_id"
DELTA_FLOOR = 0.005                      # registered floor-of-the-floor
CEILING_CLOSED_M = 0.06                  # closure-reason threshold (07 sealed 0.055 ceil)
UNMEASURABLE_FAIL_FRACTION = 0.10
#: Registered eps for the LOG/LOGIT transforms ONLY. Never applied to Brier.
EPS = 1e-6
AUX_METRICS = (
    "val_logloss",
    "val_auc",
    "val_pr_auc",
    "val_accuracy",
    "val_f1",
    "cal_intercept",
    "cal_slope",
)
AUX_COLUMNS = ("family", "rung", "repeat", "fold", "metric", "value", "note")
NA = "NA"

#: Registered seed-domain asserts (claim 08#C11). Cheap, loud, and at import time.
SEED_DOMAIN = 2**32
assert REPEAT_SEED_BASE + REPEATS < SEED_DOMAIN, "repeat seeds must be < 2**32"
assert REPEAT_SEED_BASE + 1 == 2026099201, "registered first repeat seed is 2026099201"
assert REPEAT_SEED_BASE + REPEATS == 2026099210, "registered last repeat seed is 2026099210"
assert (
    SUBSET_SEED_BASE + 100 * REPEATS + (FOLDS - 1) < SEED_DOMAIN
), "subset seeds must be < 2**32"


def ceil_3dp(value: float) -> float:
    """Round UP to 3 decimal places. Exact-boundary values are NOT bumped."""
    return math.ceil(value * 1000.0 - 1e-12) / 1000.0


# ---------------------------------------------------------------------------
# geometry — an exact port of study 08's frozen scan
# ---------------------------------------------------------------------------

def load_declared(study_dir: Path):
    """(non_sealed, declared_dev_row_ids, sealed_n) from the contract split."""
    contract = load_contract(study_dir)
    split = contract["data"]["split"]
    if split.get("kind") != "group":
        raise SystemExit(f"expected a group split, contract declares {split.get('kind')!r}")
    if not 0 <= int(split["seed"]) < SEED_DOMAIN:
        raise SystemExit(f"declared split seed {split['seed']} is outside [0, 2**32)")
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
    if not 0 <= seed < SEED_DOMAIN:
        raise SystemExit(f"derived subset seed {seed} is outside [0, 2**32)")
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


def build_geometry(
    non_sealed: pd.DataFrame,
    declared_dev_rows: set,
    repeats: int,
    rungs: tuple[int, ...] = RUNGS,
):
    """All (j,k) partitions + per-rung subsets + the geometry/disclosure table."""
    partitions: dict[tuple[int, int], dict] = {}
    geometry_rows: list[dict] = []
    y = non_sealed[TARGET]
    for j in range(1, repeats + 1):
        repeat_seed = REPEAT_SEED_BASE + j
        if not 0 <= repeat_seed < SEED_DOMAIN:
            raise SystemExit(f"derived repeat seed {repeat_seed} is outside [0, 2**32)")
        skf = StratifiedGroupKFold(n_splits=FOLDS, shuffle=True, random_state=repeat_seed)
        for k, (pool_idx, dev_idx) in enumerate(
            skf.split(non_sealed, y, groups=non_sealed[GROUP])
        ):
            pool = non_sealed.iloc[pool_idx]
            dev = non_sealed.iloc[dev_idx]
            perms = class_group_permutation(pool, SUBSET_SEED_BASE + 100 * j + k)
            ceil_class = 1 if (j + k) % 2 == 0 else 0
            dev_rows = set(dev["_row"])
            inter = len(dev_rows & declared_dev_rows)
            union = len(dev_rows | declared_dev_rows)
            subsets = {}
            for n in rungs:
                sub = quota_subset(pool, perms, n, ceil_class)
                subsets[n] = sub
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


# ---------------------------------------------------------------------------
# auxiliary metrics (RQ4) — one probability vector, seven registered readings
# ---------------------------------------------------------------------------

def _logit(p: np.ndarray) -> np.ndarray:
    """logit of the EPS-CLIPPED probability. The clip lives here and in log loss ONLY."""
    q = np.clip(p, EPS, 1.0 - EPS)
    return np.log(q / (1.0 - q))


def aux_metrics(y_true: np.ndarray, proba: np.ndarray) -> dict[str, tuple[float | None, str]]:
    """Registered auxiliary metrics as `metric -> (value | None, note)`.

    `None` means UNDEFINED on these rows (written `NA`), never 0. The EPS clip is
    applied to the log/logit transforms only — Brier never sees it.
    """
    y = np.asarray(y_true).astype(int)
    p = np.asarray(proba, dtype=float)
    out: dict[str, tuple[float | None, str]] = {}

    clipped = np.clip(p, EPS, 1.0 - EPS)
    out["val_logloss"] = (
        float(-np.mean(y * np.log(clipped) + (1 - y) * np.log(1.0 - clipped))),
        "",
    )
    hard = (p >= 0.5).astype(int)
    out["val_accuracy"] = (float(accuracy_score(y, hard)), "")
    out["val_f1"] = (float(f1_score(y, hard, zero_division=0)), "")

    single_class = len(np.unique(y)) < 2
    if single_class:
        # A group-quota eval fold CAN carry one class. Ranking and calibration are
        # undefined there — recorded as NA, never as 0, and never a crash.
        for name in ("val_auc", "val_pr_auc", "cal_intercept", "cal_slope"):
            out[name] = (None, "single-class-eval")
        return out

    out["val_auc"] = (float(roc_auc_score(y, p)), "")
    out["val_pr_auc"] = (float(average_precision_score(y, p)), "")

    z = _logit(p).reshape(-1, 1)
    if float(np.ptp(z)) == 0.0:
        # Constant logit: the slope is not identified (any slope fits equally).
        out["cal_intercept"] = (None, "constant-logit")
        out["cal_slope"] = (None, "constant-logit")
        return out
    # UNPENALISED via C=inf, not penalty=None: sklearn deprecated `penalty` in
    # 1.8 and removes it in 1.10 ("use C=np.inf instead of penalty=None").
    model = LogisticRegression(C=np.inf, solver="lbfgs", max_iter=1000)
    with warnings.catch_warnings():
        # Perfect separation is COMMON on this pair; the non-convergence is recorded
        # in the note rather than shouted 1680 times into the log.
        warnings.simplefilter("ignore", ConvergenceWarning)
        model.fit(z, y)
    note = "not-converged" if int(model.n_iter_[0]) >= 1000 else ""
    out["cal_intercept"] = (float(model.intercept_[0]), note)
    out["cal_slope"] = (float(model.coef_[0][0]), note)
    return out


class AuxWriter:
    """Append-as-you-go writer for the long-format aux sidecar.

    Mirrors `kleinlib.sweep.SweepRunner`'s discipline: flushed per trial, never
    buffered, so an interrupted sweep keeps every completed cell. Opened LAZILY so
    that SweepRunner's own "sidecar already exists" refusal fires first and this
    file is never clobbered by a run that was going to be rejected anyway.
    """

    def __init__(self, path: Path, *, append: bool) -> None:
        self.path = path
        self.append = append
        self._ready = False

    def _ensure(self) -> None:
        if self._ready:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not (self.append and self.path.exists()):
            self.path.write_text("\t".join(AUX_COLUMNS) + "\n", encoding="utf-8")
        self._ready = True

    def write(self, family: str, rung: int, repeat: int, fold: int,
              metrics: dict[str, tuple[float | None, str]]) -> None:
        self._ensure()
        lines = []
        for name in AUX_METRICS:
            value, note = metrics[name]
            lines.append(
                "\t".join(
                    [family, str(rung), str(repeat), str(fold), name,
                     NA if value is None else repr(float(value)), note]
                )
            )
        with self.path.open("a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# the sweep
# ---------------------------------------------------------------------------

def stage_families(stage: str) -> list[str]:
    if stage == "anchor":
        return [families.ANCHOR, *families.CONTROLS]
    return list(families.CHALLENGERS)


def build_params(stage: str, repeats: int, rungs: tuple[int, ...] = RUNGS) -> list[dict[str, object]]:
    params: list[dict[str, object]] = []
    for family in stage_families(stage):
        for n in rungs:
            if stage == "full" and not families.eligible(family, n):
                continue
            for j in range(1, repeats + 1):
                for k in range(FOLDS):
                    params.append({"family": family, "rung": n, "repeat": j, "fold": k})
    return params


def make_trial_fn(partitions, aux: AuxWriter):
    """ONE fit per cell; Brier and every aux metric come from the same proba vector."""
    def trial_fn(params: dict) -> dict:
        family = str(params["family"])
        rung, repeat, fold = (
            int(params["rung"]), int(params["repeat"]), int(params["fold"])
        )
        part = partitions[(repeat, fold)]
        train = part["subsets"][rung]
        dev = part["dev"]
        proba = families.fit_predict_proba(family, train, dev, target=TARGET)
        # RAW probabilities — the EPS clip never touches a Brier term.
        brier = float(brier_score_loss(dev[TARGET], proba))
        aux.write(family, rung, repeat, fold, aux_metrics(dev[TARGET].to_numpy(), proba))
        return {"primary_metric": brier, "status": "ok"}

    return trial_fn


def identity_preflight(partitions, rungs: tuple[int, ...]) -> None:
    """Refuse to start unless proba->Brier reproduces `families.dev_brier` exactly.

    Study 09 derives the primary metric from `fit_predict_proba` (one fit per cell,
    aux metrics guaranteed to describe that same fit) where study 08 called
    `dev_brier`. This costs ONE extra fit for the whole sweep and makes the
    substitution auditable instead of assumed.
    """
    key = sorted(partitions)[0]
    n = rungs[0]
    train, dev = partitions[key]["subsets"][n], partitions[key]["dev"]
    proba = families.fit_predict_proba(families.ANCHOR, train, dev, target=TARGET)
    mine = float(brier_score_loss(dev[TARGET], proba))
    theirs = float(families.dev_brier(families.ANCHOR, train, dev, target=TARGET))
    if not math.isclose(mine, theirs, rel_tol=0.0, abs_tol=1e-12):
        raise SystemExit(
            "REFUSING TO RUN — identity preflight failed: proba->brier_score_loss "
            f"gives {mine!r} but families.dev_brier gives {theirs!r}. The aux "
            "metrics would describe a different fit than the primary metric."
        )
    print(f"identity preflight OK: proba->Brier == families.dev_brier ({mine:.6f})")


def write_headroom(trials, out_path: Path, rungs: tuple[int, ...] = RUNGS) -> None:
    """Stage-A ONLY: per-rung anchor floor + OPEN/CLOSED, before any challenger."""
    anchor_vals: dict[int, list[float]] = {n: [] for n in rungs}
    anchor_fail: dict[int, int] = {n: 0 for n in rungs}
    for t in trials:
        if str(t.params["family"]) != families.ANCHOR:
            continue
        n = int(t.params["rung"])
        if n not in anchor_vals:
            continue
        if t.status == "ok" and t.primary_metric is not None:
            anchor_vals[n].append(float(t.primary_metric))
        else:
            anchor_fail[n] += 1
    rows = []
    for n in rungs:
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
    if not state_path.is_file():
        raise SystemExit("study_state.json is missing; scaffold the study first")
    gates = json.loads(state_path.read_text(encoding="utf-8")).get("gates", {})
    pending = [g for g in ("consult", "data", "method")
               if gates.get(g, {}).get("status") not in {"recorded", "overridden"}]
    if pending:
        raise SystemExit(
            "refusing to run: the arena is MEASUREMENT and runs only after the "
            f"gates. Pending: {', '.join(pending)}."
        )


def parse_rungs(raw: str | None) -> tuple[int, ...]:
    if raw is None:
        return RUNGS
    try:
        chosen = tuple(int(v) for v in raw.split(",") if v.strip())
    except ValueError as exc:
        raise SystemExit(f"--rungs must be a comma-separated list of integers: {exc}") from exc
    unknown = [n for n in chosen if n not in RUNGS]
    if unknown:
        raise SystemExit(f"--rungs may only SUBSET the registered {RUNGS}; got {unknown}")
    if not chosen:
        raise SystemExit("--rungs must name at least one rung")
    return tuple(n for n in RUNGS if n in chosen)  # registered order, always


def main() -> None:
    parser = argparse.ArgumentParser(description="09 arena (measurement sweep)")
    parser.add_argument("--stage", choices=["anchor", "full"], required=True)
    parser.add_argument("--repeats", type=int, default=REPEATS)
    parser.add_argument("--rungs", default=None,
                        help="SMOKE ONLY: comma-separated subset of the registered rungs")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    rungs = parse_rungs(args.rungs)

    require_gates(STUDY_DIR)
    if args.stage == "full":
        anchor_sidecar = STUDY_DIR / "sweeps" / "arena_anchor.sidecar.tsv"
        if not anchor_sidecar.is_file():
            raise SystemExit("stage full refuses to run before the Stage-A sidecar is committed")

    non_sealed, declared_dev_rows, sealed_n = load_declared(STUDY_DIR)
    print(f"non-sealed rows: {len(non_sealed)}  sealed (frozen out): {sealed_n}")
    print(f"stage {args.stage}: {stage_families(args.stage)}")
    partitions, geometry = build_geometry(non_sealed, declared_dev_rows, args.repeats, rungs)
    identity_preflight(partitions, rungs)

    # Stage A -> arena_anchor.sidecar.tsv + arena_anchor_aux.sidecar.tsv
    # Stage B -> arena.sidecar.tsv        + arena_aux.sidecar.tsv
    # Two stages, two PAIRS of files: neither stage can overwrite the other's, and
    # sweeps/analysis.py concatenates whichever aux files exist.
    name = "arena_anchor" if args.stage == "anchor" else "arena"
    aux_path = STUDY_DIR / "sweeps" / f"{name}_aux.sidecar.tsv"
    aux = AuxWriter(aux_path, append=args.resume)
    if args.resume and not aux_path.exists():
        print(f"WARNING: --resume but {aux_path.name} is missing; the aux rows for the "
              "already-completed trials CANNOT be reconstructed without re-fitting. "
              "Prefer --overwrite for a clean pair of sidecars.")

    summary = SweepRunner(
        name,
        study_dir=STUDY_DIR,
        trial_fn=make_trial_fn(partitions, aux),
        params_list=build_params(args.stage, args.repeats, rungs),
        metric_goal="lower",
        resume=args.resume,
        overwrite=args.overwrite,
    ).run()
    print(f"sidecar columns: {list(SIDECAR_COLUMNS)}")
    print(f"wrote {aux_path} (long format: {list(AUX_COLUMNS)})")

    crashed = [t for t in summary.trials if t.status != "ok"]
    if crashed:
        print(f"NOTE: {len(crashed)} trial(s) crashed — recorded honestly in the sidecar; "
              "they occupy their guard slots as never-firing placeholders and carry NO "
              "aux rows")

    if args.stage == "anchor":
        geometry.to_csv(STUDY_DIR / "sweeps" / "arena_partitions.tsv", sep="\t", index=False)
        print(f"wrote sweeps/arena_partitions.tsv  "
              f"(max jaccard dev-vs-declared: {geometry['jaccard_dev_vs_declared'].max():.4f})")
        n_by_rung = geometry.groupby("rung")["n_actual"].agg(["min", "max"])
        for n in rungs:
            lo, hi = int(n_by_rung.loc[n, "min"]), int(n_by_rung.loc[n, "max"])
            print(f"  nominal rung {n:>2}: realized n_actual in [{lo}, {hi}] "
                  "(NOMINAL-RUNG QUALIFIER IS MANDATORY in every claim)")
        write_headroom(summary.trials, STUDY_DIR / "sweeps" / "headroom.tsv", rungs)
        print("STAGE A COMPLETE — commit the four sweeps/ files BEFORE any challenger fit.")
    else:
        cells = len(families.CHALLENGERS) * len(rungs)
        print(f"STAGE B COMPLETE — {cells} (challenger, rung) cells; verdicts come ONLY "
              "from sweeps/analysis.py.")

    if args.repeats != REPEATS or rungs != RUNGS:
        print(f"WARNING: ran {args.repeats} repeats over rungs {rungs}, not the "
              f"registered {REPEATS} over {RUNGS}; wiring smoke only — must never feed "
              "study.yaml or the analysis.")
    print("MEASUREMENT SWEEP: no winner promoted, no results.tsv row (sweep-rules.md carve-out)")


if __name__ == "__main__":
    main()
