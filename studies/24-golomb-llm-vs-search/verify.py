"""The declared verifier — the checker, never the searcher.

`klein run-one` runs this after search.py exits, with KLEIN_ARTIFACT pointing at the
artifact the run printed under `solution:`; the run is decided on the number THIS
script prints. It is outside `entrypoint.mutable`, hashed at the METHOD gate, and
shares no code with search.py: nothing is imported from it, and the check below is
written from the definition, not from the searcher's private checker.

It is the dumbest correct thing. For every (order, trial) pair of the lane the
artifact declares, the stored best ruler is re-checked from scratch with exact
integer arithmetic — exactly n integer marks, starting at 0, strictly increasing,
and all n(n-1)/2 pairwise differences distinct as a set — and it prints

  primary_metric       optima_matched: pairs whose VERIFIED best length equals the
                       optimum of OEIS A003022 for that order (instance.json)
  first_batch_matches  llm arm: pairs whose stored FIRST proposal batch holds a valid
                       optimal ruler (re-checked here); 0 for the search arm
  invalid_best         pairs with no verified best ruler (none stored, or the stored
                       one fails the check while claiming no length); never matched
  pairs                pairs checked;  sealed_lane: 1 when the artifact is the sealed lane

Rejects (exit 2): a malformed artifact (not JSON, wrong problem, an arm other than
the run's track, orders that are not the lane's, a missing or repeated (order,
trial) pair, more evaluations than the budget, an llm first batch that is not
exactly llm_batch entries); a claimed `best_length` that differs from the verified
one (including a length claimed for a ruler that fails the check); a first-batch
ruler that is valid and shorter than the stored best (the searcher lost its best);
and a verified ruler shorter than the tabulated optimum (the table or this checker
is wrong, and nothing is counted until that is resolved).
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from kleinlib.eval import evaluate_scalar

INSTANCE = Path(__file__).resolve().parent / "data" / "prepared" / "instance.json"


class Rejected(Exception):
    """The artifact cannot be scored as it stands."""


def is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def golomb_length(marks: object, n: int) -> int | None:
    """The length of `marks` if it is a valid n-mark Golomb ruler, else None."""
    if not isinstance(marks, list) or len(marks) != n:
        return None
    for mark in marks:
        if not is_int(mark):
            return None
    if marks[0] != 0:
        return None
    for i in range(1, n):
        if marks[i] <= marks[i - 1]:
            return None
    differences = []
    for i in range(n):
        for j in range(i + 1, n):
            differences.append(marks[j] - marks[i])
    if len(set(differences)) != len(differences):
        return None
    return marks[-1]


def check(payload: object, instance: dict, track: str | None) -> tuple[int, dict[str, float]]:
    if not isinstance(payload, dict):
        raise Rejected("the artifact is not a JSON object")
    if payload.get("problem") != "golomb-ruler":
        raise Rejected(f"the artifact declares problem {payload.get('problem')!r}")
    arm = payload.get("arm")
    if arm not in ("search", "llm"):
        raise Rejected(f"unknown arm {arm!r}")
    if track and track != arm:
        raise Rejected(f"the artifact is from arm {arm!r} but the run's track is {track!r}")
    lane = payload.get("lane")
    if lane not in ("development", "sealed"):
        raise Rejected(f"unknown lane {lane!r}")
    orders = instance[f"{lane}_orders"]
    if payload.get("orders") != orders:
        raise Rejected(f"orders {payload.get('orders')!r} are not the {lane} orders {orders}")
    trials = instance["trials"]
    budget = instance["budget_evaluations"]
    batch = instance["llm_batch"]
    optima = instance["optima"]
    pairs = payload.get("pairs")
    if not isinstance(pairs, list):
        raise Rejected("the artifact has no `pairs` list")

    expected = {(order, trial) for order in orders for trial in range(trials)}
    seen = set()
    matched = first_batch_matches = invalid_best = 0
    for index, pair in enumerate(pairs):
        if not isinstance(pair, dict):
            raise Rejected(f"pair {index} is not an object")
        order, trial = pair.get("order"), pair.get("trial")
        if not (is_int(order) and is_int(trial)) or (order, trial) not in expected:
            raise Rejected(f"pair {index}: (order, trial) = ({order!r}, {trial!r}) is not in the lane")
        if (order, trial) in seen:
            raise Rejected(f"pair ({order}, {trial}) appears twice")
        seen.add((order, trial))
        evaluations = pair.get("evaluations")
        if not is_int(evaluations) or not 0 <= evaluations <= budget:
            raise Rejected(f"pair ({order}, {trial}): evaluations {evaluations!r} outside 0..{budget}")
        optimum = optima[str(order)]

        claimed = pair.get("best_length")
        if claimed is not None and not is_int(claimed):
            raise Rejected(f"pair ({order}, {trial}): best_length {claimed!r} is not an integer")
        best = pair.get("best")
        length = None if best is None else golomb_length(best, order)
        if claimed != length:
            why = ""
            if length is None:
                why = " (no ruler is stored)" if best is None else " (the stored ruler fails the check)"
            raise Rejected(
                f"pair ({order}, {trial}): claims length {claimed!r} but the verified length "
                f"is {length!r}{why}"
            )
        if length is not None and length < optimum:
            raise Rejected(
                f"pair ({order}, {trial}): verified length {length} is below the tabulated "
                f"optimum {optimum}: the table or this checker is wrong"
            )
        if length is None:
            invalid_best += 1
        elif length == optimum:
            matched += 1

        if arm == "llm":
            entries = pair.get("first_batch")
            if not isinstance(entries, list) or len(entries) != batch:
                raise Rejected(f"pair ({order}, {trial}): first_batch must hold exactly {batch} entries")
            lengths = [golomb_length(entry, order) for entry in entries]
            valid = [x for x in lengths if x is not None]
            if valid and (length is None or min(valid) < length):
                raise Rejected(
                    f"pair ({order}, {trial}): the first batch holds a valid ruler of length "
                    f"{min(valid)}, shorter than the stored best {length!r}"
                )
            if optimum in valid:
                first_batch_matches += 1

    if seen != expected:
        raise Rejected(f"missing pairs: {sorted(expected - seen)}")
    return matched, {
        "first_batch_matches": first_batch_matches,
        "pairs": len(expected),
        "invalid_best": invalid_best,
        "sealed_lane": 1 if lane == "sealed" else 0,
    }


def main() -> None:
    t0 = time.time()
    path = os.environ.get("KLEIN_ARTIFACT")
    if not path:
        raise SystemExit("verify.py is run by `klein run-one`, which sets KLEIN_ARTIFACT")
    instance = json.loads(INSTANCE.read_text(encoding="utf-8"))
    try:
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise Rejected(f"the artifact is not readable JSON: {exc}") from exc
        matched, extra = check(payload, instance, os.environ.get("KLEIN_TRACK") or None)
    except Rejected as exc:
        print(f"REJECTED: {exc}")
        sys.exit(2)
    evaluate_scalar(
        float(matched),
        exp_id=os.environ.get("KLEIN_EXPERIMENT_ID", "VERIFY"),
        metric_name="optima_matched",
        metric_goal="higher",
        extra=extra,
        t0=t0,
        # study_dir is deliberately NOT passed: aux_metrics.tsv is idempotent per
        # experiment id, so a verifier writing under the run's id would erase the
        # search telemetry the run just recorded.
        study_dir=None,
    )


if __name__ == "__main__":
    main()
