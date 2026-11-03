---
type: findings
domain: "deep-learning scaling (image classification)"
profile: "ml-research"
kind: "estimate"
status: complete
concepts: [data-scaling-exponent, pure-power-law, sealed-extrapolation, step-budget-floor, nested-subsamples, detached-attested-cells]
related: [22-cnn-data-scaling, 13-charlm-fixed-budget]
---

# Findings — 22-cnn-data-scaling

> SYNTHESIZE stage output (klein-synthesist, 2026-11-03). Every claim cites evidence ids
> from the immutable run manifests, the replication records or a pinned artifact
> (`art:<alias>` in `claims.lock`). Fully qualified claim ids are
> `22-cnn-data-scaling#Cn`. Not yet refereed — Gate 3 follows in a fresh context.

**How to read the evidence.** Two registered tracks, no frontier and no keeps.
`primary` holds seven cells: the six development cells E0001–E0006 (each a 3-seed array,
scored on the development lane = official train rows 50,000–59,999) and the one sealed
full-pool cell E0008 (scored on the official t10k test set). `exponent` holds one cell,
E0007, the pure power-law fit over the six pinned cells. E0001–E0006 ran as detached jobs
and are **attested, not observed** (`execution.mode: detached`, `observed_by_notary:
false` in each manifest); E0007 and E0008 ran under the notary in the foreground. Two
replications re-executed under observation and reproduced with difference 0:
`rep:E0005@20261103T084144Z` (the N=8000 cell) and `rep:E0007@20261103T084735Z` (the fit).
Derived numbers that no run prints (local exponents, per-seed slopes, epochs per cell, the
post-hoc refit) live in `tables/synthesis_summary.tsv`, written by
`figures/synthesis_summary.py` from the pinned tables alone — no training, no data read;
every row of it is **post-hoc and exploratory**.

## ① Research-question verdicts

| Claim | RQ | Track | Verdict | Strength | Class | Evidence | Delta + uncertainty |
|---|---|---|---|---|---|---|---|
| **[C1]** | RQ1 | exponent | **answered (estimate)**: alpha 0.1304, a 2.126 — inside the prior range 0.1–0.6, but BELOW its "most likely 0.2–0.4" band | confirmed | empirical-description | E0001–E0006, E0007, rep:E0007@20261103T084735Z, art:fit | printed within-N bootstrap 0.1181 to 0.1411 — descriptive, NOT a calibrated 95% interval (method card §4(c)); post-hoc per-seed-slope t-interval 0.1033 to 0.1569 (art:synth) |
| **[C2]** | RQ2 | exponent | **refuted**: a pure power law is not adequate over N=500 to 16000 | confirmed | empirical-description | E0001–E0006, E0007, rep:E0007@20261103T084735Z, art:fit | log-log R² 0.7955 vs the registered 0.98; the three smallest cells are flat (0.8296, 0.9492, 0.8408) where the law needs a decline |
| **[C3]** | RQ3 | primary | **refuted**: the law did not predict the full-pool loss within 0.20 | confirmed | procedural-verdict | E0007, E0008, art:fit | measured 0.3959 (seed sd 0.0090) vs predicted 0.5066; signed relative error -0.2802 (per seed -0.2819, -0.2502, -0.3084) |
| **[C4]** | RQ4 | primary | **refuted — opposite sign**: the measured loss is BELOW the prediction; the law was pessimistic | confirmed | procedural-verdict | E0007, E0008, art:synth | predicted minus measured +0.1107 nats; partition caveat — cells on development, sealed cell on t10k |

Claim sentences, as locked:

- C1 — The pure power law fitted to the six seed-mean development cells has exponent alpha 0.1304 and prefactor a 2.126; its printed bootstrap spread 0.1181 to 0.1411 is descriptive, not a calibrated interval.
- C2 — A pure power law is not an adequate description of N=500 to 16000: the six-cell log-log fit has R² 0.7955, below the registered 0.98, because the three smallest cells are flat at 0.8296, 0.9492 and 0.8408 instead of declining.
- C3 — The law fitted on the development cells did not predict the sealed full-pool test loss within the registered 0.20: measured 0.3959 against predicted 0.5066, a signed relative error of -0.2802 (P3 refuted).
- C4 — The miss runs opposite to the registered direction: the measured full-pool loss is below the law's prediction by 0.1107 nats, so the pure law was pessimistic rather than optimistic (P4 and P6 refuted), with the fit cells scored on development and the sealed cell on the official test set.

**Strength scoping.** C1 and C2 are `confirmed` on the exponent track, whose
`confirmation.require: [replicate]` is met by `rep:E0007@20261103T084735Z` — a replication
of the fit's ARITHMETIC on the pinned cells, not a re-measurement of the cells (only E0005
was re-executed). C3 and C4 are procedural verdicts on the primary track, whose sealed
access was spent once (E0008) and which carries `rep:E0005@20261103T084144Z`, so
`[sealed, replicate]` are both on record. "Confirmed" here means the procedure's verdict
stands — not that the mechanism is known (see ③).

## ② Registered predictions (from the ledger)

Copied from `klein predict list` (2 supported, 5 refuted, 0 inconclusive, 0 open).

| P# | Statement | Rule | Observed | Verdict (ledger) | Evidence | Decision |
|---|---|---|---|---|---|---|
| P1 | fitted alpha in [0.10, 0.60] | `{primary_metric, between, [0.10, 0.60]}` | alpha 0.1304 | supported | E0007 | — |
| P2 | pure power law log-log R² >= 0.98 | `{fit_r2, >=, 0.98}` | R² 0.7955 | refuted | E0007 | program.md 2026-11-03 "Decision: P2 refuted (fit_r2 0.796 < 0.98)" |
| P3 | full-pool test loss within 0.20 relative of the law | `{extrapolation_rel_error, abs_le, 0.20}` | abs value 0.2802 | refuted | E0008 | program.md 2026-11-03 "Decision: P3 refuted" |
| P4 | measured full-pool loss ABOVE the law (error > 0) | `{extrapolation_rel_error, >, 0.0}` | -0.2802 | refuted | E0008 | program.md 2026-11-03 "Decision: P4 refuted, and P6 refuted" |
| P5 | alpha in [0.15, 0.32] (method card MC1) | `{primary_metric, between, [0.15, 0.32]}` | alpha 0.1304 | refuted | E0007 | program.md 2026-11-03 "Decision: P5 refuted (alpha 0.130 < 0.15)" |
| P6 | signed error in [0.03, 0.25] (method card MC3) | `{extrapolation_rel_error, between, [0.03, 0.25]}` | -0.2802 | refuted | E0008 | program.md 2026-11-03 "Decision: P4 refuted, and P6 refuted" |
| P7 | sealed seed-mean best_step >= 6329 (method card MC5, sealed half) | `{best_step, >=, 6329}` | 8050 of 8437 steps | supported | E0008 | — |

**[C5]** P7 held: the full-pool cell's best inner-validation checkpoint came at seed-mean
step 8050 of 8437, above the registered 6329, so the cell was still improving near the end
of its budget (best_step share 0.954; per seed 8400, 7770, 7980 — E0008, `runs/E0008/seeds.tsv`).

- C5 — P7 held: the full-pool cell's best inner-validation checkpoint came at seed-mean step 8050 of 8437, above the registered 6329, so the cell was still improving near the end of its budget.

**The method card's unregistered priors, held to account** (art:synth, post-hoc
arithmetic on pinned tables):

- **MC2 — the curve FLATTENS (small-end local exponent exceeds the large-end one by
  >= +0.03): CONTRADICTED.** Small-end local exponent -0.0096, large-end 0.2127,
  difference -0.2223. The curve steepens with N over this range; it does not flatten (C7).
- **MC4 — printed interval width <= 0.04 and per-seed t-interval >= 2x wider: HELD.**
  Printed width 0.0230; the per-seed-slope t-interval (0.1033 to 0.1569, width 0.0536) is
  2.33 times wider (C12).
- **MC5, N=16000 half — seed-mean best_step >= half of 2250: HELD** (2202.67; E0006, aux).

The sharper METHOD-gate predictions fared worse than the wide CONSULT ones: P5, P6 and the
unregistered MC2 were all refuted; the one sharp prior that held (P7) was about training
dynamics, not about the curve. The card's whole belief (a floor fraction U(0.40, 0.80), an
optimistic law) was built around a saturating curve; the data showed the reverse — a flat
start and a steepening curve.

## ③ Surprises and why

**Surprise 1 — the small end of the curve is flat, and N=1000 is worse than N=500.**

**[C6]** Every cell's best checkpoint fell in the last 5% of its step budget (best_step
share 0.954 to 1.0 across E0001–E0006 and E0008), and the three smallest cells all sat on
the shared 400-step floor — 113.8, 56.9 and 28.4 epochs — while every cell from N=4000 up
trained 20.0 epochs (E0001–E0006, E0008, art:synth).

- C6 — Every cell's best checkpoint came at 0.954 to 1.0 of its step budget, and the three smallest cells shared the 400-step floor, with epoch counts of 113.8, 56.9 and 28.4.

**[C7]** The method card's flattening prior MC2 is contradicted: the local exponent over
the three smallest cells is -0.0096 against 0.2127 over the three largest, a difference of
-0.2223 where MC2 required at least +0.03 — over this range the curve steepens with N
(E0001–E0006, art:synth; post-hoc).

- C7 — The method card's flattening prior is contradicted: the local exponent over the three smallest cells is -0.0096 against 0.2127 over the three largest, a difference of -0.2223 where the prior required at least +0.03, so the curve steepens with N over this range.

**[C8]** N=1000 sits above N=500 in all three seeds — paired, because subsamples are
nested within a seed — by +0.1195 on average (range 0.0347 to 0.1748), at an identical
400-step budget (E0001, E0002, art:synth). The cell journal recorded it at the time and did
not retry (program.md, "Observation (E0002)").

- C8 — N=1000 sits above N=500 in all three seeds on nested, paired subsamples, by +0.1195 on average (range 0.0347 to 0.1748), at an identical 400-step budget.

**[C9]** *Mechanism — a hypothesis, not tested.* The flat left end may be compute-limited:
at one shared 400-step budget the smallest cells' loss would track optimisation steps more
than data, which would flatten the six-cell slope and make the pinned law over-predict the
full-pool loss. No step-matched or step-extended small cell was run, so this stands
untested. Rival readings fit the same evidence: the "small-data region" Hestness et al.
describe, where loss barely improves with N whatever the budget (`ref:hestness2017`), and
sample-wise non-monotonicity of a fixed model (`ref:nakkiran2020`), though the
best-checkpoint rule should damp the latter. The N=1000 inversion itself is **unresolved**:
checkpoint selection on 50- and 100-image inner sets is visibly optimistic at N=500
(held-out over inner-validation loss ratio 1.2245 against 1.0801 at N=1000, art:synth) and
E0002's seed sd of 0.0626 is the largest of any cell, but neither was isolated (E0001,
E0002, E0003, E0007, E0008).

- C9 — Hypothesis, untested: the small end is compute-limited, so at a shared 400-step budget the loss tracks steps more than data, which would flatten the pinned slope and make the six-cell law over-predict the full-pool loss; no step-matched or step-extended small cell was run to test it.

**Surprise 2 — the law over-predicted, and so did the most favourable refit.**

**[C10]** A post-hoc pure-law refit over the three largest cells alone gives alpha 0.2127
and predicts 0.4254 at the full pool — still above the measured 0.3959, a signed relative
error of -0.0745 (E0004–E0006, E0008, art:synth; NOT registered, NOT the pinned law). So
beyond the small-end slope bias, the curve kept steepening past N=16000: the descriptive
cross-partition local exponent from N=16000 to the full pool is 0.2674 (art:synth). A pure
law has one slope and floor terms can only flatten it; nothing in the registered fit can
steepen.

- C10 — A post-hoc pure-law refit over the three largest cells alone gives alpha 0.2127 and predicts 0.4254 at the full pool, still above the measured 0.3959, a signed relative error of -0.0745.

**[C11]** *Mechanism — interpretation.* An easier test set is an unlikely explanation of
the over-prediction: in the sealed cell the test loss is 1.0877 times the same run's
inner-validation loss, against 1.0158 and 1.0161 for development loss in the two largest
development cells (E0005, E0006, E0008, art:synth). Relative to train-file images, the
t10k partition looks slightly HARDER for this network, not easier — which pushes against
the observed sign and so strengthens C4. Caveats: the inner loss is a minimum over
checkpoints (biased low), and the data card measured no first-order covariate shift (WARN
1: per-image SMD +0.015) but not loss; the partition difference remains a confound in
magnitude, if not in sign.

- C11 — An easier test set is an unlikely explanation of the over-prediction: the sealed cell's test loss is 1.0877 times its own inner-validation loss against 1.0158 and 1.0161 for the two largest development cells, so the test partition looks slightly harder, not easier.

**Surprise 3 (expected by the card, confirmed) — the printed interval is too narrow.**

**[C12]** The printed within-N bootstrap width is 0.0230 exponent units and the
per-seed-slope t-interval (0.1033 to 0.1569) has width 0.0536 — 2.33 times wider, so MC4
held; the per-seed slopes are 0.1423, 0.1260 and 0.1219 (E0001–E0007, art:synth, art:fit).

- C12 — The printed within-N bootstrap width is 0.0230 exponent units and the per-seed-slope t-interval (0.1033 to 0.1569) has width 0.0536, which is 2.33 times wider, so the card's interval prior held.

**Prediction health and calibration.** No cell collapsed: every array printed finite
losses, top-5 accuracy is at least 0.987 in every cell (aux). Calibration improves along
the curve — val_ece 0.0516 at N=500, 0.0261 at N=16000, 0.0104 at the full pool (E0001,
E0006, E0008, aux; the last on the test partition) — so rank and calibration did not trade
off from N=2000 upward, where lower cross-entropy came with lower ECE at every step; the one
exception is N=1000 to N=2000, where loss fell but val_ece rose from 0.0824 to 0.0876. No crashes, no
discards and no sweeps exist; the two `sweeps/sealed_dryrun.*.log` files are the sealed dry
runs, which spent nothing.

## ④ Practical advice

1. **[C13]** Before fitting a data-scaling exponent, make the step budget grow with N
   across the whole range — no minimum that several cells share — and check that no cell's
   best checkpoint sits at the end of its budget; here three cells shared one 400-step
   budget and every best checkpoint sat in its last 5% (E0001–E0006, E0008, art:synth).
   - C13 — Before fitting a data-scaling exponent, make the step budget grow with N across the whole range, with no minimum that several cells share, and check that no cell's best checkpoint sits at the end of its budget; here three cells shared one 400-step budget and every best checkpoint came at 0.954 or more of its budget.
2. **[C14]** Do not accept a fitted law on its in-range R² or its interval; hold it to a
   sealed extrapolation point — here the registered law missed by -0.2802 and even the most
   favourable post-hoc refit missed by -0.0745 (E0007, E0008, art:synth).
   - C14 — Do not accept a fitted law on its in-range R² or its interval; hold it to a sealed extrapolation point: here the registered law missed by -0.2802 and even the most favourable post-hoc refit missed by -0.0745.
3. **[C15]** Report the per-seed-slope t-interval beside any within-N bootstrap: with nested
   subsamples the bootstrap width 0.0230 was 2.33 times narrower than the per-seed
   t-interval width 0.0536 (E0007, art:synth).
   - C15 — Report the per-seed-slope t-interval beside any within-N bootstrap: with nested subsamples the bootstrap width 0.0230 was 2.33 times narrower than the per-seed t-interval width 0.0536.
4. **[C16]** Score the fit cells and the extrapolation point on the same distribution, or
   run a control that measures the partition gap; here the sealed point used t10k and the
   cells the development lane, so the extrapolation error cannot be split exactly between
   law and partition (E0006, E0008, art:synth).
   - C16 — Score the fit cells and the extrapolation point on the same distribution, or run a control that measures the partition gap; here the sealed point used the official test set and the cells the development lane, so the extrapolation error cannot be split exactly between the law and the partition.
5. **[C17]** Do not assume a pure law is optimistic for a fixed small model: the
   saturating-floor argument behind P4 and P6 predicted a positive error, and the observed
   error was negative — the curve's shape over the measured range came from the protocol
   (its step schedule and checkpoint rule) as much as from any floor (E0007, E0008).
   - C17 — Do not assume a pure law is optimistic for a fixed small model: the floor argument behind P4 and P6 predicted a positive error, and the observed error was negative.

## ⑤ Practitioner impact — what to change in a training recipe, and at what cost

No `materiality:` block is registered, so nothing here is priced; the only bars cited are
the registered prediction rules.

- **The change.** Replace the `max(400, 20 epochs)` step rule with a schedule whose steps
  grow with N over the whole fitted range (or a fixed, large step budget under which every
  cell's best checkpoint lands well before its end), then refit. Evidence: C6–C9 — three
  shared-budget cells and a -0.2223 difference in local slope between the two ends.
- **Matched-compute condition.** These cells were NOT matched in compute: steps scale with
  N above N=4000 (20.0 epochs each) and the three smallest share 400 steps. The
  data-scaling exponent quoted in C1 is therefore a property of this protocol, not of the
  network alone. The full-pool cell trained 8437 steps.
- **Seed spread.** Seed sd per cell runs from 0.0072 (N=8000) to 0.0626 (N=1000), and is
  0.0090 at the full pool. The registered `minimum_delta` 0.001 is a contract resolution,
  not a measured floor — `klein verify` reports the noise floor "not measured" on both
  tracks; no claim here leans on a keep bar.
- **Hardware.** 4-CPU x86_64 Linux VM, no GPU, torch 2.13 CPU path, `TORCH_THREADS = 1`.
  The sealed 3-seed array took 1883.8 s wall (E0008 manifest), mean training time 614.6 s
  per seed; the N=16000 cell 181.1 s per seed (aux). Wall time is informational only.
- **Cost of the fix.** Extending the three smallest cells to (say) the N=4000 budget adds a
  few minutes of CPU per seed on this hardware — the cheapest test of C9 available.

## ⑥ Literature tie-back

- **Hestness et al. 2017** (`ref:hestness2017`): exponents between -0.07 and -0.35 across
  domains, for model-grown-with-data curves. Our alpha 0.1304 sits inside that range at the
  shallow end, below their ImageNet cross-entropy value of 0.35. Their "small-data region"
  is a live rival to the compute-limited reading of our flat left end (C9).
- **Kaplan et al. 2020** (`ref:kaplan2020`): alpha_D near 0.095 for large early-stopped
  models. Ours is steeper overall, and much steeper at the top of the range (local exponent
  0.2127).
- **Rosenfeld et al. 2020; Hoffmann et al. 2022; Bahri et al. 2024** (`ref:rosenfeld2020`,
  `ref:hoffmann2022`, `ref:bahri2024`): fixed-model curves saturate at a floor, so a pure
  law should be optimistic. **Not observed at this scale** — the error sign was negative
  (C4). This does not refute the floor; it says a floor, if present, was masked by the
  steepening.
- **Alabdulmohsin et al. 2022** (`ref:alabdulmohsin2022`): judge laws by extrapolation, not
  interpolation. Matched — the sealed point is what exposed the law; R² alone would have
  refuted it without saying which way it misses.
- **Caballero et al. 2023** (`ref:caballero2023`): broken power laws. A flat-then-steep
  curve is the shape a broken law models and a single exponent cannot (C2, C7).
- **Viering & Loog 2023; Clauset et al. 2009; Hoiem et al. 2021** (`ref:viering2023`,
  `ref:clauset2009`, `ref:hoiem2021`): non-monotone learning curves occur, and a high R² is
  not evidence for a power law. Both match: our R² was low, and the inversion is real across
  all three seeds (C8).
- **Besiroglu et al. 2024** (`ref:besiroglu2024`): published scaling-fit intervals are
  implausibly narrow. Matched in miniature (C12).
- **Xiao et al. 2017** (`ref:xiao2017`): the full-pool CNN reaches test accuracy 0.8605
  (E0008, aux), below the paper's sklearn MLP (0.871) and RBF SVC (0.897) context numbers —
  not matched budgets, so no ranking, and P7 says the CNN was still improving.
- **Priors scorecard.** Knowledge-sourced priors: RQ1's band held (P1), RQ3 and RQ4 missed
  (P3, P4) — one of three. The uninformed RQ2 prior missed (P2). The method card's
  theory-derived sharpenings went one of three (P5, P6 refuted; P7 held), plus the
  unregistered MC2 refuted and MC4 held. Neither source outpredicted the other; the shared
  error was assuming a saturating curve.

## ⑦ What to try next

1. **Step-extended small cells (tests C9).** Re-run N=500, 1000 and 2000 with the 20-epoch
   rule replaced by a budget at least as large as the N=4000 cell's, 3 seeds each, same
   development lane. If the left end then declines and the six-cell exponent steepens, the
   compute-limited reading gains support; if it stays flat, the small-data-region reading
   does.
2. **A same-partition extrapolation control (tests C11/C16).** Train on N=50000 (the train
   lane) and score development — in a fresh study, registered as its sealed point instead,
   or as an extra development cell — to split the -0.2802 miss into its law and partition
   parts.
3. **Register a two-regime or floor law before data.** Pre-register a smoothly broken power
   law or `L_inf + b N^-beta` fitted on the same six cells and hold it against a fresh
   sealed point (a new size between N=16000 and the full pool, on held-out data) — never
   refit on E0008.
4. **Longer full-pool training (follows P7).** The full-pool cell's best checkpoint sits in
   the last 5% of its budget; measure how far the loss keeps falling with a larger step
   budget to learn whether 0.3959 is data-limited or compute-limited.

Evidence use: every non-keep run (E0001–E0008) is cited above; `klein verify
--evidence-use` reports 1.00.
