# Research plan — 23-lalonde-causal-replication

## Question

Does the Dehejia-Wahba NSW experimental benchmark (about $1,794) reproduce from the authors' own files, how far does a naive non-experimental comparison miss it, and do propensity-score estimators recover it on PSID-1 and then, sealed, on CPS-1?

## Contract

- Domain: program evaluation (labor economics)
- Data: Dehejia's posted NSW / PSID / CPS files (`url:` pins with sha256), lanes by a predefined split
- Tracks: `reproduction` (targets outside tolerance, exact) and `att` (ATT in 1982 dollars with a bootstrap interval)
- Method depth: full
- Per-run maximum: 900 seconds

## Validation policy

Use train/development for adaptive choices. Access the sealed test partition once per
track through `uv run --locked klein run-one --final-test`; label synthesis
exploratory or confirmed.

## Experiment ladder

1. **Anchor (P1).** Reproduce Table 3 columns (1)-(2) for NSW and PSID-1 and Table 1's
   sizes on the development lane. A miss stops the study until the files or the
   standard-error formula are explained.
2. **Estimators on PSID-1 (P2-P5).** Four registered cells, one idea each: IPW on DW's
   PSID-1 logit; AIPW (same weights, OLS outcome model); 1-NN matching on the score;
   IPW with every 1974-earnings term removed. Each prints its gap to the experimental
   estimate computed in the same run.
3. **Selection, on the record.** The sealed estimator is the P2-P4 cell with the
   smallest |gap| (ties to the simpler: IPW < matching < AIPW), written as a dated
   `Decision:` line in program.md before any sealed access.
4. **Sealed CPS-1 (P6, P7).** `--final-test --dry-run`, then one sealed cell per track.
5. **Replication.** `klein replicate` one cell per track (confirmation requires it).

## What would change the conclusion

- A reproduction miss on the adjusted columns would make every later estimate a
  statement about OUR pipeline, not DW's — findings would say so.
- A gap within $1,000 driven by a handful of controls (max_weight_share near 1) is
  agreement by accident; the cell's table pins the share so the referee can see it.
