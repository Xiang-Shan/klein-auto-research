# Program — 24-golomb-llm-vs-search

## Roster

Who is doing what, and on what. REFEREE cites this table for the independence rung
(`references/referee-protocol.md`); a blank `experimenter` row caps the achievable
rung at "fresh session", because no artifact then says what ran the loop. Fill the
experimenter row at CONSULT and update a row whenever its model, tool or session
changes.

| Role | Who (model · tool · session) | Since |
| --- | --- | --- |
| experimenter | | |
| data-gate auditor | | |
| referee | | |
| lead | (the human who owns this study) | 2026-11-03 |

This is the living lab notebook. `study.yaml` is the machine contract;
`study_state.json`, `events.jsonl`, and `runs/E####/manifest.json` are generated audit
state and must not be hand-edited.

## Goal and track contract

- Goal: At a matched budget of verifier calls, does an LLM proposing Golomb rulers as data match the known optimal lengths (OEIS A003022) as often as a classical randomized search, on development orders n = 8-11 and sealed orders n = 12-13 — and is a match search or recall?
- Track: `primary`
- Primary metric: `ruler_length` (lower is better; minimum meaningful
  delta 0)
- Results are exploratory until the track's one sealed final-test run confirms them.
  A small delta without uncertainty must not be described as real or decisive.

## Data and split

- Source: synthetic:prepare.py
- Adaptive work uses train + development only. The test partition stays sealed.
- Gate 1 records the prepared-data SHA-256 and split-policy fingerprint.

## Workflow

1. `uv run --locked klein gate record consult --study . --acknowledged-by <name>`
2. Prepare data and write a `Decision: GO` data card; record the DATA gate.
3. Write the method card; record the METHOD gate.
4. Commit gate evidence, switch to `experiments/24-golomb-llm-vs-search`, and run
   `uv run --locked klein preflight --study .`.
5. Edit `train.py`, then
   `uv run --locked klein run-one --study . --track primary --description ...`.

Every candidate is committed before execution. Discards and crashes remain resolvable
commits; the evidence transaction then restores `train.py` to the pre-candidate
base commit.

## Decisions (append-only)

- 2026-11-03 — schema-v3 study scaffolded; gates pending.

## Phase slates

At every phase start, run the slate ritual (references/phase-ritual.md):
propose 4-6 falsifiable candidates, score novelty / testability / expected
information 1-3, record the table and the chosen candidate here, and mirror
the ranked survivors into playbook.md "Next-best candidates".

### Phase <id> slate

| # | Candidate (falsifiable) | Novelty 1-3 | Testable 1-3 | Info 1-3 | Sum |
| --- | --- | --- | --- | --- | --- |
