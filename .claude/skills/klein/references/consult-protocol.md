# CONSULT — Gate 0

Advice for a vague or ambitious goal. Turn "I want to try X on my data" into a scoped
study: `study.yaml` + `research_plan.md` + a generated `program.md`. This gate ENDS with
an explicit user ack before the DATA gate begins.

Role: consultant. Any agent or human can execute this protocol directly — it is the
source of truth; Claude Code ships it pre-wired as the `klein-consultant` worker.

## The interview: at most six questions

Ask only what the brief has not already answered. Keep it to ONE short message; do not
interrogate. The six axes, with example phrasings:

1. **Goal / decision.** "What question should this study answer, and what will you do
   differently depending on how it comes out?" A study that changes no decision is not
   worth running.
2. **Data availability & size.** "What data do you have — source, rough rows × columns,
   and the target column? If none, should we build a synthetic known-truth lab instead?"
3. **Method familiarity.** "Is the method one you know well, or one you've only read
   about? Frontier / unfamiliar methods get a full METHOD gate (intuition → math → refs)."
4. **Metric & decision use.** "For each distinct task, what primary metric should its
   track optimize, higher or lower, what minimum delta matters, and which guardrails
   must hold?" Never combine unrelated tasks into one global frontier.
5. **Compute / time budget.** "What are the maximum seconds for one run, each phase's
   total budget, and its experiment-count cap?" These are separate controls.
6. **Deliverable form.** "Besides the always-on `findings.md` + HTML tutorial, do you
   want any study-specific docs?"

### Fast-path

If the brief already answers FIVE or more of the six, do NOT re-ask. Draft everything,
then present a single CONFIRM-ONLY summary (below). Ask only about the one genuinely
missing axis.

## Draft the artifacts

From the answers, scaffold, then fill:

```bash
uv run --locked klein new NN-slug \
    --goal "..." --domain ... --metric ... --goal-direction higher|lower --data "..."
```

Fill in `study.yaml`: `schema_version: 2`, explicit `task_type`, `method_depth`, one or
more track metric contracts (name, direction, minimum delta, guardrails), a three-way
train/development/test split, `max_run_seconds`, phases with independent
`budget_seconds` and `max_experiments`, research questions with honest priors, and
signed/unit-bearing predictions to falsify. Mirror the phases, RQs, and predictions
into `program.md`; sketch the experiment ladder in `research_plan.md`.

Rules for good drafting:

- **Priors must be honest.** Write what you actually expect ("no lift over 0.67"), not
  what you hope. SYNTHESIZE holds each prior to account.
- **Predictions must be falsifiable.** "swap-rate 0.25 gives +0.001 val_auc", not "tuning
  helps".
- **Phase 0 is always a split-identity anchor** when a comparable baseline exists —
  reproduce it EXACTLY (STOP if off) before exploring. This catches split/leakage bugs
  before they poison every later comparison.
- **Then measure the noise floor — never guess `minimum_delta`.** After the anchor,
  run a k-seed measurement sweep of the SAME config varying only the seed (k=5
  default; k=3 if one run exceeds ~5 minutes) via `sweeps/noise_floor.py` →
  `sweeps/noise_floor.sidecar.tsv` (a measurement sweep promotes NO winner — see the
  carve-out in `sweep-rules.md`). Then `klein noise-floor --study <dir>` prints the
  per-track `noise_floor:` block; set `minimum_delta = max(2×std, range/2)` in
  `study.yaml` and re-record the consult gate with
  `--note "minimum_delta set from the measured noise floor"`. Preflight fails a
  `minimum_delta` set inside a declared floor, and findings must report any delta
  under 2× the floor std as within-noise.
- Set budgets from the problem class (see `defaults-and-scaffolding.md`).

## Confirm — and STOP for ack

Present a concise summary: goal, metric contract, data source, split, the phase ladder
with budgets, the research questions with priors, and the predictions to falsify. Then
ask:

> Here is the study contract. Anything to change before we start the DATA gate?

WAIT for the user. Apply any changes to `study.yaml` + `program.md` immediately. Do NOT
proceed to the DATA gate until the user explicitly acks. Then record Gate 0 with
`klein gate record consult --study <study> --acknowledged-by <actor>` so the ack and
artifact hashes are machine-verifiable.

**Relay pattern for delegated runs.** When a tool runs this stage as an isolated
subagent (e.g. Claude Code's `klein-consultant`), that subagent cannot address the
user or write files: it RETURNS the interview questions (pass 1) and then the drafted
study.yaml/research_plan.md/program.md contents plus the `new_study.py` command (pass 2)
to the orchestrating session, which asks the user, writes the files, and owns the ack.
A session running this protocol solo — the default with any tool — does those steps
directly.

## Prior provenance

Every research-question prior names its source in parentheses:
`(source: knowledge/gbdt-hyperparameter-guide.md#C2)`, `(source: method_card §4)`,
or `(source: uninformed)`. Findings §⑥ then settles the scorecard — did
knowledge-sourced priors outpredict uninformed ones? — which is what makes the
knowledge promotion loop measurable rather than devotional.
