# Changelog

All notable changes to Klein Auto Research. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[SemVer](https://semver.org/) with 0.x meaning the contract may still move.

## [0.3.0] — 2026-07-30

The distillation release: v0.2's hardening adopted, audited live, and slimmed —
plus the researcher-value layer (measured noise floors, a rolling playbook,
a phase-start slate ritual, a clean-room leakage audit, decision-trajectory
visualization) and a fourth executed study proving the v2 contract end to end.

### Added

- `docs/reviews/2026-07-30-v0.2-adoption-audit.md` — live behavioral audit of
  the v0.2 hardening: every P0 mechanism verified by driving it, 18 ergonomic
  defects found and dispositioned.
- v2 phase telemetry: `summarize_results.py` renders per-phase experiments and
  wall-seconds from `runs/E####/manifest.json` against the contract's budgets.
- Preflight warns when `train.py` still contains scaffold stubs.
- Help text on every `klein new` / `klein gate` flag.
- CHANGELOG (this file), canonical diagrams under `docs/diagrams/`.

### Changed

- **CLI verbs file their own receipts**: `klein gate record`, `finalize`, and
  `recover` commit the state files they write; derived views
  (`results_summary.md`, `progress.svg`, `figures/`) never block `run-one` and
  are swept into the next state commit. The documented loop no longer dead-ends
  on a dirty tree the CLI itself created.
- Scaffold's default `prepared_path` is CSV (parquet stays one
  `--prepared-path` away) — the core install can pass its own DATA gate.
- Data-card decision regex accepts markdown headings (`## Decision: GO`); gate
  errors name the accepted forms and explain override semantics.
- GBDT smoke fits self-isolate in subprocesses, so the default `pytest`
  collection is safe even with torch loaded (macOS arm64 dual-libomp war story
  enforced by construction; CI's three-process choreography removed).
- Dev tools moved to a default dependency group — `uv run --locked pytest`
  works as documented; default pytest collection covers framework paths only.
- The strong-claim prose lint in `finalize` is a loud warning; the
  exploratory/confirmed label check stays hard.
- `AGENTS.md`/`SKILL.md` teach the loop as three layers: the loop is yours
  (judgment) / `run-one` is the crash boundary (notary) / state files are
  receipts. Stage names and CLI verbs are mapped explicitly.
- Version is single-sourced from package metadata.

### Removed

- `kleinlib/keep_awake.py` (unused mouse-jiggler; `caffeinate -i` is the
  documented path).
- `klein migrate` — folded into `klein verify` (v1 errata print there; nothing
  was ever migrated).
- The embedded schema fallback in `preflight.py` and the five drifted asset
  templates — `kleinlib` is the single source for schema and scaffold templates.
- Dead code (`ensure_uv_locked_command_available`), the hardcoded CLI version
  string, and a stale `VIRTUAL_ENV` leaking uv warnings into archived run logs.

## [0.2.0] — 2026-07-12

The hardening release, implementing
`docs/reviews/2026-07-10-v0.1-review.md` (4 P0 / 6 P1 / 2 P2): the `klein` CLI;
transactional evidence (per-run `manifest.json`, append-only self-verifying
`events.jsonl`, `study_state.json`, `StudyLock`, atomic writes); candidate
commits before execution so negative evidence stays resolvable; a subprocess
crash boundary with real exit codes (124 on timeout); per-track frontiers with
declared direction/minimum-delta/guardrails; a sealed one-access final-test
partition with exploratory/confirmed labeling; stateful preflight (exact
branch, gate acknowledgements, artifact and split fingerprints); metric specs
that reject non-finite values; collision-proof relocatable snapshots; sweep
sidecar hardening with resume; a 7-job CI (Python 3.11–3.14 matrix, ≥80%
engine coverage, tutorial network isolation, reproduction anchors, macOS +
Windows CLI portability, clean-wheel install) plus a weekly scheduled audit
with an Apple-silicon MPS canary; `SECURITY.md`, `THIRD_PARTY_NOTICES.md`,
standard MIT `LICENSE`.

## [0.1.0] — 2026-07-10

First public release: the six-stage lifecycle (CONSULT → DATA → METHOD →
EXPERIMENT/SWEEP → SYNTHESIZE → TUTORIAL) with hard gates; `kleinlib` engine
(schema single-sourcing, data/split contract, evaluators with a collapsed-
prediction guard, 15 figure functions, snapshotting, the sanctioned
`SweepRunner` escape-hatch); the `/klein` skill with 8 reference protocols and
war stories; tool-neutral `AGENTS.md`; seed `knowledge/` base; bundled
Apache-2.0 insurance-claims dataset; three executed exemplar studies
(GLM quickstart, DAE honest-no, robust-QLS synthetic lab).

[0.3.0]: https://github.com/Xiang-Shan/klein-auto-research/releases/tag/v0.3.0
[0.2.0]: https://github.com/Xiang-Shan/klein-auto-research/releases/tag/v0.2.0
[0.1.0]: https://github.com/Xiang-Shan/klein-auto-research/releases/tag/v0.1.0
