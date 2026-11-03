---
type: method-card
domain: "medical image classification (hematology microscopy)"
profile: "cv"
status: complete
concepts: [softmax-cross-entropy, convolution, weight-sharing, translation-equivariance, receptive-field, pooling, batch-normalization, d4-augmentation, macro-f1, seed-array, item-bootstrap, fit-noise-vs-marginal-resplit]
related: [knowledge/method_cards/cnn-image-classification.md, 21-bloodmnist-cnn]
refs_verified: true    # 19 rows, each read against a fetched record 2026-11-03; klein refs verify: 18 resolved, 0 failed, 1 url-only
triad:                 # the Theory + Papers + Practice contract — self-asserted, gate-checked
  theory: true         # §2: notation table + five load-bearing display equations
  papers: true         # refs_verified is true (references.yaml, 19 rows)
  practice: true       # §3: the plan model.py / train.py realize (the anchor runs as written); the P1 / P3 diffs and the macro-F1 floor are specified
---

# Method card — from a linear softmax on pixels to a small CNN on BloodMNIST, judged against seed noise and item noise

> Gate 2 (METHOD). Pedagogy written BEFORE modeling. Protocol:
> `.claude/skills/klein/references/method-gate-protocol.md`. Instantiates the seed card
> `knowledge/method_cards/cnn-image-classification.md` for this study. Nothing on this
> card was trained or scored on the study's data; every number below is either from
> a cited paper, counted from `model.py`, or arithmetic on published split sizes.
>
> **Reader.** An ML practitioner who trains small CNNs but has not had to prove an
> improvement is larger than its seed and item noise.

## 1. Intuition (for a practitioner)

**The images.** BloodMNIST is 17,092 photographs of single normal blood cells
(neutrophils, eosinophils, basophils, lymphocytes, monocytes, immature granulocytes,
erythroblasts, platelets), taken on one analyser (CellaVision DM96) in one hospital
laboratory (Hospital Clinic of Barcelona, 2015–2019) from May Grünwald-Giemsa-stained
smears (`ref:acevedo2020`). MedMNIST v2 centre-cropped each 360 × 363 image to 200 × 200
and shrank it to **28 × 28 RGB** (`ref:yang2023medmnist`). Each image is one cell,
roughly centred. The classes differ in three kinds of cue: **colour** (eosinophil
granules stain orange-red, basophil granules dark purple), **size** (a platelet is a
small fragment, a monocyte is large), and **nucleus shape** (a segmented neutrophil,
the kidney-shaped nucleus of a metamyelocyte inside the immature-granulocyte class, the
folded monocyte nucleus, the round lymphocyte or erythroblast nucleus). Keep those
three in mind: the whole ladder of this study is about which model can read which cue.

**A linear softmax on pixels is eight stencils.** Flatten the 3 × 28 × 28 image into
2,352 numbers; each class gets one weight per number; the score is a dot product. So
each class owns one *template image*, and a cell is called whatever template it
overlaps best. Because the cells are centred, a template can do real work: "orange
blob in the middle" is an eosinophil stencil, "small dark dot, lots of background" a
platelet stencil. What a stencil cannot do is see the same thing in a different place
or orientation, or express a conjunction ("dark nucleus AND lobed AND pale
cytoplasm"). That is the honest baseline (P1): it measures how much of the task is
colour and size at fixed positions.

**A convolution is a stencil you slide.** If you have smoothed a time series with a
rolling window, or run a Sobel edge detector over a photo, you have used a
convolution with hand-picked weights. A CNN learns those small weights (here 3 × 3
pixels) and applies the *same* filter at every position — **weight sharing**. Two
consequences. The parameter count stops depending on the image size. And the layer is
**translation-equivariant**: shift the cell two pixels and the feature map shifts two
pixels; nothing has to be relearned for the new position. Stacking conv →
nonlinearity → conv lets later filters combine earlier ones (edges → granules →
nucleus outline) — the conjunctions a stencil cannot express. **Pooling** summarises
a neighbourhood (max-pool 2 × 2 keeps the strongest response), which buys tolerance to
small shifts; **global average pooling** at the end turns "where is each pattern" into
"how much of each pattern is there".

**The sharpest fact about this study's first comparison.** Counted from `model.py`:
the linear softmax has **18,824** parameters and the anchor `SmallCNN` has **19,912**.
Same budget, to within 6%. So P1 versus P2 is not "small model versus big model"; it is
*the same number of weights spent two ways*. The CNN reuses each weight at up to 784
positions and spends about 228× more arithmetic per image (≈ 4.29 M multiply-adds
versus 18,816). Whatever gap appears is the architecture — weight sharing,
nonlinearity, pooling — not the parameter budget.

**What the anchor can and cannot see.** `SmallCNN` is conv3×3 → ReLU → max-pool 2 →
conv3×3 → ReLU → global average pool → linear. Its last conv units each look at an
**8 × 8-pixel** window of a 28-pixel image (receptive field: 3 → 4 after the pool → 8).
Then global pooling averages them. So the anchor is a *bag of local 8 × 8 textures*:
it knows how much of the frame is orange granule, dark nucleus edge, pale cytoplasm —
which captures colour and the nucleus-to-cytoplasm ratio well — but not the
arrangement of those textures across the whole cell. Nucleus *shape* at this
resolution spans more than 8 pixels. A third conv–pool block raises the receptive field
to about **18 pixels** (a conv-pool-conv-pool-conv stack), roughly the whole cell.
That is why depth is a real lever here (P3), not just "more capacity".

**Batch normalization is z-scoring inside the network.** You standardise features
before fitting a GLM so no column dominates the optimizer. Batch normalization does
that to every channel of every layer, per mini-batch, then lets the network learn a
scale and shift back. The original paper explained it as reducing "internal covariate
shift" (`ref:ioffe2015`); a later careful study found that distributional stability
"has little to do with" why it works and that it "makes the optimization landscape
significantly smoother" (`ref:santurkar2018`). The practical reading for a **fixed step
budget**: BN lets each step make more progress, so at 4,000 steps it can matter even
if it would not at 40,000. At evaluation the batch statistics are replaced by running
averages (`model.eval()`, which `train.py` already calls).

**Augmentation is a prior you state by showing examples.** A blood smear has no "up".
A cell rotated by 90° or mirrored is the same cell type. The survey definition: an
augmentation is *safe* when it is likely to preserve the label — "rotations and flips
are generally safe on ImageNet challenges such as cat versus dog, but not safe for
digit recognition tasks such as 6 versus 9" (`ref:shorten2019`). Blood cells are the
cat-versus-dog case. The eight symmetries of the square (four rotations by 90°, each
with or without a mirror — the group called D4) are therefore free labelled data: the
network is told "these eight images have the same answer" instead of having to learn
it from eight times more cells. At 28 pixels these eight transforms are *exact pixel
permutations* — no interpolation blur, unlike a 17° rotation. The alternative is to
build the symmetry into the layers (group-equivariant CNNs, `ref:cohen2016`; applied to
pathology because "histopathology images are inherently symmetric under rotation and
reflection", `ref:veeling2018`). This study teaches by augmentation; it names the
architectural route and does not run it.

**Accuracy versus macro-F1.** Accuracy weights each class by how common it is;
macro-F1 computes an F1 per class and averages them with equal weight. Here the
largest class is 19.48% of the images (neutrophils) and the smallest 7.10%
(lymphocytes) (`ref:acevedo2020`, Table 1) — a 2.7 : 1 ratio, moderate. So the two
numbers will be close, but macro-F1 punishes a model that buys accuracy on the big
classes by giving up the 7% ones. The study's primary is macro-F1 (the CV profile's
rule); accuracy is printed beside it because MedMNIST reports accuracy, and P5 reads
it.

**The two noises — the part this study is really about.** Run the same recipe with a
different seed and the score moves: different initial weights, different batch order.
That is **fit noise** — the instability of your *fitting procedure*, like refitting a
non-convex model from a different random start. Now hold the predictions fixed and ask
a different question: had the 1,712 development images been a different draw of 1,712
cells from the same smears, how much would the score move? That is **item noise** —
the precision of the *ruler*, like the standard error of a claim frequency estimated
from 1,712 policies. They answer different questions, and a seed array only fixes one
of them: averaging 3 seeds shrinks fit noise by about √3 but does nothing to item
noise, because all three seeds are scored on the same 1,712 images. For scale: an
accuracy near 0.90 measured on 1,712 images has a binomial standard error of about
0.0073 — so a "+0.006 improvement" from one seed is not a result, it is the ruler's
own wobble. This is why the study's keep bar is the **item bootstrap** of the anchor's
development macro-F1 (estimand `marginal-resplit`) and the seed-block spread is
recorded as **`fit_noise`**, never as the bar (`ref:bouthillier2021`,
`ref:varoquaux2022`, `ref:picard2021`).

## 2. Math core

| Symbol | Meaning |
|---|---|
| $x \in [0,1]^{C\times H\times W}$ | one image; here $C = 3$, $H = W = 28$ (uint8 pixels divided by 255 in `train.py`) |
| $y \in \{0,\dots,K-1\}$ | its class; $K = 8$ (index map in `ref:medmnist_info`: 3 = immature granulocytes) |
| $f_\theta(x) \in \mathbb{R}^K$ | the network's logits; $\theta$ all weights |
| $p = \mathrm{softmax}(f_\theta(x))$ | predicted class probabilities, $p_k = e^{f_k} / \sum_j e^{f_j}$ |
| $B$ | mini-batch size (64 in the recipe) |
| $\mathcal{G} = D_4$ | the 8 symmetries of the square: rotations by $0^\circ, 90^\circ, 180^\circ, 270^\circ$, each with or without a horizontal flip |
| $W \in \mathbb{R}^{C'\times C\times k\times k}$, $b \in \mathbb{R}^{C'}$ | a convolution's filter bank ($C'$ filters of size $k\times k$) and biases |
| $\mu_\mathcal{B}, \sigma^2_\mathcal{B}$ | per-channel mean and variance over a mini-batch (and spatial positions) |
| $\gamma, \beta$ | batch-norm's learned per-channel scale and shift; $\epsilon$ a small constant |
| $TP_k, FP_k, FN_k$ | true positives, false positives, false negatives of class $k$ in the confusion table $M$ ($M_{tp}$ = items of true class $t$ predicted $p$) |
| $\pi_k$ | class $k$'s share of the evaluated items |
| $m(\cdot)$ | the metric (macro-F1 or accuracy) as a function of a set of (true, predicted) pairs |
| $s = 1..S$ | seeds of one seed array ($S = 3$: seeds 0, 1, 2) |
| $D_\text{dev}$, $n$ | the development items ($n = 1{,}712$); $D^*_b$ a bootstrap re-draw, $b = 1..B_\text{boot}$ |
| $\delta$ | `minimum_delta`, the keep bar |

**(1) The training objective — softmax cross-entropy, with augmentation as a prior.**

$$
\mathcal{L}(\theta) \;=\; -\frac{1}{B}\sum_{i=1}^{B} \log \mathrm{softmax}\!\big(f_\theta(g_i \cdot x_i)\big)_{y_i},
\qquad g_i \sim \mathrm{Uniform}(D_4),
\qquad \frac{\partial \mathcal{L}_i}{\partial f} = p_i - e_{y_i}.
$$

Without augmentation $g_i$ is the identity. With it, the network minimises the loss
averaged over each cell's eight-member orbit — it is penalised for any answer that
depends on orientation. This is safe only because $y(g\cdot x) = y(x)$ for every
$g \in D_4$ on a blood smear. The gradient with respect to the logits is "predicted
minus one-hot", which is why the loss never saturates for a confident wrong answer.
(The optimizer is AdamW, `ref:loshchilov2019`: Adam's adaptive step on
$\partial\mathcal{L}/\partial\theta$ plus a separate shrink $\theta \leftarrow \theta - \eta\lambda\theta$,
not an L2 term inside the gradient.)

**(2) Convolution: weight sharing and translation equivariance.**

$$
(W \star x)[c', i, j] \;=\; b_{c'} + \sum_{c=1}^{C}\sum_{u,v=0}^{k-1} W[c', c, u, v]\, x[c,\, i+u,\, j+v],
\qquad
\#\theta_\text{conv} = C' C k^2 + C' \;\;\text{(no } H, W\text{)},
\qquad
\#\theta_\text{linear} = K\,C H W + K .
$$

The same $W$ is used at every $(i,j)$; translating the input translates the output,
$(W \star T_t x) = T_t (W \star x)$ for integer shifts $t$ away from the border. For the
anchor: $3\cdot32\cdot9 + 32 = 896$, $32\cdot64\cdot9 + 64 = 18{,}496$, head
$64\cdot8+8 = 520$ — total 19,912; the linear softmax is $8\cdot2352 + 8 = 18{,}824$.
Receptive field grows as $r \leftarrow r + (k-1)\,j$, $j \leftarrow j\cdot\text{stride}$
per layer: $1 \to 3 \to 4 \to 8$ for the anchor, $\to 10 \to 18$ with a third pooled
block. Max-pooling ($\max$ over a $2\times2$ window, stride 2) and global average pooling
($\frac{1}{HW}\sum_{i,j}$) are what turn equivariance into (approximate) invariance.

**(3) Batch normalization (per channel, per mini-batch).**

$$
\hat z = \frac{z - \mu_\mathcal{B}}{\sqrt{\sigma^2_\mathcal{B} + \epsilon}},
\qquad
\mathrm{BN}(z) = \gamma\, \hat z + \beta ;
\qquad \text{at evaluation } \mu_\mathcal{B}, \sigma^2_\mathcal{B} \to \text{running averages.}
$$

The implementer's two traps: put the network in `eval()` before scoring (or the
development batch's own statistics leak into its predictions and the scores depend on
batch composition), and remember that the conv bias before a BN layer is redundant.

**(4) Macro-F1 versus accuracy, both read off the confusion table.**

$$
F1_k = \frac{2\,TP_k}{2\,TP_k + FP_k + FN_k},
\qquad
\text{macro-F1} = \frac{1}{K}\sum_{k=1}^{K} F1_k,
\qquad
\text{accuracy} = \frac{\sum_k TP_k}{n} = \sum_{k=1}^{K} \pi_k\,\mathrm{recall}_k .
$$

Accuracy is a $\pi$-weighted average of per-class recalls; macro-F1 is an unweighted
average of per-class F1s and also charges false positives *into* a class. Two facts an
implementer needs: macro-F1 is **not a mean over items** (it is a ratio of sums per
class), so any bootstrap of it must recompute it on each re-draw; and both are fully
determined by $M$, so a re-draw of items is the same thing as a multinomial re-draw of
$M$'s cells.

**(5) Two floors, two questions.**

$$
\bar m = \frac{1}{S}\sum_{s=1}^{S} m\big(\hat y^{(s)};\, D_\text{dev}\big),\quad
\mathrm{Var}_\text{seed}(\bar m) \approx \frac{\sigma^2_\text{fit}}{S}
\qquad\Big|\qquad
m^*_b = m\big(\hat y;\, D^*_b\big),\;\; D^*_b \sim \text{re-draw } n \text{ items of } D_\text{dev} \text{ with replacement},
$$

$$
\delta \;\ge\; \max\!\big(2\,\mathrm{sd}_b(m^*_b),\; \tfrac{1}{2}\mathrm{range}_b(m^*_b)\big),
\qquad
\mathrm{SE}_\text{item}(\text{accuracy}) \approx \sqrt{a(1-a)/n}.
$$

The left side is **fit noise**: how much the seed-array mean moves when the seeds are
re-drawn (the seed blocks of Phase 0; recorded as `fit_noise`). The right side is the
**item bootstrap** (`ref:efron1979`): how much the same predictions' score moves when
the evaluation set is re-drawn — estimand `marginal-resplit`, the keep bar. Two
numerical consequences follow from the formulas alone. At $n = 1{,}712$ the binomial
standard error of accuracy is 0.0086 at $a = 0.85$, 0.0073 at $a = 0.90$ and 0.0053 at
$a = 0.95$. And with $B_\text{boot} = 1000$ re-draws the expected range of roughly
normal bootstrap means is about $6.5$ standard deviations, so the $\tfrac12$range term,
about $3.2\,\mathrm{sd}$, is the one that binds — the bar will be roughly three item
standard errors, not two.

## 3. Minimal from-scratch implementation plan

The anchor is already written and is not duplicated here: **`model.py`** holds
`SmallCNN` (the §2 eq. 2 stack) and **`train.py`** is the loop. What `train.py`
realizes, step by step, and the kleinlib helper each step leans on:

1. **Partition from the contract** — `kleinlib.data.load_items()` returns the fit and
   evaluation ids for the official split (`kind: predefined`) and prints the
   `split_fingerprint:` the notary compares with the DATA gate's. No literal seed
   chooses any item.
2. **Seed** — `kleinlib.dl.seed_everything(KLEIN_SEED)`; the notary runs seeds 0, 1, 2
   as one seed array and decides on the mean of every printed key.
3. **Device** — `kleinlib.torch_device.pick_device()`.
4. **Batches** — `kleinlib.torch_loop.iterate_minibatches(n, 64, shuffle=True,
   generator=rng)`: streamed index-shuffle batching, never a `DataLoader` over a
   `TensorDataset` (the MPS constant-prediction war story).
5. **Step budget** — a `while step < steps` loop with AdamW; the budget is optimizer
   steps (1,500 for the anchor), so CPU and accelerator runs are comparable;
   `kleinlib.dl.report_usage(steps=…)` records it.
6. **Score** — softmax probabilities on the evaluation items into
   `kleinlib.eval_multiclass.evaluate_multiclass(...)`, which refuses non-finite or
   non-normalised probabilities and collapsed (single-class) predictions, prints
   `val_macro_f1` (primary), `val_accuracy`, `val_balanced_accuracy`,
   `val_top5_accuracy`, `val_mlogloss`, `val_ece` and `wall_seconds`, and pins the
   confusion table as `tables/confusion_<exp>.tsv`.
7. `kleinlib.encoders` is **not used**: images have no categorical columns.

**The weight-sharing idea at numpy level** (for understanding — `nn.Conv2d` is what runs):

```python
def conv2d(x, W, b):                       # x: (C, H+2, W+2) zero-padded; W: (C', C, 3, 3)
    Cp, C, k, _ = W.shape
    H, Wd = x.shape[1] - k + 1, x.shape[2] - k + 1
    out = np.empty((Cp, H, Wd))
    for i in range(H):
        for j in range(Wd):                # the SAME W at every (i, j): weight sharing
            out[:, i, j] = np.tensordot(W, x[:, i:i + k, j:j + k], axes=3) + b
    return out
```

**The registered cells, as diffs to the surface (one idea per candidate):**

- **P1 — linear softmax.** In `train.py`, replace `SmallCNN(...)` with
  `nn.Sequential(nn.Flatten(), nn.Linear(3 * 28 * 28, 8))`; everything else (steps,
  batch, AdamW, lr, weight decay, seeds) unchanged — "trained like the anchor".
- **P3 — three blocks + BN + D4 + 4,000 steps.** In `model.py`, blocks of
  conv3×3 → BatchNorm2d → ReLU → MaxPool2 (pool after the first two), then GAP and a
  linear head. In `train.py`, `steps = 4000` and D4 augmentation applied **to the
  training batch only, after the split, inside the loop** (never in `prepare.py`):

```python
aug_rng = np.random.default_rng(SEED + 10_000)   # its OWN generator: batch order stays
                                                 # identical to the anchor's at the same seed
def d4(xb):                                      # xb: (B, C, H, W) training batch
    k = aug_rng.integers(0, 4, len(xb)); flip = aug_rng.random(len(xb)) < 0.5
    out = xb.clone()
    for r in (1, 2, 3):
        m = torch.from_numpy(k == r)
        if m.any(): out[m] = torch.rot90(out[m], r, dims=(2, 3))   # exact pixel permutation
    m = torch.from_numpy(flip)
    if m.any(): out[m] = out[m].flip(3)
    return out
```

  P3 bundles four levers (depth, BN, augmentation, schedule). If it holds, it does not
  say which lever paid; the adaptive slate should give at least depth+BN and D4 their
  own single-lever candidates so the bundle can be decomposed.

**The keep bar — item bootstrap of macro-F1** (the Phase-0 floor sweep). Macro-F1 is not
a mean over items, so `kleinlib.metrology.item_bootstrap` — which re-takes the *mean* of
per-item scores — would, fed per-item correctness, measure **accuracy's** floor, not
macro-F1's. Recompute the metric on every re-draw instead. Because a re-draw of items
is a multinomial re-draw of the confusion table's cells, the pinned table suffices:

```python
def macro_f1(M):                                  # M[t, p] = count; same rule as evaluate_multiclass
    tp = np.diag(M).astype(float); fp = M.sum(0) - tp; fn = M.sum(1) - tp
    f1 = np.divide(2 * tp, 2 * tp + fp + fn, out=np.zeros_like(tp), where=(2 * tp + fp + fn) > 0)
    return f1[M.sum(1) > 0].mean()

def item_bootstrap_macro_f1(M, n_boot=1000, seed=0):
    rng = np.random.default_rng(seed); n = int(M.sum())
    return np.array([macro_f1(rng.multinomial(n, (M / n).ravel()).reshape(M.shape))
                     for _ in range(n_boot)])   # -> sidecar rows; klein noise-floor
                                                #    --recipe item-bootstrap --estimand marginal-resplit
```

Bootstrapping each seed's table separately and taking the mean of the three standard
deviations is a slight over-estimate of the seed-mean's item noise (the standard
deviation of an average is at most the average of the standard deviations), so the bar
errs conservative. **One thing to fix before the floor sweep:** as written, all three
seeds of one array call `evaluate_multiclass(exp_id=EXPERIMENT_ID, ...)`, so they write
the same path `tables/confusion_<exp>.tsv` and the table that survives to be pinned is
the last seed's. If the floor needs every seed's table, the table name must carry the
seed.

**Practice leg.** The anchor is runnable now (`KLEIN_SMOKE=1` for the shape check, then
`klein run-one`); the P1 and P3 cells are one-file diffs specified above; the floor
computation is specified to the line. That is the plan `train.py` realizes.

## 4. When it pays / when it doesn't

The CV doctrine anchor (`references/profiles/cv.md` §3): split by the unit that would
leak, audit near-duplicates, macro-F1 under imbalance with the confusion table pinned,
deep runs as seed arrays with the floor measured on aggregates, augmentation inside
the loop, and for MedMNIST keep the official splits and *say whether they are
patient-grouped*.

**They are not, and cannot be.** MedMNIST v2 says only "We split the source dataset
with a ratio of 7:1:2 into training, validation and test set" (`ref:yang2023medmnist`).
The source dataset saved every image "with a random identification number to remove
any link and traceability to the patient data" (`ref:acevedo2020`). So cells from the
same smear, patient and staining run almost certainly sit on both sides of every
partition, and no audit can reconstruct the grouping. Every number this study reports
— and every MedMNIST reference number — answers "new cells from the same smears, the
same analyser, the same lab", not "a new patient" and not "another hospital"
(`ref:varoquaux2022` names repeated measures across train and test as a leakage route).
The P5 comparison is like-for-like on this point; neither number speaks to transfer.

| Regime | Data size | Signal | Verdict |
|---|---|---|---|
| Linear softmax on raw pixels | ~1.2 × 10⁴ training images, 2,352 inputs | strong colour/size cues at fixed (centred) positions; nucleus shape needs conjunctions | **pays partly** — reads colour and size; cannot read shape. auto-sklearn's *nonlinear* search over the same flattened pixels reached 0.878 test accuracy (`ref:yang2023medmnist` Table 3), a loose ceiling for any pixel-input non-convolutional model |
| Two-block CNN, GAP, 8-px receptive field (the anchor) | same; 1,500 steps × 64 ≈ 8.0 epochs | local texture + area fractions | **pays over linear at matched parameters**; capped by the 8-px window on shape-defined classes |
| Three blocks + BN + D4 augmentation | same; 4,000 steps ≈ 21.4 epochs | whole-cell shape (≈ 18-px receptive field); exact rotation/flip symmetry | **likely pays** — every lever addresses a named limit of the anchor; BN and D4 are cheapest per step |
| MedMNIST ResNet-18 (28) reference | up to 100 epochs ≈ 1.2 × 10⁶ images seen (12.5× the anchor, 4.7× P3), ≈ 9,400 steps at batch 128, lr decay, early stopping on validation | — | **0.958 test accuracy** (Table 3); 224-px input adds only 0.005 (0.963), so resolution is not what separates a CPU-budget CNN from the reference — training budget and network are the candidates |
| ≤ 10³ images (not this study) | | | pretrained features + a linear head usually win; a scratch CNN overfits (`ref:doerrich2025` finds efficient training schemes and foundation-model features competitive with end-to-end training) |
| Same-smear leakage (this study, unavoidable) | | | in-distribution scores are optimistic for new patients; nothing here measures that |
| Site / stain / scanner shift (not this study) | | | in-distribution accuracy says little; test on the shifted site |

**Where the floor bites.** Development is 1,712 images. From §2 eq. 5, the item standard
error of macro-F1 near 0.90 is about 0.008 (a crude delta-method estimate using the
source's class shares: $\sqrt{0.9\cdot0.1/K^2 \cdot \sum_k 1/n_k} \approx 0.0079$ with
expected class counts $n_k$ between ≈ 122 and ≈ 333), and the bar is about three of
those. So the study's resolving power is ≈ 0.02–0.03 macro-F1: big architectural steps
(linear → CNN, 8-px → 18-px receptive field) should clear it; a width change or a
learning-rate tweak should not. Headroom $h = (1 - \text{incumbent})/\delta$ falls below 1
once the incumbent passes $1 - \delta$ (≈ 0.97 for $\delta \approx 0.03$) — then no keep is
arithmetically possible, and the study should say so rather than run more candidates.

### What I expect for each registered prediction (and why)

Written before any run; probabilities are the scholar's, for the §⑥ prior scorecard.

- **P1 — linear softmax, dev macro-F1 ∈ [0.50, 0.85].** *Expect: holds* (≈ 0.8);
  central guess ≈ 0.72. Centred cells make colour/size stencils work for eosinophils,
  basophils, platelets and erythroblasts; neutrophil / immature-granulocyte / monocyte /
  lymphocyte separation needs nucleus-shape conjunctions a stencil cannot form. Above
  0.85 would put a linear model within reach of auto-sklearn's nonlinear 0.878 (test
  accuracy — a different metric and partition, so only a sanity bracket). Below 0.50
  would point at an optimisation bug (8 epochs of AdamW on [0, 1] pixels should
  converge a linear model).
- **P2 — anchor SmallCNN, dev macro-F1 ≥ 0.85.** *Expect: lean holds* (≈ 0.6); central
  ≈ 0.87, plausible 0.80–0.92. A 20k-parameter bag-of-8-px-textures at 8 epochs and a
  constant learning rate reads colour, granularity and nucleus/cytoplasm ratio, but is
  blind to whole-nucleus shape; a miss would show up as immature-granulocyte /
  neutrophil / monocyte confusion.
- **P3 — three blocks + BN + D4 + 4,000 steps, dev macro-F1 ≥ 0.93.** *Expect: coin
  flip* (≈ 0.5); central ≈ 0.93, plausible 0.89–0.96. Every lever fixes a named anchor
  limit (receptive field, steps per unit of progress, symmetry, epochs), but it still
  sees 4.7× fewer images than the ResNet-18 recipe with no learning-rate decay, and the
  last iterate of a constant-rate run is noisier than an annealed one.
- **P4 — incumbent, sealed-test macro-F1 ≥ 0.90.** *Expect: holds* (≈ 0.75). The
  official partitions are random draws from one pool, so development and test are
  exchangeable; test item noise is ≈ 0.005 at n = 3,421; selection optimism from
  picking the best of ≤ 8 candidates on 1,712 items is of order one development
  standard error (≈ 0.005–0.015); the sealed fit uses train + development (+14% images).
  Holds if the development incumbent reaches ≈ 0.92.
- **P5 — incumbent, sealed-test accuracy < 0.958.** *Expect: holds* (≈ 0.8). **The
  threshold is confirmed** (§5): ResNet-18 (28), BloodMNIST, ACC 0.958 in Table 3. The
  ResNet recipe trains far longer with decay and early stopping. Read the outcome with
  its noise: the binomial standard error of 0.958 on 3,421 test images is ≈ 0.0034, so a
  gap under ≈ 0.01 is "indistinguishable from ResNet-18 (28)", whatever the arithmetic
  verdict. Two recipe differences to disclose beside it: MedMNIST trains on train only
  with validation early stopping and reports "the mean value of at least 3 trials";
  this study's sealed run refits on train + development and reports a 3-seed mean.

### Falsifiable priors this card stakes (beyond P1–P5)

`study.yaml` already carries the registered `predictions:` P1–P5, and the schema-3
contract refuses `predictions_to_falsify:` beside them ("give predictions: or
predictions_to_falsify:, never both"), so these card priors are **not** mirrored into
the contract; P1–P5 are the mirrored register. The lead may register any of K1–K5 as
P6+ (a consult re-record) before E0001; otherwise SYNTHESIZE holds them to account from
this card.

- **K1 — floor size.** The item-bootstrap keep bar on the anchor's development
  macro-F1 (`max(2·sd, range/2)`, 1,000 re-draws) lands in **[0.015, 0.040] macro-F1**.
  Falsified by a bar outside that interval.
- **K2 — which noise is bigger.** The block-to-block standard deviation of the anchor's
  3-seed-mean macro-F1 (`fit_noise`) is **smaller** than the item-bootstrap standard
  deviation: ratio fit/item **< 1.0**. Falsified by a ratio ≥ 1.0.
- **K3 — metric gap.** At the anchor, `val_accuracy − val_macro_f1` (seed means) lies in
  **[0.000, 0.030]**. Falsified by a negative gap or one above 0.030.
- **K4 — hardest class.** In the anchor's pinned confusion table, class 3 (immature
  granulocytes) has the **lowest or second-lowest recall** of the eight. Falsified if
  two or more classes have lower recall.
- **K5 — headroom.** Headroom stays **h ≥ 1** through the whole adaptive phase (the
  incumbent's development macro-F1 never exceeds 1 − δ). Falsified by any recorded
  h < 1.

### Notes raised at METHOD for the lead (contract text, not predictions)

1. **P5's 0.958 is correct** — no change needed before any run.
2. **RQ1's prior says auto-sklearn reached "near 0.88 test accuracy with feature
   engineering".** The number is right (0.878) but the paper says the opposite about the
   inputs: "We flatten the images into one dimension, and provide reshaped
   one-dimensional data ... for auto-sklearn to fit" — no hand-made features; the search
   (2 h / 4 h / 6 h by dataset scale; 4 h for a 17k-image set) ran over scikit-learn's
   models and preprocessors.
3. **RQ4's prior reads "stays below 0.958 (about 0.65)".** 0.65 is inconsistent with P4
   (≥ 0.90 test macro-F1) and with the rest of the contract; it looks like a typo.
4. The floor-sweep macro-F1 and per-seed confusion-table points in §3.

## 5. Verified references

Every row was checked on 2026-11-03 against a fetched record (publisher full text via
Europe PMC, Crossref, arXiv abstract pages, PMLR / MLSys / NeurIPS proceedings pages,
the repository file), then resolved mechanically by `klein refs verify --record`:
**19 references, 0 failed, 18 recorded** (one url-only row, `medmnist_info`, checked by a
reader). export.arxiv.org rate-limited this machine (HTTP 429) on the day, so four
arXiv-only rows (Ioffe, Kingma, Bouthillier, Picard) carry arXiv's own DataCite DOI
(10.48550/arXiv.ID) and resolved through OpenAlex. Loshchilov & Hutter is cited as
ICLR 2019; arXiv's first posting is 2017 (the verifier's year warning, expected). See
`references.yaml` for locators and `verified_by` detail.

**What MedMNIST v2 actually says (Table 3, "Benchmark on each dataset of MedMNIST2D in
metrics of AUC and ACC", BloodMNIST columns — read from the published full text,
PMC9852451, and cross-checked against the arXiv LaTeX source):**

| Method | AUC | ACC |
|---|---|---|
| ResNet-18 (28) | 0.998 | **0.958** |
| ResNet-18 (224) | 0.998 | 0.963 |
| ResNet-50 (28) | 0.997 | 0.956 |
| ResNet-50 (224) | 0.997 | 0.950 |
| auto-sklearn | 0.984 | **0.878** |
| AutoKeras | 0.998 | 0.961 |
| Google AutoML Vision | 0.998 | 0.966 |

"We calculate the mean value of at least 3 trials for each method on each dataset."
Split (Table 2): 17,092 images, 11,959 / 1,712 / 3,421. ResNet recipe: cross-entropy,
batch 128, Adam lr 0.001, 100 epochs, lr × 0.1 after epochs 50 and 75, early stopping on
validation. **P5's 0.958 is confirmed; RQ1's "about 0.88" is confirmed as 0.878.**

| Reference | Where | Verified? |
|---|---|---|
| Yang et al. 2023, MedMNIST v2 — a large-scale lightweight benchmark for 2D and 3D biomedical image classification | *Scientific Data* 10:41; doi:10.1038/s41597-022-01721-8; arXiv:2110.14795 | ✅ |
| Acevedo et al. 2020, A dataset of microscopic peripheral blood cell images for development of automatic recognition systems | *Data in Brief* 30:105474; doi:10.1016/j.dib.2020.105474 | ✅ |
| Acevedo et al. 2019, Recognition of peripheral blood cell images using convolutional neural networks | *Comput. Methods Programs Biomed.* 180:105020; doi:10.1016/j.cmpb.2019.105020 | ✅ |
| LeCun, Bottou, Bengio & Haffner 1998, Gradient-based learning applied to document recognition | *Proc. IEEE* 86(11):2278–2324; doi:10.1109/5.726791 | ✅ |
| He, Zhang, Ren & Sun 2016, Deep residual learning for image recognition | CVPR 2016, 770–778; doi:10.1109/CVPR.2016.90; arXiv:1512.03385 | ✅ |
| Ioffe & Szegedy 2015, Batch normalization | ICML 2015, PMLR 37:448–456; arXiv:1502.03167 | ✅ |
| Santurkar, Tsipras, Ilyas & Madry 2018, How does batch normalization help optimization? | NeurIPS 2018; arXiv:1805.11604 | ✅ |
| Kingma & Ba 2015, Adam | ICLR 2015; arXiv:1412.6980 | ✅ |
| Loshchilov & Hutter 2019, Decoupled weight decay regularization | ICLR 2019; arXiv:1711.05101 | ✅ |
| Shorten & Khoshgoftaar 2019, A survey on image data augmentation for deep learning | *J. Big Data* 6:60; doi:10.1186/s40537-019-0197-0 | ✅ |
| Cohen & Welling 2016, Group equivariant convolutional networks | ICML 2016, PMLR 48:2990–2999; arXiv:1602.07576 | ✅ |
| Veeling, Linmans, Winkens, Cohen & Welling 2018, Rotation equivariant CNNs for digital pathology | MICCAI 2018, LNCS 11071:210–218; doi:10.1007/978-3-030-00934-2_24; arXiv:1806.03962 | ✅ |
| Bouthillier et al. 2021, Accounting for variance in machine learning benchmarks | MLSys 2021; arXiv:2103.03098 | ✅ |
| Picard 2021, Torch.manual_seed(3407) is all you need | arXiv:2109.08203 (preprint) | ✅ |
| Varoquaux & Cheplygina 2022, Machine learning for medical imaging: methodological failures and recommendations for the future | *npj Digit. Med.* 5:48; doi:10.1038/s41746-022-00592-y | ✅ |
| Efron 1979, Bootstrap methods: another look at the jackknife | *Ann. Statist.* 7(1):1–26; doi:10.1214/aos/1176344552 | ✅ |
| Guo, Pleiss, Sun & Weinberger 2017, On calibration of modern neural networks | ICML 2017, PMLR 70:1321–1330; arXiv:1706.04599 | ✅ |
| Doerrich, Di Salvo, Brockmann & Ledig 2025, Rethinking model prototyping through the MedMNIST+ dataset collection | *Sci. Rep.* 15:7669; doi:10.1038/s41598-025-92156-9; arXiv:2404.15786 | ✅ |
| MedMNIST package metadata, `medmnist/info.py` (label index map, split sizes) | github.com/MedMNIST/MedMNIST (url; read 2026-11-03) | ✅ (url-only) |

**Lit-scan and positioning.** The method is not frontier — convolution with shared
weights and pooling is `ref:lecun1998`, residual depth `ref:he2016`, normalization
`ref:ioffe2015` / `ref:santurkar2018`. What this study adds is measurement discipline on
a benchmark where published comparisons are single numbers. The landscape: the
dataset's own authors reached 96.2% accuracy by fine-tuning ImageNet networks at full
resolution on their own split (`ref:acevedo2019`); MedMNIST v2 shows a ResNet-18 at
28 px reaching 0.958 and 224 px adding half a point (`ref:yang2023medmnist`); MedMNIST+
re-benchmarks CNNs and ViTs across resolutions and finds that "higher image resolutions
do not consistently improve performance beyond a certain threshold" and that CNNs
remain competitive with ViTs (`ref:doerrich2025`). The symmetry prior this study adds by
augmentation has an architectural counterpart with a microscopy track record
(`ref:cohen2016`, `ref:veeling2018`). The trend runs toward pretrained foundation
features and away from training small networks from scratch; this study goes the
other way on purpose, because a 20k-parameter network on a CPU is small enough that
seed noise and item noise can each be measured rather than assumed — and on 1,712
development images the ruler's own wobble (≈ 0.02–0.03 macro-F1 at the bar) is
the size of most published "improvements".
