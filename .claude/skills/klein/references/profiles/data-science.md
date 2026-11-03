# Profile: data-science

For studies that answer a question with observational or experimental tabular data —
an effect estimate, a causal contrast, a segment analysis, a forecast that informs a
decision — where the reader acts on the number rather than on the model.

## 1. Audience
A data scientist, economist, epidemiologist or analyst who knows that a regression
coefficient is not an effect, that a significant p-value is not a size, and that the
same data can support opposite stories; they will ask "compared with what, adjusted for
what, and would a randomized benchmark agree?".

## 2. §⑤ heading
**⑤ What the decision-maker should take from this.** Prompt: state the estimand in
words (whose outcome, contrast, population), the estimate with its interval, the
identification assumption it rests on, how far the observational estimate sits from
any experimental benchmark, and what would change the conclusion.

## 3. Doctrine
Name the estimand before the estimator (ATE, ATT, a conditional effect, a predictive
level) and keep predictive and causal claims in separate classes. An observational
contrast is reported beside the naive comparison and, where one exists, an
experimental benchmark — LaLonde (1986, American Economic Review) showed that
non-experimental estimators can miss an experimental answer by its whole size, and
Dehejia & Wahba (1999, JASA) that propensity-score methods can recover it under
stated overlap; both the overlap diagnostics and the sensitivity of the answer to the
specification are part of the evidence. Every estimate carries an interval
(`evaluate_estimate`; bootstrap, analytic or jackknife, named). Multiple specifications
are a family (`n_comparisons`, `metrology.family_maxt` or Bonferroni) or they stay
exploratory. Feature importance and SHAP values describe the model, never the world.

## 4. Figures
The estimate with its interval across specifications (a forest plot with the
experimental benchmark as a reference line); covariate balance before and after
adjustment; propensity overlap by group; the decision trajectory per track.
Tutorial §⑥ heading: **Analysis-pipeline advice**.

## 5. Knowledge
`knowledge/domains/data-science/` (created when the first data-science exhibit closes)
and `knowledge/research-discipline.md`; method card `knowledge/method_cards/causal-propensity-methods.md`.

## 6. Budgets
| Run-cost class | Starting `max_run_seconds` | Floor recipe |
|---|---|---|
| thousands of rows, seconds | 300 | bootstrap interval per cell; `split-lottery` for a predictive level |
| millions of rows | 1 800 | subsample-bootstrap, disclosed |
Specifications are registered cells; a specification search is a sweep, registered.

## 7. Vocabulary
Banned: "causes", "drives", "proves", "significant" — the first two claim identification
the design may not have, the last two confuse a test with a size. Must be qualified:
"effect" (which estimand, under which assumption), "impact" (measured how), "robust"
(across which specifications). Honest verbs: is associated with, under unconfoundedness
the estimated ATT is, recovers the experimental benchmark within, depends on the
specification.

## 8. CONSULT hints
`estimate` for an effect or a level with its interval; `replicate` for a published
estimate (two-source transcription of the target values); `test` for a registered
contrast; `predict` when the deliverable is a forecast. Modality `tabular` (or
`timeseries`); several input files go in `data.inputs`.
