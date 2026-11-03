---
title: "Small Convolutional Networks for Image Classification"
type: method-card
domain: ml
profile: [cv, ml-research]
status: seed
concepts: [convolution, weight-sharing, pooling, softmax-cross-entropy, data-augmentation, seed-variance, calibration, near-duplicates]
related: [README.md, scaling-law-fits.md]
triad:
  theory: true
  papers: true
  practice: false
---

# Small Convolutional Networks for Image Classification

*Seed card (Klein 2.3) for the `cv-classify` recipe. A study instantiates it against
its own images at the METHOD gate and verifies every reference there.*

## 1. Practitioner intuition

A linear classifier on raw pixels has to learn a separate weight for "edge at position
(3, 7)" and "edge at position (4, 7)". A convolution learns ONE small filter and slides
it everywhere — the same detector at every position (weight sharing), so the number of
parameters stops growing with the image and the model is translation-equivariant by
construction. Stacking convolution → nonlinearity → pooling builds detectors of
increasing size: edges, then textures, then parts. On small images (28–64 px) two or
three such blocks plus a linear head already beat a pixel-level logistic regression by
a wide margin; the honest baseline is still the logistic regression, because it says
how much of the task is linearly separable in pixel space.

The traps are not in the network. They are in the data (the same patient or the same
photo on both sides of the split), the seed (a single run of a small network moves by
a point or more), and the metric (accuracy on an imbalanced set hides the rare class).

## 2. Math core

| Symbol | Meaning |
|---|---|
| `x ∈ R^{C×H×W}` | an image with C channels |
| `W ∈ R^{C'×C×k×k}` | a bank of C' filters of size k×k |
| `z = softmax(f(x))` | predicted class probabilities over K classes |

1. Convolution: `(W * x)[c', i, j] = Σ_c Σ_{u,v} W[c', c, u, v] · x[c, i+u, j+v] + b[c']`.
2. Loss: cross-entropy `L = -(1/n) Σ_i log z_{i, y_i}` (the `val_mlogloss` the evaluator reports).
3. Optimizer: AdamW, `θ ← θ - η (m̂ / (√v̂ + ε) + λ θ)`.
4. Calibration: ECE `= Σ_b (|B_b|/n) · |acc(B_b) - conf(B_b)|` over confidence bins.

## 3. Minimal from-scratch implementation

```python
import torch, torch.nn as nn
class SmallCNN(nn.Module):
    def __init__(self, c_in: int, k: int, width: int = 32):
        super().__init__()
        self.body = nn.Sequential(
            nn.Conv2d(c_in, width, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(width, 2 * width, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.AdaptiveAvgPool2d(1), nn.Flatten(), nn.Linear(2 * width, k))
    def forward(self, x): return self.body(x)
```

Train with streamed index-shuffle batches (`kleinlib.torch_loop.iterate_minibatches`,
never `DataLoader` on MPS — war story 2), a fixed step budget, `kleinlib.dl.seed_everything`
per seed, and score with `kleinlib.eval_multiclass.evaluate_multiclass(y, softmax)`.
Augmentation (flips, small crops) is applied inside the training loop to the training
batch only.

## 4. When it pays / when it doesn't

| Regime | Expectation |
|---|---|
| ≥ 10⁴ small images, K ≤ 20 | a 2–3 block CNN clearly beats pixel logistic regression |
| ≤ 10³ images | pretrained features + a linear head usually win; a scratch CNN overfits |
| strong texture cues, centred objects (cells, digits) | shallow CNNs saturate quickly; width matters less than steps |
| site / scanner shift between partitions | in-distribution accuracy says little; test on the shifted site |

Falsifiable priors a study can register: a 2-block CNN beats pixel logistic regression
on macro-F1 by more than the measured floor; doubling width moves macro-F1 by less
than the floor at a fixed step budget; flip augmentation helps on rotation-invariant
cell images.

## 5. References (verify at instantiation)

- LeCun, Bottou, Bengio & Haffner (1998). Gradient-based learning applied to document recognition. *Proc. IEEE* 86(11). doi:10.1109/5.726791
- He, Zhang, Ren & Sun (2016). Deep residual learning for image recognition. arXiv:1512.03385
- Guo, Pleiss, Sun & Weinberger (2017). On calibration of modern neural networks. arXiv:1706.04599
- Yang et al. (2023). MedMNIST v2. *Scientific Data* 10. doi:10.1038/s41597-022-01721-8
- Acevedo et al. (2020). A dataset of microscopic peripheral blood cell images. *Data in Brief* 30. doi:10.1016/j.dib.2020.105474
