# Program — 23-lalonde-causal-replication

## Roster

Who is doing what, and on what. REFEREE cites this table for the independence rung
(`references/referee-protocol.md`); a blank `experimenter` row caps the achievable
rung at "fresh session", because no artifact then says what ran the loop. Fill the
experimenter row at CONSULT and update a row whenever its model, tool or session
changes.

| Role | Who (model · tool · session) | Since |
| --- | --- | --- |
| consultant | lead agent (Claude Code orchestrating session) — drafted the contract | 2026-11-03 |
| experimenter | `klein-experimenter` subagent (Sonnet tier) · Claude Code · a fresh subagent context per phase | 2026-11-03 |
| data-gate auditor | `klein-data-auditor` subagent (Sonnet tier) · Claude Code | 2026-11-03 |
| method scholar | `klein-method-scholar` subagent (Opus tier) · Claude Code | 2026-11-03 |
| synthesist | `klein-synthesist` subagent (Opus tier) · Claude Code | 2026-11-03 |
| referee | `klein-referee` subagent (Opus tier) · Claude Code · fresh context that never saw the loop (rung: different model than the experimenter) | 2026-11-03 |
| lead | lead agent, acting on the repository owner's delegation | 2026-11-03 |

**Acknowledgements are delegated.** The repository owner approved the Klein 2.3 plan
that commissions this exhibit, and that approval delegates the CONSULT, DATA, METHOD
and phase acknowledgements of exhibits 20-24 to the lead agent; each is recorded as
`--acknowledged-by lead-agent` with this note, the convention studies 10-15 used.
The referee verdict is never delegated: it is the referee subagent's own.

This is the living lab notebook. `study.yaml` is the machine contract;
`study_state.json`, `events.jsonl`, and `runs/E####/manifest.json` are generated audit
state and must not be hand-edited.

## Goal and track contract

- Goal: Does the Dehejia-Wahba NSW experimental benchmark (about $1,794) reproduce from the authors' own files, how far does a naive non-experimental comparison miss it, and do propensity-score estimators recover it on PSID-1 and then, sealed, on CPS-1?
- Tracks (both registered):
  - `reproduction` — `targets_outside_tolerance` (exact; resolution one target): how
    many of Dehejia & Wahba's printed Table 3 (1)-(2) values and Table 1 sizes the
    cell misses by more than +-1.
  - `att` — `att_usd`, an ATT point estimate in 1982 dollars with a percentile
    bootstrap interval; predictions read `att_gap_usd`, its distance from the
    experimental estimate computed in the same run from the NSW controls.
- Predictions P1-P7 are registered in study.yaml with arithmetic rules.
- Results are exploratory until each track's one sealed CPS-1 cell and a
  replication record confirm them (`confirmation.require: [sealed, replicate]`).

## Data and split

- Sources: `nsw_dw.dta` (data.source) and `psid_controls.dta`, `cps_controls.dta`
  (data.inputs), each a `url:` pin with sha256, from Dehejia's NBER data page.
- Predefined lanes (`data.split.kind: predefined`, column `partition`):
  train = the NSW experimental sample (185 treated + 260 controls),
  development = PSID-1 (2,490), test = CPS-1 (15,992) — sealed.
- Adaptive work uses train + development only. CPS-1 is read once per track.
- Gate 1 records the prepared-data SHA-256 and split-policy fingerprint.

## Phases and registered predictions (mirror of study.yaml)

| Phase | Cells | Predictions |
| --- | --- | --- |
| anchor | reproduction · development | P1 — all 11 development targets within +-1 |
| estimators | att · PSID-1: IPW, AIPW, 1-NN matching, IPW without RE74 | P2-P4 — |gap| <= $1,000; P5 — no-RE74 IPW |gap| > $1,000 |
| confirmation | reproduction · CPS-1 sealed; att · CPS-1 sealed (selected estimator) | P6 — all 5 CPS-1 targets within +-1; P7 — |gap| <= $1,000 |

Research questions RQ1-RQ5 and their priors are in study.yaml; RQ1 and RQ2 rest on
values seen at inspection and are labelled `(source: scouted)`.

## Workflow

1. `uv run --locked klein gate record consult --study . --acknowledged-by <name>`
2. Prepare data and write a `Decision: GO` data card; record the DATA gate.
3. Write the method card; record the METHOD gate.
4. Commit gate evidence, switch to `experiments/23-lalonde-causal-replication`, and run
   `uv run --locked klein preflight --study .`.
5. Set the cell in `analyze.py` (`CELL`), then
   `uv run --locked klein run-one --study . --track <reproduction|att> --tests P# --description ...`.

Every candidate is committed before execution. On a registered track the evidence
transaction always restores `analyze.py`; the candidate commit stays resolvable.

## Decisions (append-only)

- 2026-11-03 — schema-v3 study scaffolded from recipe `ds-causal`, typed
  replicate · tabular · data-science; the recipe's synthetic `make_data.py` removed.
- 2026-11-03 — Decision: two registered tracks (reproduction, att) rather than one,
  so the replication of the published numbers and our own estimators carry separate
  sealed numbers and separate claims.
- 2026-11-03 — Decision: CPS-1 is the sealed lane. The estimator is selected on
  PSID-1 by a registered rule (smallest |gap| among P2-P4; ties to IPW < matching <
  AIPW) and carried to CPS-1 with its PSID-1 specification unchanged (P7).
- 2026-11-03 — Decision: estimators and targets live in `lib/lalonde.py`, outside
  the mutable surface; a cell only selects lane, estimator and specification.
- 2026-11-03 — Note (after the consult gate): `KLEIN_SMOKE=1` checks of both tracks ran
  on the real prepared data (the sanctioned off-loop smoke); predictions were already
  hashed. Smoke output is not evidence.
- 2026-11-03 — DATA gate: the dataframe-mode leakage audit exposed a harness defect
  (scalar task and predefined split not reproduced); fixed in `kleinlib/leakage.py`,
  audit 7/7, recorded GO with cautions.
- 2026-11-03 — METHOD finding: Table 3 column (2) is not one regression. Its NSW value
  (1,672) is Table 2 Panel C column (4) — note a's covariates — while its PSID-1 (731)
  and CPS-1 (972) values are Panel C column (5), "all pre-treatment covariates". P1 and
  P6 are expected to miss on exactly the adjusted PSID-1 / CPS-1 value and its standard
  error. Decision: the registered predictions are NOT changed (they were registered
  before this was known; a refutation for this reason is itself the finding). The
  reproduction cell gains DIAGNOSTIC rows (never counted) that regress each lane under
  note a and under two readings of "all pre-treatment covariates", against Panel C
  columns (4) and (5), so the anchor shows which regression each printed value is.
  A P1 miss of exactly these targets is therefore explained in advance and does not
  trigger the anchor's STOP; any other miss does.

- 2026-11-03 — Decision: P1 REFUTED by the notary at E0001 (targets_outside_tolerance = 2;
  disposition measured). The two misses are exactly the pre-announced ones (psid1_adjusted
  731 vs 217.94; psid1_adjusted_se 886 vs 866.20), so the anchor's STOP does not fire; the
  registered prediction stays as registered and the refutation is the finding: Table 3
  column (2) PSID-1 is not the note-a regression. The anchor phase closes; estimators
  phase proceeds on lead's ack. No analyze.py or lib edit was made to chase the miss.

## Phase slates

At every phase start, run the slate ritual (references/phase-ritual.md):
propose 4-6 falsifiable candidates, score novelty / testability / expected
information 1-3, record the table and the chosen candidate here, and mirror
the ranked survivors into playbook.md "Next-best candidates".

### Phase anchor slate

| # | Candidate (falsifiable) | Novelty 1-3 | Testable 1-3 | Info 1-3 | Sum |
| --- | --- | --- | --- | --- | --- |
| 1 | Reproduction cell on the development lane as committed (Table 3 cols (1)-(2) + Table 1 sizes, plus never-counted diagnostic rows): 0 targets missed (P1) | 3 | 3 | 3 | 9 |
| 2 | Same cell with a HC-robust standard-error formula for the SE targets: only if 1 misses on SEs other than PSID-1 adjusted | 2 | 3 | 2 | 7 |
| 3 | Re-hash the three pinned files against the NBER page: only if 1 misses on a count or an unadjusted value | 1 | 3 | 2 | 6 |
| 4 | att cell (IPW, PSID-1) ahead of the anchor | 3 | 2 | 1 | 6 |

Chosen: #1 -- the anchor is the phase's single pre-registered cell (max_experiments 1); 2-3 are contingent follow-ups that the STOP rule forbids anyway, and 4 belongs to the estimators phase.

### Phase anchor reflection (E0001, measured, metric 2)

Notary: P1 refuted (primary_metric 2 <= 0 false). 9 of 11 targets reproduced within +-1:
NSW unadjusted 1794 / SE 633, NSW adjusted 1672 / SE 638 (diffs 0.15-0.40), PSID-1
unadjusted -15205 / SE 1154 (diffs 0.22, 0.61), and sizes 185 / 260 / 2490 (exact).
Experimental ATT 1794.34. Missed: psid1_adjusted 731 vs 217.94 (diff 513.06) and
psid1_adjusted_se 886 vs 866.20 (diff 19.80) -- exactly the targets the METHOD finding
predicted. Diagnostic rows (never counted): the PSID-1 note-a regression gives 217.94,
which matches Panel C column (4) (218, diff 0.06) and not column (5) (731); the two
"all pre-treatment covariates" readings give 795.02 (diff 64.02 from col 5) and 67.28
(diff 663.72); neither reading reproduces column (5) within +-1. The NSW lane: note a
matches col (4) 1672 (diff 0.20); the other NSW readings (1675.86, 1669.84) lie 2-4 from
col (4) and 15-21 from col (5) 1655. So the mixed-column explanation is confirmed for the
note-a side, but the exact covariate set behind column (5) is NOT recovered by either
reading tried; that remains open and costs nothing downstream (att cells use note a).
Standard-error formula (classical OLS) matched on every non-PSID-adjusted target, so
RQ1's SE worry did not materialise.

### Phase estimators slate

| # | Candidate (falsifiable) | Novelty 1-3 | Testable 1-3 | Info 1-3 | Sum |
| --- | --- | --- | --- | --- | --- |
| 1 | att IPW, dw_psid, 500 reps (P2): |gap| <= $1,000 | 3 | 3 | 3 | 9 |
| 2 | att 1-NN matching, dw_psid (P4): |gap| <= $1,000 | 3 | 3 | 3 | 9 |
| 3 | att AIPW, dw_psid (P3): |gap| <= $1,000 | 3 | 3 | 2 | 8 |
| 4 | att IPW, no_re74 (P5): |gap| > $1,000 | 3 | 3 | 3 | 9 |

Chosen order: P2, P4, P3, P5 (lead's order) -- IPW is the tie-break baseline of the selection rule, then the other two selection candidates, then the RE74 sensitivity, which does not enter selection. All four are pre-registered cells; the slate records order only.

### E0002 reflection (att, ipw, dw_psid, 500 reps; adjudicates P2)

ATT 3038.44, bootstrap 95% CI [976.01, 4501.30], gap +1244.09 vs experimental 1794.34, n_controls_used 1146 of 2490, max_weight_share 0.135 (13.5% of the control weight sits on one unit -- concentrated, as RQ3 feared). The CI covers the experimental value, but the point estimate misses the $1,000 band: P2 refuted by the notary.

- 2026-11-03 — Decision: P2 REFUTED at E0002 (|gap| 1244.09 > 1000). Odds-weighted IPW on DW's PSID-1 logit overshoots by about $1.2k with a heavy single-unit weight; the prediction stays as registered, IPW remains the tie-break baseline of the selection rule.

### E0003-E0005 reflection (att, match, dw_psid; adjudicates P4)

Process note (driver error, recorded as data): E0003 was interrupted when the experimenter's own foreground wrapper timeout killed `klein run-one` mid-run (stale lock removed after confirming no live run; `klein recover` filed it as a crash with NA). E0004 was then launched with `CELL` still on ipw (the notary restores the surface) and was killed by the experimenter before completing: crash, NA. Both are bugs of the loop driver, not bad ideas, and carry no scientific content. E0005 is the real P4 cell.

E0005: 1-NN matching with replacement, ATT 560.28, bootstrap 95% CI [-619.80, 3857.86], gap -1234.06 vs 1794.34, n_controls_used 56 (distinct matched controls), max_weight_share 0.146. The estimate undershoots by more than $1,000: P4 refuted by the notary.

- 2026-11-03 — Decision: P4 REFUTED at E0005 (|gap| 1234.06 > 1000). Matching on DW's PSID-1 logit lands about $1.2k below the benchmark on only 56 distinct controls with a wide CI; direction is opposite to IPW (E0002, +1244). The prediction stays as registered.

- 2026-11-03 — Incident (lead's operator error) and repair: a framework cherry-pick and a
  `git reset --keep` by the lead while E0005 was finishing removed E0005's evidence
  commits from the branch; the next cell (AIPW) started misnumbered as E0005. The lead
  killed that run before it produced any number, reset the unpushed branch to the fully
  filed E0005 (d25a53e) and re-applied the reflection. Full account and every leftover
  artifact: `incidents/2026-11-03-e0005-history-repair/`. `klein verify` passes after the
  repair. The AIPW cell (P3) re-runs as E0006.
- 2026-11-03 — Decision (lead): the `estimators` phase budget is raised from 4 to 6
  experiments. E0003 and E0004 were driver crashes (a tool timeout killed `run-one`;
  a run launched before the cell was set), recorded as crashes with NA; they spent two
  of the four slots the phase needs for its four PRE-REGISTERED cells, so P3 and P5
  could not run. Only `phases[estimators].max_experiments` changes — no prediction,
  rule, track, target or other budget — and the consult gate is re-recorded with this
  reason. The crashes stay in the ledger as evidence of the driver errors.
