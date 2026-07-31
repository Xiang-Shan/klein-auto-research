# Playbook — 04-fremtpl2-frequency

> Rolling state of play (keep under ~120 lines). RE-READ this file before
> choosing every candidate; refresh at every phase boundary or every 5
> experiments, whichever comes first. `program.md` is the append-only journal;
> THIS is the current map. SYNTHESIZE mines both. Swept into the next state
> commit automatically; its hash is recorded at every phase acknowledgement.

## Current best (per track)

| Track | Exp | Metric | Config one-liner | Held since |
| --- | --- | --- | --- | --- |
| primary | E0003 | 0.444689 | hgbt_ohe, lr .1, 200 iters, leaf 31 | adaptive-1 (5.7x floor over plain GLM; 11.4 paired SEs) |

## Ruled out (evidence, not opinion)

| Direction | Evidence (exp IDs) | Why it lost (one line) |
| --- | --- | --- |
| Native categoricals for HGBT here | E0004 | 0.37x floor from OHE — the predicted tie at <=22 levels |
| Post-hoc spline shaping as a GLM rescue | E0002 | kept by 0.000002 — closed 18% of the gap, not the predicted "large part" (scope caveat in program.md) |

## Open hypotheses

| ID | Hypothesis | Prior | Cheapest next test |
| --- | --- | --- | --- |
| H1 | HGBT beats plain GLM by several x floor (RQ1) | high (gbdt-tabular card; N-S-W case study) | hgbt_ohe baseline |
| H2 | GLM shaping closes much of the gap (RQ2) | medium-high (glm-pricing card) | glm_shaped |
| H3 | native-cat ~ OHE for HGBT here (RQ3) | medium (encoder-comparison) | hgbt_native |

## Next-best candidates (ranked — mirror of the phase slate, see references/phase-ritual.md)

1. Sealed final test of E0003's config — the only remaining move
2. NEXT STUDY queue: capacity/lr sweep via SweepRunner; column-scoped splines (E0002 caveat); Area×VehGas interactions; Tweedie pure-premium track
