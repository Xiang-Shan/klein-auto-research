# Playbook — 12-insurance-claims-frequency

> Rolling state of play (keep under ~120 lines). RE-READ this file before
> choosing every candidate; refresh at every phase boundary or every 5
> experiments, whichever comes first. `program.md` is the append-only journal;
> THIS is the current map. SYNTHESIZE mines both. Swept into the next state
> commit automatically; its hash is recorded at every phase acknowledgement.

## Current best (per track)

| Track | Exp | Metric | Config one-liner | Held since |
| --- | --- | --- | --- | --- |
| primary | E0003 | 0.664051 | `hgbt_balanced` — HGBT(lr 0.05, 500 iters, 31 leaves, class_weight=balanced, early stopping) over OHE(min_frequency=20), 7 model-derivative columns dropped | 2026-09-03 |

## The bar, and what it did

`minimum_delta` 0.0375805 (paired-bootstrap, k = 20, `glm_ohe_balanced` vs
`hgbt_balanced`). It is 96.7 % of the whole v1 ledger's spread (0.625462 → 0.664322).
Four runs later, what it actually decided:

| Comparison | Paired lift | In floors | Verdict |
| --- | --- | --- | --- |
| E0002 spline+isotonic vs the raw anchor | +0.035956 | 0.9568 | under the bar — P3 refuted |
| E0003 tree vs the calibrated GLM | +0.013956 | 0.3714 | under the bar — P5 refuted |
| E0003 tree vs the incumbent anchor | +0.049911 | 1.3282 | over the bar — the study's one keep |
| E0004 doctrine A/B vs the anchor | −0.001465 | −0.0390 | inside the bar, as P6 predicted |

## Ruled out (evidence, not opinion)

| Direction | Evidence (exp IDs) | Why it lost (one line) |
| --- | --- | --- |
| feature engineering on the linear rung as a route to a KEEP | E0002 | the whole spline + log1p + interaction + isotonic chain is 0.9568 floors — real, and under the bar |
| the tree's edge over the calibrated GLM as a filing argument | E0003 | 0.3714 floors; the price of a filable GLM is not resolvable at this sample size |
| `class_weight="balanced"` as a way to buy rank | E0004 | it costs 0.039 floors of AUC and 4.06x of Brier; it buys nothing |
| duplicated rows as an explanation of any rung's score | E0001, E0002, E0003, E0004 | `twin_free_gap` ∈ [−0.001415, +0.001198] across all four; three of four are POSITIVE, so the duplicates never flattered a headline number |
| a keep bar from the fit-seed spread | `sweep:fit_noise` | std 2.5e-06 — it would keep anything that moved the fifth decimal |
| fixing the duplicate-row FAIL by dedupe or a content-grouped split | `data_card.md` BLOCKER #1 | both change which rows are trained on, voiding the v1 identity P1/P2/P4 rest on |

## Open hypotheses

| ID | Hypothesis | Prior | Cheapest next test |
| --- | --- | --- | --- |
| H1 | the duplicated rows inflate a TREE's AUC more than a GLM's | **REFUTED** by E0003: `twin_free_gap` +0.001018, the same sign and size as the GLMs' | closed |
| H2 | the paired floor is large because THIS pair is unusually dissimilar; a similar pair's floor would be several times smaller | open — the ladder's own three comparisons have very different similarity | the post-loop pair-specific floor sweeps registered in `program.md` |
| H3 | prose-with-kwargs reproduces less tightly than a committed file (RQ2) | **directionally supported, quantitatively almost empty**: 0.001154 (verbatim) vs 0.001612 (prose+kwargs) vs 0.011322 (the anchor's quoted constructor) | closed by E0001-E0003; the residual question is why the ANCHOR is 7x looser |
| H4 | the anchor's 0.011322 residual is evaluation-row sampling, not an unrecovered kwarg | uninformed; it equals the closed-form transfer SD (0.011226) to three decimals, which is either strong support or a coincidence | a split-lottery of the anchor already gives the spread (std 0.0179641); separating the two would need the v1 model itself, which does not survive |

## Next-best candidates (ranked — mirror of the phase slate, see references/phase-ritual.md)

1. Pair-specific paired floors for each of the ladder's three comparisons (registered
   before the loop, to be run after it). Answers H2 and RQ3 directly; cannot change a
   registered verdict.
2. Drop the six redundant categoricals the data card's WARN #4 names. Still not chosen:
   a few thousandths against a floor of 0.0376.
3. Re-run the v1 sweep's winning `learning_rate` 0.06. Still not chosen: its lift was
   +0.001425 and P8 settles it arithmetically.
