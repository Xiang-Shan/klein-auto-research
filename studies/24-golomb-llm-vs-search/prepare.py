"""Freeze the problem instance: orders, trials, budget, optima and seed blocks.

`data/prepared/instance.json` is fingerprinted at the DATA gate. It names the
development orders (the only ones adaptive work may touch), the sealed orders (one
run per arm, `klein run-one --final-test`), the trials per order, the matched budget
of candidate evaluations per (order, trial), the LLM batch size, the known optimal
lengths, and the seed block each lane may use. No literal seed lives in search.py or
verify.py (war story 8): both read this file.

Optima: OEIS A003022, "Length of shortest (or optimal) Golomb ruler with n marks",
read 2026-11-03 at revision #130 (Oct 28 2026). OEIS starts the sequence at n = 2
(offset 2); a(2..14) = 1, 3, 6, 11, 17, 25, 34, 44, 55, 72, 85, 106, 127. Order 1 has
length 0 by convention (the one-mark ruler {0}, listed in the sequence's comments);
it is not an OEIS term and no study lane uses it.
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

OPTIMA = (0, 1, 3, 6, 11, 17, 25, 34, 44, 55, 72, 85, 106, 127)  # orders 1..14

INSTANCE = {
    "problem": "golomb-ruler",
    "development_orders": [8, 9, 10, 11],
    "sealed_orders": [12, 13],
    "trials": 3,
    "budget_evaluations": 2000,
    "llm_batch": 10,
    "optima": {str(order): length for order, length in enumerate(OPTIMA, start=1)},
    "optima_source": {
        "sequence": "OEIS A003022",
        "url": "https://oeis.org/A003022",
        "checked_on": "2026-11-03",
        "revision": "#130 (Oct 28 2026)",
        "note": (
            "OEIS offset 2: orders 2-14 are the sequence's terms a(2)..a(14); order 1 "
            "(length 0, the one-mark ruler {0}) is the trivial convention, not an OEIS term"
        ),
    },
    "seed_blocks": {"development": 20261106, "sealed": 20261107},
}


def main() -> None:
    budget, batch = INSTANCE["budget_evaluations"], INSTANCE["llm_batch"]
    if budget % batch:
        raise SystemExit(f"budget_evaluations={budget} must be a multiple of llm_batch={batch}")
    out = HERE / "data" / "prepared" / "instance.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(INSTANCE, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out.relative_to(HERE).as_posix()}")
    print(json.dumps(INSTANCE, sort_keys=True))


if __name__ == "__main__":
    main()
