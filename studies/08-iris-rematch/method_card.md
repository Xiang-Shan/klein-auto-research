---
type: method-card
domain: "small-n tabular classification (Fisher 1936 iris hard pair, n=100)"
status: go
concepts: [selection-guard, data-ladder, calibration-lane, foundation-model, coda-manifest]
related: [studies/07-iris-90years/method_card.md]
---

# Method card — 08-iris-rematch

> Gate 2 (METHOD). Written BEFORE any challenger run. The registered protocol is
> research_plan.md (§§1–9) + the docstrings of `sweeps/rematch_arena.py` and
> `sweeps/rematch_analysis.py` (frozen by this gate) — this card records the
> method-level choices, their reasons, and the failure policies.

## §1 The anchor and the question

Anchor: `anchor_lda4` — LDA (svd), 4 features, fit train-only; digit-exact
lineage to Fisher 1936 established in study 07 (claim C9, cos 1.000000 to the
printed setosa-versicolor compound; the reproduction question is NOT re-litigated
here). The study asks whether ANY of 21 registered challengers beats it — on the
ledger, past the Bar-1 selection guard, or by a keep-sized margin at an open rung
of the data ladder — and whether any win is captured by an LDA-family adjustment.

## §2 The roster (frozen; 23 families + 2 coda entries)

families.py REGISTRY is the single source: era tags (1936 ×2 / 20c-stats ×8 /
modern-ml ×11 / foundation ×2), eligibility matrix MIN_RUNG (isotonic lanes ≥30,
SVM lanes ≥12, stacking ≥20 — infeasibility-of-method reasons, fixed before any
measurement), estimator seed 20260907 throughout. Method-level laws:

- **Group-aware inner CV everywhere** (`families.inner_splits`,
  StratifiedGroupKFold(3), seeded): calibration (CalibratedClassifierCV),
  kNN tuning (GridSearchCV), and stacking receive precomputed splits — the twins
  ruling enforced INSIDE estimators. `SVC(probability=True)` (row-level internal
  5-fold Platt) is banned; svm families are external Platt maps.
- **`ensemble=False` on every CalibratedClassifierCV**: base model fits on ALL
  train rows; only the calibration map is learned out-of-fold — the pure
  calibration lane RQ4's capture ratio needs.
- **TabPFN v2** (package tabpfn==8.4.0 pinned in uv.lock, optional extra
  `foundation`; checkpoint family v2 pinned in-factory via
  `create_default_for_version(ModelVersion.V2)` — the Nature-2025 model,
  HF repo Prior-Labs/TabPFN-v2-clf, public/ungated, default file
  tabpfn-v2-classifier-finetuned-zk73skhh.ckpt, cached 2026-08-25). cpu,
  torch single-thread at spike; n_estimators 4 and 16 variants; spike evidence:
  bit-identical same-seed fits, seed-live, 0.099 s warm. All study runs export
  `HF_HUB_OFFLINE=1`.
- **Registered fallbacks (dormant — spike passed)**, frozen substitution map:
  `tabpfn` → `nystroem_logit` = Pipeline(StandardScaler, Nystroem(RBF,
  n_components=min(30, n_train−1), random_state=20260907), LogisticRegression
  C=1.0 lbfgs max_iter=1000); `tabpfn_e16` → `mlp_bag5` = soft-vote of 5×
  mlp_small with seeds 20260907+i (i=0..4); coda Branch-G challenger →
  `gpc_rbf`. Same eligibility (all rungs). These activate ONLY if TabPFN cannot
  run at parade time; the substitution would be committed with its reason before
  any substituted fit is summarized.

## §3 Verdict machinery (frozen)

- Ledger: klein's own keep/discard vs `minimum_delta`, measured at Phase 1 by
  07's exact recipe on this split (`sweeps/ledger_floor.py`; the script is the
  registration of the arithmetic, incl. ddof=1 sample std and the raise-only
  escalation exactly as coded).
- Arena: `sweeps/rematch_arena.py` two-stage (Stage A headroom BEFORE any
  challenger number; Stage B full roster), per-rung floors
  δ_n = max(ceil3dp(2×sd_n), 0.005 fixed materiality floor), OPEN ⇔ m_n ≥ δ_n,
  descriptive closure labels, UNMEASURABLE >10% anchor failures, per-cell
  row-set hashes published.
- Bar-1 = the SELECTION GUARD (joint repeat-level sign-flip max-t, 1024
  enumerated flips, fixed 113-cell family with never-firing placeholders);
  registered status: a randomization diagnostic under a registered symmetry
  assumption — never "exact", never "FWER", never population inference.
  Bar-2 = guard ∧ mean gain ≥ δ_n ∧ OPEN. Control: one-sided worsening,
  Bonferroni. RQ4: LDA-family adjustment capture, observed non-causal ratio,
  0.5 threshold. All computed ONLY by `sweeps/rematch_analysis.py`; editing
  that file after this gate breaks this card's frozen-analysis clause.
- **Failure policy (registered)**: a challenger fold-eval that raises is a crash
  row in the sidecar (SweepRunner); a cell left with <2 paired repeats becomes a
  never-firing placeholder (t = −inf) that still occupies its guard slot;
  kNN's all-candidates-infeasible case raises (recorded crash), never re-grids;
  nothing is dropped, re-run, or substituted after outcomes are visible.

## §4 Sealed coda (two tracks, one look each)

Registered in program.md §Sealed: mechanical branch rule (W iff ≥1 Bar-2 cell),
`sweeps/coda_manifest.json` written by the frozen analysis (families, baked
train positions from the registered quota scan seed 20260901999 under Branch W,
position hashes, numeric bands, sign convention g_sealed = sealed_primary −
sealed_challenger vs the arena's [p10,p90] of g = anchor − f), executed via the
pre-registered registry entries `coda_primary`/`coda_challenger` that READ the
manifest. The coda band has no nominal coverage after selection — a
procedurally locked audit, never an evidence upgrade; `confirmed` is a
protocol-completion label only. Four Branch-G sentences pre-committed verbatim
(program.md), Branch-W templates slot-filled by the frozen selection.

## §5 Known limits (stated up front)

- All conclusions are conditional on these 100 flowers and this procedure — the
  registered estimand sentences bind every downstream wording; nothing here
  generalizes to other data and no sentence may imply it does.
- The guard's symmetry assumption is registered, not derived (shared anchor,
  deterministic fits); the fold-level max-t sensitivity exhibit is published so
  a skeptic can see whether the verdict is unit-choice-fragile.
- The arena pool is 79 rows with no multi-row group this study (twins sealed
  together); the twins-last rule is registered but idle.
- With 10 repeats the guard's smallest attainable adjusted score is 1/1024;
  single-cell effects smaller than the joint max-t null spread at J=10 are
  invisible — "the guard did not clear" never reads as "no effect exists".

**Decision: GO** — roster, bars, failure policies, coda mechanics, and fallback
map frozen; the analysis file is the registration and is hash-bound by this gate.
