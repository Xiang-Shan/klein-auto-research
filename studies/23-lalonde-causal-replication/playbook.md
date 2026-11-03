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
| att | E0006 | att_usd 2683.82 (gap +889.48; measured; P3 supported) | AIPW, dw_psid, selected for the sealed CPS-1 cell by the registered rule | estimators |

## Ruled out (evidence, not opinion)

| Direction | Evidence (exp IDs) | Why it lost (one line) |
| --- | --- | --- |
| Reading PSID-1 Table 3 col (2) 731 as the note-a regression | E0001 diag rows | note a gives 217.94 = Panel C col (4) 218; 731 is col (5) |
| "all covariates" readings (married; married+u) as col (5) | E0001 diag rows | 795.02 and 67.28 vs 731: neither within +-1 |
| Standard-error formula as a source of misses | E0001 | classical OLS SE matched on all 6 non-PSID-adjusted SE/estimate targets |
| IPW dw_psid as a sealed candidate | E0002 gap +1244.09 (P2 refuted) | lost the selection to AIPW; heavy single-unit weight 0.135 |
| 1-NN matching dw_psid | E0005 gap -1234.06, 56 distinct controls (P4 refuted) | lost the selection; wide CI |
| Dropping RE74 as a harmless simplification | E0007 gap -1809.67 (P5 supported) | RE74 is load-bearing: estimate collapses to about 0 |

## Open hypotheses

| ID | Hypothesis | Prior | Cheapest next test |
| --- | --- | --- | --- |
| H1-H4 | P2 refuted, P3 supported, P4 refuted, P5 supported | resolved | -- |
| H5 | col (5) covariate set unrecovered (expect P6 CPS-1 adjusted target and SE to miss) | 0.8 | confirmation reproduction cell |
| H6 | P7: AIPW dw_psid carried unchanged to CPS-1 lands within $1,000 | 0.5 | sealed att cell |

## Next-best candidates (ranked — mirror of the phase slate, see references/phase-ritual.md)

Confirmation phase (each sealed access once, each after `--final-test --dry-run`):
1. reproduction track, CPS-1 sealed (P6), unchanged anchor cell
2. att track, CPS-1 sealed: AIPW, spec dw_psid, reps 500 (P7); selected at E0006 by the registered rule
Note: AIPW at 500 reps took about 11 min on PSID-1 under load; CPS-1 has 15,992 rows against max_run_seconds 900 -- check the dry run's wall_seconds before the real run.
Process: launch with nohup and poll; never wrap run-one in a foreground timeout.
