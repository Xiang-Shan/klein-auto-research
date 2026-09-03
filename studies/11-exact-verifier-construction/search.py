"""Search for the object the verifier will grade.

This is the per-experiment mutable surface declared in study.yaml:entrypoint.
ONE falsifiable idea per candidate; `klein run-one` commits it before it runs.

A candidate here is a CELL: which mode, and which rung of the frozen budget
ladder. Everything else — the grid size, the seed blocks, the budget values, the
control objects — comes from `data/prepared/instances.json`, which the DATA gate
hashed, and the fixed machinery lives in `lib/nothree.py`. Nothing in this file
computes the objective that enters the ledger: it writes an object, states what
it thinks that object is worth, and the declared verifier decides.

  MODE = "controls"  -> run the frozen control battery against verify.py and
                        hand the notary the known-valid object (E0001)
  MODE = "search"    -> run the iterated local search at BUDGET (E0002-E0007,
                        E0009-E0010)
  MODE = "overclaim" -> search, then report OVERCLAIM_BY more points than the
                        object actually has (E0008, on purpose)
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from kleinlib.eval import evaluate_scalar  # noqa: E402
from lib.nothree import (  # noqa: E402
    Search,
    load_instances,
    run_verifier,
    write_planted,
    write_solution,
)

# --- the cell -------------------------------------------------------------
# Every candidate names its cell here and sets the three knobs below. The base
# state committed between runs is `unassigned`, so that the surface a discard
# restores is never itself a cell: on this study EVERY run is a discard (the
# frontier is seeded at the proven maximum), so without a cell label the surface
# would return to the previous candidate's exact configuration and `run-one`
# would rightly refuse the next one as an unchanged re-execution.
CELL = "n_large@200k"        # the cell this candidate measures
MODE = "search"            # controls | search | overclaim
BUDGET = "medium"           # small | medium | large — a rung of the frozen ladder
OVERCLAIM_BY = 0           # points to add to the SEARCH's self-report, not to the object
# --------------------------------------------------------------------------

SMOKE = os.environ.get("KLEIN_SMOKE") == "1"
SEALED_DRYRUN = os.environ.get("KLEIN_SEALED_DRYRUN") == "1"
EXPERIMENT_ID = os.environ.get("KLEIN_EXPERIMENT_ID") or ("SMOKE" if SMOKE else None)
TRACK = os.environ.get("KLEIN_TRACK") or ("n_small" if SMOKE else None)


def seed_block(evaluation_kind: str) -> str:
    """Which frozen seed block this run may use — the analogue of a partition.

    `development` is the only block adaptive work may touch. `final_test`
    selects `sealed`, the block no development run has used, and that is the
    track's one sealed access. The sealed REHEARSAL
    (`klein run-one --final-test --dry-run`) must not touch it: like
    `kleinlib.data.load_partition`, it hands back the development block and
    prints `sealed_dryrun: 1` so a silent success cannot be mistaken for a pass.
    """
    if evaluation_kind not in {"development", "final_test"}:
        raise RuntimeError(f"invalid KLEIN_EVALUATION_KIND={evaluation_kind!r}")
    if evaluation_kind == "final_test" and SEALED_DRYRUN:
        print("sealed_dryrun: 1")
        return "development"
    return "sealed" if evaluation_kind == "final_test" else "development"


def block_fingerprint(track: str, n: int, block: str, seed: int) -> str:
    """What this study prints where a tabular study prints its partition hash.

    `data.split.kind` is `none`, so the DATA gate could realize no partition and
    the notary has nothing to compare against — it says so and proceeds. The
    fingerprint is printed anyway, because it is what makes each manifest carry
    a machine-readable record of WHICH seed block the run drew from: the sealed
    runs' manifests carry a different one from every development run's.
    """
    payload = json.dumps(
        {"track": track, "n": n, "block": block, "seed": seed},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def controls(instances: dict, out_dir: Path) -> tuple[list[tuple[int, int]], int, dict]:
    """Run the frozen control battery against the DECLARED verifier.

    Positive control: every planted invalid object must be REJECTED (the
    detector must fire). Negative control: the known-valid Erdos parabola set is
    handed to the notary as this cell's own artifact, so the acceptance half is
    performed by the notary's own verifier invocation rather than by this file.
    """
    positive = instances["controls"]["positive"]["objects"]
    rejected = 0
    verdicts = []
    for obj in positive:
        path = write_planted(out_dir, obj)
        proc = run_verifier(path, study_dir=".", experiment_id=EXPERIMENT_ID or "CONTROL")
        fired = proc.returncode != 0
        rejected += fired
        verdicts.append((obj["name"], proc.returncode))
        print(f"control {obj['name']}: exit={proc.returncode} {'REJECTED' if fired else 'ACCEPTED'}")
    negative = instances["controls"]["negative"]
    points = [(int(x), int(y)) for x, y in negative["points"]]
    print(f"control {negative['name']}: handed to the notary as this cell's artifact")
    return points, negative["expected_objective"], {
        "planted": float(len(positive)),
        "rejected": float(rejected),
        "verdicts": verdicts,
    }


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

    instances = load_instances(".")
    n = int(instances["instances"][TRACK]["n"])
    block = seed_block(evaluation_kind)
    seed = int(instances["seed_blocks"][block])
    budget = int(instances["budgets"][BUDGET])
    if SMOKE:
        budget = 200

    out_dir = Path("models") / ("_smoke" if SMOKE else EXPERIMENT_ID)
    out_dir.mkdir(parents=True, exist_ok=True)

    extra: dict[str, float] = {}
    search_t0 = time.perf_counter()
    if MODE == "controls":
        points, claimed, control_extra = controls(instances, out_dir)
        extra["planted"] = control_extra["planted"]
        extra["rejected"] = control_extra["rejected"]
        extra["evaluations"] = 0.0
        extra["passes"] = 0.0
        extra["best_at_evaluation"] = 0.0
    else:
        result = Search(n=n, seed=seed, budget=budget).run()
        points = result.points
        claimed = result.objective + (OVERCLAIM_BY if MODE == "overclaim" else 0)
        extra["evaluations"] = float(result.evaluations)
        extra["passes"] = float(result.passes)
        extra["best_at_evaluation"] = float(result.best_at_evaluation)
    extra["search_seconds"] = time.perf_counter() - search_t0
    extra["grid_n"] = float(n)
    extra["budget"] = float(budget)
    extra["search_seed"] = float(seed)
    extra["sealed_block"] = 1.0 if block == "sealed" else 0.0
    extra["overclaim_by"] = float(OVERCLAIM_BY if MODE == "overclaim" else 0)
    extra["claimed_objective"] = float(claimed)
    extra["object_size"] = float(len(points))

    artifact = write_solution(
        out_dir / "solution.json",
        n=n,
        points=points,
        claimed_objective=claimed,
        meta={
            "mode": MODE,
            "track": TRACK,
            "seed_block": block,
            "budget_rung": BUDGET,
            "experiment": EXPERIMENT_ID,
        },
    )
    print(f"solution: {artifact.as_posix()}")

    evaluate_scalar(
        float(claimed),
        exp_id=EXPERIMENT_ID,
        study_dir=None if SMOKE else ".",
        t0=t0,
        metric_name="points",
        metric_goal="higher",
        split_fingerprint=block_fingerprint(TRACK, n, block, seed),
        extra=extra,
    )


if __name__ == "__main__":
    main()
