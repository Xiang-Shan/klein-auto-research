# Playbook — 12-insurance-claims-frequency

> Rolling state of play (keep under ~120 lines). RE-READ this file before
> choosing every candidate; refresh at every phase boundary or every 5
> experiments, whichever comes first. `program.md` is the append-only journal;
> THIS is the current map. SYNTHESIZE mines both. Swept into the next state
> commit automatically; its hash is recorded at every phase acknowledgement.

## Current best (per track)

| Track | Exp | Metric | Config one-liner | Held since |
| --- | --- | --- | --- | --- |
| primary | — | — | no incumbent yet; E0001 will set one | — |

## The bar, and what it means for every candidate

`minimum_delta` 0.0375805 (paired-bootstrap, k = 20, the `glm_ohe_balanced` vs
`hgbt_balanced` pair). That is 96 % of the whole v1 ledger's spread
(0.625462 → 0.664322 = 0.038860). Consequences to keep in mind at every candidate
choice:

- Nothing in the v1 ladder is expected to be a KEEP against an incumbent that is
  already one rung up. A keep needs a move bigger than the v1 study's entire range.
- The anchor predictions (P1, P2, P4) are `within` rules on `primary_metric` and are
  NOT governed by the floor — a run that cannot keep can still decide them.
- The comparison predictions (P3, P5, P6) are written in floors, so this bar decides
  them directly. P3 and P5 need ≥ 1 floor of paired lift; the v1 gaps they correspond
  to are 0.026245 and 0.011190, i.e. 0.70 and 0.30 floors.
- Fit noise is 2.5e-06. Anything that only re-seeds a fit is noise by four orders of
  magnitude and must never be proposed as a candidate.

## Ruled out (evidence, not opinion)

| Direction | Evidence (exp IDs) | Why it lost (one line) |
| --- | --- | --- |
| a keep bar from the fit-seed spread | `sweep:fit_noise` | std 2.5e-06 — it would keep anything that moved the fifth decimal |
| fixing the duplicate-row FAIL by dedupe or a content-grouped split | `data_card.md` BLOCKER #1, `program.md` 2026-09-03 | both change which rows are trained on, which voids the v1 train-partition identity P1/P2/P4 rest on |

## Open hypotheses

| ID | Hypothesis | Prior | Cheapest next test |
| --- | --- | --- | --- |
| H1 | the duplicated rows inflate a TREE's AUC more than a GLM's, because only a tree can memorise a cell | scouted-adjacent: the smoke check showed the GLM's `twin_free_gap` is +0.0012, i.e. the duplicates slightly DEPRESS the GLM | already wired: every run prints `twin_free_auc`; compare E0001's gap with E0003's |
| H2 | the paired floor is large because THIS pair is unusually dissimilar; a floor measured on a similar pair would be several times smaller | uninformed — the k = 20 and k = 1000 runs agree the pair's own spread is ~0.014-0.017 | the post-loop pair-specific floor sweeps registered in `program.md` |
| H3 | prose-with-kwargs reproduces less tightly than a committed file (RQ2) | scouted: the v1 study's own advice #5 says naming the kwargs is enough | compare E0002's and E0003's `anchor_gap` magnitudes |

## Next-best candidates (ranked — mirror of the phase slate, see references/phase-ritual.md)

1. Drop the six redundant categoricals the data card's WARN #4 names
   (`region_code` ↔ `region_density`, `model` ↔ `engine_type` / `segment` are 1:1
   mappings) and refit the anchor. Not chosen: the predicted move is a few
   thousandths against a floor of 0.0376, and GLM coefficient stability is not a
   question this study registered.
2. Re-run the v1 sweep's winning `learning_rate` 0.06 against `hgbt_balanced`. Not
   chosen: its own recorded lift was +0.001425, which P8 compares against the floor
   arithmetically with no run needed.
