"""The only per-candidate mutable surface in a Klein v2 study."""

from __future__ import annotations

import os
import time

import kleinlib

RANDOM_SEED = 42
EXPERIMENT_ID = os.environ.get("KLEIN_EXPERIMENT_ID")
TRACK = os.environ.get("KLEIN_TRACK")


def load_split(evaluation_kind: str):
    """Select development or the sealed final-test partition explicitly.

    The workflow sets KLEIN_EVALUATION_KIND. Implement this function so
    ``development`` returns train/development and ``final_test`` returns the frozen
    chosen training data/final test. Never choose the partition from experiment code.
    """
    if evaluation_kind not in {"development", "final_test"}:
        raise RuntimeError(f"invalid KLEIN_EVALUATION_KIND={evaluation_kind!r}")
    raise NotImplementedError("implement the fixed three-way split declared in study.yaml")


def build_model():
    raise NotImplementedError("build this candidate")


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
    X_tr, X_dev, y_tr, y_dev = load_split(evaluation_kind)
    model = build_model()
    fit_start = time.time()
    model.fit(X_tr, y_tr)
    fit_seconds = time.time() - fit_start
    kleinlib.eval.evaluate(
        model,
        X_dev,
        y_dev,
        exp_id=EXPERIMENT_ID,
        study_dir=".",
        t0=t0,
        fit_seconds=fit_seconds,
        train_n=len(X_tr),
        val_n=len(X_dev),
        metric_name="mean_final_gap",
        metric_goal="lower",
    )


if __name__ == "__main__":
    main()
