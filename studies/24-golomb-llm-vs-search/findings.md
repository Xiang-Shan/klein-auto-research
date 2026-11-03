---
type: findings
domain: "combinatorial search (Golomb rulers)"
profile: "math"
kind: "test"
status: synthesized
concepts: [golomb-ruler, exact-verifier, matched-budget, recall-vs-search, llm-as-proposer, contamination, order-clustering]
related: [studies/11-exact-verifier-construction/findings.md]
---

# Findings — 24-golomb-llm-vs-search

> SYNTHESIZE stage output. Protocol: `.claude/skills/klein/references/synthesis-protocol.md`;
> the lock and the numbers law: `references/claims-protocol.md`; the call ledger:
> `references/model-calls-protocol.md`; vocabulary: `references/profiles/math.md` §7.
>
> **What this study is.** Two registered arms, one exact checker. A classical randomized
> construction plus local search (`search` track) and the model snapshot
> `qwen-flash-2025-07-28` proposing rulers as JSON data, never code (`llm` track). Each arm
> got exactly 2000 candidate evaluations per (order, trial) pair. Both were scored by the
> same declared verifier against the tabulated optimal lengths of OEIS A003022
> (`ref:oeis_a003022`; optimality is the table's, from exhaustive searches by others, never
> this study's). The development orders are n = 8 to n = 11 with three trials each, so 12
> pairs per arm. The sealed orders are n = 12 and n = 13, so 6 pairs per arm, each read
> once. Every verdict below is the verifier's number, not the searcher's (manifest
> `metric.reported` equals `metric.verified` in every measured run).
>
> **Vocabulary.** A pair "matched" when its best verified ruler has the tabulated length.
> Nothing here is "found", "discovered" or "proved": every lane order's answer is public.
>
> **Derived tables.** Two synthesis tables are new at this stage. `tables/synthesis_pairs.tsv`
> (`art:synth_pairs`) has one row per pair. `tables/synthesis_summary.tsv`
> (`art:synth_summary`) holds the aggregates, the exact tests, n_comparisons, usage totals
> and a ledger cross-check. Both are written by `tables/synthesis_derive.py`, which reads
> only committed evidence and makes no model call. Re-run it with
> `uv run --no-sync python studies/24-golomb-llm-vs-search/tables/synthesis_derive.py`.

## ① Research-question verdicts

**Headline, development lane (exploratory as a contrast).** The LLM arm matched 6 of 12
pairs and the search arm matched 0 of 12 (E0004 vs E0001), a difference of +6 pairs.
**Sealed lane (confirmation).** Both arms matched 0 of 6 (E0006, E0005). The LLM arm
produced no valid ruler at all there: `invalid_best` is 6 of 6, and 265 of 1200 replies
were unparsed. Every other reply parsed, but none was a valid Golomb ruler.

| Claim | RQ | Track | Verdict | Strength | Class | Evidence | Delta + uncertainty |
|---|---|---|---|---|---|---|---|
| **[C1]** | RQ1 | search | supported (prior "at most half" held) | confirmed | empirical-description | E0001, rep:E0001@20261103T090037Z, E0005, art:synth_summary, ref:oeis_a003022 | At a budget of 2000 candidate evaluations per pair the classical search matched the tabulated optimum in 0 of 12 development pairs, its mean gap growing from 5.667 to 35.333 length units across the four development orders, and a re-execution reproduced the count exactly. |
| **[C2]** | RQ2 | llm | refuted (prior "about even that it reaches 9 of 12") | exploratory | empirical-description | E0004, rep:E0004@20261103T090054Z, art:sol_E0004, art:rep_E0004, ref:oeis_a003022 | On the same development pairs the LLM arm matched the tabulated optimum in 6 of 12 pairs, all three trials of the two orders that matched and none of the other two, and a salted re-query of every call reproduced the count of 6 of 12 but not the pair-level detail: first-batch matches 2 against 1, valid rulers 788 against 719, unparsed replies 531 against 593. |
| **[C3]** | RQ2 | llm vs search | inconclusive as an inference; the count difference is measured | exploratory | empirical-description | E0001, E0004, art:synth_summary | The development contrast is +6 pairs for the LLM arm over the search arm, with an exact McNemar p of 0.03125 when the 12 pairs are treated as independent, which does not clear the Bonferroni level of 0.025 for the two arm contrasts, and a p of 0.5 when the four orders are the unit, so the advantage is a measured count difference on two orders, not an established rate. |
| **[C4]** | RQ3 | llm | refuted (prior "yes for most matches") | exploratory | empirical-description | E0004, rep:E0004@20261103T090054Z, art:synth_pairs | Only 1 of 12 development pairs held a verified optimum in its first proposal batch, and 2 of 12 in the salted re-query; 5 of 6 matched pairs first reached the optimum after verifier feedback, at proposals as late as 74 of 200, so the registered first-batch recall signature was not observed, which does not exclude recall, because a late match can be a resampled or repaired memory. |
| **[C5]** | RQ4 | search, llm | supported for search (prior 0.85 held); LLM arm did not reach the optimum | confirmed | empirical-description | E0005, E0006, art:sol_E0005, art:sol_E0006, art:synth_summary, ref:robinson1979, ref:robinson1983 | On the sealed orders both arms matched the tabulated optimum in 0 of 6 pairs; the search arm's best verified lengths stayed at least 48 length units above it, and the LLM arm produced no verified ruler at all, with an invalid best in 6 of 6 pairs, 265 of 1200 replies unparsed and none of its candidates a valid Golomb ruler. |
| **[C6]** | all | search, llm | procedural | confirmed | procedural-verdict | E0001, E0004, E0005, E0006 | The predictions ledger holds 2 supported and 3 refuted of the 5 registered predictions: P1 and P4 supported, P2, P3 and P5 refuted, each refutation answered by a dated Decision line in program.md. |

**Strength labels.** `confirmed` is used only where the track holds both kinds of
evidence its `confirmation.require: [sealed, replicate]` names *for the statement made*.
C1 is the search arm's 0 of 12, re-executed with difference 0 (rep:E0001), together with
the sealed 0 of 6 (E0005). C5 is the sealed evidence itself. C6 is a ledger fact.

C2 stays `exploratory` for two reasons. The re-query reproduced only the count. The sealed
lane tests different orders, and there the count did not carry over (0 of 6). C3 and C4
are exploratory by construction.

**Controls that exist.** There are three.

1. **The exact verifier** (`verify.py`, sha256 `63a60221be1a…`). It sits outside the
   mutable surface and was hashed at METHOD. It re-derives every count from the artifact
   with integer arithmetic.
   - It refuses: wrong lane, missing lane kind, another run's artifact, a pair that did not
     spend exactly 2000 evaluations, a tampered optimum or budget, a claimed length that
     differs from the verified one, and a verified length below the table.
   - `sweeps/verifier_checks.py` re-runs nine of these refusals and all nine pass
     (data card).
   - Positive control: hand-transcribed tabulated rulers scored 12 of 12 (development) and
     6 of 6 (sealed). Negative controls: planted invalid objects were rejected. Both are
     recorded in the data card. Those control artifacts lived in a scratch directory and
     are not pinned, so the record of them is the card's text.
2. **The oracle of known optimal lengths.** `verify.py` pins the OEIS A003022 values for
   orders 8 to 13 (34, 44, 55, 72, 85, 106) in its `ORACLE`, and it refuses an
   `instance.json` that disagrees. Those lengths are the only reference values any count
   is compared against.
3. **A ledger cross-check, run at this stage** (data card NOTE 5 and WARN 1).
   - Every pair has exactly 200 calls in the pinned call ledger.
   - The stored first batch equals the ledger's first reply in 12 of 12 development pairs
     and 6 of 6 sealed pairs.
   - The three trials of each order sent one distinct first request between them
     (`art:synth_summary`).

**Controls that are missing, and why.** All of them are absent by design: the CONSULT
contract registered exactly two arms, and both phase allowances were spent (development 4
of 4 experiments, confirmation 2 of 2).

- **A contamination control.** Every lane order is tabulated, so no instance has an answer
  the model could not have seen, for example an order beyond the table or a perturbed
  Golomb variant. This is the control that would separate search from recall.
- **A no-feedback LLM control.** The same prompt resampled 200 times without verdicts would
  separate feedback-steered repair from plain resampling. That is the question C4 leaves
  open.
- **A compute-matched or stronger classical arm.** The budget was matched in candidate
  evaluations, i.e. verifier calls, by a dated decision. It was not matched in wall-clock,
  tokens or information: the search arm sees one verdict per candidate, the LLM one text
  batch per 10. No published heuristic such as `ref:dotu2005` was run. The search arm's
  0 of 12 describes this annealer at this budget only.
- **A second model, snapshot or temperature.** Only one snapshot was queried, at
  temperature 0.7. Every LLM statement is about `qwen-flash-2025-07-28` as served on
  2026-11-03.
- **An empirical blind random-proposal null.** None was run. The method card gives an
  analytic one instead (its equation 5).

**n_comparisons, per family.**

| Family | Count | How it is handled |
|---|---|---|
| Arm contrasts | 2 | Development (E0004 vs E0001) and sealed (E0006 vs E0005). Bonferroni level 0.025 per contrast. The sealed contrast has no discordant pair. |
| Registered predictions | 5 | P1 to P5, each a deterministic arithmetic rule on one cell, adjudicated by the notary. No multiplicity correction applies to a rule; the five are reported as a family. |
| Method-card priors | 5 | Card-level priors (the card's own labels C1 to C5, part 4(b), not this file's claim ids). These are descriptive checks, not tests. |
| Replications | 2 | rep:E0001 and rep:E0004, each at tolerance 0 on the primary metric. |
| Post-hoc descriptive counts | 4 | The first-batch prefix counts against the tabulated 8- and 11-mark rulers, the nested-prefix count, and the order-9 valid-ruler count (③). None is a test, and none is used to decide anything. |

**Crash audit.** E0002 and E0003 crashed on transport. Neither was a bug in the ruler logic.

- **E0002** got HTTP 429 from the provider after 613 calls (run.log). The ledger's
  three-attempt retry over 14 s was too short for a per-minute limit.
- **E0003** got a bare `ConnectionResetError`, which the 429 backoff did not cover, after
  523 live calls plus 613 cache hits.
- **The fix.** Both were fixed in the framework transport, recorded by dated lead decisions
  in program.md, and the same pre-registered cell ran to completion as E0004. So the crashed
  direction *was* retried.
- **The caveat it leaves.** E0004 answered 1136 of its 2400 requests from the E0002 and
  E0003 shards, a share of 0.4733. These are genuine recorded responses to byte-identical
  requests, but they make E0004 partly the same sample as the crashed runs. The salted
  re-query (rep:E0004) is the only fully independent second draw.

**Rehearsals.** The `DRYRUN` rows in aux_metrics.tsv and the files under `sweeps/` are
sealed dry runs. They are never evidence.

## ② Registered predictions (from the ledger)

These rows are copied from `klein predict list` and never re-decided here. The score is
2 held and 3 refuted, out of 5.

| P# | Statement | Rule | Observed | Verdict (ledger) | Evidence | Decision |
|---|---|---|---|---|---|---|
| P1 | search, development: optimum in at most 6 of 12 pairs | `{primary_metric, <=, 6}` | 0 | supported | E0001 | — |
| P2 | llm, development: optimum in at least 9 of 12 pairs | `{primary_metric, >=, 9}` | 6 | refuted | E0004 | program.md, 2026-11-03: "Decision: P2 refuted by E0004 (6 of 12 < 9) … withdrawn; replicated at 6/12 by the E0004 replication" |
| P3 | llm, development: at least 6 of 12 pairs hold an optimum in the FIRST batch | `{first_batch_matches, >=, 6}` | 1 | refuted | E0004 | program.md, 2026-11-03: "Decision: P3 refuted by E0004 (first_batch_matches 1 < 6): the recall-in-first-batch account is not supported on development orders" |
| P4 | search, sealed: optimum in none of 6 pairs | `{primary_metric, <=, 0}` | 0 | supported | E0005 | — |
| P5 | llm, sealed: optimum in at least 3 of 6 pairs | `{primary_metric, >=, 3}` | 0 | refuted | E0006 | program.md, 2026-11-03: "Decision: P5 refuted by E0006 (0 of 6 < 3): the LLM arm's development matches did not carry to sealed orders 12-13; no verified ruler was produced there" |

**Priors scorecard** (`art:synth_summary`). This is descriptive only, with n = 4 or 5
predictions, so it is not a calibration claim.

- The method card's P(rule holds) gave a Brier score of 0.036 over P1 to P5, and its
  direction was right on all five.
- On the four predictions both sources priced (P2 to P5), the card scored 0.044. The
  CONSULT-time RQ priors scored 0.171. Those priors are "knowledge, recalled" and expected
  recall of the tables.
- The CONSULT priors that expected the model to recall the tables (RQ2, RQ3, RQ4's LLM half)
  are the ones that failed.

**Method-card part 4(b) priors.**

| Prior | Rule | Observed | Outcome |
|---|---|---|---|
| card C1 · the annealer's ceiling | M_search at most 2, and none at orders 10 and 11 | 0 of 12 | held |
| card C2 · the gap grows with order | per-order mean gap non-decreasing, at least 3 at n = 11 | 5.667, 11.333, 25.0, 35.333 | held |
| card C3 · LLM clusters by order | at least 3 of 4 orders all-or-none | 4 of 4 | held |
| card C4 · recall dominates matches | first-batch matches at least M_llm / 2 = 3.0 | 1 | **refuted** |
| card C5 · LLM not behind | M_llm − M_search at least 0 | +6 | held |

The card staked its recall reading on card prior C4, and the data contradict it: see ③.

## ③ Surprises and why

Every mechanism sentence below is an **untested hypothesis** (class
`mechanism-interpretation`, strength `exploratory`). No experiment in this study was
designed to test it, and the controls that could test it are listed as missing in ①.

**[C7]** Untested hypothesis: the LLM arm's matches are retrieval of tabulated rulers. Every
matched ruler is the row the public table prints, and the best ruler in all three trials at
order ten is the first ten marks of the tabulated eleven-mark ruler, a Golomb ruler by
inheritance at length 70 against the optimum 55. But identity with a unique tabulated
optimum cannot separate recall from search, and the study ran no control that could.

- **Observed.** At n = 8 every matched ruler is `0 1 4 9 15 22 32 34`. At n = 11 every
  matched ruler is `0 1 4 13 28 33 47 54 64 70 72`. Both are the rows of the data card's
  transcription of the Wikipedia table (`ref:wikipedia_golomb`). At n = 10 all three bests
  are the first ten marks of that 11-mark row (`best_is_prefix_of_tab11` is 1 in 6 of 6
  rows at orders 10 and 11, `art:synth_pairs`). No order-10 proposal reached the tabulated
  10-mark row `0 1 6 10 23 26 34 41 53 55`.
- **Why it surprised.** Card prior C4 expected recall to show up *at once*. Instead the
  tabulated rows arrived at proposals 1, 70 and 34 (n = 8) and 2, 74 and 11 (n = 11).
- **The hypothesis.** The model holds those two rows, and a sample at temperature 0.7,
  nudged by "difference d repeats" feedback, lands on them within tens of proposals.
- **Why it stays a hypothesis.** It is equally consistent with a short local search that
  happens to converge on a unique optimum. Identity is uninformative when the optimum is
  unique, so only the missing contamination control could separate the two readings.

**[C8]** Untested hypothesis: order nine failed for the LLM arm, with no valid ruler in 600
proposals, because its proposals anchor on extending the tabulated eight-mark row. 8 of 120
development first-batch rulers share that row's first seven marks, including one in every
order-nine first batch, and extending a Golomb ruler by a mark usually repeats a difference.

- **Observed.** Order 9 is non-monotone in difficulty for the LLM arm. It got 0 valid rulers
  at n = 9, but it matched at n = 11 and produced valid (unmatched) rulers at n = 10.
- **Telling detail.** The first nine marks of the tabulated 11-mark ruler, `0 1 4 13 28 33 47
  54 64`, form a valid 9-mark Golomb ruler of length 64. Since `valid_rulers` is 0 at n = 9,
  it was never proposed. So truncating the 11-mark row is not a general strategy of this
  model.
- **The prefix count is post-hoc.** It is one of the four descriptive counts in ①.

**[C9]** The method card's prior that recall dominates the matches (first-batch matches at
least half the matched count, a bar of 3) is refuted at 1. Its other four card-level priors
held: the search arm matched 0 of 12, its mean gap was non-decreasing with order and 35.333
at the largest development order, every development order clustered all-or-none for the LLM
arm, and the LLM arm was not behind at +6 pairs.

**The sealed lane.** The LLM arm produced no valid ruler at n = 12 or n = 13, not merely no
match. Its closest first-batch candidate still had 5 repeated differences
(`E0006_fb_min_repeated_differences`).

- Six first-batch rulers at n = 12, trial 1, open with at least six marks of the tabulated
  11-mark row (`E0006_fb_prefix_tab11_ge6`).
- The reading that the development matches are short-row recall that does not extend to
  12- or 13-integer rows is the program's own (2026-11-03 Decision on P5). It fits these
  counts. It remains a hypothesis under C7, not a finding.

**The search arm.** Its 0 of 12 contrasts with the METHOD-gate toy calibration (orders 5 to 7:
20 of 20, 20 of 20, 9 of 20), the same algorithm at the same budget. The gap grows with order
exactly as card prior C2 predicted. This is hardness growth at a fixed budget, not a defect.

**A correction to the program's prose.** The development Log says "Every n=8 first batch opens
with the same prefix 0,1,4,9,15,22,32". The pinned tables show that prefix in trials 0 and 2
only. Trial 1 opens `0 1 3 7 12 20 29 38` (`fb_prefix_tab8_ge7` per row, `art:synth_pairs`).
The program's next sentence ("consistent with retrieval or recall … cannot separate") already
carried the right strength.

**Unresolved.** It is unexplained why the n = 10 trials converge on the truncated 11-mark row
(gap 15) rather than the tabulated 10-mark row. It is also unexplained why the salted re-query
moved first-batch matches from 1 to 2 and `invalid_best` from 3 to 2 while keeping the count
at 6. The replica's per-pair table is not in its record (see C14), so which pairs changed is
not known.

## ④ Practical advice

**[C10]** Report a matched-evaluation budget beside its compute: at 2000 evaluations per pair
the LLM arm took about 10234 times the search arm's searcher-reported wall-clock on
development and 13016 times on the sealed orders, and the study made 6000 live model calls
carrying 6507285 tokens.

**[C11]** Count an LLM arm's outcomes in orders as well as in pairs: the trials of an order
sent byte-identical first requests and every development order came out all-or-none, so the
exact test moved from 0.03125 to 0.5 when the unit changed from pair to order.

**[C12]** Treat a rerun after a crash as partly the crashed run: E0004 answered 1136 of 2400
requests from the crashed runs' shards, a share of 0.4733, so only a salted re-query is an
independent second draw from the model.

**[C13]** Declare a price block before a model-calling run: this study's calls block declares
none, so every recorded usd reads 0, and the dollar cost of its 6000 live calls is unrecorded,
not zero.

- `kleinlib.calls.CallLedger._cost` returns 0.0 whenever `price` is absent.
- `price_configured` in `art:synth_summary` records the absence.
- Live token counts are recorded, so a price applied later can be computed from them.

**[C14]** Keep the replica's solution table when an LLM cell is re-queried: the salted
re-query's record keeps its call shards and its metric block but not its per-pair artifact, so
whether the same pairs matched cannot be read from the record, only that the count of 6 of 12
recurred.

- The salted shards *are* kept (`runs/E0004/replications/20261103T090054Z-calls/`).
- An offline replay against them could rebuild the table. This synthesis did not do that.

**[C15]** Do not read a match on a tabulated object as search: a matched-budget comparison on
instances whose answers are public measures recall and search together, so a claim about
search needs a contamination control (an untabulated or perturbed instance) and a
no-feedback arm before it is made.

This study has neither (①), which is why C7 and C8 stay hypotheses.

## ⑤ Consequences for the conjecture or bound

**[C16]** The matched rulers re-attain upper bounds already known to be tight, length 34 at
eight marks and 72 at eleven marks per the OEIS table, so the study establishes nothing new
about any Golomb length, and every miss is a fact about these proposers at this budget, never
evidence that a shorter ruler or a match is out of reach.

**What the verified objects establish.**

- A verified ruler of length ℓ certifies only the upper bound G(n) ≤ ℓ.
- The matched rulers give G(8) ≤ 34 and G(11) ≤ 72. Both equal the tabulated values of
  OEIS A003022 (`ref:oeis_a003022`). Optimality of those values rests on exhaustive
  searches by others, which this study did not re-run and did not check.
- The unmatched verified rulers give weaker upper bounds than the table already holds:
  - LLM at n = 10: 70 against 55.
  - Search at n = 8 to 11: 38 to 111 against 34 to 72.
  - Search at n = 12 and 13: 133 to 166 against 85 and 106 (`ref:robinson1979`,
    `ref:robinson1983`).

**What they do not establish.**

- No lower bound and no impossibility.
- Nothing about whether a classical search or an LLM proposer *can* reach these lengths at
  another budget, prompt, temperature or model.
- No statement about orders beyond 13, and nothing about the open orders past the table's
  end.
- The LLM arm's failure to produce a single valid 12- or 13-mark ruler is not evidence that
  such rulers are hard to write down. Explicit constructions exist (`ref:singer1938`,
  `ref:atkinson1986`). It describes this snapshot under this prompt.

**What each result is compared against.** Only the A003022 values pinned in the verifier's
`ORACLE` (OEIS revision #130, checked 2026-11-03). Data card WARN 3 records that per-order
optimality credits for n ≤ 14 rest on the literature, not on a source this study opened.

## ⑥ Literature tie-back

- **Classical search.** `ref:dotu2005` reports that a hybrid evolutionary algorithm "quickly
  finds optimal rulers with up to 11 marks", at a budget stated in time. This study's simpler
  annealer, at 2000 evaluations, matched 0 of 12 at orders 8 to 11. That is not a
  contradiction, because the budgets are not comparable. It does mean that C1 says nothing
  about classical search in general.
- **LLM-guided search.** The method card positioned this design honestly against FunSearch
  (`ref:funsearch2024`), AlphaEvolve (`ref:alphaevolve2025`) and its at-scale application
  (`ref:georgiev2025`). Those systems evolve *programs* against evaluators, often on problems
  without a public answer key, and the last of them reports rediscovered and improved results
  separately. This study's arm emits *objects* on tabulated problems. It is the OPRO-style
  regime (`ref:opro2024`) with a one-batch memory, the weakest regime for any claim beyond
  rediscovery.
- **Memorization.** The results sit where `ref:carlini2023` would place a flash-tier model.
  The shortest tabulated rows are reproduced, at least eventually: 8 marks, and 11 marks with
  its two optima. There is no exact 12- or 13-integer row and not even a valid one.
- **The card's own scan.** It found no paper applying an LLM proposer to Golomb rulers, and a
  two-query scan finding nothing is not evidence that nothing exists. This study adds one
  dated data point for one snapshot. It does not position the model class.
- **Priors.** The method card's literature-and-reasoning priors outpredicted the CONSULT-time
  recalled priors on the shared predictions (Brier 0.044 against 0.171, n = 4, ②). That is
  descriptive only.

## ⑦ What to try next

1. **A contamination control, first.** Re-run the LLM arm unchanged on instances with no
   public answer, at the same 2000 evaluations: a perturbed Golomb variant (for example
   rulers with a forbidden difference set) whose optima this study's verifier can certify by
   exhaustive enumeration at small n. A match there could not be retrieval. This is the single
   experiment that converts C7 and C8 from hypotheses into findings or refutations.
2. **A no-feedback arm.** Run the same model and prompt resampled for 200 proposals without
   verdicts, on orders 8 and 11. If the late matches (proposals 34, 70, 74) recur without
   feedback, they are resampling. If they vanish, feedback steered them. Register it as a
   rule on `first_optimal_proposal`.
3. **A compute-honest classical baseline.** Run the search arm (or `ref:dotu2005`'s hybrid)
   at the LLM arm's wall-clock, or at 10 and 100 times the evaluations, with the budget
   reported in evaluations and seconds. This sets where the annealer's 0 of 12 sits on its
   own budget curve.
4. **Snapshot and temperature replication.** Query a second dated snapshot and temperature
   0, with a price block declared (C13) and the replica's per-pair table kept (C14). Report
   results in orders as the unit (C11).

**Candidate claims for a cross-study survey** (not written here): C3, C10, C11, C12, C13 and
C15 are process lessons that may promote into `knowledge/research-discipline.md` with typed
citations after the referee's verdict.
