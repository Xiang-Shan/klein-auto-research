---
type: findings
domain: "{{DOMAIN}}"
profile: "{{PROFILE}}"
kind: "{{KIND}}"
status: draft
concepts: []
related: []
---

# Findings — {{STUDY_ID}}

> SYNTHESIZE stage output. QUALITY BAR: every claim cites evidence ids from the
> immutable run manifests / derived results; no claim without evidence. Track
> frontiers stay separate, conclusions carry a strength (exploratory / confirmed) and
> a class, and contradictions with the registered predictions are called out
> explicitly. Protocol: `.claude/skills/klein/references/synthesis-protocol.md`;
> the lock and the numbers law: `references/claims-protocol.md`.
>
> CLAIM IDs: every ① verdict and every ④ advice item carries a stable ID —
> `**[C1]**, **[C2]**, ...` — never renumbered once published. Fully qualified
> form: `<study_id>#C<n>`. The same ids live in `claims.lock` with their class,
> strength, pinned artifact and evidence; knowledge/ docs cite them with a typed verb:
> `(supports 03-noisy-rosenbrock-dfo#C3)` / `(refutes 09-iris-first-lesson#C15)`.

## ① Research-question verdicts

One row per RQ in `study.yaml`. The verdict MUST cite evidence ids
(`E####`, `sweep:<name>`, `rep:E####@<ts>`, `verify:E####@<ts>`, `art:<alias>`).

| Claim | RQ | Track | Verdict | Strength | Class | Evidence | Delta + uncertainty |
|---|---|---|---|---|---|---|---|
| **[C1]** | RQ1 | primary | supported / refuted / inconclusive | exploratory / confirmed | empirical-description / procedural-verdict / mechanism-interpretation / known-dgp-teaching / research-discipline | E0003, E0005 | … |

## ② Registered predictions (from the ledger)

One row per `P#` in `study.yaml`, in id order. `Verdict` is COPIED from
`study_state.json` (`klein predict list`), never re-decided here; a refuted row names
the dated `Decision:` line in `program.md` that answered it.

| P# | Statement | Rule | Observed | Verdict (ledger) | Evidence | Decision |
|---|---|---|---|---|---|---|
| P1 | … | `{key, op, value}` | … | supported / refuted / inconclusive | E… | program.md 2026-… |

## ③ Surprises and why

What defied the prior, and the mechanism you believe explains it. A mechanism is a
`mechanism-interpretation` claim: exploratory by class, however convincing. A surprise
with no explanation is a loose end for the next study.

## ④ Practical advice

"On your own data, do X, avoid Y." Concrete, and every item carries the next claim
ID (continue the ① numbering): `**[C4]** Reach for ... first (evidence: E0003).`

## ⑤ {{SECTION5_HEADING}}

The heading and its prompt come from the study's profile
(`references/profiles/<profile>.md` §2). Whatever the audience: nothing here is
priced without a registered `materiality:` block, and "actionable" means only that a
registered bar was cleared.

## ⑥ Literature tie-back

Did results match the references (`references.yaml`, all `verified: true` behind any
confirmed claim)? Where do they sit against the profile's doctrine anchor? Settle the
priors' scorecard: did knowledge-sourced priors outpredict `uninformed` ones
(`scouted` priors are excluded)? A knowledge doc that mispredicted gets updated at
promotion.

## ⑦ What to try next

The next 2-4 experiments a follow-up study should run, in priority order. A
`discover` study sketches the `test` study that could promote its hypotheses.

## Errata (appendix — present only when an erratum is filed)

| Erratum | Filed | Claims re-scoped | What is now known |
|---|---|---|---|
| E1 | … | C3, C7 | … |
