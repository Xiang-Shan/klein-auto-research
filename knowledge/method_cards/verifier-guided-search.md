---
title: "Verifier-Guided Search for Mathematical Constructions"
type: method-card
domain: science
profile: [math]
status: seed
concepts: [exact-verifier, local-search, llm-proposals, matched-budget, best-known-value, golomb-rulers, found-vs-proved]
related: [README.md]
triad:
  theory: true
  papers: true
  practice: false
---

# Verifier-Guided Search for Mathematical Constructions

*Seed card (Klein 2.3) for the `math-verify` recipe — searches for objects judged by an
exact verifier, including comparisons of a language model as a proposer against a
classical search at a matched budget of verifier calls.*

## 1. Practitioner intuition

Many open problems in combinatorics ask for an object with a property — a set without
three points on a line, a ruler whose marks have all-distinct differences — that is
hard to FIND but easy to CHECK. That asymmetry is the whole method: any proposer
(random restarts, simulated annealing, a language model writing candidates, a program a
language model wrote) is acceptable, because a small exact verifier, written once and
never edited by the search, decides. FunSearch made this famous by evolving programs
with a language model and scoring them with a verifier.

What a search may claim is narrow: "found an object of value v" (pinned, re-verified),
"matched the best known", "did not reach it within budget B". Never "proved optimal",
and never "impossible" from a failure.

## 2. Math core

| Symbol | Meaning |
|---|---|
| `x` | a candidate object (e.g. a Golomb ruler: marks `0 = a_1 < … < a_n`) |
| `V(x) ∈ {valid, invalid}`, `f(x)` | the exact verifier and the objective (ruler length `a_n`) |
| `B` | the budget in verifier calls |

1. Golomb validity: all `n(n-1)/2` differences `a_j - a_i` (i < j) are distinct.
2. Success at budget B: `min_{t ≤ B, V(x_t)} f(x_t) = f*` (the known optimum, OEIS A003022).
3. Matched comparison: two proposers, the same B, success rates compared per n as
   registered cells; an exact test on success counts.

## 3. Minimal from-scratch implementation

```python
def is_golomb(marks):                      # the verifier: tiny, exact, never mutable
    diffs = [b - a for i, a in enumerate(marks) for b in marks[i + 1:]]
    return marks[0] == 0 and marks == sorted(set(marks)) and len(diffs) == len(set(diffs))
def random_search(n, length, budget, rng):
    for _ in range(budget):
        marks = [0, *sorted(rng.choice(range(1, length), n - 2, replace=False)), length]
        if is_golomb(marks): return marks
    return None
```

An LLM proposer returns candidate mark lists AS DATA (parsed, then verified) — the
model never runs code in the study.

## 4. When it pays / when it doesn't

| Regime | Expectation |
|---|---|
| small n, cheap verifier | exhaustive or random search matches the known optimum quickly |
| moderate n (12–14) | blind search success collapses; structure (constructions, backtracking) wins |
| an LLM proposing objects directly | recall of published rulers is possible — a match is not a discovery |
| an LLM proposing heuristics/programs scored over many instances | the FunSearch regime: gains need many verifier calls |

Registrable priors: classical random search matches f* for n ≤ 10 within B calls; an LLM
proposer matches f* at most n where it can reproduce a memorised ruler, and its success
on n with no memorisable answer does not exceed classical search at matched B.

## 5. References (verify at instantiation)

- Romera-Paredes et al. (2024). Mathematical discoveries from program search with large language models (FunSearch). *Nature* 625. doi:10.1038/s41586-023-06924-6
- OEIS A003022: Length of shortest (or optimal) Golomb ruler with n marks. https://oeis.org/A003022
