# Program — 20-llm-cot-contamination

## Roster

Who is doing what, and on what. REFEREE cites this table for the independence rung
(`references/referee-protocol.md`); a blank `experimenter` row caps the achievable
rung at "fresh session", because no artifact then says what ran the loop. Fill the
experimenter row at CONSULT and update a row whenever its model, tool or session
changes.

| Role | Who (model · tool · session) | Since |
| --- | --- | --- |
| consultant | lead agent (Claude Code orchestrating session) — drafted the contract | 2026-11-03 |
| instrument builder | general-purpose subagent · Claude Code — wrote lib/twins.py, lib/prompts.py, prepare.py, the first analyze.py; made no model call | 2026-11-03 |
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

- Goal: Does chain-of-thought prompting raise a hosted small model's exact-match on GSM8K, and does the gain survive on procedurally generated fresh twins of the same problems (a contamination probe)?
- Tracks (both registered, both arms in one cell so every comparison is paired):
  - `cot_gain` — `em_gain` = exact-match(CoT) − exact-match(direct) on the same items,
    with a paired bootstrap interval (cluster bootstrap over templates on twin blocks);
    `em_direct`, `em_cot` and McNemar's exact p are printed beside it.
  - `contamination` — `em_gap` = mean over templates of (CoT score on the GSM8K
    original − CoT mean on its fresh twins); lower is better (no memorization signature).
- Model: `qwen-flash` on DashScope's OpenAI-compatible endpoint, temperature 0, thinking
  disabled; every request and response pinned by the call ledger (`calls/`), so the study
  replays offline. Budget: 6,000 calls / 4M tokens (hard stops). Costs are reported in
  calls and tokens copied from `manifest.usage`; no price is pinned, so no dollar figure.
- Predictions P1-P6 are registered in study.yaml with arithmetic rules.
- Results are exploratory until each track's sealed twin-block cell and a replication
  record confirm them (`confirmation.require: [sealed, replicate]`).

## Data and split

- Source: GSM8K test (1,319 items, MIT), bundled at `datasets/gsm8k-test/` (sha256 in its
  README), plus procedurally generated twins from `lib/twins.py` (50 templates written
  from GSM8K items chosen by a fixed permutation; each template must reproduce its
  original's gold answer exactly).
- Lanes (predefined split on `index.csv`): train = the 50 template originals (scored only
  by the contamination cells); development = a 300-item public GSM8K sample + twin block
  A (seed 20261104, 4 per template); test = twin block C (seed 20261105) — SEALED.
- Adaptive work uses train + development only. The sealed block is read once per track.
- Gate 1 records the prepared-data SHA-256 and split-policy fingerprint.

## Instrument notes (before DATA)

- 50 templates from the first 56 permutation candidates; 6 skipped (5 with too few
  well-posed twins in 0.5x-2x, 1 with an ambiguous gold answer). Every template
  reproduces its GSM8K question byte-for-byte and its gold answer exactly.
- Twins never reuse the original's answer (a memorized number cannot score on a twin);
  the sealed block is disjoint from the development block by construction.
- Identical requests are answered once: a CoT request on a twin shared by the
  contamination and cot_gain cells is one ledger entry (temperature 0). Cells are
  therefore not independent re-queries of each other; the salted re-query replication
  is the independent one.
- The sealed DRY run answers only from the ledger and writes no table, so it spends
  nothing; it needs the development twin answers recorded first (P3, P4 run before it).
- 2026-11-03 — one connectivity request (lead, for study 24's instrument): "Reply with
  the single word OK." with `enable_thinking: false` top-level — accepted. Not a GSM8K
  item; recorded here because it confirms this study's PARAMS are accepted.
- 2026-11-03 — Decision: CONSULT re-recorded before any run to (a) say the call and
  token caps are per run, and (b) add scouting entry S4 (templates were written from
  GSM8K items). No prediction, rule, track or phase changed.

## Lead decisions after the DATA/METHOD review (2026-11-03, before any study call)

- Decision: pin the model to the dated snapshot `qwen-flash-2025-07-28` (served — checked
  with the trivial "Reply with the single word OK." request); the alias can be repointed
  by the provider mid-study. Every call also records `model_served`.
- Decision: the twin sampler draws slot values LOG-uniformly within [v/2, 2v] (median ≈
  the original) instead of linearly — the review measured twins ~1.3x larger than their
  originals, which would bias `em_gap` upward — and forbids degenerate draws (a fraction
  of 1/1, a zero quantity, a multiplier of 1 where the original's step was non-trivial).
- Decision: the public GSM8K block excludes the skipped template candidates (7 after the fix; one, gsm-288,
  has a gold answer the instrument shows to be wrong); it is the next 300 permutation items
  that are neither sources nor skipped.
- Decision (pre-registered replication tolerances, before any run): a salted re-query
  replication of a `cot_gain` cell reproduces when |Δ em_gain| <= 0.03, of a
  `contamination` cell when |Δ em_gap| <= 0.05 (`klein replicate --tolerance`). The 0.01
  resolution in the contract is the metric's resolution, not a reproduction bar: the METHOD
  review estimates temperature-0 serving noise alone fails it in roughly half to two thirds
  of re-queries (method_card.md §4).
- Note: on twin blocks `mcnemar_p` treats the 4 twins of a template as independent and
  overstates the evidence; the cluster bootstrap interval is the inference there.
- Decision: the mechanized text near-duplicate audit FAILs BY DESIGN (each twin is a
  number-swapped copy of its own template original, which sits in train); if the re-run
  audit shows every hit is own-template, the DATA gate proceeds by
  `klein gate override data --reason`, the protocol's route for a reasoned exception.

## Lead decisions after the second review (2026-11-03, before any study call)

- The fixed sampler is in place: 50 templates, 7 skipped, 57 candidates consumed (t0096
  retired by the degeneracy guards, t0805 templated in its place); index.csv sha256
  a36b5e35…, split fingerprint printed by the smoke. Twin answers are now 1.13x (dev) and
  1.29x (sealed) their originals at the median (they were 1.31x / 1.33x); the remaining
  drift comes from answers that must stay positive (t1281, t0466, …), not from the sampler.
- Decision: the replication tolerances are made MECHANICAL — each track's
  `minimum_delta` is its pre-registered tolerance (cot_gain 0.03, contamination 0.05), the
  value `klein replicate` uses when no `--tolerance` is passed. CONSULT re-recorded.
- Decision: 5 of the 50 template sources are GSM-Symbolic templates (t1264, t0116, t0976,
  t1031, t1088 — byte-identical questions in apple/ml-gsm-symbolic, read at branch main,
  no commit SHA pinned): number-swapped variants of them are public. The template set is
  NOT changed; the contamination cells' pinned per-template tables let findings report the
  45-template split descriptively (n=5 is too small for a test). Likewise a
  magnitude-matched sensitivity (dropping the templates whose answers must grow) is
  descriptive, from the same tables.
- Decision: the DATA gate proceeds by `klein gate override data --reason`: the mechanized
  text near-duplicate rows FAIL by design (every hit is a twin against its OWN template
  original or a twin of the same template), proved by the auditor's block-pair matrix and
  re-checked by an adversarial reviewer; no cross-template and no GSM8K-public hit.

## Phases and registered predictions (mirror of study.yaml)

| Phase | Cells | Predictions |
| --- | --- | --- |
| anchor | cot_gain · public GSM8K sample | P1 — direct EM <= 0.85; P2 — CoT gain >= 0.10 |
| twins | contamination · originals vs twin block A (CoT); cot_gain · twin block A | P3 — gap <= 0.05; P4 — gain >= 0.10 |
| confirmation | sealed twin block C, both tracks, after dry runs | P5 — gain >= 0.10; P6 — gap <= 0.05 |

## Workflow

1. `uv run --locked klein gate record consult --study . --acknowledged-by <name>`
2. Prepare data and write a `Decision: GO` data card; record the DATA gate.
3. Write the method card; record the METHOD gate.
4. Commit gate evidence, switch to `experiments/20-llm-cot-contamination`, and run
   `uv run --locked klein preflight --study .`.
5. Set the cell in `analyze.py` (`CELL`, the lane), then
   `uv run --locked klein run-one --study . --track <cot_gain|contamination> --tests P# --description ...`.

Every candidate is committed before execution. Discards and crashes remain resolvable
commits; the evidence transaction then restores `analyze.py` to the pre-candidate
base commit.

## Decisions (append-only)

- 2026-11-03 — schema-v3 study scaffolded from recipe `llm-eval`, typed test · text · llm.
- 2026-11-03 — Decision: compare the two prompt arms INSIDE one cell (paired on the same
  items) rather than one arm per cell, so the gain and its McNemar test are printed keys
  the notary adjudicates.
- 2026-11-03 — Decision: the contamination probe is template-paired (GSM-Symbolic design):
  each fresh twin keeps its original's wording and arithmetic structure and changes only
  the numbers, validated by an exact solver against the original's gold answer.
- 2026-11-03 — Decision: model outputs are committed under `calls/` as AI-generated
  evaluation records. Terms read 2026-11-03 (Model Studio Service Agreement, effective
  2026-09-02, cl. 4.3.1 / 4.6 / 6.2.1 / 7.5): API data is the customer's; generated content
  must be labelled when published; outputs may not train competing models. The stricter
  service-specific clause on TRIAL outputs (evaluation use only, no third-party sharing)
  is flagged to the repository owner, who decides whether the shards are pushed publicly.

## Phase slates

At every phase start, run the slate ritual (references/phase-ritual.md):
propose 4-6 falsifiable candidates, score novelty / testability / expected
information 1-3, record the table and the chosen candidate here, and mirror
the ranked survivors into playbook.md "Next-best candidates".

### Phase anchor slate (2026-11-03)

| # | Candidate (falsifiable) | Novelty 1-3 | Testable 1-3 | Info 1-3 | Sum |
| --- | --- | --- | --- | --- | --- |
| 1 | cot_gain on the 300-item public GSM8K sample, CELL gsm8k, tests P1 (em_direct <= 0.85) and P2 (gain >= 0.10) | 2 | 3 | 3 | 8 |
| 2 | cot_gain on development twin block A (CELL twin_dev; P4) | 2 | 3 | 2 | 7 |
| 3 | contamination, originals vs twin block A (P3) | 3 | 3 | 3 | 9 |
| 4 | salted re-query replication of the anchor | 1 | 3 | 2 | 6 |

Chosen: #1 (the phase allows one experiment and it is the identity anchor; #2-#3 belong to phase twins, #4 to confirmation).

## Anchor phase outcome (2026-11-03, experimenter)

- E0001 (cot_gain, CELL gsm8k, --tests P1,P2): CRASH, not retried. Reason: one request
  returned HTTP 429 (`limit_requests`, DashScope rate limit) and `kleinlib/calls.py`
  `openai_chat` raises on it without retry or backoff; 599 of ~600 calls had been made and
  pinned (`calls/E0001-000.jsonl.gz`; 172,657 tokens), so no em_gain / em_direct / em_cot /
  mcnemar_p was printed and P1, P2 stay open. This is an infrastructure fault (a bug in
  the harness path, not a bad idea). max_workers: 8 against this account's request limit.
- Observation from the pinned shard (direct arm, 300 requests, prompt "Answer with the
  final number only."): the model does NOT comply. Median direct response is 289 chars,
  294 of 300 exceed 25 characters, and responses begin with worked reasoning ("Amalia took
  4 hours ... 4 + 2 = 6 hours"); mean output 144 tokens vs 266 for the CoT arm. Only 6 of
  300 are bare numbers. So the "direct" arm is closer to a terse CoT, which will shrink
  em_gain and make P1 (em_direct <= 0.85) likely refuted for an instrument reason, not a
  model-ability reason. Also 2 CoT responses hit finish_reason=length at max_tokens 1024.
- Open for the lead (not changed by the experimenter): (a) rate-limit handling (retry with
  backoff in calls.py, or lower calls.max_workers) before re-running; (b) whether the
  direct-arm compliance finding warrants a prompt/extraction change (lib/prompts.py) before
  the anchor is re-run; any such change is a deliberate instrument edit, outside the
  per-experiment diff. Decision: no prediction is refuted (none adjudicated); no rerun by
  the experimenter.

- 2026-11-03 — Decision (lead): E0001 crashed on HTTP 429 (`limit_requests`) after 599 of
  ~600 calls, despite the ledger's backoff (8 attempts over ~3 min): eight concurrent
  workers here plus study 24's on the same account kept it over the request limit.
  `calls.max_workers` 8 -> 2; the anchor phase gets one more slot (`max_experiments` 1 -> 2,
  `budget_seconds` 3600 -> 7200); the re-run (E0002) starts only after study 24's LLM cell
  has finished, and answers its first 599 requests from E0001's pinned shard. E0001 stays
  in the ledger as a crash. Consult re-recorded.
- 2026-11-03 — Decision (lead): the experimenter's read of E0001's responses shows the
  direct arm does NOT comply with "Answer with the final number only." (6/300 bare numbers;
  median 289 characters; working shown). The registered prompt is NOT changed: response
  lengths were seen (no score was computed), and changing the instrument now would adapt it
  to observed outputs. So P1/P2 measure the registered INSTRUCTION, not answering without
  reasoning; findings must say so and report compliance (share of bare-number replies,
  output tokens per arm) from the pinned ledger.

## Anchor rerun outcome (2026-11-03, experimenter)

- E0002 (cot_gain, gsm8k, --tests P1,P2, rerun after E0001's 429 crash): measured. 599 calls
  were cache hits, 1 new call; usage 182 tokens new (75 in / 107 out); 600 calls total
  across the two shards. em_gain = 0.01 (paired item bootstrap CI [-0.01, 0.03]),
  em_direct = 0.95, em_cot = 0.96, McNemar exact p = 0.5078 (6 CoT-only vs 3 direct-only
  discordant of 300).
- Decision: P1 REFUTED (em_direct 0.95 > 0.85). The registered number-only instruction
  is not followed, and the model is strong on this sample; the prior (0.55-0.85) was too low.
  Prediction left as registered; not rewritten.
- Decision: P2 REFUTED (em_gain 0.01 < 0.10; the CI excludes 0.10). CoT adds nothing
  detectable on the public sample because the direct arm already reasons (below) and both
  arms sit near ceiling. Consequence for the twins phase: P4 (gain >= 0.10 on twins) is
  now a priori unlikely for the same reason; it stays registered and is run as is.
- Direct-arm compliance (both pinned shards, 600 unique requests; bare = reply is only a
  number): direct arm 4/300 bare (1.3%), median output 112.5 tokens (mean 143.5), 4/300
  cut at max_tokens; CoT arm 0/300 bare, median 243 tokens (mean 265.7), 2/300 cut at
  max_tokens. So the "direct" arm is a terse CoT (about 0.46x the CoT tokens), which
  explains the near-zero gain. Reported, prompt not changed (lead decision).

### Phase twins slate (2026-11-03)

| # | Candidate (falsifiable) | Novelty 1-3 | Testable 1-3 | Info 1-3 | Sum |
| --- | --- | --- | --- | --- | --- |
| 1 | contamination cell: CoT on 50 originals vs 200 development twins, template-paired (P3: gap <= 0.05) | 3 | 3 | 3 | 9 |
| 2 | cot_gain on development twins, CELL twin_dev (P4: gain >= 0.10) | 2 | 3 | 2 | 7 |
| 3 | descriptive splits of the P3 table (GSM-Symbolic overlap 5 vs 45; magnitude-matched) | 2 | 2 | 2 | 6 (not a run; read from the pinned table) |

Chosen: #1 then #2 (the phase's two experiments); #3 is read-only. Expectation: both arms near ceiling, so P3 likely supported and P4 likely refuted.

## Twins phase outcome (2026-11-03, experimenter)

- E0003 (contamination, CoT, 50 originals vs 200 development twins, --tests P3): measured.
  em_gap = 0.02, bootstrap-over-templates CI [-0.015, 0.060]; em_original 0.98, em_twins 0.96;
  250 calls (0 cached), 99,352 tokens (22,960 in / 76,392 out). P3 SUPPORTED (0.02 <= 0.05),
  but the CI upper end 0.06 exceeds 0.05, so the data do not exclude a gap above the bound.
  Only 5 of 50 templates differ between original and twin mean (t0906, t1088, t1183, t1046:
  original right, twins 0.5-0.75; t1179: original wrong, twins 0.5).
- Descriptive splits from tables/contamination_E0003.tsv (no new predictions):
  GSM-Symbolic overlap (t1264, t0116, t0976, t1031, t1088; n=5): original 1.00, twins 0.95,
  gap 0.05 (one template, t1088, drives it). Other 45: original 0.978, twins 0.961, gap
  0.017. Magnitude-matched (excluding t1281, t0466; n=48): original 0.979, twins 0.958, gap
  0.021; excluding both the 5 and the 2 (n=43): gap 0.017. No split moves the gap beyond
  0.05; n=5 is too small to test.
- E0004 (cot_gain, CELL twin_dev, 200 twins, --tests P4): measured. em_gain = -0.025,
  cluster-bootstrap CI [-0.065, 0.005]; em_direct 0.985, em_cot 0.96; McNemar p 0.125 (treats
  twins as independent, overstated); discordant CoT-only 1, direct-only 6. 200 calls (200
  cached CoT hits from E0003, 200 new direct), 48,642 tokens. Direct arm on twins: 0/200 bare
  replies, median output 120.5 tokens, 2/200 cut at max_tokens.
- Decision: P4 REFUTED (em_gain -0.025 < 0.10; CI excludes 0.10). CoT does not raise EM on
  twins; the point estimate is slightly negative (direct 0.985 vs CoT 0.96), the direct arm
  again reasons freely and both arms are at ceiling. The gain null of the anchor (0.01)
  replicates in direction on fresh items. P5 is expected to fail the same way.
- Note: CELL in analyze.py now stays "twin_dev" at HEAD (committed before E0004 so the run
  was not on an unchanged surface); the lead should reset it deliberately if a gsm8k cell is
  needed again. Sealed cells ignore CELL.

- 2026-11-03 — Note (lead, twins boundary): the experimenter committed `CELL = {"block":
  "twin_dev"}` in analyze.py BEFORE E0004 instead of letting `run-one` file it as the
  candidate, so E0004's candidate diff is empty; the cell it ran is the committed HEAD and
  the manifest records it. Disclosed for the referee; no evidence is affected.

### Phase confirmation slate (2026-11-03)

| # | Candidate (falsifiable) | Novelty 1-3 | Testable 1-3 | Info 1-3 | Sum |
| --- | --- | --- | --- | --- | --- |
| 1 | sealed cot_gain on twin block C, after dry run (P5: gain >= 0.10) | 2 | 3 | 3 | 8 |
| 2 | sealed contamination on twin block C, after dry run (P6: gap <= 0.05) | 3 | 3 | 3 | 9 |
| 3 | salted re-query replications of E0002 (tol 0.03) and E0003 (tol 0.05) | 2 | 3 | 3 | 8 |
| 4 | offline --replay of E0002 (never counts) | 1 | 3 | 1 | 5 |

Order: dry runs first, then sealed cot_gain, sealed contamination, replications. Expectation: P5 refuted (ceiling, as P2/P4), P6 likely supported.
