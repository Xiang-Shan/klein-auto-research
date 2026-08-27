"""metrology_paired.py — the study's PAIRED metrology (Phase 1 MEASUREMENT sweep).

Study 09's registered floor measurement. It fuses study 07's `split_lottery.py`
(MULTI-FAMILY: every family fitted on every draw, so the sidecar carries paired
deltas, not just the incumbent's wobble) with study 08's `ledger_floor.py`
skeleton (contract-read partitions, SweepRunner sidecar discipline, in-domain seed
namespace, gate refusal, measurement carve-out footer).

What it measures
----------------
"When only the split changes, how much does each candidate's score move RELATIVE TO
THE ANCHOR'S, on the very same rows?"

k = 20 group-aware re-draws of the **NON-SEALED rows** (train + development of the
declared seed-20260909 split; the sealed partition's ~20 rows are frozen out of
every draw — not re-drawn, not scored, not seen). Each draw re-splits the non-sealed
pool with `GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=draw_seed)`,
the same primitive `kleinlib.data.three_way_split(strategy="group")` uses, so the
twin group (iris rows 102/143) can never straddle a draw either. Group constraints
make the boundary wobble by +/-1 row; that is documented, never forced.

On each draw, ALL TEN roster members — the anchor, the 7 registered challengers and
the 2 controls — are fitted on the IDENTICAL train rows and scored on the IDENTICAL
eval rows. That identity is what makes the difference series paired:

    d_c(draw) = brier_c(draw) - brier_anchor(draw)

SIGN CONVENTION (read this before quoting any number): POSITIVE d_c means the
candidate is WORSE than the anchor. This is the OPPOSITE of the arena's
`mean_gain = brier_anchor - brier_f` (positive = challenger better). The two live in
different files on purpose; never move a number between them without re-reading the
sign.

Registered deviation from study 07 (fixed by construction): 07's draw namespace made
the DECLARED split its own draw 1, so the "floor" and the ledger number were partly
self-referential. Study 09's draw seeds 2026099101..2026099120 are DISJOINT from the
declared split's {20260909, 20260910} and from every 07/08 namespace.

Registered scope deviation from study 08: 08's `ledger_floor.py` fitted the ANCHOR
ONLY and produced one marginal floor. Study 09 fits the whole roster and produces
PER-CANDIDATE PAIRED floors (`noise_floor_protocol.estimand: paired-comparison`).
The anchor's own MARGINAL spread is still published — in the same sidecar, as the
RQ0 comparison exhibit — because neither estimand is "the sharp one" a priori (07
measured paired > marginal for 5 of 6 families).

What this script does NOT do
----------------------------
It states NO floor. The reduction — per-candidate `floor_c = max(2*std(d_c),
range(d_c)/2)` at full precision, the ledger scalar `ceil3dp(max over the 7
CHALLENGER floors)` and the paste-ready `noise_floor:` block — is
`sweeps/candidate_floors.py`, a deterministic reducer that fits nothing. Splitting
the fitting from the reduction means the floor can be recomputed and audited without
re-running a single model.

BLINDNESS CLAUSE (study.yaml `noise_floor_protocol.blindness_clause`): `floor_c` is a
location-invariant dispersion functional of `d_c` (std and range ignore the mean), so
the floor cannot be tuned by the observed gains, and the verdict rule was frozen at
the METHOD gate before this sweep ran. The MEANS this sweep prints are SCOUTING
quantities that the arena re-measures on different geometry — they are never quoted
as RQ1 results, and never as evidence that a family "wins".

SEED DOMAIN (claim 08#C11 — the `2**32-1` overflow trap bit BOTH prior studies):
DRAW_SEED_BASE + draw for draw = 1..20 gives 2026099101..2026099120; asserted
`< 2**32` at import time.

EVIDENCE OF THIS SWEEP (registered): the sidecar
`sweeps/metrology_paired.sidecar.tsv`, the `noise_floor:` block that
`sweeps/candidate_floors.py` prints from it, and the CONSULT-gate re-record that
follows the paste. Nothing else.

This is a MEASUREMENT sweep — `references/sweep-rules.md` carve-out: it promotes no
winner and writes no `results.tsv` row.

Run it (from the study directory, AFTER the gates, AFTER E0001/E0002/E0003 and AFTER
`sweeps/kseed_floor.py`)::

    uv run --locked python ../../scripts/run_with_log.py \
      --timeout-seconds 1800 --log sweep_metrology_paired.log -- \
      uv run --locked python -u sweeps/metrology_paired.py

Smoke-check the wiring without spending the sweep: `--draws 3` (prints a WARNING;
must never feed study.yaml, candidate_floors.py or the analysis).
"""

from __future__ import annotations

import argparse
import json
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
from kleinlib.sweep import SweepRunner  # noqa: E402
from kleinlib.workflow import load_contract  # noqa: E402

SWEEP_NAME = "metrology_paired"
DRAWS = 20
#: Per-draw seed = base + draw -> 2026099101..2026099120. In-domain by
#: construction (claim 08#C11): both prior studies crashed all 20 trials on a
#: base that overflowed sklearn's 2**32-1 bound. Disjoint from the declared
#: split's {20260909, 20260910} and from every 07/08 namespace.
DRAW_SEED_BASE = 2026099100
#: 0.25 of the non-sealed rows -> ~20 eval rows, ~60 train rows.
DRAW_DEV_FRACTION = 0.25
TARGET = "is_virginica"
GROUP = "group_id"

#: Registered seed-domain assert (claim 08#C11). Cheap, loud, and at import time.
SEED_DOMAIN = 2**32
assert DRAW_SEED_BASE + DRAWS < SEED_DOMAIN, "metrology draw seeds must be < 2**32"
assert DRAW_SEED_BASE + 1 == 2026099101, "registered first draw seed is 2026099101"
assert DRAW_SEED_BASE + DRAWS == 2026099120, "registered last draw seed is 2026099120"


def roster() -> list[tuple[str, str]]:
    """The registered draw roster as `(family, role)` — anchor first, then order.

    Role is written into `params_json` so the reducer never has to re-derive
    membership from a name pattern: the sidecar is self-describing.
    """
    members: list[tuple[str, str]] = [(families.ANCHOR, "anchor")]
    members += [(f, "challenger") for f in families.CHALLENGERS]
    members += [(f, "control") for f in families.CONTROLS]
    names = [m[0] for m in members]
    if len(set(names)) != len(names):
        raise SystemExit(f"roster has duplicate family names: {names}")
    return members


def load_declared_partitions(study_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return `(non_sealed_rows, sealed_rows)` for the DECLARED contract split.

    Read from `study.yaml` rather than restated here: the metrology must never be
    able to drift away from the contract it is measuring.
    """
    contract = load_contract(study_dir)
    split = contract["data"]["split"]
    if split.get("kind") != "group":
        raise SystemExit(f"expected a group split, contract declares {split.get('kind')!r}")
    if not 0 <= int(split["seed"]) < SEED_DOMAIN:
        raise SystemExit(f"declared split seed {split['seed']} is outside [0, 2**32)")
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
    """One group-aware re-draw of the non-sealed rows into (train, evaluation)."""
    splitter = GroupShuffleSplit(
        n_splits=1, test_size=DRAW_DEV_FRACTION, random_state=draw_seed
    )
    positions = np.arange(len(non_sealed))
    train_idx, eval_idx = next(
        splitter.split(positions, non_sealed[TARGET], non_sealed[GROUP])
    )
    return non_sealed.iloc[train_idx], non_sealed.iloc[eval_idx]


def build_params(draws: int) -> list[dict[str, object]]:
    """One trial per (draw, family) — the sidecar IS the full paired record.

    Draw-major order so that every family in a draw sees the cached partition and
    an interrupted sweep leaves whole draws behind, never half a comparison.
    """
    params: list[dict[str, object]] = []
    for draw in range(1, draws + 1):
        seed = DRAW_SEED_BASE + draw
        if not 0 <= seed < SEED_DOMAIN:
            raise SystemExit(f"derived draw seed {seed} is outside [0, 2**32)")
        for family, role in roster():
            params.append(
                {"draw": draw, "seed": seed, "family": family, "role": role}
            )
    return params


def make_trial_fn(non_sealed: pd.DataFrame):
    """Identical train rows and identical eval rows for every family in a draw."""
    cache: dict[int, tuple[pd.DataFrame, pd.DataFrame]] = {}

    def trial_fn(params: dict) -> dict:
        seed = int(params["seed"])
        if seed not in cache:
            cache[seed] = draw_partitions(non_sealed, seed)
        train, evaluation = cache[seed]
        brier = families.dev_brier(str(params["family"]), train, evaluation, target=TARGET)
        return {
            "primary_metric": brier,
            "status": "ok",
            "train_n": len(train),
            "evaluation_n": len(evaluation),
        }

    return trial_fn


def report(trials, draws: int) -> None:
    """Print the per-family spread board and the anchor's MARGINAL exhibit.

    NO floor is stated here and NO study.yaml block is printed — that is
    `sweeps/candidate_floors.py`'s job, deliberately, so the floor can be
    recomputed and audited without re-fitting anything.
    """
    by_family: dict[str, dict[int, float]] = {}
    roles: dict[str, str] = {}
    for trial in trials:
        if trial.status != "ok" or trial.primary_metric is None:
            continue
        family = str(trial.params["family"])
        roles[family] = str(trial.params["role"])
        by_family.setdefault(family, {})[int(trial.params["draw"])] = float(
            trial.primary_metric
        )

    anchor = by_family.get(families.ANCHOR, {})
    if len(anchor) < 3:
        raise SystemExit(
            f"need >= 3 successful anchor draws to publish metrology, got {len(anchor)}"
        )
    common = sorted(anchor)
    anchor_values = [anchor[d] for d in common]

    print()
    print("=" * 78)
    print(
        f"PAIRED METROLOGY — k={len(common)} group-aware re-draws of the non-sealed rows"
    )
    print("=" * 78)
    print("SCOUTING QUANTITIES (blindness clause): these means are re-measured by the")
    print("arena on different geometry and are NEVER quoted as RQ1 results.")
    print()
    print(f"{'family':<18} {'role':<11} {'k':>3} {'mean_brier':>11} "
          f"{'mean_d':>10} {'std_d':>10} {'range_d':>10}")
    for family, role in roster():
        series = by_family.get(family, {})
        paired = [d for d in common if d in series]
        if not paired:
            print(f"{family:<18} {role:<11} {0:>3}  (no successful draws)")
            continue
        vals = [series[d] for d in paired]
        mean_brier = statistics.fmean(vals)
        if family == families.ANCHOR:
            print(f"{family:<18} {role:<11} {len(paired):>3} {mean_brier:>11.6f} "
                  f"{'—':>10} {'—':>10} {'—':>10}   (reference)")
            continue
        d = [series[dd] - anchor[dd] for dd in paired]
        std_d = statistics.stdev(d) if len(d) >= 2 else float("nan")
        range_d = max(d) - min(d)
        print(f"{family:<18} {role:<11} {len(paired):>3} {mean_brier:>11.6f} "
              f"{statistics.fmean(d):>+10.6f} {std_d:>10.6f} {range_d:>10.6f}")
    print()
    print("d_c = brier_c - brier_anchor; POSITIVE = candidate WORSE than the anchor.")
    print("(The arena's mean_gain = brier_anchor - brier_f has the OPPOSITE sign.)")

    marginal_std = statistics.stdev(anchor_values)
    print()
    print("--- RQ0 exhibit: the ANCHOR's own MARGINAL spread (estimand: marginal-resplit) ---")
    print(f"  k {len(anchor_values)}  mean {statistics.fmean(anchor_values):.6g}  "
          f"std {marginal_std:.6g}  "
          f"range {max(anchor_values) - min(anchor_values):.6g}")
    print(f"  marginal 2*std = {2.0 * marginal_std:.6g}  "
          "(published for comparison ONLY — it is NOT this study's ruler)")
    print(f"  values {[round(v, 6) for v in anchor_values]}")
    print()
    print("NEXT (the floor is stated THERE, not here):")
    print("  uv run --locked python -u sweeps/candidate_floors.py")
    print("    -> sweeps/candidate_floors.tsv  (per-candidate floor_c, FULL precision)")
    print("    -> the ledger scalar ceil3dp(max over the 7 CHALLENGER floors)")
    print("    -> the paste-ready noise_floor block (estimand: paired-comparison)")
    print("  then paste into BOTH tracks, commit, and re-record the consult gate:")
    print('    klein gate record consult --study . --acknowledged-by <actor> \\')
    print('      --note "minimum_delta set from the measured paired-redraw floors"')
    print("  then publish sweeps/rq0_headroom.tsv BEFORE any arena challenger number.")
    if draws != DRAWS:
        print()
        print(f"WARNING: ran {draws} draws, not the registered {DRAWS}. This output is a")
        print("         wiring smoke check and must NOT feed study.yaml, candidate_floors.py,")
        print("         or the analysis.")


def require_gates(study_dir: Path) -> None:
    """Refuse to run before the gates: this is Phase-1 measurement, not scouting."""
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
            "refusing to run: the paired metrology is Phase-1 MEASUREMENT and runs "
            f"only after the gates. Pending: {', '.join(pending)}."
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="paired-redraw metrology (measurement sweep)"
    )
    parser.add_argument("--draws", type=int, default=DRAWS, help="k (default: the registered 20)")
    parser.add_argument("--resume", action="store_true", help="continue an interrupted sidecar")
    parser.add_argument("--overwrite", action="store_true", help="replace an existing sidecar")
    args = parser.parse_args()

    require_gates(STUDY_DIR)
    non_sealed, sealed = load_declared_partitions(STUDY_DIR)
    print(f"non-sealed rows: {len(non_sealed)}  sealed (frozen out): {len(sealed)}")
    print(f"non-sealed groups: {non_sealed[GROUP].nunique()}")
    members = roster()
    print(f"roster: {len(members)} families "
          f"(1 anchor + {len(families.CHALLENGERS)} challengers "
          f"+ {len(families.CONTROLS)} controls)")

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
        print("         crashed cells are recorded honestly and are NOT re-run")
    report(summary.trials, args.draws)
    print()
    print("MEASUREMENT SWEEP: no winner promoted, no results.tsv row (sweep-rules.md carve-out)")


if __name__ == "__main__":
    main()
