---
type: method-card
domain: "combinatorial geometry"
profile: "math"
status: complete
concepts: [no-three-in-line, iterated-local-search, exact-verifier]
related: []
refs_verified: true   # set true ONLY after every reference below is verified
triad:                 # the Theory + Papers + Practice contract — self-asserted, gate-checked
  theory: true         # §2 carries the notation table and the four load-bearing equations
  papers: true         # refs_verified is true: ten references, each checked on 2026-09-03
  practice: true       # §3 is the from-scratch VERIFIER, written and tested before any search ran
---

# Method card — an exact verifier for no-three-in-line, and the search it judges

> Gate 2 (METHOD). Pedagogy for an unfamiliar or frontier method, written BEFORE
> modeling. Protocol: `.claude/skills/klein/references/method-gate-protocol.md`.
> The five parts are an authoring ARC — written in order.
>
> For an `optimize` study the Practice leg is the from-scratch **verifier**, not the
> searcher (`method-gate-protocol.md` §4). That is why §3 below is `verify.py` and the
> search appears only afterwards, as the thing being judged.

## 1. Intuition (for a practitioner)

A mathematician or algorithm designer reading this will ask "who checked it?" before
"how good is it?", so start there.

**The problem.** Put as many points as you can on the n × n grid of lattice points so
that no straight line — of any slope, not just rows, columns and diagonals — passes
through three of them. Dudeney posed it in 1900 with sixteen pawns on a chessboard
(`ref:dudeney1900`): the 8 × 8 answer is 16, and 16 = 2 × 8 is not a coincidence.

**The ceiling is free.** Three points in one row are collinear, so each row holds at
most two. There are n rows. Hence **at most 2n points**, always, for every n. That is
the whole argument, it takes one line, and it is a *theorem*: no configuration, found
by any method, can ever exceed it.

**The floor is not free.** Whether 2n can be *attained* at a given n is a different
question and a hard one. Erdős's construction (`ref:roth1951`) puts n points on the
parabola `{(x, x² mod p)}` for prime p = n, and its validity is provable in three
lines; the best general construction, hyperbolas (`ref:hall1975`), reaches only
3(n−2)/2. Everything past that is computer search: Flammenkamp
(`ref:flammenkamp1992`, `ref:flammenkamp1998`) and successors have pushed 2n-point
configurations to every n ≤ 70 (`ref:flammenkamp_records`), while Guy and Kelly
(`ref:guy1968`) conjecture that for large enough n even 2n is out of reach.

**Why this problem, for a study about verifiers.** The objective is an integer — how
many points are in the set — so the checker needs no tolerance: two integers either
agree or they do not. And the check itself is trivial to write correctly and easy to
write *subtly wrong*. That combination is the whole exhibit. The analogy for anyone
who has trained a model: this is a study where the *evaluation* code is the interesting
part and the *training* code is the boring part, which is the opposite of the usual
arrangement and closer to how mathematics actually works.

**Why the checker must not be the searcher.** A search that scores itself is a witness
testifying about its own case. Klein's `optimize` contract enforces the separation
mechanically: `tracks.<id>.verifier` names a script, the script is outside
`entrypoint.mutable`, it is hashed at this gate, `klein run-one` runs it in a second
process on the artifact the search wrote, and ITS number is the one that enters the
ledger. The searcher's own claim is recorded beside it, and a disagreement larger than
the declared tolerance is a **crash**, not a result.

## 2. Math core

| Symbol | Meaning |
|---|---|
| `n` | the grid size; the point set is `G = {0,…,n−1}²` |
| `S ⊆ G` | a candidate configuration |
| `k = |S|` | the objective — the number of points, an integer |
| `p, q, r` | points of `S`, written `(x, y)` with integer coordinates |
| `p × q` | the scalar cross product `p_x q_y − p_y q_x` |
| `2n` | the pigeonhole upper bound on `k` |
| `d(p, q)` | the primitive, sign-normalized direction from `p` to `q` |
| `B` | the search budget, in **addability tests** |

**(1) Validity.** `S` is a no-three-in-line configuration exactly when

$$ \forall\, \{p,q,r\} \subseteq S,\qquad (q-p)\times(r-p) \;=\; (q_x-p_x)(r_y-p_y)-(q_y-p_y)(r_x-p_x) \;\neq\; 0 . $$

The quantity is twice the signed area of the triangle `pqr`; it is an **integer**, so
the test is exact and no rounding decision exists anywhere on the path.

**(2) The upper bound.** For every `n`, `k ≤ 2n`. Three points sharing a `y`-coordinate
are collinear, so `|S ∩ (G × {y})| ≤ 2` for each of the `n` values of `y`; summing over
`y` gives `k ≤ 2n`. (This study's `metric.bound.ideal`.)

**(3) The parabola construction.** For prime `p`, the set `P = {(x, x² mod p) : 0 ≤ x < p}`
has `|P| = p` and no three collinear. If three of its points were collinear the
integer determinant of (1) would vanish and hence vanish mod `p`; mod `p` it factors as

$$ (b-a)(c-a)(c-b) \pmod p, $$

which is a product of units for distinct `a, b, c ∈ [0, p)`. Contradiction. This is the
study's negative control: a valid object whose objective is `p`, known before any code
runs.

**(4) Adding one point.** `S ∪ {p}` is valid, given a valid `S`, exactly when no two
points of `S` share a line through `p`:

$$ q \neq r \in S \;\Longrightarrow\; d(p,q) \neq d(p,r),\qquad d(p,q) = \tfrac{q-p}{\gcd(|q_x-p_x|,\,|q_y-p_y|)}\ \text{sign-normalized}. $$

Collinearity of `{p,q,r}` is exactly `(q−p) ∥ (r−p)`, so testing from `p`'s point of
view catches every triple that contains `p` — and those are the only new triples. This
turns an `O(k²)` question into an `O(k)` one and is the search's fast path. **It is not
the checker's.**

## 3. Minimal from-scratch implementation plan — the VERIFIER

This is the Practice leg. It was written and tested before any search ran, and it is
`verify.py`, unchanged, as hashed by this gate.

```python
# verify.py — the dumbest correct checker. No sampling, no early exit that could
# hide a triple, no floating point, and nothing imported from the search.
def check(artifact_path):
    payload = json.load(open(artifact_path))            # 1. readable JSON
    assert payload["problem"] == "no-three-in-line"     # 2. the declared problem
    n = payload["n"]; assert isinstance(n, int) and n >= 1
    points = []
    for x, y in payload["points"]:                      # 3. integer lattice points
        assert isinstance(x, int) and not isinstance(x, bool)   # True is an int
        assert isinstance(y, int) and not isinstance(y, bool)
        assert 0 <= x < n and 0 <= y < n                # 4. on the grid
        points.append((x, y))
    assert len(set(points)) == len(points)              # 5. a set, not a multiset
    for a, b, c in combinations(points, 3):             # 6. EVERY triple
        assert (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0]) != 0
    claimed = payload["claimed_objective"]              # 7. the searcher's self-report
    return len(points), {"claim_excess": claimed - len(points), ...}
```

It leans on exactly one helper, `kleinlib.eval.evaluate_scalar`, to print the canonical
block the notary parses; it passes `study_dir=None` so that writing the verifier's aux
row cannot erase the search's (the aux sidecar is idempotent per experiment id).
On any failed assertion it prints `REJECTED: <reason>` and exits 2, which the notary
records as `verifier_failed`. `claim_excess` is *reported*, never punished — policing
the searcher's self-report is the notary's job, and it becomes a
`verifier_disagreement` crash at `tolerance: 0`.

Cost: `C(k,3)` integer cross products — 165 at k = 11, 1540 at k = 22, 37 820 at
k = 62. Sub-millisecond at every size in this study. **A checker has no reason to be
clever**, and every reason not to be: the planted control `parabola_plus_one` is twelve
points with exactly one broken triple out of 220, which a sampling checker would
probably pass.

### The thing being judged — `lib/nothree.py` + `search.py`

Iterated local search (`ref:lourenco2019`): local search to a maximal state, then
perturb, then repeat, keeping the best state seen.

```python
S = []                                  # always a VALID configuration
while evaluations < B:
    order = shuffle(all cells); order.sort(key=lambda c: rows[c.y] + cols[c.x])
    for p in order:                     # one pass = one greedy completion
        evaluations += 1                # ONE EVALUATION = one addability test
        if addable(p, S): S.append(p)   # equation (4), O(|S|)
    if len(S) > len(best): best = S[:]  # accept improvements only
    elif stale >= 2n:     S = []        # restart from empty
    else:                 remove 1-3 random points from S
```

The most-constrained-first ordering is the one design choice that is not generic: a 2n
configuration needs *exactly* two points in every row and every column, so the emptiest
lines are the ones still to be filled. The shuffle happens before the sort, so ties
break randomly and every pass is a fresh sample.

The whole thing is deterministic in `(n, seed, B)`: one `random.Random(seed)` stream
drives every choice and `B` only says when to stop. A larger budget is therefore a
strict extension of a smaller one, which is why the budget ladder is one trajectory
read at three points and the objective across it is monotone **by construction**, not
by luck. `search.py` — the mutable surface — chooses only the cell: which instance,
which budget, which mode. The grid sizes and the seed blocks come from the
DATA-gate-hashed `data/prepared/instances.json`, never from a literal in a script.

## 4. When it pays / when it doesn't

The regime table is keyed on grid size, because that is the only thing that varies
here. "Pays" means *reaches the proven maximum 2n*.

| Regime | Grid size | What is known about 2n there | Verdict for a budgeted ILS |
|---|---|---|---|
| toy | n ≤ 8 | attained; enumerable by hand or by brute force | pays trivially — a few hundred addability tests |
| small | 9 ≤ n ≤ 15 | attained (`ref:flammenkamp_records`, `ref:mathworld_no3`) | should pay: ILP reaches provable optima to 19×19 and a transformer matches them to 14×14 (`ref:ramanathan2025`), so the instance is not intrinsically hard — though a PPO agent in that same paper solves 10×10 and *fails* at 11×11 |
| medium | 16 ≤ n ≤ 32 | attained, but by dedicated searches (`ref:flammenkamp1992`, `ref:flammenkamp1998`) | should not pay at a fixed evaluation budget: one greedy completion costs about n² evaluations, so the SAME budget buys ≈ (31/11)² ≈ 8 times fewer restarts at n = 31 than at n = 11, against a far denser constraint set |
| large | n > 70 | not known to be attained anywhere; Guy and Kelly conjecture it is not (`ref:guy1968`) | out of scope — and the regime that makes "the search did not reach 2n" permanently uninformative about the problem |

**Falsifiable priors this card commits to** (they are the study's registered
predictions P1–P7, hashed at the consult gate before this card was written):

1. At n = 11, the ILS reaches 22 within 2 000 000 addability tests. *Could come out
   false* — the closest published comparison has a reinforcement-learning agent failing
   at exactly this size (`ref:ramanathan2025`), and this study's search is far simpler.
2. At n = 31, the same ILS at the same budget does not reach 62. *Could come out false*
   — Flammenkamp's searches did reach it, with different moves and far more compute.
3. The verifier rejects all twelve planted invalid objects and accepts the parabola set
   at exactly 11.
4. Re-running the verifier on a pinned artifact reproduces the integer exactly.
5. The notary refuses an inflated self-report rather than recording it.
6, 7. Both reach-predictions hold again from a seed block no development run has used.

**What this card explicitly declines to predict:** *how far short* the n = 31 search
lands. The card has no basis for a number there, and inventing one after the fact is
what the predictions ledger exists to prevent.

**A note on the lit-scan and the registration order.** `ref:ramanathan2025` was found
at THIS gate, after the consult gate had already hashed `study.yaml` with P1–P7 and
their magnitudes. It sharpened the *reason* to expect P1 to be interesting; it changed
no rule, and changing one here would have required a consult re-record on the record.
What it did change, lawfully, is `metric.incumbent_external` and `metric.bound.ideal`,
which were deliberately left out of the consult contract precisely so that they could
be filled from a verified reference at this gate — see the re-record and its reason.

## 5. Verified references

Ten references, in `references.yaml`, each checked on 2026-09-03 against the
publisher, arXiv or maintainer page — none quoted from memory, none marked UNVERIFIED.
`refs_verified: true`.

| key | what it is relied on for |
|---|---|
| `ref:dudeney1900` | provenance of the problem |
| `ref:roth1951` | the Erdős parabola construction — the negative control, and its proof |
| `ref:guy1968` | the conjecture that 2n is eventually unattainable — why a search failure is never evidence about the problem |
| `ref:hall1975` | the 3(n−2)/2 hyperbola construction — the constructive yardstick |
| `ref:flammenkamp1992`, `ref:flammenkamp1998` | the computational record papers |
| `ref:flammenkamp_records` | the maintained record page: 2n attained for every n ≤ 70 — the source of `metric.incumbent_external` on both tracks |
| `ref:mathworld_no3` | the independent second source: "For 2 ≤ n ≤ 32, it is possible to select 2n such points", which covers both instances |
| `ref:ramanathan2025` | the closest modern comparison (ILP / transformer / PPO on this exact problem) |
| `ref:lourenco2019` | the iterated-local-search skeleton §3 realizes |

**The consequence for the contract.** Both sources agree that at n = 11 and n = 31 the
best known value *equals* the pigeonhole bound 2n. So `metric.incumbent_external` and
`metric.bound.ideal` are the same number on each track, headroom
`h = (ideal − incumbent) / minimum_delta = 0`, and **no keep is arithmetically possible
on either track**: a keep would have to beat a theorem. This study therefore knows,
before its first run, that every run it files will be a discard — and it acknowledges
that closed door with `klein headroom ack` rather than discovering it afterwards.
Matching the value is recorded as `matched_external: true` and disclosed; it is not
counted as an improvement.
