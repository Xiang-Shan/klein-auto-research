---
type: method-card
domain: "combinatorial search (Golomb rulers)"
profile: "math"
status: complete
concepts: [golomb-ruler, sidon-set, exact-verifier, matched-budget, recall-vs-search, simulated-annealing, llm-as-proposer, opro-style-loop, contamination]
related: [knowledge/method_cards/verifier-guided-search.md, studies/11-exact-verifier-construction/method_card.md]
refs_verified: true   # all 21 rows verified on 2026-11-03; 17 also resolved mechanically by `klein refs verify --record` (re-run after this revision)
triad:                 # the Theory + Papers + Practice contract — self-asserted, gate-checked
  theory: true         # §2: notation table + five load-bearing display equations + the known-values table
  papers: true         # refs_verified is true: 21 references, none UNVERIFIED
  practice: true       # §3: the from-scratch VERIFIER (verify.py, hardened: pinned ORACLE + lane bound to KLEIN_EVALUATION_KIND), 25 toy checks on orders 5-7 + the pinned toy enumeration sweeps/toy_enumeration.{py,tsv}; search.py realizes §3b-§3c
---

# Method card — verifier-guided search for Golomb rulers: one checker, two proposers, and the recall question

> Gate 2 (METHOD). Pedagogy written BEFORE any lane run. Protocol:
> `.claude/skills/klein/references/method-gate-protocol.md`. The five parts are an
> authoring arc and are written in order.
>
> This card describes `verify.py` at sha256 `63a60221be1a…` (the hardened verifier of
> the lead's post-review decision in `program.md`, tightened once more after the
> re-check: exact budget per pair, the artifact must name the run; the toy checks below
> ran on the previous version `f7a106592e4e…`, and `sweeps/verifier_checks.py` re-runs
> the lane, oracle, experiment and budget checks on this one), `search.py` at sha256
> `8096e1698472…`, and `data/prepared/instance.json` at sha256 `717e406cc9a9…`, all as
> found on 2026-11-03. It cites one pinned computation of its own:
> `sweeps/toy_enumeration.py` (sha256 `b851abf99152…`) and its output
> `sweeps/toy_enumeration.tsv` (sha256 `0f3b173b3cf6…`), at toy orders 5-7 only.
> No lane order (8-13) was searched or checked for a ruler, and no model was queried to
> write it. The only numbers it gives at lane orders are binomial counts from the
> tabulated `G(n)`.
>
> Revised 2026-11-03 after an adversarial review of the DATA/METHOD gates. The
> revision corrects the likelihood-ratio statement in (5), the description of the LLM
> loop's memory and parser, and the annealer's pseudocode; it pins the toy enumeration,
> documents the hardened verifier, and records the pinned model snapshot
> `qwen-flash-2025-07-28`. No registered rule changed. No card expectation changed.

## 1. Intuition (for a practitioner)

*For a mathematician or ML researcher weighing claims that an LLM found an optimal
combinatorial object.*

**Start with an exam whose answer key is printed in the textbook.** A student who
writes the right answer in the first minute has shown you they read the book. A student
who gets there after twenty crossed-out attempts may have worked it out, or may have
half-remembered it and fixed the details. The grader is a stencil: it tells right from
wrong without knowing how either student got there. This study is that exam. The
answer key is OEIS A003022 and the Wikipedia table of optimal Golomb rulers
(`ref:oeis_a003022`, `ref:wikipedia_golomb`). The stencil is `verify.py`. The two
students are a simulated-annealing search and a language model.

**The object.** A Golomb ruler is a ruler with n marks at integer positions, where
every distance between two marks shows up exactly once. With `0, 1, 4, 9, 11` you can
measure 1, 2, 3, 4, 5, 7, 8, 9, 10 and 11, each in exactly one way. That gives 5 marks
on a ruler of length 11. A pinned exhaustive enumeration checked all 210 five-mark
candidates of length 10 or less and found none valid (`sweeps/toy_enumeration.py` →
`sweeps/toy_enumeration.tsv`, §3a). That agrees with the tabulated optimum
`a(5) = 11` (`ref:oeis_a003022`). It is a finite computation at a toy order, of the
kind this study never runs at a lane order. To a number theorist this is a **finite Sidon set**, a set whose pairwise
sums are all distinct; the two definitions say the same thing (`ref:wikipedia_sidon`).
To an ML researcher it is a hash whose differences never collide. The object began as
a radio-engineering problem: pick channels so that no two pairs of transmitters share
a frequency difference (`ref:babcock1953`, `ref:bloom_golomb1977`,
`ref:atkinson1986`).

**The asymmetry is the whole method.** Checking a ruler takes n(n-1)/2 subtractions
and a duplicate test. *Finding the shortest one* is a different matter. The optimal
lengths are known only because people searched exhaustively, one order at a time:
Robinson for 12 and 13 marks (`ref:robinson1979`, `ref:robinson1983`), Shearer for 14
to 16 (`ref:shearer1990`), Dollas, Rankin and McCracken for 19 (`ref:dollas1998`), and
distributed.net's volunteers for 24 to 28, where the 27-mark stage finished in 2014
and the 28-mark stage in 2022 (`ref:distributed_net_ogr`, `ref:wikipedia_golomb`). Verifier-guided search puts
that asymmetry to work. Anything may propose: random restarts, an annealer
(`ref:kirkpatrick1983`), a language model writing candidates as data (`ref:opro2024`),
or a language model writing programs (`ref:funsearch2024`, `ref:alphaevolve2025`). One
small checker, written once and never edited by the search, decides.

**Why this exhibit needs a second idea.** A pretrained language model is not a blind
proposer. The rulers this study asks for, at orders 8 to 13, are printed in public
tables, and each is unique up to mirror image except order 11, which has two
(`ref:wikipedia_golomb`). Ask a well-read colleague for the shortest 10-mark Golomb
ruler. If they answer at once and correctly, you have learned that they read the
table, not that they can search. An ML researcher knows this as test-set
contamination: the answer key is on the web. So the study's sharpest question is not
"does the LLM match more often than the annealer?" but "**when it matches, did it
search, or did it remember?**" Its sharpest instrument is the timing of the match: was
the optimum already in the first batch, before any verifier feedback existed?

**What the study can and cannot conclude.** It can say that proposer X, at budget B,
matched the tabulated optimum in k of 12 (order, trial) pairs. It cannot say anything
new about Golomb rulers. A matched ruler is one the table already contains, and a miss
says nothing about whether a shorter ruler exists. The honest verbs are *found,
verified, matched the tabulated optimum, did not reach it within B evaluations*.

## 2. Math core

### Notation

| Symbol | Meaning |
|---|---|
| `n` | the order: the number of marks |
| `A = {a_1 < … < a_n}`, `a_1 = 0` | a candidate ruler (integers; normalized to start at 0) |
| `ℓ(A) = a_n` | its length (the objective, minimized) |
| `Δ(A)` | the multiset `{a_j − a_i : 1 ≤ i < j ≤ n}` of its n(n−1)/2 differences |
| `V(A) ∈ {0, 1}` | the verifier: 1 iff `A` is a valid n-mark Golomb ruler (equation 1) |
| `G(n)` | the optimal length, OEIS A003022 `a(n)` (`ref:oeis_a003022`) |
| `c_n` | the number of optimal rulers up to mirror image (`ref:wikipedia_golomb`) |
| `R_n(L)` | the set of n-mark candidates `0 < a_2 < … < a_{n−1} < a_n = L` |
| `B` | the budget: candidate evaluations per (order, trial), `B = 2000` |
| `b`, `K` | LLM batch size `b = 10` and proposals per trial `K = B / b = 200` |
| `T` | trials per order, `T = 3`; `τ ∈ {0, 1, 2}` indexes them |
| `O_dev`, `O_seal` | the lanes: development orders {8, 9, 10, 11}, sealed orders {12, 13} |
| `x_t` | the t-th candidate an arm submits to its own checker, `t = 1 … B` |
| `M` | `optima_matched`: pairs whose best verified ruler has length `G(n)` |
| `F` | `first_batch_matches`: LLM pairs whose first batch holds a verified length-`G(n)` ruler |
| *blind* | the null proposer of (5): each of its `b` first-batch entries is, marginally, a **uniform draw from `R_n(G(n))`**. It is told n and the target length, both ends sit at 0 and `G(n)`, and it has no other information |
| `ε_n` | the upper bound (5) on `Pr_blind[batch_1 hits]` at order n |
| `q` | `Pr_informed[batch_1 hits]`: the chance that a proposer holding the table row puts an optimal ruler in its first batch. Unknown; this study does not measure it independently |
| `Λ_n` | the likelihood ratio of a first-batch hit, informed vs blind: `q / Pr_blind[batch_1 hits]` |

### The five load-bearing equations

**(1) Validity: Golomb is the same as Sidon.**

$$ V(A)=1 \iff a_j-a_i \neq a_l-a_k \ \text{ for all pairs } (i,j)\neq(k,l),\ i<j,\ k<l \iff |\{a_j-a_i\}_{i<j}| = \binom{n}{2}. $$

The equivalence with Sidon's condition is one rearrangement:
`a_j − a_i = a_l − a_k ⟺ a_j + a_k = a_l + a_i`. Everything here is integer
arithmetic, so the check is exact and has no tolerance to choose. No ruler with n ≥ 3
marks is its own mirror image: symmetry would force `a_2 − a_1 = a_n − a_{n−1}`, a
repeated difference. So "unique up to mirror image" means exactly **two** rulers
(`2·c_n` in general).

**(2) Where G(n) lives.** The n(n−1)/2 differences are distinct positive integers no
larger than `ℓ`, which gives the trivial floor. The Erdős–Turán bound on Sidon sets
(`ref:erdos_turan1941`, statement per `ref:wikipedia_sidon`) and Singer's perfect
difference sets (`ref:singer1938`) pin the order of magnitude:

$$ \binom{n}{2} \;\le\; G(n), \qquad G(n) \;\ge\; n^2 - O\!\left(n^{3/2}\right), \qquad G(q+1) \;\le\; q^2+q \ \ \text{for every prime power } q . $$

The middle inequality: a ruler of length L is a Sidon subset of {0..L}, so
`n ≤ √(L+1) + O((L+1)^{1/4})`; solve for L. The right inequality: Singer gives q+1
residues mod `m = q²+q+1` with every nonzero residue a difference exactly once. Read
as integers in `[0, m−1]`, an integer coincidence `a − b = c − d` would also hold mod
m, so the set is a Golomb ruler of length at most `m − 1`. The bounds explain the
scale (`G(n) ≈ n²`) and nothing finer. At this study's orders the tabulated optima sit
well inside them, for example `28 ≤ G(8) = 34 < 64 = 8²`. The exact values come only
from exhaustive search.

**(3) The search space, and why optimality is expensive.** Fixing both ends,

$$ |R_n(L)| = \binom{L-1}{n-2}, \qquad \sum_{L<G(n)} |R_n(L)| \;=\; \binom{G(n)-1}{\,n-1\,}. $$

The left count is what a proposer aiming at length L faces. The right count (by the
hockey-stick identity) is what an *unpruned* certificate of optimality must rule out:
every ruler shorter than `G(n)`. Real exhaustive searches prune hard: branch-and-bound
(`ref:robinson1979`, `ref:shearer1990`), parallel distributed derivation
(`ref:dollas1998`), then volunteer computing (`ref:distributed_net_ogr`). Still, the
counts show why each new order was a separate paper.

| n | G(n) | n(n−1)/2 | n² | c_n | `|R_n(G)|` = C(G−1, n−2) | shorter candidates C(G−1, n−1) | chance per uniform draw at length G, `2c_n/|R_n(G)|` |
|---|---|---|---|---|---|---|---|
| 5 | 11 | 10 | 25 | 2 | 120 | 210 | 3.33e-02 |
| 6 | 17 | 15 | 36 | 4 | 1,820 | 4,368 | 4.40e-03 |
| 7 | 25 | 21 | 49 | 5 | 42,504 | 134,596 | 2.35e-04 |
| **8** | **34** | 28 | 64 | 1 | 1,107,568 | 4,272,048 | 1.81e-06 |
| **9** | **44** | 36 | 81 | 1 | 32,224,114 | 145,008,513 | 6.21e-08 |
| **10** | **55** | 45 | 100 | 1 | 1,040,465,790 | 5,317,936,260 | 1.92e-09 |
| **11** | **72** | 55 | 121 | 2 | 74,473,879,480 | 461,738,052,776 | 5.37e-11 |
| ***12*** | ***85*** | 66 | 144 | 1 | 2,761,025,887,620 | 18,574,174,153,080 | 7.24e-13 |
| ***13*** | ***106*** | 78 | 169 | 1 | 249,145,778,809,200 | 1,951,641,934,005,400 | 8.03e-15 |

Bold rows are the development lane; bold italic rows are the sealed lane. `G(n)` is
from `ref:oeis_a003022` and equals `instance.json` and the verifier's pinned `ORACLE`.
`c_n` is from `ref:wikipedia_golomb`; at orders 5-7 it was re-derived by the pinned
enumeration (`sweeps/toy_enumeration.tsv`, §3a). Who
established optimality: orders 12 and 13 by `ref:robinson1979` and `ref:robinson1983`
(primary); orders 8-11, per `ref:wikipedia_golomb`, by William Mixon in 1972. That
primary source was not located, so at orders 8-11 "optimal" rests on OEIS and that
secondary.

**(4) Matched-budget success, decided by the verifier alone.**

$$ s_{\text{arm}}(n,\tau) = \mathbf 1\!\left[\ \min_{\,t\le B,\ V(x_t)=1}\ \ell(x_t) \;=\; G(n)\ \right], \qquad M_{\text{arm}} = \sum_{n\in O}\ \sum_{\tau=0}^{T-1} s_{\text{arm}}(n,\tau), \qquad M \in \{0,\dots,|O|\,T\}. $$

The budget is matched in **candidate evaluations**, not wall time, tokens or calls.
Each candidate checked costs 1, whatever produced it. The annealer submits one at a
time. The LLM submits `b = 10` per request for `K = 200` requests (`K·b = B`), and a
missing or unparseable entry still spends its evaluation. The verifier enforces
`ℓ ≥ G(n)` (a verified ruler shorter than the table aborts the run: either the table
or the checker is wrong). So `s = 1` means "equal to the tabulated optimum", never
"beat it". What is deliberately **not** matched is each proposer's *prior*. The
annealer starts from a random ruler with its ends fixed at 0 and `n²` and `n − 2`
interior marks drawn without replacement from `{1, …, n² − 1}`. The LLM starts from
whatever its training data held. That unmatched prior is the confound the study exists to expose.

**(5) The recall signature and its chance baseline.**

$$ F = \sum_{n\in O}\sum_{\tau} \mathbf 1\!\left[\exists\, x \in \text{batch}_1(n,\tau):\ V(x)=1,\ \ell(x)=G(n)\right] \;\le\; M_{\text{llm}}, \qquad \Pr_{\text{blind}}\!\left[\text{batch}_1 \text{ hits}\right] \;\le\; \varepsilon_n := \frac{b\cdot 2c_n}{\binom{G(n)-1}{n-2}}, \qquad \Lambda_n = \frac{q}{\Pr_{\text{blind}}[\text{batch}_1 \text{ hits}]} \;\ge\; \frac{q}{\varepsilon_n} . $$

`F ≤ M` holds by the verifier's rules: a first-batch ruler shorter than the stored best
is rejected, and nothing verifies below `G(n)`. A first-batch optimum therefore forces
the pair's best to equal `G(n)`.

**What "blind" means.** The null hypothesis is a proposer whose `b` first-batch entries
are each, marginally, a uniform draw from `R_n(G(n))`: every n-mark candidate with ends
at 0 and `G(n)`, equally likely. The bound `ε_n` follows by the union bound over the
`2c_n` optimal rulers and the `b` entries. It needs only the uniform marginals, so it
holds whether the entries are drawn with or without replacement, and however they
depend on one another. This null is generous to chance in one respect: a truly
uninformed proposer is not told `G(n)` and would spread its draws over other lengths
and over invalid lists. In another respect it covers less than the word suggests. A
proposer that never saw the table but is biased toward structured rulers is not
"blind" in this sense, and `ε_n` says nothing about it. Examples are a construction
it half-knows, or local edits of near-rulers.

**What the bound bounds.** `ε_n` caps the *denominator* of the likelihood ratio and
nothing else. The numerator `q` is the chance that an informed proposer, one that
holds the row, shows it in batch 1. It is unknown, and the study has no independent
measurement of it. So the honest statement is the lower bound `Λ_n ≥ q / ε_n`, given
for a range of `q`:

| n | `ε_n` (blind hit bound, b = 10) | `Λ_n` if q = 0.1 | if q = 0.5 | if q = 0.9 |
|---|---|---|---|---|
| **8** | 1.81e-05 | ≥ 5.5 × 10³ | ≥ 2.8 × 10⁴ | ≥ 5.0 × 10⁴ |
| **9** | 6.21e-07 | ≥ 1.6 × 10⁵ | ≥ 8.1 × 10⁵ | ≥ 1.5 × 10⁶ |
| **10** | 1.92e-08 | ≥ 5.2 × 10⁶ | ≥ 2.6 × 10⁷ | ≥ 4.7 × 10⁷ |
| **11** | 5.37e-10 | ≥ 1.9 × 10⁸ | ≥ 9.3 × 10⁸ | ≥ 1.7 × 10⁹ |
| ***12*** | 7.24e-12 | ≥ 1.4 × 10¹⁰ | ≥ 6.9 × 10¹⁰ | ≥ 1.2 × 10¹¹ |
| ***13*** | 8.03e-14 | ≥ 1.2 × 10¹² | ≥ 6.2 × 10¹² | ≥ 1.1 × 10¹³ |

Even at q = 0.1 and the weakest lane order (n = 8), a first-batch hit is at least
5.5 × 10³ times likelier under "informed" than under "blind". The same test is nearly
worthless at the toy orders. At n = 5, `ε_5 = 0.33`, and ten independent uniform draws
hit with probability `1 − (29/30)^10 ≈ 0.29`. Against that blind proposer `Λ_5` is at
most about 3.5, whatever q is. That is one more reason toy orders are never evidence.
Two limits apply at the lane orders. First, the three trials of an order send
byte-identical first requests ("Recall versus search" below). Three first-batch hits at
one order are therefore not three independent ratios to multiply. Second, a large `Λ_n` rejects the uniform null; it does **not** name the
prior information. A remembered table row and a structured construction both pass the
test. This card knows of no classical construction that lands exactly on `G(n)` at
these orders, and is not claiming that none exists.

### Matched versus a certificate of optimality

In a minimization problem the two halves of a statement about `G(n)` have very
different costs:

- **The easy half is the upper bound.** A verified ruler of length ℓ certifies
  `G(n) ≤ ℓ`. That is all any proposer in this study can produce. (In study 11's
  maximization problem a found object was a *lower* bound; the direction flips here,
  the logic does not.)
- **The hard half is the lower bound.** `G(n) ≥ ℓ` means no ruler of length `ℓ − 1`
  exists, and it needs an exhaustive search over equation (3)'s right-hand count. This
  study runs none. Its optimality statements are always "per `ref:robinson1979`",
  "per `ref:oeis_a003022`", never its own.
- **So a match establishes nothing new about G(n).** It re-attains an upper bound
  already known to be tight. A miss establishes nothing about `G(n)` either, and
  nothing about the *class* of proposer: it describes this annealer or this model, at
  B = 2,000. Every number this study produces is a fact about the proposers, not about
  rulers.

### Recall versus search: what the instruments can and cannot separate

- **Identity is uninformative.** At orders 8, 9, 10, 12 and 13 the optimum is unique
  up to mirror image (two at order 11). A matched ruler *is* the published ruler, so
  comparing it with the table cannot tell searching from remembering.
- **Timing is informative in one direction only.** A first-batch match comes before
  any verifier feedback. By (5) it rejects the uniform *blind* null with likelihood
  ratio `Λ_n ≥ q / ε_n`: at n = 8 that is at least 5.5 × 10³, 2.8 × 10⁴ or
  5.0 × 10⁴ for q = 0.1, 0.5 or 0.9. It still does not say *which* prior information
  the model had. A *late* match is **not** evidence of search. At temperature 0.7 a
  model that emits a memorized row with probability p per sample needs about 1/p
  samples. The feedback ("difference 7 repeats") can also turn a near-recall into the
  exact row. With the arm's one-batch memory (§3c) that steering comes from the
  previous batch's verdicts and the best length so far, never from a longer history.
- **Trials are not independent draws of a fresh prompt.** The ledger's `sample` index
  is a cache key, not part of the request (`kleinlib/calls.py`). The three trials of
  one order send byte-identical first requests and differ only by sampling noise. LLM
  outcomes should therefore cluster by order, so read `M_llm` and `F` in units of
  orders (4 development, 2 sealed) as much as in units of pairs.
- **What would separate recall from search further** (SYNTHESIZE-level reading of the
  pinned artifacts and call ledger, not a registered rule): how close the first-batch
  proposals come to the tabulated ruler (shared marks), and whether the eventual match
  arrives through a chain of single-mark edits of earlier proposals (search-like) or
  appears de novo (recall-like).

## 3. Minimal from-scratch implementation plan

This is an `optimize`-shaped instrument inside a `test` study: two registered arms
judged by one declared verifier. Per the protocol (§4), **the Practice leg is the
from-scratch verifier, written and tested before any search runs**. The checker is
never the searcher. `search.py` realizes §3b-§3c and is the mutable surface.
`verify.py` is outside it, shares no code with it, and is hashed by this gate.

### 3a. The verifier — `verify.py` (the dumbest correct check)

```python
def golomb_length(marks, n):                 # equation (1), from the definition
    if not isinstance(marks, list) or len(marks) != n: return None
    if any(not is_int(m) for m in marks): return None        # bool is not an int here
    if marks[0] != 0: return None
    if any(marks[i] <= marks[i-1] for i in range(1, n)): return None
    diffs = [marks[j] - marks[i] for i in range(n) for j in range(i+1, n)]
    return marks[-1] if len(set(diffs)) == len(diffs) else None   # ALL n(n-1)/2, no early exit

ORACLE = {"development_orders": [8, 9, 10, 11], "sealed_orders": [12, 13], "trials": 3,
          "budget_evaluations": 2000, "llm_batch": 10,
          "optima": {8: 34, 9: 44, 10: 55, 11: 72, 12: 85, 13: 106}}   # PINNED in verify.py
LANE_FOR_KIND = {"development": "development", "final_test": "sealed"}

def pinned_instance(instance):               # instance.json must agree field by field ...
    for key, value in ORACLE.items():
        if instance[key] != value: reject("instance.json disagrees with the pinned oracle")
    return ORACLE                            # ... and only the pinned values are scored

def check(payload, oracle, track):
    kind = os.environ.get("KLEIN_EVALUATION_KIND")     # set by klein run-one / klein replicate
    if kind not in LANE_FOR_KIND: reject("the verifier must be told the partition")
    if payload["lane"] != LANE_FOR_KIND[kind]: reject("artifact lane != judged partition")
    G = oracle["optima"]                              # the PINNED optima, never instance.json's
    # arm == track; orders == the lane's; every (order, trial) exactly once;
    # 0 <= evaluations <= budget for each pair
    for pair in payload["pairs"]:
        length = golomb_length(pair["best"], pair["order"])
        assert pair["best_length"] == length          # the searcher's claim must equal the check
        assert length is None or length >= G[pair["order"]]   # below the table => table or checker wrong
        M += (length == G[order])
        if arm == "llm":                              # recall signature, equation (5)
            first = [golomb_length(x, order) for x in pair["first_batch"]]   # exactly b entries
            assert not any(v is not None and (length is None or v < length) for v in first)
            F += G[order] in first
    print_block(primary_metric=M, first_batch_matches=F, invalid_best=..., pairs=..., sealed_lane=...)

# main():  check(json.load($KLEIN_ARTIFACT), pinned_instance(json.load("instance.json")), $KLEIN_TRACK)
```

Any failed assertion prints `REJECTED: <reason>` and exits 2, so the run is a crash
and never a number.

**Why the oracle and the lane live inside the verifier (the hardening).** Two
holes were found at the DATA/METHOD review and closed by the lead (`program.md`,
"Lead decisions after the DATA/METHOD review"):

- *The goalposts were in a writable file.* `instance.json` is gitignored (`data/`) and
  sits where `search.py`, the mutable surface, has just run with write access. A
  searcher that rewrote an optimum or the budget would have changed what the verifier
  scored against. Now the verifier carries its own **pinned `ORACLE`**: lane orders,
  trials, budget, batch size, and the OEIS optima for orders 8-13 (revision #130,
  checked 2026-11-03). It refuses an `instance.json` that disagrees with any field,
  and it scores only against the pinned values. Because the oracle is in `verify.py`,
  this gate's hash of `verify.py` pins the goalposts too.
- *The artifact named its own lane.* A development artifact could have been scored as
  the sealed lane, or the reverse. Now the lane must equal the partition the notary
  judged the run on. That partition is `KLEIN_EVALUATION_KIND` (development →
  development lane, final_test → sealed lane). `klein run-one` passes it to every
  declared verifier (framework fix "verifiers see the evaluation kind", `d2d78f7` on
  this branch, `fcadacf` in `program.md`), and `klein replicate` already did. A
  missing or unknown kind is a rejection, not a default.

The block is printed by `kleinlib.eval.evaluate_scalar` with
`study_dir=None`, so the verifier's aux row cannot overwrite the searcher's (the aux
sidecar is idempotent per experiment id). The verifier's `wall_seconds` is its own,
and the declared `wall_seconds` guardrail checks the verifier, not the search.

**Exercised before any lane run, on toy orders only (2026-11-03, this gate, re-run on
the hardened `verify.py` at `f7a106592e4e…`).** I ran the checks below by importing
`verify.check` with a toy `instance` dict of orders 5-7 and the stated
`KLEIN_EVALUATION_KIND`. The oracle rows call `verify.pinned_instance` on the real
`instance.json` and on doctored copies of it: they compare dicts and check no ruler.
No lane order was searched or checked for a ruler. All 25 checks behaved as expected:
the 11 artifact checks, 5 lane-binding checks, 7 oracle checks and 2 subprocess exit
checks in the table. They ran from a scratch harness, not filed in the study. The
first row is pinned instead as a re-runnable artifact, the enumeration. Run
`uv run --locked python sweeps/toy_enumeration.py` from the study directory; it is
deterministic, offline, toy orders only, and rewrites `sweeps/toy_enumeration.tsv`
byte for byte (sha256 `0f3b173b3cf6…`).

| Test | Expected | Observed |
|---|---|---|
| **Pinned:** exhaustive enumeration at n = 5, 6, 7 (`sweeps/toy_enumeration.py`), every candidate of every length up to G(n), checked by the verifier's own `golomb_length` AND an independent bitmask check | both checks agree on every candidate; none valid shorter than G(n); 2, 4, 5 optimal rulers up to mirror image | 183,618 candidates, 0 disagreements; 0 valid shorter than 11, 17, 25; 4, 8, 10 valid rulers at G(n) = 2, 4, 5 mirror pairs, matching `ref:wikipedia_golomb` and `ref:oeis_a003022` a(5..7) (`sweeps/toy_enumeration.tsv`) |
| clean artifact, all three toy orders optimal | accept, M = 3 | accept, M = 3, F = 0 |
| valid but long ruler (n = 5, length 12), honest claim | accept, not matched | accept, M = 2 |
| invalid ruler claiming length 11 | reject | reject: stored ruler fails the check |
| valid ruler, claimed length ≠ verified | reject | reject |
| evaluations = 2001 > B | reject | reject |
| a missing (order, trial) pair | reject | reject |
| a `True` among the marks | reject | reject |
| LLM first batch holds the optimum | accept, F = 1 | accept, F = 1 |
| LLM first batch shorter than stored best ("lost its best") | reject | reject |
| artifact arm ≠ run track | reject | reject |
| doctored table (G(5) set to 12) against a real length-11 ruler | reject as below the table | reject: "the table or this checker is wrong" |
| development-lane artifact, `KLEIN_EVALUATION_KIND=final_test` | reject | reject: "declares the development lane but the run was judged on the sealed partition" |
| sealed-lane artifact, `KLEIN_EVALUATION_KIND=development` | reject | reject (the mirror case) |
| sealed-lane artifact, `KLEIN_EVALUATION_KIND=final_test` | accept | accept |
| `KLEIN_EVALUATION_KIND` unset, or an unknown value | reject | reject: "the verifier must be told the partition the run was judged on" |
| real `instance.json` against the pinned `ORACLE` | agree | agree |
| doctored copies: a(8) = 35; budget 2,001; sealed orders [12]; trials 1; batch 20; a(13) missing | reject each | reject each: "disagrees with the verifier's pinned …" |
| `verify.py` as a subprocess (`main()`), kind unset; kind `development` with a toy artifact | exit 2 | exit 2 with `REJECTED:` both times (the toy orders are not the pinned development orders) |

### 3b. The search arm — randomized construction + fixed-length annealing (`search.py`, `KLEIN_TRACK=search`)

This is a design in the same **feasibility-first family** as `ref:dotu2005`, not their
algorithm. Theirs is a hybrid evolutionary algorithm that, per its abstract, "focuses on
feasibility, finding near-optimal rulers indirectly". This one is a single-trajectory
annealer with restarts and no population. What the two share, as far as the abstract
says, is the feasibility-first framing: work on making a ruler valid rather than on
its length directly. Here that means fix a target length, move interior marks until
the ruler is valid, then shrink the target and repeat.

```python
floor = n*(n-1)//2                                        # n(n-1)/2 distinct positive differences
best = None; state = None; T0 = 1.0; T = T0; step = 1
while budget.spent < B and not (best and ℓ(best) <= floor):   # every _is_golomb call spends 1
    if state is None:                                     # (re)start
        if best is None:                                  # construction: BOTH ends fixed
            cand = [0] + sorted(rng.sample(range(1, n*n), n - 2)) + [n*n]
        else:                                             # aim shorter
            cand = best with min(step, ℓ(best) - floor) empty unit cells cut out
    else:                                                 # a move: ends stay, length unchanged
        cand = state with one interior mark relocated
               (which mark: 85% one in a repeated difference, else any interior mark;
                where to:   50% shift by ±1..3, else anywhere free in (0, ℓ))
    v = _is_golomb(cand)                                  # energy E = number of repeated differences
    if v.valid:                                           # always shorter than best: shrinks and
        best = cand                                       #   length-preserving moves only
        step = min(2*step, n) if it came within n evaluations of the last valid one else 1
        state = None; T = T0                              # T RESETS to 1.0; no cooling step here
        continue
    if state is None or E(v) <= E(state) or rand() < exp((E(state) - E(v)) / T):
        state = cand                                      # Metropolis acceptance (ref:kirkpatrick1983)
    T = max(0.05, 0.98 * T)                               # cooling happens ONLY after an invalid candidate
    if 150 invalid evaluations since the last (re)start:
        state = None; step = 1; T = T0                    # restart from best (or a fresh n² ruler)
```

Seeds come from `instance.json`'s lane seed block (`seed_block + 100·n + τ`), never a
literal. The table optima enter only the bookkeeping fields
(`first_optimal_evaluation`); no search decision reads them. I checked this by reading
`search_pair`. The only theory it uses is the floor `n(n−1)/2` as a stopping rule.
At every order this study touches (5-13), `G(n)` exceeds it, so the rule never fires.
Two consequences of the schedule are worth knowing. First, the temperature anneals
only during an unbroken run of invalid candidates. Each valid ruler and each restart
puts it back to 1.0. Within one 150-evaluation window it falls as `0.98^k` and reaches
the 0.05 floor only at about the 149th invalid evaluation (`0.98^148 ≈ 0.050`), just
before the restart. Second, a restart before any valid ruler exists draws a fresh
random `n²` ruler, and a restart after one exists shrinks the best by one unit.

**Toy calibration (orders 5-7 only, seeds 1-20, outside both lane seed blocks,
B = 2,000).** This is a behaviour check, not evidence about any lane: it was run so
the regime table below rests on something observed rather than guessed.

| n | matched G(n) | best lengths | evaluation of first optimal ruler |
|---|---|---|---|
| 5 | 20 / 20 | all 11 | 20 – 341 |
| 6 | 20 / 20 | all 17 | 68 – 1,142 |
| 7 | 9 / 20 | 25 ×9, 26 ×4, 27 ×7 | 437 – 1,868 |

The budget already binds at n = 7: the successful runs found the optimum late. From
n = 7 to n = 8, `|R_n(G)|` grows 26-fold (42,504 → 1,107,568) while the number of
optimal rulers falls from 10 to 2, so the uniform chance per draw falls about
130-fold.

### 3c. The LLM arm — an OPRO-style loop with a one-batch memory, objects as data (`search.py`, `KLEIN_TRACK=llm`)

The model is **`qwen-flash-2025-07-28`**, the dated snapshot pinned in
`study.yaml:calls.model` (lead decision in `program.md`). It replaced the `qwen-flash`
alias, which the provider can repoint. Requests go to DashScope's OpenAI-compatible
endpoint, and every one passes through the call ledger.

```python
previous = None; best = None
for k in 1..K:                                            # K = 200 sequential requests per (n, τ)
    msgs = system("propose Golomb rulers as data ... JSON data only: never code")
         + user(n, b, "proposal k of K",
                if k > 1: the PREVIOUS batch only, one line "i. <entry>: <verdict>" per entry
                          (entry as JSON, cut at 160 chars, or "(no ruler)"; verdict
                           "valid, length 41" | "invalid, length 40, difference 7 repeats"
                           | "invalid, <reason>", e.g. "invalid, missing"),
                          and "Best valid length so far: ℓ" (or "No valid ruler so far."))
                                                          # never the optimum, never older batches
    reply = ledger.chat(msgs, sample=τ, temperature=0.7, max_tokens=1024, enable_thinking=False)
                                                          # model = calls.model = qwen-flash-2025-07-28
    entries, strict = parse_batch(reply, b)               # exactly b entries; None = missing
    verdicts = [_is_golomb(e) for e in entries]           # b evaluations spent: valid, invalid,
                                                          #   missing and duplicate entries alike
    best = shortest valid among best and entries
    if k == 1:                                            # stored for the verifier's F
        first_batch = [e if isinstance(e, list) else None for e in entries]
    previous = list(zip(entries, verdicts))               # the ONLY memory carried to request k+1

def parse_batch(text, b):                                 # lenient EXTRACTION, strict VALIDATION
    span = text[text.find("[") : text.rfind("]") + 1]    # strips code fences and prose around it
    value = json.loads(span) if span parses else None
    if value is a non-empty list of plain ints:
        value = [value]                                   # one bare ruler -> one entry
    if isinstance(value, list):
        entries, strict = value, True
    else:                                                 # outer span not valid JSON: a reply cut off
        entries = [json.loads(s) for s in re.findall(r"\[[^\[\]]*\]", text)   # mid-list, or prose
                   if s parses]                           #   between lists -> every complete
        strict = False                                    #   innermost [...] that parses
    return entries[:b] + [None] * (b - len(entries)), strict
```

**The parser extracts leniently and validates strictly. No ruler is repaired.** The
fallback only decides which bracketed spans count as entries. In the strict path, the
entries are the outer list's elements, of any type. In the fallback path, they are
every complete innermost `[...]` that parses as JSON. A bare list of integers is
wrapped as one entry, and the remaining `b − 1` slots are missing. Extra entries
beyond `b` are dropped, and missing ones become `None`. Each entry then faces
`_is_golomb` exactly as written. Nothing is sorted, shifted to start at 0, deduplicated,
coerced from a float or string, or completed. An entry that is not already a valid
ruler is an invalid evaluation, and a missing entry still spends its evaluation. The
`strict` flag feeds only the `unparsed_replies` telemetry; it changes no verdict. The
first batch is stored the way the verifier needs it: exactly `b` entries, lists
verbatim (valid or not, even `[0.0, 1, 4, 9, 11]`), and non-list entries (a string, a
number, an object, an empty slot) as `None`. I checked this reading on eleven
hand-written toy replies at n = 5, covering a list of lists, a bare list, a fenced
block, a truncated list, prose between lists, mixed types, an empty list, no brackets,
12 entries, a shifted ruler and an unsorted ruler. I called `_parse_batch` and
`_is_golomb` directly, with no ledger and no model.

**The loop is OPRO-style with a one-batch memory, not OPRO's loop.** OPRO
(`ref:opro2024`) generates new solutions "from the prompt that contains previously
generated solutions with their values". The new ones are scored and *added* to that
prompt, so its meta-prompt is a growing scored history. `search.py` sends back only
the **previous batch** with the checker's verdicts and the best valid length so far.
Every earlier batch is forgotten except through that single number. The model
therefore cannot read a ranked trajectory and extrapolate from it. Any search-like
improvement must come from one-step edits of the last batch, plus resampling. It is
also not `ref:funsearch2024`'s loop, which evolves programs. The (order, trial) loops
run side by side on `calls.max_workers` threads, and proposals within one loop are
sequential.

### 3d. kleinlib helpers this plan leans on

- **`kleinlib.eval.evaluate_scalar`**: prints the canonical metric block for both the
  searcher's provisional count and the verifier's deciding count, plus
  `wall_seconds` and the `extra={...}` keys (`first_batch_matches`, `pairs`,
  `evaluations`, …) the P3 rule reads.
- **`kleinlib.calls.CallLedger`**: every LLM request and response is pinned under
  `calls/`, keyed on the request payload, including the model id
  `qwen-flash-2025-07-28`, plus the `sample` index. The sealed dry run is forced
  offline (a request the ledger cannot answer crashes), and `klein replicate --replay`
  re-verifies the LLM cells with no network. `budget_calls` is a per-run cap: 2,400
  requests for the development cell (4 orders × 3 trials × 200) and 1,200 for the
  sealed cell.
- **Not used, deliberately**: `kleinlib.torch_loop` (nothing is trained) and
  `kleinlib.encoders` (there are no features). The near-constant and non-finite
  prediction diagnostics in `kleinlib.eval` concern prediction vectors; a single
  integer count has none, so the verifier's exactness (`tolerance: 0`, resolution 1)
  stands in for them.

## 4. When it pays / when it doesn't

"Pays" means *matches the tabulated optimum within B = 2,000 candidate evaluations*.
The two axes are size (order n and the space at `G(n)`, equation 3) and signal, which
here means whether the answer is public, i.e. memorizable, and how much budget there
is relative to the space. Doctrine anchor (`references/profiles/math.md` §3): the
verifier is the only judge; a construction is evidence; a search failure is never
evidence of impossibility.

| Regime | Size: n; `|R_n(G)|` | Signal: is the answer public? | Annealer at B = 2,000 | Pretrained LLM proposing objects at B = 2,000 | Verdict |
|---|---|---|---|---|---|
| toy | n ≤ 7; ≤ 4.3 × 10⁴ | yes, and several optima per order | pays (toy check: 20/20, 20/20, 9/20) | a match is cheap either way | the verifier's test bed, never evidence |
| development | n = 8–11; 1.1 × 10⁶ – 7.4 × 10¹⁰ | yes: one or two optima, printed in public tables | expected not to pay at this budget; a feasibility-first hybrid evolutionary algorithm "quickly finds optimal rulers with up to 11 marks" (`ref:dotu2005`), at a budget its abstract states in time, not evaluations | pays only through recall, exact to the integer; a first-batch match rejects the uniform blind null (`Λ_8 ≥ 5.5 × 10³` even at q = 0.1, equation 5) without naming the prior | the study's contrast lane |
| sealed | n = 12–13; 2.8 × 10¹² – 2.5 × 10¹⁴ | yes: one optimum each (`ref:robinson1979`, `ref:robinson1983`) | does not pay | pays only by exact recall of a 12- or 13-integer row | a recall probe with a longer string |
| tabulated, large | n = 14–28 | yes (`ref:shearer1990`, `ref:dollas1998`, OGR-24…28) | does not pay | recall only | a match is a table lookup |
| open | n ≥ 29 | no tabulated optimum: OEIS stops at a(28) = 585 | — | — | "matched" is undefined; only "found a ruler of length ℓ", an upper bound |

The method family, positioned by *what the language model emits*. That decides
whether recall can explain a result:

| Proposer | The model emits | Can recall of a table explain a match? | Where it pays |
|---|---|---|---|
| table lookup (the limiting case) | the row | entirely: B = 1, every tabulated order, zero search | never a discovery |
| OPRO-style, objects as data (`ref:opro2024`; **this study's LLM arm**, with a one-batch memory) | the object itself | yes, directly: the output is a table entry | small objects, cheap verifier, a scored history worth reading (OPRO's prompt accumulates one; this arm's holds only the last batch); weakest for discovery claims on tabulated objects |
| FunSearch (`ref:funsearch2024`) | a program that builds the object, scored by an evaluator | less directly: a program can hard-code a row, but it is scored on what it constructs | open problems with no table to recall (cap sets, bin-packing heuristics) |
| AlphaEvolve (`ref:alphaevolve2025`, `ref:georgiev2025`) | edits to a codebase, from an evolutionary database, multiple evaluators | as FunSearch | broad problem lists; Georgiev et al. report "rediscovered" and "improved" separately across 67 problems |
| PatternBoost (`ref:patternboost2024`) | samples from a transformer trained *from scratch* on local-search outputs | no: the model never saw a table | removes the confound by construction |
| classical heuristics (`ref:kirkpatrick1983`, `ref:dotu2005`) and constructions (`ref:singer1938`, `ref:atkinson1986`) | — | no | near-optimal rulers at sizes no exhaustive search reaches |

**Frontier lit-scan, positioned honestly.** The seminal paper for LLM-guided
verifier search is FunSearch (`ref:funsearch2024`). Its key follow-ups are AlphaEvolve
(`ref:alphaevolve2025`) and its at-scale mathematical application by Georgiev,
Gómez-Serrano, Tao and Wagner (`ref:georgiev2025`), the resonant application in this
field. The trend is *away* from what this study's LLM arm does. The frontier systems
evolve programs, against evaluators, over problems without a public answer key, and
the best of them report rediscovery and improvement as different outcomes. This
study's arm proposes objects as data on problems whose answers are tabulated. That
makes it a weak test of discovery and a **good test of contamination**, which is the
question it registers. Memorization research says why the outcome is not foregone.
Memorization grows with model capacity, with how often an example is duplicated, and
with prompt context (`ref:carlini2023`). Optimal-ruler rows are short and reproduced across
Wikipedia, its mirrors and the tables OEIS links, which favours recall. The pinned model,
`qwen-flash-2025-07-28`, is a flash-tier snapshot. This card found no official
parameter count: a WebSearch on 2026-11-03 found that the provider's Model Studio
listing for its US twin gives context length and pricing only. Run with thinking
disabled, a short prompt and a one-batch memory, it points the other way. My literature scan (two WebSearch queries: LLMs on
Golomb rulers; AlphaEvolve on Golomb rulers or Sidon sets) found **no** paper applying
an LLM proposer to Golomb rulers. The classical evolutionary and local-search
literature is large. A two-query scan finding nothing is not evidence that nothing
exists.

**A correction to a CONSULT-time source note (no rule changes).** RQ2's prior says
optimal rulers are "tabulated on Wikipedia and in OEIS" up to order 27. That is stale
by one order. OEIS now lists `a(2..28)` with `a(28) = 585` credited to OGR-28
(`ref:oeis_a003022`), and the Wikipedia table prints the rulers themselves through
order 28, with OGR-28 completed 2022-11-23 (`ref:wikipedia_golomb`). OEIS lists
lengths; the rulers are in Wikipedia's table and the tables OEIS links. The
consequence for the study is unchanged, and if anything stronger: every lane order's
answer is public.

### Falsifiable priors this study will test

The study's registered predictions P1–P5 were hashed at the CONSULT gate, and their
rules are not this card's to change. `study.yaml` carries `predictions:`, and the
contract refuses `predictions_to_falsify:` beside it (`kleinlib/contract.py`). So the
card stakes its claims in two layers. **(a)** For each registered prediction, the
card's expectation, with a probability and the reason. **(b)** Sharper card-level
priors, each naming a lever, a direction and a magnitude in stated units. SYNTHESIZE
can check each one against the pinned artifacts (`tables/solution_E####.json`: per
pair `best_length`, `first_optimal_*`, `first_batch`). They are not notary rules. All
probabilities are the method scholar's judgment from §2–§3 and the literature. No
order 8–13 was searched and no model was queried to form them.

**(a) Expectations for the registered predictions**

| ID | Rule | Card expects | P(rule holds) | Why |
|---|---|---|---|---|
| P1 | search, dev: `optima_matched ≤ 6` (of 12) | **holds**; point expectation 0–2 of 12, any match at order 8 | 0.95 | The budget already binds at n = 7 (9/20, first hits at 437–1,868 of 2,000). At n = 8 the per-draw chance at length G is about 130× smaller, and it falls by a further 29× to 36× per order through 11. Reaching 6 would need, for example, every trial of two orders. |
| P2 | llm, dev: `optima_matched ≥ 9` (of 12) | **falsified**; point expectation 3–6 of 12 | 0.30 | A match needs exact recall of 8–11 integers. Order 8's row is the shortest single-optimum row and plausibly the likeliest to be recalled. Rows 10 and 11 are less so, and order 11 has two optima, which helps a little. Feedback can repair a near-recall, which raises the count above first-batch recall alone. That repair works from the last batch's verdicts only (one-batch memory, §3c). |
| P3 | llm, dev: `first_batch_matches ≥ 6` | **falsified** | 0.25 | Identical first prompts across trials mean it effectively needs two orders recalled at the first attempt. By (5), F ≤ M, so P3 also needs M ≥ 6. Conditional on P2 holding: P(P3) ≈ 0.7, because a model that knows the table tends to show it at once. |
| P4 | search, sealed: `optima_matched ≤ 0` (of 6) | **holds** | 0.97 | 2.8 × 10¹² and 2.5 × 10¹⁴ candidates at length G, each with exactly two optimal rulers, at B = 2,000. A failure of P4 would itself be a finding that needs scrutiny before belief. |
| P5 | llm, sealed: `optima_matched ≥ 3` (of 6) | **falsified** | 0.15 | Needs exact recall of a 12- or 13-integer row in at least 3 trials. The development lane tests the same mechanism more cheaply: if dev F ≤ 2, P5 is unlikely. |

**(b) Card-level priors (unit-bearing, falsifiable, checked by SYNTHESIZE from the
artifacts)**

- **C1. The annealer's ceiling.** Search arm, development lane: `M_search ≤ 2` of 12
  (order, trial) pairs, and **0** matches at orders 10 and 11. *Falsified* if
  `M_search ≥ 3`, or if any order-10 or order-11 pair matches.
- **C2. The annealer's gap grows with order.** Per-order mean of
  `best_length − G(n)` over the 3 trials, in length units: non-decreasing from n = 8
  to n = 11, and at least 3 units at n = 11. *Falsified* if any order's mean gap is
  below a lower order's, or if the n = 11 mean gap is under 3 units.
- **C3. LLM outcomes cluster by order.** In at least 3 of the 4 development orders,
  all 3 LLM trials agree (all matched or none). *Falsified* if two or more orders
  split 1–2 or 2–1.
- **C4. Recall dominates the LLM's matches.** If `M_llm ≥ 1` on the development lane,
  then `F ≥ M_llm / 2` (at least half of the LLM's matched pairs were already optimal
  in batch 1). *Falsified* if `F < M_llm / 2`.
- **C5. At matched budget the LLM is not behind.** Development lane:
  `M_llm − M_search ≥ 0` pairs. *Falsified* if the annealer matches more pairs than
  the LLM. Read together with C4: a positive Δ that is mostly first-batch is
  contamination evidence, not evidence of a better searcher.

**What the card declines to predict.** How long the LLM's best ruler is at orders it
does not recall, and the fraction of its proposals that are valid rulers. The card has
no basis for either number, and inventing one after the fact is what the predictions
ledger exists to prevent.

## 5. Verified references

Twenty-one references, in `references.yaml`, each checked on 2026-11-03 against a
primary record and none cited from memory. DOIs were checked at Crossref, with
abstracts read from OpenAlex wherever one is deposited. arXiv ids were checked on the
arxiv.org abstract page and through OpenAlex's record of the `10.48550/arXiv.<id>` DOI.
Four web pages were fetched and read directly. `klein refs verify --record` then
resolved all 17 DOI/arXiv locators with matching titles (0 failed) and recorded
`resolved_by`, `resolved_title` and `resolved_at`. The 4 URL-only rows
(`oeis_a003022`, `wikipedia_golomb`, `distributed_net_ogr`, `wikipedia_sidon`) were
verified by reading the page; the tool flags them `[WARN] url-only` by design. After
this revision changed the `why` of `dotu2005`, `opro2024` and `wikipedia_golomb`,
`klein refs verify --record` was re-run on 2026-11-03: 21 references, 0 failed, 17
recorded. The wording now used for both changed rows was re-read at the source that
day: the `dotu2005` abstract (OpenAlex) and the `opro2024` abstract (arxiv.org). No row
is ⚠️ UNVERIFIED, so `refs_verified: true`.

| key | reference | where | relied on for | verified |
|---|---|---|---|---|
| `ref:oeis_a003022` | OEIS A003022, *Length of shortest (or optimal) Golomb ruler with n marks* | oeis.org/A003022 | every G(n) in instance.json | ✅ page read |
| `ref:wikipedia_golomb` | *Golomb ruler* | Wikipedia | c_n per order; optimality credits (Mixon 1972 for 8–11, primary not located); OGR dates | ✅ page read (secondary) |
| `ref:robinson1979` | Robinson 1979, *Optimum Golomb Rulers* | IEEE Trans. Computers C-28(12); doi:10.1109/TC.1979.1675287 | G(12) = 85 (sealed) | ✅ |
| `ref:robinson1983` | Robinson 1983, *Addendum to "Optimum Golomb Rulers"* | IEEE Trans. Computers C-32(2); doi:10.1109/TC.1983.1676205 | G(13) = 106 (sealed) | ✅ |
| `ref:shearer1990` | Shearer 1990, *Some new optimum Golomb rulers* | IEEE Trans. Inf. Theory 36(1); doi:10.1109/18.50388 | exhaustive search, 14–16 marks, unique optima | ✅ |
| `ref:dollas1998` | Dollas, Rankin & McCracken 1998, *A new algorithm for Golomb ruler derivation and proof of the 19 mark ruler* | IEEE Trans. Inf. Theory 44(1); doi:10.1109/18.651068 | parallel distributed exhaustive search | ✅ |
| `ref:distributed_net_ogr` | distributed.net, *Project OGR* | distributed.net/OGR | volunteer-computing scale (OGR-24…28) | ✅ page read (page itself stale) |
| `ref:babcock1953` | Babcock 1953, *Intermodulation Interference in Radio Systems* | Bell Syst. Tech. J. 32(1); doi:10.1002/j.1538-7305.1953.tb01422.x | provenance: interference-free channels | ✅ |
| `ref:bloom_golomb1977` | Bloom & Golomb 1977, *Applications of numbered undirected graphs* | Proc. IEEE 65(4); doi:10.1109/PROC.1977.10517 | provenance of the name | ✅ |
| `ref:atkinson1986` | Atkinson, Santoro & Urrutia 1986, *Integer Sets with Distinct Sums and Differences and Carrier Frequency Assignments for Nonlinear Repeaters* | IEEE Trans. Commun. 34(6); doi:10.1109/TCOM.1986.1096587 | near-optimal constructions for n < 100 | ✅ |
| `ref:erdos_turan1941` | Erdős & Turán 1941, *On a Problem of Sidon in Additive Number Theory, and on some Related Problems* | J. London Math. Soc. s1-16(4); doi:10.1112/jlms/s1-16.4.212 | equation (2), lower half | ✅ |
| `ref:singer1938` | Singer 1938, *A theorem in finite projective geometry and some applications to number theory* | Trans. AMS 43(3); doi:10.1090/S0002-9947-1938-1501951-4 | equation (2), upper half | ✅ |
| `ref:wikipedia_sidon` | *Sidon sequence* | Wikipedia | Golomb ⇔ Sidon; statements of the bounds | ✅ page read (secondary) |
| `ref:funsearch2024` | Romera-Paredes et al. 2024, *Mathematical discoveries from program search with large language models* | Nature 625(7995); doi:10.1038/s41586-023-06924-6 | the seminal LLM + evaluator loop (programs, not objects) | ✅ |
| `ref:alphaevolve2025` | Novikov et al. 2025, *AlphaEvolve: A coding agent for scientific and algorithmic discovery* | arXiv:2506.13131 (white paper, preprint) | key follow-up | ✅ |
| `ref:georgiev2025` | Georgiev, Gómez-Serrano, Tao & Wagner 2025, *Mathematical exploration and discovery at scale* | arXiv:2511.02864 (preprint) | resonant application; rediscovered vs improved | ✅ |
| `ref:opro2024` | Yang et al. 2024, *Large Language Models as Optimizers* | ICLR 2024; arXiv:2309.03409 | the template the LLM arm's loop is styled on (OPRO's prompt accumulates scored solutions; this arm keeps one batch) | ✅ |
| `ref:kirkpatrick1983` | Kirkpatrick, Gelatt & Vecchi 1983, *Optimization by Simulated Annealing* | Science 220(4598); doi:10.1126/science.220.4598.671 | the search arm's acceptance rule | ✅ |
| `ref:dotu2005` | Dotú & Van Hentenryck 2005, *A simple Hybrid Evolutionary Algorithm for Finding Golomb Rulers* | IEEE CEC 2005, vol. 3; doi:10.1109/CEC.2005.1554943 | classical-heuristic regime anchor; a hybrid evolutionary algorithm in the same feasibility-first family as the search arm, not the same algorithm | ✅ |
| `ref:patternboost2024` | Charton, Ellenberg, Wagner & Williamson 2024, *PatternBoost: Constructions in Mathematics with a Little Help from AI* | arXiv:2411.00566 (preprint) | the no-recall contrast design | ✅ |
| `ref:carlini2023` | Carlini et al. 2023, *Quantifying Memorization Across Neural Language Models* | ICLR 2023; arXiv:2202.07646 | why recall is plausible and variable | ✅ |

**Caveats a referee should see.** Three caveats. (i) "Optimal" at orders 8–11 rests on
OEIS plus a secondary source (`ref:wikipedia_golomb` credits Mixon 1972). The primary
source was not located. The sealed orders' optima have primary sources. (ii) Three of
the frontier references (`ref:alphaevolve2025`, `ref:georgiev2025`,
`ref:patternboost2024`) are preprints and are cited for method and positioning, never
for a number this study compares against. (iii) The Erdős–Turán and Singer statements
were read from `ref:wikipedia_sidon`, not from the 1938/1941 papers; the
bibliographic records of the papers themselves were checked.

**Triad.** Theory: §2 (notation, five display equations, the known-values table, and
the likelihood-ratio table of (5)). Papers: all 21 rows verified,
`refs_verified: true`. Practice: §3a's from-scratch verifier, hardened with a pinned
oracle and a lane bound to `KLEIN_EVALUATION_KIND`, was exercised by 25 toy checks on
orders 5–7 before any lane run. Its checker also ran over the pinned exhaustive
enumeration `sweeps/toy_enumeration.{py,tsv}`. §3b–§3c are realized by `search.py`.
All three legs stand.
