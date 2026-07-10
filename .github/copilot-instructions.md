# Klein Auto Research — Copilot instructions

This repository is an ML research framework that runs disciplined, git-ledgered
experiment **studies** through a six-stage lifecycle. The canonical operating
manual is **`AGENTS.md`** at the repo root — read it before making changes or
running a study; the stage protocols it maps to (plain markdown under
`.claude/skills/klein/`) are the source of truth.

Golden rules (details in AGENTS.md):

- Always `uv run ...`, never bare `python`; set up with `uv sync --extra dev`.
- Never edit an executed study's `results.tsv`, `findings.md`, or `program.md` —
  they are immutable exhibits. New results = new experiments.
- Experiment loop: edit `train.py` only (5–15 line diffs), run in the foreground,
  commit-or-revert FIRST, then append exactly ONE `results.tsv` row
  (`keep`/`discard`/`crash`).
- Studies run on `experiments/<study>` branches, never on `main`.
- The results schema is single-sourced in `kleinlib/schema.py`; everything that is
  not the one primary metric goes to `aux_metrics.tsv`.
- Tests: `uv run pytest kleinlib/tests .claude/skills/klein/scripts/tests
  studies/02-rqls-pv-severity/tests -q`; full pipeline proof:
  `bash scripts/verify_e2e.sh`.
