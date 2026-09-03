"""Compute the estimate or test statistic this cell registers.

This is the per-experiment mutable surface declared in study.yaml:entrypoint.
ONE falsifiable idea per candidate; `klein run-one` commits it before it runs.
"""

from __future__ import annotations

import os
import time

from kleinlib.eval import evaluate_scalar

RANDOM_SEED = 42
SMOKE = os.environ.get("KLEIN_SMOKE") == "1"
EXPERIMENT_ID = os.environ.get("KLEIN_EXPERIMENT_ID") or ("SMOKE" if SMOKE else None)
TRACK = os.environ.get("KLEIN_TRACK") or ("reproduction" if SMOKE else None)


def load_partition(evaluation_kind: str):
    """Select development or the sealed partition — explicitly, from the contract.

    `kleinlib.data.contract_split(study_dir)` / `load_partition(kind)` read
    study.yaml:data.split and print the `split_fingerprint:` line the notary
    checks. A literal split seed here is a DATA-gate BLOCKER (war story 8).
    """
    if evaluation_kind not in {"development", "final_test"}:
        raise RuntimeError(f"invalid KLEIN_EVALUATION_KIND={evaluation_kind!r}")
    raise NotImplementedError("read the partition from the contract, never from a literal seed")


def analyze(data) -> float:
    """Return the one number this cell measures."""
    raise NotImplementedError("compute the estimand (with its uncertainty) or the test statistic")


def main() -> None:
    t0 = time.time()
    evaluation_kind = os.environ.get("KLEIN_EVALUATION_KIND")
    if SMOKE:
        evaluation_kind = evaluation_kind or "development"
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
            "analyze.py must be invoked through `klein run-one`. For a pre-run "
            "syntax/shape check use `KLEIN_SMOKE=1 python analyze.py` — it prints "
            "the canonical block, writes no sidecars or snapshots, and is not "
            "evidence. Missing: " + ", ".join(missing)
        )
    data = load_partition(evaluation_kind)
    value = analyze(data)
    evaluate_scalar(
        value,
        exp_id=EXPERIMENT_ID,
        study_dir=".",
        t0=t0,
        metric_name="targets_outside_tolerance",
        metric_goal="lower",
    )


if __name__ == "__main__":
    main()
