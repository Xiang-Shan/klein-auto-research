---
type: data-card
domain: "language modeling"
modality: "text"   # tabular | timeseries | image | sequence | graph | text | simulation | none
status: go              # draft | go | no-go | go-with-cautions
concepts: [character-language-model, contiguous-block-split, eval-harness-controls]
related: []
---

# Data card — 13-charlm-fixed-budget

> Gate 1 (DATA). GIGO guard. Written BEFORE any modeling.
> Protocol: `.claude/skills/klein/references/data-gate-protocol.md`.

## Source & shape

- **Source tag:** `bundled:tinyshakespeare/tinyshakespeare.txt.gz`, resolved to
  `datasets/tinyshakespeare/tinyshakespeare.txt.gz` inside this repository (the
  `data source: bundled — …` line is in `prepare.log`). **Pin:** `data.sha256` is not
  required for a `bundled:` tag — the bytes live in the repository — but the corpus is
  pinned anyway, twice over: the bundle's README records
  `sha256(gzip) = d8b29e6338cb…82ec9` and `sha256(text) = 86c4e6aa9db7…565ed`, and
  `prepare.py` re-derives the second one and STOPS on a mismatch.
- **Modality:** text. **Corpus:** 1,115,394 characters, pure ASCII, one byte per
  character. **Vocabulary:** 65 distinct characters — `\n`, space, `!$&',-.3:;?`,
  `A`–`Z`, `a`–`z` (the only digit anywhere in the corpus is `3`).
- **Prepared artifact:** `data/prepared/prepared.csv`, **1089 rows × 5 columns** — a
  contiguous BLOCK INDEX, one row per 1024-character block, not a feature table. The
  companion artifacts are `data/prepared/index.csv` (the split index table),
  `data/prepared/tokens.bin` (the whole corpus as raw uint8 token ids) and
  `data/prepared/vocab.json`.
- **Target / estimand:** the study's real target is the NEXT CHARACTER, which no
  column can hold. `study.yaml:target` names `n_chars` because
  `kleinlib.data.contract_split` needs a target column to drop from the feature frame;
  nothing is regressed on it, and no model in this study ever reads it except as the
  block-length vector the verifier uses to reconstruct a partition's character range.
- **Split policy:** `data.split` = `kind: time`, `time_column: start_char`,
  `development_size: 0.10`, `test_size: 0.10`, `seed: 20260903` (recorded for the
  contract's identity; the time strategy orders by offset and draws no lottery).
  Realized:

  | Partition | Blocks | Characters | Share | Character range |
  |---|---|---|---|---|
  | train | 0 – 870 (871) | 891,904 | 79.96% | 0 – 891,903 |
  | development | 871 – 979 (109) | 111,616 | 10.01% | 891,904 – 1,003,519 |
  | sealed final test | 980 – 1088 (109) | 111,874 | 10.03% | 1,003,520 – 1,115,393 |

  All three are contiguous, verified by `prepare.py` (it exits non-zero otherwise).
  The 258-character remainder joins the last block rather than being dropped, so every
  character of the corpus belongs to exactly one partition. Klein's *development*
  fingerprint covers train + development — the first 90.0% of the corpus — which is
  the convention `karpathy/nanoGPT` uses on this same file (1,003,854 / 111,540 there;
  1,003,520 / 111,874 here, the 334-character difference being the block rounding).
- **Fingerprints frozen at this gate:** prepared data
  `7e8969ac834e19c2…9644a9`; split policy and realized partitions recorded by
  `klein gate record data` — development
  `0f602fcef2e45e7bdebf1a20281a4141c806c4abdaf943df9e46307d02c5ec50`, final test
  `bd7849a00c6a8bd856c9136cd211d9ecb7975fbffa9c75b08d78ed51b3e3f155`. Every run prints
  its realized `split_fingerprint:` and the notary compares it.
- **Profiler used:** the global `dataset-profiler` skill's `scripts/profile.py` on the
  index table, and `kleinlib.profile_fallback` on the block table.

## Profile summary

`data/prepared/prepared.csv` — the block table the contract splits:

| Column / field | Dtype (value-pattern) | Missing % | Cardinality | ID-like? | Leakage risk? | Notes |
|---|---|---|---|---|---|---|
| `block_id` | int64, 0…1088, strictly increasing | 0.0% | 1089 | yes | none | the row's identity; also its order |
| `start_char` | int64, 0…1114112, multiples of 1024 | 0.0% | 1089 | yes | none | the `time_column`; the split orders by it |
| `n_chars` | int64, values are exactly {1024, 1282} | 0.0% | 2 | no | none | the contract's `target` column, dropped from the feature frame; carries the block length so the verifier can rebuild a partition's character range |
| `n_distinct_chars` | int64, 33…59 | 0.0% | 22 | no | none | descriptive only |
| `content_group` | str, 16 hex characters | 0.0% | 1089 | yes | **this is the leak detector** | sha256 prefix of the block's casefolded, whitespace-collapsed text — see Group policy |

`data/prepared/index.csv` — the split index table the mechanized audit reads:
1089 rows × 4 columns (`id` 1089 unique, `group` 1089 unique, `time` int64 0…1114112,
`split` 3 values: train 871 / development 109 / test 109), 0 exact duplicate rows.

**Value-pattern check (mandatory war story):** every column was inspected by VALUE, not
by dtype. There are no string-encoded booleans, no numbers-in-strings, no sentinels and
no missing values anywhere: four columns hold genuine int64 and one holds a fixed-width
lowercase hex digest. `n_chars` is int64 with exactly two distinct values, which the
tabular profiler reports as an "imbalanced target" — that reading does not apply here
and no class weighting, calibration or threshold tuning is used anywhere in this study,
because `n_chars` is never predicted.

**Modality statistics (text).** Corpus length 1,115,394 characters; vocabulary 65;
block length 1024 characters except the last (1282); distinct characters per block
33–59; 1089 distinct normalized block contents out of 1089 blocks — the corpus contains
no repeated 1024-character passage at all. Label provenance is trivial and needs no
annotation audit: the "label" of position *t* is the character at position *t+1* of the
same public-domain text, so there is no annotator, no rater agreement and no label
noise beyond the text itself. Two computable reference levels
(`tables/reference_losses.tsv`) fix the scale a validation cross-entropy is read
against: a uniform predictor scores **4.174387 nats/char** (= ln 65) and an add-one
unigram fitted on train alone scores **3.307264 nats/char** on development.

## Group policy

- **The group id** is the sha256 prefix of the block's NORMALIZED text — casefolded and
  with runs of whitespace collapsed (`prepare.py:_normalized`). It is deliberately not
  the block id: an identity group would make the mechanized group-overlap check
  tautological. Hashing normalized content instead gives the check teeth — it fails if
  the same passage appears in two partitions under a cosmetic difference in case or
  spacing, which is exactly the "same entity under a dirty key" leak the protocol names.
- **Why the contiguous block is the right unit.** The unit that would leak if it
  straddled a partition is a training window: 128 characters of context plus the
  character after them. Partitions here are contiguous ranges of blocks, and both the
  trainer and the verifier draw windows strictly inside a partition's own character
  range, so no window can contain characters from two partitions. The block is the
  coarse-grained carrier of that guarantee: 1024 characters is eight times the
  evaluation context, so the boundary effect is confined to at most one window's worth
  of context at each of the two junctions, and those windows are never formed.
- **Group-overlap check on the index table:**
  `[OK] group-overlap: 1089 normalized group ids each stay in one partition`.
- **Duplicates and near-duplicates across partitions** (`tables/near_duplicates.tsv`),
  measured as Jaccard similarity of the sets of character **8-grams**, encoded as
  base-65 integers so the number reproduces (Python's string `hash()` is salted per
  process and would not):

  | Later partition | Compared against | Exact duplicate blocks | Near-duplicates at J ≥ 0.5 | Near-duplicate rate | Max J | Mean J |
  |---|---|---|---|---|---|---|
  | development | train | 0 | 0 | 0.0 | 0.023131 | 0.014965 |
  | test | train + development | 0 | 0 | 0.0 | 0.030059 | 0.015430 |

  The largest similarity any held-out block has to anything the model may train on is
  J = 0.030 — an overlap of common English 8-grams, not of content. There is nothing to
  memorize across the split.

## Ranked go / no-go issues

| # | Severity | Issue | Recommended action |
|---|---|---|---|
| 1 | WARN | The evaluation is windowed with a fixed 128-character context, so the first character of every window is predicted from no context at all — 1/128 of the scored characters are handicapped, which inflates every candidate's loss by a small constant. | Accept: the handicap is identical for every candidate and every partition, so it cancels in every comparison the study makes. It is disclosed here, in the method card, and in findings, and the contract pins `eval_context` at 128 as a guardrail so no candidate can quietly change it. |
| 2 | WARN | The last 128 characters of each partition's range are read as context but never predicted (their successors lie outside the partition), so 111,488 of the development partition's 111,616 characters are scored. | Accept and disclose: 99.89% coverage, identical for every candidate, and never sampled — the alternative (letting a window read across a partition boundary) is leakage. |
| 3 | NOTE | `n_chars` is a placeholder target with two distinct values, and a tabular profiler reads it as a 0.09%-minority "imbalanced target". | No action. Nothing predicts it. The note exists so a reader of the profiler output is not misled. |
| 4 | NOTE | The bundled corpus is packaged by a third party (`karpathy/char-rnn`, MIT-declared in its README) around public-domain text. | No action. `DATA_LICENSE` records both layers; the study redistributes nothing. |
| 5 | NOTE | 2000 steps × 32 windows × 128 characters = 8.19M training characters against a 891,904-character train partition — about 9.2 passes over the data. | No action, but it is the reason dropout is a live question at this budget (P4) and it is stated in the method card's regime table. |

No BLOCKER is open. In particular there is **no literal split seed or partition rule
anywhere in an evaluator or entrypoint** (war story 8): `prepare.py`, `train.py`,
`verify.py` and both sweeps obtain their partitions only from
`kleinlib.data.contract_split` / `load_partition`, and the verifier additionally
refuses any checkpoint whose recorded `split_fingerprint` disagrees with the realized
one.

## Clean-room leakage audit

Self-performed in a clean-room pass: run AFTER `prepare.py` and both profiles were
finished, reading only `study.yaml`, `prepare.py`, the prepared artifacts and the
profile output — never `program.md`. Rows 3 and 4 are mechanized.

| Check | Pass/Fail/N-A | Evidence |
|---|---|---|
| 1. Target leakage — no feature is a proxy/derivative of the target or post-outcome information | PASS | There are no features. The model sees raw character ids and nothing else; the block table's five columns are never given to a model. The only quantity derived from the text that any code reads is `content_group`, which is used solely by the leakage audit and never by `train.py` or `verify.py`. |
| 2. Lookahead — encoders/imputers/scalers fit on train only; time-derived features precede the cut | PASS | The one fitted object outside the model is the character vocabulary, and it is derived from the WHOLE corpus by construction: it is the alphabet of the text, 65 symbols that are public knowledge about English typography, contains no positional or count information, and would be identical if derived from the train partition alone (every one of the 65 characters occurs in the first 80%). The unigram reference level in `tables/reference_losses.tsv` is fitted on train only. No scaler, imputer or encoder exists. Training windows are drawn strictly inside the train range; the verifier's windows strictly inside the evaluation range. |
| 3. Split contamination — no duplicate rows straddling partitions; group ids never cross partitions; the split reproduces from `study.yaml` alone (fingerprint match) | PASS | `python -m kleinlib.leakage --index data/prepared/index.csv --study .` → `[OK] index-table: 1089 rows partitioned by the split column (train=871 development=109 test=109)` · `[OK] duplicate-rows: no id straddles partitions` · `[OK] group-overlap: 1089 normalized group ids each stay in one partition` · `[OK] time-order: partitions are ordered in time — train [0 .. 890880]; development [891904 .. 1002496]; test [1003520 .. 1114112]`. 6/6 checks passed, exit 0. Near-duplicate rate 0.0 at J ≥ 0.5 in both directions (table above). |
| 4. Eval-harness sanity — metric direction matches the contract; constant and shuffled predictors score at chance | PASS | `[OK] metric-direction[primary]: val_loss: contract-declared direction 'lower' accepted`. The chance rows are N/A in index mode (no target, no features), so they were reproduced on the study's own evaluation path by `sweep:harness_controls` (`tables/harness_controls.tsv`, 4/4 PASS): **negative control** uniform = 4.174388 nats = ln 65 to float32 resolution; **negative control** an untrained network, saved as a real checkpoint and scored by running `verify.py` itself, = 4.305432 nats — no better than chance, as a model with no information must be; **positive control** an add-one unigram fitted on train only = 3.306991 nats, strictly better than chance and far from zero; **negative control** a copy-the-input predictor = 4.750043 nats, strictly WORSE than chance — the control that catches the classic off-by-one bug of aligning targets with inputs, which would have scored it ln 2 = 0.693. The diagnostic `target_equals_input_rate` = 0.024523, not 1.0. |

## Go / no-go

> **Decision:** GO
>
> **Rationale:** The corpus reproduces its published identity exactly (1,115,394
> characters, 65 distinct, matching sha256), the partitions are contiguous ranges of an
> ordered text with no window able to straddle them, no block is an exact or near
> duplicate of anything in an earlier partition (max Jaccard 0.030), all six mechanized
> index-mode checks pass, and all four eval-harness controls behave as a correct
> harness must — including the copy-the-input control that would expose an off-by-one
> target alignment. Two WARNs are accepted and disclosed: the fixed 128-character
> evaluation context handicaps the first character of each window, and the last 128
> characters of each partition are context-only. Both are identical for every candidate
> and both are pinned by the `eval_context` guardrail, so they cancel in every
> comparison this study makes.
