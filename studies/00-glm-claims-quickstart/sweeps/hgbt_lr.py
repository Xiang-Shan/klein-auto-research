"""sweeps/hgbt_lr.py — Experiment 6: HGBT learning_rate sweep via kleinlib.sweep.

Sweeps ONE axis — `learning_rate` in {0.03, 0.06, 0.1, 0.15, 0.2} — on top of exp 3's
committed HGBT recipe (same preprocessing/drops: OHE min_freq=20, drop the 7
model-derivative columns, class_weight=balanced, max_leaf_nodes=31, early_stopping;
`git show b1389ca:studies/00-glm-claims-quickstart/train.py`). Baseline: exp 3,
val_auc=0.662897. The FIXED split is loaded once and reused for every trial — a sweep
tunes the model, never the data contract.

Protocol: `.claude/skills/klein/references/sweep-rules.md`. Every trial is appended to
`sweeps/hgbt_lr.sidecar.tsv` by `kleinlib.sweep.SweepRunner` as it finishes; this
script does NOT touch `results.tsv`, does NOT commit, and does NOT pickle a model —
those stay manual, applied by hand around this script per the rules (winner snapshotted
into `train.py`, `train.py` rerun once for the official eval side-effects, THEN the one
results.tsv row).

Usage: `cd studies/00-glm-claims-quickstart && uv run sweeps/hgbt_lr.py`
"""

from __future__ import annotations

from pathlib import Path

from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import Pipeline

import kleinlib
from kleinlib.sweep import SweepRunner

RANDOM_SEED = 42
BASELINE_VAL_AUC = 0.662897  # exp 3, campaign Phase-0 HGBT recipe
MIN_FREQUENCY = 20
LEARNING_RATES = [0.03, 0.06, 0.1, 0.15, 0.2]

# Same 7 model-derivative columns exp 3 drops (campaign exp6).
DROP_REDUNDANT = [
    "engine_type",
    "displacement",
    "cylinder",
    "max_torque_nm",
    "max_torque_rpm",
    "max_power_bhp",
    "max_power_rpm",
]

STUDY_DIR = Path(".")
PREPARED_PATH = Path("data/prepared/insurance_claims_prepared.csv")
TARGET_COLUMN = "claim_status"


def load_split():
    """Same loading as exp 3's train.py: drop the 7 cols, then the FIXED split."""
    X, y = kleinlib.data.load_xy(PREPARED_PATH, TARGET_COLUMN)
    X = X.drop(columns=DROP_REDUNDANT, errors="ignore")
    return kleinlib.data.fixed_split(X, y)  # seed=42, test_size=0.2, stratify=True


def build_model(numeric_cols: list[str], categorical_cols: list[str], learning_rate: float) -> Pipeline:
    """exp 3's exact recipe, `learning_rate` as the one swept knob."""
    preprocessor = kleinlib.encoders.build_preprocessor(
        numeric_cols, categorical_cols, kind="ohe", min_frequency=MIN_FREQUENCY
    )
    classifier = HistGradientBoostingClassifier(
        learning_rate=learning_rate,
        max_iter=500,
        max_leaf_nodes=31,
        l2_regularization=0.0,
        random_state=RANDOM_SEED,
        class_weight="balanced",
        early_stopping=True,
        validation_fraction=0.1,
        n_iter_no_change=20,
    )
    return Pipeline([("preprocess", preprocessor), ("model", classifier)])


def main() -> None:
    X_tr, X_va, y_tr, y_va = load_split()
    numeric_cols, categorical_cols = kleinlib.data.feature_column_groups(X_tr)

    def trial_fn(params: dict) -> dict:
        model = build_model(numeric_cols, categorical_cols, params["learning_rate"])
        model.fit(X_tr, y_tr)
        proba = model.predict_proba(X_va)[:, 1]
        val_auc = float(roc_auc_score(y_va, proba))
        return {"primary_metric": val_auc, "status": "ok"}

    params_list = [{"learning_rate": lr} for lr in LEARNING_RATES]
    runner = SweepRunner("hgbt_lr", STUDY_DIR, trial_fn, params_list, metric_goal="higher")
    summary = runner.run()

    print(f"baseline (exp 3, val_auc): {BASELINE_VAL_AUC:.6f}")
    for t in summary.trials:
        metric_str = "NA" if t.primary_metric is None else f"{t.primary_metric:.6f}"
        print(f"trial {t.trial}: learning_rate={t.params['learning_rate']} -> "
              f"status={t.status} primary_metric={metric_str} wall_seconds={t.wall_seconds:.1f}")

    w = summary.winner
    if w is None:
        print("winner: none (every trial crashed)")
    else:
        print(f"winner: trial {w.trial} learning_rate={w.params['learning_rate']} "
              f"primary_metric={w.primary_metric:.6f}")
    print(f"improved_over(baseline={BASELINE_VAL_AUC})={summary.improved_over(BASELINE_VAL_AUC)}")


if __name__ == "__main__":
    main()
