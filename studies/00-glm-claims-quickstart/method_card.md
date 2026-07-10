---
type: method-card
domain: "insurance"
status: final
concepts: [logistic-regression, hist-gradient-boosting, familiar-anchor, isotonic-calibration]
related: [../../knowledge/method_cards/glm-pricing.md, ../../knowledge/method_cards/gbdt-tabular.md]
refs_verified: true
---

# Method card — 00-glm-claims-quickstart (short, study-local)

> Gate 2 (METHOD). This is the **FAMILIAR-model anchor study** — logistic regression
> (GLM) and sklearn's `HistGradientBoostingClassifier` are well-understood, non-frontier
> methods being used here as split-identity anchors, not as objects of new pedagogy.
> Per `.claude/skills/klein/references/method-gate-protocol.md`, the mandatory lit-scan /
> full intuition-math-impl arc applies to *unfamiliar or frontier* methods; this card is
> intentionally short and POINTS at the full pedagogy rather than repeating it.

## Full card

The complete intuition → math core → minimal implementation → when-it-pays arc for the
GLM side of this study lives in **`../../knowledge/method_cards/glm-pricing.md`** — it
was written explicitly anticipating this study ("Study 00 uses exactly this as its
familiar baseline") and already documents the exact 0.6255 → 0.6528 anchor trajectory
reproduced here as E1/E2. The GBDT side (E3) is likewise familiar; its when-it-pays
framing lives in `../../knowledge/method_cards/gbdt-tabular.md`.

This study contributes no new method pedagogy — its job is to prove the *framework*
(`kleinlib` + the loop contract) reproduces known-good numbers on both anchors, not to
teach either method for the first time.

## Falsifiable priors this study tests

Mirrored verbatim in `study.yaml:predictions_to_falsify`; `findings.md` records the
observed value and a held/falsified verdict against each:

| # | Lever | Predicted | Falsifiable? |
|---|---|---|---|
| 1 | E1 — campaign's exact Phase-0 LR (OHE min_freq=20, `class_weight=balanced`) | `val_auc = 0.6255 ± 0.001` | Yes — hard GATE, STOP everything if missed |
| 2 | E2 — campaign's winning Phase-1 LR (splines + log1p + interactions + isotonic) | `val_auc = 0.6528 ± 0.003` | Yes — looser tolerance (reconstructed recipe; see program.md) |
| 3 | E3 — campaign's tuned Phase-0 HGBT (OHE + 7 deterministic-column drops + shrinkage) | `val_auc = 0.6629 ± 0.003` | Yes — recipe recovered verbatim via `git show` (committed exps 6/7) |
| 4 | E4 — E1's config with `class_weight=None` + isotonic instead of `balanced` | `val_auc` within `± 0.003` of E1; reliability curve near-diagonal (brier/logloss much improved) | Yes — the calibration-doctrine smoke test (RQ2) |

## Regime verdict (why these are "familiar", not frontier)

| Regime | Data size | Signal | Verdict |
|---|---|---|---|
| GLM (LR) on ~59k-row weak-signal tabular claims | medium tabular | weak (best-in-class AUC ~0.65) | Pays for filing/transparency/calibration; leaves ~0.017 AUC on the table vs GBDT — expected, not a bug (see full card §4) |
| GBDT (HGBT) on the same data | medium tabular | weak-moderate | Pays for raw discrimination; used here purely as the campaign's non-linear reference point, not as a new object of study |

## References

Both are textbook methods; the campaign-specific numeric claims above are traceable to
committed campaign artifacts (git commits + `results.tsv` descriptions — see
`program.md`'s per-experiment log lines), not literature claims requiring a fresh
lit-scan. Textbook references for the two methods are already verified in the linked
full cards (`glm-pricing.md` §5, `gbdt-tabular.md` §5).
