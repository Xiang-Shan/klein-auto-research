# Klein Auto Research — Copilot instructions

This repository is a framework for **process-verifiable research studies** for AI
for Science. The canonical operating manual is **`AGENTS.md`** at the repo root —
read it before making changes or running a study; it holds the lifecycle, the stage
map, the loop contract and the full rules. The stage protocols it maps to (plain
markdown under `.claude/skills/klein/references/`, or `klein explain <topic>` from any
directory) are the source of truth, and `klein <verb> --help` documents every command.

The five rules that matter most:

- **Commands:** `uv sync --locked`, then `uv run --locked klein …` in this repository
  (add `--extra gbdt --extra deep --extra encoders` together; naming only some extras
  removes the others). `klein next --study studies/NN-slug` names the one next action.
- **Gates:** a study moves CONSULT → DATA → METHOD → EXPERIMENT/SWEEP → SYNTHESIZE →
  REFEREE → TUTORIAL; modeling is blocked until the first three gates are recorded
  with `klein gate`, and `klein finalize` runs only after the referee gate, written in
  a fresh context on a different model or tool than the experimenter.
- **One candidate, one notary:** edit only the files `entrypoint.mutable` names (one
  falsifiable idea), then run `klein run-one --study studies/NN-slug --track <track>`.
  The notary commits the candidate first and decides the disposition by the contract's
  arithmetic. Never hand-edit a ledger, a manifest, `claims.lock` or `events.jsonl`;
  predictions are adjudicated by the notary, never by prose.
- **Looking is on the record:** explore with `klein probe`, never in an ad-hoc script;
  a probe can lead to a prediction but never supports a claim.
- **Shipped studies are immutable exhibits** (`studies/ARCHIVE.md` indexes the archived
  ones); studies run on `experiments/<study>` branches, never on `main`. Klein 3 judges
  schema 3 only. Tests: `uv run --locked pytest kleinlib/tests
  .claude/skills/klein/scripts/tests scripts/tests`.
