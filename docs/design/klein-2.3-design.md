# Klein 2.3 — a trust kernel, domain packs, host bridges

Klein 2.0 asked what a research study IS, independent of its field, and answered with a
kernel: a typed question, predictions registered with arithmetic rules before their
evidence, a notary that commits a candidate before running it and decides by the
contract's arithmetic, a hash-chained event log, a claims lock in which every number has
a pinned home, and a referee who did not run the loop. 2.0–2.2 proved that kernel on
tables, a simulator, a verifier and a character model. This document records why 2.3 is
shaped as it is: the kernel did not change; what was tabular-first around it did.

## 1. What was tabular-first

An honest inventory taken before 2.3 (the plan of record is in the repository history):

- **Scoring.** The evaluator registry knew twelve metrics, and the main evaluator was
  binary-only. Vision and LLM work fell back to a scalar evaluator and lost the collapse
  guard, row counts and chance audits that protect a tabular study.
- **Data.** A split needed a target column, so a study of images or text either faked one
  (study 13 split on `n_chars`) or got a warning instead of a realized split check. One
  input file per study; no Hugging Face source; leakage meant exact ids.
- **Execution.** The whole run log was the metric channel — a training line `loss: nan`
  crashed a run, `epoch: 3` leaked into its metrics. Budgets were wall-clock only. A seed
  was one run. Remote compute meant a blocking wrapper. Nothing recorded the GPU, and
  nothing accounted for a model API's tokens.
- **Onboarding.** About twenty steps, four gate records and ten hand-written artifacts
  before the first run; the profiles covered generic, ML research, math and insurance.
- **Hosts.** No MCP, notebook or literature-connector path; Claude Science was a row of
  prose. A wheel install silently skipped the banned-word scan because the profiles lived
  in `.claude/`.

## 2. The design

```
            ┌───────────────────────── host bridges ─────────────────────────┐
            │ klein next · status --json · klein mcp (read-only) · notebook  │
            │ Claude Science kit · doctor --host · refs verify               │
            ├───────────────────────── domain packs ─────────────────────────┤
            │ recipes · evaluators · data-card variants · leakage audits     │
            │ profiles · method cards · knowledge seeds                      │
            ├───────────────────────── trust kernel ─────────────────────────┤
            │ notary transaction · events · manifests · claims law ·         │
            │ predictions ledger · referee gate · verify receipt             │
            └────────────────────────────────────────────────────────────────┘
```

**Kernel — semantics unchanged.** No rule a shipped study was judged under moved. The
golden parse test freezes, for every shipped exit-0 manifest, that re-parsing its log
gives the metrics it recorded; `scripts/verify_shipped_studies.py` re-verifies every
study with zero failures.

**Domain packs — content and code that plug into the kernel's seams.** A recipe is a
scaffold, not a framework: it writes a contract and runnable code, then leaves `{{…}}`
wherever a human judgment belongs (predictions, priors, a data card's findings), so the
consult and data gates still refuse a study nobody thought about. Evaluators print the
same canonical block every evaluator prints, so the notary needs no new code to judge a
multiclass, per-item, ranking, survival or segmentation run.

**Host bridges — read the ledger anywhere, write it only through the notary.** `klein
next` answers "what now?" from the records alone; `klein mcp` serves the same answers to
any MCP client and has no write tool at all; the Claude Science kit maps each Klein stage
to the workbench feature that serves it and keeps the referee outside the session that
did the work.

## 3. The version gate (the verify-forever rule)

Every behaviour that changes how a run is judged lives in an **allowlisted nested
contract block** that 2.3 scaffolds write: `entrypoint.printed`, `entrypoint.seeds`,
`entrypoint.execution`, the index keys of `data.split`, `calls:`. A 2.2 engine reading a
2.3 study refuses the unknown key loudly instead of judging the study by older rules.
Strictness-only knobs live in a top-level `policy:` map — an engine that ignores them is
merely less strict, never wrong. Split knobs sit inside `data.split`, so the split-policy
hash the DATA gate freezes covers them. A manifest records the rule it was judged under
only when that rule is non-default (`printed_scope: block`), and `klein replicate`
follows the manifest, never today's contract — so legacy manifests stay byte-identical
and a replication of an old run uses the old rule. New `klein verify` rows appear only
when the contract declares the field they audit, so an old study's receipt lists the same
checks it always did.

## 4. Decisions worth defending

- **Block-scoped metrics are opt-in, not the default.** Changing the default would have
  re-judged every shipped log. A study opts in at scaffold time (every recipe does); the
  manifest says so.
- **Seeds are a contract field, not a flag.** A flag lets N be chosen after the first
  seed's result; a field is hashed at CONSULT.
- **The call ledger is in the entrypoint's process, never in a Klein verb.** An import
  graph test proves `kleinlib.cli` and the verify path never load it. A replay from the
  ledger is a `replay:` record and never satisfies `confirmation.require: [replicate]` —
  re-reading what a model said is not asking it again.
- **Detached runs split one transaction, they do not add a scheduler.** One open
  detached run per study, the study frozen until collect or abandon, the receipt checked
  against a committed job bundle, the run judged locally by the same code as a
  foreground run, and the manifest saying `observed_by_notary: false`. The referee
  weighs attested runs as attested.
- **`klein mcp` is stdlib and read-only.** A dependency-free server works in hosts whose
  installers take only wheels; an MCP tool that recorded a gate would let a model
  acknowledge for a person, and an experiment outlives an MCP call's timeout.
- **`klein refs verify` is opt-in network and never part of `verify`.** `klein verify`
  must give the same answer offline in ten years; a DOI resolver may not.
- **Fixes found by exhibits land in the engine, not in the study.** Study 23's data gate
  found that the leakage audit could not reproduce a scalar-task or predefined split; the
  audit was fixed (with tests) rather than the FAIL waived. Study 21's found real
  cross-split duplicates in an official benchmark split; `prepare.py` removed them by the
  audit's own rule rather than accepting a tolerance.

## 5. Positioning

A research workbench — Claude Science, a lab notebook, an agent framework — owns
connectors, compute and conversation. Klein owns none of those. It is the discipline
that makes a workbench's output auditable by a stranger with no model in the loop: the
question typed, the prediction registered with a rule, the run notarized, the claim
locked to a pinned number, the verdict written by someone who did not do the work. 2.3
makes that discipline available in the domains where AI for Science work actually happens
— vision, deep learning, LLM evaluation, causal data science, mathematics — and in the
hosts researchers actually use.

## 6. Not in 2.3

Detection mAP (VOC and COCO conventions differ enough that a shipped evaluator would
choose for the user); a scheduler or parallel candidate execution (the driving agent IS
the loop); a hosted service; any Klein verb that calls a model. The Claude Science kit is
written against the product's published documentation; its live smoke record needs a
person with a seat.
