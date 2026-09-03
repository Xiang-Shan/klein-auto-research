"""The declared verifier — the checker, never the searcher.

`klein run-one` runs this as a second bounded subprocess after the entrypoint
exits, with KLEIN_ARTIFACT pointing at the artifact the search produced, and
decides the run on the number THIS script prints. It is outside
study.yaml:entrypoint.mutable and is hashed at the METHOD gate: once E0001 has
run, a change here is refused.
"""

from __future__ import annotations

import os
import time

from kleinlib.eval import evaluate_scalar


def check(artifact_path: str) -> float:
    """Independently score the artifact; raise on an invalid one.

    Give it a positive control (a hand-planted invalid object it must reject)
    and a negative control (a known-valid object it must accept) in the DATA
    gate's verifier card.
    """
    raise NotImplementedError("verify the artifact and return its objective value")


def main() -> None:
    t0 = time.time()
    artifact_path = os.environ.get("KLEIN_ARTIFACT")
    if not artifact_path:
        raise RuntimeError(
            "verify.py is run by `klein run-one`, which sets KLEIN_ARTIFACT to the "
            "artifact the entrypoint declared."
        )
    evaluate_scalar(
        check(artifact_path),
        exp_id=os.environ.get("KLEIN_EXPERIMENT_ID", "VERIFY"),
        study_dir=".",
        t0=t0,
        metric_name="points",
        metric_goal="higher",
    )


if __name__ == "__main__":
    main()
