---
type: research-plan
domain: "{{DOMAIN}}"
status: draft
concepts: []
related: []
---

# Research plan — {{STUDY_ID}}

> CONSULT (Gate 0) output. Human-readable companion to `study.yaml`. Drafted from the
> ≤6 interview answers; confirmed with the user before the DATA gate.
> Protocol: `.claude/skills/klein/references/consult-protocol.md`.

## The question

{{GOAL}}

State it as a decision: what will the researcher DO differently depending on how this
study comes out? A study that changes no decision is not worth running.

## Why now / why this method

- What makes this worth a study (a gap, a frontier method, a business decision)?
- The honest prior — do you expect it to work? (Priors are recorded in `study.yaml`.)

## Data

- **Source:** {{DATA_SOURCE}}
- Availability, size, known issues. The DATA gate profiles it and rules go/no-go.

## Method

- The method(s) under study and the baseline(s) they must beat.
- The METHOD gate writes `method_card.md` (intuition → math → impl → when-it-pays).

## Metric & decision use

- **Primary metric:** `{{METRIC_NAME}}` ({{METRIC_GOAL}} is better).
- How does this metric map to a real decision (premium, filing, capital, triage)?

## Experiment ladder (sketch)

A rough ordered list — the loop ADAPTS, this is not a batch script.

1. E1 — split-identity anchor: reproduce a known baseline EXACTLY (gate: STOP if off).
2. E2 — first honest baseline the method must beat.
3. E3 — the method under study.
4. … — sweeps, ablations, second acts.

## Budgets & stop rule

- Per-phase budgets in `study.yaml:phases`. Stop rule: keep going until the user stops
  or a phase max is hit.

## Deliverables

- `findings.md` (7-section synthesis) and `report/index.html` (tutorial) — ALWAYS.
- Any study-specific docs.

## Risks & unknowns

- What could make this study inconclusive? (weak signal, tiny data, leakage, drift, ...)
- What would make you abandon the direction early?
