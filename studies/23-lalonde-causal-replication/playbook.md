# Playbook — 23-lalonde-causal-replication

> Rolling state of play (keep under ~120 lines). RE-READ this file before
> choosing every candidate; refresh at every phase boundary or every 5
> experiments, whichever comes first. `program.md` is the append-only journal;
> THIS is the current map. SYNTHESIZE mines both. Swept into the next state
> commit automatically; its hash is recorded at every phase acknowledgement.

## Current best (per track)

| Track | Exp | Metric | Config one-liner | Held since |
| --- | --- | --- | --- | --- |
| reproduction | E0001 | targets_outside_tolerance = 2 (measured; P1 refuted) | development lane, as-committed anchor cell; 9/11 targets within +-1 | anchor |
| att | -- | no run yet | estimators phase not started | -- |

## Ruled out (evidence, not opinion)

| Direction | Evidence (exp IDs) | Why it lost (one line) |
| --- | --- | --- |
| Reading PSID-1 Table 3 col (2) 731 as the note-a regression | E0001 diag rows | note a gives 217.94 = Panel C col (4) 218; 731 is col (5) |
| "all covariates" readings (married; married+u) as col (5) | E0001 diag rows | 795.02 and 67.28 vs 731: neither within +-1 |
| Standard-error formula as a source of misses | E0001 | classical OLS SE matched on all 6 non-PSID-adjusted SE/estimate targets |

## Open hypotheses

| ID | Hypothesis | Prior | Cheapest next test |
| --- | --- | --- | --- |
| H1 | P2 IPW (DW PSID-1 logit) within $1,000 of 1794.34 | 0.5 | estimators cell 1 (att, ipw, dw_psid) |
| H2 | P3 AIPW within $1,000 | 0.55 | cell 2 |
| H3 | P4 1-NN matching within $1,000 | 0.55 | cell 3 |
| H4 | P5 no-RE74 IPW misses by > $1,000 | 0.6 | cell 4 |
| H5 | col (5) covariate set unrecovered by tried readings (impacts P6 CPS-1 adjusted target, expect a miss there too) | 0.8 | not needed before confirmation; note for P6 |

## Next-best candidates (ranked — mirror of the phase slate, see references/phase-ritual.md)

Estimators phase (att track, PSID-1, one registered cell each; bootstrap 500 reps):
1. P2 IPW, spec dw_psid (anchors the weights; sets the selection baseline)
2. P4 1-NN matching with replacement (same score)
3. P3 AIPW (note a outcome model)
4. P5 IPW without any RE74 term (sensitivity; RQ4)
Then apply the registered selection rule (smallest |gap| among P2-P4; ties IPW < matching < AIPW) for the sealed CPS-1 cell. Anchor phase done; do not re-run the reproduction cell.
