# Program — 24-golomb-llm-vs-search

## Roster

Who is doing what, and on what. REFEREE cites this table for the independence rung
(`references/referee-protocol.md`); a blank `experimenter` row caps the achievable
rung at "fresh session", because no artifact then says what ran the loop. Fill the
experimenter row at CONSULT and update a row whenever its model, tool or session
changes.

| Role | Who (model · tool · session) | Since |
| --- | --- | --- |
| consultant | lead agent (Claude Code orchestrating session) — drafted the contract | 2026-11-03 |
| instrument builder | general-purpose subagent · Claude Code — wrote prepare.py, search.py, verify.py; made no model call | 2026-11-03 |
| experimenter | `klein-experimenter` subagent (Sonnet tier) · Claude Code · a fresh subagent context per phase | 2026-11-03 |
| data-gate auditor | `klein-data-auditor` subagent (Sonnet tier) · Claude Code | 2026-11-03 |
| method scholar | `klein-method-scholar` subagent (Opus tier) · Claude Code | 2026-11-03 |
| synthesist | `klein-synthesist` subagent (Opus tier) · Claude Code | 2026-11-03 |
| referee | `klein-referee` subagent (Opus tier, claude-opus-5-5) · Claude Code · fresh context that never saw the loop (rung vs the experimenter: different model; rung vs the synthesist: fresh session only — both Opus tier in Claude Code, referee note 8) | 2026-11-03 |
| lead | lead agent, acting on the repository owner's delegation | 2026-11-03 |

**Acknowledgements are delegated.** The repository owner approved the Klein 2.3 plan
that commissions this exhibit, and that approval delegates the CONSULT, DATA, METHOD
and phase acknowledgements of exhibits 20-24 to the lead agent; each is recorded as
`--acknowledged-by lead-agent` with this note, the convention studies 10-15 used.
The referee verdict is never delegated: it is the referee subagent's own.

This is the living lab notebook. `study.yaml` is the machine contract;
`study_state.json`, `events.jsonl`, and `runs/E####/manifest.json` are generated audit
state and must not be hand-edited.

## Goal and track contract

- Goal: At a matched budget of verifier calls, does an LLM proposing Golomb rulers as data match the known optimal lengths (OEIS A003022) as often as a classical randomized search, on development orders n = 8-11 and sealed orders n = 12-13 — and is a match search or recall?
- Tracks (both registered, one per arm, each with the SAME declared verifier):
  - `search` — a classical randomized construction + local search;
  - `llm` — `qwen-flash-2025-07-28` proposes rulers as JSON data (never code), 10 per request, told
    the searcher's verdict on its previous batch.
  Both spend exactly 2,000 candidate evaluations per (order, trial); `verify.py`
  (outside the surface, hashed at METHOD) re-checks every reported ruler with exact
  integer arithmetic and prints `optima_matched` — the number of (order, trial) pairs
  whose best VERIFIED ruler has the OEIS A003022 optimal length — and, for the LLM arm,
  `first_batch_matches` (a recall signature). The verifier's number decides every run.
- Language: a matched optimum is "matched", never "proved optimal" or "discovered" —
  optimality is OEIS's (exhaustive search by others), not this study's.
- Predictions P1-P5 are registered in study.yaml with arithmetic rules.

## Data and split

- Source: none (modality `none`). `prepare.py` writes `data/prepared/instance.json` —
  the orders, trials, the 2,000-evaluation budget, the LLM batch size, the OEIS optima
  with their source and check date, and the seed blocks — frozen at the DATA gate.
- Lanes: development orders 8-11; sealed orders 12-13, read once per arm.
- Gate 1 records the prepared-data SHA-256 and split-policy fingerprint.

## Instrument notes (before DATA)

- `instance.json` (sha256 717e406c…) is deterministic; OEIS A003022 re-checked on
  2026-11-03 (revision #130) — values unchanged; order 1's 0 is the one-mark convention.
- Search arm: both ends fixed at 0 and n^2 with n-2 random interior marks, then repeatedly aim one below the best valid
  ruler (cut empty unit cells, anneal interior marks to remove repeated differences),
  restart from the best after 150 evaluations without a valid ruler; each candidate
  checked costs one of the 2,000 evaluations.
- LLM arm: each proposal is one request (system + user), repeating the previous batch
  with the searcher's verdicts and the best length so far, labelled "proposal k of 200";
  each (order, trial) loop runs on a worker pool of `calls.max_workers`, with the trial
  as the ledger's `sample`. Extraction is lenient (inner lists are recovered from malformed JSON) and validation is strict: nothing is sorted, shifted or repaired.
- The searcher reads the optima only to report the first optimal proposal and its
  provisional count; they never enter a prompt or a search decision. The verifier
  re-derives everything and its number decides (tolerance 0).
- The verifier additionally refuses incomplete lane coverage, more evaluations than the
  budget, a track/arm mismatch, a first-batch ruler shorter than the stored best, and a
  verified length below the tabulated optimum. Its `wall_seconds` is its own, so the
  wall-clock guardrail checks the verifier; `max_run_seconds` bounds the search.
- The instrument builder exercised the full path on TOY orders 5 and 6 (outside both
  lanes) and with a fake transport; nothing about orders 8-13 was searched or scored.
- 2026-11-03 — one connectivity request (lead): "Reply with the single word OK." with
  `enable_thinking: false` at the top level of the body — accepted ("OK", 1 token).
  Not about rulers; recorded here because the consult gate is already recorded.
- The LLM sealed dry run answers from the ledger only, so the LLM development cell runs
  before it; dry-run artifacts go to `sweeps/solution_DRYRUN_<track>.json`.

## Lead decisions after the DATA/METHOD review (2026-11-03, before any study call)

- Decision: the verifier carries its own PINNED oracle (orders per lane, trials, budget,
  batch size, OEIS optima for orders 8-13) and refuses an instance.json that disagrees
  with it: instance.json is gitignored and the mutable search.py runs with write access
  before the verifier reads it (review finding). The verifier also refuses an artifact
  whose lane differs from the partition the run was judged on — `KLEIN_EVALUATION_KIND`,
  which `klein run-one` now passes to every declared verifier (framework fix fcadacf) and
  `klein replicate` already did. Tested: right lane scores; wrong lane either way, a
  missing kind, a tampered optimum and a tampered budget all exit 2.
- Decision: pin the model to the dated snapshot `qwen-flash-2025-07-28` (served).
- Note: `budget_calls` is a per-run cap; study-wide live calls are about 7,200 including
  the salted re-query replication (a `--replay` never counts as one).
- Note (METHOD gate, recorded for the referee): the scholar checked the method on TOY
  orders 5-7 only (seeds 1-20, budget 2,000): the classical search reached the optimum in
  20/20, 20/20 and 9/20 trials; no lane order was searched and no model was called.
- Decision (lead, after the re-check): the verifier also requires each pair to report
  exactly the 2,000-evaluation budget (both arms always spend it) and the artifact to name
  the run being verified (KLEIN_EXPERIMENT_ID); its docstring now describes the pinned
  oracle. `sweeps/verifier_checks.py` re-runs nine checks (right lane both ways, wrong lane
  both ways, missing kind, another run's artifact, a short budget, a tampered optimum, a
  tampered budget) — 9/9 pass. Framework fixes this study prompted: verifiers run with
  PYTHONSAFEPATH=1 (no import from the searcher's directory) and a replication of a
  verifier track is judged by the verifier on the replica's artifact (3ceabe8).
- Note: the sealed dry run of the search arm re-runs the development cell outside a
  transaction (rehearsal output, under sweeps/); it is never citable evidence.

## Phases and registered predictions (mirror of study.yaml)

| Phase | Cells | Predictions |
| --- | --- | --- |
| development | search · orders 8-11; llm · orders 8-11 (3 trials each) | P1 — search <= 6/12; P2 — llm >= 9/12; P3 — llm first-batch matches >= 6 |
| confirmation | search and llm · sealed orders 12-13, after dry runs | P4 — search 0/6; P5 — llm >= 3/6 |

## Workflow

1. `uv run --locked klein gate record consult --study . --acknowledged-by <name>`
2. Prepare data and write a `Decision: GO` data card; record the DATA gate.
3. Write the method card; record the METHOD gate.
4. Commit gate evidence, switch to `experiments/24-golomb-llm-vs-search`, and run
   `uv run --locked klein preflight --study .`.
5. `uv run --locked klein run-one --study . --track <search|llm> --tests P# --description ...`
   (the declared verifier runs second and decides).

Every candidate is committed before execution. Discards and crashes remain resolvable
commits; the evidence transaction then restores `search.py` to the pre-candidate
base commit.

## Decisions (append-only)

- 2026-11-03 — schema-v3 study scaffolded from recipe `math-verify`, retyped
  test · none · math (two registered arms instead of one optimizing frontier).
- 2026-11-03 — Decision: the budget is matched in CANDIDATE EVALUATIONS (2,000 per
  order and trial), not in wall time or model calls: the LLM spends 10 per proposal.
- 2026-11-03 — Decision: P3 asks whether matches are recall (in the first batch) — the
  optimal rulers to order 28 are tabulated publicly, so a match is evidence of retrieval
  as much as of search, and the findings must keep the two apart.
- 2026-11-03 — Decision: `policy.realized_split: advisory` — the study has no rows; its
  sealed lane is a set of orders in instance.json, fingerprinted at the DATA gate.

## Phase slates

At every phase start, run the slate ritual (references/phase-ritual.md):
propose 4-6 falsifiable candidates, score novelty / testability / expected
information 1-3, record the table and the chosen candidate here, and mirror
the ranked survivors into playbook.md "Next-best candidates".

### Phase development slate (2026-11-03)

Registered track: the candidates are cells, not ideas to rank away; both are run.

| # | Candidate cell (falsifiable) | Novelty 1-3 | Testable 1-3 | Info 1-3 | Sum |
| --- | --- | --- | --- | --- | --- |
| 1 | search arm, orders 8-11 x 3 trials, 2,000 evaluations; tests P1 (optima matched <= 6/12) | 1 | 3 | 3 | 7 |
| 2 | llm arm (qwen-flash-2025-07-28), orders 8-11 x 3 trials, 200 x 10 proposals; tests P2 (>= 9/12) and P3 (first-batch matches >= 6) | 3 | 3 | 3 | 9 |

Chosen: both, in order E0001 (search) then E0002 (llm). Mirrored into playbook.md.

## Development phase results (2026-11-03)

- E0001 (search, measured): verifier optima_matched = 0/12, first_batch_matches 0, invalid_best 0.
  Best verified length vs OEIS optimum: n=8 41/38/40 vs 34; n=9 56/54/56 vs 44; n=10 80/83/77 vs 55;
  n=11 111/105/106 vs 72 (trials 0/1/2). P1 supported (0 <= 6).
  Note: the searcher stayed 4-7 marks above the optimum even at n=8, far from the METHOD-gate toy result
  (orders 5-7 reached optima 20/20); the gap grows with order. Not a bug claim; flagged for the referee.
- E0002 (llm): CRASH at 613 of ~2,400 calls (calls/E0002-000.jsonl.gz): the endpoint returned HTTP 429
  ("exceeded your current request limit") under the max_workers pool; the exception propagated and no
  artifact or verifier block exists (metric NA). 613 calls, 585,586 tokens (387,966 in / 197,620 out).
  Crash class: provider rate limit, not a code bug. Per instructions, NOT retried. P2 and P3 remain open.
- Phase max_experiments (2) is exhausted; an LLM re-run needs the lead's decision (lower calls.max_workers
  or a retry/backoff in search.py, plus a new experiment allowance).
- Decision: no prediction was refuted in this phase (P1 supported; P2, P3 open after the crash), so no
  refutation Decision line is owed.

- 2026-11-03 — Decision (lead, at the development boundary): E0002 (llm) crashed on an HTTP
  429 rate limit from the provider after 613 of ~2,400 calls — the ledger's transport
  retried three times over 14 s, too short for a per-minute limit. Framework fix: the
  transport now backs off to a 60 s cap over 8 attempts and honours Retry-After (commit
  "the call ledger waits out a rate limit"). Contract: `calls.max_workers` 6 -> 2, the
  development phase's `max_experiments` 2 -> 3 and `budget_seconds` 7200 -> 10800, so the
  pre-registered LLM cell can run once more as E0003; E0002 stays in the ledger as a crash.
  No prediction, rule, track or cell changed; consult re-recorded with this reason.
- Note for the referee: E0003 asks exactly the requests E0002 asked first, so its first
  613 calls are answered from E0002's pinned shard (identical requests, genuine recorded
  responses); `manifest.usage.calls_cached` will show it. The sampling is the provider's
  either way; nothing about the cell changes.
- Note for the referee: the classical search's development results (E0001: 0/12 matched,
  best lengths 38-111 vs optima 34-72) are far from the METHOD-gate toy calibration (orders
  5-7, 20/20, 20/20, 9/20). Both are the same algorithm at the same budget; the gap is the
  hardness growth from order 7 to 8+, reported as such, not as a defect.

- 2026-11-03 — E0003 (llm rerun with backoff transport, max_workers 2): CRASH, metric NA. A
  ConnectionResetError (errno 104, peer reset) on the HTTPS read escaped the transport (the backoff
  covers HTTP 429, not a socket reset). manifest.usage: 523 live calls + 613 cache hits from E0002's
  shard, 513,333 tokens (338,950 in / 174,383 out). No artifact, no verifier block; P2 and P3 stay open.
  Not retried per the lead's instruction. Crash class: network, not a code bug in the ruler logic.
  Development phase now has 3 experiments used (E0001 measured, E0002 crash, E0003 crash). Candidate
  fix for the lead: treat connection resets/timeouts as retryable in the ledger transport, and allow a new run.
  No refutation, so no refutation Decision is owed.

- 2026-11-03 — Decision (lead): E0003 crashed on a ConnectionResetError raised while a
  response was read (after 523 new calls; 613 were answered from E0002's shard). urllib
  raises that bare, not as URLError, so the transport's retry loop missed it. Framework
  fix: dropped connections, timeouts and HTTP protocol errors now back off and retry like
  a 5xx (commit "the call ledger retries a connection dropped mid-response"). Contract:
  development `max_experiments` 3 -> 4 so the pre-registered LLM cell runs once more as
  E0004 (it will answer its first 1,136 requests from the E0002/E0003 shards — identical
  requests, genuine recorded responses). E0002 and E0003 stay in the ledger as crashes.
  Consult re-recorded with this reason.

- 2026-11-03 — E0004 (llm rerun after E0003's dropped-connection crash, backoff on resets): measured.
  Verifier: optima_matched 6/12 (reported 6, verified 6), first_batch_matches 1, invalid_best 3, pairs 12,
  evaluations 24,000. manifest.usage: 1,264 live calls + 1,136 cached (2,400 total), tokens 1,388,003
  (893,189 in / 494,814 out), usd 0, wall 3,292 s. Unparsed replies 593 of 2,400 (valid rulers 719).
  Best verified length vs optimum, trials 0/1/2 (first proposal index at the optimum in brackets):
  n=8 34/34/34 vs 34 (1, 70, 34); n=9 none valid in any trial vs 44 (invalid_best, 0 valid rulers; unparsed 53/62/58);
  n=10 70/70/70 vs 55 (not matched); n=11 72/72/72 vs 72 (2, 74, 11). Unparsed per pair n=8 44/48/56,
  n=10 47/47/49, n=11 28/59/42.
  Recall signature: first_batch_matches 1 (only n=8 trial 0, proposal 1; n=11 trial 0 first matched at proposal 2).
  Every n=8 first batch opens with the same prefix 0,1,4,9,15,22,32 and the n=10 and n=11 bests are nested
  prefixes of the optimal 11-mark ruler (0 1 4 13 28 33 47 54 64 70 72) - consistent with retrieval or recall of a
  tabulated ruler, but this study cannot separate that from search; a match is a match, not evidence of reasoning.
  Language: optima "matched", never "found".
- Decision (2026-11-03): P2 refuted (6 < 9): the LLM arm matched 6 of 12 pairs, fewer than the 9 registered.
  P3 refuted (1 < 6): the first-batch recall signature appeared in 1 of 12 pairs, not >= 6. Reading: on orders
  8-11 the LLM matched more pairs than the search (6 vs 0) but not as often as predicted, and the match is not
  concentrated in the first batch - so the registered recall account of P3 is not supported; matches arrived later,
  after the searcher's feedback (proposals 2-74), though recall of partial structure remains possible. Order 9
  and 10 stayed unmatched. This is development-lane evidence; confirmation orders 12-13 remain unspent.

### Phase confirmation slate (2026-11-03)

Registered track: cells, all run; each sealed access is spent once after its dry run.

| # | Candidate cell (falsifiable) | Novelty 1-3 | Testable 1-3 | Info 1-3 | Sum |
| --- | --- | --- | --- | --- | --- |
| 1 | search arm sealed orders 12-13 x 3 trials; tests P4 (optima matched = 0/6) | 1 | 3 | 3 | 7 |
| 2 | llm arm sealed orders 12-13 x 3 trials; tests P5 (>= 3/6) | 3 | 3 | 3 | 9 |
| 3 | replicate E0001 (deterministic) | 1 | 3 | 2 | 6 |
| 4 | replicate E0004 (salted re-query, counts for confirmation) | 2 | 3 | 3 | 8 |

Order: dry runs first (search, then llm), real search, wait for study 20 to be idle, real llm, replications.

## Confirmation phase results (2026-11-03)

- Dry runs (exit 0, "sealed dry-run OK ... nothing spent"): search rehearsed on development orders (0/12), llm
  answered offline from the ledger (6/12, 2,400 cached calls). Artifacts under sweeps/.
- E0005 (search, sealed orders 12-13, measured): optima_matched 0/6, invalid_best 0. Best length vs optimum
  (trials 0/1/2): n=12 138/133/138 vs 85; n=13 164/166/164 vs 106. P4 supported (0 <= 0).
- E0006 (llm, sealed orders 12-13, measured): optima_matched 0/6, first_batch_matches 0, invalid_best 6: NO valid
  ruler in any pair (valid_rulers 0; unparsed replies 265 of 1,200, the other replies parsed but all violated the
  Golomb property). Usage 1,200 calls, 0 cached, 1,523,219 tokens (951,747 in / 571,472 out), wall 3,587 s.
  P5 refuted (0 < 3).
- Decision (2026-11-03): P5 refuted. On orders 12-13 the LLM arm matched none of 6 pairs and produced no verified
  ruler at all, against the registered >= 3. With P2 and P3 refuted on development (6/12 matched, 1/12 first batch),
  the account that the model matches optima at scale is not supported; its development matches (n=8 and n=11, plus
  nested prefixes of the tabulated 11-mark ruler) did not carry to n=12-13, which fits retrieval of short tabulated
  rulers more than search, though this study cannot prove either reading. Search also matched 0/6 (P4 supported).
- Replications: E0001 reproduced, difference 0, tolerance 0 [exact] (record runs/E0001/replications/20261103T090037Z.json;
  block keys outside tolerance: evaluations, restarts). E0004 reproduced via a salted re-query of 2,400 live calls,
  difference 0, tolerance 0 [exact] (record runs/E0004/replications/20261103T090054Z.json): optima_matched 6/12 again;
  other block keys differed (first_batch_matches 2 vs 1, invalid_best 2 vs 3, valid_rulers 788 vs 719, unparsed 531 vs 593),
  so the count of 6 reproduced but not the pair-by-pair detail.

- 2026-11-03 — Decision: P2 refuted by E0004 (6 of 12 < 9): the registered expectation that the LLM arm matches 9 or more development pairs is withdrawn; replicated at 6/12 by the E0004 replication.
- 2026-11-03 — Decision: P3 refuted by E0004 (first_batch_matches 1 < 6): the recall-in-first-batch account is not supported on development orders.
- 2026-11-03 — Decision: P5 refuted by E0006 (0 of 6 < 3): the LLM arm's development matches did not carry to sealed orders 12-13; no verified ruler was produced there.

## Referee notes answered (Gate 3 recorded at 57611b9, PASS-WITH-NOTES)

Answered by the synthesist on 2026-11-03. Each line answers the note of the same number in
`referee_report.md`. The earlier log lines above stay as written, because the notebook is
append-only.

- 2026-11-03 — Referee note: 1 (C7, "unique optimum") — **accepted.**
  - Erratum E1 was filed with `klein claims erratum`. It re-scopes C7, whose locked text
    is unchanged and whose strength stays exploratory.
  - The re-scope: the optimum is unique up to reflection at n=8, and n=11 has two optima.
  - `tables/synthesis_derive.py` now also checks every E0004 proposal. The only rulers at
    the tabulated length are the printed rows in printed orientation; the mirror images and
    the second 11-mark optimum were never proposed.
  - findings §③ now reads identity as weak, non-zero, post-hoc information, not
    "uninformative", and §⑥'s "two optima" slip is corrected.
- 2026-11-03 — Referee note: 2 (C5, "no valid ruler") — **done.** The recount now runs
  from the pinned shard `calls/E0006-000.jsonl.gz`, pinned as `art:calls_E0006`. It uses
  this file's own Golomb check, and `search.py` is never imported.
  - E0006: 11395 lists with n marks, 0 valid, under both the generous and the strict
    reading.
  - E0004 cross-check: the strict recount equals the searcher's 719. The generous reading
    finds 185 more valid rulers, all in valid-JSON replies wrapped in objects, which the
    never-repair rule scores invalid.
  - No pair's best length or first optimal proposal changes under the generous reading.
  - New numbers e6_ledger_valid_any, e6_ledger_lists_n and e4_ledger_valid_strict are
    added to the lock. C5 gains `art:calls_E0006`.
- 2026-11-03 — Referee note: 3 (C2's re-query sources) — **done.** findings §① now names
  the source of each number:
  - first-batch 2 and the primary 6 are the verifier's `replicate_block`;
  - valid 788 and unparsed 531 are the searcher's `searcher_block`, not verified.
- 2026-11-03 — Referee note: 4 (control labels) — **done in findings and here.** Labels
  used: positive control = a known-valid input the verifier must accept (the tabulated
  rulers, scoring 12/12 and 6/6); negative control = a known-invalid input it must reject
  (planted, forged, wrong-lane and tampered artifacts). The data card, which is gate-hashed
  and not edited, uses the swapped labels. These controls test the verifier only, not
  either arm.
- 2026-11-03 — Referee note: 5 (sealed replication) — **recorded.** The lead tried
  `klein replicate E0005 --verify-only` and the same for E0006. The engine refuses both by
  design, with no override: it would be a second look at the sealed partition
  (`kleinlib/replicate.py` `_refuse_unreplicable`). So C1 and C5 rest on the development
  replications rep:E0001 and rep:E0004, which is the protocol's only option, plus the
  notary's own verifier run on each sealed artifact (reported equals verified). findings §①
  says so.
- 2026-11-03 — Referee note: 6 (Carlini sentence) — **done.** §⑥ now reads "consistent
  with the memorization-scales-with-capacity account of ref:carlini2023, but untested here
  (C7)".
- 2026-11-03 — Referee note: 7 (n=8 prefix) — **acknowledged.** The development-phase log
  line "Every n=8 first batch opens with the same prefix 0,1,4,9,15,22,32" is inaccurate.
  The prefix opens trials 0 and 2 only; trial 1 opens 0 1 3 7 12 20 29 38. See the
  correction in findings §③ ("A correction to the program's prose"). The log line is left
  as written.
- 2026-11-03 — Referee note: 8 (synthesist independence) — **recorded in the Roster's
  referee row.** Relative to the experimenter the rung is "different model". Relative to
  the synthesist it is "fresh session" only, because both are Opus tier in Claude Code.
- 2026-11-03 — Referee note: 9 (tutorial and figures) — **acknowledged.** The Gate 3
  verdict does not cover `report/index.html` or any figure; none existed when it ran.
  findings §⑦ says so. The TUTORIAL stage needs its own check.
- 2026-11-03 — Referee note: 10 (minor items) — **done.**
  - (a) `art:sol_E0001` is added to C1's evidence cell in findings, matching the lock.
  - (b) The earlier phrase "block keys outside tolerance: evaluations, restarts" for
    rep:E0001 means those keys are *absent* from the verifier's block, so the tolerance
    comparison could not cover them. They are not different: in the replica's
    `searcher_block` they equal the original (evaluations 24000, restarts 94).
  - (c) The ~7,200 planned study-wide live calls versus 6000 recorded is explained by the
    record (findings §④, under C10). The first pass cost the planned 3,600, because the
    development reruns re-used earlier shards (613 + 523 + 1264). The planned sealed
    re-query (~1,200) could not happen, because sealed runs are not replicable. That leaves
    3,600 + 2400 re-query.
