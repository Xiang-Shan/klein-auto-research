# CONSULT — Gate 0

Advice for a vague or ambitious goal. Turn "I want to try X on my data" — or "does
this paper's number reproduce", "how large is this effect", "find a better
construction" — into a scoped study: `study.yaml` + `research_plan.md` + a generated
`program.md`, plus `scouting_ledger.md` for anything looked at before the contract.
This gate ENDS with an explicit user ack before the DATA gate begins.

Role: consultant. Any agent or human can execute this protocol directly — it is the
source of truth; Claude Code ships it pre-wired as the `klein-consultant` worker.

## The interview: at most six questions

Ask only what the brief has not already answered. Keep it to ONE short message; do not
interrogate. The six axes, with example phrasings:

1. **Goal / decision.** "What question should this study answer, and what will you do
   differently depending on how it comes out?" A study that changes no decision is not
   worth running.
2. **Evidence availability & size.** "What data do you have — source, rough size,
   modality, the target or the quantity to measure? If none, should we build a
   synthetic known-truth lab, or is there a verifier that judges an object instead?"
3. **Method familiarity.** "Is the method one you know well, or one you've only read
   about? Frontier / unfamiliar methods get a full METHOD gate (intuition → math → refs)."
   On a study whose generation manifest declares `expertise`, this answer is read from
   `domain_card.md`'s `method_shortlist[]` rather than invented here — the shortlist is
   locked before this gate and is what METHOD chooses FROM
   (`references/expert-protocol.md`).
4. **Metric & decision use.** "For each distinct task, what primary metric should its
   track use, higher or lower, what minimum delta matters, and which guardrails
   must hold?" Never combine unrelated tasks into one global frontier. Declare
   guardrails on keys the run will PRINT: `wall_seconds` prints on every run, and
   the CALLING evaluator's own aux metrics print for it; anything else must be
   routed through `evaluate*(..., extra={...})` — `klein preflight` warns.
5. **Compute / time budget.** "What are the maximum seconds — or steps, for a long
   run — for one run, each phase's total budget, and its experiment-count cap?"
   These are separate controls.
6. **Deliverable form.** "Besides the always-on `findings.md` + `claims.lock` +
   referee report + HTML tutorial, do you want any study-specific docs?"

### Fast-path

If the brief already answers FIVE or more of the six, do NOT re-ask. Draft everything,
then present a single CONFIRM-ONLY summary (below). Ask only about the one genuinely
missing axis.

## Type the inquiry — inferred, then confirmed; never a seventh question

From the brief, infer the three axes (`references/inquiry-model.md`) and state each
with one line of reasoning in the confirm summary:

| The brief says… | `kind` |
|---|---|
| "does X predict Y", "which model wins", "improve the metric" | `predict` |
| "how large is", "what is the value of", "with what uncertainty" | `estimate` |
| "is there a difference", "does H hold", "does the factor add signal" | `test` |
| "does the method recover the truth", "under a known process" | `simulate` |
| "does the paper's number reproduce", "reproduce table N" | `replicate` |
| "what is in this data", "what structure", "generate hypotheses" | `discover` |
| "find the best object", "beat the known bound", with a checker | `optimize` |

`modality` follows the evidence source (a table, a time series, images, sequences,
graphs, text, a simulator, or `none` when only a verifier exists). `profile` follows
the audience and the field's vocabulary (`generic` unless the brief is plainly ML
research, mathematics, or insurance — the profile files' §8 hints decide). A study
with two lanes (a registered test beside a known-truth simulation, as study 09) keeps
one study kind and overrides per track with `tracks.<id>.kind`.

## Draft the artifacts

From the answers, scaffold, then fill:

```bash
uv run --locked klein new NN-slug \
    --goal "..." --kind <kind> --modality <modality> --profile <profile> \
    --metric <name> --goal-direction higher|lower --data "<source tag>" \
    --track <name>[:registered] [--track <name2>[:registered]] [--split-seed N]
```

Fill in `study.yaml` (schema 3): `kind`, `data.modality`, `data.source` with its pin
(`references/data-sources.md`), `profile` and `audience`, `entrypoint {command,
mutable}`, explicit `task_type` (the metric family) and `method_depth`, one or more
track contracts — `mode` (frontier or registered), metric name / direction / minimum
delta / guardrails, `metric.bound.ideal` for a bounded metric, `confirmation.require`
(default by kind), a `verifier` block for `optimize` and for any checkpoint-scored
study — a three-way train/development/test split, `max_run_seconds` by run-cost class,
phases with independent `budget_seconds` and `max_experiments`, research questions
with honest priors and their provenance, and `predictions[]`. Mirror the phases, RQs,
and predictions into `program.md`; sketch the experiment ladder in `research_plan.md`.

Rules for good drafting:

- **Priors must be honest.** Write what you actually expect ("no lift over 0.67"), not
  what you hope. SYNTHESIZE holds each prior to account.
- **Predictions must be falsifiable AND decidable by arithmetic.** Each has an id
  `P#`, a track, a statement with a lever, a direction and a magnitude with units,
  and a `rule` on a printed key — `{key: primary_metric, op: ">=", value: 0.6538}`,
  `{key: ci_low, op: ">", value: 70}`, `{within: {target: 465, tol: 10}}`,
  `{all_of: [...]}` — or `manual: true` when no run can decide it (the referee asks
  why). `inconclusive_if` names the condition under which the run cannot decide
  ("n_boot < 1000"). "Tuning helps" is not a prediction; "swap-rate 0.25 gives
  +0.001 val_auc" with its rule is.

  A rule is decided by arithmetic on the printed block, and the explanation it
  returns is that arithmetic — so a reader re-checks the verdict without
  re-running anything:

<!-- test:prediction-rule:start -->
```python
from kleinlib.decision import evaluate_rule

printed = {"primary_metric": 0.6712, "ci_low": 336.4, "n_boot": 2000}

assert evaluate_rule({"key": "primary_metric", "op": ">=", "value": 0.6538}, printed) == (
    "supported",
    "primary_metric 0.6712 >= 0.6538 → supported",
)
assert evaluate_rule({"key": "ci_low", "op": ">", "value": 400}, printed)[0] == "refuted"

# A key the run never printed is INCONCLUSIVE, never a refutation.
verdict, why = evaluate_rule({"key": "effect", "op": ">", "value": 0}, printed)
assert verdict == "inconclusive" and "not printed" in why

# Combinators are three-valued: all_of is refuted by any refuted child.
assert evaluate_rule(
    {
        "all_of": [
            {"key": "primary_metric", "op": ">=", "value": 0.6538},
            {"key": "n_boot", "op": ">=", "value": 1000},
        ]
    },
    printed,
)[0] == "supported"
```
<!-- test:prediction-rule:end -->
- **Everything looked at before this gate goes into `scouting_ledger.md`**
  (scaffolded by `klein new`; shape and rationale in
  `assets/scouting-ledger-template.md`), committed before the gate is recorded:
  on schema 3, `klein gate record consult` hashes it into the consult record beside
  `study.yaml`, `research_plan.md` and `program.md`, so an edit afterwards fails
  `klein verify` until the gate is re-recorded with a reason. It is the one OPTIONAL
  consult artifact — a study that scouted nothing may delete it, and the gate then
  records `scouting_ledger: absent` on the event trail so the absence is itself on
  the record. Values seen there may seed anchors and identity checks; they may
  never be scored predictions, and priors resting on them are `(source: scouted)`. On a
  generation-enabled study the same rule types the slate: a hypothesis whose outcome the
  ledger already observed carries `provenance: scouted`, is EXCLUDED from prospective
  calibration, and is reported in a descriptive panel of its own
  (`references/generation-protocol.md`).
- **Fill the `experimenter` row of `program.md`'s `## Roster`** with the model, tool
  and session that will run the loop. REFEREE reads that table for the independence
  rung (`references/referee-protocol.md`); left blank, the rung is capped at "fresh
  session" because no artifact says what ran the loop.
- **Phase 0 is always an identity anchor** when a comparable baseline exists —
  reproduce it EXACTLY, STOP if off — this catches split/leakage bugs before they
  poison every later comparison. A `replicate` study anchors on a published sum,
  count or table dimension of the transcribed data.
  **On an `expertise`-enabled study the identity anchor IS the EXPERT obligation**: the
  card's `baseline.targets` are frozen at `klein generation expert lock` before this
  gate, the anchor runs as E0001 under a `--action baseline` admission after METHOD,
  and `klein generation expert bind E0001` discharges it. A `mismatch` or `crash`
  BLOCKS every challenger admission until a versioned `expert repair` reproduces —
  "STOP if off" stops being a discipline the driver keeps and becomes one the notary
  keeps (`references/expert-protocol.md`).
- **Then measure the noise floor — never guess `minimum_delta`.** After the anchor,
  run the floor recipe that matches the question — `seed-sweep` (fit noise; k=5
  default, k=3 if one run exceeds ~5 minutes), `split-lottery` (marginal-resplit), or
  `paired-bootstrap` (paired-comparison, both candidates predicting the SAME rows
  under common random numbers) — via `sweeps/noise_floor.py` → sidecar, registered
  with `klein sweep register`; then `klein noise-floor --study <dir> --recipe <r>
  --estimand <e>` prints the per-track block. Set `minimum_delta ≥ max(2×std,
  range/2)` (schema 3 enforces it) and re-record the consult gate with
  `--note "minimum_delta set from the measured noise floor"`. A seed-only spread is
  recorded as `fit_noise`, never pasted as the bar. An `exact` metric (integer or
  closed-form objectives) declares `metric.exactness: exact` with a resolution and an
  `exactness_note` instead.
- **Real data has more than one floor — pick the one that matches the question.**
  On real data the fit-seed spread, the marginal dev-fold bootstrap SE, and the
  paired-difference bootstrap SE can differ by an order of magnitude. For a
  COMPARISON study the honest floor is the paired one; record the recipe and the
  estimand in the block; the paired analysis itself lives in `program.md`.
- **After the floor lands, audit headroom — the floor can outgrow the prize.**
  Compute `h = (incumbent − ideal) / minimum_delta` for every bounded metric.
  `h < 1` means no keep is arithmetically possible — re-scope or pre-commit a
  door-closed branch BEFORE spending challengers. Declare `metric.bound.ideal` (+
  `on_infeasible`) and `noise_floor.estimand` so klein computes, discloses, and
  gates this automatically (`klein headroom ack` records the run-anyway branch).
  Study 07 ran a parade at h = 0.81 with no disclosure; study 08 registered the
  arithmetic first and its door-ajar frontier (h = 1.015) still produced zero keeps
  in twenty-one attempts; study 09 closed the door at h = 0.33 before any challenger
  — `h >= 1` is "not excluded", never "plausible".
- **When the research question is a comparison, decide at CONSULT how the gap gets
  its sealed number.** One sealed access per track means a single-track study can
  confirm only the incumbent's LEVEL. EITHER declare each model family its own
  track (the gap is a difference of two sealed numbers) OR pre-register the gap as
  exploratory-by-construction and say so. Choosing after the loop is how sealed
  vocabulary gets stretched.
- **Pre-script the branch you think will not fire.** Every registered prediction
  states what the study does on each verdict; an optional `stop:` rule
  (`max_consecutive_discards`) ends a losing phase on the record.
- **For `optimize` and checkpoint-scored studies, the verifier is part of the
  contract.** Name the checker script, its exactness and tolerance, and the external
  best-known value with its source (`metric.incumbent_external`); the METHOD gate
  hashes the script and the DATA gate's verifier card gives it a positive and a
  negative control.
- **Materiality is priced or absent.** If the user wants "material" or "actionable"
  in the findings, register a `materiality:` block (currency, unit, threshold, who
  priced it, when, on what basis). Without one, the findings may only say a
  registered bar was cleared — measurement resolution is never business value.
- Set budgets from the run-cost class (`defaults-and-scaffolding.md`; the profile's
  §6 table) — seconds for cheap runs, steps or tokens for long ones.

## Confirm — and STOP for ack

**Generation-enabled studies first.** If this study opts into the generation layer
(`references/generation-protocol.md`), `klein generation init` must already be
anchored before the gate is recorded — a consult record that precedes the opt-in fails
`klein generation verify` permanently, because a commitment registered after seeing
what it was supposed to constrain constrains nothing.
So must `klein generation expert lock` when the manifest declares `expertise`: the
method shortlist and the baseline targets have to precede the gate for the same
reason (`references/expert-protocol.md`).
And so must `klein generation knowledge query` when the manifest declares
`knowledge`: the consultation receipt is what the summary below cites. Present the
hits it returned with their contest closure, record a `use` or `reject` reason for
every one (`--use K1=<why>` / `--reject K2=<why>`, or `knowledge decide` before the
ack), and cite the explicit `no_match` receipt when the store held nothing — an
empty store is consulted, never skipped. A store read after the ack is a
bibliography, not a consultation, and FAILs `knowledge query`
(`references/knowledge-protocol.md`).

Present a concise summary: goal; kind / modality / profile with one line of reasoning
each; the track contracts (mode, metric, floor recipe, bound, verifier); the data
source and pin; the split; the phase ladder with budgets; the research questions with
priors and provenance; the predictions with their rules; what the scouting ledger
discloses. Then ask:

> Here is the study contract. Anything to change before we start the DATA gate?

WAIT for the user. Apply any changes to `study.yaml` + `program.md` immediately. Do NOT
proceed to the DATA gate until the user explicitly acks. Then record Gate 0 with
`klein gate record consult --study <study> --acknowledged-by <actor>` so the ack and
artifact hashes are machine-verifiable.

**Relay pattern for delegated runs.** When a tool runs this stage as an isolated
subagent (e.g. Claude Code's `klein-consultant`), that subagent cannot address the
user or write files: it RETURNS the interview questions (pass 1) and then the drafted
study.yaml / research_plan.md / program.md contents plus the exact `klein new` command
(pass 2) to the orchestrating session, which asks the user, writes the files, and owns
the ack. A session running this protocol solo — the default with any tool — does those
steps directly.

## Prior provenance

Every research-question prior names its source in parentheses:
`(source: knowledge/domains/insurance/gbdt-hyperparameter-guide.md#C2)`,
`(source: method_card §4)`, `(source: scouted)`, `(source: uninformed)`, or — on a
generation-enabled study — `(source: <study>#Hn)` for a prior that rests on an earlier
slate row and `(source: knowledge:K7)` for one that rests on a store object the
consultation receipt returned and the study recorded as `use`
(`references/knowledge-protocol.md`). Findings §⑥ then settles the scorecard — did knowledge-sourced priors
outpredict uninformed ones? — with scouted priors excluded, which is what makes the
knowledge promotion loop measurable rather than devotional. An enabled study's scorecard
also carries the slate calibration panels (`unscouted` and `derived` scored,
`scouted_descriptive` reported and never summarised as calibration), pinned as
`art:slate_calibration_<phase>`.
