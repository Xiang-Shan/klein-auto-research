---
type: data-card
domain: "{{DOMAIN}}"
status: draft        # draft | go | no-go | go-with-cautions
concepts: []
related: []
---

# Data card — {{STUDY_ID}}

> Gate 1 (DATA). GIGO guard. Written BEFORE any modeling.
> Protocol: `.claude/skills/klein/references/data-gate-protocol.md`.

## Source & shape

- **Source:** {{DATA_SOURCE}}
- **Rows × cols:** …  ·  **Target:** `{{TARGET}}`  ·  **Positive rate / target mean:** …
- **Profiler used:** global `dataset-profiler` skill if present, else
  `kleinlib.profile_fallback`.

## Profile summary

| Column | Dtype (value-pattern) | Missing % | Cardinality | ID-like? | Leakage risk? | Notes |
|---|---|---|---|---|---|---|
| … | … | … | … | … | … | … |

**Value-pattern check (mandatory war story):** never trust `dtype == "object"`.
Inspect the ACTUAL values — string-encoded booleans (`"Yes"`/`"No"`), numbers-in-strings
(`"120bhp@3000rpm"`), sentinels (`-999`, `""`, `"NA"`). Record what each column REALLY
holds, not what pandas guessed. This one check has saved whole campaigns.

## Ranked go / no-go issues

Severity: **BLOCKER** (must fix before modeling) · **WARN** (proceed with care) ·
**NOTE** (informational). Order most-severe first.

| # | Severity | Issue | Recommended action |
|---|---|---|---|
| 1 | BLOCKER | … | … |
| 2 | WARN | … | … |
| 3 | NOTE | … | … |

## Clean-room leakage audit

Performed in a FRESH context (separate agent/session, or self-performed only after the
profile is finished), reading ONLY `study.yaml`, `prepare.py`, the prepared artifact,
and the profile — never `program.md`. Rows 3–4 are mechanized:
`uv run --locked python -m kleinlib.leakage <prepared> --target <col> --study <dir>`.
Any FAIL is a **BLOCKER** (NO-GO until fixed and re-audited).

| Check | Pass/Fail/N-A | Evidence |
|---|---|---|
| 1. Target leakage — no feature is a proxy/derivative of the target or post-outcome information | … | … |
| 2. Lookahead — encoders/imputers/scalers fit on train only; time-derived features precede the cut | … | … |
| 3. Split contamination — no duplicate rows straddling partitions; group ids never cross partitions; the split reproduces from `study.yaml` | … | … |
| 4. Eval-harness sanity — metric direction matches the contract; constant and shuffled predictors score at chance | … | … |

## Go / no-go

> **Decision:** GO · NO-GO · GO-WITH-CAUTIONS
>
> **Rationale:** …
>
> If NO-GO or any BLOCKER is open, modeling is HARD-BLOCKED. A v2 override must be
> recorded with `klein gate override data --acknowledged-by <actor> --reason <reason>`;
> also explain it in `program.md`. A prose-only fast path does not unlock modeling.
