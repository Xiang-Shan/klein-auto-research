# Contributing to Klein Auto Research

Thanks for your interest! Klein is a small, opinionated framework — contributions
that respect its invariants are very welcome.

## Setup & checks

```bash
uv sync --locked --extra dev --extra encoders
uv run --no-sync pytest kleinlib/tests .claude/skills/klein/scripts/tests \
  studies/02-rqls-pv-severity/tests scripts/tests
uv run --no-sync ruff check kleinlib scripts .claude/skills/klein/scripts \
  studies/01-dae-claims/bootstrap_caches.py studies/01-dae-claims/tests/test_dae.py
bash scripts/verify_e2e.sh
```

CI additionally runs Python 3.11–3.14, all-extras deep/GBDT tests, an 80% engine
coverage floor, CPU reproduction anchors, macOS/Windows CLI smokes, and a clean
wheel installation. Scheduled jobs check dependency resolution and Apple MPS.

## Ground rules (the invariants)

These are load-bearing; PRs that renegotiate them will be declined:

- **Schema is single-sourced** in `kleinlib/schema.py`. Nothing restates the
  results columns; scripts carry an embedded fallback that is drift-asserted.
- **Executed studies are immutable history.** Never edit a shipped study's
  `results.tsv`, `findings.md`, or `program.md`. New results = new experiments
  in your own study.
- **One primary metric per v0.2 track**; unrelated tasks use separate tracks and
  everything non-primary goes to `aux_metrics.tsv`.
- **Every v0.2 candidate is committed before execution.** Discards and crashes
  remain resolvable evidence. The working `train.py` may be restored afterward,
  but the candidate commit and immutable run manifest remain.
- **Evidence is transactional.** Append-only events and run manifests are the
  source record; `results.tsv` is the derived compact view. Use `klein recover`
  after interruption instead of hand-editing half a transaction.
- **Final test data is sealed.** Adaptive work uses train/development data; each
  track receives at most one final-test access.

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
only for constraints the code can't express. Run `uv run --no-sync pytest`
after the locked sync and before pushing.

## Security reports

Do not open a public issue for a suspected vulnerability. Follow the private
reporting instructions in [`SECURITY.md`](SECURITY.md).
