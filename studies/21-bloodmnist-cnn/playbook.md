# Playbook — 21-bloodmnist-cnn

> Rolling state of play (keep under ~120 lines). RE-READ this file before
> choosing every candidate; refresh at every phase boundary or every 5
> experiments, whichever comes first. `program.md` is the append-only journal;
> THIS is the current map. SYNTHESIZE mines both. Swept into the next state
> commit automatically; its hash is recorded at every phase acknowledgement.

Refreshed at the close of phase `anchor` (E0001, E0002 and the Phase-0 floor).

## Current best (per track)

| Track | Exp | Metric | Config one-liner | Held since |
| --- | --- | --- | --- | --- |
| primary | E0001 | val_macro_f1 0.7189 (3-seed mean; seeds 0.733 / 0.734 / 0.689; acc 0.7794) | recipe SmallCNN, 2 conv blocks, width 32, 1,500 AdamW steps, lr 3e-3, batch 64 | anchor phase |

Keep bar (contract): `minimum_delta` 0.0438435 (item bootstrap, marginal-resplit) -> a keep
needs a seed-mean >= 0.7627. Fit noise (provenance): block-mean std 0.0472 over blocks
{10..12} {20..22} {30..32} (0.672, 0.589, 0.669); the incumbent's own block is the best of
four. Headroom h = 6.41.

## Ruled out (evidence, not opinion)

| Direction | Evidence (exp IDs) | Why it lost (one line) |
| --- | --- | --- |
| Pixel-linear softmax as a competitor | E0002 (0.6903, discard) | 0.029 below the incumbent at the same ~19k parameters and well inside the bar; P1 supported |
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

## Next-best candidates (ranked — mirror of the phase slate, see references/phase-ritual.md)

Both floors apply: the bar is +0.0438 (item noise), and a 3-seed mean also moves ~0.047 from
seed luck at this config, so a candidate within that of the incumbent is not resolved.

1. BatchNorm after each conv (normalization), anchor depth and steps otherwise. Sum 9.
2. D4 flip / rot90 augmentation on the training batch only (own RNG, batch order unchanged). Sum 9.
3. Third conv-pool-conv-pool-conv block, receptive field 8 -> 18 px, no BN. Sum 9.
4. Longer schedule only: 4,000 steps, anchor model. Sum 8.
5. P3 as its own registered cell (three blocks + BN + D4 + 4,000 steps; `--tests P3`); bundles four levers. Sum 8.
6. Width 64 (capacity only). Sum 7.

Adaptive phase budget: 6 experiments, 10,800 s. Note CPU load changes wall time a lot (the
anchor took 250-500 s per seed under load, ~20 s unloaded).
