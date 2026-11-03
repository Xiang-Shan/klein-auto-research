"""The declared verifier — the checker, never the searcher.

`klein run-one` runs this after search.py exits, with KLEIN_ARTIFACT pointing at the
artifact the run printed under `solution:`; the run is decided on the number THIS
script prints. It is outside `entrypoint.mutable`, hashed at the METHOD gate, and
shares no code with search.py: nothing is imported from it, and the check below is
written from the definition, not from the searcher's private checker.

It is the dumbest correct thing. Its oracle — the lanes' orders, trials, the
budget, the batch size and the OEIS optima — is PINNED below (ORACLE) and
instance.json must agree with it field by field; the lane it scores is the one the
notary judged the run on (KLEIN_EVALUATION_KIND), never the one the artifact
declares; and the artifact must name the run being verified (KLEIN_EXPERIMENT_ID).
For every (order, trial) pair of that lane the stored best ruler is re-checked from scratch with exact
integer arithmetic — exactly n integer marks, starting at 0, strictly increasing,
and all n(n-1)/2 pairwise differences distinct as a set — and it prints

  primary_metric       optima_matched: pairs whose VERIFIED best length equals the
                       optimum of OEIS A003022 for that order (pinned in ORACLE)
  first_batch_matches  llm arm: pairs whose stored FIRST proposal batch holds a valid
                       optimal ruler (re-checked here); 0 for the search arm
  invalid_best         pairs with no verified best ruler (none stored, or the stored
                       one fails the check while claiming no length); never matched
  pairs                pairs checked;  sealed_lane: 1 when the artifact is the sealed lane

Rejects (exit 2): an instance.json that disagrees with ORACLE; a missing or unknown
KLEIN_EVALUATION_KIND; an artifact whose lane is not the run's partition or whose
experiment id is not the run's; a malformed artifact (not JSON, wrong problem, an
arm other than the run's track, orders that are not the lane's, a missing or
repeated (order, trial) pair, a pair that did not spend exactly the budget — both
arms always spend all of it — an llm first batch that is not
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

#: The oracle, PINNED in this file (hashed at the METHOD gate), never read from a
#: file the searcher could rewrite: instance.json is gitignored and sits where the
#: mutable search.py has just run with write access. instance.json must agree with
#: these values exactly or nothing is scored (found at the DATA gate's review).
#: Optima: OEIS A003022 a(8..13), revision #130 (Oct 28 2026), checked 2026-11-03.
ORACLE = {
    "development_orders": [8, 9, 10, 11],
    "sealed_orders": [12, 13],
    "trials": 3,
    "budget_evaluations": 2000,
    "llm_batch": 10,
    "optima": {"8": 34, "9": 44, "10": 55, "11": 72, "12": 85, "13": 106},
}

#: Which lane a run may be scored on is decided by the partition the notary judged
#: it on (KLEIN_EVALUATION_KIND, set by `klein run-one` and `klein replicate`), never
#: by the lane the artifact declares for itself.
LANE_FOR_KIND = {"development": "development", "final_test": "sealed"}


def pinned_instance(instance: dict) -> dict:
    """The oracle, after checking instance.json agrees with it field by field."""
    for key, value in ORACLE.items():
        found = instance.get(key)
        if key == "optima":
            found = {order: (instance.get("optima") or {}).get(order) for order in value}
        if found != value:
            raise Rejected(f"instance.json {key} = {found!r} disagrees with the verifier's pinned {value!r}")
    return dict(ORACLE)


def expected_lane() -> str:
    kind = os.environ.get("KLEIN_EVALUATION_KIND")
    if kind not in LANE_FOR_KIND:
        raise Rejected(
            f"KLEIN_EVALUATION_KIND={kind!r}: the verifier must be told the partition the run was "
            "judged on (run it through `klein run-one` or `klein replicate`)"
        )
    return LANE_FOR_KIND[kind]


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
    run = os.environ.get("KLEIN_EXPERIMENT_ID")
    if run and payload.get("experiment") != run:
        raise Rejected(f"the artifact names experiment {payload.get('experiment')!r}, not the run {run!r}")
    lane = payload.get("lane")
    if lane not in ("development", "sealed"):
        raise Rejected(f"unknown lane {lane!r}")
    if lane != expected_lane():
        raise Rejected(
            f"the artifact declares the {lane} lane but the run was judged on the "
            f"{expected_lane()} partition (KLEIN_EVALUATION_KIND)"
        )
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
        if not is_int(evaluations) or evaluations != budget:
            raise Rejected(
                f"pair ({order}, {trial}): evaluations {evaluations!r} — both arms spend exactly "
                f"the budget of {budget} candidate evaluations per pair"
            )
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
    try:
        try:
            instance = json.loads(INSTANCE.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise Rejected(f"instance.json is not readable JSON: {exc}") from exc
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise Rejected(f"the artifact is not readable JSON: {exc}") from exc
        matched, extra = check(payload, pinned_instance(instance), os.environ.get("KLEIN_TRACK") or None)
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
