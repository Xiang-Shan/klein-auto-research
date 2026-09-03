---
type: scouting-ledger
study: "12-insurance-claims-frequency"
status: closed        # closed at the CONSULT gate; later entries are a gate re-record
---

# Scouting ledger — 12-insurance-claims-frequency

> Everything looked at BEFORE the CONSULT gate, so that no registered prediction can
> pretend to a surprise it already knew. Committed before `klein gate record consult`;
> in this engine version `scouting_ledger.md` is a schema-3 OPTIONAL gate artifact and
> its sha256 is hashed into the consult record beside `study.yaml`,
> `research_plan.md` and `program.md` (`kleinlib/contract.py:GATE_OPTIONAL_ARTIFACTS`),
> so an edit afterwards fails `klein verify` until the gate is re-recorded with a
> reason. Check the `consult` event's artifact list in `events.jsonl` rather than
> taking that sentence on trust.

## §0 Disclosure

This study is a PORT: it re-runs, under Klein's schema-3 contract, the three-rung model
ladder that the v1 quickstart (`studies/00-glm-claims-quickstart`, readable at tag
`v1.3.0`) ran under the looser v1 rules on the same 58,592-policy portfolio. Almost
everything a normal study discovers, this one already knows — the v1 ledger recorded
six numbers and this file copies all of them down before the contract is written.

**No classifier was fitted before this gate.** What was looked at is (a) the v1
study's own committed artifacts, (b) index arithmetic on the partitions, (c) a
closed-form standard-error formula, and (d) a byte-level fixture comparison. None of
those is a candidate's score on this study's development partition, and none of them
is the value of any registered rule that a run will decide. The rules that carry a
v1 number as their `target` are ANCHORS — identity checks whose job is to catch a
port bug before it poisons every later comparison — which is what the consult
protocol permits scouted values to seed; every prior resting on them is labelled
`(source: scouted)` and is excluded from the §⑥ prior scorecard.

## Entries

| S# | Date | What was looked at | What was seen | Why it is not evidence | Decision |
|---|---|---|---|---|---|
| S1 | 2026-09-03 | `git show v1.3.0:studies/00-glm-claims-quickstart/results.tsv` — the v1 study's whole six-row ledger | row 1 (LR + OHE(min_freq=20) + `class_weight=balanced`) **0.625462**; row 2 (prose reconstruction of the spline chain) **0.625533**; row 3 (HGBT) **0.662897**; row 4 (doctrine: `class_weight=None` + isotonic cv=3) **0.622859**; row 5 (E2-redux, the recovered true spline+isotonic rung) **0.651707**; row 6 (HGBT `learning_rate` sweep winner) **0.664322** | a different study's numbers on a different (two-way) partition under a contract with no measured floor; nothing here was produced by this study's code or rows | rows 1, 5 and 3 become the three ANCHOR targets of P1, P2 and P4; row 6 becomes the scouted constant P8 tests against the floor this study measures |
| S2 | 2026-09-03 | the launch brief's four quoted anchors against S1 | the brief quotes **0.6255 / 0.6528 / 0.6629 / 0.6643**; the ledger recorded 0.625462 / **0.651707** / 0.662897 / 0.664322. Three of the four are the ledger's own values rounded. The fourth is not: **0.6528 was never measured by the v1 study** — it is the ancestor campaign's exp47 target, which v1's row 5 approached to 0.651707, i.e. −0.001093, and which v1's row 2 missed by −0.027 | a discrepancy between a plan's prose and a ledger's record, resolved in favour of the ledger, before any run | every `within` target below is the value the v1 LEDGER recorded, never the plan's rounding; the plan's 0.6528 is retired (see Retirements) |
| S3 | 2026-09-03 | which v1 recipes survive as code: `git log --all -- studies/00-glm-claims-quickstart/train.py`, and the candidate commits the v1 ledger names (`7c3a25b`, `ae552d5`, `b1389ca`, `2e046bb`, `1fb8ca6`, `3f3822f`) | the v1 study reached this repository as ONE squashed commit (`2c791be`); none of its six candidate commits is a valid object here. The only surviving code is `v1.3.0:.../train.py`, the row-6 snapshot, whose docstring states that row 3 differs from it by `learning_rate` alone. Rows 1 and 5 survive only as PROSE — but prose that names its non-default kwargs, because naming them was v1's own advice #5 | a fact about what code exists, not a measurement | the port's three rungs have three different recovery fidelities (verbatim / prose-with-kwargs / prose-with-kwargs) and that becomes RQ2 rather than a footnote |
| S4 | 2026-09-03 | index arithmetic only: `kleinlib.data.fixed_split` (the v1 partition: seed 42, `test_size` 0.2, stratified) against `kleinlib.data.three_way_split` at three candidate settings of `development_size` / `test_size` | at **0.10 / 0.10, seed 42, stratified** the contract's train partition is the v1 training partition EXACTLY (46,873 rows, identical index set) and `development ∪ test` is the v1 validation partition exactly (11,719 rows), split 5,859 / 5,860 with 375 positives each. At the schema-3 default 0.20 / 0.20 neither identity holds (train 35,155 rows, a different set) | no model is fitted, no metric is computed; this is which rows go where | `data.split` is declared `stratified, seed 42, development_size 0.10, test_size 0.10`: the port keeps the v1 model's TRAINING rows and splits the v1 validation set in half, one half to develop on, one half sealed |
| S5 | 2026-09-03 | the closed-form Hanley–McNeil standard error of an ROC-AUC, evaluated at the v1 anchor levels for the partition sizes S4 produced | SE ≈ **0.011226** on 11,718 rows with 750 positives (the v1 validation set, AUC 0.6255) and ≈ **0.015876** on 5,859 rows with 375 positives (this study's development partition). Because the development partition is one half of the v1 validation set, the standard deviation of the DIFFERENCE between the two AUCs is `sqrt(SE_dev² − SE_v1²)` ≈ **0.011226** | a formula evaluated on row counts and a class balance, not on any model's score | the anchor tolerance is fixed at **0.0225 ≈ 2 × 0.011226** — two standard deviations of the transfer's own sampling distribution — and is written into P1, P2 and P4 before any run |
| S6 | 2026-09-03 | whether this study's `prepare.py` reproduces the v1 prepared table: regenerated the documented 2,000-row stratified fixture (`train_test_split(train_size=2000, random_state=0, stratify=claim_status)`) from this study's prepared output and compared sha256 with `v1.3.0`'s committed fixture | **byte-identical**: `b8c9333f3dd63388dab0c02122147db428f011d1a7e964cf982c599bb5247786` on both files (2,000 rows × 45 columns) | a hash comparison of a derived artifact; no model, no partition, no metric | `prepare.py` is accepted as a faithful port and the fixture is committed under this study's `fixtures/` |
| S7 | 2026-09-03 | the prepared table itself: shape, target rate, and the dtype the 19 boolean-ish columns load with under this machine's pandas | 58,592 rows × 45 columns, claim rate **0.063968**; the raw `is_*` / `rear_brakes_type` / `transmission_type` columns report dtype **`str`**, not `object` | descriptive profile of the modelling table, no split and no fit | confirms war story 1 is live in this environment; `prepare.py` keeps the value-pattern detectors and the DATA gate will re-check the same columns |

## Retirements

- **The plan's `0.6528` as a prediction target.** The v1 study never measured it; it is
  the ancestor campaign's number, approached to 0.651707 (row 5) and missed by −0.027
  (row 2). Registering it would have scored this study against a value no ledger in
  this repository holds. Retired in favour of the v1 ledger's own 0.651707 (S2).
- **The v1 identity tolerance of ±0.001.** It was an IDENTITY tolerance, valid only
  because v1 re-measured on the same rows. Schema 3 mandates a sealed third partition,
  so no lawful split reproduces the v1 evaluation set, and at SE ≈ 0.0159 on the
  development half a ±0.001 rule would be a coin flip dressed as a prediction (S5).
  Retired in favour of the derived ±0.0225.
- **A split that would have made ±0.001 attainable** — e.g. `development_size 0.199 /
  test_size 0.001`, which leaves the development partition at 99.5 % of the v1
  validation set. Rejected outright: it buys the anchor's digits by making the seal
  58 rows, which is contract-gaming, not reproduction. Never run.
- **The schema-3 default 0.20 / 0.20 split.** Lower evaluation noise (SE 0.0112 rather
  than 0.0159) but it discards the one identity the port can actually keep: the v1
  model's training rows (S4). Retired, and the cost of the choice — a noisier
  development metric, hence a higher keep bar — is accepted on the record here.
- **Refitting the v1 rungs at design time to "check" them.** Deliberately not done.
  The first time any of these recipes touches this study's development partition is
  inside a `klein run-one` transaction, with the prediction already registered.

## Prior-scorecard eligibility

This is a port, so most of what it expects it already saw: the priors of RQ1, RQ2 and
RQ4 rest on S1–S3 and are labelled `(source: scouted)` in `study.yaml`, and are
excluded from the knowledge-vs-uninformed scorecard in findings §⑥. RQ3's prior rests
on nothing in this ledger — no floor of any kind has ever been measured on this
portfolio, by v1 or by the ancestor campaign — and is labelled `(source: uninformed)`.
That single uninformed prior is the whole of this study's scorecard, and findings §⑥
says so rather than implying a fuller one.
