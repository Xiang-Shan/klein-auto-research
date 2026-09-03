---
type: method-card
domain: "language modeling"
profile: "ml-research"
status: complete
concepts: [causal-transformer, fixed-step-budget, checkpoint-verification, weight-tying, lr-warmup, dropout]
related: [13-charlm-fixed-budget]
refs_verified: true   # set true ONLY after every reference below is verified
triad:                 # the Theory + Papers + Practice contract — self-asserted, gate-checked
  theory: true         # §2 has the notation table and the four load-bearing equations
  papers: true         # references.yaml: 10 rows, all verified 2026-09-03
  practice: true       # §3 is the plan model.py / train.py realize, and verify.py is written
---

# Method card — a small causal char transformer under a fixed step budget, graded by a separate verifier

> Gate 2 (METHOD). Pedagogy for an unfamiliar or frontier method, written BEFORE
> modeling. Protocol: `.claude/skills/klein/references/method-gate-protocol.md`.

## 1. Intuition (for a practitioner)

An ML researcher already knows what a causal transformer is. What this card has to
build intuition for is the *measurement*, because that is the part this study is
actually about.

**The model, in one paragraph.** A character-level language model is a lookup table
plus a mixer. Every one of the 65 characters gets a 128-dimensional vector; a stack of
four blocks lets each position mix in information from the positions before it (never
after — that is what "causal" means); a final linear layer turns each mixed vector back
into a score for each of the 65 characters. Train it to put probability on the
character that actually came next. The loss it reports is the average surprise, in
nats, of the next character given everything before it in the window. Two reference
levels fix the scale, both computed at the DATA gate: a model that has learned nothing
scores ln 65 = 4.174387 nats, and a model that has learned only which characters are
common scores 3.307264. Anything below that is the model actually using context.

**The budget, in one paragraph.** The honest way to compare training recipes is at
matched compute, and the honest unit of compute is *optimizer steps*, not seconds. A
step is the same amount of arithmetic on a laptop CPU and on an accelerator; a second
is not. So every candidate here runs for exactly 2000 steps of 32 windows of 128
characters, and the guardrail that enforces it does not read `train.py` — it reads the
step count out of the saved checkpoint. That is the difference between a budget and a
promise.

**The verifier, in one paragraph — the idea this study exists to show.** Almost every
training script in the world computes its own validation loss and prints it. That
number is then the thing everyone believes. But a training script has a thousand ways
to be quietly wrong about it — an evaluation batch drawn from the training range, a
target sequence that was never shifted, a checkpoint saved one step later than the loss
was measured, a dropout mask left on at evaluation. **So this study separates the
searcher from the checker.** `train.py` trains and saves a checkpoint. A second,
immutable program, `verify.py`, is then run by the notary in its own process: it loads
that checkpoint from disk, asks the contract (not the training script) which characters
are the validation partition, rebuilds the model from the checkpoint's own config with
its own independent implementation of the architecture, and recomputes the loss. **The
checker's number is the one the study uses.** The trainer's number is recorded beside
it, and if the two disagree by more than 0.01 nats the run is a crash — not a result to
be argued about. The analogy an experimentalist will recognize: the person who ran the
assay does not also certify the standard.

## 2. Math core

| Symbol | Meaning |
|---|---|
| $V$ | vocabulary size, 65 characters |
| $T$ | context length, 128 characters (a contract constant, guarded as `eval_context`) |
| $d$ | model width `n_embd` (128 for the anchor, 256 for the width candidate) |
| $L, H$ | number of blocks (4) and attention heads (4); head dimension $d/H$ |
| $x_{1:n}$ | the corpus as character ids; $x_t \in \{0,\dots,V-1\}$ |
| $\theta$ | all model parameters (824,320 for the anchor) |
| $p_\theta(\cdot \mid x_{<t})$ | the model's next-character distribution |
| $\mathcal{D}$ | the development partition's character range, $[891904, 1003520)$ |
| $S$ | the step budget, 2000 |
| $B$ | batch size in windows, 32 |
| $\sigma_{\text{fit}}$ | the seed-to-seed standard deviation of `val_loss` (Phase 0) |
| $\delta$ | `minimum_delta`, set from the paired floor (Phase 0) |

**(1) The objective — mean next-character cross-entropy, in nats.** For a set of
windows $W$, each a start offset $s$ with $s+T \le \max \mathcal{D}$,

$$ \mathcal{L}(\theta) \;=\; -\frac{1}{|W|\,T} \sum_{s \in W} \sum_{k=0}^{T-1} \log p_\theta\!\left(x_{s+k+1} \,\middle|\, x_{s},\dots,x_{s+k}\right). $$

The metric `val_loss` is exactly this with $W$ the **complete, non-overlapping** tiling
of the evaluation range: $|W| = \lfloor (|\mathcal{D}|-1)/T \rfloor$ windows, no
sampling and no seed. Divide by $\ln 2$ for bits per character. A uniform model gives
$\mathcal{L} = \ln V = 4.174387$.

**(2) One block (pre-norm).** With $\mathrm{LN}$ layer normalization, $\mathrm{MHA}$
causal multi-head attention and $\mathrm{GELU}$ the activation,

$$ z \;=\; u + \mathrm{MHA}\!\left(\mathrm{LN}(u)\right), \qquad u' \;=\; z + W_2\,\mathrm{GELU}\!\left(W_1\,\mathrm{LN}(z)\right), \quad W_1 \in \mathbb{R}^{4d \times d},\; W_2 \in \mathbb{R}^{d \times 4d}. $$

The normalization sits *inside* the residual branch. That placement is the whole
content of P2's prior: Xiong et al. (2020) show Pre-LN transformers have well-behaved
gradients at initialization and, unlike Post-LN, do not need learning-rate warmup to
train stably.

**(3) Weight tying.** The output layer is $\ell = E^\top h$ with $E \in
\mathbb{R}^{V \times d}$ the token-embedding matrix, instead of an independent
$W_{\text{out}}$. It removes $Vd$ parameters and forces the input and output
representations of a character to coincide. At $V = 65$, $d = 128$ that is
$8{,}320$ of $824{,}320$ parameters — **1.0%**. Press & Wolf's gains were measured at
word-level vocabularies of tens of thousands, where the same term is most of the model.

**(4) The keep rule, in floors.** A candidate improves the frontier only if

$$ \mathcal{L}_{\text{incumbent}} - \mathcal{L}_{\text{candidate}} \;\ge\; \delta, \qquad \delta \;=\; \max\!\left(2\,\hat{\sigma}_{\text{paired}},\; \tfrac{1}{2}\,\mathrm{range}_{\text{paired}}\right), $$

where the paired quantities are the spread of $\mathcal{L}_i - \mathcal{L}_j$ over the
ten unordered pairs of five identically-configured runs that differ only in seed,
scored on the *same* windows. Every registered prediction is written as an integer
count of $\delta$, fixed before $\delta$ was known.

## 3. Minimal from-scratch implementation plan

This is the plan `model.py` and `train.py` realize, and `verify.py` independently
re-implements the scoring half of.

```text
# ---- data (prepare.py, already run at the DATA gate) --------------------
tokens   = uint8 array of the whole corpus            # data/prepared/tokens.bin
blocks   = 1089 rows of (block_id, start_char, n_chars, ...)   # prepared.csv
train/dev/sealed = contract_split(study.yaml)          # contiguous ranges

# ---- model (model.py) ---------------------------------------------------
class Block:          # pre-norm; LayerNorm -> causal MHA -> residual
                      #            LayerNorm -> 4x MLP with GELU -> residual
class CharTransformer:
    tok_emb  : Embedding(V, d)
    pos_emb  : Parameter(1, T, d)          # learned absolute positions
    blocks   : L x Block
    ln_f     : LayerNorm(d)
    head     : Linear(d, V, bias=False)    # head.weight = tok_emb.weight if tied
build(config) is called on CPU under the run's torch seed, THEN moved to the
device, so the initial weights are identical on CPU and on MPS.

# ---- training (train.py) ------------------------------------------------
for step in range(S):                      # S = 2000, the budget
    lr = base_lr * min(1, (step+1)/warmup) if warmup else base_lr
    offsets = rng.integers(train_lo, train_hi - T - 1, size=B)   # streamed
    x = tokens[o : o+T]  ;  y = tokens[o+1 : o+1+T]              # index-shuffle
    loss = cross_entropy(model(x), y)      # AdamW(lr, 0.9/0.99, wd 0.1)
save {config, state_dict, steps, evaluation_kind, split_fingerprint,
      reported_val_loss, seed, lr, batch_size, warmup_steps} -> models/E####.pt
print "checkpoint: models/E####.pt"  and  "artifact: models/E####.pt"

# ---- checking (verify.py, run by the notary in a SEPARATE process) ------
ckpt = torch.load(KLEIN_ARTIFACT, weights_only=True)
assert ckpt.config.block_size == 128 and ckpt.config.vocab_size == 65
X_fit, X_eval, _, y_eval = load_partition(kind)        # prints split_fingerprint
assert split_fingerprint(X_fit, X_eval) == ckpt.split_fingerprint
model = CharTransformer(**ckpt.config)                 # verify.py's OWN class
model.load_state_dict(ckpt.state_dict, strict=True)
val_loss = mean cross-entropy over the complete window tiling of X_eval
print the canonical block + steps + eval_context + delta_in_floors + anchor_z
```

Helpers this leans on: `kleinlib.data.load_partition` / `split_fingerprint` (the
contract's partitions and the fingerprint the notary checks — war story 8),
`kleinlib.eval.evaluate_scalar` (the canonical printed block),
`kleinlib.torch_device.pick_device` (MPS → CUDA → CPU, `KLEIN_DEVICE` overrides),
`kleinlib.sweep.SweepRunner` (both Phase-0 measurement sweeps and the harness
controls). Batching is a streamed index shuffle straight out of a numpy array — no
`DataLoader`, no `TensorDataset` (war story 2).

**Three deliberate design choices, and what each costs.**

1. *The checker re-implements the architecture instead of importing `model.py`.* Cost:
   duplicated code, and the architecture family becomes part of the contract — a
   candidate that changes the module tree makes an artifact the checker cannot load,
   and the run crashes. Benefit: the checker cannot be edited by the search. Two
   implementations that agree are evidence; one implementation compared with itself is
   not. The same reasoning applies to the loss sweep, which `train.py` also writes out
   independently.
2. *The evaluation is a complete tiling, not sampled batches.* Cost: 128 of each
   partition's characters are read as context but never predicted (99.89% coverage),
   and the first character of each window is predicted from nothing. Benefit: the
   trainer's number and the checker's number are the *same deterministic quantity*, so
   the verifier tolerance can be 0.01 nats — guarding float and device drift — rather
   than a fit-noise-sized fudge that would hide a real error.
3. *The budget is steps, not seconds.* Cost: a wider model gets the same number of
   steps and therefore more FLOPs, which is *not* the compute-optimal frontier of
   Kaplan et al. / Hoffmann et al. Benefit: the comparison is device-independent and
   reproducible in CI on a CPU. This is stated wherever P5 is reported: width is bought
   here with extra arithmetic per step, not with extra steps.

## 4. When it pays / when it doesn't

The regime this study sits in: 892k training characters, a 824k-parameter model, 2000
steps × 32 × 128 = 8.19M training characters seen — about **9.2 passes** over the train
partition.

| Regime | Data size | Signal | Verdict for each lever |
|---|---|---|---|
| Tiny corpus, tiny model, few steps (here) | ~1M chars | dense, local | **Width** pays if capacity binds — but at 9 epochs a wider model also overfits sooner, and it gets no extra steps to exploit the capacity (`kaplan2020` says grow the model at fixed *compute*; `hoffmann2022` says grow tokens with it, and this study grows neither). Genuinely uncertain. |
| | | | **Warmup** should not pay: the blocks are Pre-LN, and `xiong2020` is explicit that Pre-LN removes the instability warmup exists to fix. If it pays here it means the constant learning rate is too aggressive for the first few dozen steps, which would be worth knowing. |
| | | | **Weight tying** should be neutral: it touches 1.0% of the parameters at a 65-symbol vocabulary, where `press2017`'s mechanism (sharing a large, sparsely-updated embedding table) barely applies. |
| | | | **Dropout** should not pay at this budget: `srivastava2014` buys generalization by making each step noisier, and when the binding constraint is the number of steps rather than the amount of data, that trade runs the wrong way. The counter-case is real though — 9 epochs is enough to memorize — and it is the live hypothesis H3 in the playbook. |
| Word-level LM, large vocabulary | ≥100M tokens | sparse, long-range | Weight tying pays clearly (`press2017`); warmup pays for Post-LN stacks; dropout pays once epochs ≫ 1. None of that transfers automatically to the row above, which is the point of measuring. |
| Anything, one seed | — | — | Never trust it. `picard2021` and `bouthillier2021` are why this study measures a floor before it compares anything. |

**Falsifiable priors this study will test** (mirrored in `study.yaml:predictions`):

- **P1** the anchor recipe at a sixth seed lands within 2 fit-noise standard deviations
  of the five-seed mean — i.e. the recipe is reproducible and the floor is usable.
- **P2** warmup improves `val_loss` by ≥ 1 floor. *Card's expectation: refuted*, on
  `xiong2020`.
- **P3** weight tying stays within 1 floor of the anchor. *Card's expectation:
  supported*, on the 1.0% parameter-share arithmetic in §2(3).
- **P4** dropout 0.1 is ≥ 1 floor WORSE. *Card's expectation: supported but the least
  safe of the four* — H3 says the opposite and 9.2 epochs is enough for it to be right.
- **P5** doubling width improves by ≥ 1 floor. *Card's expectation: genuinely
  uncertain* — capacity may not be the binding constraint at 2000 steps.
- **P6** the sealed final tenth scores within 2 fit-noise standard deviations of the
  development incumbent.

## 5. Verified references

Every row was checked on 2026-09-03 against the arXiv abstract page, the publisher page
or the repository page — not quoted from memory. Full entries, with the reason each is
load-bearing, are in `references.yaml`.

| Reference | Where | Verified? |
|---|---|---|
| Vaswani et al. 2017, *Attention Is All You Need* | NeurIPS 30 · arXiv:1706.03762 | ✅ |
| Loshchilov & Hutter 2019, *Decoupled Weight Decay Regularization* | ICLR 2019 · arXiv:1711.05101 | ✅ |
| Xiong et al. 2020, *On Layer Normalization in the Transformer Architecture* | ICML 2020 · arXiv:2002.04745 | ✅ |
| Press & Wolf 2017, *Using the Output Embedding to Improve Language Models* | EACL 2017 · arXiv:1608.05859 | ✅ |
| Srivastava et al. 2014, *Dropout: A Simple Way to Prevent Neural Networks from Overfitting* | JMLR 15(56), 1929–1958 | ✅ |
| Kaplan et al. 2020, *Scaling Laws for Neural Language Models* | arXiv:2001.08361 | ✅ |
| Hoffmann et al. 2022, *Training Compute-Optimal Large Language Models* | arXiv:2203.15556 | ✅ |
| Picard 2021, *Torch.manual_seed(3407) is all you need* | arXiv:2109.08203 | ✅ |
| Bouthillier et al. 2021, *Accounting for Variance in Machine Learning Benchmarks* | MLSys 2021 · arXiv:2103.03098 | ✅ |
| Karpathy, *nanoGPT* (`data/shakespeare_char`) | github.com/karpathy/nanoGPT, MIT | ✅ |

Nothing on this card is cited from memory and nothing is marked UNVERIFIED.
