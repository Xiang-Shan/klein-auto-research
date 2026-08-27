# Findings — 09-iris-first-lesson

Study label: **exploratory** (protocol-completion label, pre-registered as the
Branch-B outcome: no challenger cleared both its own resolution bar and the
selection guard, so the challenger seal stayed shut by rule and finalize ran
`--allow-exploratory`. NOT an evidence downgrade — research_plan §7; the label
never translates into scientific language.)

Claim ids are stable (`09-iris-first-lesson#C<n>`, never renumbered). Every
claim carries one registered CLASS (study.yaml `claims_discipline.claim_classes`)
and an Evidence level (`exploratory` until the track's sealed run completes its
band check; the sealed coda is discipline, never an upgrade). Vocabulary is
bound by `claims_discipline`; the two-headroom-numerators law and the
nominal-rung qualifier apply throughout.

## ① RQ0 — measurement permission (the study's lead result)

- **[C1] · procedural-verdict · exploratory.** The ledger door is CLOSED:
  h = anchor_declared_dev / δ = 0.026408807494830228 / 0.08 = **0.330 < 1**.
  Registered at scaffold (`bound {ideal: 0.0, on_infeasible: ack}` — the first
  shipped study to arm klein's detection-limit audit), measured at adaptive-1,
  acknowledged with the pre-committed run-anyway note BEFORE any challenger
  arena number existed. A scalar-δ keep was arithmetically impossible for every
  challenger; every parade disposition inherits that scope.
- **[C2] · empirical-description · exploratory.** The per-candidate permission
  map (numerator: anchor metrology mean 0.04302915 over the 20 paired redraws;
  denominator: each challenger's OWN paired floor): **open** — lda_shrinkage
  h_c 1.57, logit_l2 1.36, qda 1.29, tabpfn 1.23; **measurement-closed** —
  svm_rbf_platt 0.958, knn_tuned 0.59, hgbt 0.54. Three of seven comparisons
  could not be won at their own resolution no matter the data's verdict;
  results there are descriptive only. `sweeps/rq0_headroom.tsv`.
- **[C3] · empirical-description · exploratory.** The registered
  paired-vs-marginal prediction was **FALSIFIED**: on this geometry only
  **2 of 7** paired floors (knn 0.0730, hgbt 0.0796) exceed the anchor's
  marginal 2×std (0.0501); the 07 recomputation had given 5/6. Which floor is
  wider is geometry- and roster-dependent — "measure both, name the estimand"
  is the durable rule, not any fixed ordering. `sweeps/candidate_floors.tsv`.

## ② RQ1 — the contest (nobody cleared their own bar)

- **[C4] · procedural-verdict · exploratory.** Bar-1: **0 of 42** cells cleared
  the registered selection guard (repeat-level sign-flip max-t, full 1024
  enumeration, adjusted score ≤ 51/1024). Bar-2: **0** (it additionally needs
  mean gain ≥ floor_c at an OPEN rung — and no rung opened). The fold-level
  SENSITIVITY exhibit also fires 0 cells (seed 2026101500) — unlike study 08,
  this Branch B carries no fragile lone detection to caveat. The anchor stands
  **by default, not by victory**. `sweeps/arena_verdicts.tsv`, `sweeps/analysis.log`.
- **[C5] · empirical-description · exploratory.** The two-level verdict, both
  levels published: on the ONE declared split, four challengers beat the
  anchor's raw Brier (svm_rbf_platt 0.016995, qda 0.019434, tabpfn 0.019730,
  logit_l2 0.025256 vs 0.026409; best gap 0.0094 = 0.12×δ — and svm's own
  comparison is h_c-closed at 0.958); across the registered rung-60 lottery the
  impression **reverses** — only lda_shrinkage's mean gain is positive
  (+0.004171 = 0.15× its own bar, guard score 0.39), every other family is
  worse on average (tabpfn −0.0040 … hgbt −0.0595). One split is one lottery
  draw; the lottery is the estimand. Ledger E0004–E0010 (all `discard`, 0
  crashes) + `arena_verdicts.tsv`.

## ③ RQ2 — the sample-size ladder

- **[C6] · empirical-description · exploratory.** Anchor risk and instability
  grow together as n falls: m_n 0.0332 → 0.1055 and across-fold sd 0.0336 →
  0.0867 from nominal rung 60 → 8, while the per-rung floor grows 0.068 →
  0.174. **All six rungs are CLOSED** (60/45/30/20 ceiling-closed, 12/8
  fog-closed; m_n/δ_n 0.47–0.61): the instrument loses resolution faster than
  the families separate — small n blinds the ruler, not just the models.
  `sweeps/headroom.tsv`.
- **[C7] · empirical-description · exploratory.** At the starvation rungs the
  descriptive board flips exactly as scouted: at nominal rung 8 the leaders
  vs the anchor are lda_shrinkage +0.0405 (the registered ≥0.02 lever — HELD),
  qda +0.0285, tabpfn +0.0265 — all deep inside the 0.174 fog floor (≤0.23×,
  guard scores ≥ 0.11). Shared-covariance estimation is the anchor's fragile
  joint at n ≤ 12 and shrinkage buys the repair — stated as a descriptive
  pattern; the MECHANISM demonstration lives in the simulation lane ([C11]).
- Zero seed-variance note: the k-seed sweep is degenerate (std exactly 0,
  closed-form LDA) — this establishes zero algorithmic fit randomness under
  fixed inputs and NOTHING more (never "low variance"). `sweeps/kseed_floor.log`.

## ④ RQ3 — feature sufficiency

- **[C8] · empirical-description · exploratory.** Petal-only LDA retains most
  of the probability quality: declared split 0.03135 (E0002) vs anchor
  0.026409; rung-60 lottery mean 0.0483 vs 0.0332. Sepal-only is the
  registered catastrophe: declared 0.156308 (E0003), rung-60 mean 0.2146.
- **[C9] · procedural-verdict · exploratory.** The positive control FIRED at
  every rung: one-sided worsening test p = 0.0010 at all six rungs against the
  Bonferroni bar 0.0083, worsening +0.15 to +0.19. The instrument that
  declared every contest closed can still see a real difference when one is
  there — the closures are about resolution, not blindness. `sweeps/analysis.log`.

## ⑤ RQ4 — ranking vs probability quality

- **[C10] · empirical-description · exploratory.** At nominal rung 60, ROC-AUC
  sits exactly at 1.0 on **55%** of all 400 fold-evals (anchor: 77.5% of its
  40) while the same fold-evals' Brier means span 0.029 (shrinkage) to 0.215
  (sepal control) and log loss spans 0.093–0.618. A saturated ranking metric
  is silent where the probability metrics still order the room — the
  registered reason Brier is this study's primary. `sweeps/rq4_saturation.tsv`.

## ⑥ RQ5 — the simulation lane (the only place the decomposition is legal)

- **[C11] · known-dgp-teaching · exploratory.** Under known p*(x) with the
  plug-in decomposition (ddof=0; identity |total−(irr+bias²+var)| ≤ 8.3e-17
  across all 164 populated cells; 100 registered draws/cell): **G1** (LDA's
  world) — every model converges to the irreducible floor 0.1113; at n=8
  shrinkage/logit edge plain LDA by variance (0.1479/0.1533 vs 0.1585); no
  nonlinear model beats the linear family at any n. **G2** (+16 irrelevant
  dims) — variance explodes at small n (plain LDA var 0.133 at n=12; shrinkage
  0.121) and **QDA is unfittable (rank-deficient) for n ≤ 30 — 400 recorded
  failures, published as data**: flexible covariance doesn't degrade
  gracefully, it exits. **G3** (unequal covariance) — QDA's structural win:
  bias² 0.0014 vs LDA's persistent 0.0320 at n=500. **G4** (XOR) — the linear
  family plateaus at bias² 0.216 (total 0.251, marginally worse than the
  constant predictor's 0.25) while hgbt reaches 0.051; at n=8 hgbt IS the
  constant predictor (var exactly 0 under min_samples_leaf=5). Mechanisms are
  DGP-licensed teaching results — never the true iris DGP, never an empirical
  decomposition of studies 07–09. `sweeps/sim_risk.tsv`, `sweeps/sim_cells_failed.tsv`.

## ⑦ Interpretation (labeled)

- **[C12] · mechanism-interpretation · exploratory.** The anchor's standing on
  this data is best read as an **inductive-bias match**: four nearly
  sufficient, nearly Gaussian features (petal-only already carries most of the
  signal — [C8]), an almost-linear boundary, small-to-medium n, and
  shared-covariance regularization. The same reading predicts its failure
  modes: break equal covariance (G3) or linearity (G4) and the match — and
  the standing — inverts. 「口径：这是解读，不是登记过的分解量。」
- **[C13] · research-discipline · exploratory.** What transfers is the
  process, not the winner: publish the permission map BEFORE the tournament
  (three of seven contests here could never have been won — saying so first is
  what makes "nobody displaced the anchor" meaningful); name the estimand of
  every floor; let controls prove the instrument alive; and let the ledger
  catch its own contaminations — this study retired a split seed over a
  pre-gate staging smoke (scouting_ledger S10) and re-registered two seed
  namespaces on build-time disclosures, all before the consult ack.

## Prediction scorecard (registered levers; study.yaml `predictions_to_falsify`)

| Lever | Registered | Outcome |
| --- | --- | --- |
| DOOR-CLOSED branch | fires iff h<1 | **FIRED** (h=0.330; ack recorded) |
| DOOR-AJAR branch | fires iff h≥1 | not fired (mutually exclusive pair) |
| k-seed fit noise | std exactly 0 | **HELD** |
| paired vs marginal floors | ≥5/7 paired wider | **FALSIFIED** (2/7) — the honest headline of §① |
| shrinkage at rung 8 | ≥0.02 better, descriptive | **HELD** (+0.0405) |
| sepal control | separates at every measurable rung | **HELD** (6/6, p=0.0010) |
| sealed T1 band | \|sealed − 0.026409\| ≤ 0.16 | see §Sealed below |
| sealed T2 | Branch A only | **NOT FIRED by rule** (Branch B; seal stays shut) |

Scoreable RQ priors (`(source: uninformed)` only): RQ4 saturation RATE —
measured 0.55 pooled / 0.775 anchor at rung 60 (prior held directionally; no
numeric prior was registered, so it scores as observed-only); RQ5 crossovers —
G3 QDA leads from n=60; G4 hgbt/svm lead from n≈30–60 (observed-only).

## Frictions filed (for the framework)

1. `klein new` freezes `fingerprints.split` from the scaffold's placeholder
   seed; the DATA gate refreshes the prepared-data hash but not the split hash
   — every seed-editing study must re-touch state (07/08 regenerated wholesale;
   09 refreshed the one field, disclosed). P1 candidate.
2. `klein noise-floor` still cannot emit `estimand:`; hand-added again.
3. `cal_intercept`/`cal_slope` on (near-)separable eval folds are separation
   markers, not calibration readings (E0001: 16.99/8.27) — a registered-aux
   caveat any small-n study should copy.

## §Sealed (appended after the confirmation phase; sentences pre-committed in program.md)

PENDING at synthesis-commit time — the confirmation ack, the single Branch-B
sealed look (coda_primary), and the finalize label follow in the next commits;
the selected pre-committed sentence will be recorded here verbatim.
