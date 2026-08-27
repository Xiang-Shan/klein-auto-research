# Research plan — 09-iris-first-lesson (registered protocol)

Frozen at CONSULT; the consult gate hashes this file. Amendments after the ack
are batched into an explicit consult re-record (the one registered amendment is
the post-metrology `noise_floor`/`minimum_delta` paste — §4). Where any other
document disagrees, THIS file governs. Disclosure: `scouting_ledger.md` §0 —
this is a prospectively locked THIRD study on fully scouted data; the lock, not
blindness, is the integrity claim.

Vocabulary law (binds every artifact and the talk): klein ledger **tracks** are
`primary`/`challenger`; the empirical-iris work vs the known-DGP simulation are
**lanes** (empirical lane / simulation lane) — never "tracks".

## §1 Questions

Ninety years after Fisher, the first lesson of data science re-asked as six
registered questions — measurement permission BEFORE model comparison:

- **RQ0 (claim permission).** For each frozen challenger, is the Brier
  comparison arithmetically capable of clearing its OWN paired resolution
  threshold, given Brier's ideal bound 0.0? Ledger scale: h = anchor_dev/δ.
  Candidate scale: h_c = anchor-metrology-mean / floor_c. The two numerators
  are named every time; conflating them is a banned claim.
- **RQ1 (the contest).** At nominal rung 60, does any challenger clear BOTH its
  candidate-specific paired bar (mean paired gain ≥ floor_c) AND the Bar-1
  selection guard, at an OPEN rung?
- **RQ2 (sample size).** How do predictive risk and resampling instability move
  across nominal rungs n ∈ {8,12,20,30,45,60}; does shrinkage LDA lead plain
  LDA descriptively where covariance estimation is fragile (n ≤ 12)?
- **RQ3 (feature sufficiency).** How much probability quality does petal-only
  LDA retain; does the sepal-only positive control fire at every measurable rung?
- **RQ4 (metric meaning).** Where ranking metrics saturate (share of fold-evals
  at the ceiling, published), do Brier / log loss / calibration still separate
  the families?
- **RQ5 (simulation lane).** Under four known DGPs, how do squared probability
  bias, training-set variance, and irreducible uncertainty trade as n grows —
  when the DGP matches LDA's assumptions, adds irrelevant dimensions, breaks
  equal covariance, breaks linearity?

## §2 Identity (all pre-committed)

Declared split: group-aware 60/20/20, seed **20260912** (derived inner seed
20260913), twins rows 102/143 one group (99 groups / 100 rows) — NO REDRAW
under any outcome. RETIRED PRE-GATE: candidate seed 20260909 (inner 20260910)
— a staging smoke scored dev+sealed Briers under it before any gate ack; logs
deleted, seed retired on the 07 seed-42 precedent, re-registered as 20260912
before the CONSULT ack (scouting_ledger S10; agent smokes are
synthetic-frames-only by rule, method card §6).
Seed namespaces, all fresh, disjoint from every 07/08 seed
and inside sklearn's 2**32−1 domain (both predecessors crashed a namespace on
exactly this — 08#C11; every sweep asserts its own seed domain):
metrology paired redraws **2026099101–120** · arena repeats **2026099201–210**
· arena subsampling **2026099300 + 100j + k** · analysis sensitivity MC
**2026101500** · simulation training draws **2026400000 + dgp·100000 +
n_idx·1000 + rep** · simulation truth samples **2026900000 + dgp** ·
ESTIMATOR_SEED_009 = **20260912** (the 07/08 split=estimator idiom, registered
explicitly) · k-seed fit-noise sweep seeds 0–4 (07/08 recipe).
The metrology namespace is disjoint from {20260912, 20260913}: study 07's
declared-split=draw-1 self-reference defect (07 §⑦.1) is fixed by construction
— a registered improvement, stated here so it can be scored as such.
Metric `val_brier` (lower) on BOTH tracks; `bound {ideal: 0.0, on_infeasible:
ack}` registered AT SCAFFOLD (before any measurement — a 09 improvement over
08's hand-computed comment). Guardrails: max_run_seconds 120, wall_seconds ≤ 60.

## §3 Ledger protocol (declared split; ALL development transactions on `primary`)

Registered order (no challenger arena number may exist before step 6):

1. **E0001** anchor_lda4 (keep expected — first valid result sets the frontier).
2. **E0002** lda_petal, **E0003** lda_sepal — controls, δ=0 era, dispositions
   descriptive (registered: both discard, sepal by a catastrophe margin).
3. k-seed fit-noise sweep (seeds 0–4): registered expectation degenerate, std
   exactly 0 — closed-form LDA. Zero seed-variance establishes ONLY zero
   algorithmic fit randomness under fixed inputs; it is never "low variance".
4. `sweeps/metrology_paired.py`: 20 group-aware paired redraws of the
   non-sealed pool (GroupShuffleSplit test_size=0.25, draw seeds 2026099101–120),
   anchor + 7 challengers + 2 controls fit on identical train rows, scored on
   identical eval rows. `sweeps/candidate_floors.py` reduces the sidecar to
   per-candidate paired floors floor_c = max(2×std(d_c), range(d_c)/2), ddof=1,
   FULL precision (`sweeps/candidate_floors.tsv`), plus the anchor's marginal
   stats for the same-sidecar comparison exhibit. Blindness clause
   (study.yaml `noise_floor_protocol`): floor_c is location-invariant; the rule
   is frozen HERE, before the sweep; metrology means are scouting only.
5. Paste into BOTH tracks: `noise_floor` block (binding challenger's series,
   `estimand: paired-comparison` hand-added) + `minimum_delta = ceil3dp(max
   over the 7 CHALLENGER floors — controls excluded)`. **Re-record consult.**
6. `sweeps/rq0_headroom.py` publishes `sweeps/rq0_headroom.tsv`: ledger h
   (numerator anchor_declared_dev = E0001) + per-candidate h_c (numerator
   anchor_metrology_mean), measurement_closed flags. Committed BEFORE Stage B.
7. Headroom branches (both pre-scripted; study.yaml predictions rows 1–2):
   **DOOR-CLOSED (h < 1, the expected case):** record
   `klein headroom ack --track primary --note "run-anyway: pre-registered
   DOOR-CLOSED branch — the scalar ledger delta is the widest challenger's
   paired floor, so h<1 was the RQ0 prior; the arena with per-candidate floors
   and the selection guard is the registered evidence; ledger-scale keeps are
   acknowledged arithmetically impossible; no re-scope, no redraw; see
   sweeps/rq0_headroom.tsv"`. **DOOR-AJAR (h ≥ 1):** no ack is possible or
   needed (klein refuses at h ≥ 1); the parade is a live contest at the scalar
   bar; no redraw, no re-registration.
8. Stage-A arena (anchor + controls, all 6 rungs) commits its sidecar,
   `arena_partitions.tsv`, and `headroom.tsv` before any challenger summary.
   Phase ack (adaptive-1).
9. **Adaptive-2 = the parade:** one run-one per challenger on the PRIMARY
   track, registry order (`families.CHALLENGERS`), 7 transactions + crash
   slack. Dispositions are judged against the anchor frontier at the scalar δ;
   per-candidate readings live in RQ0. The challenger track carries NO
   development run (verified 08 pattern; a first result on an empty track
   would fabricate a keep).

## §4 Metrology protocol (per-candidate floors — the RQ0 instrument)

Registered in full in study.yaml `noise_floor_protocol` + the sweep docstrings
(part of this plan by reference). The direction rationale is registered: a
per-candidate floor here is a CLEARANCE bar the candidate must beat — the
opposite failure mode from 07's banned per-method tie-buying floors. The scalar
ledger δ takes the WIDEST challenger floor: conservative, pre-committed,
unreachable by tuning. The enforced preflight bar (≥1×std) is weaker than this
registered 2× discipline; this plan self-binds to the 2× rule, raise-only.

## §5 Arena protocol (primary evidence for RQ1–RQ4)

`sweeps/arena.py` — geometry, seeds, twins-last quota scan, two-stage commit
order registered in its docstring (part of this plan by reference). Key rules:
10 repeats × StratifiedGroupKFold(4) over the non-sealed pool; nested
whole-group quota subsampling to nominal rungs {60,45,30,20,12,8} — **nominal
labels: realized n_actual ≤ nominal, distribution published in
arena_partitions.tsv; "trained on 60 rows" without the qualifier is banned**;
identical (train, eval) rows served to every family (rows_sha256 per cell);
per-rung δ_n = max(ceil3dp(2×sd of the anchor's 40 fold-evals), 0.005), OPEN(n)
⇔ m_n ≥ δ_n, closure labels ceiling-closed (m_n < 0.06) / fog-closed —
descriptive, never causal; UNMEASURABLE rung at >10% anchor failures; Stage A
(anchor+controls) fully committed before Stage B (challengers); crashes are
sidecar rows, honest data. RQ4 companion: `arena_aux.sidecar.tsv` records
val_logloss (eps 1e-6; clip applies to log/logit transforms only, never Brier),
val_auc, val_pr_auc, val_accuracy, val_f1, cal_intercept, cal_slope per
fold-eval; degenerate single-class eval folds record NA for ranking metrics.

## §6 Verdict quantities (frozen in `sweeps/analysis.py`; run under run_with_log)

- **Bar-1 (selection guard):** joint repeat-level sign-flip max-t over the
  FIXED 42-cell family (7 challengers × 6 rungs; never-firing placeholders for
  missing cells), full 1024 enumeration, adjusted score ≤ 0.05 (grid 1/1024;
  ≤ 51/1024). A registered guard under a symmetry assumption — never exact,
  never FWER, never population inference. **09's 42-cell max-t is not 08's
  113-cell max-t: cross-study p_guard comparison is banned.**
- **Bar-2 (the RQ1 keep rule):** Bar-1 cleared ∧ mean paired gain ≥ floor_c
  (that challenger's OWN candidate floor — the 09 innovation) ∧ rung OPEN.
- Fold-level max-t: SENSITIVITY exhibit only (40 units, MC flips, seed
  2026101500), published beside the guard, never the verdict.
- **Control test (RQ3):** one-sided worsening sign-flip for lda_sepal,
  Bonferroni 0.05/6 across measurable rungs; a miss triggers
  instrument-downgrade language for that rung.
- **RQ4 exhibit:** `rq4_saturation.tsv` — per rung/metric the share of
  fold-evals at the ceiling, beside per-family Brier/logloss means.
- No capture-ratio lane in 09 (08's RQ4 is not re-registered; shrinkage LDA is
  in the roster as a first-class challenger instead).

## §7 Sealed coda (confirmation phase) + finalize paths — both pre-registered

The frozen analysis writes `sweeps/coda_manifest.json` (branch, families, baked
train positions, position sha256, numeric bands) BEFORE the confirmation ack.
Branch rule, mechanical: **Branch A** iff ≥1 Bar-2 cell at rung 60 — winner =
largest guard t among rung-60 Bar-2 qualifiers; **Branch B** otherwise.

- Branch A: TWO sealed looks. `coda_primary` (anchor, all train rows): band
  |sealed − E0001_dev| ≤ 2δ (07/08 convention). `coda_challenger` (the winner,
  group-aware inner CV — the registered coda amendment; 08's non-group cv=3
  lawfulness argument does not port to seed 20260912): band = the winner's
  arena [p10, p90] of fold-level g = brier_anchor − brier_winner at rung 60,
  sign convention g_sealed = sealed_primary − sealed_challenger.
  `klein finalize` → label `confirmed` (protocol completion ONLY).
- Branch B: ONE sealed look (`coda_primary`, same band). The challenger seal
  STAYS SHUT by rule; `klein finalize --allow-exploratory` → label
  `exploratory`, pre-registered here as the planned Branch-B outcome: "no
  licensed challenger comparison existed", not incompleteness. Any attempt to
  build `coda_challenger` under Branch B raises.

The coda band carries no nominal coverage after selection: an in-band result is
a procedurally locked audit, never an evidence upgrade. The sealed result never
rebuilds the ladder, retunes a model, redefines a band, or changes the RQ1
verdict. "The arena is the evidence; the seal is the discipline." The spoken
sentences for every sealed outcome are pre-committed in `program.md` §Sealed
(一个字都不许改); `klein verify` output is captured to
`sweeps/klein_verify.capture.log` as the committed verify evidence.

## §8 Result-contingent endings (all four pre-scripted; findings + S8 titles)

- **(a) Nobody clears (Branch B):** headline "第三次测量：仍然没有人越过自己的
  门槛 / Third measurement: still nobody cleared their own bar." Anchor
  undisplaced at rung 60 — by default, not by victory; per-candidate claim
  permission published (h_c table); measurement-closed comparisons named
  per-candidate — never "the ruler could have seen any winner" (true only where
  floor_c ≤ anchor level).
- **(b) A challenger clears (Branch A):** headline "第三次测量：有人清了自己的
  门槛——名字与边距 / A challenger cleared its own bar — name and margin."
  Winner named with floor-relative margin + guard status (never "significant");
  sealed comparison runs; mechanism reading stays an interpretation.
- **(c) Detectable, not actionable:** headline "可探测，不可行动 / Detectable,
  not actionable." Guard-cleared cells named with their sensitivity status;
  no bar cleared → Branch B mechanics.
- **(d) Measurement-closed dominant:** headline "这一次，尺子先说话 / This
  time, the ruler speaks first." Composable with (a)–(c); the RQ0 table leads.

## §9 RQs, priors, tags

As study.yaml `research_questions` (RQ0–RQ5). Scorecard rule (07/08 law): only
`(source: uninformed)` priors are scorable — here: RQ4's fold-level saturation
rate; RQ5's measured crossover points. Everything else is tagged scouted or
derived and is EXCLUDED from the scorecard by construction.

## §10 Claims discipline

study.yaml `claims_discipline` binds findings.md, claims.lock, the report, and
every talk deliverable. 09 additions over 08: measurement-closed / claim
permission; the five claim classes (every claims.lock headline carries exactly
one); the two-headroom-numerators law; the nominal-rung qualifier; resampling
instability ≠ model variance; the empirical-lane bias–variance ban (the
decomposition lives ONLY in the simulation lane); no cross-study p_guard
comparison; "confirmed"/"exploratory" are protocol labels; no
materiality/actionability language for resolution thresholds.

## §11 Simulation lane (RQ5; fully separate from empirical claims)

`sweeps/sim_dgp.py` — DGPs, models, grid, seeds registered in its docstring
(part of this plan by reference): G1 linear-match / G2 +16 irrelevant dims /
G3 unequal rotated covariance / G4 XOR mixture; models LDA, shrinkage LDA, QDA,
L2 logit, calibrated RBF SVM, HGBT (no TabPFN); n ∈ {8,12,20,30,60,120,500};
100 registered draws per cell; fixed truth sample M=4096/DGP; analytic p*(x)
and analytic E_Y. Reported per cell: irreducible, squared probability bias,
training-set variance (ddof=0), total risk, identity check |total −
(irr+bias²+var)| ≤ 1e-9 (algebraic; asserted), MC uncertainty, effective k.
FIREWALL (study.yaml `simulation_firewall`): a plug-in decomposition of the
measured risk over these 100 draws — never the true iris DGP, never an
empirical decomposition of studies 07–09. Failed draws are recorded cells.

## §12 Feasibility + fallbacks (registered before running)

Compute: metrology 20 draws × 10 families ≈ 200 fits; arena ≈ 400 anchor/
control + 1,680 challenger fold-evals, ms-scale except TabPFN (~0.1–0.3 s,
spike PASSED bit-identical offline); parade 7 transactions; simulation 16,800
small fits — total well under one hour. TabPFN fallback (dormant):
`nystroem_logit` per the frozen map. GPC-class families are excluded at
registration (08's separability pathology). If an arena stage crashes
irrecoverably, the study finalizes on the ledger + metrology evidence with
`--allow-exploratory` and the failure published. If klein itself misbehaves on
the first-shipped-use `metric.bound` path, that is a P0 FINDING for
`framework_assessment.md` — stop and report, never hack around.
