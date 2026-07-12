"""train.py — the mutable experiment surface for a Klein study.

THIS is the one file you edit per experiment (5-15 line diffs). Everything stable
(data loading, the fixed split, metrics, model saving) lives in kleinlib so
experiments compose and stay comparable.

Loop contract:  repo CLAUDE.md + .claude/skills/klein/SKILL.md Hard Rules
Sweeps (the ONLY escape-hatch):  .claude/skills/klein/references/sweep-rules.md
"""

from __future__ import annotations

import os
import time

import kleinlib  # engine: kleinlib.data, kleinlib.encoders, kleinlib.eval, kleinlib.snapshot

# --- experiment knobs (the obvious mutable surface) -------------------------
RANDOM_SEED = 42
EXPERIMENT_ID = os.environ.get("KLEIN_EXPERIMENT_ID")
TRACK = os.environ.get("KLEIN_TRACK")
RUN_BUDGET_SECONDS = 600   # keep within the CURRENT phase budget in study.yaml


def load_split(evaluation_kind: str):
    """Load the configured development or sealed final-test partition."""
    if evaluation_kind not in {"development", "final_test"}:
        raise RuntimeError(f"invalid KLEIN_EVALUATION_KIND={evaluation_kind!r}")
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
    evaluation_kind = os.environ.get("KLEIN_EVALUATION_KIND")
    missing = [
        name
        for name, value in (
            ("KLEIN_EVALUATION_KIND", evaluation_kind),
            ("KLEIN_EXPERIMENT_ID", EXPERIMENT_ID),
            ("KLEIN_TRACK", TRACK),
        )
        if value is None
    ]
    if missing:
        raise RuntimeError(
            "train.py must be invoked through `klein run-one`; missing "
            + ", ".join(missing)
        )
    X_tr, X_va, y_tr, y_va = load_split(evaluation_kind)
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
        exp_id=EXPERIMENT_ID,
        study_dir=".",
        t0=t0, fit_seconds=fit_seconds,
        train_n=len(X_tr), val_n=len(X_va),
        metric_name="{{METRIC_NAME}}", metric_goal="{{METRIC_GOAL}}",
    )


if __name__ == "__main__":
    main()
