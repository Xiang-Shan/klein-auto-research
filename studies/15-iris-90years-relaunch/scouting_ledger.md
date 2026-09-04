---
type: scouting-ledger
study: "15-iris-90years-relaunch"
status: open        # open | closed (closed at the CONSULT gate; later entries are a gate re-record)
---

# Scouting ledger — 15-iris-90years-relaunch

> Everything looked at BEFORE the CONSULT gate, so that no registered prediction can
> pretend to a surprise it already knew. Committed before `klein gate record consult`,
> which hashes this file into the consult record; an edit afterwards fails
> `klein verify` until the gate is re-recorded with a reason.

## §0 Disclosure

No data was loaded, no code was run, and no file under `studies/07-iris-90years/`,
`studies/08-iris-rematch/` or `studies/09-iris-first-lesson/` was opened while this
contract was written. The study was scaffolded first and its questions typed from the
brief alone.

That is not the same as an empty ledger, and this study will not pretend it is.
Executing the CONSULT protocol *requires* reading three reference documents, and all
three of them state, in the open, outcome summaries of three earlier studies in this
repository on this exact species pair — headroom values, keep counts over a challenger
parade, and one study's cell-map design. That exposure cannot be un-seen, it is not
independent of this study's headline question, and it is recorded below.

Its consequences are applied, not merely noted:

* the two research-question priors that rest on it (RQ1, RQ3) are tagged
  `(source: scouted)` in `study.yaml`, not `uninformed`, and are therefore excluded
  from the knowledge-versus-uninformed prior scorecard in findings §⑥;
* **no numeral disclosed below appears as a threshold in `predictions[]`.** Every
  threshold in the contract is either definitional (a row count, "one floor", the
  headroom law's own boundary of 1) or my own first-principles estimate (dev AUC
  >= 0.90, <= 3 misclassified flowers, a bootstrap interval wider than 0.05 AUC, and
  "several floors" for the sepal-only ablation). A scouted value may seed an anchor;
  it may never be a scored prediction.

## Entries

| S# | Date | What was looked at | What was seen | Why it is not evidence | Decision |
|---|---|---|---|---|---|
| S1 | 2026-09-04 | `.claude/skills/klein/references/consult-protocol.md` — required reading for this gate | Its headroom bullet names three earlier iris studies in this repository by number, with each one's headroom value and, for one of them, the number of challengers it ran and the number of keeps it got | Prose about other studies' outcomes, not a measurement on this study's split, this study's metric, or this study's floor. None of it can be re-derived from anything this study will produce. | Disclosed. RQ1 and RQ3 priors tagged `(source: scouted)` and excluded from the §⑥ scorecard. No value from it used as a prediction threshold. |
| S2 | 2026-09-04 | `.claude/skills/klein/references/inquiry-model.md` — required reading for this gate | Its worked-instantiations table types the same three studies and repeats one headroom value and one keep count | Same reason as S1 | Same as S1 |
| S3 | 2026-09-04 | `.claude/skills/klein/references/registered-mode.md` — required reading for this gate | Its worked example describes one of those studies' 42-cell permission map (families × feature sets) and the shape of the rule that adjudicated it | A design pattern and a rule shape, not a number about these flowers. This study's ablation was designed from the brief's own two sub-questions (petal-only, sepal-only) and uses three cells, not a 42-cell map. | Disclosed. The ablation design is stated in `research_plan.md` and rests on the brief, not on this. |
| S4 | 2026-09-04 | `AGENTS.md` and `CLAUDE.md`, auto-loaded project instructions | The war-story list, which names the class of bug behind the headroom law without naming this dataset | Framework doctrine, dataset-agnostic | No effect on any prior. |
| S5 | 2026-09-04 | `kleinlib/eval.py`, `kleinlib/contract.py`, `kleinlib/metrology.py`, `kleinlib/schema.py`, and the shipped `study.yaml` files of studies 00, 10 and 12 | The classification metric registry (which fixes `val_auc` as the only ROC-AUC primary), the schema-3 validation rules, the floor recipes, and the drafting conventions of three non-iris studies | Engine source and non-iris exemplars. Nothing here is a fact about iris. | The metric choice is grounded in the registry rather than in taste; recorded in `research_plan.md`. |

Not treated as scouting, and stated here for completeness: the brief itself supplies
the row count (100 flowers, versicolor and virginica). Fisher (1936), Anderson (1935)
and the general structure of the iris table are public literature that predates every
study in this repository; where a prior leans on that background rather than on a
measurement — RQ2's expectation that the petals carry the signal — the prior says so
in its own text so that findings §⑥ can discount it.

## Retirements

Directions or values scouted and dropped before the contract, with the reason, so the
next study does not re-scout them: none. Nothing was tried and abandoned; nothing was
computed at all.

## Prior-scorecard eligibility

Every research-question prior that rests on a value seen in this ledger is labelled
`(source: scouted)` in `study.yaml` — not `uninformed`, not `knowledge/…` — and is
excluded from the knowledge-vs-uninformed scorecard in findings §⑥. That is RQ1 and
RQ3. RQ2 and RQ4 are `(source: uninformed)` and are scored.
