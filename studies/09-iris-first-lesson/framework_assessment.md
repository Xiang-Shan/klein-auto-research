# Framework assessment — klein @ e99a89a, audited before Study 09's CONSULT gate

Question: does expressing Study 09's registered design require any change to
`kleinlib` or the klein skill? **Answer: NO — zero core changes.** Everything
the design needs is either implemented-and-tested in the framework or
legitimately study-local by the framework's own architecture. This file is the
required P0/P1/P2 record. Baseline evidence: full suite 306 passed / 6 skipped
at `e99a89a`; every mechanic below was verified against source before this
study opened (workflow.py line references as of that commit).

## 1. Already supported and verified (used as-is)

- **Bounded-metric headroom** — `metric.bound {ideal, on_infeasible∈{ack,warn,
  block}}`, `track_headroom` h=(incumbent−ideal)/δ, disclosure at preflight and
  verify, enforcement at run-one, `klein headroom ack` (refuses at h≥1; demands
  a note; hash-chained event; self-commit). Nine dedicated tests. **Study 09 is
  the FIRST SHIPPED STUDY to arm `bound`** (07/08 declare none; 08's headroom
  was a hand-computed comment) — first-user friction is budgeted, and any
  misbehavior on this path is a P0 finding to report, never to hack around.
- **`noise_floor.estimand`** schema (`marginal-resplit | paired-comparison`),
  required once a floor block exists alongside a declared bound.
- **Sealed-look enforcement** — one access per track, tamper-evident
  ledger-derived refusal, final-phase-only, development-forbidden-in-final,
  access burned before the child process launches.
- **Group-aware splitting + leakage machinery** — `three_way_split(kind=group)`,
  split fingerprint frozen at DATA and re-enforced at run-one,
  `kleinlib.leakage` duplicate-rows-straddle and normalized group-overlap
  blockers.
- **Ledger integrity** — hash-chained `events.jsonl`, immutable manifests,
  derived `results.tsv`, gate artifact-hash freezing with the sanctioned
  re-record flow (08 precedent: lone consult re-record after the floor paste).
- **`finalize` / `verify`** — including `--allow-exploratory`, which Branch B
  pre-registers as its planned path.

## 2. P0 needs — all study-local by design (no kleinlib change to make)

The framework deliberately leaves the experiment layer to the study; each item
below is authored in `studies/09-iris-first-lesson/` with tests:

- **Selection guard** (repeat-level sign-flip max-t, 1024 enumeration, fixed
  42-cell family): no engine support exists; ported from the frozen
  `08/sweeps/rematch_analysis.py` reference implementation.
- **Candidate-specific paired floors**: the ledger holds one scalar
  `minimum_delta` per track by design; per-candidate floors live in metrology
  sidecars as CLEARANCE bars (registered direction rationale in
  `noise_floor_protocol`), the scalar = ceil3dp(max over challengers).
- **Repeated group-aware CV arena + nested rung ladder + roster module**:
  ported from `08/sweeps/rematch_arena.py` + `families.py`; sklearn's
  `StratifiedGroupKFold` imported directly (no kleinlib CV-with-groups exists).
- **Group-aware coda entry**: 08's `build_coda` hard-coded non-group `cv=3`
  (lawful there only because its non-sealed pool held no multi-row group);
  09's port forwards the precomputed group-aware splits and gives the subset
  wrapper a groups channel — registered before the confirmation phase.
- **TabPFN availability/determinism**: no framework check exists; study-local
  spike (scouting_ledger S7, PASSED) + frozen dormant fallback map.
- **Known-DGP simulation lane + decomposition validation**: plain study-local
  scripts (03-noisy-rosenbrock known-truth precedent); `task_type: simulation`
  plumbing exists but is not needed for a companion lane inside a
  classification study.

## 3. P1/P2 — valuable, deliberately NOT done during this study

- `klein noise-floor --estimand <v>` so the emitted YAML block carries the line
  (today it must be hand-added; the schema then validates it). P1.
- Escalate the enforced preflight floor bar from ≥1×std to the doctrinal
  `max(2×std, range/2)` (today: studies self-bind in `noise_floor_protocol`
  prose; the machine accepts 1×). P1.
- A framework paired-floor/CRN helper and `StratifiedGroupKFold` support in
  `kleinlib.data` / `evaluate_with_inner_cv` (today: study-local). P2.
- A `klein verify` receipt artifact (today: verify is console-only; 09 captures
  it via `run_with_log.py` to a committed log). P2.
- Version bookkeeping: `pyproject version = 1.2.0` and CHANGELOG carry no
  1.3.0 entry despite the merged "detection-limit release (v1.3.0)"; both prior
  claims.lock files say `klein_version: "1.2.0"`. Pin by commit, not tag. P2.
- **Resolution vs. materiality — assessed, explicitly NOT implemented.**
  `minimum_delta` and the candidate floors are MEASUREMENT-RESOLUTION
  thresholds. No decision-value model (cost of a wrong probability, portfolio
  impact, retention/pricing consequence) exists anywhere in this repository, so
  no klein artifact may describe clearing a floor as "business actionability"
  or "materiality" — 09's `claims_discipline` bans the conflation outright.
  A future optional `materiality:` contract block (own provenance: who priced
  the consequence, in what currency, dated) is sketched for the roadmap; until
  a study registers one, "actionable" in klein prose means only "Bar-2: the
  registered keep-sized bar was cleared", nothing economic. P1 to design;
  nothing to code tonight.

## 4. Verdict

Proceed with Study 09 on the unmodified framework at `e99a89a`. Zero kleinlib
edits; all expressiveness gaps closed study-locally with tests; the two
framework firsts exercised here (armed `bound`, estimand-tagged paired floor)
are the study's contribution back to the framework as lived precedent.
