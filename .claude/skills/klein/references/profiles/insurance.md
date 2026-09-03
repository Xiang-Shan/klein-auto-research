# Profile: insurance

The reference profile. Klein's discipline was first proven on insurance data (the
215-experiment ancestor campaign, studies 00–09), which is why its vocabulary is the
most developed — and why every insurance sentence now lives here rather than in the
core protocols. It is one profile among four, not the default.

## 1. Audience
An actuary or pricing analyst who needs calibrated probabilities or rates they can
file, defend, and reconcile to experience — for whom calibration often matters more
than rank, and for whom "material" is a priced word.

## 2. §⑤ heading
**⑤ Business / actuarial value implications.** Prompt: premium, calibration, filing,
capital, triage — what the result is worth in decisions, not in metric points. Price
nothing without a registered `materiality:` block (who priced the consequence, in what
currency, on what date); without one, "actionable" means only that the registered
keep-sized bar was cleared.

## 3. Doctrine
Trees still win on most tabular problems (Grinsztajn et al. 2022) — a deep or frontier
method must earn its place against a tuned GBDT and a GLM anchor. On weak-signal
imbalanced targets, default to `class_weight=None` + isotonic calibration + threshold
tuning; resampling the training fold is an experiment, resampling the development
fold is forbidden (war story 4). Tweedie power is dataset-dependent: 1 = frequency
(Poisson), 2 = severity (Gamma), 1 < p < 2 = pure premium; state it in the track
contract. Rank and calibration are weighed together in SYNTHESIZE, never rank alone.

## 4. Figures
Classification: ROC, PR, reliability, score histogram by class, decile lift, confusion
at best threshold. Frequency / severity / pure premium: Lorenz and Gini, CAS-style
lift and quantile charts, actual-vs-expected calibration by decile
(`kleinlib.figures.standard_regression_report`), and — when the `pricing-eval`
accelerator is available — the underwriting eval card built from
`kleinlib.eval.save_holdout_predictions` (the predictions table itself is never
committed). Tutorial §⑥ heading: **Model coding advice**.

## 5. Knowledge
`knowledge/domains/insurance/` — `best-practices-auto-insurance.md`,
`gbdt-hyperparameter-guide.md`, `encoder-comparison.md`, the pricing method cards —
and `knowledge/research-discipline.md`.

## 6. Budgets
| Run-cost class | Starting `max_run_seconds` |
|---|---|
| small tabular (< 10k rows, < 50 features) | 120 |
| medium tabular (10k–100k rows) | 300 |
| large tabular (100k–1M rows) | 600 |
| GBDT HPO / sweeps | 900–1 800 |
| deep tabular / torch | 1 800–3 600 |
After the anchor: `max(3× anchor wall-clock, 60 s)`.

## 7. Vocabulary
Banned: "material" / "actionable" without a `materiality:` block (study 09 banned the
conflation of measurement resolution with business materiality outright); "lift"
without its decile and base rate; "significant" without the test. Must be qualified:
"better" (rank or calibration, and by how many floors). Honest verbs: cleared the bar,
within noise, calibrated within ±x at decile d.

## 8. CONSULT hints
`predict` for frequency, severity, lapse, fraud, triage; `estimate` for return levels
and tail quantities; `test` for "does the new rating factor add signal"; `replicate`
for a benchmark paper's number. Modality is almost always `tabular`, occasionally
`timeseries` (claims development) with a time split.
