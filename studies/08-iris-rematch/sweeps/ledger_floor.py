"""ledger_floor.py — the LEDGER's noise floor (Phase 1 MEASUREMENT sweep).

Study 08 adaptation of study 07's split_lottery.py: SAME registered recipe
(GroupShuffleSplit test_size=0.25 over the non-sealed rows — 80 in study 07,
79 here (the 08 split sealed 21 rows, twin pair included) — k=20, statistic
ceil3dp(2*std of the anchor), RAISE-ONLY escalation to klein's default
max(2*std, range/2)) applied to the FRESH declared split (seed 20260907), with a
fresh disjoint draw-seed namespace. Scope deviation from 07, registered: this
sweep fits the ANCHOR ONLY — the floor statistic never used the other families;
every family's distributional evidence lives in sweeps/rematch_arena.py, which
has its own registered per-rung floors (no range/2 escalation there; see
research_plan.md §4). Committed BEFORE any challenger transaction.

What it measures
----------------
"How much does the incumbent's own score wobble when only the split changes?"

k = 20 group-aware re-draws of the **79 non-sealed rows** (train + development of
the declared seed-20260907 split; the sealed partition took 21 rows, twins included). The 20 sealed test rows are frozen out of every
draw — they are not re-drawn, not scored, not seen. Each draw re-splits the 80 rows
into ~60 train / ~20 development with `GroupShuffleSplit(test_size=0.25)`, the same
primitive `kleinlib.data.three_way_split(strategy="group")` uses, so the twin group
(iris rows 102/143) can never straddle a draw either. Group constraints make the
60/20 boundary wobble by ±1 row; that is documented, never forced.

Only the ANCHOR is fitted on every draw (registered scope deviation from 07 —
see header); the sidecar carries the anchor's spread, which IS the floor.

The registered statistic
------------------------
    minimum_delta = 2 x std(anchor development Brier across the 20 draws)
                    rounded UP to 3 decimal places

This is an ACTIONABILITY THRESHOLD, conditional on these 100 flowers. It is not a
confidence interval, not a standard error of a population quantity, and not a
significance test. Do not let it masquerade as one.

Pre-registered escalation rule (committed before measurement): the script also
prints klein's protocol default `max(2*std, range/2)`. If that default EXCEEDS the
registered value, `minimum_delta` takes the LARGER number. A floor may be raised by
a documented rule; it may never be lowered after seeing data.

This is a MEASUREMENT sweep — `references/sweep-rules.md` carve-out: it promotes no
winner and no `results.tsv` row. Its evidence is the sidecar, the `noise_floor:`
block it prints for `study.yaml`, and the consult-gate re-record that follows.

Run it (from the study directory, AFTER the gates and AFTER the E0001 anchor)::

    uv run --locked python ../../scripts/run_with_log.py \
      --timeout-seconds 900 --log sweep_ledger_floor.log -- \
      uv run --locked python -u sweeps/ledger_floor.py

Smoke-check the wiring without spending the sweep: `--draws 2`.
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
from sklearn.model_selection import GroupShuffleSplit

STUDY_DIR = Path(__file__).resolve().parent.parent
if str(STUDY_DIR) not in sys.path:
    sys.path.insert(0, str(STUDY_DIR))

import families  # noqa: E402  (needs STUDY_DIR on sys.path)

from kleinlib.data import three_way_split  # noqa: E402
from kleinlib.noise_floor import summarize_noise  # noqa: E402
from kleinlib.sweep import SweepRunner  # noqa: E402
from kleinlib.workflow import load_contract  # noqa: E402

SWEEP_NAME = "ledger_floor"
DRAWS = 20
# Per-draw seed = base + draw -> 2026091001..2026091020. AMENDED 2026-08-25:
# the registered namespace 20260901001+ OVERFLOWED sklearn's 2**32-1 bound and
# all 20 trials crashed (sidecar preserved as *.crashed-seed-overflow.tsv) —
# the exact failure study 07's claim C19 warns about, reproduced here and fixed
# the same way: in-domain base, committed before any floor was stated.
DRAW_SEED_BASE = 2026091000
#: 0.25 of the 80 non-sealed rows -> ~20 development rows, ~60 train rows.
DRAW_DEV_FRACTION = 0.25
TARGET = "is_virginica"
GROUP = "group_id"


def load_declared_partitions(study_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return `(non_sealed_rows, sealed_rows)` for the DECLARED contract split.

    Read from `study.yaml` rather than restated here: the lottery must never be
    able to drift away from the contract it is measuring.
    """
    contract = load_contract(study_dir)
    split = contract["data"]["split"]
    if split.get("kind") != "group":
        raise SystemExit(f"expected a group split, contract declares {split.get('kind')!r}")
    prepared = pd.read_csv(study_dir / contract["data"]["prepared_path"]).reset_index(drop=True)

    X = prepared.drop(columns=[TARGET])
    y = prepared[TARGET]
    X_tr, X_dev, X_te, _y_tr, _y_dev, _y_te = three_way_split(
        X,
        y,
        task="classification",
        strategy="group",
        development_size=float(split["development_size"]),
        test_size=float(split["test_size"]),
        seed=int(split["seed"]),
        groups=prepared[split["group_column"]],
    )
    non_sealed = prepared.loc[sorted([*X_tr.index, *X_dev.index])].reset_index(drop=True)
    sealed = prepared.loc[sorted(X_te.index)].reset_index(drop=True)
    if len(non_sealed) + len(sealed) != len(prepared):
        raise SystemExit("partition arithmetic does not cover every row")
    if set(non_sealed[GROUP]) & set(sealed[GROUP]):
        raise SystemExit("a group straddles the sealed boundary — refusing to measure")
    return non_sealed, sealed


def draw_partitions(
    non_sealed: pd.DataFrame, draw_seed: int
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """One group-aware re-draw of the non-sealed rows into (train, development)."""
    splitter = GroupShuffleSplit(
        n_splits=1, test_size=DRAW_DEV_FRACTION, random_state=draw_seed
    )
    positions = np.arange(len(non_sealed))
    train_idx, dev_idx = next(
        splitter.split(positions, non_sealed[TARGET], non_sealed[GROUP])
    )
    return non_sealed.iloc[train_idx], non_sealed.iloc[dev_idx]


def build_params(draws: int) -> list[dict[str, object]]:
    """One trial per (draw, family) — the sidecar IS the full lottery record."""
    params: list[dict[str, object]] = []
    for draw in range(1, draws + 1):
        for family in (families.ANCHOR,):
            params.append(
                {"draw": draw, "seed": DRAW_SEED_BASE + draw, "family": family}
            )
    return params


def make_trial_fn(non_sealed: pd.DataFrame):
    cache: dict[int, tuple[pd.DataFrame, pd.DataFrame]] = {}

    def trial_fn(params: dict) -> dict:
        seed = int(params["seed"])
        if seed not in cache:
            cache[seed] = draw_partitions(non_sealed, seed)
        train, development = cache[seed]
        brier = families.dev_brier(str(params["family"]), train, development, target=TARGET)
        return {
            "primary_metric": brier,
            "status": "ok",
            "train_n": len(train),
            "development_n": len(development),
        }

    return trial_fn


def ceil_3dp(value: float) -> float:
    return math.ceil(value * 1000.0 - 1e-12) / 1000.0


def report(trials, draws: int) -> None:
    """Print the floor, the paired-delta spreads, and the study.yaml block."""
    by_family: dict[str, dict[int, float]] = {}
    for trial in trials:
        if trial.status != "ok" or trial.primary_metric is None:
            continue
        family = str(trial.params["family"])
        by_family.setdefault(family, {})[int(trial.params["draw"])] = float(
            trial.primary_metric
        )

    anchor = by_family.get(families.ANCHOR, {})
    if len(anchor) < 3:
        raise SystemExit(
            f"need >= 3 successful anchor draws to state a floor, got {len(anchor)}"
        )
    anchor_values = [anchor[d] for d in sorted(anchor)]
    floor = summarize_noise(anchor_values)

    registered = ceil_3dp(2.0 * floor.std)
    protocol_default = floor.suggested_minimum_delta
    chosen = max(registered, protocol_default)

    print()
    print("=" * 72)
    print(f"LEDGER FLOOR (07 recipe, 08 split) — k={len(anchor_values)} group-aware re-draws of the 79 non-sealed rows")
    print("=" * 72)
    print(f"anchor ({families.ANCHOR}) development Brier across draws:")
    print(f"  mean {floor.mean:.6g}  std {floor.std:.6g}  range {floor.value_range:.6g}")
    print(f"  values {[round(v, 6) for v in anchor_values]}")
    print()
    print(f"registered rule   2*std, ceil to 3dp      -> minimum_delta = {registered:.3f}")
    print(f"protocol default  max(2*std, range/2)     -> {protocol_default:.6g}")
    print(f"ESCALATION RULE   take the LARGER          -> minimum_delta = {chosen:.6g}")
    if protocol_default > registered:
        print("  (protocol default exceeded the registered value; the floor is RAISED, per")
        print("   the escalation rule committed at CONSULT before this measurement ran)")
    print()
    print("anchor-only sweep: paired family deltas live in sweeps/rematch_arena.py")
    print()
    print("--- paste into study.yaml under BOTH tracks' metric (primary AND challenger) ---")
    print(f"      minimum_delta: {chosen:.6g}   # split-lottery floor, k={floor.k}")
    print("      noise_floor:")
    print(f"        k: {floor.k}")
    print(f"        std: {floor.std:.6g}")
    print(f"        range: {floor.value_range:.6g}")
    print(f"        mean: {floor.mean:.6g}")
    print(f"        values: [{', '.join(f'{v:.6g}' for v in floor.values)}]")
    print(f'        source: "sweeps/{SWEEP_NAME}.sidecar.tsv"')
    print('        measured_after: "E0001"')
    print('        method: "split-lottery"')
    print("--- end block ---")
    print()
    print("next: set minimum_delta + noise_floor in study.yaml, commit, then")
    print('      klein gate record consult --study . --acknowledged-by <actor> \\')
    print('        --note "minimum_delta set from the measured split-lottery floor"')
    if draws != DRAWS:
        print()
        print(f"WARNING: ran {draws} draws, not the registered {DRAWS}. This output is a")
        print("         wiring smoke check and must NOT be pasted into study.yaml.")


def require_gates(study_dir: Path) -> None:
    """Refuse to run before the gates: this is Phase-0 measurement, not scouting."""
    state_path = study_dir / "study_state.json"
    if not state_path.is_file():
        raise SystemExit("study_state.json is missing; scaffold the study first")
    gates = json.loads(state_path.read_text(encoding="utf-8")).get("gates", {})
    pending = [
        name
        for name in ("consult", "data", "method")
        if gates.get(name, {}).get("status") not in {"recorded", "overridden"}
    ]
    if pending:
        raise SystemExit(
            "refusing to run: the ledger floor is Phase-1 MEASUREMENT and runs only "
            f"after the gates. Pending: {', '.join(pending)}."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="split-lottery noise floor (measurement sweep)")
    parser.add_argument("--draws", type=int, default=DRAWS, help="k (default: the registered 20)")
    parser.add_argument("--resume", action="store_true", help="continue an interrupted sidecar")
    parser.add_argument("--overwrite", action="store_true", help="replace an existing sidecar")
    args = parser.parse_args()

    require_gates(STUDY_DIR)
    non_sealed, sealed = load_declared_partitions(STUDY_DIR)
    print(f"non-sealed rows: {len(non_sealed)}  sealed (frozen out): {len(sealed)}")
    print(f"non-sealed groups: {non_sealed[GROUP].nunique()}")

    summary = SweepRunner(
        SWEEP_NAME,
        study_dir=STUDY_DIR,
        trial_fn=make_trial_fn(non_sealed),
        params_list=build_params(args.draws),
        metric_goal="lower",
        resume=args.resume,
        overwrite=args.overwrite,
    ).run()

    crashed = [t for t in summary.trials if t.status != "ok"]
    if crashed:
        print(f"WARNING: {len(crashed)} trial(s) crashed; see the sidecar's error column")
    report(summary.trials, args.draws)
    print()
    print("MEASUREMENT SWEEP: no winner promoted, no results.tsv row (sweep-rules.md carve-out)")


if __name__ == "__main__":
    main()
