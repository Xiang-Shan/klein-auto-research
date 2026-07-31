# Program — 06-hurricane-gqls-returnlevels

This is the living lab notebook. `study.yaml` is the machine contract;
`study_state.json`, `events.jsonl`, and `runs/E####/manifest.json` are generated audit
state and must not be hand-edited.

## Goal and track contract

- Goal: On the 30 most-damaging US hurricanes (Pielke-Landsea 1998, normalized 1995 USD), does a from-scratch gQLS reproduce Adjieteh (2024) Table 6.9 within the published reporting resolution; does its robustness advantage over MLE survive the thesis's 10x contamination and leave-top-k-out stress; and does that advantage carry into per-event return levels - the thesis's own declared future work?
- Tracks: `reproduction` (mean_abs_param_deviation over the 36 published Table-6.9
  parameters, lower; max-deviation guardrails stop a broken cell hiding) and
  `decision` (return_level_instability_pct, lower; `w_pvalue ≥ 0.10` guardrail —
  "among models that FIT, which gives the most stable 1-in-100"). Deltas
  PROVISIONAL (0.005 resolution / 1.0pp) until the adaptive-1 floor sweeps.
- Sealed evidence = pre-registered third-party PUBLISHED truth: reproduction →
  the full Table 6.10 grid (original + modified; adaptive touches Table 6.9
  only); decision → the thesis's exact 10× modification. Results are exploratory
  until those sealed runs; small deltas without uncertainty are never decisive.

## Data and split

- Source: data_hub:hurricane_top30_pl1998 (+ bundled datasets/ copy — bare-clone
  reproducible). n=30, split kind none; fitting on log-dollars (×1e9).
- Identity gate: six Table-6.8 statistics exact under Hazen quantiles + ddof=1
  (they certify this is the thesis's sample — the AOML Table 8 top-30 with its
  three pre-1925 supplemental storms, NOT extRemes::damage's true-1925-95 top-30
  and NOT the annual Rsum series; see the bundled dataset README).
- Gate 1 records the prepared-data SHA-256.

## Workflow

1. `uv run --locked klein gate record consult --study . --acknowledged-by <name>`
2. Prepare data and write a `Decision: GO` data card; record the DATA gate.
3. Write the method card; record the METHOD gate.
4. Commit gate evidence, switch to `experiments/06-hurricane-gqls-returnlevels`, and run
   `uv run --locked klein preflight --study .`.
5. Edit `train.py`, then
   `uv run --locked klein run-one --study . --track reproduction --description ...`.

Every candidate is committed before execution. Discards and crashes remain resolvable
commits; the evidence transaction then restores `train.py` to the pre-candidate
base commit.

## Decisions (append-only)

- 2026-07-31 — schema-v2 study scaffolded; gates pending.
- 2026-07-31 — CONSULT fast-path taken (approved cross-session plan answers all
  six questions; the thesis PDF and the data acceptance gate were pre-verified
  at plan stage: all six Table-6.8 statistics ≤3.3e-5 under Hazen+ddof1, MLE
  lognormal anchors 22.8002/0.8339 clean and 22.8769/1.0975 contaminated exact).
  Two-track design with the decision track's w_pvalue anti-degeneracy guardrail;
  sealed = published third-party truth (Table 6.10 grid; exact 10× modification).
  RQ1-RQ6 + eight predictions in study.yaml. Acknowledged by Xiang.
- 2026-07-31 — F2 lesson from study 05 applied AT SCAFFOLD: the `decision` track
  was added to study.yaml post-scaffold, so `final_holdout_access` was topped up
  with a generator-shape zero entry immediately, before any gate or run (the
  framework fix — load_state top-up from the contract — remains queued in study
  05's findings §⑦).
- 2026-07-31 — DATA gate recorded (GO-WITH-CAUTIONS; clean-room audit 7/7
  mechanized clean; identity gate live-verified: 8 statistics + 4 MLE anchors,
  max dev 3.3e-5, prep deterministic sha a0e6a5d9…). Standing rules adopted:
  (a) only `log_damage_usd` is consumed; `rank` is a target bijection (Spearman
  −1.0) and must never be a covariate; (b) Hazen is DESCRIPTIVE-only — the
  thesis's defined fitting convention is inverted_cdf, and the difference
  (0.0084 vs 0.0020 mean dev) exceeds both the 0.005 resolution and, for Hazen,
  the 0.02 guardrail; (c) every return level is FAMILY-CONDITIONAL extrapolation
  (fitted lognormal 1-in-100 = $55.5bn < the largest observed event $72.3bn;
  support tops out at p=0.9667) — say so alongside every figure; (d) σ̂ carries
  a ±25% bootstrap band at n=30 — instability numbers are ordering devices on a
  fixed sample, never population claims; (e) sealed evidence = independent
  PUBLISHED TARGETS, not independent data — confirmation wording is
  "implementation fidelity + within-sample robustness", never out-of-sample
  generalization; (f) the 1900–1995 exchangeability rests wholly on the
  Pielke-Landsea normalization — inherited assumption, stated not established.
  Audit previews (to be formalized on-ledger): MLE-lognormal 1-in-100 moves
  −25.7/−36.5/−44.6% under leave-top-1/2/3 and +99.4% under the exact 10×
  modification.
- 2026-07-31 — adaptive-1 COMPLETE. E0001 discard 0.00309 under the REGISTERED
  hazen default: the identity gate passed (12 quantities ≤3.3e-5 — this IS the
  thesis's sample) and the single-cell params landed inside 0.005, but
  max_abs_w_deviation 0.494 breached the 0.10 guardrail — an honest discard that
  forces the convention question the thesis itself defines (F̂⁻¹(p)=X₍⌈np⌉₎ =
  inverted_cdf, ch. 2). Floors measured: numerical 8.8e-17 (≈0 IS the finding);
  convention sweep k=5 (inverted_cdf 0.002754 / hazen 0.009303 / weibull
  0.021252 / median_unbiased 0.012036 / normal_unbiased 0.011024 — spread 0.0185
  = 3.7× resolution, a SPECIFICATION spread, not folded into the delta);
  reproduction minimum_delta = 0.005 (resolution-governed). Decision floor:
  paired log-RL bootstrap SE 3.461, essentially all from the log-Cauchy arm
  (3.59 alone) — RQ5's punchline as metrology (at n=30 the log-Cauchy 1-in-100
  is not estimable to useful precision); resolution (1) adopted: minimum_delta
  stays 1.0pp as a within-sample ORDERING DEVICE with the band stated; never
  quietly shrunk. Ladder amendment recorded: adaptive-2 = grid-hazen /
  grid-inverted_cdf / gof_redundancy / oqls_mle_arms (the k-sensitivity content
  moves to an off-ledger measurement table + E0005 aux — the convention sweep
  already covers convention sensitivity).
- 2026-07-31 — Metric-registry note: both primaries are custom scalar names
  (simulation task type, evaluate_scalar path, study-03 precedent
  `mean_final_gap`); directions declared explicitly in the contract; guardrail
  values (w_pvalue, max_abs_* deviations) must be PRINTED by train.py via extra
  (F1 lesson from study 05 — the runner reads the printed block).
## Phase slates

At every phase start, run the slate ritual (references/phase-ritual.md):
propose 4-6 falsifiable candidates, score novelty / testability / expected
information 1-3, record the table and the chosen candidate here, and mirror
the ranked survivors into playbook.md "Next-best candidates".

### Phase <id> slate

| # | Candidate (falsifiable) | Novelty 1-3 | Testable 1-3 | Info 1-3 | Sum |
| --- | --- | --- | --- | --- | --- |
