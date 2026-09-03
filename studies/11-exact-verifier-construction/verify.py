"""The declared verifier — the checker, never the searcher.

`klein run-one` runs this as a second bounded subprocess after the entrypoint
exits, with KLEIN_ARTIFACT pointing at the artifact the search produced, and
decides the run on the number THIS script prints. It is outside
study.yaml:entrypoint.mutable and is hashed at the METHOD gate: once E0001 has
run, a change here is refused.

Two design rules, and they are the whole point of the study:

1. **It shares no code with the search.** `lib/nothree.py` is never imported
   here and nothing here is importable from there. The search decides whether a
   candidate point is addable in O(k) by hashing normalized directions; this
   file re-derives the objective by enumerating every one of the C(k,3) triples
   and applying the integer cross-product test to each. The clever algorithm
   and the obvious one agreeing is evidence; one algorithm agreeing with itself
   would be a tautology.

2. **It is the dumbest correct thing.** No sampling, no early exit that could
   hide a triple, no floating point anywhere: `(b-a) x (c-a)` is an integer and
   the test is whether that integer is zero. C(62,3) = 37820 triples at the
   largest grid this study uses — a checker has no reason to be clever.

What it rejects, with exit code 2: a malformed artifact, a coordinate that is
not an integer, a point off the n x n grid, a repeated point, and any three
points on a common line. What it reports rather than rejects: `claim_excess`,
the searcher's own claimed objective minus the objective computed here. A
non-zero `claim_excess` is not the checker's business to punish — it is the
notary's, and it becomes a `verifier_disagreement` crash.
"""

from __future__ import annotations

import json
import os
import sys
import time
from itertools import combinations

from kleinlib.eval import evaluate_scalar


class Rejected(Exception):
    """The artifact is not a valid no-three-in-line configuration."""


def _load(artifact_path: str) -> dict:
    try:
        with open(artifact_path, encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError) as exc:
        raise Rejected(f"artifact is not readable JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise Rejected("artifact must be a JSON object")
    return payload


def _points(payload: dict, n: int) -> list[tuple[int, int]]:
    raw = payload.get("points")
    if not isinstance(raw, list):
        raise Rejected("artifact has no `points` list")
    points: list[tuple[int, int]] = []
    for index, item in enumerate(raw):
        if not isinstance(item, list) or len(item) != 2:
            raise Rejected(f"point {index} is not a [x, y] pair: {item!r}")
        x, y = item
        # bool is an int in Python; a lattice point is not True.
        for name, value in (("x", x), ("y", y)):
            if isinstance(value, bool) or not isinstance(value, int):
                raise Rejected(
                    f"point {index} has a non-integer {name} coordinate {value!r} — "
                    "a lattice point that is not one"
                )
        if not (0 <= x < n and 0 <= y < n):
            raise Rejected(f"point {index} = ({x}, {y}) is off the {n} x {n} grid")
        points.append((int(x), int(y)))
    if len(set(points)) != len(points):
        raise Rejected("the point list repeats a lattice point; a configuration is a set")
    return points


def check(artifact_path: str) -> tuple[float, dict[str, float]]:
    """Independently score the artifact; raise :class:`Rejected` on an invalid one.

    The controls live in `data/prepared/instances.json`, frozen at the DATA gate:
    a negative control (the Erdos parabola set, which this checker must ACCEPT
    and score at exactly 11) and twelve positive controls (planted invalid
    objects, on which this checker must FIRE). E0001 runs both batteries.
    """
    payload = _load(artifact_path)
    if payload.get("problem") != "no-three-in-line":
        raise Rejected(f"artifact declares problem {payload.get('problem')!r}")
    n = payload.get("n")
    if isinstance(n, bool) or not isinstance(n, int) or n < 1:
        raise Rejected(f"artifact declares a non-positive-integer grid size n={n!r}")
    points = _points(payload, n)

    triples = 0
    for a, b, c in combinations(points, 3):
        triples += 1
        cross = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        if cross == 0:
            raise Rejected(f"points {a}, {b} and {c} are collinear")

    claimed = payload.get("claimed_objective")
    if isinstance(claimed, bool) or not isinstance(claimed, int):
        raise Rejected(
            "artifact does not state an integer `claimed_objective`; a searcher that "
            "will not say what it thinks it found cannot be audited"
        )
    objective = len(points)
    return float(objective), {
        "grid_n": float(n),
        "triples_checked": float(triples),
        "claim_excess": float(claimed - objective),
    }


def main() -> None:
    t0 = time.time()
    artifact_path = os.environ.get("KLEIN_ARTIFACT")
    if not artifact_path:
        raise RuntimeError(
            "verify.py is run by `klein run-one`, which sets KLEIN_ARTIFACT to the "
            "artifact the entrypoint declared."
        )
    try:
        value, extra = check(artifact_path)
    except Rejected as exc:
        print(f"REJECTED: {exc}")
        sys.exit(2)
    evaluate_scalar(
        value,
        exp_id=os.environ.get("KLEIN_EXPERIMENT_ID", "VERIFY"),
        # study_dir is deliberately NOT passed: aux_metrics.tsv is idempotent per
        # experiment id, so a verifier writing under the run's id would erase the
        # search telemetry the run just recorded. The verifier's own cost is on
        # the manifest as `verifier.wall_seconds`, where it belongs.
        study_dir=None,
        t0=t0,
        metric_name="points",
        metric_goal="higher",
        extra=extra,
    )


if __name__ == "__main__":
    main()
