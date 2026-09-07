# Klein Auto Research — agent manual

This is the canonical operating manual for **any coding agent** working in this
repository — OpenAI Codex, GitHub Copilot, Cursor, Gemini CLI, Qwen Code, GLM-based
CLIs, Claude Code, a Claude Science custom agent, or the next one — and it doubles as
the runbook for a **human driving the framework by hand**. Tools that auto-read
`AGENTS.md` are already set. Claude Code loads it through `CLAUDE.md`. Anything else:
read this file first.

Klein runs **process-verifiable research studies** for AI for Science: any inquiry
where a question can be typed, a prediction registered before its evidence, the
evidence notarized, a claim earned, and a stranger left able to audit the process
with no model in the loop. It works on the user's data, on public data, on a
simulator, or on nothing but a verifier — and it always closes the loop with mined
insights (`findings.md` + `claims.lock`), an independent referee's verdict, and a
self-contained teaching tutorial (`report/index.html`).

## The study lifecycle

Every study moves through seven stages, in order, past four gates:

```
new ─▶ CONSULT ─▶ DATA ─▶ METHOD ═══▶ EXPERIMENT/SWEEP ─▶ SYNTHESIZE ─▶ REFEREE ─▶ TUTORIAL
        Gate 0   Gate 1   Gate 2      └ the honest loop ┘    findings.md    Gate 3     report/
```

**CONSULT (Gate 0).** For vague or ambitious goals: at most six questions — goal,
data availability + size, method familiarity, metric + decision use, compute/time
budget, deliverable form. Fast-path: if the brief already answers five or more, skip
straight to confirmation. The consultant also **types the inquiry** — `kind`,
`modality`, `profile` (`.claude/skills/klein/references/inquiry-model.md`) — inferred
from the brief and confirmed, never a seventh question. Output: `study.yaml` (with
`predictions[]`, each carrying an arithmetic rule), `research_plan.md`, a generated
`program.md`, and `scouting_ledger.md` for anything looked at beforehand. Requires an
explicit user ack before Gate 1.

**DATA (Gate 1).** GIGO guard, typed by modality: profile the evidence source and
write `data_card.md` with ranked go/no-go issues before any modeling. A table gets the
value-pattern check (never trust `dtype == "object"`) and the four-row clean-room
leakage audit, mechanized by `python -m kleinlib.leakage`; a time series adds a time
policy; images, sequences, graphs and text add a group policy and run the audit on
the split index table; a simulation gets a DGP card; a verifier-only study gets a
verifier card. Partitions come from the contract (`kleinlib.data.contract_split`),
never from a literal seed — a literal seed in an evaluator is a BLOCKER. Any FAIL is
a BLOCKER.

**METHOD (Gate 2).** Pedagogy for unfamiliar or frontier methods: write
`method_card.md` — intuition for the profile's audience → math core → minimal
from-scratch implementation → when-it-pays / when-it-doesn't → verified references
(`references.yaml`). The card asserts its Theory+Papers+Practice `triad:`; the gate
refuses an incomplete triad unless the note names the missing leg. When a track
declares a verifier, the gate hashes the verifier script — it never changes again.

**Hard-block rule:** modeling is BLOCKED until CONSULT, DATA and METHOD are
acknowledged and `data_card.md` says GO. Record or override a gate with
`klein gate`; the timestamp, artifact hashes, actor and reason are persisted in
`study_state.json` and the append-only, self-verifying `events.jsonl`.

**EXPERIMENT/SWEEP.** The edit-run-log loop under the contract below. A **frontier**
track climbs (keep / discard / crash); a **registered** track measures (measured /
crash) — every run a pre-registered cell whose tables are pinned as evidence. Sweeps
only through the one sanctioned escape-hatch.

**SYNTHESIZE.** Mine the full trajectory — manifests and `results.tsv`, the
predictions ledger, `aux_metrics.tsv`, `program.md`'s decision history,
`playbook.md`, the method card's expectations — and write `findings.md` with exactly
seven sections (① verdicts with claim ids `<study>#Cn`; ② registered predictions
copied from the ledger; ③ surprises; ④ advice; ⑤ the profile's implications section;
⑥ literature; ⑦ next), then author `claims.lock` with `klein claims` so every number
has a pinned home and every claim a class, a strength and resolvable evidence.

**REFEREE (Gate 3).** A fresh context — on a different model or tool than the
experimenter wherever possible — reads `findings.md` before `program.md`, runs
`klein verify --numbers --evidence-use` and `klein claims verify`, applies a fixed
ten-check rubric, and writes `referee_report.md` with a machine-read `Verdict:`.
`klein gate record referee` hashes it; a FAIL cannot be recorded; `klein finalize`
runs only after this gate (`--no-referee --reason` is recorded and labels the study
`unrefereed`).

**TUTORIAL.** Build `report/index.html` — a self-contained TEACHING artifact, not a
figure dump — with a fixed seven-section arc: the question → the method taught → the
data story → the experiment journey → findings & insights → the profile's coding
advice section → next steps + verified references. Base64-inlined captioned figures
that re-render byte-identically, build-time typeset math and highlighted code, the
EXECUTED source included by reference (the bytes a named run ran, not the restored
file on disk), claim totals and the referee's verdict copied from the records, headline
numbers read from `claims.lock`; no CDN, no fonts, no runtime rendering; must open from
`file://`.

## The stage map

The protocols are the source of truth. They live under `.claude/skills/klein/` —
a Claude Code packaging convention, but **every file is plain markdown or plain
Python: read and follow them with any tool, or by hand.** (Claude Code users get
this same table routed as the `/klein` skill.)

| Stage | Protocol (source of truth) | Key outputs | Helper |
|---|---|---|---|
| scaffold | `references/defaults-and-scaffolding.md` | study dir + templates, typed by kind / modality / profile | `klein new` |
| CONSULT | `references/consult-protocol.md` + `references/inquiry-model.md` | study.yaml (predictions with rules), research_plan.md, program.md, scouting_ledger.md | `klein doctor --study` |
| DATA | `references/data-gate-protocol.md` + `references/data-sources.md` | data_card.md (modality-typed go/no-go) | `python -m kleinlib.profile_fallback`, `python -m kleinlib.leakage` |
| METHOD | `references/method-gate-protocol.md` | method_card.md, references.yaml, the verifier script | — |
| EXPERIMENT | loop contract below + `SKILL.md` Hard Rules; `references/registered-mode.md` | immutable run manifests + derived results, models/, figures/ | `klein preflight`, then `klein run-one [--tests P#]`; `klein run-one --final-test --dry-run` before every sealed run |
| SWEEP | `references/sweep-rules.md` | trials → sidecar TSV, one winner transaction; measurement sweeps registered as `sweep:<name>` | `kleinlib.sweep.SweepRunner`, `klein sweep register` |
| REPLICATE (any time after a run) | `references/replication-protocol.md` | `runs/E####/replications/<ts>.json` | `klein replicate E#### [--verify-only]` |
| SYNTHESIZE | `references/synthesis-protocol.md` + `references/claims-protocol.md` | findings.md, claims.lock | `.claude/skills/klein/scripts/summarize_results.py`, `klein predict list`, `klein claims …` |
| REFEREE | `references/referee-protocol.md` | referee_report.md | `klein verify --numbers --evidence-use`, `klein claims verify`, then `klein gate record referee`; `klein finalize` after |
| TUTORIAL | `references/tutorial-spec.md` + `references/profiles/<profile>.md` | report/index.html | `.claude/skills/klein/scripts/build_tutorial.py`, `figures/make_figures.py` |
| status / verify (any time) | — | results_summary.md, progress.svg, verify_receipt.json | `klein status`, `klein verify`, `summarize_results.py` |

(`references/…` paths above live under `.claude/skills/klein/`; a bare `scripts/…`
path means the repo root. Every helper is a plain CLI:
`uv run --locked python <path> --help`.)

## The inquiry model, in one paragraph

A study is typed on three orthogonal axes. **`kind`** is the question's shape —
`predict | estimate | test | simulate | replicate | discover | optimize` — and fixes
the track mode, what "sealed" means, what confirmation requires
(`confirmation.require ⊆ {sealed, replicate, verify}`), and the strength a claim can
reach. **`modality`** is the evidence source — `tabular | timeseries | image |
sequence | graph | text | simulation | none` — and selects the data-gate card.
**`profile`** is the audience — `generic | ml-research | math | insurance`, or a
repo-local `profile_doc` — and changes headings, doctrine anchors, figure sets,
budgets and banned words, never what the engine checks. Five objects thread through
every study: a Question, a Prediction (registered, with a rule), Evidence (manifests,
registered sweeps, replications, verified references), a Claim (`<study>#Cn`, with a
class and a strength), and a Decision (a dated line in `program.md`).

## The experiment loop contract

These invariants are battle-tested — each guards against a failure that actually
happened (`.claude/skills/klein/references/war-stories.md`), and the lessons of the
studies that paid for them are promoted in `knowledge/research-discipline.md`. Do
not renegotiate them mid-study.

The loop has three layers. Keep them straight and the rest follows:

1. **The loop is yours — judgment.** Think → edit the mutable surface with ONE
   falsifiable idea (the files `entrypoint.mutable` names; `train.py` by default for
   `predict`) → run it → reflect in `program.md` → repeat. On a registered track the
   idea is a cell: which measurement, adjudicating which prediction. No meta-runner
   exists and none is missing: **the driving agent IS the loop**, because only the
   agent can change direction based on what just happened.
2. **`klein run-one` is the crash boundary — a notary, not a driver.** One
   invocation is one candidate transaction: it commits your candidate BEFORE
   execution, runs one bounded foreground subprocess (unbuffered, the contract's
   `max_run_seconds`, process-group timeout, the real exit code — 124 on timeout),
   runs the declared verifier as a second subprocess when the track has one and
   decides on the verifier's number, compares the printed `split_fingerprint:` with
   the one frozen at the DATA gate, decides keep / discard / measured / crash by
   arithmetic on the contract YOU declared, adjudicates the predictions named with
   `--tests`, restores the mutable surface (on a non-keep, or always on a registered
   track — the candidate commit stays resolvable; negative evidence is evidence), and
   files the evidence commit. It never proposes, schedules, or retries an experiment.
   It refuses an unchanged surface before any id or commit exists — pass
   `--allow-rerun` for an intentional identical replication, or `--tests P#` on a
   registered track (sealed final tests and `--command` overrides stay exempt).
3. **The state files are receipts — generated, never hand-edited.**
   `runs/E####/manifest.json`, `study_state.json`, the append-only self-verifying
   `events.jsonl`, `claims.lock`, `verify_receipt.json`, and the derived `results.tsv`
   record what layer 1 decided and layer 2 observed. Gate records, `klein finalize`,
   `klein recover`, `klein claims`, `klein predict adjudicate` and `klein verify`
   commit their own state writes; if the tree is dirty at run time, it is your edit,
   not Klein's — and it stays yours: verify, claims, predict, replicate, sweep, stop
   and headroom commit only the files they wrote; gate records, run-one and finalize
   file the study artifacts they hash.

The standing rules around those layers:

- `program.md` is the living lab notebook: hypotheses, decisions, phase plans, and
  the dated `Decision:` line every refuted prediction must receive live there.
- `playbook.md` is the rolling state of play — current best per track, ruled-out
  directions with evidence, open hypotheses, next-best candidates. RE-READ it
  before selecting every candidate; refresh it at every phase boundary and at
  least every 5 experiments. At each phase start, run the slate ritual
  (`references/phase-ritual.md`): 4–6 falsifiable candidates (cells, on a registered
  track), scored, recorded in `program.md`, survivors mirrored into the playbook.
- The mutable surface is `entrypoint.mutable` ONLY. Library code (`kleinlib/`, study
  `lib/`), `prepare.py` and the declared verifier change rarely, deliberately, and
  never as part of the per-experiment diff. **The verifier is never in the mutable
  surface** — the checker is never the searcher.
- Status honesty: `keep` / `discard` / `measured` / `crash` — a crash is logged as a
  crash with `NA` metric, not silently retried into oblivion.
- **Predictions are adjudicated by the notary, never by prose.** `run-one --tests P#`
  evaluates the registered rule on the printed block; `klein predict adjudicate`
  records sidecar evidence with its hash. `finalize` refuses open predictions; a
  refuted prediction without a recorded decision fails `klein verify`.
- Detection-limit honesty: once a track declares `metric.bound.ideal` and holds an
  incumbent, klein computes headroom `h = (incumbent − ideal) / minimum_delta` and
  discloses it at preflight/verify. `h < 1` means no keep is arithmetically
  possible — the default posture refuses further development runs until
  `klein headroom ack` puts the closed door on the record. Read `h >= 1` as "not
  excluded", never "plausible". A `stop:` rule works the same way (`klein stop ack`).
- `KLEIN_SMOKE=1 python <entrypoint>` is the ONE sanctioned off-loop smoke check;
  `run-one` force-clears the flag in its child so ambient smoke can never suppress
  real evidence. `klein run-one --final-test --dry-run` is the ONE sanctioned
  rehearsal of a sealed run: it spends nothing and is mandatory before the real one.
- The ONE sanctioned escape-hatch is the sweep protocol
  (`references/sweep-rules.md`): every trial to a sidecar TSV, exactly one winner
  transaction, winner config snapshotted into the surface, winner model stored
  locally with its hash in the committed manifest. Measurement sweeps are registered
  with `klein sweep register` so findings can cite them; crash rows are data.
- `minimum_delta` is MEASURED, never guessed: Phase 0 runs a floor recipe with a named
  estimand and `klein noise-floor --recipe --estimand` prints the contract block;
  preflight fails a delta declared inside its own floor (schema 3: below
  `max(2×std, range/2)`); an `exact` metric declares its resolution instead.
- Adaptive work uses train/development data only. Each track may access its sealed
  evidence once with `klein run-one --final-test`; confirmation evidence is excluded
  from the adaptive frontier. `klein replicate E####` re-executes a development run
  in a detached worktree (or re-runs the verifier on a pinned artifact) and records
  the reproduction; `confirmation.require` says which records `confirmed` needs.
- **Claims are locked, numbers have homes, errata re-scope.** `claims.lock` is
  produced by `klein claims`, verified by the seven-check claims law, append-only
  across its git history; every numeral in findings, lock and tutorial is a copy of a
  pinned value; an erratum tags claims, never deletes them.
- **The referee is independent by mechanism.** REFEREE runs in a fresh context on a
  different model, tool or person than the experimenter; the rung reached is on the
  gate record. A synthesist never referees its own findings.
- Phase-boundary pauses: at every phase boundary defined in `study.yaml`, summarize,
  STOP for user ack, then record it with `klein gate record phase --phase <id>`.
- Studies run on `experiments/<study>` branches, never on `main`. Merge at study end.
- **The opt-in generation layer records commitments before actions.** A schema-3
  study may run `klein generation init` before Gate 0 and one `klein generation check`
  before every `run-one`; the receipt binds the intended action and the exact mutable
  surface, a refusal is recorded evidence, and `klein generation verify` writes its own
  separate receipt (`generation/verify_receipt.json`). The `generation-verified` label
  needs BOTH that receipt and the core `klein verify` receipt passing at the same HEAD.
  The core never depends on it: a study that does not opt in is untouched, no core verb,
  receipt or disposition changes, and the layer never proposes, ranks, selects,
  schedules or retries. `.claude/skills/klein/references/generation-protocol.md`.
- Schema-2 studies (03, 05–09) keep verifying under schema-2 rules forever; none of
  the schema-3 checks are enforced on them. Version-1 studies are readable at tag
  `v1.3.0`. Nothing ever notarized is rewritten.

## Schema discipline

- The results schema lives ONLY in `kleinlib/schema.py`. Templates, docs, and
  scripts POINT there; none of them restate the column list.
- `schema_version` selects the rule set: 2 (frozen) or 3 (Klein 2.0). A missing
  `schema_version` is v1, readable only at tag `v1.3.0`. Registries that docs may
  name: `KNOWN_PROFILES`, `KNOWN_MODALITIES`, `MODALITY_CARD_SECTIONS`,
  `VALID_STATUSES`, `EVALUATOR_PRINTED_KEYS`.
- Track metrics carry their own name, direction, minimum delta, guardrails, optional
  bound, exactness, external incumbent, and verifier. `keep` means a frontier
  improvement on that track satisfying those guardrails; `measured` is a registered
  cell; `discard` is retained evidence; `crash` has `NA` as its primary metric.
  Guardrails are evaluated on the PRINTED metric block (from the verifier's block
  when one is declared): `wall_seconds` is printed by every evaluator; any other
  declared key must be printed via `evaluate*(..., extra={...})` — `klein preflight`
  warns when a declared key is neither auto-printed nor named in the study's sources.
- Everything that is not the one primary metric goes to `aux_metrics.tsv` in long
  format (`experiment  metric  value`), never into extra results columns; tables a
  cell produces are pinned with `artifact:` lines and cited as `art:<alias>`.

## War stories (why the guards exist)

- pandas string-dtype broke `dtype == "object"` checks and silently skipped
  categorical handling → all dtype checks are value-pattern checks now.
- On Apple-silicon MPS, DataLoader + TensorDataset silently collapsed predictions
  to a constant → torch loops use streamed index-shuffle batches, and evaluators
  reject non-finite or near-constant predictions.
- A 4-column vs 5-column schema drift between two docs corrupted `results.tsv`
  appends → the schema is single-sourced in `kleinlib/schema.py` and drift-tested.
- class-weight reweighting ruined calibration on weak-signal insurance data → the
  insurance profile's doctrine: `class_weight=None` + isotonic + threshold tuning.
- torch + LightGBM in one process SIGSEGV on macOS arm64 → two-stage process
  isolation; the runner preserves the subprocess status.
- A declared guardrail that was never printed dispositioned a healthy run `discard`
  → every evaluator prints `wall_seconds`; preflight checks guardrail visibility.
- A measured floor larger than the incumbent's whole distance to perfection put the
  keep bar below zero and nobody noticed for a study → `metric.bound` + headroom.
- An evaluator hardcoded a retired split seed and a whole ledger lane measured the
  wrong partition; the lock's numeral scan caught it a study later → contract-driven
  splits with a printed fingerprint the notary checks; errata re-scope.
- A study's only sealed access was spent by a crash before any data was read →
  the sealed dry-run, mandatory before every real sealed run.

## Worker roles (optional parallelization)

One agent following this manual runs the whole lifecycle solo, in stage order —
that is the default and it is fully supported. If your tool can spawn subagents,
the stages map to natural roles; match model strength to the stage, and put the
referee on a different model or backend than the experimenter:

| Stage | Role | Suggested model tier |
|---|---|---|
| CONSULT | consultant | strongest reasoning model |
| DATA | data auditor | fast/cheap model is fine |
| METHOD | method scholar | strongest reasoning model |
| EXPERIMENT | experimenter | fast/cheap model is fine |
| SWEEP | sweeper | fast/cheap model is fine |
| SYNTHESIZE | synthesist | strongest reasoning model |
| REFEREE | referee | strongest reasoning model — and NOT the experimenter's model or session |
| TUTORIAL | tutor | fast/cheap model is fine |

Claude Code ships these roles pre-wired in `.claude/agents/`; with any other tool,
run the stages sequentially or use your tool's own subagent mechanism. Some
protocols name optional external accelerators (a dataset profiler, a paper-lookup,
a tutorial renderer, a pricing eval-card generator, a knowledge-vault Q&A, a
corpus synthesizer); when absent, Klein's bundled fallbacks run instead — the
protocols always spell out both paths.

## Driving Klein with your tool

- **Agents that auto-read `AGENTS.md`** (Codex, Copilot coding agent, Cursor,
  Jules, Zed, …): you are already set — ask for "a Klein study on `<your data>`,
  following the stage map in AGENTS.md".
- **Claude Code**: the `/klein` skill routes the same stages; `CLAUDE.md` imports
  this manual.
- **Claude Science**: run Klein as the lab-notebook discipline inside a session —
  a custom agent that follows this manual, with the referee stage handed to a
  different model or a different session.
- **Gemini CLI / Qwen Code**: add `AGENTS.md` to the context files — the
  settings.json `context.fileName` key takes a string or list — or start the
  session with "read AGENTS.md first".
- **GLM and other Anthropic-compatible CLIs**: they load `CLAUDE.md`, which points
  here.
- **Model backends.** Any driver above runs over any backend that speaks its
  protocol — a subscription agent CLI, or a **local model** behind an
  OpenAI-compatible or Anthropic-Messages-compatible server. Klein itself calls no
  model APIs and requires no API keys — the framework is plain Python + git; the
  driving agent brings its own model.
- **No agent at all**: follow the stage map by hand — each protocol is a
  human-readable runbook and each helper is a plain CLI.

This matrix is re-verified at each release — live driver smokes and official-doc
citations are filed under `docs/reviews/`.

## Run commands

- Always locked `uv run ...` (e.g. `uv run --locked klein status`,
  `uv run --locked pytest`), never bare `python`. CI may use `uv run --no-sync`
  immediately after a successful `uv sync --locked` to prove it is not mutating the
  environment. `klein doctor` reports what this machine can run without fetching.
- The opt-in generation layer adds one verb group, `klein generation
  init|check|verify|label|status|recover`, plus one sub-group per declared capability
  (`generation expert lock|amend|bind|repair|review` and `generation reference record`
  for `expertise`; `generation slate lock|amend|score|show` for `slates`; `generation
  design lock` for `design`; `generation premortem record|respond` for `premortem`;
  `generation parity lock|amend|bind|assess|show` for `parity`; `generation
  contribution record|show` for `contribution`; `generation escalate
  lock|record|close|pivot|show` for `escalation`; `generation knowledge
  promote|contest|resolve|query|decide|show` for `knowledge`; `generation surprise
  register|record|show` for `surprise`; `generation benchmark
  commit|submit|reveal|retire|show` for `benchmark`), plus `generation custody attest`,
  which belongs to no capability and any generation-enabled study may record. It is
  schema-3 only and writes
  nothing outside `<study>/generation/` except the human artifacts a capability names —
  `domain_card.md`, `slates/<phase>.yaml`, `evidence_design.yaml`,
  `premortem/<phase>.yaml`, `parity.yaml`, `ai_value.jsonl`, `escalation_plan.yaml`,
  `discovery_cells.yaml`, `benchmark.yaml`, the copied
  `benchmark-submission.schema.json` and `submissions/<arm>.json` at the study root,
  and repo-level `knowledge/references/<id>.json`, `knowledge/objects/<sha256>.json`
  and `knowledge/events.jsonl`.
- `uv sync --locked` to set up; extras compose and must be named together:
  `uv sync --locked --extra gbdt --extra deep` (naming only some extras removes
  the others from the environment). `KLEIN_OFFLINE=1` refuses every network data
  source; `KLEIN_DEVICE` overrides device selection.

## Durable notes

- `program.md` is per-study memory: record hypotheses, decisions, and phase plans
  there as the study runs — it is what SYNTHESIZE mines later.
- Findings that generalize beyond one study are promoted into `knowledge/` — the
  field's `knowledge/domains/<profile>/` or the framework's own
  `knowledge/research-discipline.md` — always with a typed claim citation
  `(supports <study>#Cn)`, so the next study starts from accumulated knowledge
  instead of a blank page.
- If your tool keeps its own cross-session memory, store study pointers and
  conclusions at phase boundaries (the same cadence as user acks), never mid-loop.
