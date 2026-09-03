# Research plan — 13-charlm-fixed-budget

## Question

Under a fixed 2000-step training budget on a character-level corpus, which
single-change training-recipe edits to a small char transformer improve held-out
validation loss by more than the measured run-to-run floor, when every checkpoint is
scored by a verifier the training script cannot touch?

The deliberate constraint is the one an ML reader asks about first: **compute is held
fixed in optimizer steps, not in wall-clock seconds**, so a candidate cannot buy an
improvement by running longer, and a CPU result and an MPS result of the same recipe
are the same experiment.

## Contract

- Kind / modality / profile: `predict` · `text` · `ml-research`
- Domain: language modeling
- Data: `bundled:tinyshakespeare/tinyshakespeare.txt.gz` — 1,115,394 characters,
  65-character vocabulary, public-domain text packaged by `karpathy/char-rnn`
- Track: `primary` (frontier)
- Metric: `val_loss` — mean next-character cross-entropy in **nats per character**,
  lower is better; `bpc` (bits per character) is printed alongside for readers who
  think in bits. Minimum delta measured at Phase 0, never guessed.
- Budget: `max_steps = 2000`, printed by the verifier out of the checkpoint and
  guarded (`steps` must equal 2000); `eval_context` must equal 128;
  `max_run_seconds = 900` is the runaway stop, not the budget.
- Verifier: `verify.py`, tolerance 0.01 nats, `artifact_key: checkpoint`. It is
  outside the mutable surface and hashed at the METHOD gate.
- Method depth: full
- Devices: `pick_device()` (MPS here, CPU in CI). `wall_seconds` is informational.

## Split policy

A contiguous-block time split over character offsets — the corpus is ordered natural
language, so the partitions are ranges and never a shuffle:

| Partition | Blocks (1024 characters each) | Characters | Share |
|---|---|---|---|
| train | 0 – 870 | 891,904 | 79.96% |
| development (validation) | 871 – 979 | 111,616 | 10.01% |
| sealed final test | 980 – 1088 | 111,874 | 10.03% |

Klein's "development" fingerprint covers train + development — the first 90% of the
corpus. Adaptive work sees only that. The sealed final tenth is opened once, after a
mandatory `--final-test --dry-run` rehearsal.

## Validation policy

Use train/development for every adaptive choice. Access the sealed test partition
once through `uv run --locked klein run-one --final-test`, after the dry-run. Label
synthesis exploratory or confirmed per `confirmation.require: [sealed]`.

## Experiment ladder

**Phase `adaptive-1` — floor, then anchor.**

1. `prepare.py` re-derives the corpus identity (1,115,394 characters, 65 distinct
   characters, the README's sha256) and hard-STOPs on any mismatch; it writes the
   block table, the split index table, the token array and the vocabulary.
2. `sweeps/noise_floor.py fit_noise` — the anchor recipe refit at five seeds on the
   same partition. Registered as `sweep:fit_noise`; recorded as `fit_noise`, which is
   provenance about the fit and is never pasted in as the keep bar.
3. `sweeps/noise_floor.py paired_floor` — for each of the ten unordered seed pairs,
   both checkpoints re-scored on the SAME validation windows and their paired mean
   difference recorded. Registered as `sweep:paired_floor`; its spread sets
   `minimum_delta` through a consult re-record, because the quantity a keep must clear
   here is a difference between two runs, not the level of one.
4. **E0001** — the identity anchor: the same recipe at a sixth seed, through the
   entrypoint, scored by the verifier. Tests **P1**.

**Phase `adaptive-2` — one recipe edit per candidate, all at 2000 steps.**

| Run | Edit (one idea) | Tests |
|---|---|---|
| E0002 | linear learning-rate warmup | P2 |
| E0003 | weight tying (output head shares the token embedding) | P3 |
| E0004 | dropout 0.1 | P4 |
| E0005 | width 128 → 256 | P5 |
| E0006 | chosen by the `adaptive-2` slate ritual from what E0002–E0005 showed | — |

Each candidate is a `keep` only if the verifier's number improves the frontier by at
least the measured floor AND the matched-compute guardrails hold. Nothing is compared
against an untuned baseline: the anchor recipe is the reference and it was tuned no
more than the candidates were.

**Phase `confirmation`.** `klein run-one --final-test --dry-run`, then one sealed
run of the selected candidate. Tests **P6**.

**Any time.** `klein replicate E0001` re-executes the anchor in a detached worktree;
agreement within the fit-noise spread is expected and a larger gap is a finding about
devices, not a failure.

## Deliverables

`findings.md` (seven sections), `claims.lock`, `referee_report.md`,
`report/index.html`, plus the first typed citation into
`knowledge/domains/ml-research/README.md` when findings close.
