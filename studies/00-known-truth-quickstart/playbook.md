# Playbook — 00-known-truth-quickstart

> Rolling state of play (keep under ~120 lines). RE-READ this file before
> choosing every candidate; refresh at every phase boundary or every 5
> experiments, whichever comes first. `program.md` is the append-only journal;
> THIS is the current map. SYNTHESIZE mines both.

## Current best (per track)

| Track | Exp | Metric | Config one-liner | Held since |
| --- | --- | --- | --- | --- |
| primary | — | — | no run yet; the gates are recorded and Phase 0 metrology is next | — |

## Ruled out (evidence, not opinion)

| Direction | Evidence (exp IDs) | Why it lost (one line) |
| --- | --- | --- |
| — | — | nothing yet: the ledger is empty |

## Open hypotheses

| ID | Hypothesis | Prior | Cheapest next test |
| --- | --- | --- | --- |
| H1 | the distance from a raw-feature linear model to the known ceiling is several measured floors wide | scouted: the linear-oracle projection of the true log-odds sits ~0.076 AUC below the ceiling | E0001, the anchor, which prints its own `gap_in_floors` |
| H2 | a boosted tree recovers both the interaction and the quadratic without being told either | method card §4 and ref:grinsztajn2022 | E0003 |
| H3 | the headroom closes (`h < 1`) before the fourth candidate is spent | uninformed — the floor is not measured yet | read `h` at the preflight before E0004 |

## Next-best candidates (ranked — mirror of the phase slate, see references/phase-ritual.md)

1. Filled at the `adaptive-1` slate ritual, immediately after the Phase 0 floors
   are measured and pasted into the contract.
