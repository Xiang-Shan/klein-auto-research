---
type: research-plan
domain: "insurance"
status: draft
concepts: [denoising-autoencoder, swap-noise, self-supervised-tabular, representation-learning, when-dl-pays]
related: [../../knowledge/insights-and-framework.md, ../../knowledge/method_cards/gbdt-tabular.md]
---

# Research plan — 01-dae-claims

> CONSULT (Gate 0) output. Human-readable companion to `study.yaml`. Drafted from the
> ≤6 interview answers; confirmed with the user before the DATA gate.
> Protocol: `.claude/skills/klein/references/consult-protocol.md`.
> CONSULT fast-path taken (brief answered all six axes) — see `program.md` Log.

## The question

Does a swap-noise **denoising autoencoder (DAE)** — the representation-learning trick
Michael Jahrer used to win Porto Seguro (also auto-insurance claims) — pay on THIS 58k-row,
6.4%-positive, weak-signal insurance-claims dataset? And more usefully: **quantify WHEN
tabular self-supervised learning (SSL) pays**, so an actuary knows whether to reach for it.

**Stated as a decision.** After this study, an actuary facing a ~50k-row tabular claims
problem will know whether spending an afternoon on a DAE is worth it, or whether a tuned
GBDT is the honest stopping point — AND will have three concrete second-act uses of the
same DAE (linear-probe featurization, missing-value imputation, anomaly ranking) to weigh.
The study changes the "should I try SSL here?" decision from vibes to a measured verdict in
under three hours on the user's own data.

## Why now / why this method

- **The frontier is moving.** SSL/foundation models are redrawing the tabular map
  (VIME 2020, SCARF 2022, TabPFN 2025). Actuaries keep asking "does the Kaggle-winning DAE
  trick help MY data?" This study answers it on a representative claims table.
- **A resonant precedent.** Jahrer's 1st-place Porto Seguro solution was a swap-noise DAE
  on auto-insurance claims — but at ~1.5M rows (train+test, transductive). Our data is ~25×
  smaller and we hold the DAE to an inductive (train-fold-only) standard. Same method, very
  different regime — exactly the comparison worth making.
- **Honest prior (recorded in `study.yaml`):** the DAE reps will likely land ~0.66-0.67 and
  NOT beat the campaign's tuned raw single-GBDT (0.6701). SSL pays at scale / multimodal /
  high-cardinality — none of which this dataset has. So the expected headline is a
  measured "no lift" — which is itself the valuable result, plus the imputer/anomaly
  second acts that may pay independently.

## Data

- **Source:** `data_hub:insurance-claims` (kaggle `litvinenko630/insurance-claims`,
  Apache-2.0), the SAME dataset the 215-experiment campaign used — 58,592 rows, 6.40%
  positive `claim_status`, mixed numeric + low-cardinality categorical + 17 `is_*` Yes/No
  binaries + two numbers-in-strings columns (`max_torque`, `max_power`).
- Known issues (see `data_card.md`): the string-dtype Yes/No war story (value-pattern
  conversion), 7 near-deterministic-of-`model` vehicle-spec columns, class imbalance.
  All WARN-severity, all mitigated. DATA gate = **GO**.

## Method

- **Under study:** a swap-noise **denoising autoencoder** (encoder 3×256 ReLU, deep-stack
  768-d representation = concat of the 3 hidden layers), trained self-supervised to
  reconstruct RankGauss-scaled numerics + OHE categoricals from a swap-noise-corrupted copy
  (`is_*` binaries pass through, excluded from corruption). Full pedagogy: `method_card.md`.
- **Baselines it must beat (cited from the campaign, NOT rerun):**
  - raw-LR floor `val_auc 0.6255` (E1 reproduces it exactly — the split-identity gate),
  - tuned raw single-GBDT `0.6701` (the honest bar for RQ1/RQ2),
  - cross-family soft-vote `0.6715` (reference line only).
- **Fairness rule:** the headline DAE is INDUCTIVE (train-fold features only). A Jahrer-style
  transductive (train+val) variant is a labeled "Kaggle-style" aside, never the headline.

## Metric & decision use

- **Primary metric:** `val_auc` (higher is better) — one number, directly comparable to the
  campaign baselines on the identical fixed split.
- **Decision mapping.** AUC is the ranking quality an actuary needs to triage/segment risk;
  the campaign showed reweighting for imbalance wrecks calibration, so the downstream
  classifiers keep `class_weight=None` where calibration matters and calibration/lift go to
  `aux_metrics.tsv`. E7 (imputation) maps to "how well can we fill missing telematics/spec
  fields?"; E8 (anomaly) maps to "can recon-error flag odd policies for review?"

## Experiment ladder (sketch)

A rough ordered list — the loop ADAPTS, this is not a batch script. Full table + keep-rules
in `program.md`.

1. **E1** — split-identity anchor: LR+OHE(min_freq=20)+`class_weight=balanced` → GATE
   `val_auc = 0.6255 ± 0.001`, else STOP.
2. **E2** — supervised MLP raw floor (3×256, no SSL): what does representation power ALONE buy?
3. **E3** — frozen DAE(768-d) → LGBM (RQ1 headline): does SSL reach 0.6701?
4. **E4** — linear probe (LR on frozen DAE reps, RQ3): did SSL linearize the signal past 0.6255?
5. **E5** — swap-rate sweep {0.10, 0.15, 0.25} via the sweep escape-hatch (noise sensitivity).
6. **E6** — DAE+raw → LGBM (RQ2): additive value, keep IFF > 0.6701.
7. **E7** — DAE-imputer vs median under MCAR {10%, 30%} (RQ4a).
8. **E8** — recon-error anomaly lift@10% (RQ4b).

## Budgets & stop rule

- Per-phase budgets in `study.yaml:phases` (Phase 0 = 0.5h, Phase 1 = 1.5h, Phase 2 = 1.0h;
  ~3h total, deep/torch on MPS). Stop rule: keep going until the user stops or a phase max is
  hit. **User-ack pauses: after E1, after E5, at end.**

## Deliverables

- `findings.md` (7-section synthesis) and `report/index.html` (self-contained tutorial with
  the model-coding-advice section) — ALWAYS.
- The `dae.py` `SwapNoiseDAE` is itself a reusable artifact (sklearn-style
  fit_transform/transform + reconstruct, inductive/transductive modes).

## Risks & unknowns

- **Weak signal + small data** could make every DAE number statistically indistinguishable
  from the GBDT baseline — in which case the honest finding is "no measurable lift", which
  the study is designed to report cleanly (that is a result, not a failure).
- **MPS prediction collapse** (the war story): mitigated by index-shuffle batching, CPU eval,
  and the `min_proba_std` guard. A collapsed run crashes loud.
- **Transductive temptation:** the Kaggle-style DAE-on-train+val will look better; the
  fairness rule keeps it a labeled aside so it never masquerades as the headline.
- **Abandon-early trigger:** if E1 misses the 0.6255 gate, STOP — the split/preprocessing has
  drifted and every later comparison would be poisoned.
