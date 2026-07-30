# Klein Auto Research — Copilot instructions

This repository is an ML research framework that runs disciplined, git-ledgered
experiment **studies** through a six-stage lifecycle. The canonical operating
manual is **`AGENTS.md`** at the repo root — read it before making changes or
running a study; the stage protocols it maps to (plain markdown under
`.claude/skills/klein/`) are the source of truth.

Golden rules (details in AGENTS.md):

- Always locked `uv run ...`, never bare `python`; set up with `uv sync --locked`
  (dev tools are a default dependency group; add `--extra gbdt --extra deep` for
  the optional stacks, named together).
- Never edit an executed study's ledgers, `findings.md`, or `program.md` — they
  are immutable exhibits. New results = new experiments.
- Experiment loop (schema v2): edit `train.py` only (5–15 line diffs), then run
  exactly one candidate transaction with
  `uv run --locked klein run-one --study studies/NN-slug --track <track>`.
  It commits the candidate BEFORE execution, runs one bounded foreground
  subprocess, restores `train.py` on a non-keep, and derives `results.tsv` —
  never hand-edit the v2 ledger; the evidence is `runs/E####/manifest.json` +
  `events.jsonl`. After an interruption: `klein recover`.
- Gates are machine state: `klein gate record consult|data|method` (or
  `gate override ... --reason`) before any modeling; phase boundaries are
  acknowledged with `klein gate record phase --phase <id>`. Close a study with
  `klein finalize`.
- Studies run on `experiments/<study>` branches, never on `main`.
- The results schema is single-sourced in `kleinlib/schema.py`; everything that is
  not the one primary metric goes to `aux_metrics.tsv`.
- Tests: `uv run --locked pytest` (framework suite; study test dirs are named
  explicitly by CI with the right extras). Full pipeline proof:
  `bash scripts/verify_e2e.sh`.
