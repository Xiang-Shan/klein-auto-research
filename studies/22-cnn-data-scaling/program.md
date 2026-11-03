# Program — 22-cnn-data-scaling

## Roster

Who is doing what, and on what. REFEREE cites this table for the independence rung
(`references/referee-protocol.md`); a blank `experimenter` row caps the achievable
rung at "fresh session", because no artifact then says what ran the loop. Fill the
experimenter row at CONSULT and update a row whenever its model, tool or session
changes.

| Role | Who (model · tool · session) | Since |
| --- | --- | --- |
| consultant | lead agent (Claude Code orchestrating session) — drafted the contract | 2026-11-03 |
| instrument builder | general-purpose subagent · Claude Code — wrote prepare.py, lib/protocol.py, the first analyze.py; trained only at smoke budget | 2026-11-03 |
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

- Goal: Estimate the data-scaling exponent of a small CNN's test cross-entropy on Fashion-MNIST, and test whether the power law fitted on small training sets predicts the loss at the full training set (a sealed extrapolation).
- Tracks (both registered):
  - `primary` — `val_mlogloss` of one cell = one training-set size N, a 3-seed array
    (`entrypoint.seeds`); each seed draws its own N-item subsample, so data-sampling
    variance is inside the cell. The training protocol is fixed in `lib/protocol.py`
    (outside the mutable surface): a cell only sets N.
  - `exponent` — `scaling_exponent` alpha of L(N) = a N^(-alpha) fitted on log-log axes
    over every pinned development cell, with `fit_r2`; confirmation is a replication.
- Execution: `entrypoint.execution: [local, detached]` — the six cells run as detached
  jobs (`klein run-one --detach` → `klein job exec` → `klein run-one --collect`), the
  exhibit for Klein 2.3's detached transaction; the referee weighs them as attested.
- Predictions P1-P4 are registered in study.yaml with arithmetic rules.

## Data and split

- Source: Fashion-MNIST (Xiao et al. 2017, MIT licence), the four IDX files from
  zalandoresearch/fashion-mnist, each a `url:` pin with sha256 (`data.source` + `data.inputs`).
- Lanes (predefined, by position — no seed): train = official train rows 0-49,999;
  development = official train rows 50,000-59,999; test = the official 10,000 t10k
  images — SEALED, read once by the full-data cell.
- Adaptive work uses train + development only.
- Gate 1 records the prepared-data SHA-256 and split-policy fingerprint.

## Phases and registered predictions (mirror of study.yaml)

| Phase | Cells | Predictions |
| --- | --- | --- |
| cells | primary · N = 500, 1k, 2k, 4k, 8k, 16k (detached, 3 seeds each) | — (measurements) |
| fit | exponent · the power-law fit | P1 — alpha in [0.10, 0.60]; P2 — fit_r2 >= 0.98 |
| confirmation | primary · N = 60,000 on the sealed test, after its dry run | P3 — abs rel. error <= 0.20; P4 — rel. error > 0 |

## Workflow

1. `uv run --locked klein gate record consult --study . --acknowledged-by <name>`
2. Prepare data and write a `Decision: GO` data card; record the DATA gate.
3. Write the method card; record the METHOD gate.
4. Commit gate evidence, switch to `experiments/22-cnn-data-scaling`, and run
   `uv run --locked klein preflight --study .`.
5. Set `CELL["n_train"]` in `analyze.py`, then
   `uv run --locked klein run-one --study . --track primary --detach --description ...`,
   `uv run --locked klein job exec runs/E####/job.json`, and
   `uv run --locked klein run-one --study . --collect E####`.

Every candidate is committed before execution. Discards and crashes remain resolvable
commits; the evidence transaction then restores `analyze.py` to the pre-candidate
base commit.

## Decisions (append-only)

- 2026-11-03 — schema-v3 study scaffolded from recipe `dl-scaling`, typed
  estimate · image · ml-research.
- 2026-11-03 — Decision: six sizes at doubling spacing (500 … 16,000) — 1.5 decades for
  the fit, and a 3.75x extrapolation to the full 60,000 for the sealed test.
- 2026-11-03 — Decision: the training protocol scales steps with N (20 epochs, at least
  400 steps) and keeps the best inner-validation checkpoint, so small cells are not
  over-trained into a loss that measures overfitting rather than data.
- 2026-11-03 — Decision: the sealed cell's relative error is computed per seed against
  the PINNED fit (tables/scaling_fit.tsv) and the notary averages it; the fit is frozen
  before the sealed access.

## Phase slates

At every phase start, run the slate ritual (references/phase-ritual.md):
propose 4-6 falsifiable candidates, score novelty / testability / expected
information 1-3, record the table and the chosen candidate here, and mirror
the ranked survivors into playbook.md "Next-best candidates".

### Phase <id> slate

| # | Candidate (falsifiable) | Novelty 1-3 | Testable 1-3 | Info 1-3 | Sum |
| --- | --- | --- | --- | --- | --- |
