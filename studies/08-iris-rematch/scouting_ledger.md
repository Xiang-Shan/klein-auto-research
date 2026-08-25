---
type: scouting-ledger
scouted_on: "2026-08-25"
status: frozen-before-consult-gate
predecessor: studies/07-iris-90years (finalized `confirmed` 2026-08-25, claims.lock git_head 1c32260)
---

# Scouting ledger — study 08-iris-rematch

## §0 What this study is and is not

This is a PROSPECTIVELY LOCKED SECOND STUDY ON FULLY SCOUTED DATA. Study 07 published
its entire ledger, both floor sidecars, its measured floor, and its one sealed value —
so **every one of the 100 rows' values is public knowledge before this study begins**,
and the new sealed rows (21 under the pre-committed seed) are *procedurally fresh only*: the registered protocol never
conditions selection on them, but no one is blind to them. The integrity claim of this
study is the LOCK (seeds, bars, eligibility, branch rules registered before any 08
measurement), not blindness. Banned everywhere: 独立复现 / blind / untouched / virgin.

## §1 Scouted quantities (all from study 07's committed artifacts unless marked)

- S1 Anchor declared-split dev Brier (07, seed 20260828): **0.026744** (E0001, keep).
- S2 Anchor lottery over the 80 non-sealed rows, k=20 (07 recipe): **mean 0.018714,
  std 0.016314** → floor 2×std = 0.0326 → ceil3dp **0.033**; klein default
  max(2std, range/2) equal after rounding; no raise.
- S3 **Headroom arithmetic** (drives this study's design): Brier ≥ 0 ⇒ max possible
  improvement over the anchor = the anchor's own score. vs lottery mean: 0.0187 =
  **0.57×δ**; vs 07 declared split: 0.026744 = **0.81×δ**. A keep-sized (≥δ) win at
  n≈60 was arithmetically impossible in study 07's frame.
- S4 The lottery tail: **4 of 20 draws** had anchor dev Brier > 0.033 (0.0332, 0.0375,
  0.0431, 0.0501) ⇒ a FRESH declared split has ≈20% chance of "door ajar"
  (headroom_declared ≥ 1). RQ1's prior comes from exactly this row.
- S5 07 challenger lottery means (all WORSE than anchor 0.0187): logit 0.0454 ·
  knn7 0.0355 · svm_rbf 0.0362 · hgbt 0.0494 · lda_petal 0.0422 · lda_sepal 0.2261.
  Best-per-draw counts: anchor 9 · hgbt 5 · logit 3 · knn7 3. Draw-15 counterexample:
  2 keep-sized flips / 120 paired comparisons.
- S6 07 sealed one-look (spent forever): anchor sealed Brier **0.055198**, +0.86×δ vs
  dev, inside the registered ±2δ band; sealed AUC/PR-AUC/F1 all 1.0 (ceiling).
- S7 07 declared-split challenger values (E0003–E0008): logit 0.059078 · knn7 0.045403
  · svm_rbf 0.056963 · hgbt 0.099975 · lda_petal 0.069452 · lda_sepal 0.168936.
- S8 k-seed fit-noise sweep (07): std exactly **0** — LDA closed form; registered
  degenerate companion.
- S9b Declared-split geometry (measured at data-card authoring, pre-gate,
  deterministic given the pre-committed seed): train 59 (30/29), dev 20 (12/8),
  sealed 21 (8 versicolor / 13 virginica) with the twin pair together behind the
  seal; non-sealed pool = 79 rows, no multi-row group.
- S9 **Pre-gate smoke preview (this study, 2026-08-25)**: the standard KLEIN_SMOKE=1
  syntax/shape check on train.py printed the anchor's dev Brier on the FRESH declared
  split (seed 20260907): **0.029442**. Seen before the gates; disclosed here. The
  RQ1 branch fires on the MEASURED minimum_delta at Phase 1, not on this preview —
  but note 0.029442 < 0.033 would close the door if δ repeats. Nothing else was run
  on the 08 split; no challenger has been scored on it; no sealed row has been scored.
- S10 TabPFN infrastructure spike (2026-08-25, sklearn breast_cancer rows ONLY, never
  iris): package 8.4.0; checkpoint **v2** (Prior-Labs/TabPFN-v2-clf, public, ungated;
  the 8.4.0 "auto" path resolves to a newer checkpoint family gated behind a browser
  license flow — v2 is pinned in-factory). Bit-identical same-seed CPU fits
  (max |Δp| = 0.0); different seed differs; fit+predict 0.099 s warm at n=60,
  4 features. Weights cached locally; HF_HUB_OFFLINE=1 for all study runs.

## §2 Adaptive influences (design choices this scouting shaped)

- A1 The entire estimand architecture (headroom audit → open/closed rungs → Bar-1
  statistical / Bar-2 actionability split → data ladder) exists BECAUSE S3 shows a
  bare "beat Fisher by a keep at n=60" is closed by arithmetic ~80% of the time.
- A2 Metric val_brier inherited from 07 (AUC pegged at ceiling on 14/20 splits and on
  the sealed rows; logloss = clipping artifact) — and because AUC is invariant under
  recalibration, which would blind RQ4's calibration lane.
- A3 Roster composition: the calibration lane (lda_platt/lda_isotonic/lda_shrinkage,
  *_isotonic wrappers) targets the S6 observation that only the proper score moved at
  the ceiling; the foundation lane (tabpfn, tabpfn_e16) is the user's "modern
  challenger" ask, spike-verified in S10.
- A4 Twins ruling, group split, 99-groups contract: inherited unchanged from 07.
- A5 Ledger floor recipe = 07's EXACT recipe on the new split (like-for-like with
  0.033); the ARENA's per-rung floors drop the range/2 escalation (k=40 inflates
  range mechanically) — deviation registered in study.yaml/research_plan.
- A6 Fresh seed namespace 202609xxxxx chosen to be disjoint from every 07 namespace;
  declared seed 20260907 pre-committed with a no-redraw rule (S4 makes the redraw
  temptation concrete; the rule kills it).
- A7 Both parade branches (door-closed / door-ajar) pre-scripted from S4.
- A8 Sealed-coda branch G's challenger pick (tabpfn at n=60) chosen BEFORE any 08
  measurement — the 1936-vs-2025 marquee gap, band-check role only.

## §3 Honest residual — NOT scouted (what this study can genuinely learn)

- The measured minimum_delta under the 08 recipe (seeds 20260901001-020) and the
  arena's per-rung floors δ_n at every rung.
- Every challenger's value on the seed-20260907 declared split (only the ANCHOR's
  smoke preview exists, S9).
- The sealed evaluations: no model has been scored on the 21 sealed rows of
  seed 20260907 (their raw values are public via 07 — the disclosure — but no
  T1/T2 sealed Brier exists).
- Whether ANY rung below 60 comes out OPEN — the per-rung anchor means m_n and
  stds at n ∈ {45,30,20,12,8} have never been measured (07's lottery ran only at
  full train size).
- Every number for the 16 families that did not exist in study 07 (qda, gnb,
  lda_shrinkage, lda_platt, lda_isotonic, logit_l2, logit_area, knn_tuned,
  svm_linear_platt, rf, rf_isotonic, extratrees, hgbt_isotonic, gpc_rbf, mlp_small,
  tabpfn, tabpfn_e16, vote_soft, stack_logit) — on any split, at any rung.
- All Bar-1 max-t results; RQ4's attribution fractions; RQ5's per-rung control
  separations under the sign-flip test.

## §4 Prior-scoring rule (binding on findings)

The findings prior scorecard counts ONLY priors tagged `(source: uninformed)`:
RQ3(a), RQ3(b), RQ4. RQ1, RQ2's classical half, and RQ5 are tagged
`(source: scouting-study-07 (measured))` and are EXCLUDED from the scorecard.

## §5 Provenance

Study 07 artifacts as of git 8d6f41e (claims.lock pinned at 1c32260): results.tsv,
sweeps/split_lottery.sidecar.tsv, sweeps/kseed_floor.sidecar.tsv, study.yaml
noise_floor block, findings.md C1–C19, aux_metrics.tsv (sealed row). TabPFN spike
script + JSON summary preserved in the presentation task worklog (2026-08-25 entry).
Smoke preview S9 produced by `KLEIN_SMOKE=1 uv run --locked python train.py` at
commit 3d5e481, no sidecars written.
