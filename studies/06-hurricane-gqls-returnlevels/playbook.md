# Playbook — 06-hurricane-gqls-returnlevels

> Rolling state of play (keep under ~120 lines). RE-READ this file before
> choosing every candidate; refresh at every phase boundary or every 5
> experiments, whichever comes first. `program.md` is the append-only journal;
> THIS is the current map. SYNTHESIZE mines both. Swept into the next state
> commit automatically; its hash is recorded at every phase acknowledgement.

> **Process note (2026-08-01, synthesis time):** this map was reconstructed AT
> SYNTHESIS. The 11-experiment ladder ran in a single session with per-phase
> summaries written to `program.md` (the journal), and the per-candidate
> playbook refreshes were skipped — the three phase acknowledgements therefore
> recorded the scaffold hash. Recorded honestly as findings limitation 7; the
> content below mirrors the final state of play and is NOT contemporaneous
> loop memory.

## Current best (per track)

| Track | Exp | Metric | Config one-liner | Held since |
| --- | --- | --- | --- | --- |
| reproduction | E0003 | 0.002754 | full 18-cell gQLS grid, k=8, inverted_cdf (the thesis's ch.2 definition) | 2026-07-31 |
| decision | E0009 | 27.584597 | gQLS lognormal, trim (0.10,0.90) — widest breakdown point | 2026-08-01 |

## Ruled out (evidence, not opinion)

| Direction | Evidence (exp IDs) | Why it lost (one line) |
| --- | --- | --- |
| Hazen as the fitting convention | E0001, E0002 | descriptive-only: W dev 0.494 and max|Δθ| 0.0318 breach the guardrails; the thesis's own ch.2 defines inverted_cdf |
| log-Cauchy as a decision family | E0007 | perfect contamination robustness (0.0%) but worst resample instability (62.9%) and a family-conditional 1-in-100 of ~4.1e7 $bn — no finite moments, unbounded transform |
| MLE-lognormal as the stable choice | E0006, E0010+E0011 | +58.1% under 5× adaptive stress; +99.4% under the sealed 10× (derived on-ledger from E0010's MLE*/lognormal cell) |
| Narrow trim (0.05,0.95) as incumbent | E0008 vs E0009 | 41.3% vs 27.6% — instability monotone in the breakdown point; leave-2 breaches 0.05 exactly as eq. 2.5 predicts |

## Open hypotheses (inherited by findings §⑦)

| ID | Hypothesis | Cheapest next test |
| --- | --- | --- |
| N1 | Results replicate on the full extRemes::damage n=144 | new study; same surface |
| N2 | GPD/EVT arm changes the family verdict | one added family in estimators.py |
| N3 | frequency×severity with Rsum annual series (Katz 2002) | new study, compound model |

## Metrology (fixed — cite, don't remeasure)

- reproduction minimum_delta 0.005 (resolution-governed; numerical floor 8.8e-17;
  convention spread 0.0185 = SPECIFICATION, not noise)
- decision minimum_delta 1.0pp = within-sample ORDERING DEVICE (paired log-RL
  bootstrap SE 3.461, log-Cauchy-driven — RQ5-as-metrology; never quietly shrunk)
- k-sensitivity 0.1223 > convention-sensitivity 0.1040: BOTH load-bearing at n=30
