# Playbook — 00-known-truth-quickstart

> Rolling state of play (keep under ~120 lines). RE-READ this file before
> choosing every candidate; refresh at every phase boundary or every 5
> experiments, whichever comes first. `program.md` is the append-only journal;
> THIS is the current map. SYNTHESIZE mines both.

## Current best (per track)

| Track | Exp | Metric | Config one-liner | Held since |
| --- | --- | --- | --- | --- |
| primary | E0003 | val_auc 0.87139 | `hgbt_default` — a boosted tree at library defaults, told none of the DGP's true terms | adaptive-1 |

Distance left to the declared ceiling of 0.884116: `gap_in_floors` 1.7077, i.e.
headroom h = 1.708. Ajar, not open.

## Ruled out (evidence, not opinion)

| Direction | Evidence (exp IDs) | Why it lost (one line) |
| --- | --- | --- |
| more capacity in the boosted family | E0004 | val_auc 0.858049, `delta_in_floors` -1.7903 against its own default-capacity reference — measurably WORSE than the incumbent, not merely within noise |
| a single hyperplane over the raw features | E0001 | val_auc 0.806201 is the anchor to beat, not the answer: it is 10.4555 floors from the ceiling because the truth contains an interaction and a quadratic it cannot express |
| more hand-specified terms in the linear model | E0002, E0003 | the interaction bought 3.9699 floors and stopped there; the boosted tree bought 4.7779 more without being told anything |
| the fit-seed spread as a keep bar | sweep:fit_noise | std 0 over k = 5 — a convex solver on fixed rows does not move, so pasting it in would put the bar at zero |

## Open hypotheses

| ID | Hypothesis | Prior | Cheapest next test |
| --- | --- | --- | --- |
| H4 | the frontier reproduces on the sealed partition within the measured floor | supported by construction if nothing leaked; the ceiling itself differs between the two 4 000-row draws by 0.009353 | E0005, the one sealed access, testing P5 |
| H5 | the 1.7077 floors left between E0003 and the ceiling are irreducible at this sample size, not a modelling failure | uninformed | out of budget; a paired floor and a larger table would both sharpen it (findings section seven) |

## Next-best candidates (ranked — mirror of the phase slate, see references/phase-ritual.md)

1. `logreg_quadratic` — hand the linear model `x3^2` as well as `x1*x2`. Sum 6:
   it would reach the ceiling, but by construction, so the run teaches nothing
   the generator has not already said. NOT taken: the phase budget is spent and
   E0003 already answered the question the rung was there to answer.
2. `logreg_raw` without `x7` and `x8` — Sum 5: the predicted move is well under
   `minimum_delta` 0.00745212, so a single run cannot decide it. NOT taken.
3. A shrunk, early-stopped boosted tree between E0003 and E0004's settings —
   proposed only after E0004 landed; not taken, because the phase budget is spent
   and it is the same lever E0004 has already ruled out at this table size.

## Phase boundary

`adaptive-1` closes with its four experiments spent: three keeps (E0001, E0002,
E0003) and one discard (E0004). P1, P2 and P3 are supported and P4 refuted, each
adjudicated by the notary against a printed block, each with a dated decision in
`program.md`. The `confirmation` phase spends the one sealed access on E0003's
configuration, rehearsed first with `--final-test --dry-run`.
