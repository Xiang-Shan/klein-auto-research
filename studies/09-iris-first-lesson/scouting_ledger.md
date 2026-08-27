# Scouting ledger — 09-iris-first-lesson

Committed BEFORE the CONSULT gate is recorded (07/08 law). Everything below was
seen before any 09 measurement; findings' prior scorecard counts ONLY priors
tagged `(source: uninformed)`.

## §0 Disclosure (binds every description of this study)

This is the THIRD study on the same 100 hard-pair rows. Study 07 published every
row's values in its public ledger and sidecars. Study 08 additionally published
BOTH of its sealed values (T1 anchor 0.077176; T2 tabpfn 0.066863) and the full
arena partition row-id lists (`studies/08-iris-rematch/sweeps/arena_partitions.tsv`
publishes `row_ids` for all 240 cells). NOTHING about these flowers is unseen.
The sealed ~20 rows of THIS study (group split, seed 20260912) are PROCEDURALLY
FRESH ONLY: the protocol never conditions selection on them, but no one is blind
to them. Banned framings: 独立复现 / independent replication / blind / untouched
/ virgin. The registered protocol — seeds, per-candidate bars, guard family,
branch rules, coda bands, finalize paths — was locked before any 09 measurement;
that lock, not blindness, is the integrity claim.

## §1 Scouted items (S-entries; each is PRIOR knowledge, never 09 evidence)

- **S1 — Study 07, complete.** Anchor declared-split Brier 0.026744 (E0001);
  split-lottery mean 0.0187138 / std 0.0163144 (k=20); registered δ 0.033 =
  ceil3dp(2×std); the sub-zero keep bar 0.026744 − 0.033 = −0.006256 (printed
  in a figure legend at run time; concluded in prose only post-hoc — tutorial
  retrofit 2026-08-26; findings/claims.lock silent); four challengers all worse
  (logit 0.059078, knn7 0.045403, svm_rbf 0.056963, hgbt 0.099975); ablations
  petal 0.069452 / sepal 0.168936; sealed E0009 0.055198, ±2δ band HELD,
  sealed base rate 7/13. 07 recorded per-family paired deltas in its lottery
  sidecar but keyed δ off the anchor's MARGINAL std.
- **S2 — Study 08, complete.** Fresh-split anchor 0.029442; δ 0.029; declared
  headroom 1.015 (door ajar); keep bar 0.000442; 21-challenger parade → 18
  discard / 3 crash / 0 keep; arena 113 cells → exactly one Bar-1 clear
  (qda@n8, gain 0.07296 = 0.29×δ₈, p_guard 0.0195) that the fold-level
  sensitivity did NOT confirm (0 cells); 0 Bar-2; all six rungs closed
  (m_n/δ_n 0.45–0.53; 60/45/30/20 ceiling-closed, 12/8 fog-closed); per-rung
  anchor means 0.0167 (rung 60) → 0.1292 (rung 8); shrinkage-LDA capture ratio
  0.9751 → published 0.98 (non-causal); sealed T1 0.077176 (band HELD at 82%
  of width), T2 tabpfn 0.066863, g_sealed +0.010313 vs [−0.0160274, +0.0050326]
  → registered MISS (0.36×δ, direction favored the challenger). 08's floor was
  MARGINAL anchor-resplit by registered scope deviation.
- **S3 — Full-rule paired floors recomputed from 07's own sidecar** (during 09
  planning; the quantitative driver of RQ0's prior): floor = max(2·sd, range/2)
  per family: svm_rbf 0.024029 · logit 0.041974 · knn7 0.045469 · lda_petal
  0.051159 · hgbt 0.080287 · lda_sepal 0.093980; anchor marginal 2×std 0.0326.
  Paired exceeds marginal for 5 of 6 — neither floor type is "the sharp one"
  a priori; 09 measures its own paired floors on the 20260909 geometry.
- **S4 — A pasted bias–variance discussion (2026-08, one Claude answer about
  07/08).** Used as hypothesis fuel only (n-ladder mechanism story; feature-
  sufficiency framing; "undominated / cheapest member" superlative). Known
  defects, NOT inherited: mean≈bias / sd≈variance table read as "dominance";
  an unverified `sd 0.074→0.126` (suspected mislabeling of the rung MEANS
  0.0687→0.1292); the −0.006256 keep bar misattributed to Bayes risk (klein's
  arithmetic uses ideal = 0); "pairwise spreads wider" quoted without the
  registered "5 of 6 families" qualifier.
- **S5 — The 20260828 CAS talk (deck v3) and its claims maps** (numbers.md,
  numbers.py dual-lock, citations A1–A17). Spoken-form authority for zh
  wording; no 09 evidence.
- **S6 — Klein framework @ e99a89a** (v1.3 detection-limit machinery: bound /
  headroom / estimand / ack; verified test baseline 306 passed / 6 skipped).
  09 is the first shipped study to arm `metric.bound`.
- **S7 — TabPFN v2 availability/determinism spike, 2026-08-27, pre-consult.**
  breast_cancer rows (never iris), 60 train / 20 eval, seed 20260909,
  HF_HUB_OFFLINE=1, pinned V2 ckpt (…zk73skhh.ckpt): predict_proba sha256
  b452f7d074f5d4266061f698087577f20b8f5a8fd21c0044cb8faa9236dadb17 —
  bit-identical across two separate processes; ~0.9 s wall each. TabPFN live;
  fallback `nystroem_logit` dormant (declared before outcomes).
- **S8 — 09 plan red-team (2026-08-27).** Findings adopted into registration:
  parade on PRIMARY (a first result on an empty track auto-keeps); δ maximizes
  over challengers only; claims.lock authored after the seal; bound declared at
  scaffold; repo-wide worktree discipline; uv extras rule; group-aware coda
  entry (08's non-group cv=3 lawfulness argument does not port); nominal-rung
  qualifier; 1/1024 guard grid; no cross-study p_guard comparison.
- **S9 — Study 07/08 design briefs** in the presentation task's reference/
  (historical design context only).
- **S10 — Pre-gate staging-smoke contamination + seed retirement (2026-08-27).**
  A build-agent smoke, staging train.py OUTSIDE the ledger and before any gate
  ack, scored development AND sealed Briers for every family under candidate
  split seed 20260909. The orchestrator did not read the logs; they were
  deleted, though four truncated dev-Brier values embedded in model FILENAMES
  crossed the screen during deletion. Handling, on the 07 seed-42 precedent:
  seed 20260909 (inner 20260910) RETIRED; the declared split re-registered as
  seed 20260912 (inner 20260913) BEFORE the consult ack; a registered
  agent-smoke law added (method card §6: subagent smokes run on synthetic
  frames only). Every number seen belongs to the retired namespace and is
  quoted nowhere. This entry exists so the event is disclosure, not a secret.

## §2 Priors and tags (mirror of study.yaml; scoreable = uninformed ONLY)

| RQ | Prior (one line) | Tag | Scoreable |
| --- | --- | --- | --- |
| RQ0 | ledger h<1 (P~0.8); h_c<1 for wide-floor families, ≥1 for svm-class | scouting-study-07 (measured, S3) | no |
| RQ1 | nobody clears own bar + guard at rung 60 | scouted 07/08 (S1,S2); per-candidate reading derived | no |
| RQ2 | risk+instability grow as n falls; fog outpaces gaps; shrinkage leads at n≤12 | scouting-study-08 (measured, S2) | no |
| RQ3 | petal retains most; sepal fires everywhere | scouting-study-07 (measured, S1) | no |
| RQ4 | ranking saturates while Brier separates; the fold-level saturation RATE | derived (S1/S2 AUC scouting); rate **uninformed** | rate only |
| RQ5 | G1/G2/G3/G4 textbook shapes; the measured crossover n's | derived (theory); crossovers **uninformed** | crossovers only |

## §3 Fresh-seed declaration

All 09 namespaces are new and disjoint from every 07/08 seed (inventory in
research_plan §2), inside the 2**32−1 domain, and the metrology namespace is
disjoint from {20260912, 20260913} — study 07's declared-split=draw-1
self-reference defect is fixed by construction (registered improvement).
