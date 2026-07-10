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

## Go / no-go

> **Decision:** GO · NO-GO · GO-WITH-CAUTIONS
>
> **Rationale:** …
>
> If NO-GO or any BLOCKER is open, modeling is HARD-BLOCKED. The only override is a
> logged `--fast-path`, recorded WITH A REASON in `program.md`.
