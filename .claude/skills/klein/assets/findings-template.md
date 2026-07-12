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

## ① Research-question verdicts

One row per RQ in `study.yaml`. The verdict MUST cite evidence experiment IDs.

| RQ | Track | Verdict | Evidence level | Evidence (exp IDs) | Metric delta + uncertainty |
|---|---|---|---|---|---|
| RQ1 | primary | supported / refuted / inconclusive | exploratory / confirmed | E0003, E0006 | ... |

## ② Predictions to falsify (filled)

Copy the levers from `program.md`; fill observed + verdict from the trajectory.

| Lever | Predicted delta | Observed delta | Verdict | Evidence |
|---|---|---|---|---|
| ... | ... | ... | held / falsified | E... |

## ③ Surprises and why

What defied the prior, and the mechanism you believe explains it. Be concrete about the
"why" — a surprise with no explanation is a loose end for the next study.

## ④ Practical advice

"On your own data, do X, avoid Y." Concrete and numbered (the best-practices style):
what to reach for first, what to skip, the trap to avoid.

## ⑤ Business / actuarial value implications

Premium, calibration, filing, capital, triage — what the result is WORTH in decisions,
not just in metric points.

## ⑥ Literature tie-back

Did results match what the method-card papers claim? Where do they sit against the
trend (e.g. Grinsztajn "trees still win on tabular"; the DAE / SSL literature)?

## ⑦ What to try next

The next 2-4 experiments a follow-up study should run, in priority order.
