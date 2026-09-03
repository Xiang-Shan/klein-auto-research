---
type: scouting-ledger
study: "13-charlm-fixed-budget"
status: closed        # open | closed (closed at the CONSULT gate; later entries are a gate re-record)
---

# Scouting ledger — 13-charlm-fixed-budget

> Everything looked at BEFORE the CONSULT gate, so that no registered prediction can
> pretend to a surprise it already knew. Committed before `klein gate record consult`,
> which hashes this file into the consult record; an edit afterwards fails
> `klein verify` until the gate is re-recorded with a reason.

## §0 Disclosure

Four things were looked at before this contract was written, and all four are
below. Two of them are ordinary provenance (the bundled corpus's own README; the
engine's verifier plumbing). The other two are MEASUREMENTS on the anchor recipe —
a timing sweep that chose the compute budget, and three full 2000-step anchor runs
that confirmed the recipe trains stably and fixed the order of magnitude of its
validation loss. Those two are why `max_steps` is 2000 rather than a guess, and why
the RQ2 prior about devices is labelled `(source: scouted)`.

**No candidate edit was ever run before the gate.** Warmup, weight tying, dropout
and width — the levers P2 through P5 register — were never executed, never timed
and never scored at design time. The anchor was, because a budget nobody has timed
is not a budget.

## Entries

| S# | Date | What was looked at | What was seen | Why it is not evidence | Decision |
|---|---|---|---|---|---|
| S1 | 2026-09-02 | `datasets/tinyshakespeare/README.md` and `DATA_LICENSE` (the bundled corpus, prepared by another agent) | 1,115,394 characters, 65 distinct characters, sha256 of the decompressed text pinned in the README; the README records nanoGPT's own contiguous 1,003,854 / 111,540 convention | a README is documentation, not a measurement this study made; `prepare.py` re-derives the count, the vocabulary and the digest and hard-STOPs on any mismatch | adopt the contiguous-block convention; make the character count and vocabulary size the study's identity anchor |
| S2 | 2026-09-03 | timing sweep of four char-transformer sizes, CPU and MPS, 25–60 steps each, batches drawn from the raw corpus with no partitioning | 4-layer / 4-head / 128-wide / 128-context at batch 32 = 0.824M parameters, 29.4 ms/step warm on CPU and 8.0 ms/step on MPS; the same shape at 256 wide = 3.222M parameters, 62.2 ms/step CPU and 15.3 ms/step MPS | a step-timing measurement carries no validation loss and adjudicates nothing; it only prices the budget | fix the budget at 2000 optimizer steps: ~59 s on this machine's CPU and ~16 s on its MPS for the anchor, ~124 s / ~31 s for the widest candidate — inside the brief's "about three minutes on CPU" for every configuration the study will run |
| S3 | 2026-09-03 | three full 2000-step anchor runs (seeds 1, 2, 3) on MPS and one (seed 1) on CPU, using the same contiguous 80/10/10 block arithmetic the contract now declares | val_loss 1.567907 / 1.553969 / 1.567601 nats on MPS; 1.569609 nats on CPU at seed 1; the recipe trains stably at a constant learning rate of 3e-3 with no warmup and no divergence | these runs used a throwaway script, not the study's entrypoint, wrote no manifest and were never notarized; the floor sweep re-measures the spread from scratch through `sweeps/noise_floor.py`, and every scored number in this study comes from the verifier | keep the anchor recipe as written; expect a fit-noise standard deviation near 0.008 nats, which is what makes an integer-count-of-floors prediction grammar worth registering; label the RQ2 device prior `(source: scouted)` |
| S4 | 2026-09-03 | the engine's verifier path (`kleinlib/workflow.py` `_run_declared_verifier`, `kleinlib/transaction.py`), the repository `.gitignore`, and `kleinlib/decision.py`'s incumbent rule | the verifier child inherits no `KLEIN_EVALUATION_KIND`; `*.pt` is both gitignored and an unsafe payload suffix, so a checkpoint is hashed into the manifest and stays local; the development incumbent is the last `keep` manifest on the development partition | reading the engine is not measuring the study | make the checkpoint carry its own `evaluation_kind` and `split_fingerprint` so the verifier can re-derive the right partition and refuse a mismatch; let the verifier read the incumbent from the run manifests rather than from a constant in the mutable surface |

## Retirements

Directions or values scouted and dropped before the contract, with the reason, so the
next study does not re-scout them:

- **A `split-lottery` (marginal-resplit) floor.** Considered and dropped before the
  contract: this study never re-draws its split. The partitions are contiguous ranges
  of an ordered corpus fixed by the contract, and every candidate is measured on
  exactly the same validation characters, so the spread of a re-drawn validation block
  is not the quantity a keep has to clear. The floor that matches the question is the
  spread of the DIFFERENCE between two independently seeded runs of the same recipe on
  the same windows — a paired-comparison estimand — and that is what Phase 0 measures.
- **Sampled validation batches.** The common `eval_iters = 200 random batches` habit
  was dropped before the contract: it makes the training script's number and the
  verifier's number disagree for a reason that has nothing to do with the checkpoint.
  Both sides compute the same deterministic full-coverage sweep instead, which is what
  lets the verifier tolerance be 0.01 nats rather than a fit-noise-sized fudge.

## Prior-scorecard eligibility

Every research-question prior that rests on a value seen in this ledger is labelled
`(source: scouted)` in `study.yaml` — not `uninformed`, not `knowledge/…` — and is
excluded from the knowledge-vs-uninformed scorecard in findings §⑥. That is exactly
one prior: RQ2's device claim, which rests on S3. RQ1 and RQ3 are `(source:
uninformed)`: nothing in this ledger says what warmup, tying, dropout or width do at
this budget, because none of them was ever run.
