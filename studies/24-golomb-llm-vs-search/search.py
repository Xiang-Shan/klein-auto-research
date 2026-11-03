"""The searcher (the mutable surface): two arms that propose Golomb rulers for verify.py.

A Golomb ruler with n marks is a list of integers 0 = a1 < ... < an whose pairwise
differences are all distinct; its length is an, and shorter is better. For every
(order, trial) pair of the lane this run draws, an arm gets the same budget of
candidate evaluations — ONE candidate ruler checked by this file's private
`_is_golomb` is ONE evaluation, whatever produced it — and keeps the shortest valid
ruler it found:

  search  randomized construction + simulated annealing on the mark positions
          (KLEIN_TRACK=search)
  llm     qwen-flash proposes batches of rulers as JSON DATA (never code), each
          batch told the checker's verdicts on the previous one, every request
          through the call ledger (KLEIN_TRACK=llm)

The lane is KLEIN_EVALUATION_KIND: development -> development_orders, final_test ->
sealed_orders; the sealed rehearsal (KLEIN_SEALED_DRYRUN=1) runs the development
orders and prints `sealed_dryrun: 1`. Orders, trials, budget, batch size and seed
blocks come from data/prepared/instance.json (hashed at the DATA gate). The known
optima are read for BOOK-KEEPING ONLY — the provisional count printed below and the
index of the first optimal ruler; no search decision and no prompt uses them.

The run's number is provisional: the declared verifier (verify.py — outside this
surface, sharing no code with it, hashed at METHOD) recomputes `optima_matched` and
`first_batch_matches` from the artifact printed under `solution:`, and decides.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import random
import re
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kleinlib.eval import evaluate_scalar

SMOKE = os.environ.get("KLEIN_SMOKE") == "1"
SEALED_DRYRUN = os.environ.get("KLEIN_SEALED_DRYRUN") == "1"
EXPERIMENT_ID = os.environ.get("KLEIN_EXPERIMENT_ID") or ("SMOKE" if SMOKE else None)
TRACK = os.environ.get("KLEIN_TRACK")
ARMS = ("search", "llm")

# Smoke: the first development order, one trial, a tiny budget (a shape check, not evidence).
SMOKE_BUDGET = {"search": 200, "llm": 30}

# --- the search arm -----------------------------------------------------------
SA_T0 = 1.0           # starting temperature, in units of "repeated differences"
SA_COOLING = 0.98     # per evaluation
SA_T_MIN = 0.05
SA_PATIENCE = 150     # evaluations at one target length without a valid ruler -> restart there
P_CONFLICTED = 0.85   # move a mark that takes part in a repeated difference
P_LOCAL = 0.5         # ... by a small shift (else: anywhere free on the ruler)

# --- the llm arm --------------------------------------------------------------
LLM_PARAMS = {"temperature": 0.7, "max_tokens": 1024, "enable_thinking": False}
SYSTEM_PROMPT = (
    "You propose Golomb rulers as data. A Golomb ruler with n marks is a list of n "
    "integers that starts at 0, is strictly increasing, and has all pairwise "
    "differences distinct. Its length is its last mark, and a shorter ruler is "
    "better. Reply with JSON data only: never code, never an explanation."
)


# --- the searcher's own checker (never the verifier) -----------------------------


class Budget:
    """Candidate evaluations for one (order, trial): every `_is_golomb` call spends one."""

    def __init__(self, limit: int) -> None:
        self.limit = int(limit)
        self.spent = 0

    def exhausted(self) -> bool:
        return self.spent >= self.limit

    def spend(self) -> None:
        if self.spent >= self.limit:
            raise RuntimeError(f"evaluation budget overspent ({self.limit})")
        self.spent += 1


@dataclass(frozen=True)
class Verdict:
    valid: bool
    reason: str                    # "valid", or why the candidate is not a valid ruler
    length: int | None             # the last mark, when the candidate is a well-formed mark list
    first_repeat: int | None       # the first repeated difference, pairs scanned (i < j) by j then i
    repeats: int                   # differences that repeat an earlier one
    conflicted: tuple[int, ...]    # mark indices that take part in a repeated difference


def _is_golomb(marks: Any, n: int, budget: Budget) -> Verdict:
    """The searcher's private checker. Each call is one evaluation of the budget."""
    budget.spend()
    if marks is None:
        return Verdict(False, "missing", None, None, 0, ())
    if not isinstance(marks, list) or not all(
        isinstance(m, int) and not isinstance(m, bool) for m in marks
    ):
        return Verdict(False, "not a list of integers", None, None, 0, ())
    if len(marks) != n:
        return Verdict(False, f"has {len(marks)} marks, needs {n}", None, None, 0, ())
    if marks[0] != 0:
        return Verdict(False, "does not start at 0", None, None, 0, ())
    if any(b <= a for a, b in zip(marks, marks[1:], strict=False)):
        return Verdict(False, "not strictly increasing", None, None, 0, ())
    owner: dict[int, tuple[int, int]] = {}
    repeats, first, conflicted = 0, None, set()
    for j in range(1, n):
        for i in range(j):
            d = marks[j] - marks[i]
            earlier = owner.get(d)
            if earlier is None:
                owner[d] = (i, j)
                continue
            repeats += 1
            first = d if first is None else first
            conflicted.update((i, j, *earlier))
    if repeats:
        return Verdict(False, f"difference {first} repeats", marks[-1], first, repeats,
                       tuple(sorted(conflicted)))
    return Verdict(True, "valid", marks[-1], None, 0, ())


# --- arm 1: randomized construction + simulated annealing ------------------------


def _random_ruler(n: int, length: int, rng: random.Random) -> list[int]:
    return [0, *sorted(rng.sample(range(1, length), n - 2)), length]


def _shrink(marks: list[int], step: int, rng: random.Random) -> list[int]:
    """Cut `step` empty unit cells at random: differences on one side of a cut survive."""
    marks = list(marks)
    for _ in range(step):
        occupied = set(marks)
        cut = rng.choice([c for c in range(1, marks[-1]) if c not in occupied])
        marks = [m - 1 if m > cut else m for m in marks]
    return marks


def _move(marks: list[int], verdict: Verdict, rng: random.Random) -> list[int]:
    """Relocate one interior mark (the ends 0 and L stay): the length is unchanged."""
    n, length = len(marks), marks[-1]
    interior = [i for i in verdict.conflicted if 0 < i < n - 1]
    if interior and rng.random() < P_CONFLICTED:
        i = rng.choice(interior)
    else:
        i = rng.randrange(1, n - 1)
    occupied = set(marks)
    while True:
        if rng.random() < P_LOCAL:
            p = marks[i] + rng.choice((-3, -2, -1, 1, 2, 3))
        else:
            p = rng.randrange(1, length)
        if 0 < p < length and p not in occupied:
            break
    return sorted([*marks[:i], *marks[i + 1:], p])


def search_pair(n: int, seed: int, limit: int, optimum: int) -> dict[str, Any]:
    """One (order, trial): the shortest valid ruler found within `limit` evaluations.

    Construction: n marks at random on a ruler of length n*n (sparse enough that a few
    moves make it valid). Then repeatedly: aim one length shorter than the best valid
    ruler (an adaptive step, doubling while successes come fast), start from the best
    with empty cells cut out, and anneal the interior marks to remove repeated
    differences; restart from the best after SA_PATIENCE evaluations without a valid
    ruler. Stops at the budget, or at the trivial bound n(n-1)/2 (a perfect ruler).
    """
    if n < 3:
        raise ValueError("the search arm needs at least 3 marks")
    rng = random.Random(seed)
    budget = Budget(limit)
    floor = n * (n - 1) // 2
    best: list[int] | None = None
    best_at = first_optimal_at = None
    state: list[int] | None = None
    state_verdict: Verdict | None = None
    step, since_valid, since_start, restarts = 1, 0, 0, 0
    temperature = SA_T0
    while not budget.exhausted():
        if best is not None and best[-1] <= floor:
            break  # n(n-1)/2 distinct positive differences: nothing shorter exists
        if state is None:
            if best is None:
                candidate = _random_ruler(n, n * n, rng)
            else:
                candidate = _shrink(best, min(step, best[-1] - floor), rng)
        else:
            candidate = _move(state, state_verdict, rng)
        verdict = _is_golomb(candidate, n, budget)
        since_valid += 1
        if verdict.valid:
            if best is None or candidate[-1] < best[-1]:
                best, best_at = candidate, budget.spent
                if first_optimal_at is None and candidate[-1] == optimum:
                    first_optimal_at = budget.spent
            step = min(2 * step, n) if since_valid <= n else 1
            state, state_verdict = None, None
            since_valid, since_start, temperature = 0, 0, SA_T0
            continue
        if (
            state_verdict is None
            or verdict.repeats <= state_verdict.repeats
            or rng.random() < math.exp((state_verdict.repeats - verdict.repeats) / temperature)
        ):
            state, state_verdict = candidate, verdict
        temperature = max(SA_T_MIN, temperature * SA_COOLING)
        since_start += 1
        if since_start >= SA_PATIENCE:
            state, state_verdict = None, None
            step, since_start, temperature = 1, 0, SA_T0
            restarts += 1
    return {
        "best": best,
        "best_length": None if best is None else best[-1],
        "evaluations": budget.spent,
        "best_found_at_evaluation": best_at,
        "first_optimal_evaluation": first_optimal_at,
        "restarts": restarts,
    }


def run_search(orders: list[int], trials: int, limit: int, lane_seed: int,
               optima: dict[int, int]) -> tuple[list[dict[str, Any]], dict[str, float]]:
    pairs = []
    for n in orders:
        for trial in range(trials):
            seed = lane_seed + n * 100 + trial
            pairs.append({"order": n, "trial": trial, "seed": seed,
                          **search_pair(n, seed, limit, optima[n])})
    return pairs, {"restarts": float(sum(p["restarts"] for p in pairs))}


# --- arm 2: the LLM proposes rulers as data -------------------------------------

_INNER_LIST = re.compile(r"\[[^\[\]]*\]")


def _parse_batch(text: str, batch: int) -> tuple[list[Any], bool]:
    """Exactly `batch` entries (None = missing) and whether the reply was one JSON list.

    The outermost [...] span is read as JSON (this strips code fences and any prose
    around it). A reply cut off mid-list falls back to every complete inner list.
    Nothing is repaired: an entry that is not already a valid ruler is an invalid
    evaluation, and a missing entry still spends its evaluation.
    """
    entries: list[Any] | None = None
    start, end = text.find("["), text.rfind("]")
    if start != -1 and end > start:
        try:
            value = json.loads(text[start:end + 1])
        except ValueError:
            value = None
        if isinstance(value, list):
            if value and all(isinstance(v, int) and not isinstance(v, bool) for v in value):
                value = [value]  # one bare ruler
            entries = value
    strict = entries is not None
    if entries is None:
        entries = []
        for chunk in _INNER_LIST.findall(text):
            try:
                entries.append(json.loads(chunk))
            except ValueError:
                continue
    entries = entries[:batch]
    return entries + [None] * (batch - len(entries)), strict


def _show(entry: Any) -> str:
    if entry is None:
        return "(no ruler)"
    text = json.dumps(entry)
    return text if len(text) <= 160 else text[:157] + "..."


def _describe(verdict: Verdict) -> str:
    if verdict.valid:
        return f"valid, length {verdict.length}"
    if verdict.first_repeat is not None:
        return f"invalid, length {verdict.length}, difference {verdict.first_repeat} repeats"
    return f"invalid, {verdict.reason}"


def _messages(n: int, k: int, proposals: int, batch: int,
              previous: list[tuple[Any, Verdict]] | None,
              best_length: int | None) -> list[dict[str, str]]:
    lines = [
        f"Propose exactly {batch} candidate Golomb rulers with {n} marks each.",
        f"Every ruler must start at 0, be strictly increasing, contain exactly {n} "
        f"integers, and have all {n * (n - 1) // 2} pairwise differences distinct. "
        "Shorter is better: the length of a ruler is its last mark.",
        f"This is proposal {k} of {proposals}.",
    ]
    if previous is not None:
        lines += ["", "The verifier's verdicts on your previous batch:"]
        lines += [f"{i}. {_show(entry)}: {_describe(verdict)}"
                  for i, (entry, verdict) in enumerate(previous, start=1)]
        lines.append(f"Best valid length so far: {best_length}." if best_length is not None
                     else "No valid ruler so far.")
    lines += ["", f"Reply with a JSON list of {batch} lists of integers and nothing else."]
    return [{"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "\n".join(lines)}]


class _Aborted(RuntimeError):
    """Another (order, trial) loop failed; this one stops before its next request."""


def llm_pair(ledger: Any, n: int, trial: int, limit: int, batch: int, optimum: int,
             abort: threading.Event) -> dict[str, Any]:
    """One (order, trial): `limit // batch` sequential proposals, each fed back the last."""
    budget = Budget(limit)
    proposals = limit // batch
    best: list[int] | None = None
    best_at = first_optimal = None
    first_batch: list[Any] | None = None
    previous: list[tuple[Any, Verdict]] | None = None
    valid = unparsed = 0
    for k in range(1, proposals + 1):
        if abort.is_set():
            raise _Aborted(f"order {n} trial {trial} stopped at proposal {k}")
        reply = ledger.chat(_messages(n, k, proposals, batch, previous,
                                      None if best is None else best[-1]),
                            sample=trial, **LLM_PARAMS)
        entries, strict = _parse_batch(reply, batch)
        unparsed += not strict
        verdicts = [_is_golomb(entry, n, budget) for entry in entries]
        if k == 1:
            first_batch = [entry if isinstance(entry, list) else None for entry in entries]
        for entry, verdict in zip(entries, verdicts, strict=True):
            if not verdict.valid:
                continue
            valid += 1
            if best is None or entry[-1] < best[-1]:
                best, best_at = list(entry), k
            if first_optimal is None and entry[-1] == optimum:
                first_optimal = k
        previous = list(zip(entries, verdicts, strict=True))
    return {
        "best": best,
        "best_length": None if best is None else best[-1],
        "evaluations": budget.spent,
        "proposals": proposals,
        "best_found_at_proposal": best_at,
        "first_optimal_proposal": first_optimal,
        "valid_rulers": valid,
        "unparsed_replies": unparsed,
        "first_batch": first_batch,
    }


def _smoke_reply(n: int) -> str:
    """A fenced JSON batch for KLEIN_SMOKE=1: one entry per parse/verdict path, then padding."""
    sidon = [2 ** i - 1 for i in range(n)]  # 2^j - 2^i are all distinct: a valid ruler
    batch = [
        sidon,
        [2 * m for m in sidon],             # valid, longer
        [m + 1 for m in sidon],             # does not start at 0
        list(range(0, 2 * n, 2)),           # difference 2 repeats
        sidon[:-1],                         # wrong mark count
        [0, *sidon[:0:-1]],                 # not strictly increasing
        "x",                                # not a list
    ]
    return "Here are the rulers:\n```json\n" + json.dumps(batch) + "\n```"


def run_llm(orders: list[int], trials: int, limit: int, batch: int,
            optima: dict[int, int]) -> tuple[list[dict[str, Any]], dict[str, float], dict[str, Any]]:
    from kleinlib.calls import CallLedger

    if limit % batch:
        raise SystemExit(f"budget {limit} is not a multiple of the batch {batch}")
    # The sealed rehearsal replays the development cell from the ledger and must
    # spend nothing: offline, a request the ledger cannot answer is a crash.
    overrides = {"offline": True} if SEALED_DRYRUN else {}
    jobs = [(n, trial) for n in orders for trial in range(trials)]
    abort = threading.Event()
    results: dict[tuple[int, int], dict[str, Any]] = {}
    error: BaseException | None = None
    with CallLedger.from_contract(".", smoke_response=_smoke_reply(orders[0]), **overrides) as ledger:
        # Proposals within a trial are sequential (each carries the last batch's
        # verdicts); the (order, trial) loops are independent and run side by side,
        # calls.max_workers at a time. Each loop passes its trial index as `sample`,
        # so the trials are distinct requests, not cached copies of one another.
        with ThreadPoolExecutor(max_workers=min(ledger.max_workers, len(jobs))) as pool:
            futures = {pool.submit(llm_pair, ledger, n, trial, limit, batch, optima[n], abort): (n, trial)
                       for n, trial in jobs}
            for future in as_completed(futures):
                exc = future.exception()
                if exc is None:
                    results[futures[future]] = future.result()
                elif error is None:
                    error = exc
                    abort.set()
        meta = {"model": ledger.model, "base_url": ledger.base_url, "params": LLM_PARAMS,
                "batch": batch, "proposals_per_trial": limit // batch,
                "system_prompt": SYSTEM_PROMPT}
    if error is not None:
        raise error
    pairs = [{"order": n, "trial": trial, "sample": trial, **results[(n, trial)]} for n, trial in jobs]
    extra = {
        "valid_rulers": float(sum(p["valid_rulers"] for p in pairs)),
        "unparsed_replies": float(sum(p["unparsed_replies"] for p in pairs)),
        **ledger.summary(),
    }
    return pairs, extra, meta


# --- the run ------------------------------------------------------------------


def _artifact_path() -> Path:
    if SMOKE:
        return Path(tempfile.mkdtemp(prefix="klein-smoke-")) / f"solution_SMOKE_{TRACK}.json"
    if SEALED_DRYRUN:
        # Filed with the rehearsal's own state commit (sweeps/), so the tree the
        # sealed run needs stays clean; tables/ holds only real runs' artifacts.
        return Path("sweeps") / f"solution_DRYRUN_{TRACK}.json"
    return Path("tables") / f"solution_{EXPERIMENT_ID}.json"


def main() -> None:
    t0 = time.time()
    kind = os.environ.get("KLEIN_EVALUATION_KIND") or ("development" if SMOKE else None)
    if EXPERIMENT_ID is None or kind is None or TRACK is None:
        raise SystemExit("run through `klein run-one` (or KLEIN_SMOKE=1 KLEIN_TRACK=<arm> for a shape check)")
    if TRACK not in ARMS:
        raise SystemExit(f"KLEIN_TRACK={TRACK!r}: this study's arms are {ARMS}")
    if kind not in {"development", "final_test"}:
        raise RuntimeError(f"invalid KLEIN_EVALUATION_KIND={kind!r}")
    instance = json.loads(Path("data/prepared/instance.json").read_text(encoding="utf-8"))
    lane = "sealed" if kind == "final_test" else "development"
    if kind == "final_test" and SEALED_DRYRUN:
        print("sealed_dryrun: 1")
        lane = "development"
    orders = [int(n) for n in instance[f"{lane}_orders"]]
    trials = int(instance["trials"])
    limit = int(instance["budget_evaluations"])
    batch = int(instance["llm_batch"])
    lane_seed = int(instance["seed_blocks"][lane])
    optima = {int(n): int(length) for n, length in instance["optima"].items()}
    if SMOKE:
        orders, trials, limit = orders[:1], 1, SMOKE_BUDGET[TRACK]

    payload: dict[str, Any] = {
        "problem": "golomb-ruler", "arm": TRACK, "experiment": EXPERIMENT_ID, "lane": lane,
        "sealed_dryrun": SEALED_DRYRUN, "orders": orders, "trials": trials,
        "budget_evaluations": limit,
    }
    if TRACK == "search":
        pairs, extra = run_search(orders, trials, limit, lane_seed, optima)
        payload["seed_block"] = lane_seed
    else:
        pairs, extra, payload["llm"] = run_llm(orders, trials, limit, batch, optima)
    payload["pairs"] = pairs

    matched = sum(p["best_length"] == optima[p["order"]] for p in pairs)
    first_batch = sum(p.get("first_optimal_proposal") == 1 for p in pairs)

    out = _artifact_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"solution: {out.as_posix()}")
    print(f"artifact: {out.as_posix()}")

    lane_fingerprint = hashlib.sha256(json.dumps(
        {"lane": lane, "orders": orders, "trials": trials, "budget": limit, "seed_block": lane_seed},
        sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    evaluate_scalar(
        float(matched), exp_id=EXPERIMENT_ID, metric_name="optima_matched", metric_goal="higher",
        extra={
            "first_batch_matches": float(first_batch),
            "pairs": float(len(pairs)),
            "evaluations": float(sum(p["evaluations"] for p in pairs)),
            "sealed_lane": 1.0 if lane == "sealed" else 0.0,
            **extra,
        },
        split_fingerprint=lane_fingerprint, t0=t0, study_dir=None if SMOKE else ".",
    )


if __name__ == "__main__":
    main()
