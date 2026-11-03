---
title: "Fitting and Testing Data-Scaling Laws"
type: method-card
domain: ml
profile: [ml-research, cv]
status: seed
concepts: [power-law, log-log-regression, irreducible-loss, bootstrap-interval, extrapolation-test, seed-arrays, registered-cells]
related: [README.md, cnn-image-classification.md]
triad:
  theory: true
  papers: true
  practice: false
---

# Fitting and Testing Data-Scaling Laws

*Seed card (Klein 2.3) for the `dl-scaling` recipe — an `estimate` study whose cells
are training-set sizes and whose sealed evidence is an extrapolation.*

## 1. Practitioner intuition

Train the same model on growing fractions of the data and the held-out loss usually
falls along a straight line on a log-log plot — a power law — until it bends toward a
floor the model or the labels cannot get under. The slope is the useful number: it says
what ten times more data buys. A scaling "law" is an empirical regularity, so the honest
test of a fitted curve is a prediction it did not see: fit on the small cells, predict
the largest one, and only then train it.

Three things make naive fits wrong: seed noise at small N (single runs zig-zag), a floor
that bends the tail (a pure power law then underestimates the loss at large N), and
compute that is not matched (bigger N trained for the same number of epochs gets more
steps).

## 2. Math core

| Symbol | Meaning |
|---|---|
| `N` | training-set size |
| `L(N)` | held-out loss at size N |
| `α, A, E` | exponent, scale, irreducible loss |

1. Pure power law: `L(N) = A · N^(-α)` ⇒ `log L = log A - α log N` (OLS on logs).
2. With a floor: `L(N) = E + A · N^(-α)` (nonlinear least squares, `E ≥ 0`).
3. Interval for α: bootstrap over seed replicates within each cell, refit each draw.
4. Extrapolation check: the sealed cell's loss lies inside the prediction interval at `N_max`.

## 3. Minimal from-scratch implementation

```python
import numpy as np
def fit_power(N, L):                                  # cells: arrays of sizes and mean losses
    slope, intercept = np.polyfit(np.log(N), np.log(L), 1)
    return -slope, np.exp(intercept)                   # alpha, A
rng = np.random.default_rng(0)
alphas = [fit_power(N, [rng.choice(seed_losses[n]).mean() for n in N])[0] for _ in range(2000)]
lo, hi = np.quantile(alphas, [0.025, 0.975])
```

Each cell is a registered `measured` run (a seed array over N); the fit is computed in
the analysis cell and pinned as a table; the sealed run trains at the full size.

## 4. When it pays / when it doesn't

| Regime | Expectation |
|---|---|
| N spans ≥ 1.5 decades, ≥ 3 seeds per cell | α is identifiable; interval width a few hundredths |
| N spans < 1 decade | α is poorly identified; report the interval, claim nothing about the slope |
| the loss is near its floor at large N | pure power law under-predicts the largest cell; fit the floor |
| epochs fixed across N | larger N gets more steps — confounded; fix steps or state it |

Registrable priors: α lies in a stated range; the full-size loss lies inside the 95 %
prediction interval of the small-N fit; the floor model fits better than the pure power
law by more than the seed noise.

## 5. References (verify at instantiation)

- Hestness et al. (2017). Deep learning scaling is predictable, empirically. arXiv:1712.00409
- Rosenfeld et al. (2020). A constructive prediction of the generalization error across scales. arXiv:1909.12673
- Kaplan et al. (2020). Scaling laws for neural language models. arXiv:2001.08361
- Hoffmann et al. (2022). Training compute-optimal large language models. arXiv:2203.15556
