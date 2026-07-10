---
type: findings
domain: insurance
status: complete
concepts: [swap-noise-dae, tabular-ssl, supervised-mlp-floor, when-dl-pays, dae-imputer, recon-error-anomaly, inductive-fairness, libomp-process-isolation, rankgauss, deep-stack-representation]
related: [program.md, method_card.md, data_card.md, results.tsv, aux_metrics.tsv, sweeps/swaprate.sidecar.tsv, ../../knowledge/method_cards/dae-tabular.md, ../../knowledge/insights-and-framework.md, ../../.claude/skills/klein/references/war-stories.md, report/index.html]
---

# Findings — 01-dae-claims

> SYNTHESIZE stage output. QUALITY BAR: every claim cites experiment IDs from
> `results.tsv` / `aux_metrics.tsv`; no claim without evidence. Contradictions with the
> method-card priors are called out explicitly. Protocol:
> `.claude/skills/klein/references/synthesis-protocol.md`.
>
> Trajectory mined: 8 experiments — 4 `keep` (E1, E2, E4, E7), 4 `discard`
> (E3, E5, E6, E8), 0 crash. The discards are not failures of execution: E3/E5/E6/E8 are
> pre-registered null results logged honestly against pre-registered keep bars. The
> discard CLUSTER is itself the headline evidence — every DAE-fed classifier arm
> (E3, E5, E6) lost to the plain supervised MLP (E2), and the unsupervised second act
> split 1–1 (E7 imputer yes, E8 anomaly no). Total ledger wall-clock ≈ 61 s (~0.02 h of
> the 3 h budget; the E5 sidecar's three sweep trials add ~106 s more).

## ① Research-question verdicts

| RQ | Verdict | Evidence (exp IDs) | Metric delta |
|---|---|---|---|
| **RQ1** — do frozen swap-noise DAE reps + LGBM beat the tuned raw-GBDT 0.6701? | **NO** (prior held) | E3 (0.668271, discard); bar sharpened by E2 (0.670616) | E3 −0.001829 vs 0.6701; −0.002345 vs E2 |
| **RQ2** — does DAE+raw concat → LGBM lift over 0.6701? | **NO — and it *regresses* below reps-only** (sharper than the prior) | E6 (0.660653, discard) vs E3 (0.668271) | −0.009447 vs the 0.6701 bar; **−0.007618 vs E3**; `lgbm_best_iteration` 107 → 55 |
| **RQ3** — does a linear probe on frozen DAE reps beat the raw-LR floor 0.6255 (did SSL linearize the signal)? | **YES** (prior held, upper half of band) | E4 (0.658019, keep) vs E1 (0.625462) | **+0.032557** — ~72% of the raw-LR → tuned-GBDT gap (0.6255 → 0.6701) |
| **RQ4a** — does the DAE-reconstruction imputer beat median/mode under MCAR? | **YES — decisively at the cell level, marginally on rank** | E7 (keep): downstream +0.001497 @10% (0.659068 vs 0.657571), +0.001286 @30% (0.632213 vs 0.630926) | cell level: numeric RMSE **1.02 vs 3.42** (3.4×, RankGauss space), cat accuracy **90.1% vs 33.4%** (@10%; 89.7% vs 33.5% @30%) |
| **RQ4b** — does recon-error rank claims (lift@10% > 1.0)? | **NO — prior falsified; signal slightly inverted** | E8 (0.480548, discard) | lift@10 **0.9341** < 1.0 (lift@5 0.9081, lift@20 0.9203); ranker val_auc 0.4805 |

**RQ1 detail.** E3 is the study's headline experiment: an inductive `SwapNoiseDAE`
(swap 0.15, fit on the 46,873 train-fold rows only — `dae_n_fit_rows=46873`, the
fairness canary), 768-d deep-stack reps into the campaign's LGBM recipe. It landed at
0.668271 — dead-center in the predicted 0.66–0.67 band — below both the tuned raw-GBDT
citation (0.6701, −0.0018) and, more tellingly, below E2's plain supervised MLP on the
*identical* 94-dim encoding (0.670616, −0.0023). The DAE detour also cost ~3× E2's
wall-clock (E3 37.2 s incl. 32.8 s DAE fit vs E2 12.5 s, aux `wall_seconds`). The
emerging Phase-1 ordering (program.md, E4 entry): raw-LR 0.6255 < probe 0.6580 <
DAE→LGBM 0.6683 < GBDT 0.6701 ≈ MLP 0.6706 — the reps carry real signal, but **nothing
DAE-based ever beat plain supervised learning on this data**.

**RQ2 detail.** The prior said "≤ +0.001, likely a discard"; the observation is
sharper — concat(94-d raw + 768-d reps = 862 dims, aux `concat_dims=862`) is **worse
than reps alone by −0.0076** (E6 0.660653 vs E3 0.668271). Mechanism, visible in aux:
`lgbm_best_iteration` fell 107 → 55 — with `colsample_bytree=0.7` over 862 largely
redundant dimensions, the raw dims dilute the split budget and the model overfits
earlier. Trees do not want a re-expression of information they already have.

**RQ4 detail.** The two second acts split. E7: the SAME frozen E3 DAE, used as an
imputer, beats train-fold median/mode at BOTH MCAR rates on downstream val_auc through
the deterministically-refit E3 LGBM head (`auc_clean_reps=0.668271` bit-exact) — but
the margins are ~0.0013–0.0015, while the cell-level dominance is not close (3.4× RMSE,
90% vs 33% categorical accuracy over 31,580 / 94,867 masked cells). The dominant effect
is information loss itself (clean 0.6683 → 0.6322 at 30% MCAR, −0.036) — no imputer
recovers it, so the LGBM head is largely indifferent to WHICH imputer filled the cells.
E8: the same DAE's per-row reconstruction error, rank-normalized as a 1-D claim ranker,
is slightly *inverted* (val_auc 0.4805; every lift@k < 1.0) — unusual rows are
marginally LESS claim-prone. See ③.

## ② Predictions to falsify (filled)

Levers copied from `program.md` / `study.yaml:predictions_to_falsify`; observed +
verdict from the trajectory. Tally: 4 held (E1, E3, E4, E6), 2 falsified (E5, E8), 1
split (E7 — sign held, growth clause falsified), and 1 falsified *upward* — E2, the
study's surprise.

| Lever | Predicted Δ | Observed Δ (exp IDs) | Verdict |
|---|---|---|---|
| **E1** anchor: LR+OHE(min_freq=20)+cw=balanced | val_auc = 0.6255 ± 0.001 (GATE) | 0.625462; \|Δ\|=0.000038 (matches study 00's E1 exactly — shared prepare.py) | **HELD** — GATE PASS |
| **E2** supervised MLP raw floor | val_auc ~0.63–0.65; > 0.6255, < GBDT 0.6701 | **0.670616** — +0.045154 over E1, **+0.0005 OVER the 0.6701 GBDT**, −0.0009 vs the 0.6715 soft-vote | **FALSIFIED (missed high) — the surprise.** The "floor" ties the tuned GBDT; see ③ |
| **E3** frozen DAE(768-d)→LGBM (RQ1) | val_auc ~0.66–0.67; Δ ≤ 0 vs 0.6701 | 0.668271; Δ=−0.001829 vs 0.6701 (band hit dead-center) | **HELD** |
| **E4** linear probe on DAE reps (RQ3) | val_auc ~0.63–0.66; Δ > 0 vs 0.6255 | 0.658019; Δ=+0.032557 (upper half of band) | **HELD** |
| **E5** swap-rate sweep {.10,.15,.25} | \|Δ\| ≤ 0.002 across rates; best ≈ 0.15 | 0.10 → 0.661953 (**−0.0063**), 0.25 → 0.664123 (**−0.0041**); best 0.15 = 0.668271, E3 bit-exact (`sweeps/swaprate.sidecar.tsv`) | **FALSIFIED on flatness** — swap-rate is a real lever; 0.15 is a genuine local optimum (best-≈-0.15 clause held) |
| **E6** DAE+raw→LGBM (RQ2) | Δ ≤ +0.001 vs 0.6701 (likely discard) | Δ=−0.009447 vs 0.6701; also −0.007618 vs E3 reps-only | **HELD, sharper than predicted** — not merely "no lift" but a regression |
| **E7** DAE-imputer vs median, MCAR {10,30}% (RQ4a) | downstream Δ ≥ 0, **growing** with missing rate | Δ=+0.001497 @10%, +0.001286 @30% — positive at both, **flat-to-shrinking** | **SPLIT** — sign HELD, gain-growth clause **FALSIFIED** |
| **E8** recon-error anomaly (RQ4b) | lift@10% > 1.0 | lift@10 = 0.9341 (lift@5 0.9081, lift@20 0.9203); ranker val_auc 0.480548 | **FALSIFIED** — mildly inverted |

The two clause-falsifications carry mechanism, not just a miss. E5: the DAE's held-out
recon `es_mse` rises with rate (0.0154 / 0.0230 / 0.0358, aux exp-5 rows) — 0.10's
easier pretext task applies the least denoising pressure and learns the weakest reps,
0.25 over-corrupts; the metric peaks between. E7: information loss dwarfs imputer
choice (−0.036 from clean at 30% MCAR vs a ±0.0013 imputer delta), so the gain has no
room to "grow with rate."

## ③ Surprises and why

**Surprise 1 — the E2 meta-finding (the study's headline): a *plain* supervised MLP
ties the tuned GBDT at 58k rows.** Predicted 0.63–0.65 as a mere "floor"; observed
**0.670616** (E2) — +0.0005 over the campaign's tuned single-GBDT citation (0.6701) and
within 0.0009 of its cross-family soft-vote global best (0.6715). And it is not a
rank-vs-calibration trade: E2 simultaneously posts the study's best brier (0.058749),
best logloss (0.227846), and best lift@10 (1.881445) — aux exp-2 rows. Sharpened
against the ancestor campaign's Phase-4 results (`knowledge/insights-and-framework.md`
§5.1): the campaign's best FT-Transformer was 0.6695 (15 configs) and best TabNet
0.6633 (25 configs) — **a plain 3×256 ReLU MLP with RankGauss+OHE inputs, cw=None, and
val-AUC early stopping (best epoch 15/26, 12.5 s on MPS) beats both fancy
architectures** and the entire DAE ladder of this study. Why (mechanism): (a) the
encoding is doing representation work the fancy models re-derive — RankGauss
normalization plus dense OHE is exactly the input regime where an MLP's smooth-manifold
bias works, per Grinsztajn 2022's analysis (NN failure modes there — rotation
invariance, sensitivity to uninformative features — are mitigated by a clean 94-dim
encoded input); (b) attention-based architectures (FTT, TabNet) carry HPO surface and
regularization burden that 58k weak-signal rows cannot pay for (the campaign needed a
zero-dropout FTT to reach 0.6695); (c) early stopping on the *task* metric at epoch 15
is aggressive capacity control a pretext-task DAE cannot replicate — the DAE early
stops on recon MSE, which is not the objective that matters. The honest framework
implication: **the campaign's Phase-4 "DL below GBDT" conclusion was drawn without ever
running a plain MLP** — this study fills that gap, and the gap mattered.

**Surprise 2 — torch + LightGBM cannot share a process on macOS arm64 (the ops war
story; program.md "Ops war stories").** E3's first run died at `LGBMClassifier.fit`
with SIGSEGV (exit 139), no Python traceback, and an *empty* run.log. Cause: both
wheels bundle their own `libomp`; whichever framework engages OpenMP heavily SECOND
segfaults the process, and import order only moves the victim (lightgbm-first survived
toy loads, then died inside the full-scale torch stage). The armed `min_proba_std`
guard never fired — the failure is *below Python*. The three-step isolation diagnostic
that pinned it: (A) torch-free process, LGBM on cached reps → OK (0.668271, 1.5 s);
(B) tiny torch-MPS op then LGBM fit, same process → exit 139; (C) lightgbm imported
first, tiny torch → OK, full-scale → exit 139 inside the torch stage. THE fix,
sanctioned by SKILL.md's "wrap a launcher inside one train.py" note: **two-stage
process isolation** — a torch-only child subprocess fits the DAE and dumps `.pkl`
caches (never imports lightgbm); the parent imports lightgbm FIRST and runs the GBDT
head (torch bound passively, never operated). Corollaries now house rules: `set -o
pipefail` on every tee'd run (tee otherwise masks the real exit code) and
`PYTHONUNBUFFERED=1` (block-buffered stdout dies with the process, eating the log). A
bit-exact rerun (E3 = E5 trial 2 = 0.668271) is the cheap proof isolation preserved
determinism. Promoted to `references/war-stories.md` #5 and the repo CLAUDE.md.

**Surprise 3 — E8's mild inversion: unusual ≠ risky on policy data.** The prior
(recon-error lift@10 > 1.0) assumed outlier-ness in the feature joint concentrates
claims. Observed: every lift@k *below* 1.0 (0.908/0.934/0.920 at 5/10/20%) and ranker
AUC 0.4805 — the rows the DAE reconstructs worst are marginally LESS claim-prone. Why:
reconstruction error tracks **feature-space rarity** — unusual vehicle-spec
combinations, exactly the model-derivative redundancy structure the data card's NOTE 2
flagged (recon_err p50 0.000841 vs p90 0.004844, aux exp-8) — while claims on this book
are driven by weak **exposure/usage** signal (subscription_length, customer_age,
region_density; campaign feature importances). "Weird configuration" is
orthogonal-to-slightly-negative for claim propensity here. Recon-error anomaly scoring
is a fraud/data-quality tool, not a risk ranker, on weak-signal personal-lines data.

## ④ Practical advice

On your own data, in priority order (imperatives, best-practices voice):

1. **Run the supervised-DL floor BEFORE any SSL detour.** One plain MLP on the same
   encoding you would feed the DAE (E2: 12.5 s) re-set this study's keep bar from
   0.6701 to 0.670616 and pre-empted three would-be "wins." If the plain supervised
   model already ties your tuned GBDT, a frozen-representation detour has nothing left
   to add (E3 −0.0023 vs E2). Never evaluate an SSL pipeline against only a linear
   baseline.
2. **Reach for a tabular DAE for *values*, not for headline AUC, at this scale.** At
   ~58k single-modal weak-signal rows the DAE lost the headline every way we asked
   (E3, E5, E6) — but as an imputer it recovers masked cells 3.4× better numerically
   and 90% vs 33% categorically (E7). Use it in data-quality/imputation workflows
   (reports, ratemaking features, audit) where the filled VALUE matters; skip it when
   only the classifier's rank matters (the rank delta was +0.0013–0.0015).
3. **Sweep the swap rate; never default it.** The pre-registered "it's flat" prior was
   falsified: 0.10 costs −0.0063 and 0.25 costs −0.0041 vs 0.15 (E5 sidecar). Jahrer's
   0.15 replicated as a genuine local optimum here — but you only know that on your
   data after a 3-point sweep (~106 s here). Watch the held-out recon MSE per rate
   (0.0154/0.0230/0.0358) to see the pretext-difficulty mechanism directly.
4. **Process-isolate torch from GBDT libraries on macOS arm64.** Two-stage pattern
   inside one train.py: torch-only child fits and caches; lightgbm-first parent heads.
   Always `set -o pipefail` and `PYTHONUNBUFFERED=1` on tee'd runs, or the segfault
   eats both the exit code and the log (③, surprise 2). Prove isolation preserved
   determinism with one bit-exact rerun (E3 = E5-trial-2).
5. **Keep the inductive fairness discipline.** Fit the DAE on TRAIN-fold features only
   and log the row-count canary (`dae_n_fit_rows=46873`, E3/E4). Jahrer's transductive
   train+test fit is how Porto Seguro was won, but it quietly uses the val
   distribution — report it only as a clearly-labeled aside, never as the headline.
6. **Don't feed trees a concatenation of raw + learned reps.** It is not merely
   neutral — redundant dims dilute the split budget under column subsampling and
   trigger earlier overfit (E6: −0.0076 vs reps-only, best_iter 107 → 55). Pick one
   representation per tree model.
7. **Calibration doctrine transfers to NNs unchanged.** cw=None + natural base rate
   gave every Phase-1/2 classifier arm a brier of 0.0587–0.0591 (E2/E3/E4/E6/E7 aux);
   the lone cw=balanced run (E1, anchor-only) sits at 0.240153 — 4.1× worse. Train on
   the truth; calibrate after.

## ⑤ Business / actuarial value implications

- **No pricing-metric lift from the DAE — say so plainly.** Nothing DAE-based improved
  rank (E3/E5/E6 all below E2/0.6701), and the best DAE arm's lift@10 (E3 1.868) sits
  below E2's 1.881 (aux). No rate filing, triage queue, or capital number moves on this
  study's representation-learning results. The honest verdict IS the deliverable: an
  actuary asking "should we invest in tabular SSL for claims data like ours?" now has a
  quantified NO with mechanism, not a vibe.
- **The imputer is the bankable asset.** E7's 3.4× numeric-RMSE and 90.1%-vs-33.4%
  categorical-accuracy advantage (31,580 masked cells @10%; 94,867 @30%) is value
  recovery for **data-quality workflows** — completing MI/statutory report extracts,
  filling ratemaking feature gaps, pre-audit reconstruction — anywhere the *cell value*
  is the product. Do not sell it as a model-accuracy tool: downstream rank moved only
  +0.0013–0.0015, and information loss (−0.036 AUC at 30% MCAR) dwarfs imputer choice.
- **The meta-finding repositions the DL-for-tabular budget conversation.** The
  question "should we buy/build deep learning for claims?" usually prices in exotic
  architectures (TabNet, FTT) or SSL pipelines. E2 says: at this scale the entire DL
  value on offer is captured by a plain MLP that trains in 12.5 s on a laptop — and it
  only *ties* the GBDT (+0.0005), it does not beat it. Budget accordingly: encoding +
  early stopping + calibration discipline is where the money is; architecture novelty
  paid nothing here (campaign FTT 0.6695 < plain MLP 0.6706).
- **The framework's own cost story.** The full 8-experiment ladder — including a
  frontier-method literature gate, a falsified-priors table, and two independent
  second-act verdicts — consumed ≈ 61 s of ledger wall-clock (~0.02 h of the 3 h
  budget; +~106 s of sweep trials) at ~$0 marginal compute on a laptop. The alternative
  a real team faces is weeks of ad-hoc exploration with no pre-registered bars and no
  audit trail. The disciplined NO is cheap; the undisciplined maybe is expensive.

## ⑥ Literature tie-back

- **Jahrer / Porto Seguro (method_card §4): the regime caveat behaved exactly as
  predicted.** Jahrer's DAE won at ~1.5M rows (train+test, transductive, ~1500-unit
  layers); our honest inductive fit on 46,873 rows produced reps that a plain
  supervised model beats (E3 0.6683 < E2 0.6706). This is precisely the
  representation-learning-needs-scale story, and it is the Grinsztajn 2022 prediction —
  trees (and here, simple supervised nets) still win on medium tabular — landing on
  schedule. **One part of the Porto Seguro recipe DID replicate: swap rate 0.15.** E5
  shows it is a genuine local optimum on data 25× smaller (0.15 beats 0.10 by +0.0063
  and 0.25 by +0.0041) — the corruption-strength sweet spot appears to transfer across
  regimes even when the headline payoff does not.
- **VIME / SCARF framing.** Our DAE is VIME's reconstruction pretext half (no
  mask-prediction head, no consistency regularizer) and shares SCARF's corruption
  mechanism (random-feature resampling) without its contrastive objective. Both papers
  report gains concentrated where SSL has room — label scarcity, larger unlabeled
  pools. This study has neither (all 46,873 train rows are labeled), so finding the
  reconstruction-only pretext insufficient here is consistent with, not contrary to,
  that literature. Untested here: whether VIME's mask-estimation task or SCARF's
  InfoNCE would close the −0.0023 gap to E2 — at this scale we doubt it, but it is a
  falsifiable follow-up.
- **The knowledge base's when-DL-pays table gains an empirical row.**
  `knowledge/insights-and-framework.md` §5.2 lists five regimes where DL pays (>500k
  rows, multi-modal, multi-task/pretraining, >1000-level cardinality, foundation
  models). This study sits in none of them and got the predicted null — but adds a row
  the table did not have: *"58k single-modal weak-signal, SSL-DAE reps: 0.6683 <
  plain-MLP 0.6706 ≈ tuned GBDT 0.6701; imputer second-act pays 3.4× at cell level;
  recon-anomaly does not (lift@10 0.93)"* (E2/E3/E7/E8). Carried into
  `knowledge/method_cards/dae-tabular.md` §4.
- **E2 nuances the campaign's Phase-4 conclusion — a gap, stated plainly.** The
  campaign concluded "deep tabular sits below the GBDT trio" from TabNet (0.6633, 25
  configs) and FT-Transformer (0.6695, 15 configs). **A plain MLP was never tried
  there.** E2 (0.670616) shows the conclusion's boundary was drawn one model short: the
  cheapest DL architecture, on the right encoding with task-metric early stopping, ties
  the tuned GBDT that 40 fancy-architecture configs could not reach. The campaign's
  ranking within DL ("simpler-is-better at this scale": FTT-zero-dropout > tuned
  TabNet) extrapolated one more step exactly as the trend suggested.

## ⑦ What to try next

In priority order:

1. **TabPFN v2 zero-shot on this data.** The knowledge base flags it as the default
   first move under 50k rows (`insights-and-framework.md` §5.3; Hollmann et al. 2025,
   Nature), and at 58,592 rows this dataset sits at the edge of TabPFN v2.5's envelope.
   One inference pass answers whether a tabular foundation model beats E2/GBDT
   (0.6706/0.6701) with zero tuning — the highest information-per-second experiment
   available.
2. **MLP + GBDT cross-family soft vote.** E2's MLP is a genuinely different inductive
   bias at GBDT strength (0.6706 vs 0.6701) — exactly the diversity profile the
   campaign's soft-vote doctrine wants (add a learner only if OOF-pred correlation
   < 0.95; the FTT failed that test, `gbdt-tabular.md` §4). Target: beat the 0.6715
   campaign global best. Check the correlation gate first.
3. **Complete the transductive aside.** `dae.py` ships `fit_mode="transductive"`
   (train+val features, Jahrer-style) but the ladder never ran it — the fairness rule
   kept it out of the headline, and the study closed at 8/8 experiments. One
   clearly-labeled run would quantify exactly what the "Kaggle-style" peek is worth at
   58k rows (prediction: +0.001–0.003 over E3, still ≤ E2).
4. **Entity embeddings for `region_code`.** The one high-ish-cardinality column (22
   levels) got OHE everywhere here. A small `nn.Embedding` inside the E2 MLP tests the
   knowledge base's embeddings-beat-encoding claim at far lower cardinality than its
   >1000-level rule — cheap, and it upgrades the E2 architecture rather than the DAE.
5. **Productionize the imputer under MAR, not just MCAR.** E7's 3.4× win was measured
   under MCAR masking (`default_rng(4210/4230)`, eligible columns only). Real
   missingness is MAR-at-best (e.g. spec fields missing conditional on model/segment).
   Re-run the E7 harness with MAR injection keyed on `model` before recommending the
   DAE-imputer for a production data-quality workflow.
