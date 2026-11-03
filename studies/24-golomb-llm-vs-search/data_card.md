---
type: data-card
domain: "combinatorial search (Golomb rulers)"
modality: none
status: go-with-cautions
concepts: [golomb-ruler, oeis-a003022, verifier-card]
related: []
---

# Data card — 24-golomb-llm-vs-search

Recipe `math-verify`. Gate 1 (DATA), modality `none` with a declared verifier, so the
audit is the VERIFIER card. Written from `study.yaml`, `prepare.py`, `verify.py`,
`search.py`, `scouting_ledger.md` and the prepared `instance.json`; of `program.md` only
the section "Lead decisions after the DATA/METHOD review" was read (clean-room
otherwise). This is the second version of the card: it was updated after an adversarial
review found two holes in the verifier and the lead hardened `verify.py` (then
`f7a106592e4e…`; after the re-check the lead tightened it once more — each pair must spend
exactly the budget, the artifact must name the run, docstring corrected — final sha256
`63a60221be1a0b66c36095c804d08799df889156c7299c1129df16f2c0bc903c`,
re-run checks in `sweeps/verifier_checks.py`, 9/9 pass). No model API was called, and the search arm was not run on orders
8-13 (all verifier tests below use hand-made artifacts, toy orders, or published
optimal rulers pasted in by hand).

## Source & shape

- **Source tag:** `synthetic:prepare.py` (`klein doctor --study`: "script found at
  prepare.py"; no network; no `data.sha256` pin needed, the script is deterministic and
  its output is hashed by this gate). **Modality:** `none`. **Target:** `ruler_length`
  (the metric is `optima_matched`, an integer count in 0..12 development, 0..6 sealed).
- **Prepared artifact:** `data/prepared/instance.json`, produced by
  `uv run --locked python -u prepare.py`. Run twice: byte-identical, sha256
  `717e406cc9a9b453fe33458e9aade36dab9c36cc08f425e80f74004d0cdb661e`; the working tree
  stayed clean (the committed file is identical). It is the only prepared artifact; there
  are no rows, no index table and no partitions.
- **Split policy:** `data.split.kind: none` (seed 42, inert), `realized_split:
  advisory`. The "split" is the pair of lanes declared inside `instance.json`.
  **Fingerprints frozen at this gate:** data = the hash of `instance.json` above; split =
  none registered (see issue 6 for what that means for run-one).
- **Profiler:** not applicable (no table). The profile is the field-by-field audit of
  `instance.json` below. `kleinlib.profile_fallback` and `kleinlib.leakage` need a
  csv/parquet; leakage is N/A for modality `none`.

### Every field of `instance.json`, and where it comes from

| Field | Value | Provenance / check |
|---|---|---|
| `problem` | `"golomb-ruler"` | constant; `verify.py` rejects any artifact with another value |
| `development_orders` | `[8, 9, 10, 11]` | study design (`study.yaml` goal and phases); the only orders adaptive work may touch |
| `sealed_orders` | `[12, 13]` | study design; one run per arm via `klein run-one --final-test`; disjoint from development orders |
| `trials` | `3` | design; 12 development pairs (4 x 3), 6 sealed pairs (2 x 3); matches the thresholds of P1-P5 (6, 9, 6, 0, 3) |
| `budget_evaluations` | `2000` | design; `prepare.py` refuses a budget that is not a multiple of `llm_batch` (2000 / 10 = 200 proposals) |
| `llm_batch` | `10` | design; `verify.py` demands exactly 10 first-batch entries from the llm arm |
| `optima` | orders 1..14 -> 0, 1, 3, 6, 11, 17, 25, 34, 44, 55, 72, 85, 106, 127 | OEIS A003022 (below); orders 8-13 are 34, 44, 55, 72, 85, 106; order 14 and orders 1-7 are used by no lane |
| `optima_source` | OEIS A003022, revision #130 (Oct 28 2026), checked 2026-11-03, offset note | confirmed against oeis.org during this audit (below) |
| `seed_blocks` | development 20261106, sealed 20261107 | design; read by `search.py`; no literal seed elsewhere (see determinism) |

Value-pattern check (mandatory): there is no column. Every scalar was inspected by
value, not by type: all counts and lengths are JSON integers (no numbers-in-strings, no
booleans, no sentinels such as `-1`/`NA`/`""`); the optima keys are strings of integers
(`"1"`..`"14"`) and `search.py` converts them with `int()`; `trials`,
`budget_evaluations` and `llm_batch` are positive integers; both seed blocks are
integers; the only free text is `optima_source`. One convention to know: order 1 has
length 0 by convention (the one-mark ruler {0}); it is not an OEIS term and no lane uses
it.

### Provenance of the optima (OEIS A003022), confirmed 2026-11-03

Fetched `https://oeis.org/search?q=id:A003022&fmt=text` (no WebFetch tool in this
environment; curl through the sanctioned proxy). Header `%I A003022 M2540 #130 Oct 28
2026`, offset `%O 2,2`, data `1,3,6,11,17,25,34,44,55,72,85,106,127,151,177,199,...`.
With offset 2, a(2..14) = 1, 3, 6, 11, 17, 25, 34, 44, 55, 72, 85, 106, 127, so
a(8..13) = 34, 44, 55, 72, 85, 106 exactly as in `instance.json`, and a(14) = 127 too.
The revision and date in `prepare.py` are correct.

Who established optimality, stated honestly: the OEIS entry credits distributed.net's
OGR projects only for **a(25)-a(28)** (`%E` lines: a(25), a(26) by OGR-25 and OGR-26,
a(27) by OGR-27, a(28) by OGR-28). An earlier version of this card, and the brief it was
written from, premised that distributed.net had a part in the orders used here; that
premise was wrong: **distributed.net proved orders 24-28 and nothing in 8-14**. The OEIS
entry gives no per-term proof reference for n <= 14. Its `%H` links name the primary
compilations for that range, which the card now cites directly instead of via Wikipedia:
**James B. Shearer's tables**, linked from A003022 as "Golomb ruler table"
(`web.archive.org/web/20111113044544/http://www.research.ibm.com/people/s/shearer/grtab.html`),
"Table of Known Optimal Golomb Rulers" (`.../20110629190307/.../shearer/gropt.html`) and
"Difference Triangle Sets: Discoverers" (`.../20110629185858/.../shearer/dtslb.html`),
alongside Dewdney's Scientific American columns (1985-86) and Golomb's 1972 letter to
Sloane. Honest limit: this sandbox's proxy reset every connection to `web.archive.org`,
so I could NOT open Shearer's pages; the OEIS page itself (fetched) is what I verified.
The discoverer-and-year attribution in the previous version (Mixon 1972 for 8-11,
Robinson 1979/1981 for 12/13, Shearer 1985 for 14) came from Wikipedia and is therefore
**unconfirmed here**; it is dropped from the citation line, and the discoverers table
above is where to read it. Findings must say "optimal per OEIS A003022 (Shearer's tables,
exhaustive searches)" and must not say "proved by this study" or credit distributed.net.
I did not re-prove any lower bound (forbidden for orders 8-13). What I did check
independently is attainability: rulers for orders 8-13 transcribed by hand were accepted
by `verify.py` with exactly the table lengths (see controls), so every lane optimum is
achieved by a ruler an independent checker accepts; only "nothing shorter exists" rests
on the literature.

### Lanes and budget accounting

- **Development lane:** orders 8-11 x trials 0-2 = 12 pairs, seed block 20261106.
  **Sealed lane:** orders 12-13 x trials 0-2 = 6 pairs, seed block 20261107. The lane is
  selected by `KLEIN_EVALUATION_KIND` (`development` / `final_test`); the sealed rehearsal
  (`KLEIN_SEALED_DRYRUN=1`) runs the DEVELOPMENT orders, prints `sealed_dryrun: 1`, writes
  its artifact under `sweeps/`, and the llm arm runs offline from the ledger. **The
  search arm's sealed dry run re-runs the development cell outside any transaction: its
  output under `sweeps/` is rehearsal output and is never citable evidence** (issue 10).
  `verify.py` rejects an artifact whose lane differs from the partition the run was
  judged on, and one whose `orders` differ from that lane's orders (next section).
- **Matched budget, 2,000 candidate evaluations per (order, trial):** the unit is one
  call of `search.py:_is_golomb`, which calls `Budget.spend()` first and raises
  `RuntimeError` on the 2,001st. Search arm: one candidate per call, loop `while not
  budget.exhausted()`; every candidate (including `_shrink` proposals and SA moves) goes
  through `_is_golomb`. LLM arm: 200 proposals x batch 10; each reply is padded or
  truncated to exactly 10 entries and every entry, including a missing one (`None`),
  spends one evaluation, so malformed output is not free. Totals: 24,000 evaluations per
  arm in development, 12,000 sealed. LLM calls: 12 x 200 = 2,400 (development) and
  6 x 200 = 1,200 (sealed). `calls.budget_calls: 5000` is **per run** (study.yaml says
  so), so each cell fits with room. Study-wide, live calls are about **7,200**: 3,600 for
  the first pass plus about 3,600 for the salted re-query replication; a `--replay` is
  offline and never counts as one (issue 11).
- The accounting is by candidates, not by information or wall time: the search arm gets
  feedback after every candidate, the llm arm after every ten, in text. Claims must be
  phrased "at a matched number of candidate evaluations".

## Verifier card

- **Oracle:** `studies/24-golomb-llm-vs-search/verify.py`, declared for both tracks
  (`tracks.<id>.verifier`, `artifact_key: solution`). It is not in `entrypoint.mutable`
  (`["search.py"]`). Run-one executes it with `KLEIN_ARTIFACT` and `KLEIN_TRACK`; without
  `KLEIN_ARTIFACT` it exits 1 with a message.
- **Two holes found by the adversarial review, and the new behaviour (tested below).**
  (a) *Self-declared lane.* The artifact names its own `lane`, so a development run could
  have submitted a sealed-lane artifact (or the reverse) and been scored on the wrong
  partition without spending the seal. Now `expected_lane()` maps `KLEIN_EVALUATION_KIND`
  (`development` -> `development`, `final_test` -> `sealed`) and `check()` rejects any
  artifact whose declared lane differs, in either direction; a missing or unknown kind is
  rejected outright (`REJECTED: KLEIN_EVALUATION_KIND=None: ...`), so running the
  verifier by hand scores nothing. Confirmed in `kleinlib/workflow.py`: `klein run-one`
  passes `"KLEIN_EVALUATION_KIND": evaluation_kind` in the verifier's `env_overrides`
  (line 433; the kind is `final_test` or `development` from the run, lines 936 and 1534,
  and from the manifest on a re-verify, line 910), and `klein replicate` already did
  (`kleinlib/replicate.py:619`, from the manifest). Framework commit `fcadacf` ("verifiers
  see the evaluation kind") is an ancestor of this branch's HEAD.
  (b) *Mutable oracle.* `instance.json` is gitignored and `search.py` (mutable, write
  access) runs just before the verifier reads it, so the optima, orders, trials and
  budget the verifier trusted were editable by the thing being judged. Now `verify.py`
  carries `ORACLE` (development orders 8-11, sealed 12-13, trials 3, budget 2000,
  llm_batch 10, optima 8..13 = 34, 44, 55, 72, 85, 106; OEIS revision #130) inside the
  file the METHOD gate hashes, and `pinned_instance()` rejects an `instance.json` that
  disagrees with any pinned field (optima compared for orders 8-13 only); scoring uses
  the pinned values, not the file's. Not pinned: `seed_blocks` and the optima outside
  8-13, which scoring never uses (issue 1).
- **What it accepts, read line by line.** `golomb_length(marks, n)` returns a length only
  if: `marks` is a list of exactly `n` elements; every element is an `int` and not a
  `bool` (so `1.0`, `"1"`, `true` fail); `marks[0] == 0`; strictly increasing (so no
  negatives, no duplicates); and the set of all n(n-1)/2 pairwise differences has no
  repeats (exact integers, no floating point). The length is `marks[-1]`.
  `check()` then requires, per artifact: a JSON object with `problem == "golomb-ruler"`,
  `arm` in {search, llm} and equal to `KLEIN_TRACK` when set, `lane` in {development,
  sealed} and equal to the lane of `KLEIN_EVALUATION_KIND`, `orders` exactly equal to the instance's orders for that lane, and a `pairs`
  list; every pair an object with integer `order`/`trial` in `orders x range(3)`, no pair
  repeated or missing, integer `evaluations` in 0..2000, and `best_length` an integer or
  null **equal to the length the verifier recomputes from `best`** (null iff no ruler is
  stored or the stored one fails); a valid ruler shorter than the tabulated optimum is
  rejected as "table or checker wrong". For the llm arm also: `first_batch` is a list of
  exactly 10 entries and, if any holds a valid ruler, none is shorter than the stored
  best (a lost best is rejected). Score: `primary_metric` = pairs whose verified length
  equals the tabulated optimum; `first_batch_matches` = llm pairs whose first batch holds
  a valid optimal ruler (0 for search); also `pairs`, `invalid_best`, `sealed_lane`.
- **What it rejects (exit 2, prints `REJECTED: …`):** unreadable or non-JSON artifact,
  wrong problem, unknown or mismatched arm, unknown lane, a lane that is not the run's
  partition, a missing or unknown `KLEIN_EVALUATION_KIND`, an `instance.json` that
  disagrees with the pinned oracle, wrong orders, missing or
  duplicate pairs, pairs outside the lane, out-of-range evaluations, a claimed length
  that differs from the recomputed one (a forged length, or a length claimed for an
  invalid ruler), an invalid first batch, a lost best, and a verified length below the
  table. Everything else is scored: a pair with `best: null, best_length: null` is
  honest, counts as `invalid_best`, and is never a match.
- **`metric.exactness`:** `exact` (integer count, resolution 1, `minimum_delta` 1,
  `tolerance` 0.0). **Cost per call:** milliseconds per artifact (<= 78 differences per
  ruler at order 13); `total_seconds` printed 0.0.
- **Tolerance:** none needed; all arithmetic is exact integer arithmetic and set
  membership, so there is no floating-point failure mode. `evaluate_scalar` receives
  `study_dir=None`, so the verifier cannot overwrite the run's `aux_metrics.tsv`.
- **Known failure modes / what it does NOT check:**
  1. `evaluations`, `trials`, `budget_evaluations`, `seed`, `experiment`, `sealed_dryrun`
     and the `llm` metadata are self-reported and unaudited (only `0 <= evaluations <=
     2000` is enforced). Equal budget is enforced by `search.py`'s own `Budget`, which is
     in the mutable surface. For the llm arm the call ledger
     (`calls/E####-NNN.jsonl.gz`, `manifest.usage`) is the independent record.
  2. It cannot tell how a valid ruler was produced. An edit of `search.py` that pastes a
     published optimal ruler would score as a match. The defence is procedural: the
     committed diff, `klein replicate`, and the ledger.
  3. `first_batch` is self-reported; only its consistency with `best` is checked. A
     forged first batch could hide a recall signature; P3 is a mechanism hint, not
     proof of recall.
  4. A table entry that is too HIGH is caught (a valid shorter ruler aborts the run); one
     that is too LOW (unattainable) would only show as never being matched. Attainability
     of all orders 8-13 optima was checked here, which closes that direction.
- **Independence from `search.py`.** `verify.py` imports only `json`, `os`, `sys`,
  `time`, `pathlib` and `kleinlib.eval.evaluate_scalar` (the shared metric-block
  printer). It does not import, read or call anything in `search.py`, and its checker
  (`golomb_length`: a set of exact differences) is a separate implementation from
  `_is_golomb` (owner-dict scan with repeat bookkeeping). The shared pieces are
  `kleinlib.eval` (printing only) and `instance.json`, which `verify.py` no longer
  trusts: it only checks that it equals the pinned `ORACLE`.
- **Positive control (hand-planted invalid objects it must reject).** Run in a temp
  directory with a copy of `verify.py` and a toy `instance.json` (development orders 4,
  5; sealed 6; trials 1; budget 20; batch 2); exit codes captured from the process:

  | Artifact | Exit | Message |
  |---|---|---|
  | order 4 `[0,1,2,6]` (difference 1 repeats), claimed length 6 | 2 | claims length 6 but the verified length is None (the stored ruler fails the check) |
  | forged length: valid `[0,1,4,6]` claimed 5 | 2 | claims length 5 but the verified length is 6 |
  | invalid `[0,1,3,5]` claimed 5 | 2 | claims length 5 but verified None |
  | `[0,1.0,4,6]` and `[false,1,4,6]` | 2 | rejected (non-int / bool marks) |
  | duplicate pair | 2 | pair (4, 0) appears twice |
  | missing pair | 2 | missing pairs: [(5, 0)] |
  | evaluations 21 > budget 20 | 2 | outside 0..20 |
  | llm artifact on the search track | 2 | arm 'llm' but the run's track is 'search' |
  | sealed orders submitted as development | 2 | not the development orders |
  | llm first batch of wrong length | 2 | first_batch must hold exactly 2 entries |
  | llm first batch holds valid length 11, stored best 12 | 2 | first batch holds a valid ruler shorter than the stored best |
  | table forged high (order 5 optimum set to 12) with a true length-11 ruler | 2 | verified length 11 is below the tabulated optimum 12 |
  | non-JSON file; missing file | 2 | not readable JSON |
  | no `KLEIN_ARTIFACT` | 1 | refuses to run |

- **Controls for the two fixed holes (run in this audit: temp copy of `verify.py` and
  `instance.json` outside the repo, hand-made artifacts built from the published optimal
  rulers below, 3 trials per order, `arm: search`, via `uv run --locked`).**

  | Case | `KLEIN_EVALUATION_KIND` | Artifact lane | Instance | Exit | Result |
  |---|---|---|---|---|---|
  | right lane, development | `development` | development | real | 0 | `primary_metric 12`, `sealed_lane 0` |
  | right lane, sealed | `final_test` | sealed | real | 0 | `primary_metric 6`, `sealed_lane 1` |
  | wrong lane | `development` | sealed | real | 2 | declares the sealed lane but the run was judged on the development partition |
  | wrong lane, other way | `final_test` | development | real | 2 | declares the development lane but the run was judged on the sealed partition |
  | kind missing | unset | development | real | 2 | `KLEIN_EVALUATION_KIND=None: the verifier must be told ...` |
  | kind unknown | `bogus` | development | real | 2 | same message |
  | optimum of order 10 raised to 56 | `development` | development | tampered | 2 | `instance.json optima ... disagrees with the verifier's pinned ...` |
  | optimum of order 8 raised to 35 | `development` | development | tampered | 2 | same |
  | `budget_evaluations` 4000 | `development` | development | tampered | 2 | `... disagrees with the verifier's pinned 2000` |
  | `sealed_orders` [3, 4] | `final_test` | sealed | tampered | 2 | `sealed_orders = [3, 4] disagrees ...` |
  | instance restored | `development` | development | real | 0 | `primary_metric 12` again |

  Tampering was done in the temp copy only; the study's `instance.json` (sha256
  `717e406c...`) was never touched. This covers `verify.py` alone: I did not run `klein
  run-one` (not allowed here), so end-to-end delivery of the variable rests on reading
  `workflow.py`; the first real run-one's verifier line is the live confirmation.
- **Negative control (known-valid objects it must accept).** Toy: `[0,1,4,6]` and
  `[0,1,4,9,11]` (search track) -> exit 0, `primary_metric 2.0`; valid suboptimal
  `[0,1,4,10,12]` for order 5 -> exit 0, `primary_metric 1.0` (valid, not matched); an
  honest `best: null` pair -> exit 0, score 1.0; an llm artifact with first batches ->
  exit 0, score 2.0. Real instance, published optimal rulers transcribed by hand from the
  Wikipedia table (8: 0 1 4 9 15 22 32 34; 9: 0 1 5 12 25 27 35 41 44; 10: 0 1 6 10 23 26
  34 41 53 55; 11: 0 1 4 13 28 33 47 54 64 70 72; 12: 0 2 6 24 29 40 43 55 68 75 76 85;
  13: 0 2 5 25 37 43 59 70 85 89 98 99 106), three trials each: development artifact ->
  exit 0, `primary_metric 12.0`; sealed artifact -> exit 0, `primary_metric 6.0`. The
  checker and the table agree on every lane order. (These artifacts were not produced by
  a search arm, were kept in a scratch directory outside the repo, and are not evidence.)
- **External best-known value with source:** OEIS A003022 a(8..13) = 34, 44, 55, 72, 85,
  106; revision #130, Oct 28 2026; optimality per Shearer's tables, which A003022 links
  (`%H`); not distributed.net, which proved orders 24-28 only. Matching it is a match of
  the best known, not a new result and not a proof.
- The first (toy) positive-control table above predates the hardening. Its rejections
  are logic `check()` still runs unchanged; the lane test now runs first, so a toy
  artifact additionally needs a matching kind, as the rerun above supplies.

### Search-side audit: does anything about the sealed lane reach a prompt or a decision?

- `search.py` loads the `optima` of all orders. They are used for book-keeping only:
  `search_pair(..., optimum)` sets `first_optimal_at` after a ruler is found,
  `llm_pair(..., optimum)` sets `first_optimal` likewise, and `main()` computes the
  provisional `matched` count. I read every use; none enters a stopping rule, an
  annealing move, a message or a request.
- The llm prompt (`SYSTEM_PROMPT`, `_messages`) contains: the order `n`; the batch size;
  the required pairwise-difference count; "proposal k of 200"; the checker's verdict on
  the previous batch (the ruler, "valid, length L" or "invalid ... difference d
  repeats"); and the best valid length so far. It contains no optimum, no table, no lane
  name, no seed, no mention of OEIS or of an optimal value. One template serves
  development and sealed orders, so what the model is shown does not depend on the lane.
- Residual exposure, not a code leak: the sealed orders and their optima (12: 85, 13:
  106) sit in plain text in the hashed `instance.json`, in the public OEIS, and very
  likely in qwen-flash's training data. "Sealed" protects against adaptive tuning of
  `search.py` (one run per arm, `--final-test`, dry run first); it does NOT make the
  sealed orders unseen by the model. A sealed-lane LLM match is consistent with recall,
  the confound RQ3 asks about. No fresh-order control outside the published tables
  exists.

### Determinism

- Search arm: `random.Random(lane_seed + n*100 + trial)`, the seed read only from
  `instance.json`'s `seed_blocks`. The grep `random_state|seed|train_test_split` finds no
  literal partition seed in `prepare.py` (only the block definition), `verify.py`
  (none) or `search.py` (derivation only); no `contract_split` is involved (kind none).
  Development seeds span 20261906..20262208, sealed 20262307..20262409: distinct per pair,
  lanes do not overlap. The generator uses stdlib `random` methods and `math.exp` on the
  interpreter pinned by `uv.lock` (3.13), so a re-run reproduces the artifact
  (`klein replicate` should confirm); a different Python minor version is a reason to
  re-check, not a guarantee.
- LLM arm: no seed is sent; temperature 0.7, `enable_thinking False`, `max_tokens` 1024.
  Trials are distinct requests through `sample=trial`. Reproduction is by call-ledger
  replay (offline), so the API's own non-determinism does not affect re-verification.
  The 12 (order, trial) loops run concurrently but each depends only on its own history,
  so request content is order-independent.
- The lane fingerprint printed by `search.py` hashes lane, orders, trials, budget and
  seed block (not the optima).

## Ranked go / no-go issues

| # | Severity | Issue | Recommended action |
|---|---|---|---|
| 1 | WARN (kept, narrowed) | Budget parity (`evaluations`, seed) is self-reported by `search.py`, which is the mutable surface; `verify.py` enforces only `0 <= evaluations <= 2000`. An edit could change `Budget`, or hard-code a published ruler, and still score. The hardening pinned trials, budget, orders, optima and the lane, but not this, and not `seed_blocks`. | Every experiment diff must leave `Budget`, `_is_golomb`, lane/seed reading and the prompt untouched; the referee and `klein replicate` re-check; for the llm arm compare the ledger's 200 calls per pair with `evaluations`. |
| 2 | WARN | The sealed orders 12-13 are public (OEIS, Wikipedia) and in `instance.json`; the model may have them memorised. "Sealed" prevents adaptation, not recall; a sealed LLM match cannot by itself be called a search result. | Claim "matched the best known at 2,000 candidate evaluations", never "found" or "discovered"; report RQ3 / P3 (first-batch hit) beside P5; no claim of novelty. |
| 3 | WARN (kept, re-sourced) | Optimality of the table rests on literature: OEIS A003022 has no per-term proof reference for n <= 14; its `%H` links name Shearer's tables (grtab, gropt, dtslb), which I could not open (archive.org unreachable from this sandbox), so per-order discoverer and year are unconfirmed here. distributed.net proved orders 24-28 only (the earlier premise was wrong). | Cite "OEIS A003022 and Shearer's tables" directly with the archive URLs; never "proved" for a study result; never credit distributed.net for 8-14; open Shearer's page before the tutorial states any discoverer. Attainability was verified here. |
| 4 | WARN | The matched budget counts candidates, not information: the search arm sees one verdict per candidate, the llm arm one text batch per 10; no wall-time or token matching. | Phrase every comparison "at a matched number of candidate evaluations (2,000)"; disclose the feedback asymmetry in findings. |
| 5 | NOTE | `first_batch` and `llm` metadata are self-reported; the verifier checks only that no first-batch entry beats `best` and that it holds exactly 10 entries. | Cross-check P3 against the ledger's first request per pair when synthesizing. |
| 6 | NOTE (kept, stronger) | `split.kind: none`: no partition fingerprint is registered, so run-one will most likely print "partition not verified" for the lane fingerprint. The lane is now also guarded by `KLEIN_EVALUATION_KIND` in the verifier, and orders/optima by the pinned oracle. | Do not edit `prepare.py` or `instance.json` after this gate is recorded. |
| 7 | NOTE (kept) | `verify.py` does not compare the artifact's `experiment` id with `KLEIN_EXPERIMENT_ID` and ignores `sealed_dryrun`; a rehearsal artifact has lane `development`, so it cannot be mistaken for the sealed lane (and is refused on a `final_test` run). | None; run-one pins the artifact per run. |
| 8 | NOTE | The order-1 optimum (0) is a convention, not an OEIS term; order 14 and orders 1-7 are used by no lane. | None. |
| 9 | NOTE | The scouting ledger says priors resting on ledger values are labelled `(source: scouted)`; the RQ2/RQ3 priors rest on general knowledge that tables exist, not on a ledger value. | Keep; mention in the scorecard if a reviewer asks. |
| 10 | NOTE (new) | The search arm's sealed dry run re-runs the development cell outside a transaction and writes rehearsal output under `sweeps/`. | Never cite or pin anything under `sweeps/` from the dry run; the sealed number comes only from the real `--final-test` run-one. |
| 11 | NOTE (new) | `calls.budget_calls: 5000` is per run (dev 2,400, sealed 1,200); study-wide live calls are about 7,200 including the salted re-query replication; `--replay` never counts. | Report about 7,200 as the study's live-call total, not 3,600 or 5,000. |
| 12 | NOTE (new) | `verify.py` is modified in the worktree and uncommitted; the METHOD gate hashes it, so the hashed bytes must be these (sha256 above). It must not change afterwards. | Commit before `klein gate record method`. |

No BLOCKER is open: the instance is deterministic and hashed, the optima match OEIS
revision #130, are pinned in the verifier and are attainable by independently checked
rulers, the verifier takes its lane from the notary (`KLEIN_EVALUATION_KIND`) and its
oracle from its own hashed source, rejects every planted fault (old and new) and
accepts every valid object, shares no checking code with the
searcher, the sealed lane does not reach any prompt or decision, and no literal partition
seed exists.

## Clean-room leakage audit

Performed after the verifier tests were finished, reading `study.yaml`, `prepare.py`,
`instance.json` and this profile (plus the verifier and searcher named in the brief);
`program.md` was not read. Modality `none`: the table-leakage rows read N/A with the
reasons below, and the verifier card above is the audit.

| Check | Pass/Fail/N-A | Evidence |
|---|---|---|
| 1. Target leakage | N/A | no features; the nearest analogue, optima reaching a prompt or a decision, was checked by reading `search.py`: book-keeping only, absent from every prompt |
| 2. Lookahead | N/A | nothing is fitted; no encoder, imputer or scaler exists |
| 3. Split contamination | N/A | `split.kind: none`, no rows; lanes are disjoint order sets (8-11 vs 12-13) with disjoint seed blocks; `kleinlib.leakage` itself reports N/A for kind none |
| 4. Eval-harness sanity | PASS (hand-made controls) | direction `higher` matches `optima_matched`; an all-`null` artifact scores 0 matches; forged and invalid artifacts are rejected; see the controls above |

## Go / no-go

**Rationale:** the prepared instance is deterministic (two runs, identical sha256) and
every field is traced; the optima for orders 8-13 (34, 44, 55, 72, 85, 106) match OEIS
A003022 revision #130 and are attainable under the independent verifier; the verifier is
exact, independent of the searcher, and passed every positive and negative control with
the expected exit codes (2 for rejects, 0 for valid); the budget is 2,000 candidate
evaluations per (order, trial) on both arms; the sealed lane is absent from prompts and
search decisions; seeds derive from the instance's seed blocks. Four WARNs travel with
the study, all kept from the previous version (1 narrowed, 3 re-sourced to Shearer's
tables): self-reported budget in the mutable surface (1), sealed orders are public and
possibly memorised (2), optimality is literature-based and not distributed.net's (3),
and the budget is matched by candidates, not information (4). NOTEs 5-9 are kept (6 and
7 strengthened); notes 10-12 are new. Neither review hole remains open. No BLOCKER is
open. A record of the gate should carry these cautions in its note.

> **Decision:** **GO-WITH-CAUTIONS**
