# Program — {{STUDY_ID}}

> This file is the living lab notebook for this study. Hypotheses, decisions, phase
> plans, and the Predictions-to-falsify table live here and are updated AS THE STUDY
> RUNS. `study.yaml` is the machine-readable contract; this file is the narrative.
> The loop invariants live in the repo `CLAUDE.md` and `.claude/skills/klein/SKILL.md`
> Hard Rules — this file does not restate them, it applies them to THIS study.

## Goal & metric contract

**Goal:** {{GOAL}}

**Primary metric:** `{{METRIC_NAME}}` ({{METRIC_GOAL}} is better) — the ONE number every
experiment optimizes. Everything else (PR-AUC, brier, wall_seconds, ...) goes to
`aux_metrics.tsv`, never into results.tsv.

**Schema:** the shape of `results.tsv` and `aux_metrics.tsv` is defined ONLY in
`kleinlib/schema.py`. This file never restates the column list — see
`kleinlib.schema.RESULTS_COLUMNS`. `new_study.py` wrote the header from
`kleinlib.schema.header_line()` at scaffold time; the indicative shape is
`experiment<TAB>...` (generated from kleinlib.schema — do not hand-edit).

## Data & split contract

- **Source:** {{DATA_SOURCE}} — prepared by `uv run prepare.py`.
- **Split:** see `study.yaml:data.split` — FIXED across every experiment. Never
  resample, reshuffle, or peek at the held-out split. Comparability depends on it.
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

| Phase | Description | Min/Max exp | Budget |
|---|---|---|---|
| 0 | split-identity anchors | 1–4 | 1h |
| … | (fill from study.yaml) | | |

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

- **Foreground runs only:** `uv run train.py 2>&1 | tee run.log`, terminal timeout =
  phase budget in ms. A run over budget is a `crash` (timeout note), reverted.
- **Commit-or-revert FIRST, then ONE results.tsv row.** Never the reverse; never batch.
- **Status honesty:** keep / discard / crash. A crash is logged with `NA` metric, not
  retried into oblivion. A missing row is worse than a crash row.
- **Sweeps:** only via the escape-hatch — every trial to a sidecar TSV, ONE winner row.
- **Phase-boundary acks:** summarize and STOP at each phase boundary.
- **Branch:** run on `experiments/{{STUDY_ID}}`, never `main`. Merge at study end.

## Log (append-only)

Narrate decisions here as the study runs — why each direction, what a cluster of
discards taught you, where you changed course. This is what SYNTHESIZE mines.

- {{DATE}} — study scaffolded. Next: CONSULT confirm → DATA gate → METHOD gate.
