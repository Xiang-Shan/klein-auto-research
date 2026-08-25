"""kseed_floor.py — the protocol-prescribed k-seed FIT-noise floor (Phase 0).

`references/consult-protocol.md` prescribes a k-seed measurement sweep before
`minimum_delta` is set: re-run the SAME config varying ONLY the seed, and the spread
of those runs is the smallest difference worth talking about.

**This study runs it first and expects it to be DEGENERATE.**

Registered prediction (`study.yaml:predictions_to_falsify`, tagged
`source: derived - closed-form estimator`): std is **exactly 0.0**. Linear
discriminant analysis is closed form — group means, a pooled covariance, one
eigen/SVD solve. There is no optimizer, no subsampling, no initialization: nothing
for a seed to perturb. Fisher's 1936 method has no random seed to vary.

That is not a reason to skip the step. The degenerate result is committed as the
documented deviation and is the evidence for the study's registered choice of a
DIFFERENT floor — `sweeps/ledger_floor.py`, which measures split noise rather than
fit noise, because on real data with a deterministic estimator the split is the only
thing that actually wobbles.

**Do NOT paste this sweep's block into `study.yaml`.** A zero floor would let any
difference count as a keep, which is the exact dishonesty the measurement exists to
prevent. The registered floor is the split lottery's.

Run it (from the study directory, AFTER the gates and AFTER the E0001 anchor, and
BEFORE `sweeps/ledger_floor.py`)::

    uv run --locked python ../../scripts/run_with_log.py \
      --timeout-seconds 300 --log sweep_kseed_floor.log -- \
      uv run --locked python -u sweeps/kseed_floor.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

STUDY_DIR = Path(__file__).resolve().parent.parent
if str(STUDY_DIR) not in sys.path:
    sys.path.insert(0, str(STUDY_DIR))

import families  # noqa: E402  (needs STUDY_DIR on sys.path)

from kleinlib.data import three_way_split  # noqa: E402
from kleinlib.noise_floor import summarize_noise  # noqa: E402
from kleinlib.sweep import SweepRunner  # noqa: E402
from kleinlib.workflow import load_contract  # noqa: E402

SWEEP_NAME = "kseed_floor"
#: k=5 is the consult protocol's default for runs under ~5 minutes.
SEEDS = (0, 1, 2, 3, 4)
TARGET = "is_virginica"


def load_declared_split(study_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return `(train, development)` for the DECLARED contract split.

    Read from `study.yaml`, never restated: the anchor whose fit noise we measure
    must be the anchor the ledger runs.
    """
    contract = load_contract(study_dir)
    split = contract["data"]["split"]
    prepared = pd.read_csv(study_dir / contract["data"]["prepared_path"]).reset_index(drop=True)
    X = prepared.drop(columns=[TARGET])
    y = prepared[TARGET]
    X_tr, X_dev, _X_te, _y_tr, _y_dev, _y_te = three_way_split(
        X,
        y,
        task="classification",
        strategy="group",
        development_size=float(split["development_size"]),
        test_size=float(split["test_size"]),
        seed=int(split["seed"]),
        groups=prepared[split["group_column"]],
    )
    return prepared.loc[X_tr.index], prepared.loc[X_dev.index]


def make_trial_fn(train: pd.DataFrame, development: pd.DataFrame):
    def trial_fn(params: dict) -> dict:
        # Vary ONLY the seed. LDA consumes no randomness, so this is exactly the
        # point: the global RNG is re-seeded and nothing downstream can notice.
        np.random.seed(int(params["seed"]))
        brier = families.dev_brier(families.ANCHOR, train, development, target=TARGET)
        return {"primary_metric": brier, "status": "ok"}

    return trial_fn


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
            "refusing to run: the k-seed floor is Phase-0 MEASUREMENT and runs only "
            f"after the gates. Pending: {', '.join(pending)}."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="k-seed fit-noise floor (measurement sweep)")
    parser.add_argument("--resume", action="store_true", help="continue an interrupted sidecar")
    parser.add_argument("--overwrite", action="store_true", help="replace an existing sidecar")
    args = parser.parse_args()

    require_gates(STUDY_DIR)
    train, development = load_declared_split(STUDY_DIR)
    print(f"declared split: train {len(train)} rows, development {len(development)} rows")

    summary = SweepRunner(
        SWEEP_NAME,
        study_dir=STUDY_DIR,
        trial_fn=make_trial_fn(train, development),
        params_list=[{"seed": seed} for seed in SEEDS],
        metric_goal="lower",
        resume=args.resume,
        overwrite=args.overwrite,
    ).run()

    values = [
        float(t.primary_metric)
        for t in summary.trials
        if t.status == "ok" and t.primary_metric is not None
    ]
    if len(values) < 3:
        raise SystemExit(f"need >= 3 successful trials, got {len(values)}")
    floor = summarize_noise(values, seeds=list(SEEDS)[: len(values)])

    print()
    print("=" * 72)
    print(f"K-SEED FIT-NOISE FLOOR — k={floor.k}, anchor config, seed varied and nothing else")
    print("=" * 72)
    print(f"values {[round(v, 12) for v in values]}")
    print(f"mean {floor.mean:.12g}  std {floor.std:.12g}  range {floor.value_range:.12g}")
    print()
    if floor.std == 0.0 and floor.value_range == 0.0:
        print("RESULT: DEGENERATE — std is exactly 0, as registered.")
        print("  LDA is closed form (group means, pooled covariance, one solve): there is")
        print("  no optimizer, no subsampling, no initialization for a seed to perturb.")
        print("  Fisher's 1936 method has no random seed to vary.")
        print("  The registered prediction HELD.")
    else:
        print("RESULT: NOT degenerate — the registered prediction was FALSIFIED.")
        print("  Something in the anchor path consumes randomness. Find it before")
        print("  trusting any other number in this study.")
    print()
    print("DO NOT paste this block into study.yaml. A zero floor would let any")
    print("difference count as a keep — the exact dishonesty the measurement prevents.")
    print("The study's registered floor is sweeps/ledger_floor.py's (split noise).")
    print()
    print("MEASUREMENT SWEEP: no winner promoted, no results.tsv row (sweep-rules.md carve-out)")


if __name__ == "__main__":
    main()
