---
type: findings
domain: "medical image classification (hematology microscopy)"
profile: "cv"
kind: "predict"
status: complete
concepts: [macro-f1, seed-array, item-bootstrap, fit-noise, batch-normalization, bn-running-statistics, d4-augmentation, near-duplicate-audit, image-level-split, headroom]
related: [21-bloodmnist-cnn, knowledge/method_cards/cnn-image-classification.md]
---

# Findings — 21-bloodmnist-cnn

> SYNTHESIZE stage output. Every claim cites evidence ids from the immutable run
> manifests (`runs/E####/manifest.json`), the two registered sweeps, the replication
> record and the pinned tables. Protocol: `.claude/skills/klein/references/synthesis-protocol.md`;
> the lock and the numbers law: `references/claims-protocol.md`. Derived numbers that
> are not in a run manifest live in `tables/synthesis_summary.tsv`, `tables/controls.tsv`,
> `tables/per_class.tsv` and `tables/seed_dominance.tsv`, written by the read-only script
> `tables/synthesis.py` from the committed evidence (it trains nothing and reads no image).
>
> The one-paragraph result. Eight development seed arrays (three seeds each, seeds 0/1/2)
> took an 8-class blood-cell classifier on 28 x 28 images from a pixel-linear softmax
> (macro-F1 0.6903) to a three-block CNN with working batch normalization, flip/rotation
> augmentation and 4000 steps (0.9461), judged against an item-bootstrap keep bar of
> 0.0438. Only two changes earned a keep: batch normalization, once a running-statistics
> bug was fixed, and a four-lever bundle whose gain the study cannot attribute to any one
> lever. The one sealed run of that configuration on the official test split scored
> macro-F1 0.9465 and accuracy 0.9527, no drop from development, and 0.0053 below the
> MedMNIST v2 ResNet-18 (28) accuracy of 0.958 — about 1.5 binomial standard errors, so
> indistinguishable at this test size. Every score is image-level: the official split is
> not grouped by patient or smear.

## ① Research-question verdicts

| Claim | RQ | Track | Verdict | Strength | Class | Evidence | Claim sentence (delta + uncertainty) |
|---|---|---|---|---|---|---|---|
| **[C1]** | RQ1 | primary | supported (prior range held) | exploratory | empirical-description | E0002, `art:controls` | A linear softmax on raw pixels reached a seed-mean development macro-F1 of 0.6903 (accuracy 0.7353), far above the chance controls (prior-matched random 0.125, majority class 0.0408) and inside the prior range of 0.50 to 0.85, so a pixel-linear model solves a large part of BloodMNIST but not most of it. |
| **[C2]** | RQ2 | primary | refuted | exploratory | empirical-description | E0001, E0002, `sweep:item_bootstrap`, `art:summary` | The recipe two-block CNN scored 0.7189 and cleared the pixel-linear baseline by only +0.0286 macro-F1 (0.65 floors), inside the measured keep bar of 0.0438 and far below the prior of 0.85. |
| **[C3]** | RQ3 | primary | supported for normalization; inconclusive for depth, schedule and augmentation | exploratory | empirical-description | E0004, E0005, E0006, E0007, `art:summary`, `art:seed_dominance` | Working batch normalization was the only single change to earn a keep (E0004, +0.1771 macro-F1, 4.04 floors over E0001); a third block (+0.0326) and 4000 steps (+0.0280) were positive on every seed but short of the bar by 0.0112 and 0.0158, and flip/rotation augmentation alone (-0.0067) is unresolved at this budget. |
| **[C4]** | RQ3 | primary | supported for the bundle; not attributable | exploratory | empirical-description | E0004, E0006, E0007, E0008, `art:summary` | The four-lever bundle E0008 (third block, working batch normalization, flip/rotation augmentation, 4000 steps) kept at 0.9461, +0.0501 over E0004 and 0.0062 above the bar, but its margins over the depth-only and schedule-only runs (+0.0175 and +0.0221) are inside the bar, so the gain cannot be attributed to any single lever. |
| **[C5]** | RQ4 | primary | supported (holds; indistinguishable from the reference) | confirmed | empirical-description | E0009, E0008, `rep:E0008@20261103T090709Z`, `art:summary` | On the sealed official test split (3413 items after near-duplicate removal) the E0008 configuration scored macro-F1 0.9465 and accuracy 0.9527 over three seeds, +0.0004 macro-F1 against development; the accuracy is 0.0053 below the MedMNIST v2 reference of 0.958, about 1.5 binomial standard errors of 0.0034, so the two are indistinguishable at this test size. |
| **[C6]** | — | primary | held | confirmed | procedural-verdict | E0001, E0004, E0008, E0009, `rep:E0008@20261103T090709Z`, `art:summary` | The frontier closed with two keeps (E0004, E0008) out of seven candidate-versus-incumbent comparisons, the one sealed access went to the E0008 configuration, the incumbent replicated with difference 0, and headroom h = 1.23 means a further keep would need 0.9899. |
| **[C7]** | RQ3 | primary | interpretation | exploratory | mechanism-interpretation | E0003, E0004, `art:summary` | E0003's collapse to 0.3005 was an inference bug, not a verdict on batch normalization: the same layers with running statistics recomputed on the training set before evaluation (E0004) scored +0.5955 higher. |
| **[C8]** | RQ2 | primary | measured | exploratory | empirical-description | E0001, `sweep:fit_noise`, `sweep:item_bootstrap`, `art:summary` | At the anchor the seed-block spread of the three-seed mean (fit noise, sd 0.0472) is 3.94 times the item-bootstrap sd of 0.0120 that sets the bar, and the E0001 block is the highest of four (four-block mean 0.6620), so the anchor's 0.7189 is a favourable draw. |
| **[C9]** | RQ3, RQ4 | primary | measured | exploratory | empirical-description | E0001, E0004, E0008, E0009, `art:per_class` | Per-class effects are uneven: from E0001 to E0008 basophil recall rose from 0.2562 to 0.9201 and immature-granulocyte recall from 0.7046 to 0.9149, but monocyte recall fell from 0.8345 at E0004 to 0.7949 at E0008 and monocytes remain the weakest class on the sealed test at 0.8582. |
| **[C10]** | RQ3, RQ4 | primary | measured | exploratory | empirical-description | E0001, E0008, E0009, `art:summary` | Ranking and calibration did not trade off: expected calibration error fell from 0.0828 at the anchor to 0.0125 at E0008 (0.0086 on the sealed test) and log-loss from 0.6660 to 0.1333. |
| **[C11]** | RQ2 | primary | interpretation | exploratory | mechanism-interpretation | E0001, E0004, `sweep:fit_noise`, `art:summary` | The anchor's narrow margin over the linear model reflects unstable, under-trained optimisation rather than missing capacity: the same two-block network with working batch normalization at the same 1500 steps reached 0.8960, and its seed sd fell from 0.0255 to 0.0145. |

**Strength note.** `confirmation.require` is `[sealed, replicate]`, and both records exist:
the sealed run E0009 and the replication `rep:E0008@20261103T090709Z` (difference 0 at
tolerance 0.0438435). That confirms the level in C5 and the procedure in C6. Every
comparison between development candidates (C1–C4, C7–C11) is a development-partition
measurement and stays exploratory: one track has one sealed number, and a difference
between two configurations would need two.

**Keep chain (track `primary`, development only).** E0001 0.7189 (anchor) → E0004 0.8960
(+0.1771, 4.04 floors) → E0008 0.9461 (+0.0501, 1.14 floors). Discards: E0002 linear
(-0.0286 vs E0001), E0003 BN with the default inference path (-0.4184), E0005 flip/rotation
augmentation (-0.0067 vs E0004, -0.15 floors), E0006 third block (+0.0326, 0.74 floors),
E0007 4000 steps (+0.0280, 0.64 floors). E0009 is the sealed confirmation, recorded as a
discard row by design and excluded from the frontier. No run crashed; the only failed
idea, E0003, ran to completion and measured a broken inference path (see ③).

**Controls that exist, and the one that does not** (`art:controls`).
- *Chance level, analytic.* On development (1709 items) the majority class (neutrophils)
  gives accuracy 0.1949 and macro-F1 0.0408; a uniform random guess gives accuracy 0.125
  and expected macro-F1 0.1202; a guess matched to the class priors gives expected
  macro-F1 0.125. The sealed-test values agree to three decimals (majority accuracy
  0.1948, macro-F1 0.0408). Reason: macro-F1 has no single chance value, so the three
  standard null classifiers bound it from below.
- *Pixel-logistic baseline, measured.* E0002 — Flatten + one linear layer, the anchor's
  loop, optimizer, steps and seeds — at macro-F1 0.6903, accuracy 0.7353. Reason: it
  separates what a convolution adds from what raw colour and size already give.
- *Label-shuffled / constant-prediction harness control — NOT run.* The data card's
  leakage row 4 asked for it to be reproduced from `train.py` at EXPERIMENT; `program.md`
  records no such run. The harness is checked only by the analytic chance level above,
  the notary's near-constant-prediction rejection, and the replication. This is a gap,
  named again in ⑦.

**Scope that travels with every claim.** (1) The official MedMNIST split is a random
image-level 7:1:2 split, not grouped by patient, smear or staining run, and the source
removed patient identifiers, so no audit can group it (data card WARN 2): all scores
answer "new cells from the same smears and lab", never "a new patient". (2) `prepare.py`
removed 11 cross-split near-duplicates (dHash within 4 bits) before any model ran — 3
from development, 8 from test — so development is 1709 and test 3413 images, against
MedMNIST's published 1712 and 3421. (3) The sealed run refits the configuration on
train + development (13668 rows against E0008's 11959), so E0009 scores E0008's recipe,
not E0008's weights.

## ② Registered predictions (from the ledger)

Copied from `klein predict list` (4 supported, 1 refuted, 0 inconclusive, 0 open);
nothing here is re-decided.

| P# | Statement | Rule | Observed | Verdict (ledger) | Evidence | Decision |
|---|---|---|---|---|---|---|
| P1 | Linear softmax on raw pixels, seed-mean dev macro-F1 between 0.50 and 0.85 | `{primary_metric, between, [0.50, 0.85]}` | 0.69032 | supported | E0002 | — |
| P2 | Recipe SmallCNN (two blocks, width 32, 1500 steps), seed-mean dev macro-F1 at least 0.85 | `{primary_metric, >=, 0.85}` | 0.718932 | **refuted** | E0001 | program.md 2026-11-03 "Decision: P2 refuted (anchor 0.7189 < 0.85 …) No change to the contract; P2 stays refuted and the adaptive phase tests which lever moves it." |
| P3 | Three blocks + BN + flip/rot90 + 4000 steps, seed-mean dev macro-F1 at least 0.93 | `{primary_metric, >=, 0.93}` | 0.946093 | supported | E0008 | program.md 2026-11-03 "Decision: P3 supported … the verdict is about the bundle, not any lever." |
| P4 | Final incumbent, sealed-test seed-mean macro-F1 at least 0.90 | `{primary_metric, >=, 0.90}` | 0.946520 | supported | E0009 | program.md 2026-11-03 "Decision: P4 supported" |
| P5 | Final incumbent, sealed-test seed-mean accuracy below 0.958 (MedMNIST v2 ResNet-18 (28)) | `{val_accuracy, <, 0.958}` | 0.952729 | supported | E0009 | program.md 2026-11-03 "P5 supported … 'indistinguishable from ResNet-18 (28)' is the honest wording" |

**Score: 4 held, 1 falsified (P2).** P5's arithmetic verdict is "below", but the gap of
0.0053 is 1.54 binomial standard errors of 0.0034 at the reference accuracy and the
3413-image test size (1.45 at this study's own accuracy; 1.05 if the reference's own
sampling error is added, `art:summary`). One of the three sealed seeds (0.9587) is above
0.958. The honest reading is "indistinguishable from ResNet-18 (28) at this test size",
and C5 says so. `program.md`'s log rounded the same ratio to "about 1.6"; the recomputed <!-- klein:numbers-ok: quotes program.md's own rounding of gap_in_binomial_se_at_0958 (1.535063, art:summary) in order to correct it -->
value is 1.54.

**`n_comparisons` — stated with its reason.**
- **7 frontier comparisons** (E0002–E0008, each candidate against its incumbent at the
  fixed bar of 0.0438). No family-wise correction is applied. Reason: the bar is a measured
  per-comparison item-noise floor at 3.66 item sds, and the selection effect of picking
  the best of 8 development configurations on 1709 images is not corrected for. The single
  sealed access (+0.0004 against development) bounds the net effect of selection and the
  train + development refit together; it does not measure selection on its own (§③ item 7).
- **5 registered predictions** (P1–P5), each one pre-registered threshold adjudicated by
  the notary on one printed block; P1–P3 on development, P4 and P5 on the one sealed run.
  No prediction was reassigned, re-scoped or re-run.
- **5 method-card priors** (K1–K5, below), scored descriptively; they were never
  registered, so they carry no rule and are not tests.
- **7 seed-level dominance comparisons** in `art:seed_dominance`, chosen after the runs
  for description only. "All three candidate seeds beat all three reference seeds" has
  probability 0.05 per pair under exchangeable seeds; across 7 post-hoc pairs that is not a
  significance statement and is not offered as one.

**Card priors K1–K5 (method_card.md §4, not registered; scored from `program.md`).** Four of
five were falsified — the method card's priors about noise and class difficulty were
mostly wrong, and that is the most transferable result of the anchor phase.

| Prior | Stated | Observed | Outcome |
|---|---|---|---|
| K1 floor size | bar in [0.015, 0.040] | 0.0438 (range/2 binds) | **falsified** (`sweep:item_bootstrap`) |
| K2 fit vs item noise | fit/item sd ratio < 1.0 | 3.94 | **falsified** (`sweep:fit_noise`) |
| K3 metric gap | accuracy minus macro-F1 in [0, 0.03] | 0.0605 (0.7794 − 0.7189) | **falsified** (E0001) |
| K4 hardest class | immature granulocytes lowest or second-lowest recall | 0.7046, with basophil 0.2562, lymphocyte 0.5027 and monocyte 0.5734 below it | **falsified** (E0001, `art:per_class`) |
| K5 headroom | h ≥ 1 throughout the adaptive phase | lowest h 1.23 (at E0008) | held (`art:summary`) |

## ③ Surprises and why

1. **The recipe CNN barely beat a linear softmax (P2 refuted).** The prior expected 0.85;
   the anchor scored 0.7189, only +0.0286 (0.65 floors) above E0002. Mechanism (C11,
   exploratory): the anchor was optimisation-limited, not capacity-limited. Its per-seed
   macro-F1 ranged from 0.6895 to 0.7342 in E0001, another seed block averaged only 0.5886
   (`sweep:fit_noise`), its loss was still noisy at step 1500, and adding working batch
   normalization at the same depth and step count lifted it to 0.8960 with a seed sd of
   0.0145 against 0.0255. The two models also fail on different classes: the linear model
   recalls basophils at 0.771 and immature granulocytes at 0.2851, the anchor the reverse
   (0.2562 and 0.7046) (`art:per_class`). Reading the pattern as "colour stencils versus
   local texture" is an untested interpretation: no run probed what either model uses.
2. **Batch normalization first measured as a catastrophe (E0003, 0.3005).** Mechanism
   (C7, exploratory): eval-mode inference used momentum-0.1 running averages that lag
   weights still moving at a constant learning rate; `program.md` records an off-loop
   diagnostic (seed 0, not evidence) in which batch-statistics accuracy stayed high while
   eval-mode accuracy collapsed at the end of training. E0004 recomputed the statistics as a cumulative average over one pass
   of the training set (no development data) and scored 0.8960, +0.5955 over E0003. E0003 is
   a bug that E0004 repaired, not a ruled-out lever; the "working BN" lever is two edits
   (layers + statistics pass), and the study treats them as one because the first is not
   measurable without the second.
3. **Seed luck is bigger than item noise (K2 falsified, C8).** The method card expected
   item noise to dominate; at the anchor the block-to-block sd of a three-seed mean
   (0.0472) is 3.94 times the item-bootstrap sd (0.0120). The keep bar (0.0438) therefore
   sits at only 0.93 fit-noise sds, and the E0001 block (0.7189) is the best of four
   (four-block mean 0.6620, sd 0.0541). Mechanism: an untested hypothesis (C11,
   exploratory) — unstable optimisation at about 8 epochs. The learning-rate schedule was
   never varied, so "constant-rate" names a recipe property, not a measured cause. What is
   measured: once BN was added, per-candidate seed sds fell to 0.0070–0.0145 (E0004–E0008),
   so the anchor's fit noise does not describe the incumbent's.
4. **Depth and schedule were real in sign but sub-bar (E0006, E0007).** Every E0006 seed
   beat every E0004 seed (9 of 9 pairs, paired differences 0.0258 to 0.0393), likewise every
   E0007 seed (paired 0.0048 to 0.0403), yet both fell short of the bar by 0.0112 and
   0.0158. The bar was not relaxed after the fact. They are recorded as "positive, below
   the bar", not as null. The bar is set by item noise measured at an anchor near 0.72,
   where macro-F1 is noisier per item than near 0.93; it is probably wider than the item
   noise at the incumbent's level (unmeasured — ⑦ item 2).
5. **Flip/rotation augmentation alone did nothing measurable (E0005, -0.0067).** The prior
   (and Veeling et al. 2018) favoured rotation symmetry for microscopy. Mechanism:
   **unresolved**. `program.md`'s reading — at 1500 steps each orbit member is seen about
   once, so augmentation mainly slows fitting of a two-block network — is a hypothesis
   nobody tested. The margin (-0.15 floors) is inside the incumbent's seed sd 0.0145. The
   lever rides inside E0008, where its contribution is not separated.
6. **Monocyte recall fell at the bundle, within per-class noise (C9).** Basophil recall rose from 0.2562 to
   0.9201 and immature-granulocyte recall from 0.7046 to 0.9149 (E0001 → E0008), but
   monocyte recall fell from 0.8345 at E0004 to 0.7949 at E0008; in E0008's seed-0 table 33
   of 143 development monocytes were called immature granulocytes. On the sealed test
   monocytes remain the weakest class (recall 0.8582). On 143 development monocytes this
   drop (0.0396) is 1.2 to 1.3 binomial standard errors of recall (`art:per_class_noise`), so it is within per-class
   noise and not an established effect. Mechanism: **unresolved**.
7. **No development-to-test drop after selection (+0.0004).** Picking the best of 8
   configurations on 1709 images should leave selection optimism of order one development
   standard error. Two forces push in opposite directions in E0009 — selection optimism
   (down) and the refit on 13668 rather than 11959 rows (up) — and one sealed number cannot
   separate them. Recorded as unresolved, not as "no optimism".

## ④ Practical advice

1. **[C12]** Before calling a batch-normalization candidate a failure, compare its training-mode and evaluation-mode outputs and recompute the running statistics on the training set; at a constant learning rate and a short budget the default running averages broke inference here. (evidence: E0003, E0004)
2. **[C13]** Measure fit noise across seed blocks as well as item noise before the adaptive phase, and when fit noise exceeds the item-noise bar read every keep together with its seed spread rather than the bar alone. (evidence: `sweep:fit_noise`, `sweep:item_bootstrap`, E0001)
3. **[C14]** Budget the ablations before a registered multi-lever bundle: decompose it inside the phase cap or its gain stays unattributed, as the E0008 bundle's did. (evidence: E0005, E0006, E0007, E0008)
4. **[C15]** On a MedMNIST official split, run the near-duplicate audit before training, drop cross-split copies from the evaluation partitions (11 items here), and state that the split is image-level rather than patient-grouped. (evidence: `art:data_card`, E0009)
5. **[C16]** Report a sealed comparison against a published number in binomial standard errors at the test size, and call a gap under two of them indistinguishable whatever the arithmetic verdict of the rule. (evidence: E0009, `art:summary`)
6. **[C17]** Run the label-shuffled harness control the data card asks for during the anchor phase; without it the harness check rests on analytic chance levels alone, as it does in this study. (evidence: `art:data_card`, `art:controls`)

Read with these: report accuracy beside macro-F1 but decide on macro-F1 under imbalance —
the anchor's accuracy exceeded its macro-F1 by 0.0605 (K3), so accuracy alone flatters a
model that fails small classes. And use the per-seed table (`runs/E####/seeds.tsv`), not a
single aux row: E0001's and E0002's `aux_metrics.tsv` rows hold the last seed's values
(seed 2), filed before the notary began writing seed means (`program.md`, framework fix
fcadacf).

## ⑤ What this means for the imaging pipeline

- **The change.** From the recipe two-block CNN (width 32, 1500 AdamW steps, constant
  learning rate, batch 64) to three conv-BN-ReLU blocks (32/64/128) with global average
  pooling, batch-normalization statistics recomputed on the training set before
  evaluation, a random dihedral flip/rot90 per training image from its own RNG, and 4000
  steps. No pretrained weights; native 28 x 28 resolution; no learning-rate decay.
- **Split unit and near-duplicate rate.** Official MedMNIST v2 partitions, image-level, not
  patient-grouped; cross-split near-duplicates 3 of 1712 development (0.18%) and 8 of 3421
  test, all removed by `prepare.py` before the gate (data card). Nothing here estimates
  performance on a new patient, smear, analyser or hospital.
- **Seed spread cleared.** E0004 over E0001 cleared the bar by 4.04 floors and every seed
  pair (9 of 9). E0008 over E0004 cleared it by 1.14 floors (0.0062 above the bar), every
  seed pair, with candidate seed sd 0.0086. The sealed seeds spread with sd 0.0072
  (macro-F1) and 0.0055 (accuracy).
- **Per-class effect.** Uneven (C9): the gains are concentrated in basophils and
  immature granulocytes; monocytes regressed on development and are the weakest sealed
  class (0.8582). A deployment that cares about monocytes should look at that class first.
- **Compute.** CPU only (x86_64, 4 cores, no CUDA, torch 2.13.0). The budget is steps:
  4000 per seed, 12000 per sealed seed array (`runs/E0009/usage.json`). Wall clock was
  dominated by contention from sibling studies — E0008's seeds took 162.5 s and 2885.6 s
  for the same configuration (a factor of 17.8) — so wall time ranks nothing here; the
  sealed seeds averaged 171.5 s each. The gain cost the step budget of 4000 against the
  anchor's 1500 steps per seed.
- **Calibration came along** (C10): ECE 0.0125 at E0008 and 0.0086 on the sealed test, so
  no recalibration step was needed to report probabilities at this level.
- No `materiality:` block is registered, so nothing here is priced and no deployment
  threshold is claimed.

## ⑥ Literature tie-back

- **MedMNIST v2 (Yang et al. 2023, Table 3; `ref:yang2023medmnist`).** The sealed accuracy
  0.9527 sits 0.0053 below ResNet-18 (28) at 0.958 and below ResNet-18 (224) 0.963,
  AutoKeras 0.961 and Google AutoML Vision 0.966 — within about 1.5 binomial standard
  errors of the 28-pixel ResNet with a network of three conv blocks trained for 4000 CPU
  steps without learning-rate decay. The comparison is on 3413 rather than 3421 test
  images, a three-seed mean against MedMNIST's "mean value of at least 3 trials", and a
  refit on train + development against training on train with validation early stopping;
  it is like-for-like on the image-level split. auto-sklearn's 0.878 test accuracy on
  flattened pixels stays a loose ceiling for non-convolutional pixel models: the linear
  softmax reached 0.7353 development accuracy, below it, as the card expected.
- **Acevedo et al. 2019 (`ref:acevedo2019`)** report 96.2% accuracy from ImageNet-pretrained
  networks at full resolution on their own split; this study's 28-pixel scratch network
  is in the same neighbourhood on a different split and metric, which says nothing about
  either beyond that.
- **Batch normalization (`ref:ioffe2015`, `ref:santurkar2018`).** The size of the BN gain
  (+0.1771) agrees with BN as an optimisation stabiliser. Ioffe & Szegedy define inference
  with population statistics over the training data; E0004's recomputation is exactly
  that, and E0003 shows what the momentum shortcut cost here. That the cause is lagging
  averages over weights still moving rests only on the off-loop seed-0 diagnostic in
  `program.md`, which is not evidence.
- **Seed variance (`ref:bouthillier2021`, `ref:picard2021`).** Fit noise at 3.94 times item
  noise at the anchor is a concrete instance of their warning: a benchmark difference read
  from one seed, or from one seed block, would have been read from luck.
- **Rotation symmetry in microscopy (`ref:cohen2016`, `ref:veeling2018`).** Not
  contradicted: augmentation alone was unresolved at 1500 steps and two blocks, and its
  share of the bundle's gain is unmeasured.
- **Doctrine anchor (`references/profiles/cv.md` §3).** Kept: official split with its
  grouping stated, near-duplicate audit before training, macro-F1 primary with accuracy
  reported, confusion tables pinned per seed, seed arrays with a measured floor,
  augmentation inside the loop.
- **Prior scorecard.** Knowledge-sourced priors (RQ1, RQ4) both held: P1 inside its range,
  P4 and P5 supported. Uninformed priors did worse: RQ2's (P2) was refuted, and RQ3's held
  only in part — "a longer schedule alone helps less than the floor" held (E0007, 0.64
  floors), while "augmentation and depth together reach 0.93" was tested only inside a
  bundle that also carried 4000 steps. The method card's own probabilities: P1 (0.8),
  P3 (0.5), P4 (0.75), P5 (0.8) held; P2 (0.6) failed; four of its five K-priors were
  falsified. The seed card `knowledge/method_cards/cnn-image-classification.md` should
  learn at promotion that fit noise can exceed item noise at a short constant-rate budget
  (supports 21-bloodmnist-cnn#C8).

## ⑦ What to try next

1. **Decompose E0008** — three registered cells at three seeds each: E0008 minus
   augmentation, E0008 minus the extra steps (back to 1500), E0008 minus the third block.
   This is the only way to attribute the bundle's +0.0501 and to resolve augmentation,
   which E0005 left open.
2. **Re-measure the keep bar at the incumbent.** The item bootstrap ran on the anchor's
   confusion tables (macro-F1 near 0.72); rerun it on E0008's pinned tables before any
   further keep is attempted. At h = 1.23 the frontier is close to arithmetically closed
   under the anchor's bar (a keep would need 0.9899); a bar measured near 0.95 is likely
   narrower and would say honestly whether more room exists.
3. **Run the missing harness control** — label-shuffled training through `train.py` — and
   a learning-rate decay (cosine to zero) at matched steps, the one recipe difference to
   the MedMNIST ResNet the card named and the study never varied.
4. **Measure transfer, not only fit:** a patient-grouped or other-site blood-smear set (the
   full-resolution Acevedo source with a site split, if one can be built) to answer the
   question this image-level split cannot.

## Errata

None filed.
