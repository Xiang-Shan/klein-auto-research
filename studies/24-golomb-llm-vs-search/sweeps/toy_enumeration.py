"""Exhaustive enumeration at the TOY orders 5-7 — the method card's pinned computation.

What it computes. For each toy order n in (5, 6, 7) and every length L from n-1 (the
shortest strictly increasing n-mark list starting at 0) up to G(n) = OEIS A003022 a(n),
it lists EVERY candidate 0 = a_1 < a_2 < ... < a_n = L (both ends fixed, the n-2
interior marks a combination of {1..L-1}: C(L-1, n-2) candidates), checks each one
twice, and writes one row per (n, L) to `toy_enumeration.tsv` beside this file:

  valid_verify        candidates the study's declared verifier accepts
                      (`verify.golomb_length`, imported from ../verify.py unchanged)
  valid_independent   candidates an independent check accepts (a bitmask of the
                      n(n-1)/2 differences, written here, sharing no code with verify.py)

Every candidate must get the same verdict from both checks, or the script exits 1.
It also exits 1 if the shortest valid length found differs from OEIS a(n), or if any
valid ruler equals its own mirror image (equation (1) of the card says none can).

What it is NOT. It is a finite computation at orders 5-7, outside both lanes of the
study (development 8-11, sealed 12-13); it runs no search arm, reads no instance.json,
queries no model, and touches no lane order (guarded below). Deterministic and offline:
`itertools.combinations` order, no randomness, so a re-run reproduces the TSV
byte for byte.

Run from the study directory:  uv run --locked python sweeps/toy_enumeration.py
"""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from itertools import combinations
from math import comb
from pathlib import Path

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
VERIFY = STUDY / "verify.py"
OUT = HERE / "toy_enumeration.tsv"

#: OEIS A003022 a(5..7) (ref:oeis_a003022, read 2026-11-03). Toy orders only.
TOY_OPTIMA = {5: 11, 6: 17, 7: 25}
#: The study's lanes start at order 8 (instance.json / verify.py ORACLE); nothing here may reach them.
FIRST_LANE_ORDER = 8

COLUMNS = ("order", "length", "candidates", "valid_verify", "valid_independent",
           "valid_up_to_mirror", "oeis_a003022", "rulers")


def load_verifier_checker():
    spec = importlib.util.spec_from_file_location("study24_verify", VERIFY)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.golomb_length


def independent_is_golomb(marks: tuple[int, ...]) -> bool:
    """All pairwise differences distinct, via a bitmask (no set, no shared code)."""
    seen = 0
    n = len(marks)
    for j in range(1, n):
        for i in range(j):
            bit = 1 << (marks[j] - marks[i])
            if seen & bit:
                return False
            seen |= bit
    return True


def main() -> int:
    if max(TOY_OPTIMA) >= FIRST_LANE_ORDER:
        raise SystemExit("toy_enumeration.py is for toy orders only (below the study's lanes)")
    golomb_length = load_verifier_checker()
    rows: list[tuple[object, ...]] = []
    problems: list[str] = []
    total = 0
    for n, optimum in TOY_OPTIMA.items():
        shortest = None
        for length in range(n - 1, optimum + 1):
            candidates = 0
            valid_v: list[tuple[int, ...]] = []
            valid_i = 0
            for interior in combinations(range(1, length), n - 2):
                marks = (0, *interior, length)
                candidates += 1
                by_verify = golomb_length(list(marks), n) == length
                by_indep = independent_is_golomb(marks)
                if by_verify != by_indep:
                    problems.append(f"n={n} {list(marks)}: verify={by_verify} independent={by_indep}")
                if by_verify:
                    valid_v.append(marks)
                valid_i += by_indep
            if candidates != comb(length - 1, n - 2):
                problems.append(f"n={n} L={length}: {candidates} candidates, expected C({length - 1},{n - 2})")
            def mirror(r: tuple[int, ...], length: int = length) -> tuple[int, ...]:
                return tuple(length - m for m in reversed(r))

            if any(mirror(r) == r for r in valid_v):
                problems.append(f"n={n} L={length}: a ruler equals its own mirror image")
            if any(mirror(r) not in set(valid_v) for r in valid_v):
                problems.append(f"n={n} L={length}: a valid ruler's mirror image was not accepted")
            canonical = sorted({min(r, mirror(r)) for r in valid_v})
            if valid_v and shortest is None:
                shortest = length
            total += candidates
            rulers = ";".join("[" + ",".join(map(str, r)) + "]" for r in valid_v)
            rows.append((n, length, candidates, len(valid_v), valid_i, len(canonical), optimum, rulers))
        if shortest != optimum:
            problems.append(f"n={n}: shortest valid length {shortest} != OEIS a({n}) = {optimum}")

    text = "\t".join(COLUMNS) + "\n" + "".join("\t".join(map(str, r)) + "\n" for r in rows)
    OUT.write_text(text, encoding="utf-8")
    print(f"verify.py sha256 {hashlib.sha256(VERIFY.read_bytes()).hexdigest()}")
    print(f"{OUT.name} sha256 {hashlib.sha256(text.encode('utf-8')).hexdigest()}")
    print(f"candidates enumerated: {total}")
    for n, optimum in TOY_OPTIMA.items():
        shorter = sum(r[3] for r in rows if r[0] == n and r[1] < optimum)
        at = next(r for r in rows if r[0] == n and r[1] == optimum)
        print(f"n={n}: valid rulers shorter than {optimum}: {shorter}; at length {optimum}: "
              f"{at[3]} ({at[5]} up to mirror image)")
    if problems:
        for line in problems:
            print("PROBLEM:", line)
        return 1
    print("ok: both checks agree on every candidate; shortest valid length = OEIS a(n) at n = 5, 6, 7")
    return 0


if __name__ == "__main__":
    sys.exit(main())
