"""Search for the object the verifier will grade.

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
TRACK = os.environ.get("KLEIN_TRACK") or ("n_small" if SMOKE else None)


def load_partition(evaluation_kind: str):
    """Select development or the sealed partition — explicitly, from the contract.

    `kleinlib.data.contract_split(study_dir)` / `load_partition(kind)` read
    study.yaml:data.split and print the `split_fingerprint:` line the notary
    checks. A literal split seed here is a DATA-gate BLOCKER (war story 8).
    """
    if evaluation_kind not in {"development", "final_test"}:
        raise RuntimeError(f"invalid KLEIN_EVALUATION_KIND={evaluation_kind!r}")
    raise NotImplementedError("read the partition from the contract, never from a literal seed")


def search(data) -> float:
    """Write the candidate artifact and return the searcher's own score.

    The DISPOSITION comes from the declared verifier's number, not this
    one — the checker is never the searcher."""
    raise NotImplementedError("construct a candidate, write it out, and print its artifact: line")


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
            "search.py must be invoked through `klein run-one`. For a pre-run "
            "syntax/shape check use `KLEIN_SMOKE=1 python search.py` — it prints "
            "the canonical block, writes no sidecars or snapshots, and is not "
            "evidence. Missing: " + ", ".join(missing)
        )
    data = load_partition(evaluation_kind)
    value = search(data)
    evaluate_scalar(
        value,
        exp_id=EXPERIMENT_ID,
        study_dir=".",
        t0=t0,
        metric_name="points",
        metric_goal="higher",
    )


if __name__ == "__main__":
    main()
