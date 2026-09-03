# Program — 12-insurance-claims-frequency

## Roster

Who is doing what, and on what. REFEREE cites this table for the independence rung
(`references/referee-protocol.md`); a blank `experimenter` row caps the achievable
rung at "fresh session", because no artifact then says what ran the loop.

| Role | Who (model · tool · session) | Since |
| --- | --- | --- |
| experimenter (CONSULT → SYNTHESIZE, every `run-one`) | a Claude Code general-purpose subagent · `claude-opus-5` · a fresh git worktree, this session | 2026-09-03 |
| data-gate auditor | `klein-data-auditor` · `sonnet` · fresh context, clean room (reads `study.yaml`, `prepare.py`, the prepared artifact and the leakage output; never `program.md` or `train.py`) | 2026-09-03 |
| referee | (left blank until Gate 3 runs) | — |
| lead | Claude Fable 5.1 · orchestrator · owns the delegated acks and spawns the referee | 2026-09-03 |

**Independence rung expected: `fresh session`** unless the referee runs on a different
model. The experimenter here is an Opus-class Claude Code subagent; if Gate 3 is another
Opus context the model half of the ladder is NOT met and the gate record must say so.

This is the living lab notebook. `study.yaml` is the machine contract;
`study_state.json`, `events.jsonl`, and `runs/E####/manifest.json` are generated audit
state and must not be hand-edited.

## Goal and track contract

- Goal: does the v1 quickstart's three-rung ladder reproduce under the schema-3
  contract; does prose-with-kwargs reproduce as tightly as a committed file; how big is
  the paired-comparison floor on this portfolio and how many of v1's six keeps clear it;
  and does the calibration-first doctrine hold.
- Kind / modality / profile: `predict` / `tabular` / `insurance`. Schema 3.
- Track: `primary`, mode `frontier`. Metric `val_auc`, higher is better.
- `minimum_delta` is measured at Phase 0 (`paired-bootstrap` / `paired-comparison`) and
  pasted in by a consult re-record; it is never guessed. `metric.bound.ideal` is 1.0 and
  is declared in the same re-record, because the engine refuses a bound without a floor
  estimand.
- Results are exploratory until the track's one sealed final-test run confirms them, and
  **every rung-to-rung gap in this study is exploratory by construction**: one track has
  one sealed access, which can confirm a LEVEL and never a difference. Registered up
  front so that no later sentence can stretch the word.
- A small delta without uncertainty must not be described as real or decisive. No
  `materiality:` block is registered, so nothing here may be called "material" or
  "actionable" — the honest phrasing is that a registered bar was or was not cleared.

## Data and split

- Source: `bundled:insurance-claims` — 58,592 policies, 45 prepared columns, claim rate
  0.063968. `prepare.py` reproduces the v1 prepared table; the check is the 2,000-row
  fixture, regenerated here and byte-identical to v1's (`scouting_ledger.md` S6).
- Split: `stratified`, seed 42, development 0.10, test 0.10, all from `study.yaml`.
  No seed and no partition rule is written as a literal in any script the study owns
  (war story 8). By index arithmetic done before the gate (S4): the contract's TRAIN
  partition IS the v1 training partition (46,873 rows, identical index set), and
  `development ∪ test` is exactly the v1 validation partition, split 5,859 / 5,860.
- Adaptive work uses train + development only. The sealed half stays sealed until the
  one confirmation run.
- Gate 1 records the prepared-data SHA-256 and the realized partition fingerprints.

## Research questions

- **RQ1** — do the three v1 rungs reproduce within 0.0225 (two standard deviations of
  the transfer, derived in S5) of the values the v1 ledger recorded? Prior: yes, all
  three `(source: scouted — S1, S4, S5)`.
- **RQ2** — v1's own advice #5 was to spend two words of a description on the
  non-default kwargs. One rung here is recoverable verbatim from a committed file and
  two survive only as prose that names its kwargs. Does prose-with-kwargs reproduce as
  tightly as code? Prior: the verbatim rung lands closest; the prose rungs land inside
  the same band with visibly larger residuals `(source: scouted — S3)`.
- **RQ3** — how large is the paired-comparison floor here, and how many of the v1
  ledger's six keeps clear it? Prior: `(source: uninformed)` — no floor has ever been
  measured on this data. A few thousandths of AUC is expected, which would leave v1's
  sweep keep (+0.001425) below the bar.
- **RQ4** — does the calibration-first doctrine reproduce? Prior: yes `(source:
  scouted — S1)`.

## Registered predictions

Two families, both fixed before the evidence existed. The ANCHOR family (P1, P2, P4)
carries a v1 LEDGER value as its target and the tolerance 0.0225 = 2 × 0.011226, the
closed-form standard deviation of the transfer, derived in `scouting_ledger.md` S5 from
row counts and a class balance alone. The FLOOR family (P3, P5, P6, P7) is written in
integer counts of the MEASURED floor, which does not exist at registration time.

| P# | Statement (short) | Rule | Decided by |
|---|---|---|---|
| P1 | the raw-feature GLM anchor reproduces v1's 0.625462 | `primary_metric within {target: 0.625462, tol: 0.0225}` | E0001 `--tests P1` |
| P2 | the spline + isotonic GLM rung reproduces v1's 0.651707 | `primary_metric within {target: 0.651707, tol: 0.0225}` | E0002 `--tests P2` |
| P3 | that rung beats the anchor by ≥ 1 measured floor on the same rows | `delta_in_floors >= 1` | E0002 `--tests P3` |
| P4 | the HGBT rung (the verbatim one) reproduces v1's 0.662897 | `primary_metric within {target: 0.662897, tol: 0.0225}` | E0003 `--tests P4` |
| P5 | the tree beats the calibrated GLM by ≥ 1 measured floor on the same rows | `delta_in_floors >= 1` | E0003 `--tests P5` |
| P6 | doctrine: Brier improves and the AUC paid is < 1 floor | `all_of(brier_delta_vs_reference < 0, abs(delta_in_floors) < 1)` | E0004 `--tests P6` |
| P7 | the sealed score lands within 2 floors of the development incumbent | `abs(sealed_shift_in_floors) <= 2` | E0005 `--tests P7` |
| P8 | v1's sweep keep (+0.001425) is smaller than this study's measured floor | manual | `klein predict adjudicate` against the Phase 0 sidecar |

`n_comparisons` per family is stated in findings §②: three anchors, three floor-relative
run rules, one sealed rule, one manual arithmetic — each bound to one run (or one
sidecar) fixed in advance, with no post-hoc selection among candidate comparisons.

## Phase plan

| Phase | What happens | Budget | Max experiments |
|---|---|---|---|
| (Phase 0, no ledger rows) | three floor recipes into three sidecars; `klein noise-floor` prints the contract block; a consult re-record pastes it together with `metric.bound.ideal` | — | — |
| `adaptive-1` | E0001 anchor → E0002 spline+isotonic → E0003 HGBT → E0004 doctrine A/B | 3600 s | 4 |
| `confirmation` | sealed dry-run, then E0005 once on the sealed half | 900 s | 1 |

## Controls

- **Negative control** — the DATA gate's mechanized four-row clean-room leakage audit
  (`python -m kleinlib.leakage`): a constant predictor and a label-shuffled predictor
  must score at chance. A pipeline that cannot score chance at chance cannot be trusted
  with 0.66.
- **Positive control** — E0001, which must recover a number an independent study already
  recorded on the identical training rows. It runs first, and a miss stops the study
  rather than being absorbed into the ladder.

## Workflow

1. `scouting_ledger.md` committed FIRST, then `klein gate record consult` — in this
   engine version the consult gate hashes the ledger too
   (`GATE_OPTIONAL_ARTIFACTS`), so the disclosure is notarized, not merely committed.
2. `prepare.py`, the modality-typed profile, the clean-room leakage audit,
   `data_card.md` = GO; `klein gate record data`.
3. `method_card.md` + `references.yaml`; `klein gate record method`.
4. Phase 0 floors; paste the measured block and the bound; consult re-record with a
   reason; `klein preflight`.
5. The loop: edit `train.py` (two constants), `klein run-one --tests P#`.

Every candidate is committed before execution. Discards and crashes remain resolvable
commits; the evidence transaction then restores `train.py` to the pre-candidate base
commit.

## Decisions (append-only)

- 2026-09-03 — schema-v3 study scaffolded (`predict` / `tabular` / `insurance`); gates
  pending.
- 2026-09-03 — the user's gate acknowledgements are DELEGATED to this agent for the
  Klein 2.0 exhibit studies, on the lead's standing instruction. Every gate below is
  recorded with `--acknowledged-by lead-agent`, and the same applies to the phase
  acknowledgements. Nothing else about the gates changes: the artifacts still have to
  exist, be placeholder-free, and hash.
- 2026-09-03 — Decision: the split is `stratified, seed 42, development 0.10, test 0.10`
  and not the scaffold's 0.20 / 0.20. Reason on the record before any run: at
  0.10 / 0.10 the contract's train partition is EXACTLY the v1 study's training
  partition and `development ∪ test` is exactly its validation partition
  (`scouting_ledger.md` S4). The port therefore refits the v1 models on the v1 rows and
  changes only which rows they are graded on. The price is accepted openly: a 5,859-row
  development partition has a higher sampling standard error (0.015876 vs 0.011226) than
  a 20 % one would, so the measured keep bar will be larger and the frontier less
  sensitive. Identity with the source study was judged worth more than sensitivity for a
  study whose first question is whether the source reproduces.
- 2026-09-03 — Decision: the anchor tolerance is 0.0225, derived from row counts and a
  class balance BEFORE any run (`scouting_ledger.md` S5), not the v1 study's ±0.001.
  A ±0.001 identity tolerance was only ever available to v1 because v1 re-measured on
  the same rows; schema 3 mandates a sealed third partition, so no lawful split can
  reproduce the v1 evaluation set. Registering ±0.001 anyway would have been a
  prediction with a ~5 % chance of holding for reasons that have nothing to do with the
  port — theatre, not a test. The launch brief quoted ±0.001 and this study departs from
  it deliberately; the reasoning is in the ledger's Retirements and in
  `research_plan.md`.
- 2026-09-03 — Decision: the P2 anchor target is the v1 ledger's 0.651707, not the
  0.6528 the brief quotes. 0.6528 is the ancestor campaign's exp47 number, which the v1
  study approached (−0.001093, row 5) and missed (−0.027, row 2); no ledger in this
  repository holds it as a measurement (`scouting_ledger.md` S2).
- 2026-09-03 — Decision: `confirmation.require` is `[sealed]` and not
  `[sealed, replicate]`. `klein replicate E0003` is still run, and its record is cited,
  but a study should not be labelled exploratory because a detached-worktree environment
  build failed (study 00 lost two replicate attempts that way). What the seal confirms is
  the incumbent's LEVEL; every gap here stays exploratory by construction and the plan
  says so before the first run.
