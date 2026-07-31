# Playbook — 04-fremtpl2-frequency

> Rolling state of play (keep under ~120 lines). RE-READ this file before
> choosing every candidate; refresh at every phase boundary or every 5
> experiments, whichever comes first. `program.md` is the append-only journal;
> THIS is the current map. SYNTHESIZE mines both. Swept into the next state
> commit automatically; its hash is recorded at every phase acknowledgement.

## Current best (per track)

| Track | Exp | Metric | Config one-liner | Held since |
| --- | --- | --- | --- | --- |
| primary | E0001 | 0.454861 | glm_ohe, alpha 1e-4 | anchor |

## Ruled out (evidence, not opinion)

| Direction | Evidence (exp IDs) | Why it lost (one line) |
| --- | --- | --- |

## Open hypotheses

| ID | Hypothesis | Prior | Cheapest next test |
| --- | --- | --- | --- |
| H1 | HGBT beats plain GLM by several x floor (RQ1) | high (gbdt-tabular card; N-S-W case study) | hgbt_ohe baseline |
| H2 | GLM shaping closes much of the gap (RQ2) | medium-high (glm-pricing card) | glm_shaped |
| H3 | native-cat ~ OHE for HGBT here (RQ3) | medium (encoder-comparison) | hgbt_native |

## Next-best candidates (ranked — mirror of the phase slate, see references/phase-ritual.md)

1. HGBT poisson baseline (sum 9) — RQ1; paired-floor preview says ~11 SEs
2. GLM + shaping (sum 8) — RQ2, run first (cheaper, orders the GLM story)
3. HGBT native categoricals (sum 8) — RQ3
4. HGBT max_leaf 63 (sum 7) — capacity probe
5. DEFERRED: Area×VehGas GLM interactions; Tweedie pure-premium (new track, needs severity)
