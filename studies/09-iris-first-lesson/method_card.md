<!--
METHOD gate artifact (Gate 2 hashes this file). Draft committed pre-CONSULT;
TBD-AT-GATE slots filled before `klein gate record method`. The frozen sweep
docstrings are part of this card by reference.
-->

# Method card — 09-iris-first-lesson

## §1 The anchor and the questions

Anchor: `anchor_lda4` — LinearDiscriminantAnalysis(solver="svd") on the four
1936 measurements; Fisher's method as shipped, no tuning surface. Questions
RQ0–RQ5 as registered in research_plan §1: measurement permission FIRST
(per-candidate paired floors + headroom), then the contest, the n-ladder,
feature sufficiency, metric meaning, and the known-DGP simulation lane.

## §2 The roster (frozen; 10 empirical families + 2 coda entries; no tuning)

`families.py` is the registry (ESTIMATOR_SEED_009 = 20260912; INNER_FOLDS = 3;
every inner CV = precomputed StratifiedGroupKFold(3, shuffle,
ESTIMATOR_SEED_009) — split POLICIES, never indices; 08#C20):

- anchor_lda4 · controls lda_petal / lda_sepal (LDA svd on the named columns).
- Challengers (7, registry order = parade order): lda_shrinkage (lsqr, auto) ·
  qda (reg_param 0.1) · logit_l2 (Scaler + LogisticRegression C=1.0 lbfgs) ·
  knn_tuned (GridSearchCV n_neighbors {3,5,7,9}, distance weights,
  neg_brier_score, group-aware inner splits, error_score=nan) · svm_rbf_platt
  (CalibratedClassifierCV(sigmoid, ensemble=False) over Scaler+SVC(rbf, C=1.0,
  gamma=scale, probability=False) — SVC(probability=True) BANNED, sklearn 1.9
  deprecation) · hgbt (min_samples_leaf 5, max_leaf_nodes 4, no early stop) ·
  tabpfn (TabPFN v2 via create_default_for_version(ModelVersion.V2,
  n_estimators=4, cpu), pinned ckpt …zk73skhh.ckpt, HF_HUB_OFFLINE=1; spike
  PASSED — scouting S7).
- Frozen dormant fallback (declared before outcomes): tabpfn → nystroem_logit.
- Excluded at registration: gpc_rbf-class (08's separability pathology, 160
  crash rows), ensembles/stacks (nothing to confirm), any new tuning.

## §3 Metrology + verdict machinery (frozen)

- Paired metrology: `sweeps/metrology_paired.py` (20 group-aware redraws,
  seeds 2026099101–120, all 10 families on identical rows) →
  `sweeps/candidate_floors.py`: floor_c = max(2×std(d_c), range(d_c)/2), ddof=1,
  full precision; anchor marginal stats published beside. Ledger scalar δ =
  ceil3dp(max over the 7 CHALLENGER floors); controls excluded from the max;
  raise-only; blindness clause in study.yaml `noise_floor_protocol`.
  TBD-AT-GATE: measured floors table + the binding challenger + δ (paste +
  consult re-record happen in adaptive-1 per research_plan §3; this card
  freezes the RULE, not the number).
- RQ0: `sweeps/rq0_headroom.py` — ledger h (numerator anchor_declared_dev) and
  per-candidate h_c (numerator anchor_metrology_mean); measurement-closed flags;
  committed before Stage B.
- Arena: `sweeps/arena.py` — 10 repeats (2026099201–210) × StratifiedGroupKFold(4)
  over the non-sealed pool; nested whole-group quota rungs {60,45,30,20,12,8}
  (SUBSET_SEED_BASE 2026099300 + 100j + k; twins pinned last; nested subsets;
  identical rows to every family; nominal-rung qualifier binding); per-rung
  δ_n = max(ceil3dp(2×sd of anchor's 40 fold-evals), 0.005); OPEN/ceiling-/
  fog-closed labels; UNMEASURABLE at >10% anchor failures; Stage A before any
  challenger summary; RQ4 companions `arena_aux.sidecar.tsv` (Stage B) + `arena_anchor_aux.sidecar.tsv` (Stage A) (logloss eps 1e-6 —
  clip never touches Brier; AUC/PR-AUC/acc/F1; cal_intercept/cal_slope by
  logit-scale recalibration; NA on single-class eval folds).
- Verdicts: frozen `sweeps/analysis.py` under `run_with_log.py` →
  `sweeps/analysis.log`. Bar-1 = repeat-level sign-flip max-t, FIXED 42-cell
  family, full 1024 enumeration, ≤ 0.05 (grid 1/1024); never FWER/population
  language; no cross-study p_guard comparison. Bar-2 = Bar-1 ∧ mean gain ≥
  floor_c (candidate-specific — the 09 innovation) ∧ rung OPEN. Fold-level
  max-t = SENSITIVITY only (seed 2026101500). Control: one-sided worsening
  sign-flip for lda_sepal, Bonferroni 0.05/6. RQ4 exhibit:
  `sweeps/rq4_saturation.tsv` (ceiling shares beside Brier/logloss means).
  Editing analysis.py after this gate breaks the frozen-analysis clause.

## §4 Sealed coda (branch-dependent; registered amendment: group-aware coda)

Mechanical branch in `sweeps/coda_manifest.json` (written by the frozen
analysis BEFORE the confirmation ack): Branch A iff ≥1 Bar-2 cell at rung 60 —
coda_primary (anchor, band |sealed − E0001| ≤ 2δ) AND coda_challenger (winner,
band = its arena [p10,p90] fold-level g at rung 60, g_sealed = sealed_primary −
sealed_challenger). Branch B — coda_primary only; the challenger seal stays
shut; finalize --allow-exploratory per the pre-registered path. REGISTERED CODA
AMENDMENT (before confirmation): coda bases receive the precomputed group-aware
inner splits and a groups channel in the subset wrapper — 08's non-group cv=3
was lawful only because its non-sealed pool held no multi-row group; that
argument does not port to seed 20260912. Sentences: program.md §Sealed,
一个字都不许改.

## §5 Simulation lane (RQ5; firewall)

`sweeps/sim_dgp.py` — G1 linear-match / G2 +16 irrelevant dims / G3 unequal
rotated covariance / G4 XOR mixture; 6 sklearn models (no TabPFN); n ∈
{8,12,20,30,60,120,500}; 100 draws per cell (seeds 2026400000+…); fixed truth
sample M=4096/DGP (2026900000+g); analytic p*(x), analytic E_Y; plug-in
decomposition irr + bias² + var (ddof=0), identity ≤ 1e-9 asserted per cell;
failed draws recorded, effective k published. Never the true iris DGP; never an
empirical decomposition of 07–09.

## §6 Smoke discipline + known limits (stated up front)

- Smoke: `KLEIN_SMOKE=1 python train.py` for the ledger surface; every sweep
  smoke-tests via sliced params (`--repeats 1` prints the 08 WARNING and never
  feeds study.yaml or the analysis); the study-local test file gates the
  metrology/arena/analysis mechanics before their gates.
- AGENT-SMOKE LAW (registered after the S10 event, scouting_ledger): any
  subagent smoke runs on SYNTHETIC frames only — never the real prepared CSV,
  never the declared split; only orchestrator-run, ledger-governed transactions
  and the registered sweeps touch real rows.
- Limits: estimand is conditional on these 100 flowers and this procedure —
  never new-iris population claims; across-repeat SD is resampling instability,
  never model variance; the empirical lane proves no bias–variance
  decomposition (simulation-lane firewall); "confirmed"/"exploratory" are
  protocol labels; per-candidate floors make some comparisons measurement-
  closed — continued numbers there are descriptive only.
