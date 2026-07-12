# Program — {{STUDY_ID}}

> This file is the living lab notebook for this study. Hypotheses, decisions, phase
> plans, and the Predictions-to-falsify table live here and are updated AS THE STUDY
> RUNS. `study.yaml` is the machine-readable contract; this file is the narrative.
> The loop invariants live in the repo `CLAUDE.md` and `.claude/skills/klein/SKILL.md`
> Hard Rules — this file does not restate them, it applies them to THIS study.

## Goal & track metric contract

**Goal:** {{GOAL}}

**Track:** `{{TRACK}}` · **Primary metric:** `{{METRIC_NAME}}` ({{METRIC_GOAL}} is
better). Every distinct task has its own track frontier, minimum meaningful delta, and
guardrails. Everything else (PR-AUC, brier, wall_seconds, ...) goes to
`aux_metrics.tsv`, never into `results.tsv`.

**Schema:** schema-v2 `results.tsv` is a derived view of immutable
`runs/E####/manifest.json` records. Its shape is defined in `kleinlib/schema.py`; do
not hand-edit it. `study_state.json` and hash-chained `events.jsonl` record gates,
fingerprints, acknowledgements, and sealed-test access.

## Data & split contract

- **Source:** {{DATA_SOURCE}} — prepared by a locked `uv run` command through the
  exit-safe runner.
- **Split:** see `study.yaml:data.split` — FIXED train/development/test partitions.
  Adaptive work sees train/development only; each track gets one sealed final-test
  access. Comparability and confirmation depend on it.
- The DATA gate (`data_card.md`) must say **go** before the first modeling run.

## Mutable surface

- **Mutable:** `train.py` ONLY. The per-experiment diff is 5–15 lines.
- **Fixed:** `prepare.py`, `study.yaml`, `kleinlib/` — changing these is rare and
  deliberate, never part of an experiment diff.
- Sweeps are the ONE exception and live under `sweeps/` — see
  `.claude/skills/klein/references/sweep-rules.md`.

## Phases & budgets

Authoritative copy is `study.yaml:phases`. Mirror here for quick reading; STOP for user
ack at every phase boundary.

| Phase | Description | Max exp | Total budget | Per-run max |
|---|---|---|---|---|
| adaptive-1 | split-identity anchor + bounded adaptive work | 4 | 3600s | 600s |
| confirmation | one sealed final-test evaluation per track | 1 | 900s | 600s |

## Research questions

Authoritative copy is `study.yaml:research_questions`. One verdict per RQ in
`findings.md`, each citing evidence experiment IDs.

| ID | Question | Prior (honest expectation) |
|---|---|---|
| RQ1 | {{RQ1_QUESTION}} | {{RQ1_PRIOR}} |

## Predictions to falsify

Fill `predicted` NOW (before running); fill `observed` + `verdict` during SYNTHESIZE.
A prediction with no verdict is an unfinished study.

| Lever | Predicted Δ | Observed Δ (exp IDs) | Verdict |
|---|---|---|---|
| {{LEVER_1}} | {{DELTA_1}} | | |

## Guardrails (this study)

- **Single safe runner:** `uv run --locked klein run-one --study . --track <track>` runs one
  unbuffered, locked subprocess, preserves its exit code, and enforces
  `max_run_seconds`. Never pipe a training command through `tee`.
- **Candidate commit first, then evidence transaction.** Every keep, discard, and
  crash has a resolvable candidate commit; `results.tsv` is regenerated afterward.
- **Status honesty:** keep / discard / crash. A crash is logged with `NA` metric, not
  retried into oblivion. A missing manifest is an interrupted transaction: recover it.
- **Sweeps:** only via the escape-hatch — every trial to a sidecar TSV, one winner
  transaction / derived result.
- **Phase-boundary acks:** summarize, STOP, and record the user acknowledgement with
  `klein gate record phase` before continuing.
- **Branch:** exact `experiments/{{STUDY_ID}}`; preflight rejects every other branch.
- **Claims:** until a sealed final-test run exists, findings are exploratory. A small
  delta without uncertainty is not “real” or “decisive.”

## Log (append-only)

Narrate decisions here as the study runs — why each direction, what a cluster of
discards taught you, where you changed course. This is what SYNTHESIZE mines.

- {{DATE}} — study scaffolded. Next: CONSULT confirm → DATA gate → METHOD gate.
