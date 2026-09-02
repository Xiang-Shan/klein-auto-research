# Contributing to Klein Auto Research

Thanks for your interest! Klein is a small, opinionated framework — contributions
that respect its invariants are very welcome.

## Setup & checks

```bash
uv sync --locked --extra encoders
uv run --no-sync pytest kleinlib/tests .claude/skills/klein/scripts/tests scripts/tests
uv run --no-sync ruff check kleinlib scripts .claude/skills/klein/scripts
uv run --no-sync python scripts/verify_shipped_studies.py   # every shipped ledger still verifies
bash scripts/verify_e2e.sh
```

CI additionally runs Python 3.11–3.14, all-extras deep/GBDT tests, an 80% engine
coverage floor, CPU reproduction anchors, macOS/Windows CLI smokes, and a clean
wheel installation. Scheduled jobs check dependency resolution and Apple MPS.

## Ground rules (the invariants)

These are load-bearing; PRs that renegotiate them will be declined:

- **Schema is single-sourced** in `kleinlib/schema.py`. Nothing restates the
  results columns; scripts import the schema from `kleinlib.schema` and fail
  loudly if the engine is absent.
- **Executed studies are immutable history.** Never edit a shipped study's
  `results.tsv`, `findings.md`, `program.md`, `claims.lock`, or receipts. New
  results = new experiments in your own study; new knowledge = an erratum that
  re-scopes, never a deletion. Schema-2 studies verify under schema-2 rules
  forever — a schema-3 check is never enforced on them.
- **One primary metric per track**; unrelated tasks use separate tracks and
  everything non-primary goes to `aux_metrics.tsv`; tables a registered cell
  produces are pinned with `artifact:` lines.
- **Every candidate is committed before execution.** Discards, crashes and
  measured cells remain resolvable evidence. The mutable surface may be restored
  afterward, but the candidate commit and immutable run manifest remain.
- **Evidence is transactional.** Append-only events and run manifests are the
  source record; `results.tsv` is the derived compact view. Use `klein recover`
  after interruption instead of hand-editing half a transaction.
- **Final test data is sealed.** Adaptive work uses train/development data; each
  track receives at most one final-test access, rehearsed first by the sealed
  dry-run.
- **Predictions are adjudicated by the notary, never by prose.** A prediction's
  rule is declarative arithmetic on printed keys — no `eval`, no model — and its
  verdict is written inside the run transaction.
- **The verifier is never in the mutable surface.** A declared verifier script is
  hashed at the METHOD gate; the disposition uses its number, not the searcher's.
- **Claims are locked and numbers have homes.** `claims.lock` is produced by
  `klein claims`, append-only across its git history; every numeral in findings,
  lock and tutorial is a copy of a pinned value. A PR that retypes a number fails.
- **The referee is independent by mechanism.** Schema-3 `finalize` requires a
  referee gate recorded from a report written in a fresh context, on a different
  model or tool than the experimenter wherever possible; the rung reached is on
  the record.

## Good contribution targets

- New evaluator shapes (multiclass, survival, ranking) — with a worked study
  proving them, per the repo's own ethos.
- New method cards under `knowledge/method_cards/` (intuition → math → minimal
  implementation → when-it-pays → verified references).
- New studies: scaffold with `uv run --locked klein new NN-slug`, run the full
  lifecycle, and include `findings.md` + tutorial.
- New modalities' leakage helpers (sequence identity clustering, graph scaffold
  splits) and new profiles under `.claude/skills/klein/references/profiles/`.
- Portability fixes (Windows paths, `git worktree` on Windows, devices).

## Style

Match the surrounding code; one falsifiable idea per candidate (the diff can be
any size, but it is one idea); comments only for constraints the code can't
express. Run `uv run --no-sync pytest`
after the locked sync and before pushing.

## Security reports

Do not open a public issue for a suspected vulnerability. Follow the private
reporting instructions in [`SECURITY.md`](SECURITY.md).
