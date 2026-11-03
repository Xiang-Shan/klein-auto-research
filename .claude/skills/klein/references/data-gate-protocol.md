# DATA — Gate 1 (GIGO guard)

No modeling until the evidence source is profiled and ruled fit. Output:
`data_card.md` with a ranked go/no-go issue list. The gate encodes two war stories as
mandatory checks — the string-dtype boolean (story 1) and the hardcoded retired split
seed (story 8) — and in schema 3 it is **typed by modality**: a table, a time series,
images, sequences, graphs, text, a simulator, or nothing but a verifier each get the
card variant that can actually catch their failures.

Role: data auditor. Any agent or human can execute this protocol directly — it is
the source of truth; Claude Code ships it pre-wired as the `klein-data-auditor` worker.

## 0. Declare the modality and the source

`study.yaml` names `data.modality` and `data.source` (`references/data-sources.md`:
`csv: | parquet: | synthetic: | bundled: | hub: | sklearn: | openml: | url: | hf:`, with a
`data.sha256` pin wherever the bytes could change, and `data.inputs` for further files). Resolve the source once —
`klein doctor --study <dir>` says whether it resolves on this machine without
fetching — and read the provenance line it prints. The card's frontmatter carries
`modality:`; the gate checks that the card has the headings that modality requires
(`kleinlib.schema.MODALITY_CARD_SECTIONS`). A study that sets `policy.card_sections:
enforce` (every 2.3 recipe does) has those headings — plus `## Near-duplicate audit` for
image, text, sequence and graph data and `## Contamination audit` for the `llm` profile
(`POLICY_CARD_SECTIONS`, `PROFILE_CARD_SECTIONS`) — checked mechanically when the DATA
gate is recorded; a missing heading refuses the record.

**Items that are not rows of a table** (images, documents, sequences, graphs, benchmark
questions) are split through an **index**: `prepare.py` writes the payload (arrays,
text, files) and an index table into a prepared DIRECTORY, and the contract names it —

```yaml
data:
  prepared_path: data/prepared            # a directory: its whole tree is fingerprinted
  split:
    kind: predefined                      # or stratified | random | group | time
    index: index.csv                      # inside prepared_path: id, [label], [group], [time], [split]
    id_column: id
    label_column: label                   # needed to stratify; optional otherwise
    split_column: split                   # predefined only: values train | development | test
```

`kind: predefined` keeps a dataset's official partitions (MedMNIST, a benchmark's own
test set) — `prepare.py` maps the source's names onto `train | development | test`.
The gate then freezes REAL partition fingerprints over item ids, `load_items()` /
`load_partition()` print them, and run-one crashes a run measured on other items —
no fake target column, no "partition not verified". `policy.realized_split: required`
makes a split that cannot be realized refuse the gate instead of leaving a note.

## 1. Prepare, then profile the PREPARED artifact

Run prep first so you profile the thing the entrypoint sees:

```bash
uv run --locked python ../../scripts/run_with_log.py \
  --timeout-seconds <max-run-seconds> --log prepare.log -- \
  uv run --locked python -u prepare.py
```

`prepare.py` obtains its partitions from the contract — `kleinlib.data.contract_split(
study_dir)` / `load_partition(kind)` — never from a literal seed. For a non-tabular
modality it also emits the **split index table** `data/prepared/index.csv`
(`id, group, time, split`), which is what the mechanized leakage rows read.

No argument of `contract_split` can change the split — that is the point. The
partitions and their fingerprint come from `study.yaml` alone, so two machines
that read the same contract measure the same rows:

<!-- test:contract-split:start -->
```python
from pathlib import Path

import pandas as pd

from kleinlib.data import contract_split, partition_fingerprints

study = Path("studies/99-split-demo")
(study / "data" / "prepared").mkdir(parents=True)
pd.DataFrame({"x": range(40), "y": [i % 2 for i in range(40)]}).to_csv(
    study / "data" / "prepared" / "prepared.csv", index=False
)
(study / "study.yaml").write_text(
    "schema_version: 3\n"
    "study_id: 99-split-demo\n"
    "target: y\n"
    "task_type: classification\n"
    "data:\n"
    "  prepared_path: data/prepared/prepared.csv\n"
    "  split:\n"
    "    kind: stratified\n"
    "    seed: 20260903\n"
    "    development_size: 0.20\n"
    "    test_size: 0.20\n",
    encoding="utf-8",
)

X_train, X_dev, X_test, y_train, y_dev, y_test = contract_split(study)
assert (len(X_train), len(X_dev), len(X_test)) == (24, 8, 8)
assert not set(X_train.index) & set(X_dev.index) & set(X_test.index)

# The fingerprint the DATA gate freezes, and every later run prints back.
first = partition_fingerprints(study)
assert set(first) == {"development", "final_test"}
assert partition_fingerprints(study) == first  # stable: it is a function of the contract
```
<!-- test:contract-split:end -->

Then profile. Prefer the global skill; fall back to the bundled profiler:

- **If the `dataset-profiler` skill is available** (check: does
  `~/.claude/skills/dataset-profiler/SKILL.md` exist?): use it on the prepared table.
  A main session invokes the skill directly; a worker agent without the Skill tool
  reads that SKILL.md and drives its `scripts/profile.py` via Bash.
- **Else:** `kleinlib.profile_fallback` — the same profile from stdlib + pandas
  (CLI: `uv run --locked python -m kleinlib.profile_fallback <prepared.csv> --target <col>`).
- **Non-tabular modalities** profile the index table plus the modality statistics
  (item count, size or length distribution, resolution, label provenance, duplicate
  and near-duplicate rate at a stated similarity).

Copy `assets/data-card-template.md` to the study as `data_card.md`, keep the sections
your modality requires, and fill the profile summary table from the profiler output.

## 2. The mandatory value-pattern check (tabular and every table you touch)

This is non-negotiable and has saved whole campaigns. For EVERY column:

- Do NOT trust `dtype == "object"` or `dtype == "string"`. Inspect the ACTUAL values.
- Flag string-encoded booleans (`"Yes"`/`"No"`), numbers-in-strings
  (`"120bhp@3000rpm"`), sentinels (`-999`, `""`, `"NA"`, `"unknown"`), mixed types.
- Record what each column REALLY holds. A silently-skipped categorical or a string-typed
  boolean contaminates every downstream metric.

(War story 1: `is_*` Yes/No columns came in as string dtype; `dtype`-based handling
skipped them; the fix cost ~2h and salvaged every later comparison.)

## 3. The modality sections

- **tabular** — the profile summary and the four-row leakage audit below; nothing
  more.
- **timeseries** — `## Time policy`: the cut dates for train / development / sealed
  (the contract's `time` strategy seals the newest rows), the horizon, which features
  use only pre-cut information, how look-ahead is prevented in `prepare.py`, and the
  leakage-through-time check that was run (a feature computed with any post-cut row is
  a BLOCKER).
- **image, sequence, graph, text** — `## Group policy`: how the group id is computed
  (patient, cluster at what similarity, molecular scaffold, document, source), why that
  unit is the right one for the question (the unit that would leak if it straddled
  partitions), and the group-overlap check on the index table. Duplicates and
  near-duplicates across partitions are the leak that makes every image and sequence
  benchmark look better than it is; state the rate and the threshold.
- **image (deeper, 2.3)** — beyond the group policy, the card answers: the **unit of
  leakage** (patient, slide, subject, scene, video, capture session — never the file);
  **near-duplicates** across partitions from `--near-dup image` (dHash, the threshold in
  bits, the rate per held-out partition, and what was done about each hit);
  **augmentation twins** (no augmented copy of a held-out image was generated before
  the split); **resolution and channel statistics** per partition (a split whose test
  images were resized differently is a covariate shift, not a benchmark); **class
  balance** per partition; **label provenance** (who labelled, inter-rater agreement if
  known, known label noise); and the dataset **licence** and any pretrained weights'
  training data (a backbone pretrained on the test set is contamination).
- **text, LLM evaluation (2.3)** — `## Contamination audit` (profile `llm`) answers,
  before any model is queried: the benchmark's **publication date versus the model's
  stated training cutoff** (later-than-cutoff is not proof of cleanliness, earlier is
  not proof of contamination — both are stated); **n-gram overlap** of the evaluated
  items with every text the prompt will carry (few-shot exemplars, instructions,
  templates) from `--near-dup text --against <pool>` (13-grams by default); the
  **fresh-item control** — a procedurally generated or held-back block the model cannot
  have seen, used as the sealed comparison (a gain that exists on the public items but
  not on fresh twins is the contamination signature); any **perturbation probe**
  (renamed entities, changed numbers) with the generator's own exact-answer check; the
  answer key's provenance and the exact-match normalization; and the **licence** of the
  items and of the model outputs the study will commit (model responses are committed
  in the call ledger — check the provider's terms first).
- **simulation** — `## DGP card`: the declared truth in full (generating process,
  every parameter, seed blocks for development and sealed, sample sizes), what
  "recover" means numerically — the criterion each prediction's rule will use — and
  the in-silico scope sentence every `known-dgp-teaching` claim will carry. The
  leakage rows are N/A with that reason; the DGP card is the audit.
- **none** — `## Verifier card`: the oracle and what it checks, `metric.exactness`
  (exact or stochastic), cost per call, the tolerance and how it was chosen, known
  failure modes (floating point, symmetry, degenerate inputs), a **positive control**
  (a hand-planted invalid object the verifier must reject) and a **negative control**
  (a known-valid object it must accept), and the external best-known value with its
  source. The verifier script is named and is outside the entrypoint's `mutable[]`.

**External evidence, on a study that locked an evidence design.** Any modality section
that describes evidence Klein did not produce — an imported extract, a vendor table, a
wet-lab run, a colleague's file — copies the acquisition and custody fields for it from
the study's locked `evidence_design.yaml` (`evidence.acquisition[]`: `source`, `kind`,
`acquired_at`, and for `kind: acquisition` the `custody` chain and who `attested_by` it).
The card restates them; it never re-decides them, because the design was locked before
this gate. Two reminders travel with them: import chronology does not prove acquisition
chronology, and custody is testimony rather than a verification. Narratives about how
the evidence was generated stay OUTSIDE the clean-room leakage audit — the audit reads
the prepared table and the split index, and a provenance story is neither.

**Planted-truth benchmarks: the DGP card belongs to the custodian.** A benchmark
splits one simulation across two studies, so the `## DGP card` above splits with it
(`references/planted-truth-protocol.md`). The CUSTODIAN's `simulate` study carries the
card **in full** — generating process, every parameter, the seed blocks for
development and sealed, the sample sizes, what "recover" means numerically — and that
is where the simulation disclosure requirement is satisfied. Each PARTICIPANT's
`discover` study carries a card that says, in one line, **"observations only; truth
custodied by `<holder>`"**, names the public bundle and its hash, and declares nothing
about the generating process, because it knows nothing about it. A participant card
that describes the truth has either leaked it or invented it, and both are BLOCKERs.
The custodian's own card is written before the commitment and hashed with it; neither
card's generation narrative enters the clean-room leakage audit.

The receipt behind that one line — `klein generation custody attest` — is
**capability-agnostic**: it needs the generation opt-in and nothing else. A study whose
later time block is held by a colleague, whose wet-lab samples are held by a lab, or
whose sealed extract is held by a vendor records exactly the same testimony, and a card
that says "custodian-held later block" should name the attestation beside the holder.
Testimony, never a verification: a hash proves the bytes did not change, never that
nobody read them.

## 4. Rank the issues

List issues most-severe first, each with a severity and a recommended action:

- **BLOCKER** — must fix before modeling (leakage, target contamination, a broken
  encoding, an unusable split, **a literal split seed or partition rule anywhere in an
  evaluator or entrypoint** — war story 8). Any open BLOCKER makes the card NO-GO.
- **WARN** — proceed with care (high missingness, high-cardinality nominal, class
  imbalance, small n, an unpinned network source).
- **NOTE** — informational (a skewed numeric worth binning for linear models).

## 5. Clean-room leakage audit

Leakage hides best from the eyes that prepared the data. The audit therefore runs in a
FRESH context: a separate agent or session where possible; if self-performed, only
AFTER the profile is finished — never interleaved with prep work. The auditor reads
ONLY `study.yaml`, `prepare.py`, the prepared artifact (or the index table), and the
profile. Never `program.md` — its hopes, priors, and phase plans are exactly the
context that makes a leak look plausible.

Fill the four-row checklist on the data card:

1. **Target leakage** — no feature is a proxy or derivative of the target, and none
   encodes post-outcome information.
2. **Lookahead** — encoders/imputers/scalers are fit on train only; time-derived
   features precede the cut.
3. **Split contamination** — no duplicate rows straddle partitions; group ids never
   cross partitions; the split reproduces from `study.yaml` alone (the realized
   fingerprint matches the one this gate freezes).
4. **Eval-harness sanity** — the metric direction matches the contract; a constant
   predictor and a label-shuffled predictor both score at chance.

Rows 1–2 are judgment calls made from `prepare.py` plus the profile. Rows 3–4 are
mechanized — run the bundled auditor and copy its `[OK]`/`[FAIL]` lines into the
Evidence column:

```bash
uv run --locked python -m kleinlib.leakage <prepared> --target <col> --study <dir>          # dataframe mode (tabular)
uv run --locked python -m kleinlib.leakage --index data/prepared/index.csv --study <dir>    # index-table mode (any modality)
# 2.3 — the near-duplicate rows (copy them under `## Near-duplicate audit`):
uv run --locked python -m kleinlib.leakage --index data/prepared/index.csv --study <dir> \
    --near-dup image --payload data/prepared/images.npy [--threshold 4] [--max-rate 0.0]
uv run --locked python -m kleinlib.leakage --index data/prepared/index.csv --study <dir> \
    --near-dup text --text-column question [--against fewshot_pool.txt] [--threshold 13]
```

An index without a `split` column (every 2.3 index study) is audited on the partitions
the CONTRACT realizes — the audit checks the split every run is held to, not a column a
script wrote. `--max-rate` is the near-duplicate rate the study accepts (default 0); a
non-zero value is a decision the card states with its reason.

Any FAIL on any row is a **BLOCKER** — NO-GO by the ranking rule above — until the
cause is fixed deterministically (in `prepare.py` or the split block) and the audit is
re-run clean. For `simulation` and `none` the rows read N/A with the reason on the card.

## 6. Rule go / no-go

Write the decision box: **GO**, **NO-GO**, or **GO-WITH-CAUTIONS**, with a rationale. Set
the card frontmatter `status` to match.

## 7. Record the gate or an explicit override

Modeling is HARD-BLOCKED until `data_card.md` says GO (or GO-WITH-CAUTIONS with the
cautions noted), the prepared artifact exists, and DATA is recorded. After explicit
acknowledgement:

```bash
uv run --locked klein gate record data --study studies/NN-slug \
  --acknowledged-by <actor> --note "<cautions accepted>"
```

This fingerprints the prepared artifact, the gate card, and — in schema 3 — the
realized partitions (`state.fingerprints.split`), which every later run's printed
`split_fingerprint:` must match. Re-recording the gate refreshes those fingerprints
only while no run exists; a split-policy change after E0001 is refused. If accepting a
documented risk, use the machine-enforced override instead:

```bash
uv run --locked klein gate override data --study studies/NN-slug \
  --acknowledged-by <actor> --reason "<specific reason>"
```

Also explain the decision in `program.md`; prose alone never unlocks a v2 run. Legacy
v1 fast-path notes remain historical evidence but do not satisfy the preflight.
