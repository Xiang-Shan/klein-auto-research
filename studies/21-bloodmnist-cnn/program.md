# Program — 21-bloodmnist-cnn

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

- Goal: From pixel logistic regression to a small CNN: what earns a keep under a measured floor on 8-class blood-cell microscopy images (BloodMNIST, official split), and how far does a CPU-budget CNN get toward the published MedMNIST baselines?
- Track: `primary` (frontier) — `val_macro_f1`, the seed-array mean over seeds 0, 1, 2
  (`entrypoint.seeds`); higher is better; `metric.bound.ideal: 1.0`.
- The keep bar is MEASURED at Phase 0 (an item bootstrap of the anchor's development
  macro-F1 — estimand marginal-resplit) and written into the contract by
  `klein noise-floor`; the seed-block spread is recorded as `fit_noise`, never as the bar.
- Predictions P1-P5 are registered in study.yaml with arithmetic rules.
- Results are exploratory until the one sealed test run and a replication record
  confirm them (`confirmation.require: [sealed, replicate]`).

## Data and split

- Source: MedMNIST v2 `bloodmnist.npz` (28 x 28 RGB, 8 classes), Zenodo record
  10519652, a `url:` pin with sha256. Licence: CC BY 4.0.
- Split: the dataset's OFFICIAL partitions, kept (`kind: predefined`): train 11,959,
  val -> development 1,712, test -> sealed 3,421. Whether they are grouped by patient
  or slide is a DATA-gate question.
- Adaptive work uses train + development only. The test split is read once.
- Gate 1 records the prepared-data SHA-256 and split-policy fingerprint.

## Phases and registered predictions (mirror of study.yaml)

| Phase | Cells | Predictions |
| --- | --- | --- |
| anchor | the recipe SmallCNN (anchor); a linear softmax on pixels; then the floor sweep | P2 — anchor macro-F1 >= 0.85; P1 — linear in [0.50, 0.85] |
| adaptive | one idea per candidate (normalization/depth, augmentation, schedule, width) | P3 — BN + 3 blocks + flip/rot90 + 4,000 steps >= 0.93 |
| confirmation | the incumbent on the sealed test split, after its dry run | P4 — test macro-F1 >= 0.90; P5 — test accuracy < 0.958 |

## Workflow

1. `uv run --locked klein gate record consult --study . --acknowledged-by <name>`
2. Prepare data and write a `Decision: GO` data card; record the DATA gate.
3. Write the method card; record the METHOD gate.
4. Commit gate evidence, switch to `experiments/21-bloodmnist-cnn`, and run
   `uv run --locked klein preflight --study .`.
5. Edit `model.py` / `train.py` (one idea), then
   `uv run --locked klein run-one --study . --track primary [--tests P#] --description ...`.
   Each run is a seed array: the notary runs seeds 0, 1, 2 and decides on the mean.

Every candidate is committed before execution. Discards and crashes remain resolvable
commits; the evidence transaction then restores the surface (`model.py`, `train.py`) to the pre-candidate
base commit.

## Decisions (append-only)

- 2026-11-03 — schema-v3 study scaffolded from recipe `cv-classify`, typed
  predict · image · cv.
- 2026-11-03 — Decision: keep MedMNIST's official split (predefined) rather than
  re-splitting, so the sealed number is comparable with published test numbers.
- 2026-11-03 — Decision: primary metric macro-F1 (the CV profile's rule for imbalanced
  classes); accuracy is printed beside it and P5 reads it, because MedMNIST reports
  accuracy.
- 2026-11-03 — Decision (DATA gate): the official split carries 11 cross-split
  near-duplicates (dHash <= 4 bits); `prepare.py` drops them from development (3) and
  test (8). Scope limit on every claim: the official split is image-level, not grouped
  by patient or slide, so all scores are image-level.
- 2026-11-03 — Decision: `prepare.py` stores the source's uint8 pixels; the training
  loader scales them (the payload stays byte-faithful to the source).

## Phase slates

At every phase start, run the slate ritual (references/phase-ritual.md):
propose 4-6 falsifiable candidates, score novelty / testability / expected
information 1-3, record the table and the chosen candidate here, and mirror
the ranked survivors into playbook.md "Next-best candidates".

### Phase <id> slate

| # | Candidate (falsifiable) | Novelty 1-3 | Testable 1-3 | Info 1-3 | Sum |
| --- | --- | --- | --- | --- | --- |
