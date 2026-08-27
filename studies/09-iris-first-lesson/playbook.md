# Playbook — 09-iris-first-lesson

> Rolling state of play (keep under ~120 lines). RE-READ this file before
> choosing every candidate; refresh at every phase boundary or every 5
> experiments, whichever comes first. `program.md` is the append-only journal;
> THIS is the current map. SYNTHESIZE mines both. Swept into the next state
> commit automatically; its hash is recorded at every phase acknowledgement.
> 09 deviation from 07/08, deliberate: this playbook is FILLED and refreshed
> (both predecessors carried the empty scaffold through every phase ack).

## Current best (per track)

| Track | Exp | Metric | Config one-liner | Held since |
| --- | --- | --- | --- | --- |
| primary | E0001 | val_brier 0.026409 | anchor_lda4 = LDA(svd) on 4 features | adaptive-1 (delta=0 era; h=0.330 acked DOOR-CLOSED) |
| challenger | (no development runs by design) | — | carries Branch-A sealed T2 only | — |

## Ruled out (evidence, not opinion)

| Direction | Evidence (exp IDs) | Why it lost (one line) |
| --- | --- | --- |
| gpc_rbf-class families | 08 E0018/E0022 + 160 arena crash rows | non-finite probabilities on near-separable small-n fits (separability, not scarcity) |
| new hyperparameter tournaments | registration (research_plan §1) | frozen-roster study: tuning after scouting would be selection, not measurement |
| per-method floors as TIE bars | 07 study.yaml noise_floor_protocol | a wide band could buy a tie; 09's per-candidate floors are CLEARANCE bars instead (direction registered) |

## Open hypotheses

| ID | Hypothesis | Prior | Cheapest next test |
| --- | --- | --- | --- |
| RQ0 | ledger door closed (h<1); tight-floor candidates stay open (h_c≥1) | 0.8 / per-candidate split | metrology sweep + rq0_headroom.tsv |
| RQ1 | nobody clears own bar + guard at rung 60 | high (scouted) | Stage-B arena + frozen analysis |
| RQ2 | shrinkage leads plain LDA descriptively at n≤12; fog closes low rungs | scouted | arena rungs 8–12 vs 20–60 |
| RQ3 | petal-only retains most; sepal control fires everywhere | scouted | controls in metrology + arena + worsening test |
| RQ4 | AUC saturates on most rung-60 fold-evals while Brier separates | rate: uninformed | arena_aux → rq4_saturation.tsv |
| RQ5 | G1 LDA undominated; G3 QDA overtakes; G4 flexible overtakes; crossover n's unknown | shapes: derived; crossovers: uninformed | sim_dgp full grid + decomposition identity |

## Next-best candidates (ranked — mirror of the registered ladder; the registration IS the slate)

1. adaptive-1: E0001 anchor → E0002 lda_petal → E0003 lda_sepal → k-seed sweep →
   metrology_paired → candidate_floors → paste+re-record → rq0_headroom →
   headroom branch → Stage-A arena.
2. adaptive-2: parade, registry order (lda_shrinkage, qda, logit_l2, knn_tuned,
   svm_rbf_platt, hgbt, tabpfn), all on primary.
3. adaptive-3: Stage-B arena → frozen analysis → coda_manifest → sim lane import.
4. confirmation: sealed per branch; finalize per pre-registered path; verify
   captured to sweeps/klein_verify.capture.log.

## Adaptive-1 outcomes (refreshed at the phase boundary)

- Controls: E0002 lda_petal 0.03135 discard · E0003 lda_sepal 0.156308 discard
  (positive control fired on the declared split; worsening test at adaptive-3).
- k-seed: degenerate, std exactly 0 (registered).
- Floors: binding hgbt 0.0796 → δ 0.08; paired>marginal for only 2/7
  (registered ≥5/7 prediction FALSIFIED — geometry-dependent, exhibit for RQ0).
- RQ0 permission map: OPEN shrinkage 1.57 / logit 1.36 / qda 1.29 / tabpfn 1.23;
  CLOSED svm 0.958 / knn 0.59 / hgbt 0.54; ledger DOOR-CLOSED h 0.330 (acked).
- All six rungs CLOSED (60/45/30/20 ceiling, 12/8 fog) — Bar-2 requires an OPEN
  rung, so RQ1's registered bar cannot be met unless Stage B moves m_n; the
  guard and descriptive board remain the live questions.
