# Changelog

All notable changes to Klein Auto Research. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[SemVer](https://semver.org/); since 1.0.0 the study schema (v2), the `klein`
CLI surface, and the ledger formats are stable — breaking changes mean a major
version.

## [Unreleased]

### Added

- **Opt-in process-verifiable generation layer — the spine** (`klein generation
  init | check | verify | label | status | recover`). A schema-3 study may now record
  what it committed to BEFORE the evidence existed: an immutable opt-in manifest
  anchored ahead of the CONSULT gate, one admission receipt per action binding the
  intended action and the exact bytes of `entrypoint.mutable`, and a separate audit
  (`generation/verify_receipt.json`) that classifies every run in scope as
  `admitted | unadmitted | refused-but-run | mismatched | replayed`. Order is
  established by three local witnesses — the extension hash chain, a core-chain
  anchor, and git ancestry — never by a clock. A refusal is written and committed
  like an admission, so ignoring one is detectable. The dual-pass
  `generation-verified` label requires the core `klein verify` receipt AND the
  generation receipt to pass at the same HEAD, and `findings.md` to quote it.
  Protocol: `.claude/skills/klein/references/generation-protocol.md`; template:
  `.claude/skills/klein/assets/generation-manifest-template.yaml`.
- The capability vocabulary (`expertise, slates, premortem, parity, contribution,
  surprise, escalation, knowledge, benchmark, design`) and its dependency table are
  encoded. Opting in with `capabilities: []` buys the admission discipline and the
  chronology witnesses, and nothing that scores research; each capability below is
  declared explicitly at `klein generation init`. This release supports all ten; a
  name a build cannot check is still refused as *not available* — a different message,
  and a different problem, from a typo — which is what a study meets when it is
  carried back to an older Klein.
- **Capability registration hooks.** A capability now plugs into the generation spine
  by registration (`kleinlib/generation/registry.py`: a name, admission rules, one
  verify family; `capabilities.py`: the modules this version ships), never by editing
  `admission.py`, `verify.py` or `label.py`. A capability the manifest does not declare
  is not consulted; one it declares that this version cannot run FAILs
  `generation manifest`. Families report `integrity` (is the record intact) and
  `outcome` (what the research got) separately — the label copies the outcome, the
  spine judges only the integrity — and a study with `capabilities: []` runs no family,
  so its receipt is byte-for-byte the one the spine already produced.
- `Capability.receipt_inputs` — a registered capability may FILL one of the admission
  receipt's six existing `inputs` slots (`slate`, `premortem`, `parity`, `cells`,
  `design`, `benchmark`) beside the spine's own `manifest` — the `slates` capability, for
  instance, pins the lock's object sha in `inputs.slate`. The receipt's key set stays the
  spine's — no capability may add a key — and a study that declares nothing gets the
  receipt it always got.

The ten capabilities follow, in the order the spine loads them — dependencies first.

<!-- WP-01 -->
- **The `expertise` capability — acquire the domain, then prove you acquired it**
  (`klein generation expert lock | amend | bind | repair | review`). A declaring study
  freezes `domain_card.md` before the CONSULT gate — pipeline, metrics, doctrine,
  pitfalls, incumbent, a `method_shortlist[]` that precedes METHOD, and a baseline
  recipe with numeric targets — then executes that baseline as an ordinary `run-one`
  transaction admitted with `--action baseline`. `expert bind E####` recomputes each
  target from the run's printed metric block and records `reproduced | mismatch |
  crash`; **until a bind reproduces, no `run` or `sealed` admission is granted.** A
  failed reproduction is fixed by a versioned `expert repair` naming the changed files
  and their hashes (never the declared verifier), verified afterwards against those
  files at the next bound run's candidate commit. Targets are frozen at version 1: an
  amendment that moves one is refused, because lowering a bar you did not clear is a
  successor study, not a repair. The capability outcome is `incomplete` (label-eligible
  — an honestly open obligation is a WARN, never a FAIL), `source-reconstructed`, or
  `independent-review` when a recorded review carries a session-receipt hash and a
  reviewer who is not `program.md`'s roster experimenter. Protocol:
  `.claude/skills/klein/references/expert-protocol.md`; template:
  `.claude/skills/klein/assets/domain-card-template.md`.
- **Reference records** (`klein generation reference record`) — write-once, repo-level
  `knowledge/references/<id>.json` carrying the locator, the one statement the work is
  cited for, the hash of the bytes that were read, whether they were retained, and the
  verification basis (`read-at-source > bibliography > abstract-only > hash-only`),
  each basis enforcing its own consistency rule. Klein copies no bytes: the hash goes
  into git, the source stays where it is. On an `expertise`-enabled study a
  `references.yaml` row saying `verified: true` without a resolvable `record_id` FAILs
  verification. Protocol:
  `.claude/skills/klein/references/reference-protocol.md`.
<!-- end WP-01 -->

- **Hypothesis slates and forecast calibration** (the `slates` capability;
  `klein generation slate lock | amend | score | show`). A generation-enabled study may
  now record each phase's 4–6 authored candidates in `slates/<phase>.yaml`, give each a
  permanent `<study>#Hn`, admit a run with `klein generation check --hypothesis` (which
  binds the run to the row and refuses unless `--tests` covers the row's `success_P`),
  and at phase end compute the Brier score, Murphy decomposition, base-rate skill and
  best/worst bounds of the forecasts it wrote — into
  `generation/tables/slate_calibration_<phase>.tsv`, pinned as
  `art:slate_calibration_<phase>`. A locked forecast is immutable (an edit fails
  verification for the life of the study); a revision is an amendment scored in its own
  panel; the cohort denominator is frozen at lock, so withdrawal and perpetual deferral
  report as coverage below 1.0 and outcome `conditional`, never as a better Brier; a
  `provenance: scouted` row is descriptive and never calibration. Verification recomputes
  every number from the receipts, the manifests and the core chain. **Nothing generates,
  scores, ranks or selects a candidate** — the 1–3 axis scores are validated and copied,
  and the phase ritual is still not automated. Protocol:
  `references/generation-protocol.md` "Slates and calibration"; template:
  `.claude/skills/klein/assets/slate-template.yaml`.
<!-- WP-09 -->
- **Evidence design — what the evidence is FOR, locked before the DATA gate**
  (`klein generation design lock`, capability `design`). A declaring study freezes
  `evidence_design.yaml` into the extension chain before Gate 1: the Question's estimand,
  population, units, measurement process, identification assumptions and intended
  generalization; the Prediction's uncertainty method, validity conditions, practical
  threshold and provenance; the Evidence's representations, dependency hierarchy,
  permitted reuse, seal and acquisition ledger; the Claim's warrant (`prediction |
  conditional-estimation | causal-inference | exploratory-structure | checked-witness`);
  and the Decision's typed continuation with its predecessor and successor. **Every
  validity condition must reach the arithmetic:** its `rule_ref` names a registered `P#`
  carrying an `inconclusive_if` rule or an `all_of`/`any_of`/`not` combinator — a plain
  leaf comparison and a prose `inconclusive_if` are both refused, and the cross-check is
  re-run at every `generation verify` against `study.yaml` as it is now, so dropping an
  `inconclusive_if` after the lock is caught. **Import chronology is not acquisition
  chronology:** an `acquisition[]` entry with `kind: import` records when bytes arrived,
  while `kind: acquisition` claims when the measurement was taken and is refused without
  a `custody` chain and a named `attested_by` (testimony, never verified). A `--action
  cell` admission is refused until the design is locked; the capability outcome is
  `locked` or `unlocked`, and a late lock (`--allow-late`) FAILs `design lock`
  permanently. The artifact supplements the five objects and changes no id grammar and no
  engine rule. Protocol: the "Evidence design" section of
  `.claude/skills/klein/references/generation-protocol.md`; template:
  `.claude/skills/klein/assets/evidence-design-template.yaml`.
<!-- end WP-09 -->
- **Slate-time pre-mortem** — the `premortem` capability (`klein generation
  premortem record | respond`), a recorded red team between the draft slate and the
  first run. `record` binds the sha256 of the DRAFT slate lock, the reviewer, a hashed
  bundle of exactly the inputs the reviewer was handed, and the issues — each
  `{id, target, severity, kind, text}`, with the reviewer's own further fields copied
  verbatim; `respond` binds one disposition per issue. A `blocking` + `mechanical`
  issue must be `accept`ed with the hash of a NEW slate version descended from the
  reviewed draft, or `klein generation check --hypothesis` is refused naming the issue
  ids; a `scientific` objection may be rejected with a rationale, because the reviewer
  supplies arguments and never a veto. **Nothing scores or ranks**: there is no
  quality score for an issue and no comparison between candidates. A review recorded
  after the phase's hypotheses ran FAILs; the reviewer's name matching `program.md`'s
  roster `referee` FAILs — the proposal critic is not the closing referee; independence
  is `self-attested` until a session receipt is hashed into the record, and Klein calls
  no model to produce the review. The input bundle is recomputed at verify time from
  the commit that introduced the record, and an answered review is immutable. The
  generation spine's `generation orphans` family additionally FAILs an object file
  whose bytes no longer hash to its own name. Protocol:
  `.claude/skills/klein/references/premortem-protocol.md`; template:
  `.claude/skills/klein/assets/premortem-template.yaml`.
- **Expert parity and contribution ledger** — two more registered capabilities.
  `parity` (`klein generation parity lock | amend | bind | assess | show`) turns "the AI
  matched the expert" into a commitment made before the evidence: `parity.yaml` is locked
  at CONSULT with both pipelines and their selection rules, the sampling unit and
  dependence block, the matched budget rule, and every metric's direction, estimand,
  measured-floor reference, noninferiority margin and **written margin rationale** — set
  by someone who is not the roster's experimenter, and tied to a registered prediction
  whose rule must be exactly `L_<key> >= -margin`, so the notary decides the same
  inequality the assessment does. `parity bind` pins the scorer's hash, both frozen
  snapshots and every measured floor, and a registered admission rule refuses
  `--action sealed` on **any** track until it exists (deferral D-2). One sealed
  registered cell measures; `parity assess` recomputes `d/L/U` from the cell's own pinned
  `tables/parity_units.tsv` and applies the rule — **exceeds / at least parity / refuted
  / inconclusive**, mutually exclusive by construction, with an undefined metric never
  passing and A4 §7's by-δ check reported as `agreement_within_floor`, never as parity.
  Verification recomputes the same numbers from the same bytes and fails on a scorer or
  snapshot that differs at the sealed candidate commit, on a second sealed run of the
  comparison track, and on a locked metric the cell never printed or declared undefined.
  `kleinlib.generation.stats.simultaneous_bounds` is the arithmetic: a block-bootstrap
  max-t on per-block sums, pure numpy, deterministic under its seed — simultaneous bounds
  under the declared block structure, not a p-value and not FWER control beyond this
  registered family. `contribution` (`klein generation contribution record | show`)
  appends `ai_value.jsonl` and seals each line's hash into the chain; coverage counts
  every slate row and every hypothesis admission, rejections included, an accepted row
  with no human acceptor is recorded as agent-accepted and never promoted, and the
  outcome stays `descriptive` unless the parity lock cites a matched frozen-2.0 ablation
  study. Protocol: `references/expert-parity-protocol.md`; templates:
  `.claude/skills/klein/assets/parity-template.yaml` and `assets/parity_score_template.py`.
<!-- WP-07 -->
- **The escalation ladder and successor studies — getting unstuck, accounted
  for** (`klein generation escalate lock | record | close | pivot | show`, capability
  `escalation`). A declaring study freezes `escalation_plan.yaml` before the CONSULT
  gate: the triggers a stall is RECONSTRUCTED from — `consecutive_discards` through the
  `stop:` rule's own counter, `headroom_closed` through the same `kleinlib.decision`
  helpers `run-one` enforces on, `budget_exhausted` against a phase's registered
  `max_experiments` — the five rungs in one fixed order (metric diagnosis → method
  family → data leverage → adjacent-field analogy → human expert, with `stop` always
  available from anywhere), unit-bearing budgets over compute/person-time/money/samples,
  and `stop`/`pivot` as terminal actions. **Once a trigger trips, no `run` or
  `--hypothesis` admission is granted** until a `<study>#Dn` decision citing it is
  recorded after the tripping run — and the discharge is scoped to that count, exactly
  like `klein stop ack`. Each decision names the rung, the lower rungs skipped WITH
  REASONS (a silent skip is refused), the concrete changed resource or assumption, the
  estimated cost and the condition that would close it; `close` adds the outcome and the
  actuals, where a unit that cannot be measured is `unknown` with cost evidence rather
  than omitted. Verification recomputes every count from the manifests, re-derives the
  episode from the chain, FAILs an unaccounted rung, an open decision that outlived
  `evidence_window`, a budget passed without a prior `extend-budget` decision, and a
  pivot whose `old_contract_sha256` is not `study.yaml` at the pivot's own commit —
  **editing the locked threshold cannot discharge a stall**. `escalate pivot` links a
  successor study with both contract hashes, the exposure it inherits (spent seals, the
  development partition, scouted ids) and every `#Hn`/`#Sn` id handed over; the
  successor cites it back with `generation init --predecessor … --successor-receipt …`,
  and its `escalation predecessor` check reads the receipt out of the predecessor's
  store. A successor id restores no blindness. The capability outcome is
  `none | escalated | stopped | pivoted`, reported beside its integrity. **The verb
  neither chooses a rung nor launches, schedules or retries work** — whether the work
  under a rung label deserves it stays the referee's judgement, which is why the changed
  resource is written down. Protocol:
  `.claude/skills/klein/references/escalation-protocol.md`; template:
  `.claude/skills/klein/assets/escalation-plan-template.yaml`.
<!-- end WP-07 -->
<!-- WP-08 -->
- **Cross-study knowledge — transactions over pinned evidence** (the
  `knowledge` capability; `klein generation knowledge promote | contest | resolve |
  query | decide | show`). The markdown under `knowledge/` keeps its typed claim
  citations and is never rewritten; beside it, a **repo-level** store of write-once
  `knowledge/objects/<sha256>.json` and an append-only `knowledge/events.jsonl`
  chain answers what prose cannot. `promote` imports a claim only if `klein claims
  verify` passes on its study NOW, copies `class`, `strength` and `evidence_roots`
  **verbatim** — a promotion creates availability, never stronger evidence — and
  deduplicates by evidence roots, so one lesson repeated across ten studies is one
  piece of evidence. `contest` attaches contradicting evidence from the citing
  study's own verified lock and requires at least one CLAIM: **a prediction that
  failed to transfer is a prediction verdict, not a refutation.** `resolve` appends
  `upheld | scoped | withdrawn` and deletes nothing. Before the CONSULT ack, `query`
  records the consultation receipt — contract draft hash, pinned `store_head`,
  retriever version, typed query, COMPLETE hits (no top-k unless `--limit`, which is
  recorded), **each hit's contest closure whatever it would have scored**, and a
  use/reject reason for every one, or an explicit `no_match` so that an empty store
  is consulted rather than skipped. Retrieval is `lex-1`: deterministic case-folded
  token overlap, no embeddings and no model call, chosen because `generation verify`
  replays the recorded query against the store at `store_head` via `git show` and
  FAILs any difference as a suppressed hit or contest. The family also FAILs a late
  consultation, an undecided hit, a broken store chain, a deleted transaction, an
  unresolvable source hash (a foreign origin WARNs), and a strengthened copy.
  `scripts/seed_knowledge_objects.py` seeds a repository from the citations already
  in `knowledge/**/*.md` — dry-run by default, read-only over the markdown, skipping
  any study whose lock does not verify, with scope fields left empty for human
  curation. Protocol: `.claude/skills/klein/references/knowledge-protocol.md`.
<!-- end WP-08 -->
<!-- WP-06: surprise -->
- **Surprise mining — registered discovery cells, three table templates, `<study>#Sn`
  receipts** (`klein generation surprise register | record | show`, capability
  `surprise`, which requires `design`). A study screening many segments now records the
  DENOMINATOR: `discovery_cells.yaml` freezes the search space after METHOD and before
  any cell evidence — template, statistic, adapter and inputs (hashed from disk by
  `register` and pinned back into the file), partition (never `sealed`), unit and group
  policy, the complete segment inventory, `minimum_n`, and a declared multiplicity rule.
  **A measured effect floor is refused as one:** a floor answers "bigger than noise on
  ONE comparison", so a screen declares `family_maxt` (`kleinlib.metrology.family_maxt`
  over both signs of every segment), `bonferroni`, or a threshold from a registered null
  sweep. Three table producers ship as library code a study entrypoint imports —
  residual-by-segment, error slices, family disagreement — and the pinned table is PER
  UNIT, because a sign-flip max-t acts on units and a summary-only artifact could not be
  recomputed. A cell runs through ordinary `run-one --tests P#` (admitted with
  `--action cell --cell <id>`, whose `--tests` must include the cell's registered
  expectation); `surprise record --run E####` re-reads the pinned table, recomputes every
  segment of the frozen inventory, makes a slice below `minimum_n` `inconclusive` rather
  than `null`, and issues one `<study>#Sn` receipt per violation while retaining the null
  and inconclusive segments in a complete inventory object and a derived
  `generation/tables/surprise_<cell_id>.tsv`. **Explanations are never invented:**
  a receipt reads `unresolved` until a driver types one, and `--explain SEGMENT=TEXT`
  records that as testimony. The `surprise` verify family recomputes the record from the
  pinned bytes and FAILs on a late first registration, an edited registry, an adapter or
  input that differs today or at the run's candidate commit, a sealed-partition cell run,
  an omitted eligible segment, an admitted cell run that was never recorded, and a
  `confirmed` claim resting on a cell table or an S receipt — a screen selects what to
  look at and cannot also confirm it. A bare `S#` in findings §③ WARNs, because the
  scouting ledger already uses that token. Protocol:
  `.claude/skills/klein/references/surprise-protocol.md`; templates:
  `.claude/skills/klein/assets/discovery-cells-template.yaml` and
  `.claude/skills/klein/assets/discovery_cell_template.py`.
<!-- end WP-06 -->
<!-- WP-05 -->
- **Planted-truth benchmark and custody receipts** — the `benchmark`
  capability (`klein generation benchmark commit | submit | reveal | retire | show`),
  plus one verb group that belongs to no capability at all,
  `klein generation custody attest`. `commit` freezes `benchmark.yaml` after the
  CUSTODIAN's METHOD gate and before any participant access: it hashes the public
  bundle, computes `sha256(salt ‖ private-bundle bytes)` beside `sha256(salt)`, pins
  the scorer and the participant-facing submission schema, and freezes the arms and
  their budgets, the hypothesis cap, the false-positive penalty, the matching rule,
  the per-arm recovery predictions and the **disjoint** development/sealed seed
  blocks. The salt never enters the repository. `submit` validates each arm's ranked
  structures against the schema and the cap and files the participant's own bytes as
  `submissions/<arm>.json`; `reveal` recomputes the commitment once every arm has
  submitted or carries a recorded missing trial that stays in the denominator — **a
  mismatch is refused AND recorded** as `benchmark_reveal_failed`, and fails the audit
  from then on. Scoring is an ordinary sealed `run-one` on a registered track: ONE
  cell over all arms, pinning `tables/benchmark_scores.tsv`, which verification
  recomputes row by row by re-applying the locked matching rule to the same
  submissions and the same revealed truth. The machine decides variables (as a set),
  relationship and sign; the fourth condition, *context*, is a preregistered sentence
  the custodian adjudicates and records per row as `context_ok`, and verification
  takes that column rather than pretending to derive it. Each planted truth is
  recovered once — a later structure matching it is a duplicate, one matching nothing
  is a false positive the declared penalty is charged against. The family also FAILs a
  scorer that is not the pinned one at the scoring cell's candidate commit, a second
  sealed scoring cell, and a `confirmed` claim resting on the in-silico table
  (R-INV-6). **A hash is not secrecy**: `custody attest` records a NAMED holder's
  statement about accounts, containers or machines, stored with `testimony: true` and
  reported as testimony; without one the outcome reads `unverified`, which fails
  nothing. A benchmark known to have leaked is retired and its results are retained.
  Protocol: `references/planted-truth-protocol.md`; templates:
  `assets/benchmark-template.yaml`, `assets/benchmark-submission.schema.json` and
  `assets/score_submissions_template.py`.
<!-- end WP-05 -->
<!-- WP-10: docs -->
- **The documentation surface says the same thing everywhere.** `AGENTS.md` and
  `CLAUDE.md` carry the layer in one paragraph and one verb list — no new lifecycle
  stage; `SKILL.md`'s stage table names the generation verbs used at each EXISTING
  stage; `references/generation-protocol.md` lists every verb group, the six receipt
  input slots, the dependency table, the eight verify families and the label's fields
  as the code has them, and states once what the mechanism does not establish;
  `references/inquiry-model.md` carries one table of the generation record ids
  (`#Hn`, `#Sn`, `#Dn`, knowledge objects, generation objects) and the rule that they
  reach a claim only through an `art:` alias; `references/referee-protocol.md` carries
  one "Generation addenda" subsection — the ten core checks unchanged — with a reading
  obligation per capability and the report's separate `Generation:` line, now in
  `assets/referee-report-template.md`; and
  `references/defaults-and-scaffolding.md` has a row per artifact the layer writes,
  with the verb that writes it. `scripts/tests/test_docs_integrity.py` now checks the
  `.yaml` / `.json` / `.py` templates protocols name, not only the `.md` and `.toml`
  ones, and fails a packaged asset no protocol points at — the mirror of the
  orphan-protocol check that has guarded `references/` since 2.0.
<!-- end WP-10 -->

<!-- fix-1 -->
### Fixed

- **A generation receipt refreshes at a new HEAD.** `klein generation verify` used to
  skip the rewrite whenever the new audit differed from the receipt on disk only in
  `git_head`. After any unrelated commit — a `program.md` decision, a playbook
  refresh, a framework doc — the receipt was therefore stale, re-verifying changed
  nothing, and `klein generation label` refused for the life of the study. The
  rewrite is now skipped only while the receipt is still current; two verifies at one
  HEAD still file nothing.
- **A generation commit carries generation paths only.** Every generation verb filed
  its writes through a commit scope that also prepended `study_state.json` and the
  core `events.jsonl`, so an operator's uncommitted core-state edit could be swept
  into a generation transaction. Verbs now commit exactly the paths they wrote,
  refuse to name core state or core evidence at all, and refuse to run while
  `study_state.json` or the core `events.jsonl` is dirty.
- **A study that never opted in is left untouched.** `klein generation verify` on a
  study with no manifest and no chain exits 1 and writes nothing, instead of creating
  `generation/` and filing a FAIL receipt against a study that had promised nothing.
- **A run that went ahead after a refusal says so.** It is classified
  `refused-but-run` from the newest preceding receipt, rather than `replayed` from any
  older consumed one. Both still FAIL; only one is the truth.
- **The object store refuses to complete a tamper.** Writing an object over different
  bytes under the same name raises instead of overwriting, a file that is not its own
  hash (or cannot be read) blocks every writing verb until it is restored by hand, and
  `recover` never rewrites an object.
- **The expert baseline's recipe is frozen with its targets** (R-INV-3). `expert lock`
  records the sha256 of `baseline.implementation` and `baseline.fixture`; a
  `reproduced` bind whose recipe drifted since the lock now FAILs unless a repair
  declared the change. Files inside the mutable surface are recorded but exempt.
- **A repair changes what it says it changes.** `verify` diffs the study subtree
  between the failing run and the repaired one and FAILs on any unnamed change;
  `expert repair --changed` refuses core state, run evidence and the generation
  ledger (naming a path also exempts it from the clean-tree check).
- **Every cited reference record is opened.** A record reachable only from a
  `references.yaml` row used to pass by never being looked at, and a row's
  `verification_level` may no longer claim a stronger basis than its record's
  `verification_basis`.
- **Pre-mortem independence is not asserted from an empty roster.** A missing
  `referee` row now WARNs once per phase instead of passing silently, and a recorded
  review is FAILed when the document it hashed is not the document at its own commit.
- **A declared-but-unexercised capability reports `incomplete`, not `n/a`.** `n/a` is
  the label's word for "not declared" and now comes only from the label's defaults.
- Smaller: `check --action` takes argparse `choices` from a tuple asserted equal to
  `admission.CHECKPOINTS`; an unreadable `study_state.json` is a recorded refusal
  reason rather than an empty state that would admit a spent seal; `same_actor`
  compares actor components symmetrically; docs no longer describe a manifest
  amendment feature that does not ship, and state that the label's rung is always
  `local-order` in this release.
<!-- end fix-1 -->

<!-- fix-2 -->
- **The parity outcome is one cell's, decided once, and the slate scores the first
  try.** Six behaviours of the `slates` and `parity` capabilities were tightened
  before any study could depend on them:
  - The parity outcome is now read from the **comparison track's sole sealed cell**,
    resolved from the lock, rather than from whatever was assessed most recently.
    `parity assess --run` refuses a sealed run on any other track, and an assessment
    naming one FAILs `parity assessment` without displacing the comparison's verdict.
  - The sealed comparison cell must **ask the notary the questions the lock
    registered**: `generation check --action sealed` on the comparison track is
    refused unless `--tests` names every parity prediction, and `parity cell` FAILs a
    comparison run whose manifest carries no verdict for one of them.
  - `parity bind` may only read each metric's floor **where its `floor_ref` says**.
    `--floor-run` must restate the run the lock froze, and a bound floor whose
    `source` differs from the locked reference FAILs `parity bind`.
  - A `scorer.path` inside `entrypoint.mutable` is refused by `parity lock` and FAILs
    at every verify — the checker is never the searcher (R-INV-3). A
    `scoring.scorer_name` equal to the roster experimenter is a WARN (testimony).
  - A slate row's `y` now comes from its **FIRST** admitted run, not its last, so a
    resolved row cannot be re-run into a better score. Every further admitted run is
    counted in a new `n_bound_runs` field of the score object and column of the
    calibration table, and the family WARNs when any row exceeds one. `revision_of`
    is carried forward across later amendments, so a revised forecast stays in the
    revisions panel. A row's `parent_ids` must name hypotheses this study locked.
  - Arithmetic honesty: a comparison over no metrics is `inconclusive` rather than a
    vacuous `parity`; a constant metric on unequal blocks is undefined rather than
    bounded by floating-point residue; a non-numeric, non-empty cell of
    `tables/parity_units.tsv` is an error naming its line and column instead of a
    silent NA (and the NA count is recorded). Assessment replay now compares the
    bootstrap numbers at a relative tolerance and records `numpy`'s version beside
    `n_boot` and `seed`, so a numpy upgrade is diagnosed rather than read as tampering.
<!-- end fix-2 -->

### Unchanged

- **The core notary, its receipts, and schema-2 verification.** `run-one` gains no
  call site, option, default or import; `verify_receipt.json` is byte-for-byte what it
  was and never mentions the word "generation"; a lawful core run without an
  admission keeps its disposition, its confirmation and its `finalize` label — it
  simply cannot earn the generation label. `kleinlib.generation` is imported by no
  core module and not at `kleinlib.cli` import time. Schema-2 studies are refused by
  `klein generation init` outright.

## [2.0.0] — 2026-09-03

**Process-verifiable research for AI for Science.** Klein 1.x ran a disciplined
experiment loop; 2.0 makes the whole study auditable by a stranger with no model in
the loop. A study is now TYPED on three axes — `kind` (what shape of question),
`modality` (what shape of evidence), `profile` (whose vocabulary is honest here) —
predictions are registered before their evidence and adjudicated by arithmetic inside
the run transaction, every number in the write-up has a pinned home, and an
independent referee on a different model applies a fixed ten-check rubric before the
study may close.

**Schema 2 is frozen, not migrated.** Studies 03 and 05–09 keep verifying under the
rules they were run under, byte for byte, forever; none of the schema-3 checks are
enforced on them. Version-1 studies stay readable at tag `v1.3.0`.
`docs/migration-schema2-to-3.md` is the contract diff; the short version is: do not
re-open a closed study, start a new one and cite the old one's claims.

### Added

- **The inquiry model** (`references/inquiry-model.md`): `kind ∈ {predict, estimate,
  test, simulate, replicate, discover, optimize}` × `modality ∈ {tabular, timeseries,
  image, sequence, graph, text, simulation, none}` × `profile ∈ {generic, ml-research,
  math, insurance}` or a repo-local `profile_doc`. The kind fixes the default track
  mode, what "sealed" means, what `confirmation.require` defaults to, and the strength
  a claim can reach; the modality selects the data-gate card; the profile changes
  headings, doctrine anchors, figure sets, budgets and banned words — never what the
  engine checks.
- **Schema-3 contract**: `entrypoint {command[], mutable[]}` (the mutable surface is
  declared, not assumed to be `train.py`), `tracks.<id>.mode ∈ {frontier, registered}`,
  a per-track declared `verifier` (required for `optimize`, always outside the mutable
  surface — the checker is never the searcher), `metric.exactness` (+ `exactness_note`),
  `metric.incumbent_external`, `metric.fit_noise` recorded separately from the keep bar,
  `predictions[]` with arithmetic rules, `confirmation.require ⊆ {sealed, replicate,
  verify}`, `stop`, `materiality`, and `data.modality` / `data.source` / `data.sha256`.
- **Typed scaffolding**: `klein new --kind --modality --profile --profile-doc
  --audience --track NAME[:MODE] --split-seed --schema-version`, which names the
  entrypoint by kind (train.py / analyze.py / simulate.py / search.py).
- **Contract-driven splits**: `kleinlib.data.contract_split` / `load_partition` build
  every partition from `study.yaml` alone and print a `split_fingerprint:` the DATA
  gate freezes and the notary compares — a number measured on the wrong rows is a
  crash, in either direction (war story 8).
- **The sealed dry-run**, mandatory before every real sealed run:
  `klein run-one --final-test --dry-run` rehearses the whole path on development data
  and spends no id, commit, manifest, row or seal; an entrypoint that ignores the flag
  exits 3 rather than silently passing (war story 9).
- **Registered mode** (`references/registered-mode.md`): a track that MEASURES instead
  of climbing. Runs are cells, the disposition is `measured`, `artifact:` lines pin the
  tables a cell produces (hashed into the manifest with `role: declared`), and
  guardrails are recorded rather than flipping a disposition. Three cell evaluators —
  `evaluate_estimate`, `evaluate_test`, `evaluate_table` — print the block for the
  common shapes.
- **The predictions ledger**: `klein run-one --tests P#` evaluates each named
  prediction's declarative rule on the printed block INSIDE the transaction and records
  the verdict in the manifest, in state and as an event; `klein predict list` reads the
  ledger and `klein predict adjudicate` records the verdicts only a human can close,
  pinning every path it is given by sha256. `klein finalize` refuses open predictions.
- **REFEREE, Gate 3** (`references/referee-protocol.md`): a fresh context on a
  different model, tool or person reads `findings.md` first and `program.md` last, runs
  the read-only verifiers, applies a fixed ten-check rubric and writes
  `referee_report.md` with two machine-read lines. `klein gate record referee` parses
  them, refuses a FAIL outright, and stores the independence rung; schema-3
  `klein finalize` requires the gate or `--no-referee --reason`, which labels the study
  `unrefereed` on its receipt.
- **The claims lock and the numbers law** (`references/claims-protocol.md`):
  `claims.lock` schema 2 — claims with a class, a strength and resolvable evidence, and
  numbers with a pinned artifact and a precision — produced by `klein claims
  init|pin|number|add|erratum|verify` and checked by a seven-check law (shape,
  artifacts, presence, evidence, numbers, append-only across git history, ancestry).
  Errata re-scope claims; nothing is ever removed.
- **`klein verify` grows a receipt**: `verify_receipt.json`, self-committed, carrying
  every check, the hashes of the inputs the audit read, `evidence_use_rate` and the
  evidence-use law's three numbers. `--numbers` scans `findings.md` (and, always
  advisorily, the tutorial) for numerals with no home in a pinned artifact;
  `--evidence-use` checks that every discard, crash, measured cell and registered sweep
  is cited, that every refuted prediction has a dated `Decision:` line, and that a
  `confirmed` claim rests on two kinds of evidence. The figure re-render check
  compares bytes first and, when they differ, the decoded pixels: the same image
  written through another platform's PNG encoder passes (macOS and Linux link
  different zlibs); a pixel difference fails on the platform family that rendered
  the figures and is a `[WARN]` naming both platforms elsewhere (a computed curve
  can move a pixel between arm64 and x86_64 in its last floating-point bits). The
  check leaves `figures/` exactly as it found it: a script that also writes into the
  study's own figures directory despite `--out` (the engine's trajectory plotter
  does, until 2.1) has those files judged like the rest and restored, and the
  receipt names them.
- **Metrology** (`references/consult-protocol.md` Phase 0): `klein noise-floor
  --recipe {seed-sweep, split-lottery, paired-bootstrap} --estimand {fit-noise,
  marginal-resplit, paired-comparison}` prints the contract block, the schema-3 floor
  bar is `minimum_delta >= max(2*std, range/2)`, a paired bootstrap runs under common
  random numbers, and `metrology.family_maxt` is the sign-flip family-wise guard.
  `klein sweep register` hashes a measurement sweep's sidecar and script into state so
  findings can cite it as `sweep:<name>`; `klein stop ack` records a stop rule firing.
- **`klein replicate`** (`references/replication-protocol.md`): a development run
  re-executed from its own manifest in a detached worktree (`rep:E####@<ts>`), or
  `--verify-only` re-running the declared verifier on the pinned artifact
  (`verify:E####@<ts>`), decided on a documented tolerance ladder. Records never touch
  the manifest, and `reproduced: false` is kept as evidence.
- **Data source tags** (`references/data-sources.md`): `csv: | parquet: | synthetic: |
  bundled: | hub: | sklearn: | openml: | url:`, with `data.sha256` mandatory wherever
  bytes can change and `KLEIN_OFFLINE=1` refusing a network scheme before any request.
  `klein doctor` reports what this machine can run without fetching anything;
  `KLEIN_DEVICE` overrides the mps → cuda → cpu order.
- **Modality-typed DATA gate**: a time policy for time series, a group policy for
  images / sequences / graphs / text (with `python -m kleinlib.leakage --index` over
  the split index table), a DGP card for simulations, a verifier card for
  verifier-only studies — and a literal split seed anywhere in an evaluator or
  entrypoint is a BLOCKER.
- **Bundled datasets**: the Hubble 1929 tables (two-source transcription) and a
  deterministic, sha256-pinned tiny Shakespeare corpus, both with licence notes.
- **`kleinlib` split into modules** — `errors, primitives, contract, events, manifest,
  decision, transaction, state, checks` under a thin `workflow` orchestrator — a pure
  move that left every shipped study verifying byte-identically.
- **`scripts/verify_e2e.py`**, a stdlib-only cross-platform proof with two lanes:
  the v1 compatibility path, and a schema-3 lane that walks one typed inquiry from
  `klein new` to a self-contained tutorial with the CLI and nothing else. CI runs both
  on ubuntu, macOS and Windows, plus an `exhibits` job that verifies every schema-3
  exhibit from a clean, offline checkout with `$DATA_HUB` unset.
- **Six protocol code blocks are executed by the test suite**, so a documented example
  cannot drift from the engine it describes.
- **The consult gate hashes `scouting_ledger.md`** (schema 3), making true a protocol
  sentence the engine had never honoured: the pre-registration disclosure joins
  `study.yaml` / `research_plan.md` / `program.md` in the consult record, so editing it
  after the gate fails `klein verify` until the gate is re-recorded with a reason — and
  "pre-registered" rests on a hash instead of on a commit order nobody checked. The
  ledger is OPTIONAL: `klein new` now scaffolds one, and a study that keeps none
  records `scouting_ledger: absent` on the gate event, so the absence is on the record
  too. The scaffolded `program.md` also opens with a `## Roster` — experimenter,
  data-gate auditor, referee, lead, each with model · tool · session — which the
  referee reads for the independence rung; a blank experimenter row caps that rung at
  "fresh session", because nothing else in a study says what ran the loop.

### Changed

- **The lifecycle is seven stages past four gates**: CONSULT → DATA → METHOD →
  EXPERIMENT/SWEEP → SYNTHESIZE → REFEREE → TUTORIAL. `AGENTS.md`, `CLAUDE.md`,
  `README.md` and the `/klein` skill are rewritten around it, and the agent roster
  gains `klein-referee` (which must run on a different model than the experimenter).
- **`findings.md` §⑤ and the tutorial's coding-advice heading come from the profile**;
  headline numbers in every downstream deliverable are read from `claims.lock`, not
  from prose.
- **Guardrails, floors and stop rules are disclosed rather than silent**: the floor
  block names its estimand, `fit_noise` is recorded under its own key so a seed-only
  spread can never become a keep bar, and a declared guardrail key that no evaluator
  prints is flagged at preflight.
- **`klein replicate` prepares the worktree before the clock starts**: a `uv run …`
  command gets a recorded `uv sync --locked [--extra …]` step on its own budget
  (`KLEIN_REPLICATE_SETUP_SECONDS`, default 1800 s) instead of building the project
  inside `max_run_seconds`, and the prepared DIRECTORY is copied in — not only
  `data.prepared_path` — so an entrypoint that reads a sibling `prepare.py` wrote
  still runs. Both were found by exhibit study 00.
- **A verb commits only the files it wrote.** `klein verify`, `claims`, `predict
  adjudicate`, `replicate`, `sweep register`, `stop ack` and `headroom ack` file their
  own receipts through `git commit --only` and name on stdout the tracked edits they
  declined to take (`note: N uncommitted edit(s) left in the tree (…) — not part of
  this commit`); previously each swept every modified state file into its own commit,
  so a verify on a tree with a findings draft filed that draft under a
  `klein: verify receipt (…)` subject. Gate records, `run-one` and `finalize` still
  file the study artifacts they hash — "commit before the gate", made mechanical.
  Found by the study-00 driver.
- `knowledge/` is reorganised into `knowledge/research-discipline.md` (the ten process
  lessons of studies 07–09, each with a typed claim citation) and
  `knowledge/domains/<profile>/`.
- Version and description: `2.0.0`, "process-verifiable research for AI for Science".

### Removed

- **The v1 ledger adapter and the v1-era skill entry points**: version-1 studies are
  readable at tag `v1.3.0` and are not carried forward. The legacy five-column ledger
  remains documented for historical reading.
- The v1 study-00 quickstart's CI bootstrap, replaced by a marked anchor placeholder
  that fails loudly if the new exhibit lands while the step is still a no-op.

### Compatibility

- `schema_version` selects the rule set. A schema-2 study gets exactly the checks it
  was notarized under; every schema-3 addition is either schema-3-only or an `ok=True`
  `[WARN]`. `scripts/verify_shipped_studies.py` is the guard rail, run in CI: studies
  03, 05, 06, 07, 08 and 09 report 0 failed before and after every engine change.
- `claims.lock` schema 1 (the hand-built numbers ledgers of studies 07–09) verifies
  under its own rules and is never rewritten; `klein claims init --from-legacy`
  migrates a copy for a study that is being re-opened.
- Python 3.11–3.14; `uv sync --locked` with extras named together.

### Studies published in this line

- **07 `iris-90years`** and **08 `iris-rematch`** (2026-08-26/27) — the detection-limit
  pair: a parade at h = 0.81 with no disclosure, then a door ajar at h = 1.015 with
  twenty-one challengers and zero keeps.
- **09 `iris-first-lesson`** (2026-08-27) — the claim-permission map, the 0/42 guard,
  a sealed coda spent by a crash before any data was read, and erratum E1 (a retired
  split seed hardcoded in an evaluator), which the numbers law caught a study later.
  All three were run against the untagged 1.3.0 tree and their locks therefore record
  `klein_version: "1.2.0"`; pin by commit, not by version string.
- The 2.0 exhibits (`00-known-truth-quickstart`, `10-hubble-1929-replication`,
  `11-exact-verifier-construction`, `12-insurance-claims-frequency`,
  `13-charlm-fixed-budget`) ship with this release; their headline numbers below are
  copies of values their locks pin.
  - **00 `known-truth-quickstart`** (2026-09-03) — synthetic tabular data whose
    Bayes-optimal AUC is known (0.884116 on development): three keeps closed the distance
    from 10.4555 measured floors to 1.7077, the sealed look landed 1.68 floors from the
    sealed partition's own ceiling (confirmed), the over-capacity candidate at h = 1.708
    lost 1.7903 floors (P4 refuted, decision recorded), and both `klein replicate`
    attempts failed for non-scientific reasons — the defects E13 fixed.
  - **10 `hubble-1929-replication`** (2026-09-03) — Hubble's two 1929 tables, bundled; three
    registered tracks (replicate, estimate, simulate), 13 measured cells, three sealed
    accesses (one per track): neither two-parameter fit returns 465 (423.937323 / 454.158441),
    the headline is unreproducible for missing inputs rather than method, the 24 objects support
    K = 454.158441 with a 95 % bootstrap interval 316.648582–603.704762, and a single distance
    factor of 6.056247 carries the 1929 fits to within 4.990073 of the modern 70. The first
    referee round FAILED on a spelled-out ratio the numbers scan could not see; cleared, and
    round 2 passed with notes. Its run manifests pin commits from the study branch's
    pre-rebase chain (the driving agent rebased the branch, against the protocol); the
    annotated tag `evidence/10-hubble-1929-replication` keeps those commits reachable on
    every clone, and the ledger itself is untouched.
  - **11 `exact-verifier-construction`** (2026-09-03) — the mathematics exhibit: the
    no-three-in-line problem with `search.py` as the mutable surface and `verify.py`, hashed at
    the METHOD gate, as the only source of the objective. Zero keeps by arithmetic (the best known
    value equals the proven bound, headroom 0 acknowledged before the first run); 21 of 22 from
    the development seed block and 22 from the sealed one, reported as a difference and never a
    rate; 55 of the best-known 62 on the larger grid, never called impossibility; twelve planted
    invalid objects rejected and a deliberate one-point overclaim refused as a
    `verifier_disagreement` crash. The referee found a false quantity in a frozen claim sentence
    ("sub-millisecond" against a pinned 0.002046 s), cleared by erratum, never by edit.
  - **12 `insurance-claims-frequency`** (2026-09-03) — the insurance-profile exhibit, the v1
    quickstart ported onto the bundled 58k-row claims table: all three v1 rungs reproduce
    (anchor 0.011322 from the ledger's value); the paired-comparison floor 0.0375805 is
    0.9671 of the v1 ledger's whole spread, so the ladder yields exactly one measured keep
    (the boosted tree, +0.049911) and the spline chain's 0.035956 lift is 0.9568 of a floor;
    the calibration doctrine improves Brier by a factor of 4.055; the DATA gate found 615
    row-content twins straddling the partitions — a BLOCKER the v1 study never saw,
    overridden on the record with an instrument printed on every run; the sealed level
    0.657739 holds within 0.1680 floors. The v1 quickstart directory leaves the tree with
    this study (read it at tag `v1.3.0`).
  - **13 `charlm-fixed-budget`** (2026-09-03) — the deep-learning exhibit, the autoresearch
    ancestor pattern under contract: a character-level transformer on the bundled
    tiny-Shakespeare corpus at a fixed 2000-step budget, every disposition decided by
    `verify.py` re-scoring the checkpoint (gap 0.0 against a declared tolerance of 0.01).
    None of the four registered levers cleared the paired floor of 0.0149525 nats (weight
    tying cost −11.3693 floors); cosine decay, the one lever without a prediction, gained
    +3.3326 floors; the sealed final tenth came back 3.140679 floors harder, so the study
    confirms a level (1.56628 nats per character) and never a gap. Needs `--extra deep`;
    the main CI verifies its ledger, the weekly job re-runs two anchor cells on CPU.

## [1.3.0] — 2026-08-26

The detection-limit release — merged as `9f87a01` on 2026-08-26 and used by studies
07, 08 and 09, but **never tagged and never recorded here at the time**; the tag
`v1.3.0` was created retroactively on 2026-09-02 with a message naming that defect,
and this entry was reconstructed from the merge. The tree at the tag still says
`version = "1.2.0"` in `pyproject.toml`, which is why the three studies' claims
locks record `klein_version: "1.2.0"`. Pin by commit, not by version string.

### Added

- `metric.bound {ideal, on_infeasible ∈ {ack, warn, block}}` per track and
  `noise_floor.estimand ∈ {marginal-resplit, paired-comparison}` (required once a
  floor block exists beside a declared bound).
- Headroom `h = (incumbent − ideal) / minimum_delta`, computed and disclosed at
  `klein preflight` and `klein verify`, enforced at `klein run-one`: the default
  posture refuses development runs on a keep-infeasible frontier (`h < 1`) until
  `klein headroom ack --note "re-scope: … | run-anyway: …"` records the closed door
  (hash-chained event, self-committed). Nine dedicated tests.
- War story 7 (the sub-zero keep bar, study 07), SKILL Hard Rule 6, the AGENTS.md
  detection-limit invariant, the README headroom section, and the consult-protocol
  headroom bullet.

### Notes

- Born from study 07's parade at h = 0.81 with no disclosure; first exercised by
  study 08 (door ajar at h = 1.015; twenty-one challengers, zero keeps) and armed for
  the first time by study 09 (`bound` declared; h = 0.33, door closed before any
  challenger).

## [1.2.0] — 2026-08-01

The typeset release: the two frictions the 05/06 arc filed are fixed in the
engine, and generated tutorials gain build-time typeset mathematics and
highlighted code — with the zero-network CSP contract byte-identical. All four
public exhibits are re-authored to the new convention and rebuilt; their prose
numbers are unchanged (verified by numeric-multiset diff against the previous
pages).

### Added

- Tutorial builder: build-time math and code rendering. LaTeX authored in empty
  `data-math` / `data-math-display` elements is typeset to inline SVG glyph
  paths (ziamath, STIX Two Math outlines; no fonts shipped, no runtime script —
  `font-src 'none'` and the single-hash `script-src` stand, and the browser
  netlog CI fixture now exercises math and code forever). Pygments highlights
  `language-…` code blocks with pinned dual-theme styles, and
  `<pre data-code="train.py">` includes the winning script BY REFERENCE — the
  included bytes are guaranteed to be the committed file's, so a hand-paste
  can no longer drift (using the idiom remains the spec checklist's job). New
  builder exit codes: 5 math render, 6 code include, 7 renderer dependency
  missing. New dependencies: `pygments`, `ziamath`, `latex2mathml`.
- `klein preflight` check `"guardrail visibility"`: warns when a declared
  guardrail metric is neither auto-printed by the framework
  (`kleinlib.schema.AUTO_PRINTED_METRIC_KEYS`) nor named anywhere in the
  study's Python sources.
- A ledger-derived seal guard in `klein run-one --final-test`: a sealed access
  recorded in the hash-committed manifests refuses a second access even if
  `study_state.json` was edited afterwards.

- Study `06-hurricane-gqls-returnlevels` (fourth public exhibit): from-scratch
  reproduction of Adjieteh (2024) §6.2.2 — gQLS loss-model fitting on the 30
  most-damaging US hurricanes (Pielke-Landsea 1998; the 30-row dataset is
  bundled under `datasets/`, making this the repo's most reproducible study).
  Sealed evidence is the thesis's own published Table 6.10 grid (120 parameters,
  reproduced at 0.002 mean absolute deviation) plus its exact 10× contamination,
  under which the study's decision incumbent (trimmed gQLS-lognormal, wide trim)
  holds the 1-in-100 event loss to 0.0% while untrimmed MLE moves +99.4%. The
  loop's reproduction ladder discovered the thesis's own ch. 2 quantile
  convention via an honest guardrail breach, localized a typo in one printed
  Table 6.9 cell, and recorded that the best-fitting family (log-Cauchy, no
  finite moments) is decision-degenerate at this sample size.
- Bundled dataset `hurricane_top30_pl1998` (30 rows, provenance-documented,
  including the source's own "1925–95"-vs-1900–95 label trap).
- Study `05-fremtpl2-gap-forensics` (third public exhibit): the two-track
  sealed-gap redesign that study 04 (archived at [1.0.0]) queued as future
  work, executed. Each track owns one sealed final-test access, so the
  GLM-vs-GBDT headline is a difference of two sealed numbers (0.009564 = 9.3×
  the sealed paired-bootstrap SE; confirmed). Forensics layer: train-fold
  surrogate distillation, segment deviance attribution, manual 2-way partial
  dependence; deliverables include a claim-cited
  dataset-characteristics → method-choice `checklist.md`. Two framework
  frictions filed from the run (guardrail-metric print visibility; post-scaffold
  track top-up in `final_holdout_access`) — see the study's `program.md` and
  findings §⑦.

### Fixed

- F1 (study 05, E0001): every evaluator now prints a `wall_seconds:` aux line
  — the runner's guardrail check reads the PRINTED block, and the sidecar-only
  `wall_seconds` discarded an anchor-exact candidate. Callers that already
  pass `wall_seconds` via `extra=` keep byte-identical stdout.
- F2 (study 05, E0012; hand-patched again in study 06): `load_state` now tops
  up `final_holdout_access` from the current contract in memory (never
  deleting or overwriting a recorded access), so a track added to `study.yaml`
  after scaffolding no longer strands the sealed gate.

### Changed

- All four exhibits' report fragments re-authored to the typeset convention
  (three divergent math notations retired); reports rebuilt. Studies 00 and 03
  additionally gain the full winning `train.py` by reference — study 03's
  coding-advice section previously shipped no code at all.
- Report code typography: `pre code` line-height 1.55 → 1.4, 14px → 13.5px
  (the prose-tuned spacing read as "double-spaced" in code blocks).
- `tutorial-spec.md` reworked: the bundled builder is the route of record (all
  shipped exhibits were built by it); the external-renderer route is optional
  and currently non-conforming (runtime KaTeX, no CSP); new authoring
  conventions + validated LaTeX subset documented; war story №6 added (the
  unprinted guardrail).

## [1.1.0] — 2026-07-31

The slim release: public `main` becomes the reader-first product — two executed
exhibits (the bundled-data ML quickstart and the schema-v2 math/optimization
study), the engine, the protocols, and nothing a first-time reader must climb
over. **Nothing is lost:** everything removed is preserved intact at tag
[1.0.0], where every recorded candidate commit resolves — historical references
in earlier entries resolve there too.

### Removed

- Studies `01-dae-claims`, `02-rqls-pv-severity`, and `04-fremtpl2-frequency`
  plus the archive docs — `docs/lineage/`, `docs/benchmarks/`, the three
  pre-1.0 dated reviews, and the pricing eval-card worked example
  (137 files, ~3.2 MB). All preserved at tag [1.0.0].

### Changed

- CI retargeted step-level, no check renamed: core/integration pytest and ruff
  paths, the v1-verify loop (study 00 is the only remaining v1 exhibit), the
  Study-02 reproduction anchor dropped (anchors 00 and 03 remain), scheduled
  jobs run the engine suites.
- README quickstart and CONTRIBUTING commands match the slimmed tree; the
  knowledge method cards distilled from archived studies carry archived-source
  notes — knowledge outliving its source studies is the promotion loop working
  as designed.
- Commit-message trailers normalized across `main` (authorship-metadata
  cleanup); tags v0.1.0–v1.0.0 keep the original pre-normalization history,
  through which all recorded study candidate commits resolve.

### Added

- Framework tests for `kleinlib.data.load_xy` and
  `kleinlib.data.feature_column_groups`, previously exercised only through an
  archived study's suite.
- `.gitattributes` marking generated tutorial HTML as `linguist-generated`.

### Docs

- ML/Math positioning aligned across README, package metadata, and
  CITATION.cff (math labs run under `task_type: simulation`; study 03 is the
  exemplar); repo topics gained `optimization` and `simulation`.

## [1.0.0] — 2026-07-31

The universality release: what v0.4.0 could do, now proven portable and frozen.
The driver matrix is re-verified live
[`docs/reviews/2026-07-31-v1.0-driver-matrix.md`], a CI guard keeps normative
text machine-agnostic, and the pre-1.0 caveats are retired: the study schema
(v2), the `klein` CLI surface, and the ledger formats are stable from here.

### Added

- **Universality guard** (`scripts/tests/test_universality.py`, riding the core
  and integration CI jobs): tracked `*.md`/`*.py` must contain no machine-local
  strings — absolute home paths, the author's machine username, local workspace
  names. `docs/lineage/` archives and the frozen study ledgers stay exempt per
  the evidence doctrine: immutable records are never edited.
- **Driver-matrix evidence doc**
  (`docs/reviews/2026-07-31-v1.0-driver-matrix.md`): two NEW live smokes —
  Codex CLI 0.145.0 derived the doctrine-correct locked command from
  `AGENTS.md` alone; Copilot CLI 1.0.75 drove the same verification through
  `.github/copilot-instructions.md` under a granular shell-only permission —
  both returning grounded 15-check reports with clean trees; plus the two
  prior live proofs (Claude Code provenance; local Qwen-GGUF over llama.cpp's
  native Anthropic endpoint) and doc-verified rows for Gemini CLI, Qwen Code,
  and the `AGENTS.md` auto-reader ecosystem, sources cited with access dates.

### Changed

- **Stability of record**: version 1.0.0; classifier
  `Development Status :: 5 - Production/Stable`; the preamble's "0.x means the
  contract may still move" clause retired. Breaking changes to the study
  schema, the CLI surface, or the ledger formats now require a major version.
- **Foreign-repo pins** point at `v1.0.0` (the SKILL.md install line — now
  carrying the stability statement — plus the study pyproject template and the
  preflight hint).
- `CITATION.cff` cites 1.0.0 and gains the previously missing `date-released`.

### Docs

- README and `AGENTS.md` driver rows for Gemini CLI / Qwen Code updated to the
  current nested `context.fileName` settings key (per both CLIs' official
  docs — the legacy flat `contextFileName` key is gone); both files now link
  the driver-matrix evidence doc.
- README states the 1.0 stability promise at the pin advice and under
  § Lineage & citing; `SECURITY.md` clarifies that "supported" means receiving
  security fixes.

## [0.4.0] — 2026-07-31

The integration release: a real-data soak (study 04) filed six frictions
[F1–F6, `docs/reviews/2026-07-31-v0.3-soak.md`] and every one is closed here —
plus the optional-accelerator seams that let a personal research harness
compose with Klein without Klein depending on it.

### Added

- **Exposure-weighted deviance metrics** [F1]: `val_poisson_deviance` /
  `val_gamma_deviance` / `val_tweedie_deviance` join the registry under the
  exposure-weighted-rate convention (y = rate, `sample_weight` = exposure);
  `evaluate_regression` threads optional strictly-positive weights into
  RMSE/MAE/R² too, refuses out-of-domain values with clip-in-train.py guidance,
  and reports `calibration_ratio` on deviance primaries. Tweedie declares its
  `power` in the track contract (1 < power < 2, validated) and the evaluator
  echoes it as an aux line, so drift is manifest-visible.
- **Sanctioned smoke mode** [F2]: `KLEIN_SMOKE=1 python train.py` executes the
  full path while evaluators skip every sidecar/snapshot write; the scaffold's
  refusal message now teaches this instead of listing fakeable variables, and
  `run-one` force-clears the flag in the child so ambient smoke can never
  suppress real evidence.
- **Empty-diff guard + restore anchor** [F5]: `run-one` refuses an accidental
  rerun of the incumbent configuration before any experiment id, run dir, or
  commit exists (`--allow-rerun` makes intentional replication first-class;
  sealed final tests and `--command` overrides stay exempt; executed empty
  diffs carry `empty_candidate_diff: true`), and after every non-keep the CLI
  names the base commit train.py was restored to and the incumbent whose kept
  config that equals (now recorded in manifests as `incumbent`).
- **Real-data noise-floor recipe** [F4]: the consult protocol distinguishes the
  fit-seed floor, the marginal fold-bootstrap floor, and the paired-difference
  bootstrap floor for comparison studies (common-random-numbers language), and
  the `noise_floor:` block gains an optional `method:` provenance field
  (`seed-sweep` | `paired-bootstrap`) emitted by `klein noise-floor`.
- **Comparison-study guidance** [F6]: decide at CONSULT how a gap gets its
  sealed number — one track per model family, or pre-registered
  exploratory-by-construction; the CLI and summaries label the sealed
  confirmation "sealed" while its recorded disposition stays `discard`.
- **`kleinlib.eval.save_holdout_predictions`**: the per-row holdout table hook
  (`y_true`/`y_pred`/`weight` + rating dims + optional second model) under the
  new gitignored `predictions/` convention — the export path for external
  eval tooling, complementing `models/latest_val_preds.npz`.
- **Optional-accelerator seams**, each existence-checked with the bundled
  fallback named (the dataset-profiler pattern): a pricing eval-card generator
  at SYNTHESIZE (worked example: `docs/integrations/pricing-eval-example/`,
  built from study 04's incumbent; fallback `standard_regression_report`),
  knowledge-vault Q&A and paper-filing at METHOD, practice-leg satisfaction by
  citation of a from-scratch nano, a corpus synthesizer for cross-study
  writeups, and outward promotion from `knowledge/` to personal vaults with
  typed claim citations intact.
- **Model backends note** (`AGENTS.md`): any driver runs over a subscription
  agent CLI or a local model behind an OpenAI-compatible /
  Anthropic-Messages-compatible server; Klein itself calls no model APIs and
  requires no keys.
- **Study `04-fremtpl2-frequency`** — the real-data soak exhibit (678k-row
  freMTPL2 claim frequency, GLM vs GBDT): the paired-floor methodology live
  (three defensible floors differing 25×), a keep decided by 0.000002 over the
  declared delta, an accidental bit-identical replication proving end-to-end
  determinism, and a sealed level confirmation at 0.65× the fold SE.

### Fixed

- **Leakage audit covers simulation and deviance studies** [F3]: real split
  kinds on simulation contracts reproduce as regression-shaped splits,
  `kind: none` reports N/A instead of failing, custom simulation metrics get
  their declared direction, and the deviance family gains chance scorers
  (constant train-mean = the null model; shuffled must not beat it). Study
  04's committed contract now audits clean end to end, as-is.
- **Gate records sweep `sweeps/`** [papercut]: measurement-sweep sidecars are
  filed by the next gate/phase/finalize state commit instead of stranding the
  tree dirty for the following `run-one`.

### Docs

- `docs/lineage/` — the agent-smith ancestry archive (quality audit +
  campaign optimization notes, verbatim) with the ancestry README.
- The v0.3 soak review joins the review series in-repo.
- Data-auditor profiler fallback harmonized to the module CLI
  (`python -m kleinlib.profile_fallback`, csv/parquet).

## [0.3.0] — 2026-07-30

The distillation release: v0.2's hardening adopted, audited live, and slimmed —
plus the researcher-value layer and a fourth executed study proving the v2
contract end to end.

### Added

- **Simulation studies are first-class** (`task_type: simulation`): custom
  scalar metrics with explicit direction, `split.kind: none` with seed-block
  comparability — math/optimization/Monte-Carlo labs now express under v2.
- **Measured noise floor**: `klein noise-floor` + a Phase-0 k-seed measurement
  sweep turn `minimum_delta` into a measured quantity; the contract validates
  the `noise_floor:` block, preflight fails a delta set inside its own floor,
  and summaries state deltas as multiples of the floor std.
- **Rolling playbook** (`playbook.md`): the map the loop re-reads before every
  candidate — current best / ruled out with evidence / open hypotheses /
  next-best candidates; refreshed and hash-recorded at every phase
  acknowledgement, staged into evidence commits, mined as synthesis source 5.
- **Phase-start slate ritual** (`references/phase-ritual.md`): 4–6 scored
  falsifiable candidates before spending any run — procedure, not Elo.
- **Clean-room leakage audit** at the DATA gate: a four-check card table run in
  a fresh context, with `python -m kleinlib.leakage` mechanizing split
  contamination and eval-harness chance checks.
- **Decision-trajectory figure** (`kleinlib.figures.plot_decision_trajectory`):
  the keep/discard/crash journey per track with phase bands, minimum-delta and
  noise-floor bands, the sealed confirmation star — embedded in summaries and
  tutorials, with a declared log scale on extreme ranges.
- **Theory+Papers+Practice triad** on method cards, gate-checked; **stable
  claim IDs** (`<study_id>#Cn`) with typed `supports/refutes` citations
  required at knowledge promotion; RQ priors name their source and findings
  score knowledge-sourced priors against uninformed ones.
- **Study `03-noisy-rosenbrock-dfo`** — the v2 contract's live acceptance test:
  7 experiments (2 keep / 4 discard / 1 crash, all candidate commits
  resolvable), a measured floor governing dispositions, one sealed fresh-seed
  confirmation that replicates, findings C1–C7, self-contained tutorial.
- `docs/reviews/2026-07-30-v0.2-adoption-audit.md` — live behavioral audit of
  the v0.2 hardening: every P0 mechanism verified by driving it, 20 defects
  found and dispositioned (A19 journal-hash freeze and A20 phase-ladder drift
  were caught by real use during this release).
- v2 phase telemetry: `summarize_results.py` renders per-phase experiments and
  wall-seconds from `runs/E####/manifest.json` against the contract's budgets.
- Preflight warns on scaffold stubs in `train.py`, validates declared noise
  floors, and catches contract/state phase-ladder drift.
- Help text on every `klein new` / `klein gate` flag.
- CHANGELOG (this file), canonical diagrams under `docs/diagrams/`.

### Changed

- **CLI verbs file their own receipts**: `klein gate record`, `finalize`, and
  `recover` commit the state files they write; derived views
  (`results_summary.md`, `progress.svg`, `figures/`) never block `run-one` and
  are swept into the next state commit. The documented loop no longer dead-ends
  on a dirty tree the CLI itself created.
- Scaffold's default `prepared_path` is CSV (parquet stays one
  `--prepared-path` away) — the core install can pass its own DATA gate.
- Data-card decision regex accepts markdown headings (`## Decision: GO`); gate
  errors name the accepted forms and explain override semantics.
- GBDT smoke fits self-isolate in subprocesses, so the default `pytest`
  collection is safe even with torch loaded (macOS arm64 dual-libomp war story
  enforced by construction; CI's three-process choreography removed).
- Dev tools moved to a default dependency group — `uv run --locked pytest`
  works as documented; default pytest collection covers framework paths only.
- The strong-claim prose lint in `finalize` is a loud warning; the
  exploratory/confirmed label check stays hard.
- `AGENTS.md`/`SKILL.md` teach the loop as three layers: the loop is yours
  (judgment) / `run-one` is the crash boundary (notary) / state files are
  receipts. Stage names and CLI verbs are mapped explicitly.
- Version is single-sourced from package metadata.

### Removed

- `kleinlib/keep_awake.py` (unused mouse-jiggler; `caffeinate -i` is the
  documented path).
- `klein migrate` — folded into `klein verify` (v1 errata print there; nothing
  was ever migrated).
- The embedded schema fallback in `preflight.py` and the five drifted asset
  templates — `kleinlib` is the single source for schema and scaffold templates.
- Dead code (`ensure_uv_locked_command_available`), the hardcoded CLI version
  string, and a stale `VIRTUAL_ENV` leaking uv warnings into archived run logs.

## [0.2.0] — 2026-07-12

The hardening release, implementing
`docs/reviews/2026-07-10-v0.1-review.md` (4 P0 / 6 P1 / 2 P2): the `klein` CLI;
transactional evidence (per-run `manifest.json`, append-only self-verifying
`events.jsonl`, `study_state.json`, `StudyLock`, atomic writes); candidate
commits before execution so negative evidence stays resolvable; a subprocess
crash boundary with real exit codes (124 on timeout); per-track frontiers with
declared direction/minimum-delta/guardrails; a sealed one-access final-test
partition with exploratory/confirmed labeling; stateful preflight (exact
branch, gate acknowledgements, artifact and split fingerprints); metric specs
that reject non-finite values; collision-proof relocatable snapshots; sweep
sidecar hardening with resume; a 7-job CI (Python 3.11–3.14 matrix, ≥80%
engine coverage, tutorial network isolation, reproduction anchors, macOS +
Windows CLI portability, clean-wheel install) plus a weekly scheduled audit
with an Apple-silicon MPS canary; `SECURITY.md`, `THIRD_PARTY_NOTICES.md`,
standard MIT `LICENSE`.

## [0.1.0] — 2026-07-10

First public release: the six-stage lifecycle (CONSULT → DATA → METHOD →
EXPERIMENT/SWEEP → SYNTHESIZE → TUTORIAL) with hard gates; `kleinlib` engine
(schema single-sourcing, data/split contract, evaluators with a collapsed-
prediction guard, 15 figure functions, snapshotting, the sanctioned
`SweepRunner` escape-hatch); the `/klein` skill with 8 reference protocols and
war stories; tool-neutral `AGENTS.md`; seed `knowledge/` base; bundled
Apache-2.0 insurance-claims dataset; three executed exemplar studies
(GLM quickstart, DAE honest-no, robust-QLS synthetic lab).

[1.2.0]: https://github.com/Xiang-Shan/klein-auto-research/releases/tag/v1.2.0
[1.1.0]: https://github.com/Xiang-Shan/klein-auto-research/releases/tag/v1.1.0
[1.0.0]: https://github.com/Xiang-Shan/klein-auto-research/releases/tag/v1.0.0
[0.4.0]: https://github.com/Xiang-Shan/klein-auto-research/releases/tag/v0.4.0
[0.3.0]: https://github.com/Xiang-Shan/klein-auto-research/releases/tag/v0.3.0
[0.2.0]: https://github.com/Xiang-Shan/klein-auto-research/releases/tag/v0.2.0
[0.1.0]: https://github.com/Xiang-Shan/klein-auto-research/releases/tag/v0.1.0
