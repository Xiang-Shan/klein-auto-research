# Klein Auto Research — Copilot instructions

This repository is a framework for **process-verifiable research studies** for AI
for Science. The canonical operating manual is **`AGENTS.md`** at the repo root —
read it before making changes or running a study; the stage protocols it maps to
(plain markdown under `.claude/skills/klein/references/`) are the source of truth.

Golden rules (details, definitions and the full stage map in `AGENTS.md`):

- Always locked `uv run ...`, never bare `python`; set up with `uv sync --locked`
  (add `--extra gbdt --extra deep --extra encoders` together for the optional
  stacks; naming only some extras removes the others).
- A study moves through seven stages past four gates:
  CONSULT → DATA → METHOD → EXPERIMENT/SWEEP → SYNTHESIZE → REFEREE → TUTORIAL.
  Modeling is blocked until `klein gate record consult|data|method` (or
  `gate override ... --reason`); phase boundaries are acknowledged with
  `klein gate record phase --phase <id>`; `klein finalize` runs only after
  `klein gate record referee`, and the referee is a fresh context on a different
  model or tool than the experimenter.
- The experiment loop: edit only the files `entrypoint.mutable` names (one
  falsifiable idea per candidate), then run exactly one candidate transaction with
  `uv run --locked klein run-one --study studies/NN-slug --track <track>`; a
  declared verifier is never in the mutable surface. `run-one` commits the
  candidate BEFORE execution, runs one bounded subprocess, decides
  keep / discard / measured / crash by the contract's arithmetic, restores the
  surface on a non-keep, and files the evidence — never hand-edit a ledger; the
  evidence is `runs/E####/manifest.json` + `events.jsonl`. After an interruption:
  `klein recover`.
- Predictions are adjudicated by the notary (`run-one --tests P#`,
  `klein predict adjudicate`), never by prose; claims live in `claims.lock`
  (`klein claims ...`, append-only, errata re-scope); `klein verify --numbers
  --evidence-use` must pass before a study closes.
- Never edit a shipped study's ledgers, lock, cards, `findings.md` or
  `program.md` — they are immutable exhibits. New results = new studies.
- Studies run on `experiments/<study>` branches, never on `main`; study branches
  merge, never rebase (manifests pin candidate commits).
- The results schema is single-sourced in `kleinlib/schema.py`; everything that is
  not the one primary metric goes to `aux_metrics.tsv`.
- Tests: `uv run --locked pytest kleinlib/tests .claude/skills/klein/scripts/tests
  scripts/tests`; full pipeline proof: `uv run --locked python scripts/verify_e2e.py`
  (`--lane legacy|schema3|all`); every shipped study:
  `uv run --locked python scripts/verify_shipped_studies.py`.
