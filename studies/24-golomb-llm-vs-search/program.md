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
| referee | `klein-referee` subagent (Opus tier) · Claude Code · fresh context that never saw the loop (rung: different model than the experimenter) | 2026-11-03 |
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
  - `llm` — `qwen-flash` proposes rulers as JSON data (never code), 10 per request, told
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
- Search arm: n random marks on length n^2, then repeatedly aim one below the best valid
  ruler (cut empty unit cells, anneal interior marks to remove repeated differences),
  restart from the best after 150 evaluations without a valid ruler; each candidate
  checked costs one of the 2,000 evaluations.
- LLM arm: each proposal is one request (system + user), repeating the previous batch
  with the searcher's verdicts and the best length so far, labelled "proposal k of 200";
  each (order, trial) loop runs on a worker pool of `calls.max_workers`, with the trial
  as the ledger's `sample`. Parsing is strict: nothing is sorted, shifted or repaired.
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
  optimal rulers to order 27 are tabulated publicly, so a match is evidence of retrieval
  as much as of search, and the findings must keep the two apart.
- 2026-11-03 — Decision: `policy.realized_split: advisory` — the study has no rows; its
  sealed lane is a set of orders in instance.json, fingerprinted at the DATA gate.

## Phase slates

At every phase start, run the slate ritual (references/phase-ritual.md):
propose 4-6 falsifiable candidates, score novelty / testability / expected
information 1-3, record the table and the chosen candidate here, and mirror
the ranked survivors into playbook.md "Next-best candidates".

### Phase <id> slate

| # | Candidate (falsifiable) | Novelty 1-3 | Testable 1-3 | Info 1-3 | Sum |
| --- | --- | --- | --- | --- | --- |
