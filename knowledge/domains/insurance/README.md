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
