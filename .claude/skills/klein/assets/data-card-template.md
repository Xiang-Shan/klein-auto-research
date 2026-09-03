---
type: data-card
domain: "{{DOMAIN}}"
modality: "{{MODALITY}}"   # tabular | timeseries | image | sequence | graph | text | simulation | none
status: draft              # draft | go | no-go | go-with-cautions
concepts: []
related: []
---

# Data card — {{STUDY_ID}}

> Gate 1 (DATA). GIGO guard. Written BEFORE any modeling.
> Protocol: `.claude/skills/klein/references/data-gate-protocol.md`.
> Keep the sections your modality requires and delete the rest — the gate checks the
> required headings for the declared modality (`kleinlib.schema.MODALITY_CARD_SECTIONS`):
> every modality: Source & shape · Ranked go / no-go issues · Go / no-go;
> tabular, timeseries, image, sequence, graph, text: + Profile summary · Clean-room
> leakage audit; timeseries: + Time policy; image, sequence, graph, text: + Group
> policy; simulation: + DGP card; none: + Verifier card.

## Source & shape

- **Source tag:** `{{DATA_SOURCE}}` (resolved as printed on the `data source:` line) ·
  **Pin:** `data.sha256` … / not required
- **Modality:** {{MODALITY}} · **Rows × cols / items / objects:** … · **Target /
  estimand:** `{{TARGET}}` · **Positive rate / target mean:** …
- **Split policy:** `data.split` (`stratified | random | group | time`, seed, sizes) ·
  **Fingerprints frozen at this gate:** data …, split …
- **Profiler used:** global `dataset-profiler` skill if present, else
  `kleinlib.profile_fallback`.

## Profile summary

| Column / field | Dtype (value-pattern) | Missing % | Cardinality | ID-like? | Leakage risk? | Notes |
|---|---|---|---|---|---|---|
| … | … | … | … | … | … | … |

**Value-pattern check (mandatory war story):** never trust `dtype == "object"`.
Inspect the ACTUAL values — string-encoded booleans (`"Yes"`/`"No"`), numbers-in-strings
(`"120bhp@3000rpm"`), sentinels (`-999`, `""`, `"NA"`). Record what each column REALLY
holds, not what pandas guessed. For non-tabular modalities profile the index table
(`data/prepared/index.csv`: `id, group, time, split`) plus the modality statistics
(size, length, resolution, label provenance, duplicate and near-duplicate rate).

## Time policy

(timeseries) The cut dates for train / development / sealed; the features that use
only pre-cut information; the horizon; how look-ahead is prevented in `prepare.py`;
the leakage-through-time check that was run.

## Group policy

(image, sequence, graph, text) How the group id is computed in `prepare.py` (patient,
cluster at what similarity, scaffold, document, source), why that unit is the right
one for the question, and the group-overlap check on the index table.

## DGP card

(simulation) The declared truth in full: the generating equations or process, every
parameter and its value, the seed blocks (development / sealed), the sample sizes,
what "recover" means numerically (the criterion each prediction's rule uses), and the
in-silico scope sentence every `known-dgp-teaching` claim will carry.

## Verifier card

(none) The oracle: what it checks, `metric.exactness` (exact / stochastic), its cost
per call, the tolerance and how it was chosen, its known failure modes (floating
point, symmetry, degenerate inputs), the positive control (a hand-planted invalid
object it must reject) and the negative control (a known-valid object it must accept),
and the external best-known value with its source.

## Ranked go / no-go issues

Severity: **BLOCKER** (must fix before modeling) · **WARN** (proceed with care) ·
**NOTE** (informational). Order most-severe first. A literal split seed in any
evaluator or entrypoint is a BLOCKER (war story 8): partitions come from
`kleinlib.data.contract_split` / `load_partition`.

| # | Severity | Issue | Recommended action |
|---|---|---|---|
| 1 | BLOCKER | … | … |
| 2 | WARN | … | … |
| 3 | NOTE | … | … |

## Clean-room leakage audit

Performed in a FRESH context (separate agent/session, or self-performed only after the
profile is finished), reading ONLY `study.yaml`, `prepare.py`, the prepared artifact
(or the index table), and the profile — never `program.md`. Rows 3–4 are mechanized:
`uv run --locked python -m kleinlib.leakage <prepared> --target <col> --study <dir>`
(dataframe mode) or `... --index data/prepared/index.csv --study <dir>` (any modality
whose `prepare.py` emits the index table). Any FAIL is a **BLOCKER** (NO-GO until
fixed and re-audited).

| Check | Pass/Fail/N-A | Evidence |
|---|---|---|
| 1. Target leakage — no feature is a proxy/derivative of the target or post-outcome information | … | … |
| 2. Lookahead — encoders/imputers/scalers fit on train only; time-derived features precede the cut | … | … |
| 3. Split contamination — no duplicate rows straddling partitions; group ids never cross partitions; the split reproduces from `study.yaml` alone (fingerprint match) | … | … |
| 4. Eval-harness sanity — metric direction matches the contract; constant and shuffled predictors score at chance | … | … |

## Go / no-go

> **Decision:** GO · NO-GO · GO-WITH-CAUTIONS
>
> **Rationale:** …
>
> If NO-GO or any BLOCKER is open, modeling is HARD-BLOCKED. A v2 override must be
> recorded with `klein gate override data --acknowledged-by <actor> --reason <reason>`;
> also explain it in `program.md`. A prose-only fast path does not unlock modeling.
