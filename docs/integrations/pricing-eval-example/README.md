# Worked example — external eval card from a Klein study

`eval_card.md` (plus its charts) is an underwriting-ready evaluation card of
**study `04-fremtpl2-frequency`'s incumbent** (E0003, `hgbt_ohe`), with E0002's
shaped GLM as the double-lift comparison model — the study's actual
GLM-vs-GBDT question rendered for a pricing audience. The double-lift's top
band is the story in one row: where the two models disagree most, actuals side
with the GBDT.

## Provenance (fully regenerable)

- Predictions: the study's committed `pipeline.py` at the study's merge commit
  (`c55d46d`), refit on the declared train fold (E0003 config: seed 0, lr 0.1,
  200 iters; E0002 config: shaped GLM), scored on the **development** fold —
  the sealed test was not touched. The refit reproduced both kept anchors to
  6 decimals (0.444689 / 0.453073) before any export.
- Export: `kleinlib.eval.save_holdout_predictions(...)` → the gitignored
  `predictions/<exp>_holdout.csv.gz` convention (`y_true` = rate, `weight` =
  exposure, dims `DrivAge, BonusMalus, VehGas`, `y_pred_b` = the GLM).
- Card: the external `pricing-eval` skill's `eval_card.py`
  (`--power 1 --dims DrivAge,BonusMalus,VehGas --pred-b y_pred_b`) — an
  **example binding from the author's harness**; any eval-card tool consuming
  the same `y_true`/`y_pred`/`weight` table works. When no such tool is
  present, `kleinlib.figures.standard_regression_report` is the bundled
  fallback (Lorenz, CAS-style lift/quantile, calibration-by-decile).

Seam documentation: `.claude/skills/klein/references/synthesis-protocol.md`
§"Pricing studies: the eval-card exhibit". Only the card and its small charts
are committed — never the predictions table.
