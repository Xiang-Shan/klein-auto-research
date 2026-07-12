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
