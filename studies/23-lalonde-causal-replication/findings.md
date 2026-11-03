---
type: findings
domain: "program evaluation (labor economics)"
profile: "data-science"
kind: "replicate"
status: complete
concepts: [replication, experimental-benchmark, att, propensity-score, odds-weights, aipw, nearest-neighbour-matching, weight-concentration, table-inconsistency, sealed-transfer, exact-re-execution]
related: [program.md, playbook.md, data_card.md, method_card.md, scouting_ledger.md, references.yaml, incidents/2026-11-03-e0005-history-repair/README.md, claims.lock]
---

# Findings — 23-lalonde-causal-replication

> SYNTHESIZE output, 2026-11-03. Every claim cites evidence ids from the immutable run
> manifests, the replication records or a pinned table (`art:<alias>`, listed in
> `claims.lock`). Both tracks are `registered`: there is no frontier and no keep chain,
> only pre-registered cells, so nothing below is a "best model". Claim ids are fully
> qualified as `23-lalonde-causal-replication#Cn`. Protocol:
> `.claude/skills/klein/references/synthesis-protocol.md`.

**The study in one paragraph.** Dehejia and Wahba's NSW files carry an answer key: 260
randomised-out controls give an experimental ATT of 1794.34 (1982 dollars) for the 185
trainees. Nine run ids (seven measured cells and two driver crashes) asked three questions of it. Do the published numbers come back
out of the authors' own files? Mostly: 9 of 11 development targets and 3 of 5 sealed
CPS-1 targets reproduce within ±1, and the four misses trace to one inconsistency in
the paper's own Table 3, found at METHOD before any cell ran (**[C1]**, **[C6]**). How
far does a naive contrast miss? By more than the benchmark itself, with the wrong sign:
-15204.78 against PSID-1 (**[C2]**). Do 1999-vintage propensity-score estimators
recover the benchmark? On PSID-1 one of three lands within $1000 (AIPW, gap +889.48);
IPW and 1-NN matching miss by almost the same amount on opposite sides (**[C3]**,
**[C11]**). Carried unchanged to the sealed CPS-1 lane, the selected AIPW lands at a gap
of -466.80 (**[C5]**). That last number is one sealed draw under one specification,
inside a bootstrap interval that also contains zero: it is consistency with the
benchmark, not evidence that selection on observables holds.

**Scope — read before any claim.**

1. **One specification per estimator.** IPW, AIPW and matching all use Table 3 note c's
   13-term PSID-1 logit (`dw_psid`). The only specification variation is one IPW cell
   without 1974 earnings (`no_re74`), which also adds a 1975 zero-earnings flag and is
   therefore not Dehejia-Wahba's Table 5 Spec 7 (method card §3). No specification
   family was run and no covariate balance after weighting was measured.
2. **What the interval is.** Every att interval is a percentile bootstrap of 500 draws
   (fixed seed `20261103`) that resamples treated and comparison men separately and
   re-fits the logit in each draw, but holds the 260 NSW controls fixed. It is an
   interval for the ATT estimate with the benchmark held fixed, not an interval for the
   gap. For 1-NN matching it is not a valid confidence interval at all
   (`ref:abadie2008`) and is reported as descriptive. The registered rules read only
   point gaps, so no verdict depends on an interval.
3. **Selection on the development lane.** The sealed estimator was chosen by the
   registered rule — smallest absolute gap among P2-P4, i.e. by comparing each PSID-1
   estimate with the experimental answer key. The PSID-1 gaps are in-sample with
   respect to that selection. Only E0009 is out-of-sample for the att track, and it is
   one draw.
4. **Multiplicity.** The four PSID-1 att cells are a family with no family-wise
   adjustment, so under the profile's doctrine they stay exploratory. The two sealed
   cells are single pre-registered cells.
5. **Crashes and the incident.** E0003 and E0004 are driver-error crashes with no
   scientific content (a foreground tool timeout killed `klein run-one`; a re-launch on
   the restored IPW cell was then killed, exit 143); the matching cell ran as E0005. A
   lead operator error — a cherry-pick and `git reset --keep` in the experimenter's
   checkout while E0005 was finishing — removed E0005's evidence commits from the branch
   and misnumbered the next (AIPW) cell. The lead killed that run before it printed a
   number, reset the unpushed branch to the fully filed E0005, and the AIPW cell ran as
   E0006; every leftover is preserved in `incidents/2026-11-03-e0005-history-repair/`
   and `klein verify` passes after the repair. The killed run is not evidence and is
   not cited as such.
6. **What the replication shows.** rep:E0001@20261103T065031Z and
   rep:E0006@20261103T065104Z are exact re-executions — same candidate commit, data
   fingerprint, environment fingerprint and bootstrap seed — and reproduced every
   printed value except wall time with difference 0. They establish that the pipeline is deterministic,
   not that the results are stable under other code, seeds or specifications. Neither
   sealed cell (E0008, E0009) was re-executed.
7. **Where the targets come from.** Every published value was transcribed from the NBER
   working paper (`ref:dehejia1998nber`, `w6586`). The JASA article text was not
   accessed (`ref:dehejia1999`), so "identical to the JASA Table 3" is unchecked.
8. **Two budget re-records, both before the evidence they enabled, neither touching a
   prediction, rule, target or cell.** `estimators.max_experiments` 4 → 6 after the two
   crashes; `max_run_seconds` and the att `wall_seconds` guardrail 900 → 10800 and the
   confirmation `budget_seconds` 2400 → 14400 after the first sealed att dry run timed
   out (program.md 2026-11-03, both `Decision (lead)` lines; the consult gate was
   re-recorded each time).

## ① Research-question verdicts

`confirmed` below means the track holds a sealed run AND a replication record
(`confirmation.require: [sealed, replicate]`) and the claim cites at least two evidence
kinds; on this study the replication is an exact re-execution (scope item 6).

| Claim | RQ | Track | Verdict | Strength | Class | Evidence | Result + uncertainty |
|---|---|---|---|---|---|---|---|
| **[C1]** | RQ1 | reproduction | **refuted** (as registered) | confirmed | empirical-description | E0001, E0008, rep:E0001@20261103T065031Z, art:repro_psid1, art:repro_cps1 | The published targets do not all reproduce within the registered tolerance of 1 dollar: 9 of 11 development targets and 3 of 5 sealed CPS-1 targets do, and the four misses are exactly the comparison-group adjusted estimates and their standard errors (PSID-1 217.94 and 866.20 against a printed 731 and 886; CPS-1 738.83 and 547.05 against 972 and 550) |
| **[C2]** | RQ2 | reproduction | **supported** (the scouted prior, a miss of about $17,000, held) | confirmed | empirical-description | E0001, E0008, rep:E0001@20261103T065031Z, art:repro_psid1, art:repro_cps1 | The naive difference in means against PSID-1 is -15204.78 (s.e. 1154.61) against the experimental 1794.34 (s.e. 632.85), the wrong sign and a miss larger than the benchmark itself; against the sealed CPS-1 lane it is -8497.52 (s.e. 712.02) |
| **[C3]** | RQ3 | att | **refuted for IPW and matching, supported for AIPW** | exploratory | empirical-description | E0002, E0005, E0006, rep:E0006@20261103T065104Z, art:att_e0002, art:att_e0005, art:att_e0006 | On PSID-1 with the Dehejia-Wahba logit only AIPW lands within 1000 dollars of the experimental estimate: the gaps are +1244.09 (IPW), -1234.06 (1-NN matching) and +889.48 (AIPW), and all three percentile-bootstrap intervals contain the benchmark 1794.34 |
| **[C4]** | RQ4 | att | **supported** | exploratory | empirical-description | E0007, E0002, art:att_e0007, art:att_e0002 | Dropping every 1974-earnings term moves the IPW estimate on PSID-1 from 3038.44 to -15.33 (gap -1809.67), yet its bootstrap interval [-2642.44, 2471.35] still contains the benchmark: 1974 earnings is load-bearing for the point estimate under this one specification, not demonstrably for the interval |
| **[C5]** | RQ5 | att | **supported** | confirmed | empirical-description | E0009, E0006, rep:E0006@20261103T065104Z, art:att_e0009 | Carried unchanged to the sealed CPS-1 lane, AIPW with the PSID-1 logit estimates an ATT of 1327.54 with bootstrap interval [-129.17, 2835.62], a gap of -466.80 against the benchmark, on 4493 comparison men whose largest single weight share is 0.0426 |

Two further measured verdicts, from the same cells, that no single RQ asks for:

| Claim | Track | Strength | Class | Evidence | Statement |
|---|---|---|---|---|---|
| **[C6]** | reproduction | confirmed | empirical-description | E0001, E0008, rep:E0001@20261103T065031Z, art:repro_psid1, art:repro_cps1, ref:dehejia1998nber | Table 3 column (2) is two regressions: note a's covariate list reproduces Table 2 Panel C column (4) on all three lanes (1672.20, 217.94 and 738.83 against 1672, 218 and 739), which is the printed NSW value, while the printed PSID-1 and CPS-1 values (731, 972) are Panel C column (5), which neither all-covariates reading recovers (PSID-1 795.02 or 67.28; CPS-1 793.59 or 1137.20) |
| **[C7]** | att | exploratory | empirical-description | E0002, E0005, E0006, E0009, art:att_e0002, art:att_e0005, art:att_e0006, art:att_e0009 | On PSID-1 the common-support trim keeps 1146 of 2490 comparison men and one of them carries 0.135 of the odds-weight mass (IPW and AIPW), while 1-NN matching uses 56 distinct men with one matched to a 0.146 share of the trainees; on sealed CPS-1 the trim keeps 4493 men and the largest share is 0.0426 |

**Reading the verdicts together.** The reproduction track says the files are the
paper's files: every unadjusted value, every count and the whole NSW row reproduce to
within a dollar, and the classical OLS standard-error formula matches on every target it
can be checked on (E0001, E0008), so RQ1's prior worry about the SE formula did not
materialise. What fails is the paper's table, not the pipeline (**[C6]**). The att
track says the opposite of "propensity methods recover the benchmark" on PSID-1 and
something weaker than it on CPS-1: three estimators on one score span 560.28 to 3038.44
on PSID-1 (E0005, E0002), each resting on a handful of men (**[C7]**), and the selected
one transfers to CPS-1 within the band (**[C5]**).

## ② Registered predictions (from the ledger)

Copied from `uv run --no-sync klein predict list` on 2026-11-03, never re-decided
here: **3 supported, 4 refuted, 0 inconclusive, 0 open.** The `Card P(holds)` column is
the method card's §4 expectation, written at METHOD after the predictions were hashed
and before any cell ran; it is descriptive, not a calibration score.

| P# | Statement (short) | Rule | Observed | Verdict (ledger) | Card P(holds) | Evidence | Decision |
|---|---|---|---|---|---|---|---|
| P1 | every development target (4 estimates, 4 SEs, 3 sizes) within ±1 | `{key: primary_metric, op: "<=", value: 0}` | `targets_outside_tolerance` 2 | **refuted** | 0.25 | E0001 | program.md 2026-11-03: "Decision: P1 REFUTED by the notary at E0001 … the refutation is the finding: Table 3 column (2) PSID-1 is not the note-a regression" |
| P2 | odds-weighted IPW on the PSID-1 logit within $1000 | `{key: att_gap_usd, op: abs_le, value: 1000}` | gap +1244.09 | **refuted** | 0.45 | E0002 | program.md 2026-11-03: "Decision: P2 REFUTED at E0002 … IPW remains the tie-break baseline of the selection rule" |
| P3 | AIPW (same weights, OLS outcome model) within $1000 | `{key: att_gap_usd, op: abs_le, value: 1000}` | gap +889.48 | supported | 0.50 | E0006 | — |
| P4 | 1-NN matching with replacement within $1000 | `{key: att_gap_usd, op: abs_le, value: 1000}` | gap -1234.06 | **refuted** | 0.60 | E0005 (E0003, E0004 are driver crashes on the same cell) | program.md 2026-11-03: "Decision: P4 REFUTED at E0005 … direction is opposite to IPW" |
| P5 | IPW without any 1974-earnings term misses by more than $1000 | `{not: {key: att_gap_usd, op: abs_le, value: 1000}}` | gap -1809.67 | supported | 0.70 | E0007 | — (but see **[C13]**: this rule could not discriminate) |
| P6 | sealed CPS-1: 2 estimates, 2 SEs and 1 size within ±1 | `{key: primary_metric, op: "<=", value: 0}` | `targets_outside_tolerance` 2 | **refuted** | 0.25 | E0008 | program.md 2026-11-03: "Decision: P6 REFUTED at E0008 … No re-run: the track's sealed access is spent" |
| P7 | the PSID-1-selected estimator, specification unchanged, within $1000 on sealed CPS-1 | `{key: att_gap_usd, op: abs_le, value: 1000}` | gap -466.80 | supported | 0.60 | E0009 | — (selection recorded before any sealed access: "Decision: by the registered rule … AIPW with spec dw_psid unchanged, selected from E0006") |

**[C8]** *(procedural-verdict, confirmed; evidence P1, P2, P3, P4, P5, P6, P7, E0001,
E0002, E0005, E0006, E0007, E0008, E0009)* — The notary adjudicated all seven registered predictions: 3 of 7 supported (P3, P5, P7), 4 of 7 refuted (P1, P2, P4, P6) and 0 of 7 inconclusive or open, and each refutation carries a dated Decision line in program.md

**Foreseeability, stated rather than hidden.** Two of the four refutations were
foreseen before any cell ran, though after the predictions were hashed: the METHOD
gate's cross-read of Table 3 against Table 2 named the exact targets P1 and P6 would
miss and the values they would reproduce near (card §4: 218 / 866 and 739 / 547; the
cells gave 217.94 / 866.20 and 738.83 / 547.05). The predictions were deliberately left
as registered (program.md 2026-11-03, "METHOD finding … the registered predictions are
NOT changed"). Once P1 landed as foreseen, P6's outcome was nearly determined — the
card said so — so the sealed reproduction cell confirmed a pattern rather than testing
something open. RQ2's two values were seen at inspection (`scouting_ledger.md` S2) and
carry no prediction.

**Selection, on the record.** Absolute PSID-1 gaps: IPW 1244.09 (E0002), matching
1234.06 (E0005), AIPW 889.48 (E0006); no tie, AIPW selected, written as a dated
Decision before the first sealed dry run. The card had expected matching to be
selected (about 0.45); it was not.

## ③ Surprises and why

**1. The paper's Table 3 column (2) is not one regression — found at METHOD, confirmed
on both lanes.** The registered targets were transcribed from Table 3 (scouting ledger
S3). Only when the method scholar read Table 2 beside it did the mismatch show: the NSW
adjusted value (1672 / 638) is Table 2 Panel C column (4), note a's covariates, while the
PSID-1 (731 / 886) and CPS-1 (972 / 550) values are Panel C column (5), "all
pre-treatment covariates". The anchor cell's never-counted diagnostic rows settled the
column-(4) half on every lane (**[C6]**). The column-(5) half is open: two readings of
"all pre-treatment covariates" (adding `married`; adding `married`, `u74`, `u75`) give
795.02 and 67.28 against 731 on PSID-1, 793.59 and 1137.20 against 972 on CPS-1, and
1675.86 and 1669.84 against 1655 on NSW (art:repro_psid1, art:repro_cps1).

**[C10]** *(mechanism-interpretation, exploratory; evidence E0001, E0008,
art:repro_psid1, art:repro_cps1, art:card, ref:dehejia1998nber)* — The comparison-group adjusted values miss for an editorial reason, not a numerical one: Table 3 column (2) appears to be assembled from Table 2, printing Panel C column (4) in its NSW row and column (5) in its comparison rows under one note that lists column (4)'s covariates; column (5)'s covariate set is not printed and both readings tried failed, so which regression produced 731 and 972 remains unresolved

**2. IPW and matching miss on opposite sides, by almost the same amount, with the same
score.** The card's prior M5 expected every out-of-band PSID-1 gap to be negative (the
residual PSID men "earn too much"). Matching obliged (-1234.06, E0005); IPW did not
(+1244.09, E0002). AIPW, using IPW's weights plus an outcome model, moved IPW down from
3038.44 to 2683.82 (E0006), within the card's 500-dollar band for that shift (M4).

**[C11]** *(mechanism-interpretation, exploratory; evidence E0002, E0005,
art:att_e0002, art:att_e0005)* — IPW and 1-NN matching miss on opposite sides with the same score (+1244.09 and -1234.06) most plausibly because each counterfactual rests on a different handful of PSID-1 men, one man carrying 0.135 of IPW's weight and one a 0.146 share of matching's, so the sign of a miss tracks which few men are heavy rather than a shared bias of the comparison group; per-man weights were not pinned, so this is unresolved in detail

**3. Matching reproduced Dehejia-Wahba's control count but not their estimate —
unresolved.** E0005 used 56 distinct PSID-1 men, the count Dehejia-Wahba's Table 4
reports for the same design (card prior M2), yet estimated 560.28 where the paper prints
$1,691 for Table 3 column (7) (card §4). Equal counts suggest the support and the score
are close; different estimates say the matched men differ in who, not how many.
Candidate explanations from the card's §3, none tested: the files' zero-earnings flags
`u74`/`u75` standing in for the paper's "unemployed" in the `u74·black` term; this
study's trim-before-match order; the tie rule. Recorded as unresolved; no mechanism is
claimed.

**4. The sealed AIPW gap is smaller than its development gap, and of the other sign.**
Selection on PSID-1 would, if anything, make the selected estimator's development gap
look better than its true performance (a winner's-curse effect); the sealed CPS-1 gap
came out smaller instead: -466.80 (E0009) against +889.48 (E0006). The two lanes differ
in exactly the dimension the card's M8 named.

**[C12]** *(mechanism-interpretation, exploratory; evidence E0006, E0009,
art:att_e0006, art:att_e0009, ref:imbens2025, ref:dehejia1998nber)* — The sealed AIPW gap (-466.80) is smaller than its development gap (+889.48) most plausibly because CPS-1 overlaps the trainees better, with 4493 men on support against 1146 and a largest weight share of 0.0426 against 0.135, so the counterfactual rests on many men instead of a few; one sealed draw cannot separate this from luck, and agreement with the benchmark does not show that selection on observables holds

**5. P5 was supported, but its rule could not have failed for the reason it was
written.** RQ4 asks whether 1974 earnings is load-bearing. P5 scores that as "the
no-RE74 IPW misses the benchmark by more than $1000". But IPW with 1974 earnings
already missed by more than $1000 (E0002). Had RE74 been irrelevant, the no-RE74
estimate would have sat near 3038.44 and P5 would still have been supported. The
evidence that RE74 matters is the card's M6, stated against the baseline cell: -15.33
(E0007) against 3038.44 (E0002), lower by more than the card's 1,000-dollar margin.

**[C13]** *(research-discipline, exploratory; evidence E0002, E0007, P5, art:card)* — A sensitivity prediction scored against the benchmark band cannot separate the covariate mattering from the estimator missing anyway: IPW missed the 1000-dollar band both with 1974 earnings (gap +1244.09) and without them (estimate -15.33 against 1794.34), so P5 would have been supported had 1974 earnings been irrelevant; a rule stated against the baseline cell, as the card's own prior was, is the test that discriminates

**6. The method card's staked priors, scored.** Every prior below is decided from values
the registered cells printed; none needed an extra run.

| Prior | Claim (card §4, abridged) | Observed | Held? |
|---|---|---|---|
| M1 | IPW `max_weight_share` ≥ 0.05 (likely 0.10-0.40) | 0.135 (E0002) | held |
| M2 | matching uses 40-75 distinct men and `max_weight_share` ≥ 0.05 | 56 and 0.146 (E0005) | held |
| M3 | note-g trim keeps between 1,000 and 1,300 PSID-1 men | 1146 (E0002, E0006) | held |
| M4 | AIPW and IPW differ by at most 500 dollars | 2683.82 against 3038.44 (E0006, E0002) | held |
| M5 | every out-of-band P2-P4 gap is negative | IPW +1244.09 (E0002) | **falsified** |
| M6 | dropping 1974 earnings lowers IPW by more than 1,000 dollars | -15.33 against 3038.44 (E0007, E0002) | held |
| M7 | misses confined to the comparison-group adjusted value and SE, near 218 / 866 and 739 / 547 | exactly those four, 217.94 / 866.20 and 738.83 / 547.05 (E0001, E0008) | held |
| M8 | CPS-1 `max_weight_share` below the selected estimator's PSID-1 share | 0.0426 against 0.135 (E0009, E0006) | held |

**[C9]** *(empirical-description, exploratory; evidence E0001, E0002, E0005, E0006,
E0007, E0008, E0009, art:card)* — Of the method card's eight staked priors 7 of 8 held; the falsified one, that every out-of-band PSID-1 gap is negative, fell to IPW's +1244.09, and the card's leaning for 1-NN matching (holds, 0.60) missed at -1234.06

**Not surprises, but on the record (aux_metrics.tsv).** Prediction health: every att
cell estimated on n = 185 treated, and the clamp that `analyze.py` applies when a
percentile bound would exclude the point never fired — each printed `ci_low` and
`ci_high` equals the pinned table's percentile, and every point estimate lies strictly
inside its interval (art:att_e0002 … art:att_e0009). Cost: matching 24.28 s, IPW 313.43
s, IPW without RE74 388.07 s, AIPW 639.89 s on PSID-1, and the sealed AIPW 1227.74 s on
CPS-1; the reproduction cells took 0.14 s and 0.46 s. The machine was shared with
sibling exhibits (program.md), so these are not clean cost comparisons — the AIPW
replication took 904.60 s for the identical computation. The sealed att dry run on
PSID-1 data (`tables/att_DRYRUN.tsv`) printed E0006's numbers exactly (gap 889.48), a
third, informal determinism check.

## ④ Practical advice

**[C14]** *(research-discipline, exploratory; evidence E0001, E0008, art:card,
art:repro_psid1, art:repro_cps1)* — Cross-read every printed target against the paper's other tables before registering a replication: comparing Table 3 with Table 2 at METHOD explained both reproduction refutations before any cell ran, so the anchor's STOP rule could tell a known inconsistency in the paper from a broken pipeline

*How:* for each target you transcribe, find every other place the paper prints the same
quantity (a robustness table, an appendix, a text sentence) and record which column it
equals. Put the cross-reads in the reproduction cell as never-counted diagnostic rows, as
`lib/lalonde.py:PANEL_C` does here.

**[C15]** *(research-discipline, exploratory; evidence E0002, E0005, E0006, E0009,
art:att_e0002, art:att_e0005, art:att_e0006, art:att_e0009)* — Print the weight-concentration pair, the largest single weight share and the number of comparison units used, with every weighting or matching estimate and read it before the point estimate: PSID-1 shares of 0.135 (IPW, AIPW) and 0.146 (matching) said each estimate rested on a few men, which the 0.0426 share on CPS-1 did not

**[C16]** *(research-discipline, exploratory; evidence E0002, E0005, E0006, E0009,
art:att_e0002, art:att_e0005, art:att_e0006, art:att_e0009)* — Treat a registered selection among estimators whose intervals overlap as a tie-break, not a ranking: AIPW won on PSID-1 at a gap of +889.48 against +1244.09 and -1234.06, inside intervals that all contain the benchmark, and only the sealed cell at -466.80 speaks for the selected estimator, once

**[C17]** *(research-discipline, exploratory; evidence E0002, E0005, E0006, E0007,
E0009, ref:abadie2008, art:card)* — Say what the interval is for: a percentile bootstrap of 500 draws that re-fits the score but holds the experimental controls fixed is an interval for the ATT estimate, not for its gap to the benchmark, and for 1-NN matching it is descriptive only; resample the controls, or use an analytic variance, before quoting coverage of a benchmark

**[C18]** *(research-discipline, exploratory; evidence E0003, E0004, art:results,
art:contract)* — Give the loop driver's own tool timeout more room than the run's max_run_seconds and set the cell before launching: E0003 (a wrapper timeout killed run-one mid-run, recovered as a crash) and E0004 (launched on the restored IPW cell, then killed with exit 143) spent two of the four estimator slots and forced a budget re-record

**[C19]** *(research-discipline, exploratory; evidence E0005, E0006, art:incident)* — Never commit, cherry-pick or reset in a checkout where a run-one may be in flight: the lead's reset removed E0005's filed evidence commits and misnumbered the next cell, and the repair (reset to the fully filed E0005, AIPW re-run as E0006, every leftover preserved) is a recovery, not a routine

**[C20]** *(research-discipline, exploratory; evidence E0009, art:dryrun_att_timeout,
art:dryrun_att_ok, art:contract)* — Read the sealed rehearsal's exit code as a budget measurement: the first ATT dry run hit the 900-second limit (exit 124) on PSID-1 data under load, and the sealed CPS-1 cell later took 1227.74 seconds, so launching at the old limit would most likely have spent the track's only sealed access on a timeout

**[C21]** *(research-discipline, exploratory; evidence rep:E0001@20261103T065031Z,
rep:E0006@20261103T065104Z, art:rep_e0001, art:rep_e0006)* — Call an exact re-execution what it is: the same commit, data, environment and seed reproduced every printed value of E0001 and E0006 with a difference of 0 except the wall time (904.60 seconds against 639.89 for E0006), which shows the pipeline is deterministic and says nothing about robustness to code, seed or specification

For an analyst on their own observational data, in order:

1. Name the estimand and get a benchmark if one exists at all — a randomised arm, a
   pilot, a known-null placebo outcome. Here the naive PSID-1 contrast was -15204.78
   against 1794.34 (**[C2]**); without the benchmark nothing below could be judged.
2. Pin the overlap diagnostics before the estimate (**[C15]**) and the common-support
   count (1146 of 2490 on PSID-1, **[C7]**). If one unit carries a share of the weight like
   PSID-1's 0.135, report the estimate as "a few people", not as a population quantity.
3. Run more than one estimator on the same score and read the spread as uncertainty:
   560.28, 2683.82 and 3038.44 on PSID-1 (**[C3]**) is a range, not three candidates for
   the answer.
4. Write sensitivity predictions against the baseline cell, not the benchmark band
   (**[C13]**).
5. Say what your interval covers (**[C17]**) and call a same-seed re-run determinism
   (**[C21]**).

## ⑤ What the decision-maker should take from this

**The estimand.** The average effect of the NSW job-training programme on 1978
earnings (1982 dollars) for the men who took it — the ATT over the 185 trainees in
Dehejia-Wahba's subsample, all of them kept (the common-support trim drops comparison
men only, so the estimand never changes).

**The experimental answer.** 1794.34 (s.e. 632.85) as a difference in means, 1672.20
(s.e. 638.40) adjusted for note a's covariates (E0001, art:repro_psid1). This is the
number every other row is judged against.

**What the observational designs say, and how far each sits from it.**

| Design | Comparison group | Estimate | Interval (percentile bootstrap) | Gap to 1794.34 | Evidence |
|---|---|---|---|---|---|
| naive difference in means | PSID-1 | -15204.78 (s.e. 1154.61) | — | wrong sign | E0001 |
| naive difference in means | CPS-1 (sealed) | -8497.52 (s.e. 712.02) | — | wrong sign | E0008 |
| OLS with note a's covariates | PSID-1 | 217.94 (s.e. 866.20) | — | below | E0001 |
| OLS with note a's covariates | CPS-1 (sealed) | 738.83 (s.e. 547.05) | — | below | E0008 |
| IPW, PSID-1 logit | PSID-1 | 3038.44 | [976.01, 4501.30] | +1244.09 | E0002 |
| AIPW, PSID-1 logit | PSID-1 | 2683.82 | [689.10, 4101.53] | +889.48 | E0006 |
| 1-NN matching, PSID-1 logit | PSID-1 | 560.28 | [-619.80, 3857.86] (descriptive only) | -1234.06 | E0005 |
| IPW, logit without 1974 earnings | PSID-1 | -15.33 | [-2642.44, 2471.35] | -1809.67 | E0007 |
| AIPW, PSID-1 logit unchanged | CPS-1 (sealed) | 1327.54 | [-129.17, 2835.62] | -466.80 | E0009 |

**The assumption every propensity row rests on.** Selection on observables: given age,
schooling, race, marriage, degree and earnings in 1974 and 1975, whether a man is a
trainee or a survey respondent is unrelated to what he would have earned untrained in
1978 — plus overlap, which PSID-1 barely has (before any weighting the trainees differ
from PSID-1 men by standardized mean differences of -1.84 in `married`, -1.77 in `re75`,
-1.72 in `re74` and 1.48 in `black`; CPS-1 differs by 2.43 in `black`; data card). This
study does not test the assumption; the benchmark only tells us, for these files,
whether a given estimate happened to agree.

**What to take from it.**

- With only PSID-1 and these tools you could not have told which of 560.28, 2683.82
  and 3038.44 was right: their intervals overlap each other and the truth (**[C3]**).
  Report such a set as "under unconfoundedness the estimated ATT lies between 560.28 and
  3038.44 depending on the estimator, and each estimate rests on a few people"
  (**[C7]**), never as one number.
- With the larger CPS-1 pool the selected estimator, under unconfoundedness, gives an
  estimated ATT of 1327.54 with an interval that runs from -129.17 to 2835.62
  (**[C5]**): it recovers the experimental benchmark within the registered $1000 band,
  and the interval does not exclude zero.
- Dropping one covariate (1974 earnings) moved the PSID-1 IPW estimate from 3038.44 to
  -15.33 (**[C4]**): the answer depends on the specification, and this study ran one
  specification per estimator.

**What would change these conclusions.** A placebo outcome (1975 earnings as the
outcome, with the 1975 terms removed from the score) that does not come out near zero
would say the CPS-1 agreement is luck, as Imbens (2015) and Imbens-Xu (2025) found on
these files (`ref:imbens2015`, `ref:imbens2025`). A specification family in which the
CPS-1 gap moves outside $1000. An interval that also resamples the 260 controls, which
would widen every row. Nothing here is priced: the contract registers no `materiality:`
block, so no claim asserts value beyond the registered $1000 band it cleared or missed.

## ⑥ Literature tie-back

All 18 rows of `references.yaml` were verified at METHOD (2026-11-03, `klein refs
verify`: 0 failed). The references behind `confirmed` claims are `ref:dehejia1998nber`
(**[C6]**); every other reference sits behind exploratory claims or appears in prose
only. Literature values below are copied from the method card's §4, which cites them.

- **`ref:lalonde1986` — matched.** The naive contrast misses by more than the
  experimental estimate itself and with the wrong sign on both comparison groups (**[C2]**): LaLonde's lesson
  reproduces in one row.
- **`ref:dehejia1999` / `ref:dehejia1998nber` — the targets reproduce, the
  propensity numbers do not.** Dehejia-Wahba report propensity estimates from $1,473 to
  $1,774 on these files, and on PSID-1 specifically $1,608 (stratification) and $1,691
  (1-NN matching). This study's 1999-style estimators on their PSID-1 logit gave 3038.44
  (IPW), 2683.82 (AIPW) and 560.28 (matching) — none inside their range — while using
  the same 56 matched men their Table 4 reports (③, item 3; unresolved). On CPS-1 they report
  $1,713 / $1,582 with a CPS-specific logit (note e); with the PSID-1 logit held fixed,
  a deliberately harder transfer, this study's AIPW gave 1327.54 (**[C5]**). Separately,
  their Table 3 column (2) mixes two of their Table 2 columns (**[C6]**, **[C10]**).
- **`ref:smith2005` — matched.** Smith and Todd's point that agreement with the
  benchmark depends on the specification and the estimator holds in miniature: one
  covariate moved IPW by more than the benchmark's size (**[C4]**), and three estimators
  on one score spread over more than the benchmark's size (**[C3]**).
- **Dehejia-Wahba's own no-RE74 sensitivity (Table 5 Panel B, card §4) — direction
  matched, magnitude did not.** Their weighting-type estimates fell to −$869 / −$1,023
  while matching held at $1,727 / $1,340; this study's no-RE74 IPW fell to -15.33
  (E0007). Its specification is not their Spec 7 (it adds `u75`), so this is a
  comparison of directions only.
- **`ref:kang2007` — not triggered here.** Double robustness was no rescue in Kang and
  Schafer's design; here AIPW moved IPW toward the benchmark (3038.44 to 2683.82,
  **[C3]**) and was the only PSID-1 estimator within the band, but its interval is as
  wide as IPW's, so "AIPW is better" is not a conclusion this study can draw (**[C16]**).
- **`ref:abadie2008`, `ref:abadie2006`, `ref:abadie2016` — honoured by disclosure.** The
  matching interval is descriptive (**[C17]**); no valid matching variance was
  computed.
- **`ref:imbens2015`, `ref:imbens2025` — consistent.** Imbens-Xu report estimates on
  LDW-PSID from $4 to $2,420 across ten modern estimators, which "fail to recover the
  ATT" there, and CPS estimates near the benchmark with failing placebo tests. This
  study's PSID-1 spread (-15.33 to 3038.44 across four cells) and its CPS-1 agreement
  (**[C5]**) sit on the same pattern; no placebo was run (⑦, item 1).
- **`ref:crump2009` — the road not taken.** Trimming treated men by score would change
  the estimand (Imbens-Xu's trimmed LDW-PSID benchmark is $306, not 1794.34); note g's
  comparison-only trim kept the benchmark comparable.
- **`ref:rosenbaum1983`, `ref:robins1994`, `ref:bang2005`, `ref:santanna2020`,
  `ref:imbens2004`, `ref:dehejia2002`, `ref:dehejia2005`** — the method's theory and the
  Smith-Todd exchange; cited for the design, not tested by a cell.

**Where this sits against the trend.** The field since 1999 has moved to overlap-first
design, flexible nuisance models inside doubly robust estimators, and validation by
placebo outcomes (method card §5). This study deliberately used the 1999 toolkit, as a
replication should; what it adds is the audit discipline — registered gaps, pinned
weight diagnostics, a sealed second comparison group — and the documentary finding that
the paper's own table mixes two regressions.

**Priors' scorecard (knowledge vs uninformed; scouted excluded).**

| RQ | Prior | Source | Outcome | In the scorecard? |
|---|---|---|---|---|
| RQ1 | likely, about 0.7 | scouted (two of the targets were seen) | refuted at ±1 (**[C1]**) | no — scouted |
| RQ2 | a miss of about $17,000 | scouted | held (**[C2]**) | no — scouted |
| RQ3 | about even, 0.5-0.6 for each estimator | knowledge (recalled, verified at METHOD) | 1 of 3 held (AIPW) | yes |
| RQ4 | likely, about 0.6 | knowledge (recalled, verified at METHOD) | held (**[C4]**), though the rule could not discriminate (**[C13]**) | yes |
| RQ5 | about even, 0.55 | uninformed | held (**[C5]**) | yes |

Knowledge-sourced priors: 2 of 4 forecasts held, each made at about even to "likely".
The one uninformed prior held at 0.55. On four knowledge forecasts and one uninformed
one, neither source outpredicted the other in any sense a later study could lean on.
The knowledge priors were recalled from the literature rather than read from a
`knowledge/` document; the repository's seed card
(`knowledge/method_cards/causal-propensity-methods.md`) says that under poor overlap
"estimates are driven by a few heavily weighted units", which **[C7]** bears out.

## ⑦ What to try next

1. **A registered placebo-outcome cell, on both comparison groups.** 1975 earnings as
   the outcome, the 1975 terms removed from the score, the same three estimators, a
   rule of the form "placebo ATT within a registered band of zero". This tests the
   identification assumption that agreement with the benchmark cannot (method card §4;
   `ref:imbens2015`). It is the single most informative next cell.
2. **A registered specification family as a measurement sweep.** Note c (PSID), note e
   (Dehejia-Wahba's CPS logit), their Table 5 Spec 7 exactly, and Smith-Todd variants,
   crossed with IPW, AIPW and matching, with `kleinlib.metrology.family_maxt` across the
   family and a forest plot against the 1794.34 reference line; add covariate balance
   after weighting. This turns "one specification per estimator" into a sensitivity
   curve and tests whether P7's hold survives a CPS-specific score.
3. **Fix the uncertainty and test [C11] directly.** A bootstrap that also resamples the
   260 NSW controls (an interval for the gap itself); the Abadie-Imbens analytic
   variance for matching (`ref:abadie2006`, `ref:abadie2016`); and a pinned per-cell
   table of the top-weighted comparison men (id, weight, `re78`), which would show
   whether the IPW and matching misses come from different handfuls of men, and why
   matching on 56 men gives 560.28 instead of the paper's $1,691.
4. **Recover Table 2 Panel C column (5)'s covariate set (open hypothesis H5).** A
   registered sweep over candidate covariate lists scored against 731, 972 and 1655,
   or the JASA text; and an independent re-implementation (different code, a different
   bootstrap seed) so that "replicated" means robust, not only deterministic.

*Candidates for `knowledge/` (not promoted at this stage):* **[C6]** and **[C7]** to a
future `knowledge/domains/data-science/`; **[C13]**, **[C18]**, **[C19]**, **[C20]** and
**[C21]** to `knowledge/research-discipline.md`, each with its typed citation
`(supports 23-lalonde-causal-replication#Cn)`.
