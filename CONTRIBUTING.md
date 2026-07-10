# Contributing to Klein Auto Research

Thanks for your interest! Klein is a small, opinionated framework — contributions
that respect its invariants are very welcome.

## Setup & checks

```bash
uv sync --extra dev
uv run pytest kleinlib/tests .claude/skills/klein/scripts/tests studies/02-rqls-pv-severity/tests
bash scripts/verify_e2e.sh        # 19-check end-to-end proof (~2 min)
```

CI runs the same suites on ubuntu plus two study smoke gates; a green
`verify_e2e.sh` locally almost always means green CI.

## Ground rules (the invariants)

These are load-bearing; PRs that renegotiate them will be declined:

- **Schema is single-sourced** in `kleinlib/schema.py`. Nothing restates the
  results columns; scripts carry an embedded fallback that is drift-asserted.
- **Executed studies are immutable history.** Never edit a shipped study's
  `results.tsv`, `findings.md`, or `program.md`. New results = new experiments
  in your own study.
- **One primary metric per study**; everything else goes to `aux_metrics.tsv`.
- **Commit-or-revert first, then exactly one ledger row** — the loop contract in
  `AGENTS.md` and `.claude/skills/klein/SKILL.md`.

## Good contribution targets

- New evaluator shapes (multiclass, survival, ranking) — with a worked study
  proving them, per the repo's own ethos.
- New method cards under `knowledge/method_cards/` (intuition → math → minimal
  implementation → when-it-pays → verified references).
- New studies: scaffold with
  `uv run python .claude/skills/klein/scripts/new_study.py`, run the full
  lifecycle, and include `findings.md` + tutorial.
- Portability fixes (Windows paths, non-MPS torch devices).

## Style

Match the surrounding code; keep experiment diffs thin (5–15 lines); comments
only for constraints the code can't express. Run `uv run pytest` before pushing.
