---
title: "Insurance — domain knowledge"
type: reference
domain: insurance
status: ported
concepts: [insurance, pricing, calibration, gbdt, encoders]
related: [best-practices-auto-insurance.md, ../../gbdt-hyperparameter-guide.md, ../../encoder-comparison.md, ../../method_cards/glm-pricing.md]
---

# Insurance

The reference domain: Klein's discipline was first proven on insurance-claims data
(the 215-experiment ancestor campaign, best val_auc 0.6715; studies 00, 05–09, 12).

- `best-practices-auto-insurance.md` — the ported campaign synthesis (modelling
  posture, imbalance and calibration, encoders, what did not help).
- Doctrine anchor: trees still win on most tabular problems (Grinsztajn et al. 2022);
  `class_weight=None` + isotonic calibration + threshold tuning on weak-signal
  imbalanced targets; Tweedie power declared per track (1 frequency, 2 severity,
  1 < p < 2 pure premium).
- Related top-level docs: `gbdt-hyperparameter-guide.md`, `encoder-comparison.md`,
  `method_cards/glm-pricing.md`, `method_cards/gbdt-tabular.md`.

## What study 12 measured on this portfolio

The reference dataset now has a measured resolution, which every earlier number on it
was quoted without.

- The paired-comparison keep bar on the 58,592-policy motor portfolio, at a 10 %
  development partition, is 0.0375805 of AUC — 0.9671 of the entire spread of the v1
  quickstart's six-row ledger. A fourth decimal of AUC on this data is not a
  measurement (supports 12-insurance-claims-frequency#C3, supports
  12-insurance-claims-frequency#C8).
- The paired floor is a property of the PAIR, not of the data: two rungs differing by
  one lever pair down to a standard deviation of 0.001276, while a GLM against a
  boosted tree stays at 0.013942 — a ratio of 10.92 on the same rows. Measure the floor
  of the comparison you will actually make (supports
  12-insurance-claims-frequency#C9, supports 12-insurance-claims-frequency#C10).
- `class_weight=None` + isotonic calibration reproduces the doctrine here: Brier
  improves by a factor of 4.055 for 0.0390 of a floor of AUC (supports
  12-insurance-claims-frequency#C5).
- The dataset carries exact duplicate rows across any row-index split: 0.051203 of a
  10 % development partition, and 0.052223 of the v1 study's own validation partition,
  which was never checked. Their measured effect on every rung tried was at most
  0.001415 of AUC, and mostly in the direction that flatters the twin-free number
  (supports 12-insurance-claims-frequency#C6,
  supports 12-insurance-claims-frequency#C12).
- Top-decile lift is far less stable than AUC at this claim rate: it fell 0.5101
  between two halves of the same validation set while AUC moved 0.1680 of a floor
  (supports 12-insurance-claims-frequency#C11).
