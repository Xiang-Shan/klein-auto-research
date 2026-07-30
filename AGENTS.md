# Klein Auto Research — agent manual

This is the canonical operating manual for **any coding agent** working in this
repository — OpenAI Codex, GitHub Copilot, Cursor, Gemini CLI, Qwen Code, GLM-based
CLIs, Claude Code, or the next one — and it doubles as the runbook for a **human
driving the framework by hand**. Tools that auto-read `AGENTS.md` are already set.
Claude Code loads it through `CLAUDE.md`. Anything else: read this file first.

Klein runs disciplined ML research **studies** on the user's data (or synthetic
known-truth data when none exists) and always closes the loop with mined insights
(`findings.md`) and a self-contained teaching tutorial (`report/index.html`).

## The study lifecycle

Every study moves through six stages, in order:

```
new ─▶ CONSULT ─▶ DATA ─▶ METHOD ═══▶ EXPERIMENT/SWEEP ─▶ SYNTHESIZE ─▶ TUTORIAL
        Gate 0   Gate 1   Gate 2      └ the honest loop ┘    findings.md   report/
```

**CONSULT (Gate 0).** For vague or ambitious goals: at most six questions — goal,
data availability + size, method familiarity, metric + decision use, compute/time
budget, deliverable form. Fast-path: if the brief already answers five or more, skip
straight to confirmation. Output: `study.yaml`, `research_plan.md`, a generated
`program.md`. Requires an explicit user ack before Gate 1.

**DATA (Gate 1).** GIGO guard: profile the dataset and write `data_card.md` with
ranked go/no-go issues before any modeling. Check value patterns, never trust
`dtype == "object"` (see war stories).

**METHOD (Gate 2).** Pedagogy for unfamiliar or frontier methods: write
`method_card.md` — intuition → math core → minimal from-scratch implementation →
when-it-pays / when-it-doesn't → verified references.

**Hard-block rule:** modeling is BLOCKED until the CONSULT, DATA, and METHOD gates
are acknowledged and `data_card.md` says GO. In schema v2, record or override a gate
with `klein gate`; the timestamp, artifact hashes, actor, and reason are persisted in
`study_state.json` and hash-chained `events.jsonl`. The legacy v1 fast-path remains
readable but is never sufficient for a new v2 study.

**EXPERIMENT/SWEEP.** The edit-run-log loop under the contract below; sweeps only
through the one sanctioned escape-hatch.

**SYNTHESIZE.** Mine the full trajectory — `results.tsv` (keep vs discard clusters,
deltas between consecutive keeps), `aux_metrics.tsv` (tradeoffs, e.g. AUC vs brier),
`program.md` decision history, the method card's literature expectations — and write
`findings.md` with exactly seven sections: ① verdict per research question with
evidence experiment IDs; ② predictions-to-falsify table filled; ③ surprises & why;
④ practical advice; ⑤ business value implications; ⑥ literature tie-back;
⑦ what to try next.

**TUTORIAL.** Build `report/index.html` — a self-contained TEACHING artifact, not a
figure dump — with a fixed seven-section arc: the question → the method taught → the
data story → the experiment journey → findings & insights → model coding advice →
next steps + verified references. Base64-inlined figures, no CDN; must open from
`file://`.

## The stage map

The protocols are the source of truth. They live under `.claude/skills/klein/` —
a Claude Code packaging convention, but **every file is plain markdown or plain
Python: read and follow them with any tool, or by hand.** (Claude Code users get
this same table routed as the `/klein` skill.)

| Stage | Protocol (source of truth) | Key outputs | Helper script |
|---|---|---|---|
| scaffold | `.claude/skills/klein/references/defaults-and-scaffolding.md` | study dir + templates | `klein new` |
| CONSULT | `references/consult-protocol.md` | study.yaml, research_plan.md, program.md | — |
| DATA | `references/data-gate-protocol.md` | data_card.md (go/no-go) | `python -m kleinlib.profile_fallback` |
| METHOD | `references/method-gate-protocol.md` | method_card.md | — |
| EXPERIMENT | loop contract below + `SKILL.md` Hard Rules | immutable run manifests + derived results, models/, figures/ | `klein preflight`, then `klein run-one` |
| SWEEP | `references/sweep-rules.md` | trials → sidecar TSV, one winner transaction | `kleinlib.sweep.SweepRunner` |
| SYNTHESIZE | `references/synthesis-protocol.md` | findings.md | `scripts/summarize_results.py` |
| TUTORIAL | `references/tutorial-spec.md` | report/index.html | `scripts/build_tutorial.py`, `scripts/make_figures.py` |
| status (any time) | — | results_summary.md, progress.svg | `scripts/summarize_results.py` |

(Relative paths above are under `.claude/skills/klein/`. Every helper is a plain
CLI: `uv run --locked python .claude/skills/klein/scripts/<name>.py --help`.)

## The experiment loop contract

These invariants are battle-tested — each guards against a failure that actually
happened (`.claude/skills/klein/references/war-stories.md`), and the 215-experiment
ancestor campaign they come from ships its distilled findings in `knowledge/`. Do
not renegotiate them mid-study.

- `program.md` is the living lab notebook: hypotheses, decisions, phase plans, and
  predictions-to-falsify live there and are updated as the study runs.
- The mutable surface is `train.py` ONLY. Library code (`kleinlib/`, study `lib/`)
  changes are rare, deliberate, and never part of the per-experiment diff. Keep
  diffs thin: 5–15 lines.
- For schema v2, run exactly one candidate transaction in the foreground with
  `uv run --locked klein run-one --study studies/NN-slug --track <track>`. It uses
  unbuffered output, the configured
  `max_run_seconds`, process-group timeout handling, and retains the real exit code.
- Every candidate configuration is committed **before** execution, including a
  discard or crash. Non-keeps restore the working `train.py`, but the candidate
  commit remains resolvable. Evidence is then committed transactionally; use
  `klein recover` after an interruption.
- In v2, `runs/E####/manifest.json` and `events.jsonl` are the evidence. Never edit
  `results.tsv`: it is a derived, track-aware view regenerated transactionally.
- Legacy v1 studies retain their five-column, append-only ledger. If a v1 command
  must be run, use `scripts/run_with_log.py`, not a shell `| tee` pipeline, so a
  crash or timeout cannot be masked.
- Status honesty: `keep` / `discard` / `crash` — a crash is logged as a crash with
  `NA` metric, not silently retried into oblivion.
- **The driving agent IS the loop.** No meta-runners, no orchestration scripts that
  run many experiments unattended. The ONE sanctioned escape-hatch is the sweep
  protocol (`references/sweep-rules.md`): every trial to a sidecar TSV, exactly one
  winner transaction / derived row, winner config snapshotted into train.py, winner
  model stored locally with its hash/availability in the committed manifest. Unsafe
  model payloads themselves are never committed.
- Adaptive work uses train/development data only. Each track may access its sealed
  final-test partition once with `klein run-one --final-test`; confirmation evidence
  is excluded from the adaptive frontier.
- Phase-boundary pauses: at every phase boundary defined in `study.yaml`, summarize,
  STOP for user ack, then record it with `klein gate record phase --phase <id>`.
- Studies run on `experiments/<study>` branches, never on `main`. Merge at study end.

## Schema discipline

- The results schema lives ONLY in `kleinlib/schema.py`. Templates, docs, and
  scripts POINT there; none of them restate the column list.
- A missing `schema_version` means v1. Its ledger remains readable through
  `kleinlib.schema.RESULTS_COLUMNS` / `OPTIONAL_COLUMNS` and is never rewritten by
  migration. Schema v2 uses `V2_RESULTS_COLUMNS` as a derived view of manifests.
- Track metrics carry their own name, direction, minimum delta, and guardrails.
  `keep` means a frontier improvement on that track satisfying those guardrails;
  `discard` is retained evidence, and `crash` has `NA` as its primary metric.
- Everything that is not the one primary metric (PR-AUC, logloss, brier, lift@10,
  thresholds, wall_seconds, model_path, min_proba_std, ...) goes to
  `aux_metrics.tsv` in long format (`experiment  metric  value`), never into extra
  results columns.

## War stories (why the guards exist)

- pandas string-dtype broke `dtype == "object"` checks and silently skipped
  categorical handling → all dtype checks are value-pattern checks now.
- On Apple-silicon MPS, DataLoader + TensorDataset silently collapsed predictions
  to a constant → torch loops use streamed index-shuffle batches, and evaluators
  reject non-finite or near-constant predictions using range/unique diagnostics.
- A 4-column vs 5-column schema drift between two docs corrupted `results.tsv`
  appends → the schema is single-sourced in `kleinlib/schema.py` and drift-tested.
- class-weight / imbalance reweighting ruins calibration on weak-signal insurance
  data → default to `class_weight=None` + isotonic calibration + threshold tuning.
- torch + LightGBM in one process SIGSEGV on macOS arm64 (dual bundled `libomp`;
  whichever engages OpenMP second dies, below Python — no guard can fire) → any
  train.py mixing them uses two-stage process isolation; Klein's runner supplies
  unbuffered output and preserves the subprocess status.

## Worker roles (optional parallelization)

One agent following this manual runs the whole lifecycle solo, in stage order —
that is the default and it is fully supported. If your tool can spawn subagents,
the stages map to natural roles; match model strength to the stage:

| Stage | Role | Suggested model tier |
|---|---|---|
| CONSULT | consultant | strongest reasoning model |
| DATA | data auditor | fast/cheap model is fine |
| METHOD | method scholar | strongest reasoning model |
| EXPERIMENT | experimenter | fast/cheap model is fine |
| SWEEP | sweeper | fast/cheap model is fine |
| SYNTHESIZE | synthesist | strongest reasoning model |
| TUTORIAL | tutor | fast/cheap model is fine |

Claude Code ships these roles pre-wired in `.claude/agents/`; with any other tool,
run the stages sequentially or use your tool's own subagent mechanism. Some
protocols name optional external accelerators (a dataset profiler, a paper-lookup,
a tutorial renderer); when absent, Klein's bundled fallbacks run instead — the
protocols always spell out both paths.

## Driving Klein with your tool

- **Agents that auto-read `AGENTS.md`** (Codex, Copilot coding agent, Cursor,
  Jules, Zed, …): you are already set — ask for "a Klein study on `<your data>`,
  following the stage map in AGENTS.md".
- **Claude Code**: the `/klein` skill routes the same stages; `CLAUDE.md` imports
  this manual.
- **Gemini CLI / Qwen Code**: point the context file at `AGENTS.md` (e.g. the
  `contextFileName` setting), or start the session with "read AGENTS.md first".
- **GLM and other Anthropic-compatible CLIs**: they load `CLAUDE.md`, which points
  here.
- **No agent at all**: follow the stage map by hand — each protocol is a
  human-readable runbook and each helper is a plain CLI.

## Run commands

- Always locked `uv run ...` (e.g. `uv run --locked klein status`,
  `uv run --locked pytest`), never bare `python`. CI may use `uv run --no-sync`
  immediately after a successful `uv sync --locked` to prove it is not mutating the
  environment.
- `uv sync --locked` to set up; extras compose and must be named together:
  `uv sync --locked --extra gbdt --extra deep` (naming only some extras removes
  the others from the environment).

## Durable notes

- `program.md` is per-study memory: record hypotheses, decisions, and phase plans
  there as the study runs — it is what SYNTHESIZE mines later.
- Findings that generalize beyond one study are promoted into `knowledge/` (a new
  or updated synthesis doc or method card), so the next study starts from
  accumulated knowledge instead of a blank page.
- If your tool keeps its own cross-session memory, store study pointers and
  conclusions at phase boundaries (the same cadence as user acks), never mid-loop.
