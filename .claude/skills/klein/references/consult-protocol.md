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
4. **Metric & decision use.** "What single metric should every experiment optimize,
   higher or lower — and how does it map to a real decision (premium, filing, triage)?"
5. **Compute / time budget.** "Roughly how long can each experiment run, and how long the
   whole study? (Sets per-phase budgets; the default is keep-going-until-you-stop.)"
6. **Deliverable form.** "Besides the always-on `findings.md` + HTML tutorial, do you
   want any study-specific docs?"

### Fast-path

If the brief already answers FIVE or more of the six, do NOT re-ask. Draft everything,
then present a single CONFIRM-ONLY summary (below). Ask only about the one genuinely
missing axis.

## Draft the artifacts

From the answers, scaffold, then fill:

```bash
uv run python .claude/skills/klein/scripts/new_study.py NN-slug \
    --goal "..." --domain ... --metric ... --goal-direction higher|lower --data "..."
```

Fill in `study.yaml`: `target`, `family`, `data.split`, the `phases` ladder with budgets,
`research_questions` (each with an HONEST `prior`), and `predictions_to_falsify` (each a
signed, unit-bearing `predicted_delta`). Mirror the phases, RQs, and predictions into
`program.md`; sketch the experiment ladder in `research_plan.md`.

Rules for good drafting:

- **Priors must be honest.** Write what you actually expect ("no lift over 0.67"), not
  what you hope. SYNTHESIZE holds each prior to account.
- **Predictions must be falsifiable.** "swap-rate 0.25 gives +0.001 val_auc", not "tuning
  helps".
- **Phase 0 is always a split-identity anchor** when a comparable baseline exists —
  reproduce it EXACTLY (STOP if off) before exploring. This catches split/leakage bugs
  before they poison every later comparison.
- Set budgets from the problem class (see `defaults-and-scaffolding.md`).

## Confirm — and STOP for ack

Present a concise summary: goal, metric contract, data source, split, the phase ladder
with budgets, the research questions with priors, and the predictions to falsify. Then
ask:

> Here is the study contract. Anything to change before we start the DATA gate?

WAIT for the user. Apply any changes to `study.yaml` + `program.md` immediately. Do NOT
proceed to the DATA gate until the user explicitly acks. This ack is a Hard Rule — the
gates hard-block modeling, and CONSULT is the first gate.

**Relay pattern for delegated runs.** When a tool runs this stage as an isolated
subagent (e.g. Claude Code's `klein-consultant`), that subagent cannot address the
user or write files: it RETURNS the interview questions (pass 1) and then the drafted
study.yaml/research_plan.md/program.md contents plus the `new_study.py` command (pass 2)
to the orchestrating session, which asks the user, writes the files, and owns the ack.
A session running this protocol solo — the default with any tool — does those steps
directly.
