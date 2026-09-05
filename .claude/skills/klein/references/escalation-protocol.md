# ESCALATION — getting unstuck, accounted for, without automating it

A study that stalls is the moment its record is worth the least and the
temptation is worth the most. The evidence has stopped moving, the deadline has
not, and every way out — retune the same method, reach for more data, ask
somebody, change the question — is available *and* deniable afterwards. The
cheapest repair is always the one nobody writes down: a fourth round of the same
tuning quietly relabelled "data leverage", or the threshold that declared the
stall edited until the stall goes away.

The `escalation` capability makes those two moves expensive. `escalation_plan.yaml`
is locked at CONSULT, **before the consult gate**, freezing the arithmetic that
says a stall happened, the ladder of responses, the budgets they may spend, and
how the study is allowed to end. From then on, a tripped trigger blocks the next
candidate's admission until a `<study>#Dn` decision is on the record, and the
decision has to name the concrete resource or assumption it changes. Opt-in,
schema-3 only, and inert unless `generation/manifest.yaml` declares `escalation`
(`references/generation-protocol.md`).

> **The CLI neither chooses a rung nor launches, schedules, or retries work.** It
> reconstructs counts from the manifests, refuses an admission while a declared
> trigger stands undischarged, and does arithmetic on rows the driver wrote.
> Whether the work under a rung label deserves that label stays reviewable
> judgement — which is why every receipt must name what concretely changed.

Role: the driving agent, at CONSULT and then at every stall. Any agent or human
can follow this document directly.

## Verbs

```bash
uv run --locked klein generation escalate lock   --study studies/NN-slug [--allow-late]
uv run --locked klein generation escalate record --study studies/NN-slug \
    --trigger T1 [--track primary] --rung metric_diagnosis \
    [--skip <rung>="<why it does not apply>"]… \
    --action "…" --changed "…" --rationale "…" [--next "…"] [--successor NN-slug] \
    --estimated-cost compute=2 --estimated-cost person_time=1 \
    --estimated-cost money=0 --estimated-cost samples=0 \
    [--advisor NAME --advice "…" [--advice-accepted] [--advice-cost money=200]]
uv run --locked klein generation escalate close  --study studies/NN-slug --decision NN-slug#D1 \
    --actual-cost compute=3 --actual-cost person_time=unknown \
    --actual-cost money=0 --actual-cost samples=0 \
    [--cost-evidence "…"] --outcome "…"
uv run --locked klein generation escalate pivot  --study studies/NN-slug --decision NN-slug#D5 \
    --successor MM-slug --new-contract studies/MM-slug/study.yaml [--inherited scouted=…]
uv run --locked klein generation escalate show   --study studies/NN-slug
```

Every writing verb takes the four testimony flags `--actor --tool --model
--session` (recorded, never authenticated). Exit codes follow the layer's
convention: `0` did it, `1` the study is not in a state where the question can be
asked, `2` the question was asked and answered no. `show` writes nothing and
commits nothing.

## 1. The plan, locked before CONSULT

Copy `assets/escalation-plan-template.yaml` to the study as
`escalation_plan.yaml`, fill it, and lock it before `klein gate record consult`:

```yaml
type: escalation-plan
study: NN-slug
triggers:
  - {id: T1, kind: consecutive_discards, max: 5, scope: track, track: null}
  - {id: T2, kind: headroom_closed}
  - {id: T3, kind: budget_exhausted, phase: adaptive-1}
evidence_window: {runs: 5}
rungs: [metric_diagnosis, method_family, data_leverage, adjacent_field_analogy, human_expert]
budgets: {compute: 100, person_time: 8, money: 0, samples: unknown}
terminal_actions: [stop, pivot]
```

`lock` validates every field against the contract — a trigger naming an
undeclared track or phase, a ladder that is not exactly those five rungs in that
order, a budget missing a unit, `terminal_actions` without `stop` — and refuses
rather than record a plan the arithmetic cannot read. The lock stores the
document verbatim plus the sha256 of the file, and the plan is locked **once**:
a second lock is refused, and an edited file FAILs `escalation plan` for the life
of the study. `--allow-late` records a lock after the consult gate and FAILs the
same check permanently, because a stall rule written once the study is running
cannot constrain it.

## 2. Triggers are reconstructed, never asserted

A receipt claiming "we were stuck" proves nothing. Every trigger is recomputed
from evidence the study already committed:

| kind | reconstructed from | tripped when |
|---|---|---|
| `consecutive_discards` | the run manifests, through `kleinlib.stop.consecutive_discards` — a discard increments, a `keep` or `measured` resets, a `crash` is stepped over, sealed evidence never counts | the trailing run reaches `max` in `scope` |
| `headroom_closed` | the contract's `metric.bound` and the track's incumbent, through the same `kleinlib.decision` helpers `run-one` enforces on | `h = (incumbent − ideal) / minimum_delta < 1` on any track |
| `budget_exhausted` | the manifests of the named phase against its registered `max_experiments` | the phase has spent its experiments |

`budget_exhausted` counts experiments, not seconds: `budget_seconds` is the
core's own limit and `run-one` already refuses past it, so counting it here would
report a stall the notary had already prevented.

**Once a trigger trips, `klein generation check` refuses `--action run` and every
`--hypothesis` admission** — naming the trigger, its count and its evidence run
ids — until a decision citing that trigger is recorded after the tripping run.
Baseline, repair, calibration, cell and sealed admissions are not blocked: a
metric diagnosis or a confirmation is not more of the same, and making the ladder
harder to climb than to ignore would defeat it.

The discharge is scoped to the COUNT, exactly like `klein stop ack`: a decision
answers the stall as it stood, and the next discard trips the trigger again.
Editing the plan file changes nothing — `check` reads the locked document, so
widening a threshold after the fact cannot discharge a stall, and the edit FAILs
verification besides.

## 3. The ladder, and what a decision must say

Five rungs, one fixed order, cheap and local before expensive and external:

1. **`metric_diagnosis`** — direction, estimand, resolution, headroom. The
   diagnosis may not LOWER a bar to rescue a result; a changed `minimum_delta`,
   estimand, split contract, question or `kind` is a successor study, not a
   diagnosis.
2. **`method_family`** — a different family, not another tuning round.
3. **`data_leverage`** — more or different evidence: another season of field
   sampling, another characterization assay, another cohort.
4. **`adjacent_field_analogy`** — a cited correspondence and a falsifiable
   transferred prediction. A metaphor is not a rung.
5. **`human_expert`** — a named advisor, the advice verbatim, the acceptance
   decision and its cost. Expertise that was not available is recorded as
   unavailable, never as absent.

`stop` is not on the list because it is available from anywhere: **stopping is
always a recorded option**, and a phase that ends is a decision, not a failure to
decide.

Each rung is CONSIDERED in order. Taking rung *k* requires every lower rung to
have been taken earlier **in this episode** or to be skipped here with a written
reason (`--skip method_family="only one family is licensed for this estimand"`).
A silent skip is refused. An episode is one stall, from its first decision until
one of its decisions is closed; the next record opens the next episode, so a
second stall cannot inherit the first one's excuses.

Every decision records: the trigger with its evidence ids and reconstructed
count, the rung, the skipped rungs with reasons, the considered action, **the
concrete changed resource or assumption**, the rationale, the estimated cost, the
condition that would close it, and — at the human rung — the advice, its
acceptance and its cost. The changed-resource field is the one A3 §4 names as the
answer to the relabelling failure: an agent that retunes the same method a fourth
time and calls it "data leverage" has to write down what data it leveraged.

## 4. Costs are unit-bearing, and unknowns are recorded

Costs are vectors over **compute, person_time, money, samples** — all four
present, every time. A missing unit is refused, because an unrecorded cost is not
a zero cost. A unit that genuinely cannot be measured is the word `unknown`, and
closing with an unknown costs a `--cost-evidence` line saying why.

`escalate close` adds the outcome and the actuals; a decision at the `stop` rung
closes as `stopped` rather than `closed`. Verification recomputes the running
total per unit — actuals where they exist, estimates otherwise — against the
locked `budgets`, and FAILs a cap passed without an earlier decision whose
`considered_action` begins with the token `extend-budget`. The token is read, not
the sentence: `extend-budget: two more GPU-days` counts, "we may need more
budget" does not.

An OPEN decision with more runs after it than `evidence_window.runs` FAILs as
`decision recorded after its action` — a receipt that never closed while the work
went on is a description of what happened, not a commitment made before it.

## 5. Pivots and successor studies

Changing the scientific metric, the data or split contract, the question or the
`kind` is not a rung — it is a new study. `escalate pivot` links it from the
decision that called for it and records, in one object: both contract hashes (the
predecessor's `study.yaml` **as committed**, and the successor's), the successor
id, the **inherited exposure** (each spent seal, the development partition every
adaptive run has read, every scouted id, plus anything Klein cannot see, passed
with `--inherited kind=ref`), and every `<study>#Hn` / `<study>#Sn` id the
predecessor issued.

The successor cites the receipt back:

```bash
uv run --locked klein generation init --study studies/MM-slug \
    --capability escalation --predecessor NN-slug --successor-receipt <pivot object sha>
```

and its own `escalation predecessor` check reads that object out of the
predecessor's store and confirms it is a pivot naming this study. A predecessor
that cannot be resolved from here (a different repository, an archived study) is
a WARN: the link is recorded, not verified.

> **A successor id restores no blindness.** It does not replenish a spent seal,
> un-see a development partition, or make an already-scouted outcome prospective
> again. That is precisely what `inherited_exposure` is for, and why the list is
> computed rather than typed.

## 6. Verification

`klein generation verify` runs six checks for a declaring study:

| Check | FAILs on |
|---|---|
| `escalation plan` | no lock; a late lock; more than one lock; the file's sha256 no longer matching the lock; a locked document that no longer validates against the contract |
| `escalation triggers` | a decision citing a trigger the plan does not declare; a `reconstructed_count` that does not recompute from the manifests as of that decision's anchor; a `run` admission granted while a trigger stood tripped with no decision between them. A live tripped trigger with no decision yet is a WARN — the refusal is `check`'s job |
| `escalation receipts` | an episode number that does not recompute from the chain; an unaccounted rung; a decision naming no changed resource or assumption; an open decision outliving `evidence_window` |
| `escalation costs` | an estimate or actual missing a unit; an unknown actual with no cost evidence; a budget passed with no prior `extend-budget` decision |
| `escalation pivot` | a pivot naming no decision or no successor; an uncommitted pivot object; an `old_contract_sha256` that is not the sha256 of `study.yaml` at the pivot's own introducing commit |
| `escalation predecessor` | a declared predecessor with no `successor_receipt`; a receipt sha the predecessor's store does not hold; an object that is not a pivot naming this study |

The capability outcome is `none | escalated | stopped | pivoted`, reported beside
its integrity and never conflated with it: a study that stalled, climbed all five
rungs and stopped has an outcome of `stopped` and an integrity of `PASS`.

## What this establishes, and what it does not

**Establishes.** That the stall rule was registered before the stall it declared;
that a decision citing that trigger was filed after the tripping run and before
the next candidate's admission; that each lower rung was taken or excused in
writing; that costs carry units and unknowns are declared; that budgets were not
passed silently; and that a pivot did not quietly rewrite the contract it left
behind.

**Does not establish.** That the rung label fits the work — whether a fourth
tuning round really is "data leverage" is reviewable judgement and the referee's
to make, which is why the changed resource is written down. That the analogy
holds, that the advice was good, or that the successor's question is better. That
the `next_condition` was met: it is prose, recorded and never evaluated. That the
costs are accurate — they are testimony. And, as everywhere in this layer, local
ordering is not independently established chronology: a party who rewrites both
chains and git history wholesale is not detected (`references/generation-protocol.md`,
"What the witnesses do not prove").
