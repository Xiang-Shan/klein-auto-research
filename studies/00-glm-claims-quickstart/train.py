"""train.py — the mutable experiment surface for 00-glm-claims-quickstart.

THIS is the one file you edit per experiment (5-15 line diffs). Everything stable
(data loading, the fixed split, metrics, model saving) lives in kleinlib so
experiments compose and stay comparable.

Loop contract:  repo CLAUDE.md + .claude/skills/klein/SKILL.md Hard Rules
Sweeps (the ONLY escape-hatch):  .claude/skills/klein/references/sweep-rules.md

E6 — HGBT `learning_rate` sweep winner, snapshotted from `sweeps/hgbt_lr.py` (5 trials
over {0.03, 0.06, 0.1, 0.15, 0.2} on exp 3's exact preprocessing/drops; see
`sweeps/hgbt_lr.sidecar.tsv` for the full trial table). Winner: learning_rate=0.06,
val_auc=0.664322 in the sweep run, beating exp 3's baseline (0.662897, learning_rate=
0.05) by +0.001425. This file reproduces that winner with NO sweep machinery — the only
diff from exp 3 is `learning_rate` and the experiment id.
"""

from __future__ import annotations

import time
from pathlib import Path

from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.pipeline import Pipeline

import kleinlib  # engine: kleinlib.data, kleinlib.encoders, kleinlib.eval, kleinlib.snapshot

# --- experiment knobs (the obvious mutable surface) -------------------------
RANDOM_SEED = 42
EXPERIMENT_ID = 6          # bump per experiment; matches the results.tsv row
RUN_BUDGET_SECONDS = 600   # keep within the CURRENT phase budget in study.yaml
MIN_FREQUENCY = 20         # campaign OneHotEncoder rarity threshold

# 7 columns that are near-deterministic functions of `model` (campaign exp6) —
# same drop-candidates flagged in this study's data_card.md ranked issue #2.
DROP_REDUNDANT = [
    "engine_type",
    "displacement",
    "cylinder",
    "max_torque_nm",
    "max_torque_rpm",
    "max_power_bhp",
    "max_power_rpm",
]

PREPARED_PATH = Path("data/prepared/insurance_claims_prepared.csv")
TARGET_COLUMN = "claim_status"


def load_split():
    """Load prepared data, drop the 7 model-derivative cols, FIXED split (kleinlib.data)."""
    X, y = kleinlib.data.load_xy(PREPARED_PATH, TARGET_COLUMN)
    X = X.drop(columns=DROP_REDUNDANT, errors="ignore")
    return kleinlib.data.fixed_split(X, y)  # seed=42, test_size=0.2, stratify=True


def build_model(numeric_cols: list[str], categorical_cols: list[str]) -> Pipeline:
    """exp 3's recipe with the sweep winner's learning_rate=0.06 (was 0.05)."""
    preprocessor = kleinlib.encoders.build_preprocessor(
        numeric_cols, categorical_cols, kind="ohe", min_frequency=MIN_FREQUENCY
    )
    classifier = HistGradientBoostingClassifier(
        learning_rate=0.06,
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
    t0 = time.time()
    X_tr, X_va, y_tr, y_va = load_split()
    numeric_cols, categorical_cols = kleinlib.data.feature_column_groups(X_tr)
    model = build_model(numeric_cols, categorical_cols)

    fit_start = time.time()
    model.fit(X_tr, y_tr)
    fit_seconds = time.time() - fit_start

    kleinlib.eval.evaluate(
        model, X_va, y_va,
        exp_id=EXPERIMENT_ID,
        t0=t0, fit_seconds=fit_seconds,
        train_n=len(X_tr), val_n=len(X_va),
        metric_name="val_auc", metric_goal="higher",
        study_dir=".",
    )


if __name__ == "__main__":
    main()
