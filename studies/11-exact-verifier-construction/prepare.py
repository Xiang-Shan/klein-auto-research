"""Write the immutable instance file declared by study.yaml:data.prepared_path.

`data.modality` is `none`: this study reads no dataset. What it does have is a
problem statement, and that statement is what the DATA gate freezes. The file
this script writes carries, deterministically and with no randomness at all:

* the two grid sizes the two tracks search, with the pigeonhole upper bound 2n
  each and the one-line argument for it;
* the seed BLOCKS — `development`, the only block adaptive work may use, and
  `sealed`, a fresh block no development run may touch. No literal seed lives in
  search.py, verify.py or lib/ (war story 8): the entrypoint reads the block by
  name from this hashed file, chosen by KLEIN_EVALUATION_KIND;
* the registered evaluation-budget ladder;
* the verifier's two controls — one known-valid object the checker must accept
  and score at a value known in advance, and twelve planted invalid objects it
  must reject. Freezing them here, before any run, is the point: the positive
  control cannot be quietly softened after seeing whether the checker caught it.

Run it with `uv run --locked python -u prepare.py`; it is deterministic, so the
DATA gate's fingerprint is reproducible from this committed source alone.
"""

from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path

OUT = Path("data/prepared/instances.json")

#: The two instances. n_small is prime so that the Erdos parabola construction
#: below is available as the known-valid control; n_large is the same problem an
#: order of magnitude harder for a fixed evaluation budget.
N_SMALL = 11
N_LARGE = 31

#: Seed blocks. `development` is the ONLY block an adaptive run may use.
DEVELOPMENT_SEED = 20260903
SEALED_SEED = 20260917

#: The registered evaluation-budget ladder, in addability tests.
BUDGETS = {"small": 20_000, "medium": 200_000, "large": 2_000_000}

UPPER_BOUND_ARGUMENT = (
    "Three points in one row are collinear, so a no-three-in-line configuration "
    "holds at most 2 points in each of the n rows; hence at most 2n points in "
    "total. The bound is elementary and exact — it is a theorem, not a record."
)


def collinear(a: list[int], b: list[int], c: list[int]) -> bool:
    """Exact integer collinearity test (twice the signed triangle area is 0)."""
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) == 0


def parabola(p: int) -> list[list[int]]:
    """The Erdos construction: {(x, x^2 mod p)} on a p x p grid, p prime.

    No three of its p points are collinear over the integers. If three were,
    the integer determinant would vanish, hence vanish mod p; and mod p that
    determinant factors as (b-a)(c-a)(c-b), which is a unit for distinct
    a, b, c in [0, p). The construction is the study's known-valid control and
    its objective is known in advance: exactly p.
    """
    return [[x, (x * x) % p] for x in range(p)]


def parabola_plus_one(p: int) -> list[list[int]]:
    """The parabola set plus the first grid cell that breaks exactly one triple.

    The subtlest planted defect: p of the p+1 points are a published valid
    configuration, and a single added cell creates exactly one collinear triple.
    A checker that samples triples instead of enumerating them can miss this.
    """
    base = parabola(p)
    occupied = {tuple(pt) for pt in base}
    for x in range(p):
        for y in range(p):
            if (x, y) in occupied:
                continue
            candidate = [x, y]
            broken = [
                (a, b)
                for a, b in combinations(base, 2)
                if collinear(a, b, candidate)
            ]
            if len(broken) == 1:
                return base + [candidate]
    raise RuntimeError("no single-triple completion of the parabola set exists")


def planted_invalid(n: int) -> list[dict[str, object]]:
    """Twelve hand-planted objects the declared verifier must reject.

    Seven geometric defects across slopes a naive checker gets wrong, three
    well-formedness defects, one duplicate, and one 'almost valid' object.
    """
    return [
        {
            "name": "row_triple",
            "defect": "three points share a row (slope 0)",
            "n": n,
            "points": [[2, 5], [6, 5], [9, 5]],
        },
        {
            "name": "column_triple",
            "defect": "three points share a column (undefined slope)",
            "n": n,
            "points": [[4, 0], [4, 3], [4, 8]],
        },
        {
            "name": "diagonal_triple",
            "defect": "three points on a slope +1 line",
            "n": n,
            "points": [[0, 0], [3, 3], [7, 7]],
        },
        {
            "name": "antidiagonal_triple",
            "defect": "three points on a slope -1 line",
            "n": n,
            "points": [[0, 8], [2, 6], [5, 3]],
        },
        {
            "name": "slope_two_triple",
            "defect": "three points on a slope +2 line",
            "n": n,
            "points": [[0, 0], [1, 2], [2, 4]],
        },
        {
            "name": "slope_half_triple",
            "defect": "three points on a slope +1/2 line, non-adjacent lattice steps",
            "n": n,
            "points": [[0, 0], [2, 1], [4, 2]],
        },
        {
            "name": "wide_triple",
            "defect": "three points on a slope +2 line with unequal gaps (3 then 2)",
            "n": n,
            "points": [[0, 0], [3, 6], [5, 10]],
        },
        {
            "name": "duplicate_point",
            "defect": "the same lattice point listed twice — a multiset, not a set",
            "n": n,
            "points": [[1, 1], [4, 7], [1, 1]],
        },
        {
            "name": "out_of_range_high",
            "defect": f"a coordinate equal to n = {n}, one past the last column",
            "n": n,
            "points": [[0, 0], [1, 4], [n, 2]],
        },
        {
            "name": "out_of_range_negative",
            "defect": "a negative coordinate",
            "n": n,
            "points": [[0, 0], [1, 4], [3, -1]],
        },
        {
            "name": "non_integer_coordinate",
            "defect": "a coordinate that is not an integer — a lattice point that is not one",
            "n": n,
            "points": [[0, 0], [1, 4], [3.5, 2]],
        },
        {
            "name": "parabola_plus_one",
            "defect": (
                f"the {n}-point Erdos parabola set plus one cell that creates "
                "exactly one collinear triple out of the C(12,3) = 220 triples"
            ),
            "n": n,
            "points": parabola_plus_one(n),
        },
    ]


def main() -> None:
    control = parabola(N_SMALL)
    assert len({tuple(p) for p in control}) == len(control)
    assert not any(collinear(*t) for t in combinations(control, 3))

    payload = {
        "problem": "no-three-in-line",
        "statement": (
            "Place as many points as possible on the n x n integer grid "
            "{0,...,n-1}^2 so that no three of them are collinear."
        ),
        "generated_by": "prepare.py",
        "instances": {
            "n_small": {
                "n": N_SMALL,
                "upper_bound": 2 * N_SMALL,
                "upper_bound_argument": UPPER_BOUND_ARGUMENT,
            },
            "n_large": {
                "n": N_LARGE,
                "upper_bound": 2 * N_LARGE,
                "upper_bound_argument": UPPER_BOUND_ARGUMENT,
            },
        },
        "seed_blocks": {"development": DEVELOPMENT_SEED, "sealed": SEALED_SEED},
        "budgets": BUDGETS,
        "controls": {
            "negative": {
                "name": f"erdos-parabola-p{N_SMALL}",
                "role": (
                    "negative control — a known-valid object the verifier must "
                    "ACCEPT and score at a value known in advance"
                ),
                "n": N_SMALL,
                "expected_objective": N_SMALL,
                "points": control,
                "why_valid": parabola.__doc__.strip(),
            },
            "positive": {
                "role": (
                    "positive control — hand-planted invalid objects the verifier "
                    "must REJECT; the detector is supposed to fire on these"
                ),
                "count": 12,
                "objects": planted_invalid(N_SMALL),
            },
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"data source: synthetic:prepare.py -> {OUT.as_posix()}")
    print(f"instances: n_small n={N_SMALL} bound={2 * N_SMALL}; n_large n={N_LARGE} bound={2 * N_LARGE}")
    print(f"controls: 1 known-valid ({len(control)} points), {len(planted_invalid(N_SMALL))} planted invalid")


if __name__ == "__main__":
    main()
