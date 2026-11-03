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

## Phase slates

At every phase start, run the slate ritual (references/phase-ritual.md):
propose 4-6 falsifiable candidates, score novelty / testability / expected
information 1-3, record the table and the chosen candidate here, and mirror
the ranked survivors into playbook.md "Next-best candidates".

### Phase <id> slate

| # | Candidate (falsifiable) | Novelty 1-3 | Testable 1-3 | Info 1-3 | Sum |
| --- | --- | --- | --- | --- | --- |
