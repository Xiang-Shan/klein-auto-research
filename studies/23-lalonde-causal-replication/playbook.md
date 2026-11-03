# Playbook — 23-lalonde-causal-replication

> Rolling state of play (keep under ~120 lines). RE-READ this file before
> choosing every candidate; refresh at every phase boundary or every 5
> experiments, whichever comes first. `program.md` is the append-only journal;
> THIS is the current map. SYNTHESIZE mines both. Swept into the next state
> commit automatically; its hash is recorded at every phase acknowledgement.

## Current best (per track)

| Track | Exp | Metric | Config one-liner | Held since |
| --- | --- | --- | --- | --- |
| reproduction | E0001 / E0008 sealed | targets_outside_tolerance = 2 on both lanes (P1 and P6 refuted); replicated exact | as-committed reproduction cell; misses are exactly adjusted value + SE (col (5)) | confirmation |
| att | E0006 / E0009 sealed | dev gap +889.48 (P3 supported); sealed CPS-1 att 1327.54, gap -466.80, CI [-129.17, 2835.62] (P7 supported); E0006 replicated exact | AIPW, dw_psid, 500 reps | confirmation |

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

All registered cells are run: P1 refuted, P2 refuted, P3 supported, P4 refuted, P5 supported, P6 refuted, P7 supported. Sealed access spent on both tracks; both replication records filed. Remaining lifecycle: SYNTHESIZE (findings.md, claims.lock), REFEREE, TUTORIAL. No further development candidates are open.
H5 (col (5) covariate set unrecovered) is confirmed on CPS-1 (E0008 diagnostics) and stays open as a next-step question for findings.
