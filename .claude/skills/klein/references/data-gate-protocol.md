# DATA — Gate 1 (GIGO guard)

No modeling until the data is profiled and ruled fit. Output: `data_card.md` with a
ranked go/no-go issue list. This gate encodes the string-dtype war story as a mandatory
check.

Role: data auditor. Any agent or human can execute this protocol directly — it is
the source of truth; Claude Code ships it pre-wired as the `klein-data-auditor` worker.

## Profile the dataset

Run prep first so you profile the PREPARED artifact (the thing train.py sees):

```bash
uv run --locked python ../../scripts/run_with_log.py \
  --timeout-seconds <max-run-seconds> --log prepare.log -- \
  uv run --locked python -u prepare.py
```

Then profile. Prefer the global skill; fall back to the bundled profiler:

- **If the `dataset-profiler` skill is available** (check: does
  `~/.claude/skills/dataset-profiler/SKILL.md` exist?): use it on the prepared data (or
  the `data_hub` name). A main session invokes the skill directly; a worker agent
  without the Skill tool reads that SKILL.md and drives its `scripts/profile.py` via
  Bash. It reports dtypes, missingness, cardinality, ID-like and target-leakage flags,
  and the modeling implications.
- **Else:** `kleinlib.profile_fallback` — the same profile from stdlib + pandas
  (CLI: `uv run --locked python -m kleinlib.profile_fallback <prepared.csv> --target <col>`).

Copy `assets/data-card-template.md` to the study as `data_card.md` and fill the profile
summary table from the profiler output.

## The mandatory value-pattern check

This is non-negotiable and has saved whole campaigns. For EVERY column:

- Do NOT trust `dtype == "object"` or `dtype == "string"`. Inspect the ACTUAL values.
- Flag string-encoded booleans (`"Yes"`/`"No"`), numbers-in-strings
  (`"120bhp@3000rpm"`), sentinels (`-999`, `""`, `"NA"`, `"unknown"`), mixed types.
- Record what each column REALLY holds. A silently-skipped categorical or a string-typed
  boolean contaminates every downstream metric.

(War story: `is_*` Yes/No columns came in as string dtype; `dtype`-based handling skipped
them; the fix cost ~2h and salvaged every later comparison. See `war-stories.md`.)

## Rank the issues

List issues most-severe first, each with a severity and a recommended action:

- **BLOCKER** — must fix before modeling (leakage, target contamination, a broken
  encoding, an unusable split). Any open BLOCKER makes the card NO-GO.
- **WARN** — proceed with care (high missingness, high-cardinality nominal, class
  imbalance, small n).
- **NOTE** — informational (a skewed numeric worth binning for linear models).

## Clean-room leakage audit

Leakage hides best from the eyes that prepared the data. The audit therefore runs in a
FRESH context: a separate agent or session where possible; if self-performed, only
AFTER the profile is finished — never interleaved with prep work. The auditor reads
ONLY `study.yaml`, `prepare.py`, the prepared artifact, and the profile. Never
`program.md` — its hopes, priors, and phase plans are exactly the context that makes a
leak look plausible.

Fill the four-row checklist on the data card (see `assets/data-card-template.md`):

1. **Target leakage** — no feature is a proxy or derivative of the target, and none
   encodes post-outcome information.
2. **Lookahead** — encoders/imputers/scalers are fit on train only; time-derived
   features precede the cut.
3. **Split contamination** — no duplicate rows straddle partitions; group ids never
   cross partitions; the split reproduces from `study.yaml` alone.
4. **Eval-harness sanity** — the metric direction matches the contract; a constant
   predictor and a label-shuffled predictor both score at chance.

Rows 1–2 are judgment calls made from `prepare.py` plus the profile. Rows 3–4 are
mechanized — run the bundled auditor and copy its `[OK]`/`[FAIL]` lines into the
Evidence column:

```bash
uv run --locked python -m kleinlib.leakage <prepared> --target <col> --study <dir>
```

Any FAIL on any row is a **BLOCKER** — NO-GO by the ranking rule above — until the
cause is fixed deterministically (in `prepare.py` or the split block) and the audit is
re-run clean.

## Rule go / no-go

Write the decision box: **GO**, **NO-GO**, or **GO-WITH-CAUTIONS**, with a rationale. Set
the card frontmatter `status` to match.

## Record the gate or an explicit override

Modeling is HARD-BLOCKED until `data_card.md` says GO (or GO-WITH-CAUTIONS with the
cautions noted), the prepared artifact exists, and DATA is recorded. After explicit
acknowledgement:

```bash
uv run --locked klein gate record data --study studies/NN-slug \
  --acknowledged-by <actor> --note "<cautions accepted>"
```

This fingerprints the prepared artifact and gate card. If accepting a documented risk,
use the machine-enforced override instead:

```bash
uv run --locked klein gate override data --study studies/NN-slug \
  --acknowledged-by <actor> --reason "<specific reason>"
```

Also explain the decision in `program.md`; prose alone never unlocks a v2 run. Legacy
v1 fast-path notes remain historical evidence but do not satisfy the v2 preflight.
