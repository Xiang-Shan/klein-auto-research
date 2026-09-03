# Program — 00-known-truth-quickstart

This is the living lab notebook. `study.yaml` is the machine contract;
`study_state.json`, `events.jsonl`, and `runs/E####/manifest.json` are generated audit
state and must not be hand-edited.


## Roster — who ran what, on which model

The referee observed that this study recorded its experimenter nowhere: run
manifests carry no actor or model field, and `study_state.json` records only the
actor string `lead-agent`. That is a real gap — the independence rung on a gate
record is only as good as the record of who was on each side of it — so the roster
is written down here, where SYNTHESIZE and any later reader will find it.

| Role | Who | Model | Context |
|---|---|---|---|
| Experimenter (CONSULT → SYNTHESIZE, every `run-one`) | a Claude Code general-purpose subagent | `claude-opus-5` | a fresh git worktree, this session |
| DATA-gate clean-room auditor | `klein-data-auditor` | `sonnet` | fresh context; read only `study.yaml`, `prepare.py`, the prepared artifact and `truth.json` — never `program.md` or `train.py` |
| Referee (Gate 3) | `klein-referee` | `claude-opus-5` | fresh context, started AFTER synthesis, no memory of the loop |
| Lead / orchestrator | Claude Fable 5.1 | — | spawned the referee, relayed its notes, owns the delegated acks |

**Independence rung reached: `fresh session`** — the lowest rung of the ladder
(person > tool > model > backend > fresh session). The referee ran on the same
model family as the experimenter, so `independent-of-experimenter: no` is what the
referee report says and what the gate record carries. The fresh-context half of
the requirement was met in full; the model half was not, and neither the report nor
this file claims otherwise.

## Goal and track contract

- Goal: On a synthetic table whose Bayes-optimal AUC is computable from the declared
  generating process, how close to that known ideal does a short ladder of tabular
  models get, and does the headroom law correctly call the point at which further
  development is arithmetically pointless?
- Kind / modality / profile: `predict` / `tabular` / `generic`. Schema 3.
- Track: `primary`, mode `frontier`.
- Primary metric: `val_auc` (higher is better). `minimum_delta` is measured at
  Phase 0 with a named estimand and pasted into the contract; it is never guessed.
- `metric.bound.ideal` is the development partition's Bayes AUC — the best score any
  model could reach on those rows — declared only after the DATA gate has hashed the
  generator that computes it.
- Results are exploratory until the track's one sealed final-test run confirms them.
  A small delta without uncertainty must not be described as real or decisive.

## Data and split

- Source: `synthetic:prepare.py`. The generator seed is read from
  `data.split.seed`; no seed and no partition rule is written as a literal anywhere
  in a script (war story 8).
- 20 000 rows, 8 standard-normal features. Six enter the true log-odds; `x7` and
  `x8` enter nothing. One two-way interaction (`x1·x2`) and one quadratic (`x3²`)
  are the two things a linear-in-raw-features model cannot express.
- `data/prepared/truth.json` carries the per-row true log-odds and, per contract
  partition, the Bayes AUC and Bayes Brier those log-odds imply.
- Adaptive work uses train + development only. The test partition stays sealed.
- Gate 1 records the prepared-data SHA-256 and the realized partition fingerprints.

## Research questions

- **RQ1** — how much of the distance between a linear-in-raw-features baseline and
  the known Bayes ceiling does each rung of a short ladder close, in units of the
  measured floor? Prior: the anchor stops several floors short; the true interaction
  closes part of it; a boosted tree closes most of the rest without being told which
  terms are true `(source: scouted — scouting_ledger.md S2)`.
- **RQ2** — does the headroom law call the end of this ladder correctly: does
  `h = (ideal − incumbent) / minimum_delta` fall below 1 before a challenger with
  real capacity is spent, and does the run spent anyway come back within the floor?
  Prior: yes, the door closes before the fourth candidate `(source: uninformed —
  the floor is measured at Phase 0, after the scouting ledger closes)`.

## Registered predictions

Every rule is a threshold in units of the MEASURED floor, so every numeral in the
prediction block is an integer count of floors, fixed before the floor was known.
`gap_in_floors` is the run's own headroom against the declared ideal;
`delta_in_floors` is its paired lift over the named reference rung, refitted on the
same rows inside the same run so the comparison lives in one printed block.

| P# | Statement | Rule | Decided by |
|---|---|---|---|
| P1 | the raw-feature logistic model cannot reach the ceiling: more than one floor of distance is left | `gap_in_floors > 1` | E0001 `--tests P1` |
| P2 | handing it the DGP's true interaction beats it by at least one floor on the same rows | `delta_in_floors >= 1` | E0002 `--tests P2` |
| P3 | a boosted tree, told none of the true terms, beats the hand-specified interaction rung by at least one floor | `delta_in_floors >= 1` | E0003 `--tests P3` |
| P4 | buying capacity on top of the boosted rung is within noise (< 1 floor from its own reference) | `abs(delta_in_floors) < 1` | E0004 `--tests P4` |
| P5 | the sealed run lands within two floors of the sealed partition's ceiling | `abs(gap_in_floors) <= 2` | E0005 `--tests P5` |

## Phase plan

| Phase | What happens | Budget | Max experiments |
|---|---|---|---|
| (Phase 0, no ledger rows) | two floor recipes into two sidecars; `klein noise-floor` prints the contract block; consult re-record pastes it | — | — |
| `adaptive-1` | E0001 anchor → E0002 interaction → E0003 boosted → E0004 over-capacity | 3600 s | 4 |
| `confirmation` | sealed dry-run, then E0005 once on the held-out partition | 900 s | 1 |

## Workflow

1. `klein gate record consult`. The scouting ledger is committed FIRST — not
   because the gate hashes it (it does not: the consult gate hashes `study.yaml`,
   `research_plan.md` and `program.md`) but because the commit that carries the
   `study.yaml` the gate does hash carries the ledger too.
2. `prepare.py`, the profile, the clean-room leakage audit, `data_card.md` = GO;
   `klein gate record data`.
3. `method_card.md` + `references.yaml`; `klein gate record method`.
4. Phase 0 floors; paste the measured block; consult re-record with a reason;
   `klein preflight`.
5. The loop: edit `train.py` (two constants), `klein run-one --tests P#`.

Every candidate is committed before execution. Discards and crashes remain
resolvable commits; the evidence transaction then restores `train.py` to the
pre-candidate base commit.

## Decisions (append-only)

- 2026-09-03 — schema-3 study scaffolded (`predict` / `tabular` / `generic`); gates
  pending.
- 2026-09-03 — `study.yaml:target` is the target COLUMN, so it reads `y`; the
  "synthetic" part of the study's identity lives in `data.source`
  (`synthetic:prepare.py`), which is what `contract_split` and the DATA gate read.
- 2026-09-03 — the user's gate acknowledgements are DELEGATED to this agent for the
  Klein 2.0 exhibit studies. Every gate below is therefore recorded with
  `--acknowledged-by lead-agent`, on the lead's standing instruction, and the same
  applies to the phase acknowledgements. Nothing else about the gates changes: the
  artifacts still have to exist, be placeholder-free, and hash.
- 2026-09-03 — the smoke check of `train.py` ran before the consult gate was
  recorded and is disclosed as entry S4 of `scouting_ledger.md` rather than left
  silent. It wrote nothing and could not have set a rule: no floor existed yet.
- 2026-09-03 — Phase 0 measured TWO floors and they disagree by everything.
  `seed-sweep` (k = 5) refit the anchor on the same rows under five fit seeds and
  moved it not at all: std 0, range 0. That is recorded under `fit_noise` as
  provenance and is NOT the bar — a study that had pasted it into
  `minimum_delta` would carry a keep bar of zero and would keep every candidate
  that moved the fourth decimal. The bar comes from `split-lottery`
  (k = 10, estimand `marginal-resplit`, redrawing train/development inside the
  train+development pool only, never touching the sealed rows):
  std 0.00372606, range 0.012855, `minimum_delta` 0.00745212 = max(2*std, range/2).
- 2026-09-03 — Decision: `tracks.primary.metric.bound.ideal` is set to 0.884116,
  the development partition's Bayes AUC from `data/prepared/truth.json`. This is
  a contract change AFTER the DATA gate, and it is lawful only through a gate
  re-record with a reason, which is what happens next: the DATA gate had to hash
  the generator before the number it computes could be quoted in the contract. No
  run exists yet, so no result could have informed it. `on_infeasible: ack` is
  chosen over `block` deliberately — this study wants to walk through the closed
  door on the record, not be stopped by it.

- 2026-09-03 — E0001 KEEPS at val_auc 0.806201 and anchors the track. Its printed
  `gap_in_floors` is 10.4555: a single hyperplane over the raw features sits more
  than ten measured floors below the known ceiling of 0.884116. P1 SUPPORTED by
  the notary on the printed block.
- 2026-09-03 — E0002 KEEPS at val_auc 0.835785. Handing the linear model the DGP's
  true `x1*x2` term bought `delta_in_floors` 3.9699 over the same rung refitted on
  the same rows, and cut the distance to the ceiling from 10.4555 to 6.4856
  floors. P2 SUPPORTED. Decision: the remaining distance is the quadratic the
  linear model still cannot express, so the next rung changes model class rather
  than adding another hand-specified term.
- 2026-09-03 — E0003 KEEPS at val_auc 0.871390 and takes the frontier. A boosted
  tree told NONE of the true terms beat the hand-specified interaction rung by
  `delta_in_floors` 4.7779, leaving `gap_in_floors` 1.7077. P3 SUPPORTED.
- 2026-09-03 — headroom read before spending the fourth candidate:
  h = (0.87139 - 0.884116) / 0.00745212 = 1.708. The door is AJAR, not open. The
  study proceeds and records in advance that `h >= 1` means only "not
  arithmetically excluded": the attainable ceiling may sit well short of the ideal
  one, and study 08 stood at h = 1.015 and produced zero keeps in twenty-one
  attempts. No `klein headroom ack` is required at h > 1, and none is filed.
- 2026-09-03 — Decision: **P4 REFUTED** by E0004. The over-capacity boosted tree
  (500 trees, 127 leaves, `min_samples_leaf` 1, no L2, no early stopping) did not
  land within noise of its own reference — it lost `delta_in_floors` -1.7903, a
  degradation nearly twice the floor, and DISCARDS at val_auc 0.858049 against the
  incumbent 0.87139. The prediction said "within noise"; the measurement says
  "measurably worse", so the prediction is refuted rather than supported, and the
  study records that the honest reading of a refuted "no-effect" prediction is a
  real effect in the wrong direction. Its `val_logloss` 1.024102 against E0003's
  0.355165 says why: unregularized depth on 12 000 rows destroys the probabilities
  long before it destroys the ranking. Consequence: capacity is now a ruled-out
  direction on this table, the ladder stops here, and the confirmation phase
  spends the one sealed access on E0003's configuration.
- 2026-09-03 — Decision: RQ2's prior is WRONG so far. It said the headroom would
  close (h < 1) before the fourth candidate; it stood at 1.708 instead, so the law
  did not stop the study and the discard had to be paid for in full. That prior was
  `(source: uninformed)` and is recorded as a miss, not quietly rewritten.
- 2026-09-03 — Phase `adaptive-1` closes with its four experiments spent: three
  keeps (E0001, E0002, E0003) and one discard (E0004); P1, P2, P3 supported and P4
  refuted, all four adjudicated by the notary on printed blocks. Playbook
  refreshed; the acknowledgement is the lead's delegated one.

- 2026-09-03 — E0005 spends the one sealed access: val_auc 0.880949 against the
  sealed partition's OWN Bayes ceiling of 0.893469, `gap_in_floors` 1.6800.
  **P5 SUPPORTED.** The development gap was 1.7077 floors and the sealed gap is
  1.6800: the distance to the ceiling did not grow when the rows changed, which is
  what "the remaining distance is irreducible at this sample size, not
  overfitting" looks like when you can see the ceiling. The seal is spent and no
  further sealed access exists on this track.
- 2026-09-03 — Decision: two attempts at `klein replicate E0003` are on the record
  and BOTH failed, neither for a scientific reason, and both are kept
  (`rep:E0003@20260903T053202Z`, `rep:E0003@20260903T053344Z`). The first hit
  `exit 124`, a timeout: the detached worktree has to build its own virtualenv
  before the entrypoint runs at all, and this study's honest `max_run_seconds` of
  60 — sized for runs that take under a second — was consumed by that build. The
  second, given `--timeout-seconds 300`, got as far as `train.py` and crashed with
  `FileNotFoundError: data/prepared/truth.json`. The cause is a seam worth naming:
  `klein replicate` copies the ONE artifact the contract declares
  (`data.prepared_path`, here `prepared.csv`) and asserts its fingerprint; this
  study's entrypoint reads a SECOND prepared artifact beside it, `truth.json`,
  which the contract never declared and `.gitignore` never tracked. The engine did
  exactly what it documents; the study asked for something it had not declared.
  Consequence: the replication is NOT retried into a pass (both attempts stand),
  `train.py` is NOT edited after the loop closed to make an unproven fix look
  proven, and the lesson is written up as a claim instead. Nothing rests on it:
  `confirmation.require` is `[sealed]`, and the confirmed claim's two evidence
  kinds are a development run (E0003) and a sealed run (E0005). The study remains
  reproducible BY HAND — `prepare.py` regenerates `data/prepared/` deterministically
  from the contract's seed, and `klein verify --require-local` is the verb for
  checking a study after that regeneration; it is only the detached-worktree path
  that cannot do it unattended.


## Referee notes (Gate 3, verdict PASS-WITH-NOTES, 2026-09-03)

The referee returned PASS-WITH-NOTES with seven notes. Each is answered here, dated,
with what was done about it.

- 2026-09-03 — **Referee note 1 (truncated bar axis).** Upheld. The left panel of
  `headroom_bar.png` ran from 0.78 under a bar mark, and `tutorial-spec.md` critique
  point 2 says bars are zero-based. Fixed: the panel is now zero-based with a chance
  rule drawn at val_auc 0.5, because 0.5 and not 0 is where an AUC axis stops being
  informative and a bare zero-based AUC axis invites the opposite misreading. The
  honest consequence is that the five rungs now look nearly identical in metric
  units — which is the truth, and which is exactly why the right panel divides the
  same distances by the measured floor. The two panel titles were rewritten to say
  so. The value labels moved inside the bars, where they no longer collide with the
  ceiling and chance rules. Re-rendered and confirmed byte-identical across two
  further renders.
- 2026-09-03 — **Referee note 2 (the data card's literal-seed sentence).** Upheld,
  and NOT fixed in place. `data_card.md` says there is "no literal integer seed …
  in any script the study owns"; `train.py` line 58 is `RANDOM_SEED = 42`. The
  sentence is false as written. Three things are true and are recorded instead of
  editing the card: (i) that literal is a FIT seed and reaches only
  `LogisticRegression(random_state=…)` and `HistGradientBoostingClassifier(random_state=…)`;
  (ii) no partition is chosen anywhere in the study's own code — every run takes its
  rows from `kleinlib.data.load_partition`, which prints the `split_fingerprint:`
  the notary compares against the one the DATA gate froze, and `klein verify`
  reports current == recorded for the policy and for both realized partitions; and
  (iii) the sentence was asserted about `train.py`, a file the clean-room auditor
  states in the same card that it never read — so the card over-reached beyond its
  own declared reading scope. `data_card.md` is a gate-hashed artifact and its hash
  is on the DATA gate record and on `events.jsonl` sequence 3; editing it after the
  runs would silently invalidate that record, so the correction lives here and in
  findings §③ instead. The substance of war story 8 is intact; the sentence was not.
- 2026-09-03 — **Referee note 3 (an unmeasured superlative).** Upheld. Findings §⑤
  called `x1·x2` "the single most valuable hand-specified term available". No run
  measured that: the study fitted `raw` and `raw + x1·x2` and never `raw + x3²`, and
  the design-time oracle in `scouting_ledger.md` S2 points at the quadratic as the
  larger single term. The superlative is removed and replaced with what was
  measured, plus an explicit statement that the ordering of single hand-specified
  terms was never measured by a run. `claims.lock` is untouched — C2's locked
  sentence never carried the superlative, which is the lock doing its job.
- 2026-09-03 — **Referee note 4 (the controls are never called controls).** Upheld.
  Both controls existed and neither was named. They are now named in findings §① and
  here. **Negative control:** the DATA gate's mechanized eval-harness row — a
  constant predictor and a label-shuffled predictor, which scored `val_auc=0.5000`
  and `val_auc=0.5011` against a chance anchor of 0.5. A pipeline that cannot score
  chance at chance cannot be trusted to score anything else. **Positive control:**
  E0002, which hands the model a term the generating process is KNOWN to contain
  (`x1·x2`) and must therefore detect if the pipeline works at all; it recovered
  `delta_in_floors` 3.9699, and the design-time oracle in S2 had stated the expected
  magnitude in advance. A known-absent effect scoring at chance and a known-present
  effect being detected are the two halves, and on an onboarding exhibit they should
  have been labelled the first time.
- 2026-09-03 — **Referee note 5 (`n_comparisons` never stated).** Upheld. Stated now
  in findings §②: the family is the five registered predictions, each locked with
  its own arithmetic rule at the first consult gate before any evidence existed, each
  bound to exactly one run, with no post-hoc selection among candidate comparisons.
  The guard is pre-registration rather than an alpha correction, and at 4.62 to 10.46
  floors a Bonferroni over five would change no verdict.
- 2026-09-03 — **Referee note 6 ("the gate hashes it" is false of the scouting
  ledger).** Upheld, and it is a framework template defect rather than an authoring
  error — the sentence is inherited verbatim from
  `assets/scouting-ledger-template.md` and `references/consult-protocol.md`. The lead
  is fixing the template separately. In this study both copies of the wording are
  corrected to what is checkable: `scouting_ledger.md` was committed BEFORE the
  consult gate, in commit `5bda63da06f16c9a6476b49ada9e43fb226dd94b`, and that same
  commit carries the `study.yaml` the gate DID hash — `events.jsonl` sequence 2
  records `study.yaml` at sha256 `c4f66ed893b543e8…`, byte-identical to the blob at
  `5bda63da:studies/00-known-truth-quickstart/study.yaml`. The ledger is frozen one
  step removed, by the commit rather than by the gate. This matters because S4
  discloses a pre-gate smoke run: a reader told "the gate hashes it" would believe
  that disclosure is notarized when it is only committed.
- 2026-09-03 — **Referee note 7 (C5's calibration description is one-sided).**
  Upheld. §③ described only the under-prediction of high-probability rows. The
  figure shows the full pattern — over-prediction of the low-probability rows as
  well — which is shrinkage toward the base rate and a STRONGER illustration of
  C5's own point than the one-sided sentence was. Corrected in findings §③. C5's
  class (`mechanism-interpretation`) and strength (`exploratory`) are unchanged, and
  the locked sentence in `claims.lock` is untouched.

## Phase slates

At every phase start, run the slate ritual (references/phase-ritual.md):
propose 4-6 falsifiable candidates, score novelty / testability / expected
information 1-3, record the table and the chosen candidate here, and mirror
the ranked survivors into playbook.md "Next-best candidates".

### Phase adaptive-1 slate

Scored after the Phase 0 floor landed at `minimum_delta` 0.00745212, so
testability is judged against a bar that exists.

| # | Candidate (one hypothesis, one transaction) | Nov | Test | Info | Sum |
| --- | --- | --- | --- | --- | --- |
| 1 | `logreg_raw`: the raw-feature identity anchor; prints the first `gap_in_floors` and decides P1 | 1 | 3 | 3 | 7 |
| 2 | `logreg_interaction`: hand the linear model the DGP's true `x1*x2`; decides P2 | 3 | 3 | 3 | 9 |
| 3 | `hgbt_default`: a boosted tree told none of the true terms; decides P3 | 3 | 3 | 3 | 9 |
| 4 | `hgbt_overcapacity`: 5x the trees, 127 leaves, no shrinkage discipline, no early stopping; decides P4 | 2 | 3 | 3 | 8 |
| 5 | `logreg_quadratic`: hand it `x3^2` as well — reaches the ceiling by construction | 2 | 3 | 1 | 6 |
| 6 | `logreg_raw` without `x7`, `x8`: does dropping known-noise columns move anything? | 2 | 1 | 2 | 5 |

Chosen, in order: 1 (a frontier needs an incumbent before anything can be
compared to it), then 2, 3, 4 — the ladder in the order the method card argues
it. #5 scores 1 on information because the DGP already dictates its answer: a
model handed every true term must reach the ceiling, so the run would teach
nothing the generator has not already said. #6 scores 1 on testability because a
logistic regression on 12 000 rows barely notices two noise columns; the
predicted move is well under `minimum_delta`, so one run cannot decide it. Both
go to the playbook queue rather than the ledger.

### Phase confirmation slate

A confirmation phase has exactly one lawful candidate, so the ritual's job here
is to write down what was NOT done with the seal, and why.

| # | Candidate (one hypothesis, one transaction) | Nov | Test | Info | Sum |
| --- | --- | --- | --- | --- | --- |
| 1 | E0003's configuration, unchanged, once on the sealed partition; decides P5 | 1 | 3 | 3 | 7 |
| 2 | re-tune on development first, then seal the winner | 2 | 3 | 1 | 6 |
| 3 | seal E0002 as well, to get a second sealed number for the gap | 2 | 1 | 2 | 5 |
| 4 | skip the seal and close the study exploratory | 1 | 3 | 1 | 5 |

Chosen: 1. #2 is refused by the phase budget and by the discipline — the frontier
closed when the adaptive phase's experiments were spent, and re-opening it to
improve the number that is about to be sealed is how a sealed number stops
meaning anything. #3 scores 1 on testability because this study declares ONE
track and a track gets ONE sealed access: two sealed numbers would have required
two tracks declared at CONSULT, which is exactly the choice the consult protocol
says to make before the loop and not after it. #4 would waste an already-earned
confirmation.

The rehearsal (`klein run-one --final-test --dry-run`) runs first and is not
optional: study 09 lost its only seal to a crash that happened before any data
was read.

