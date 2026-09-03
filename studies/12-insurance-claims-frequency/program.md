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
- 2026-09-03 — Disclosure: `KLEIN_SMOKE=1 python train.py` was run on the E0001
  candidate as the one sanctioned off-loop syntax/shape check, at 07:59Z — AFTER the
  consult gate was recorded at 07:57:41Z, not before it. It printed the canonical block
  cleanly (`primary_metric` 0.614140, `anchor_gap` −0.011322 against the v1 anchor) and
  wrote no sidecar, no snapshot, no manifest and no ledger row. It is disclosed here
  rather than left silent, and it is NOT a scouting-ledger entry, because the ledger
  records what was seen BEFORE the contract existed: every rule that this number could
  possibly bear on — P1's target 0.625462 and its tolerance 0.0225 — was already frozen
  in the `study.yaml` the consult gate hashed to
  `49a59d02fe9a0157a6b195a4347b6fa86fce82ddeded81f2fca0c6193a86bba4`. With
  `minimum_delta` still 0 no floor existed either, so `delta_in_floors` was not printed
  and no floor-relative rule could have been read off it.
- 2026-09-03 — Decision: the rung DEFINITIONS live in `lib/rungs.py`, stable study
  library code, and `train.py` keeps only the four per-experiment constants. The loop
  contract puts a study's `lib/` beside `kleinlib/` and `prepare.py` — it changes
  rarely, deliberately, and never inside a per-experiment diff. The reason it matters
  here: `sweeps/noise_floor.py` must fit the SAME models the ledger runs. Re-typing them
  in the floor script (study 00's choice) would let the floor describe a model this
  study never fitted; importing them from the mutable surface would let a
  per-experiment edit silently change what the floor was measured on. A stable library
  module has neither failure, and the per-experiment diff is now four lines.
- 2026-09-03 — Decision, recorded BEFORE the Phase 0 measurement: **the paired floor is
  measured on the pair (`glm_ohe_balanced`, `hgbt_balanced`)**. Three reasons, none of
  them the size of the answer, which is not yet known: (i) they are the two most
  dissimilar scorers in the ladder, so their paired difference has the widest sampling
  spread of any pair this study compares — the bar it yields is conservative for every
  other comparison, and a conservative bar cannot manufacture a keep; (ii) both are v1
  rungs, so the floor is measured on configurations the source study committed;
  (iii) neither is an isotonic rung, so the calibration lever RQ4 asks about is not
  touched at Phase 0 and E0004's numbers stay unseen until E0004 runs.
- 2026-09-03 — Decision, also recorded BEFORE the measurement: **k = 20 replicates for
  the contract's floor block, with a 1000-replicate run beside it in its own sidecar.**
  The schema-3 bar is `max(2*std, range/2)`, and `range` is an order statistic: its
  expectation grows with the replicate count (≈3.7 sigma at k = 20, ≈6.5 sigma at
  k = 1000). At k = 1000 the rule would therefore return ≈3.2 sigma and inflate the bar
  by about 60 % for a reason that is an artefact of counting, not a property of the
  measurement; at k = 20, `2*std` binds and the bar is the conventional two-standard-
  error bar for a paired comparison. The 1000-replicate run is executed anyway so the
  k = 20 spread can be checked against a precise estimate of the same quantity, and this
  study pre-commits here: **if any registered verdict would flip between the k = 20 bar
  and the k = 1000 bar, findings §③ must say so explicitly** rather than quoting only
  the bar that was declared.
- 2026-09-03 — Disclosure, recorded before Phase 0 runs: measuring a paired floor
  requires fitting both rungs of the pair, so this study will know the development AUCs
  of `glm_ohe_balanced` and `hgbt_balanced` before E0001 and E0003 file them as
  evidence. That is what Phase 0 metrology is (study 00 fitted its anchor the same way),
  and it changes nothing that is still open: every prediction's rule, target and
  tolerance was frozen in the `study.yaml` the consult gate hashed, the four rungs and
  their order were fixed in the hashed `research_plan.md`, and the dispositions are
  arithmetic the notary performs. What this study's loop demonstrates is a REGISTERED
  ladder, not an adaptive search, and the plan said so before the first fit.

## The DATA gate: a FAIL, and what was done about it

- 2026-09-03 — The clean-room auditor (a `klein-data-auditor` subagent on sonnet,
  fresh context, reading only `study.yaml`, `prepare.py`, `fixtures/README.md` and the
  prepared artifact) returned **NO-GO**. Row 3 of the mechanized four-row audit fails:

  ```
  [FAIL] duplicate-rows: 615 duplicated row-content hash(es) straddle partitions
         (train/development=297, train/test=310, development/test=32)
  ```

  Rows 1, 2 and 4 pass; the negative control fires correctly (constant predictor
  val_auc 0.5000, label-shuffled 0.5114). The card ranks 1 BLOCKER, 3 WARN and 4 NOTE.
- 2026-09-03 — Decision: **the DATA gate is OVERRIDDEN, not fixed, and the size of the
  accepted risk is measured on every run from here on.** The reasoning, in full,
  because this is the study's most consequential judgment call:

  1. **What the check found is real and is not this study's doing.** 300 of 5,859
     development rows (5.12 %) and 312 of 5,860 sealed rows (5.32 %) are byte-identical
     — all 45 columns, target included — to a row in the 46,873-row training partition.
     `tables/duplicate_exposure.tsv` measures it, and measures the same thing for the
     partition the v1 study used: **612 of its 11,719 validation rows, 5.22 %, carried a
     training twin.** The v1 quickstart never ran this check, and neither did the
     215-experiment ancestor campaign. Every anchor this study is chasing was measured
     on a contaminated holdout.
  2. **A reseed cannot fix it and a real fix would delete the question.** The cause is
     the coarse feature space (22 region codes, 11 models, 17 binary flags), so
     duplicate content recurs at 6.1 % table-wide. The two structural fixes — dedupe in
     `prepare.py`, or a `kind: group` split keyed on the row-content hash — both change
     which rows are trained on, which destroys the one identity this port is built on
     (the contract's train partition IS v1's) and makes P1, P2 and P4 compare this
     study's numbers against v1 values measured on other rows. It would also not repair
     v1's number, which is the thing being reproduced.
  3. **What the check calls contamination is, for a rating model, the normal condition
     of the data.** The modelling unit of a rate is a rating CELL, not a policy: two
     distinct policies with identical rating characteristics are supposed to receive the
     same price, and their appearing on both sides of a split is not the leak of one
     individual's outcome. The only identifier of an individual policy, `policy_id`, is
     dropped in `prepare.py` and crosses nothing. What row 3 is really reporting is that
     the feature resolution is coarse enough that a holdout cannot fully separate
     memorisation from cell-level prediction.
  4. **So the risk is accepted with a number attached, not with an assurance.**
     `train.py` now prints `twin_free_rows`, `twin_free_auc` and `twin_free_gap` on
     EVERY run: the same model's AUC restricted to the evaluation rows that have no twin
     among the rows it was fitted on. `primary_metric` stays the full-partition AUC,
     because the registered anchors compare against v1 values computed the same
     contaminated way and re-defining the measurement mid-study would make that
     comparison meaningless. The gap between the two is reported for every rung in
     findings, and every generalisation sentence in this study is scoped by it.
  5. **The card is NOT edited.** `data_card.md` says NO-GO and keeps saying NO-GO; it is
     the auditor's independent verdict, it is hashed into the gate record, and an
     orchestrator who edits an auditor's verdict to unlock a gate has destroyed the
     point of having an auditor. The disagreement lives where the protocol puts it: in
     `klein gate override data --reason`, on the event trail, where the referee reads it.
  6. **Consequence carried forward.** Every AUC in this study — and every AUC in the v1
     ledger it is compared against — is a number measured on a partition with ~5 % of
     its rows duplicated from training. Findings §③ carries this as a surprise and §⑤ as
     a scope limit; no claim in this study may be read as a clean generalisation
     estimate, and the `twin_free_auc` column is what a reader should use instead.

## Phase 0 — the floors

- 2026-09-03 — Three recipes measured, and they disagree by four orders of magnitude.
  * `seed-sweep` (k = 5, estimand `fit-noise`): std **2.50998e-06**, range 6e-06, mean
    0.614142. Five different fit seeds move the anchor in the sixth decimal. Recorded
    under `fit_noise:` as provenance; a study that had pasted this into `minimum_delta`
    would carry a keep bar of essentially zero and would keep everything that moved the
    fifth decimal.
  * `split-lottery` (k = 10, estimand `marginal-resplit`): std **0.0179641**, range
    0.055312, mean 0.606522. Re-drawing the train/development partition inside the
    train+development pool moves the anchor's OWN score by ±0.018. Reported, never a
    rule — it is the right yardstick for reading an anchor residual, and it says the
    smoke check's residual of −0.011322 against the v1 value is 0.63 of one such
    standard deviation.
  * `paired-bootstrap` (k = 20, estimand `paired-comparison`, the declared pair
    `glm_ohe_balanced` vs `hgbt_balanced`): std **0.0173021**, range 0.075161, mean
    0.0457044 → **`minimum_delta` 0.0375805 = max(2*std, range/2)**. Pasted into the
    contract with `metric.bound.ideal: 1.0` by a consult re-record.
- 2026-09-03 — Decision: the declared k = 20 block is what goes into the contract, as
  registered. Two numbers are recorded beside it because the pre-commitment above
  requires it: the 1000-replicate run of the same pair (`sweeps/paired_bootstrap_b1000`)
  gives std **0.013942** and mean 0.049029, so (i) the k = 20 spread was 24 % high,
  which is ordinary sampling error for an SD estimated from twenty draws, and (ii) the
  same `max(2*std, range/2)` rule at k = 1000 returns **0.043229** — a LARGER bar, not a
  smaller one, because the range term grows with the replicate count exactly as
  predicted. The declared bar is therefore the more permissive of the two, and any
  verdict it supports would also have to survive the stricter one; findings §③ reports
  every verdict against both.
- 2026-09-03 — Surprise, recorded before the loop: the paired floor (std 0.0173) is
  essentially the SAME SIZE as the marginal re-split floor (std 0.0180), where the
  literature and the framework's own doctrine expect the paired one to be several times
  smaller. The two rungs' AUCs correlate only ≈0.4 across resamples — a logistic
  regression and a boosted tree rank these policies differently enough that pairing buys
  almost nothing. This is the reason the bar is so large, and it is a property of the
  PAIR, not of the study's arithmetic.
- 2026-09-03 — Decision, registered BEFORE the loop: the contract carries ONE bar, but
  the ladder makes three comparisons of very different similarity (a spline GLM against
  a raw GLM; a tree against a calibrated GLM; a doctrine A/B differing by one lever).
  A single bar measured on the most dissimilar pair is conservative for the other two,
  which can suppress a real effect but can never manufacture one. After the loop closes,
  a PAIR-SPECIFIC paired floor will be measured for each of the ladder's three
  comparisons and registered as measurement sweeps, so findings can report what each
  comparison's own floor would have said. Those numbers cannot and will not change a
  registered verdict — the bar was declared at Phase 0 and stays declared; they exist so
  a reader can see how much of a "within noise" verdict is the instrument rather than
  the effect. RQ3 asks exactly this question.
- 2026-09-03 — Headroom at the start of the loop: `h = (1.0 − incumbent) / 0.0375805`.
  With no incumbent yet the audit is armed but not binding; at an anchor near 0.61 it
  sits above 10, so the frontier is not arithmetically closed. `h >= 1` is read as "not
  excluded", never as "plausible".

## Phase slates

At every phase start, run the slate ritual (references/phase-ritual.md):
propose 4-6 falsifiable candidates, score novelty / testability / expected
information 1-3, record the table and the chosen candidate here, and mirror
the ranked survivors into playbook.md "Next-best candidates".

### Phase adaptive-1 slate

Scored after the Phase 0 floor landed at `minimum_delta` 0.0375805, so testability is
judged against a bar that exists — and it is a large bar: it is 96 % of the entire
spread of the v1 ledger (0.625462 to 0.664322). Any candidate whose predicted move is
under ~0.038 cannot be decided as a KEEP by one run, and every candidate below is
scored honestly on that basis rather than pretending otherwise. Note the asymmetry
that keeps three of them worth running anyway: a run that cannot produce a keep can
still adjudicate a registered prediction (the anchors are `within` rules on
`primary_metric`, which the floor does not touch) and still measure a gap.

| # | Candidate (one hypothesis, one transaction) | Nov | Test | Info | Σ |
| --- | --- | --- | --- | --- | --- |
| 1 | `glm_ohe_balanced`: the v1 split-identity anchor, refitted on the identical training rows; decides P1 and gives the frontier an incumbent | 1 | 3 | 3 | 7 |
| 2 | `glm_splines_isotonic` against that anchor: the v1 spline+isotonic chain, recovered from prose that named its three non-default kwargs; decides P2 and P3 | 3 | 2 | 3 | 8 |
| 3 | `hgbt_balanced` against the calibrated GLM: the only rung recoverable verbatim from a committed file; decides P4 and P5 | 3 | 2 | 3 | 8 |
| 4 | `glm_ohe_none_isotonic` against the anchor: the doctrine A/B, one lever, calibration measured on Brier; decides P6 | 3 | 3 | 3 | 9 |
| 5 | Drop the six redundant categoricals the data card's WARN #4 names (`region_code`↔`region_density`, `model`↔`engine_type`/`segment` are 1:1) and refit the anchor | 2 | 1 | 1 | 4 |
| 6 | Re-run the v1 sweep's winner (`learning_rate` 0.06) against `hgbt_balanced` | 1 | 1 | 2 | 4 |

Chosen, in the order the research plan registered before the gate: 1 (a frontier needs
an incumbent before anything can be compared to it), then 2, 3, 4. Candidate 4 scores
the maximum because its outcome is decidable EITHER WAY at this floor: P6 predicts the
AUC cost is under one floor, and at a floor of 0.0376 that clause is nearly certain to
hold, while the Brier clause is a large effect the floor does not govern — so the run
adjudicates a two-clause rule rather than fishing for a keep. Candidates 2 and 3 score
2 on testability, honestly: their expected moves (+0.026 and +0.011 in the v1 ledger)
are BELOW the measured floor, so neither can be a keep, but each decides two registered
predictions and measures a gap the study exists to report.

#5 scores 1 on testability (the predicted move from dropping redundant columns is a
few thousandths, an order of magnitude under the floor) and 1 on information (a GLM's
coefficient stability is not a question this study registered). #6 scores 1 on
testability for the same reason — the v1 sweep's own lift was +0.001425, which P8 exists
to compare against the floor arithmetically, with no run needed. Both go to the playbook
queue rather than the ledger.

## Decisions — the loop

- 2026-09-03 — **E0001 KEEPS at val_auc 0.614140** and anchors the track. **P1 SUPPORTED**
  by the notary on the printed block: `|0.614140 − 0.625462| = 0.011322 ≤ 0.0225`. The
  residual is 0.63 of one marginal-resplit standard deviation (0.0179641,
  `sweep:split_lottery`) and 1.01 of the closed-form transfer standard deviation the
  tolerance was built from (0.011226, `scouting_ledger.md` S5) — the port landed
  almost exactly one predicted standard deviation from the v1 value, in a study that
  fixed that standard deviation before it ran anything. The positive control fired: a
  number an independent study recorded on the identical training rows is recovered on
  the half of its validation set this study is allowed to see.
- 2026-09-03 — First `twin_free` reading, and it goes the other way: the anchor's AUC on
  the 5,559 development rows with NO training twin is 0.615337, i.e. **+0.001198 HIGHER**
  than on the full 5,859. The duplicated rows very slightly DEPRESS the GLM rather than
  inflating it — exactly what a linear model on coarse rating cells should do, because it
  cannot memorise a cell it has already priced. H1 in the playbook predicts a tree will
  behave differently; E0003 will say.
- 2026-09-03 — **E0002 DISCARDS at val_auc 0.650095** — and it is the most informative
  row in the study so far.
  * **P2 SUPPORTED**, and not marginally: `|0.650095 − 0.651707| = 0.001612`, which is
    0.14 of the transfer standard deviation the tolerance was built from. A rung that
    survives only as PROSE, recovered because the v1 study spent two words on its three
    non-default kwargs (`knots="quantile"`, `include_bias=False`,
    `CalibratedClassifierCV(cv=5)`), reproduced ~7x more tightly than the anchor whose
    constructor was quoted from a `git show`. RQ2's prior said the verbatim rung would
    land closest; on this evidence the prose rung already beats the anchor, and E0003
    decides the rest.
  * **Decision: P3 REFUTED**, by 0.0432 of a floor. The paired lift over the same anchor
    refitted on the same rows is `delta_vs_reference` 0.035956, i.e.
    `delta_in_floors` **0.9568** against a rule that required ≥ 1. The registered reading
    is the honest one: on this portfolio, at this sample size, **the entire
    spline-plus-calibration chain — three engineered feature families and a
    cross-fitted isotonic wrapper — buys less than one measured floor of rank.** The
    pre-committed cross-check fires clean: under the stricter k = 1000 bar (0.043229) the
    same lift is 0.83 floors, so the verdict does not flip between the two bars.
    Consequence for the loop: feature engineering on the linear rung is a ruled-out
    direction for KEEP purposes on this track, and the playbook records it as such — but
    the rung is not worthless, which is what the next bullet is about.
  * The calibration half is enormous and the floor does not govern it: `val_brier`
    0.240641 → **0.058994**, a factor of 4.08, matching the v1 study's own recovered
    0.058960 to the fourth decimal. Rank and calibration are different currencies and
    this row is where an actuary sees it: 0.96 floors of rank, 4x of level.
  * `twin_free_gap` −0.001415: the duplicated rows are worth about a thousandth to this
    rung too, and again in the direction that FLATTERS the twin-free number.
- 2026-09-03 — **E0003 KEEPS at val_auc 0.664051** and takes the frontier from E0001 with
  a paired lift of +0.049911 over the incumbent, the only move in this study bigger than
  the measured floor of 0.0375805.
  * **P4 SUPPORTED**: `|0.664051 − 0.662897| = 0.001154`. The one rung recoverable
    verbatim from a committed file is the tightest reproduction of the three, as RQ2's
    prior said — but only just: the prose-with-kwargs rung (E0002) landed at 0.001612.
    **The margin between a committed file and a description that names its non-default
    kwargs is 0.000458 of AUC.** RQ2's prior is directionally right and quantitatively
    almost empty, which is a stronger endorsement of v1's advice #5 than the prior was.
  * **Decision: P5 REFUTED.** Against the calibrated GLM refitted on the same rows the
    tree wins `delta_vs_reference` 0.013956 — `delta_in_floors` **0.3714**, nowhere near
    the one floor the rule required. The actuarial reading is registered here and belongs
    in §⑤: **on this portfolio the price of a filable GLM is not resolvable.** The tree's
    edge over the calibrated linear rung is a third of one measured floor; a rate filing
    cannot be argued either way from it. Under the stricter k = 1000 bar the same lift is
    0.32 floors, so again no flip. Consequence: the frontier's one keep comes from
    beating the RAW anchor, not from beating the calibrated GLM.
  * **H1 is refuted, and cleanly.** The playbook predicted the duplicated rows would
    inflate a tree's AUC more than a GLM's, because only a tree can memorise a cell.
    E0003's `twin_free_gap` is **+0.001018** — the tree, like both GLMs, scores HIGHER on
    the rows with no training twin. Across all three rungs the duplicated rows have cost
    between −0.0014 and +0.0012 of AUC and never once flattered the headline number. The
    overridden BLOCKER is real as a checked fact and small as a measured effect, and the
    study can now say which of those it is because it measured it on every run.
  * Rank and calibration part company completely here: the tree's `val_brier` is 0.223529
    against the calibrated GLM's 0.058994, a factor of 3.79 WORSE, while it wins 0.0140
    of AUC. `val_lift_top10` 2.2167 against the GLM chain's — the best top-decile lift in
    the study.
  * Housekeeping, disclosed: E0002's and E0003's logs carry sklearn's
    `ConvergenceWarning` from the `saga` solver hitting `max_iter=2000` on the widened
    spline design matrix (E0001's plain anchor converges and emits none). The rung
    nevertheless reproduces the v1 value to 0.001612 — the v1 fit was evidently equally
    unconverged, which is what reproducing an implementation, rather than an ideal,
    looks like.
- 2026-09-03 — Headroom after the keep: `h = (1.0 − 0.664051) / 0.0375805 = 8.94`. The
  door is open by the arithmetic; that is read as "not excluded", never as "plausible" —
  study 08 stood at h = 1.015 and produced zero keeps in twenty-one attempts.
- 2026-09-03 — **E0004 DISCARDS at val_auc 0.612675** and **P6 is SUPPORTED on both
  clauses**: `brier_delta_vs_reference` −0.181304 < 0 and `|delta_in_floors|` 0.0390 < 1.
  Replacing `class_weight="balanced"` with `class_weight=None` plus a cross-fitted
  isotonic wrapper takes the Brier score from 0.240641 to **0.059337** — a factor of
  4.06 — and pays 0.001465 of AUC for it, which is one twenty-fifth of one measured
  floor. `val_logloss` moves 0.673642 → 0.233051 in the same trade. The insurance
  profile's doctrine (war story 4) reproduces on this portfolio, and the two currencies
  are now measured on the same rows in the same process rather than compared across log
  files.
  * Disclosed: this rung uses `CalibratedClassifierCV(cv=5)`, while the v1 ledger's row
    4 used `cv=3`. It is therefore NOT the v1 row-4 recipe and carries no `V1_ANCHOR`
    and no registered anchor prediction — deliberately, because cv=5 is what the v1
    study's own advice #3 and the campaign best-practices document recommend, and
    registering an anchor against a recipe this study chose not to run would have been
    dishonest. For information, and not as a rule: v1's row 4 measured −0.002603 of AUC
    and Brier 0.240153 → 0.059279; this run measures −0.001465 and 0.240641 → 0.059337.
  * `twin_free_gap` +0.001106 — the fourth consecutive rung whose duplicated rows do not
    flatter it.
- 2026-09-03 — **Phase `adaptive-1` closes with its four experiments spent**: two keeps
  (E0001, E0003) and two discards (E0002, E0004); P1, P2, P4 and P6 supported, P3 and P5
  refuted, all six adjudicated by the notary on printed blocks. The phase's headline is
  the one the study registered RQ3 to be able to find: **the v1 quickstart recorded six
  keeps on this data; under a measured paired-comparison floor its ladder yields one
  frontier improvement, and that one comes from beating the raw anchor rather than from
  any rung beating the one below it.** Playbook refreshed; the acknowledgement is the
  lead's delegated one.

### Phase confirmation slate

A confirmation phase has exactly one lawful candidate, so the ritual's job here is to
write down what was NOT done with the seal, and why.

| # | Candidate (one hypothesis, one transaction) | Nov | Test | Info | Σ |
| --- | --- | --- | --- | --- | --- |
| 1 | E0003's configuration, unchanged, once on the sealed half of the v1 validation set; decides P7 | 1 | 3 | 3 | 7 |
| 2 | seal the calibrated GLM instead, because it is the rung an actuary would file | 3 | 3 | 2 | 8 |
| 3 | seal both, to get the GLM-vs-tree gap as a difference of two sealed numbers | 3 | 1 | 3 | 7 |
| 4 | re-tune on development first, then seal the winner | 2 | 3 | 1 | 6 |

Chosen: **1**, despite #2 scoring higher on the raw sum — and the reason is recorded
because the tie-break matters. #2 is the more interesting model for the profile's
audience, but the seal confirms the FRONTIER's incumbent, and the incumbent is E0003 by
the contract's own arithmetic; sealing a rung the frontier discarded would be choosing
the confirmation subject after seeing the development numbers, which is the exact move
`confirmation` exists to prevent. The phase-ritual tie-break is expected information,
then testability, but neither can override the contract: candidate 2 is not lawful here,
so its score is moot and it is recorded as the thing that was wanted and not taken.
#3 scores 1 on testability because this study declares ONE track and a track gets ONE
sealed access; two sealed numbers would have required two tracks declared at CONSULT —
which is precisely the choice `research_plan.md` made explicitly, registering every
rung-to-rung gap as exploratory by construction before the first run. #4 is refused by
the phase budget and by the discipline.

The rehearsal (`klein run-one --final-test --dry-run`) runs first and is not optional:
study 09 lost its only seal to a crash that happened before any data was read.
- 2026-09-03 — **E0005 spends the one sealed access**: the incumbent's configuration,
  unchanged, fitted on train + development and evaluated once on the sealed half of the
  v1 validation set. `val_auc` **0.657739** against a development incumbent of 0.664051 —
  `sealed_shift_in_floors` **-0.1680**. **P7 SUPPORTED.** The seal is spent and no
  further sealed access exists on this track. Two things an actuary should read off it:
  the level held (a sixth of one floor is nothing), and `val_lift_top10` did NOT —
  2.2167 on development, **1.7067** on the sealed rows. Top-decile lift is a much noisier
  statistic than AUC at this prevalence, and a triage list built on the development
  decile would have over-promised.
- 2026-09-03 — Decision: P3 stands REFUTED on the registered bar. The spline + isotonic
  chain's paired lift over the anchor is 0.035956 = 0.9568 of the declared floor
  0.0375805 (`sweep:paired_bootstrap`), and 0.83 of the stricter 1000-replicate bar
  0.043229 (`sweep:paired_bootstrap_b1000`). The belief that "feature engineering plus
  calibration is worth more than measurement noise" is revised to: on this portfolio it
  is worth almost exactly one floor of rank and a factor of four of level, and only the
  second of those is resolvable. Consequence already taken: feature engineering on the
  linear rung is recorded as a ruled-out direction for KEEP purposes in `playbook.md`.
- 2026-09-03 — Decision: P5 stands REFUTED on the registered bar. The tree's paired lift
  over the calibrated GLM is 0.013956 = 0.3714 floors (`sweep:paired_bootstrap`), 0.32
  floors under the stricter bar (`sweep:paired_bootstrap_b1000`). The belief that "the
  price of a filable GLM is larger than measurement noise" is revised to its opposite:
  at n = 5859 development rows and a 6.4 % claim rate, the tree's edge over a calibrated
  linear model is not resolvable, so the transparency argument costs nothing this study
  can measure. Consequence already taken: the GLM-vs-tree gap is recorded in
  `playbook.md` as unusable for a filing argument, and section 5 of findings says so
  rather than quoting the 0.013956 as if it were a finding.
- 2026-09-03 — `klein replicate E0003` reproduced the kept run exactly in a detached
  worktree: `difference=0`, tolerance 0.0375805, record `rep:E0003@20260903T083929Z`.
  The engine builds that environment on its own clock, so the study's honest
  `max_run_seconds` of 300 was not consumed by the build (study 00 lost two attempts to
  exactly that).

## Post-loop metrology: the pair-specific floors

Registered before the loop and run after it closed, exactly as declared. One index draw
per replicate applied to both rungs, 1000 replicates, rungs from `lib/rungs.py`.

| Sweep | Pair | mean delta | std | max(2*std, range/2) |
|---|---|---|---|---|
| `sweep:paired_bootstrap` (the declared bar, k=20) | anchor -> tree | 0.0457044 | 0.0173021 | **0.0375805** |
| `sweep:paired_bootstrap_b1000` | anchor -> tree | 0.049029 | 0.013942 | 0.043229 |
| `sweep:pair_anchor_splines` | anchor -> spline+isotonic | 0.035339 | 0.009894 | 0.032908 |
| `sweep:pair_splines_hgbt` | spline+isotonic -> tree | 0.013690 | 0.008690 | 0.030184 |
| `sweep:pair_anchor_doctrine` | anchor -> doctrine A/B | -0.001509 | 0.001276 | 0.004537 |
| `sweep:fit_noise` (never a bar) | the anchor under 5 fit seeds | 0.614142 | 0.00000250998 | — |
| `sweep:split_lottery` (reported, never a rule) | the anchor under 10 re-splits | 0.606522 | 0.0179641 | 0.0359282 |

- 2026-09-03 — **The pre-committed disclosure fires, and it fires on P3.** The paired
  standard deviation across the ladder's own comparisons spans 0.001276 to 0.013942 — an
  order of magnitude, on the same rows, with the same instrument. Consequences, stated
  because the pre-commitment requires them and NOT as a re-adjudication:
  * P3: the lift is 0.035956. Against the declared bar (0.0375805) that is 0.9568 floors
    — refuted. Against the floor of the comparison it actually makes
    (`sweep:pair_anchor_splines`, 0.032908) it is **1.0865 floors — it would have been
    SUPPORTED.** The registered verdict stands, because the bar was declared at Phase 0
    with its pair and its replicate count on the record and a bar chosen after the
    measurement is not a bar. But the honest sentence for a reader is that this verdict
    is instrument-limited, and findings section 3 says exactly that.
  * P5: 0.013956 against `sweep:pair_splines_hgbt`'s 0.030184 is 0.4624 floors — refuted
    either way. No flip.
  * P6: |-0.001465| against `sweep:pair_anchor_doctrine`'s 0.004537 is 0.3229 floors,
    still inside one floor — supported either way. No flip. The doctrine A/B is the one
    comparison in this study whose own instrument is sharp enough (std 0.001276) to
    resolve differences a tenth the size of anything else here.
  * The conservative bar cost the study one supported prediction and cost it nothing
    else: it never turned a discard into a keep, which is the direction that matters.
