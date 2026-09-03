"""Fixed machinery for the no-three-in-line search — study library code.

AGENTS.md, the experiment loop contract: library code changes rarely,
deliberately, and NEVER as part of the per-experiment diff. The per-candidate
mutable surface is `search.py`, which chooses a cell — which instance, which
budget, which mode — and calls in here. The algorithm below is fixed at the
METHOD gate and is the same on both tracks: the two tracks differ only in the
grid size they read from the DATA-gate-hashed instance file, so the pair
measures where ONE search's reach ends.

Nothing here is imported by `verify.py`, and nothing here imports it. The
checker is never the searcher.

The algorithm — iterated local search over configurations that are valid at
every instant:

* the state is a set S of points with no three collinear;
* a *pass* walks every free cell once, in an order that puts the most
  constrained cells first (a 2n configuration needs exactly two points in every
  row and every column, so cells in emptier rows and columns are the ones worth
  filling), and adds each cell that keeps S valid;
* after a pass, S is maximal for that order. If it improved on the best seen,
  it is kept; otherwise 1-3 random points are removed and the next pass tries
  again. After `restart_after` passes with no improvement the state is wiped and
  the search starts from empty.

**One evaluation is one call to `addable`** — one test of whether a specific
grid cell can join the current configuration. That is the study's budget unit,
it is what `evaluations:` prints, and it is what the registered guardrail caps.
The row/column pre-filter inside `addable` is a constant-time shortcut for a
case the direction test would reject anyway (two points already in p's row are
both in direction (1,0) from p), so it changes the cost of an evaluation but
never its answer.
"""

from __future__ import annotations

import json
import os
import random
import subprocess
import sys
from dataclasses import dataclass, field
from math import gcd
from pathlib import Path
from typing import Any

Point = tuple[int, int]


def load_instances(study_dir: str | Path = ".") -> dict[str, Any]:
    """Read the DATA-gate-hashed problem statement.

    Everything a run needs that is not a per-candidate choice lives here: the
    grid size for its track, the seed BLOCKS, the budget ladder and the
    verifier's controls. No literal seed and no literal grid size appears in
    `search.py`, in `verify.py` or in this file.
    """
    path = Path(study_dir) / "data" / "prepared" / "instances.json"
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def direction_table(n: int) -> dict[tuple[int, int], tuple[int, int]]:
    """Every grid offset mapped to its primitive direction, sign-normalized.

    Two points are on a common line through p exactly when their offsets from p
    normalize to the same primitive direction — collinearity of {p, q, r} is
    (q - p) parallel to (r - p), so testing from p's perspective catches every
    triple that contains p, which is every triple adding p could create.
    """
    table: dict[tuple[int, int], tuple[int, int]] = {}
    for dx in range(-(n - 1), n):
        for dy in range(-(n - 1), n):
            if dx == 0 and dy == 0:
                continue
            g = gcd(abs(dx), abs(dy))
            u, v = dx // g, dy // g
            if u < 0 or (u == 0 and v < 0):
                u, v = -u, -v
            table[(dx, dy)] = (u, v)
    return table


@dataclass
class SearchResult:
    """What one budgeted search produced. `points` is always valid."""

    n: int
    seed: int
    budget: int
    points: list[Point]
    evaluations: int
    passes: int
    best_at_evaluation: int
    reached_bound: bool
    trace: list[tuple[int, int]] = field(default_factory=list)

    @property
    def objective(self) -> int:
        return len(self.points)


class Search:
    """Iterated local search for a large no-three-in-line configuration.

    Deterministic in (n, seed, budget): one `random.Random(seed)` stream drives
    every choice, and the budget only says when to stop. A larger budget is
    therefore a strict extension of a smaller one — the ladder E0002 -> E0003 ->
    E0004 is one trajectory read at three points, which is why the objective
    across the ladder is monotone by construction rather than by luck.
    """

    def __init__(self, n: int, seed: int, budget: int, restart_after: int | None = None) -> None:
        self.n = n
        self.seed = seed
        self.budget = budget
        self.restart_after = restart_after if restart_after is not None else 2 * n
        self.bound = 2 * n
        self._table = direction_table(n)
        self._cells: list[Point] = [(x, y) for x in range(n) for y in range(n)]

    def _addable(self, p: Point, points: list[Point], rows: list[int], cols: list[int]) -> bool:
        """ONE evaluation: may `p` join `points` with no three collinear?"""
        if rows[p[1]] >= 2 or cols[p[0]] >= 2:
            return False
        table = self._table
        seen: set[tuple[int, int]] = set()
        px, py = p
        for qx, qy in points:
            d = table[(qx - px, qy - py)]
            if d in seen:
                return False
            seen.add(d)
        return True

    def run(self) -> SearchResult:
        rng = random.Random(self.seed)
        n = self.n
        points: list[Point] = []
        member: set[Point] = set()
        rows = [0] * n
        cols = [0] * n
        best: list[Point] = []
        best_at = 0
        evaluations = 0
        passes = 0
        stale = 0
        trace: list[tuple[int, int]] = []

        def add(p: Point) -> None:
            points.append(p)
            member.add(p)
            rows[p[1]] += 1
            cols[p[0]] += 1

        def drop(p: Point) -> None:
            points.remove(p)
            member.discard(p)
            rows[p[1]] -= 1
            cols[p[0]] -= 1

        while evaluations < self.budget:
            passes += 1
            order = self._cells[:]
            rng.shuffle(order)
            # Most-constrained-first: a 2n configuration holds exactly two
            # points in every row and every column, so the emptiest lines are
            # the ones that still have to be filled. `shuffle` first, so the
            # sort's ties break randomly and the pass order is a fresh sample.
            order.sort(key=lambda c: rows[c[1]] + cols[c[0]])
            for p in order:
                if evaluations >= self.budget:
                    break
                if p in member:
                    continue
                evaluations += 1
                if self._addable(p, points, rows, cols):
                    add(p)
            if len(points) > len(best):
                best = list(points)
                best_at = evaluations
                stale = 0
                trace.append((evaluations, len(best)))
                if len(best) >= self.bound:
                    break
            else:
                stale += 1
            if stale >= self.restart_after:
                for p in list(points):
                    drop(p)
                stale = 0
                continue
            for _ in range(min(len(points), rng.randint(1, 3))):
                drop(points[rng.randrange(len(points))])

        return SearchResult(
            n=n,
            seed=self.seed,
            budget=self.budget,
            points=sorted(best),
            evaluations=evaluations,
            passes=passes,
            best_at_evaluation=best_at,
            reached_bound=len(best) >= self.bound,
            trace=trace,
        )


def write_solution(
    path: str | Path,
    *,
    n: int,
    points: list[Point],
    claimed_objective: int,
    meta: dict[str, Any] | None = None,
) -> Path:
    """Write the artifact the declared verifier will read.

    `claimed_objective` is passed in rather than derived, because the searcher's
    self-report is exactly what the study is auditing: E0008 hands in a number
    larger than the object it wrote, and the notary has to catch it.
    """
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "problem": "no-three-in-line",
        "n": n,
        "points": [[int(x), int(y)] for x, y in points],
        "claimed_objective": int(claimed_objective),
        "meta": meta or {},
    }
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# The control battery.
#
# The controls are FROZEN in `data/prepared/instances.json` at the DATA gate,
# before the checker is ever run against them: a positive control whose planted
# defects can be softened after they fail is not a control. This helper runs the
# DECLARED verifier script itself — the same `verify.py`, in the same
# interpreter (`sys.executable` under `uv run` IS the `python` that
# `uv run --locked python -u verify.py` resolves to) — so what is tested is the
# checker the notary will use, not a copy of it.
# ---------------------------------------------------------------------------

VERIFIER_SCRIPT = "verify.py"


def run_verifier(
    artifact: str | Path,
    *,
    study_dir: str | Path = ".",
    experiment_id: str = "CONTROL",
) -> subprocess.CompletedProcess:
    """Run the declared verifier on one artifact and return the completed process.

    Exit code 0 means ACCEPTED (and the printed block carries the objective);
    a non-zero exit means REJECTED. Smoke and dry-run flags are cleared exactly
    as `klein run-one` clears them: the checker is the thing being trusted.
    """
    env = dict(os.environ)
    env["KLEIN_ARTIFACT"] = str(Path(artifact).resolve())
    env["KLEIN_EXPERIMENT_ID"] = experiment_id
    env["KLEIN_SMOKE"] = ""
    env["KLEIN_SEALED_DRYRUN"] = ""
    return subprocess.run(
        [sys.executable, "-u", VERIFIER_SCRIPT],
        cwd=str(study_dir),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def write_planted(directory: str | Path, obj: dict[str, Any]) -> Path:
    """Materialize one frozen planted object as an artifact the checker can read."""
    out = Path(directory) / f"planted_{obj['name']}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "problem": "no-three-in-line",
        "n": obj["n"],
        "points": obj["points"],
        "claimed_objective": len(obj["points"]),
        "meta": {"planted_defect": obj["defect"], "control": "positive"},
    }
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out
