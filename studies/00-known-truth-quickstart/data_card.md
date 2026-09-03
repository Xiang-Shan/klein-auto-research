---
type: data-card
domain: "synthetic"
modality: "tabular"
status: go
concepts: []
related: []
---

# Data card — 00-known-truth-quickstart

> Gate 1 (DATA). GIGO guard, written BEFORE any modeling.
> Protocol: `.claude/skills/klein/references/data-gate-protocol.md`.

## Source & shape

- **Source tag:** `synthetic:prepare.py`, resolved offline as printed on the
  `data source: synthetic — prepare.py` line. **Pin:** not required — the script
  IS the source, and its sha256 joins the data fingerprint this gate freezes.
- **Modality:** tabular. **Rows × cols:** 20 000 × 9 (eight features + the
  target). **Target:** `y`, a binary label. **Positive rate:** 0.24115 over the
  whole table (0.241 on development, 0.24125 on the sealed partition).
- **Split policy:** `data.split` — stratified, seed `20260903` read from the
  contract, `development_size` 0.20 and `test_size` 0.20, giving
  12 000 / 4 000 / 4 000. **Fingerprints frozen at this gate:** the prepared
  bytes and the realized development / final-test partitions.
- **Profiler used:** the global `dataset-profiler` skill's measuring script
  (`~/.claude/skills/dataset-profiler/scripts/profile.py`), corroborated by the
  bundled `kleinlib.profile_fallback`. Both agree on every cell below.

## Profile summary

| Column / field | Dtype (value-pattern) | Missing % | Cardinality | ID-like? | Leakage risk? | Notes |
|---|---|---|---|---|---|---|
| `x1` | float, iid standard normal rounded to 6 dp (mean ≈ 0, sd ≈ 1, range ≈ [−4.75, 3.98]) | 0.0 | 19 938 | no | no | informative; also carries the interaction with `x2` |
| `x2` | float, same law | 0.0 | 19 936 | no | no | informative; the interaction's other leg |
| `x3` | float, same law | 0.0 | 19 921 | no | no | informative; also enters squared |
| `x4` | float, same law | 0.0 | 19 941 | no | no | informative, linear only |
| `x5` | float, same law | 0.0 | 19 938 | no | no | informative, negative coefficient |
| `x6` | float, same law | 0.0 | 19 944 | no | no | informative, linear only |
| `x7` | float, same law | 0.0 | 19 939 | no | no | **pure noise** — absent from the true log-odds by construction; single-feature AUC 0.491 |
| `x8` | float, same law | 0.0 | 19 932 | no | no | **pure noise**; single-feature AUC 0.502 |
| `y` | integer in {0, 1} | 0.0 | 2 | no | target | positive rate 0.24115, matching `truth.json`'s declared `full.positive_rate` exactly |

**Value-pattern check (mandatory war story):** every column was inspected by
value, never by `dtype`. All eight features hold real floats; the target holds a
genuine binary integer. No string-encoded booleans, no numbers-in-strings, no
sentinels (`-999`, `-9999`, `999999`, `""`, `"NA"`, `"unknown"`), no mixed types,
no object/string-dtype column anywhere, no constant or quasi-constant column, and
no ID-like column (every feature's unique ratio is ≈ 0.997 because it is a
continuous draw, not because it identifies a row — the mechanized duplicate check
and the single-feature AUCs both confirm it).

**The truth is not in the feature table.** `prepare.py` computes the DGP's true
log-odds per row and writes them to `data/prepared/truth.json` ONLY. Joining that
column into `prepared.csv` would be perfect target leakage; the audit below
checked explicitly that it is absent.

## DGP appendix — the declared truth

Not a required section for the `tabular` modality, but this study's whole point
is that the ceiling is computable, so the generator is written out here as well
as in `prepare.py`.

- Eight features drawn iid standard normal, rounded to 6 decimals.
- True log-odds:
  `eta = −2.40 + 0.90·x1 + 0.80·x2 + 0.70·x3 + 0.50·x4 − 0.60·x5 + 0.40·x6 + 1.00·x1·x2 + 0.70·x3²`,
  stored rounded to 8 decimals so that everything derived from the truth — here
  and in `train.py` — is derived from the SAME numbers.
- `y ~ Bernoulli(sigmoid(eta))`. `x7` and `x8` appear nowhere in `eta`.
- Generator seed: read from `study.yaml:data.split.seed`; no literal seed exists
  anywhere in the script (war story 8).
- Ceilings implied by that truth, per contract partition (from `truth.json`):

| partition | n | positive rate | Bayes AUC | Bayes Brier |
|---|---|---|---|---|
| full | 20 000 | 0.24115 | 0.883874 | 0.105185 |
| train | 12 000 | 0.241167 | 0.880511 | 0.10695 |
| development | 4 000 | 0.241 | **0.884116** | 0.103604 |
| final_test | 4 000 | 0.24125 | 0.893469 | 0.101473 |

The development row's Bayes AUC is what `study.yaml` declares as
`tracks.primary.metric.bound.ideal` once this gate has hashed the generator. The
two 4 000-row ceilings differ by 0.009353, which is a fact about draws of 4 000
rows and not about any model — the sealed prediction is stated with a tolerance
for exactly that reason.

## Ranked go / no-go issues

| # | Severity | Issue | Recommended action |
|---|---|---|---|
| 1 | WARN | class imbalance: 24.1 % positives (4 823 of 20 000) | acceptable for an AUC-ranked primary metric; if any threshold-based number is ever quoted, calibrate rather than cut at 0.5 |
| 2 | WARN | the development partition is 4 000 rows, so the marginal-resplit floor will be wide relative to the distance the ladder has to climb | measure the floor at Phase 0 and set `minimum_delta` from it; never call a within-floor delta an improvement, and expect the headroom to close early |
| 3 | NOTE | the per-row true log-odds are row-index-aligned with `prepared.csv` in `truth.json` | the ceiling is looked up by row label at evaluation time and never joined into `X` or `y`; any future edit that merges the two files is target leakage |
| 4 | NOTE | `x7` and `x8` carry no signal at all | by construction, not a defect — they are there so the study can watch a high-capacity model spend budget on nothing |
| 5 | NOTE | the evidence is simulated, so nothing here is a fact about any real population | every claim about the ladder's behaviour is scoped `in-silico`; the study's transferable claims are about the PROCEDURE, not about the world |

No BLOCKERs.

## Clean-room leakage audit

Performed in a FRESH context by a separate agent on a different model, which read
ONLY `study.yaml`, `prepare.py`, the prepared artifact, `truth.json` and the
kleinlib source — never `program.md`, `research_plan.md`, `scouting_ledger.md` or
`train.py`. Rows 3–4 are mechanized with
`uv run --locked python -m kleinlib.leakage data/prepared/prepared.csv --target y --study .`
(6/6 checks passed: clean).

| Check | Pass/Fail/N-A | Evidence |
|---|---|---|
| 1. Target leakage — no feature is a proxy/derivative of the target or post-outcome information | Pass | `prepared.csv` holds `x1…x8, y` and nothing else; the true log-odds are written only to `truth.json`. Single-feature AUCs (raw value used as the score) are 0.671, 0.660, 0.641, 0.588, 0.405, 0.558, 0.491, 0.502 — none near 0 or 1, so no column is a proxy. `df.duplicated().sum() == 0` and the feature-only frame likewise. |
| 2. Lookahead — encoders/imputers/scalers fit on train only; time-derived features precede the cut | Pass | `prepare.py` fits nothing at all: raw draws go straight to the CSV, 0 % missing so nothing is imputed, and the split kind is `stratified`, so there is no cut date and no time-derived feature to look ahead through. Every scaler in the study lives inside a per-run pipeline fitted on the fit partition only. |
| 3. Split contamination — no duplicate rows straddling partitions; the split reproduces from `study.yaml` alone | Pass | `[OK] split-reproduces: kind=stratified reproduces deterministically from study.yaml (train=12000 development=4000 test=4000 rows)`; `[OK] duplicate-rows: no duplicate row content straddles partitions`; `[OK] group-overlap: N/A — split kind is not 'group'` |
| 4. Eval-harness sanity — metric direction matches the contract; constant and shuffled predictors score at chance | Pass | `[OK] metric-direction[primary]: val_auc: contract direction 'higher' matches the canonical registry`; `[OK] constant-chance[primary]: val_auc=0.5000 for the constant predictor (chance anchor 0.5)`; `[OK] shuffled-chance[primary]: val_auc=0.5011 for the label-shuffled predictor (chance anchor 0.5)` |

**Literal-seed check (war story 8):** Pass. `prepare.py` reads its RNG seed from
the loaded contract and takes its partitions from `contract_split(".")`; there is
no literal integer seed and no direct `train_test_split(random_state=<int>)` call
in any script the study owns, and the study has no local `lib/` module a second
seed could hide in.

## Go / no-go

> **Decision:** GO
>
> **Rationale:** the prepared table is fully numeric and clean, the split
> reproduces from the contract alone, the declared truth is kept strictly out of
> the feature table, the eval harness scores chance at chance, and no BLOCKER is
> open. The two WARNs — a 24 % positive rate and a 4 000-row development
> partition — are carried into the Phase 0 floor measurement and into the
> headroom arithmetic, not into a claim.
