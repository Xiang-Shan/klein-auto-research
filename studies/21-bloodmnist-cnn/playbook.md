# Playbook — 21-bloodmnist-cnn

> Rolling state of play (keep under ~120 lines). RE-READ this file before
> choosing every candidate; refresh at every phase boundary or every 5
> experiments, whichever comes first. `program.md` is the append-only journal;
> THIS is the current map. SYNTHESIZE mines both. Swept into the next state
> commit automatically; its hash is recorded at every phase acknowledgement.

Refreshed after E0004 (adaptive phase).

## Current best (per track)

| Track | Exp | Metric | Config one-liner | Held since |
| --- | --- | --- | --- | --- |
| primary | E0004 | val_macro_f1 0.8960 (3-seed mean; seeds 0.909 / 0.880 / 0.899; std 0.0145; acc 0.9087) | E0001 recipe + BatchNorm2d after each conv + running stats recomputed on the training set before eval | E0004 |

Keep bar `minimum_delta` 0.0438435 (item bootstrap): a next keep needs >= 0.9398. Fit noise
(anchor config) 0.047 block std; the BN config's own seed std is 0.0145. h = 2.4.

## Ruled out (evidence, not opinion)

| Direction | Evidence (exp IDs) | Why it lost (one line) |
| --- | --- | --- |
| Pixel-linear softmax as a competitor | E0002 (0.6903, discard) | 0.029 below the incumbent at the same ~19k parameters and well inside the bar; P1 supported |
| Default BN running averages at eval (momentum 0.1) at constant lr 3e-3 | E0003 (0.3005, discard) | eval-mode inference broken (batch-stat acc 0.92 vs eval acc 0.25 off-loop); fixed by recomputing the stats on train data (E0004). A bug, not a dead lever |
| Third block alone at 1,500 steps (E0006) | 0.9286, discard, +0.0326 | sub-bar by 0.0112; larger than seed spread; NOT ruled out, rides inside P3 |
| D4 augmentation alone at 1,500 steps, 2 blocks | E0005 (0.8893, discard, -0.0067) | not resolved at this budget: margin inside the incumbent seed std 0.0145 |
| "The recipe CNN clears 0.85" (P2) | E0001 (0.7189) | refuted: 1,500 constant-lr steps leave the 2-block net at 0.72 with large seed spread |

## Open hypotheses

| ID | Hypothesis | Prior | Cheapest next test |
| --- | --- | --- | --- |
| H1 | The anchor is optimisation-limited and unstable (per-seed 0.49-0.73, loss still falling and noisy); BatchNorm stabilises it and lifts the mean | 0.65 | BN after each conv, nothing else |
| H2 | D4 augmentation helps (no preferred orientation in smears) | 0.55 | flip / rot90 on the train batch, own RNG |
| H3 | The 8-px receptive field blocks shape classes (3 / 4 / 5 confusion) and a third block lifts them | 0.5 | add a third conv-pool block |
| H4 | A longer schedule alone helps less than the bar (RQ3) | 0.6 | 4,000 steps, anchor model |
| H5 | Class 0 (recall 0.26, called class 3) is the largest single loss; any lever must lift it | 0.6 | read per-class recall in aux_metrics after each candidate |
| H6 | P3's bundle (3 blocks + BN + D4 + 4,000 steps) reaches 0.93 | 0.35 given the anchor at 0.72 | its own registered cell, after single levers |

## Next-best candidates (ranked; incumbent E0004, bar +0.0438 -> 0.9398)

1. (E0005 done: D4 on E0004 = 0.8893, -0.0067, inside seed spread: NOT RESOLVED at this budget, not ruled out; revisit inside P3.)
2. (E0006 done: third block on E0004 = 0.9286 +/- 0.0079, +0.0326 vs E0004, 0.0112 short of the bar: discard; real in direction (every seed above every E0004 seed), not a keep.)
3. 4,000 steps only on E0004 (schedule). Sum 8.
4. P3 as its own registered cell (3 blocks + BN + D4 + 4,000 steps, `--tests P3`), last. Sum 8.
5. Width 64: dropped for budget (6 experiments, 3 used by E0004's close).
