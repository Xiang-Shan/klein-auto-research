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

### Phase <id> slate

| # | Candidate (falsifiable) | Novelty 1-3 | Testable 1-3 | Info 1-3 | Sum |
| --- | --- | --- | --- | --- | --- |
