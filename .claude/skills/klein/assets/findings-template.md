---
type: findings
domain: "{{DOMAIN}}"
status: draft
concepts: []
related: []
---

# Findings — {{STUDY_ID}}

> SYNTHESIZE stage output. QUALITY BAR: every claim cites experiment IDs from the
> immutable run manifests / derived results; no claim without evidence. Track
> frontiers stay separate, conclusions are labelled exploratory or confirmed, and
> contradictions with the method-card priors are called out explicitly. Protocol:
> `.claude/skills/klein/references/synthesis-protocol.md`.
>
> CLAIM IDs: every ① verdict and every ④ advice item carries a stable ID —
> `**[C1]**, **[C2]**, ...` — never renumbered once published. Fully qualified
> form: `<study_id>#C<n>`. knowledge/ docs cite them with a typed verb:
> `(supports 03-noisy-rosenbrock-dfo#C3)` / `(refutes 00-glm-claims-quickstart#C1)`.

## ① Research-question verdicts

One row per RQ in `study.yaml`. The verdict MUST cite evidence experiment IDs.

| Claim | RQ | Track | Verdict | Evidence level | Evidence (exp IDs) | Metric delta + uncertainty |
|---|---|---|---|---|---|---|
| **[C1]** | RQ1 | primary | supported / refuted / inconclusive | exploratory / confirmed | E0003, E0006 | ... |

## ② Predictions to falsify (filled)

Copy the levers from `program.md`; fill observed + verdict from the trajectory.

| Lever | Predicted delta | Observed delta | Verdict | Evidence |
|---|---|---|---|---|
| ... | ... | ... | held / falsified | E... |

## ③ Surprises and why

What defied the prior, and the mechanism you believe explains it. Be concrete about the
"why" — a surprise with no explanation is a loose end for the next study.

## ④ Practical advice

"On your own data, do X, avoid Y." Concrete, and every item carries the next claim
ID (continue the ① numbering): `**[C4]** Reach for ... first (evidence: E0003).`

## ⑤ Business / actuarial value implications

Premium, calibration, filing, capital, triage — what the result is WORTH in decisions,
not just in metric points.

## ⑥ Literature tie-back

Did results match what the method-card papers claim? Where do they sit against the
trend (e.g. Grinsztajn "trees still win on tabular"; the DAE / SSL literature)?
Also settle the priors' scorecard: did knowledge/-sourced priors outpredict
`uninformed` ones? A knowledge doc that mispredicted gets updated at promotion.

## ⑦ What to try next

The next 2-4 experiments a follow-up study should run, in priority order.
