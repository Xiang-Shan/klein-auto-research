"""train.py — the mutable experiment surface for a Klein study.

THIS is the one file you edit per experiment (5-15 line diffs). Everything stable
(data loading, the fixed split, metrics, model saving) lives in kleinlib so
experiments compose and stay comparable.

Loop contract:  repo CLAUDE.md + .claude/skills/klein/SKILL.md Hard Rules
Sweeps (the ONLY escape-hatch):  .claude/skills/klein/references/sweep-rules.md
"""

from __future__ import annotations

import time

import kleinlib  # engine: kleinlib.data, kleinlib.encoders, kleinlib.eval, kleinlib.snapshot

# --- experiment knobs (the obvious mutable surface) -------------------------
RANDOM_SEED = 42
EXPERIMENT_ID = 0          # bump per experiment; matches the results.tsv row
RUN_BUDGET_SECONDS = 600   # keep within the CURRENT phase budget in study.yaml


def load_split():
    """Load prepared data and make the FIXED train/val split (via kleinlib.data)."""
    raise NotImplementedError(
        "TODO: use kleinlib.data to load the prepared artifact and produce the FIXED "
        "split declared in study.yaml:data.split. NEVER resample the val split. See "
        "kleinlib/data.py and the split contract in "
        ".claude/skills/klein/references/defaults-and-scaffolding.md."
    )


def build_model():
    """Return the model for THIS experiment — the code change IS the experiment."""
    raise NotImplementedError(
        "TODO: build the estimator for this experiment. Keep the diff 5-15 lines and "
        "put knobs as constants above. For categorical encoding use kleinlib.encoders "
        "(OHE / ordinal / target / ...). For torch models use kleinlib.torch_loop's "
        "MPS-safe index-shuffle batching (NEVER a DataLoader on MPS — see the MPS "
        "collapse story in .claude/skills/klein/references/war-stories.md)."
    )


def main() -> None:
    t0 = time.time()
    X_tr, X_va, y_tr, y_va = load_split()
    model = build_model()

    fit_start = time.time()
    model.fit(X_tr, y_tr)
    fit_seconds = time.time() - fit_start

    # kleinlib.eval.evaluate() prints the canonical metric block, appends the
    # aux_metrics.tsv sidecar, GUARDS against collapsed preds (min_proba_std), and
    # snapshots the best model. See kleinlib/eval.py for the exact signature.
    #   - regression study:  kleinlib.eval.evaluate_regression(...)
    #   - simulation / Monte-Carlo (no model, X_val):
    #         kleinlib.eval.evaluate_scalar(value, metric_name=..., metric_goal=..., extra=...)
    kleinlib.eval.evaluate(
        model, X_va, y_va,
        t0=t0, fit_seconds=fit_seconds,
        train_n=len(X_tr), val_n=len(X_va),
        metric_name="{{METRIC_NAME}}", metric_goal="{{METRIC_GOAL}}",
        extra={"experiment": EXPERIMENT_ID},
    )


if __name__ == "__main__":
    main()
