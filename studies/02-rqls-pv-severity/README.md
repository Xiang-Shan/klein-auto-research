# 02 — Robust quantile least squares for PV loss severity

**The "no data? build a known-truth lab" study.** A fully synthetic photovoltaic
loss-severity generator (lognormal body, five-peril mix, $5k truncation, $2M
policy cap, optional GPD tail) where the *truth is known by construction* — so
estimator claims become checkable. Seven experiments comparing naive MLE against
truncation/censoring-aware MLE and robust quantile least squares (QLS), scored on
the one number an actuary feels: **absolute risk-loaded premium error vs truth**.

Headlines (full verdicts in `findings.md`; teaching write-up in
`report/index.html`, self-contained):

- **Breakdown, the money slide:** at 10% claim contamination, naive MLE's premium
  error explodes to **352%**; the observable-window QLS stays bounded at **50%**
  (at 5%: 136.6% vs 20.3%). Robustness costs only 1.083× at zero contamination.
- **Parameter bias ≠ pricing bias:** truncation-naive MLE has theory-exact
  parameter biases that nearly cancel in the layer premium — never judge an
  estimator on parameter RMSE alone.
- **The observable window ≫ blind trimming**, and a **policy cap is a tail-risk
  control** (bounds the heavy-tail premium impact to +0.17%).

## Running it

Pure numpy/scipy — no dataset, no extras, no credentials:

```bash
uv run prepare.py    # writes the generator config; no external data to download
uv run train.py      # current committed experiment state (~seconds)
```

CI runs this study's E1 truth-recovery gate on every push. The whole 7-experiment
ladder was ~5 minutes of compute (`aux_metrics.tsv` `wall_seconds`).

## Note for cloners — provenance of hashes

Executed in the Klein development lab before this repo's public history began:
the `commit` column in `results.tsv` refers to the lab's git history (your own
runs in this clone write resolvable hashes). The QLS references in
`method_card.md` are verified published work; **no published QLS-on-PV
application exists** — that bridge is this study's own construction, and the
findings say so explicitly. Ledger, findings, and program notebook are immutable
exhibits — continue only via new experiments on an `experiments/…` branch.
