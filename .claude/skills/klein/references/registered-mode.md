# Registered mode — a track that measures instead of climbing

Frontier mode answers "which candidate wins?". Most science asks something else: "what
is the value?", "does H hold?", "does the method recover the truth?", "does the paper's
number reproduce?". Those questions have no incumbent to beat. In Klein 1.x they were
bent into the frontier by hand — study 09 kept its 42-cell permission map in a sweep
sidecar beside the ledger and invented `claims.lock` to re-anchor it. Schema 3 gives
them a track mode of their own.

Role: the driving agent. Any agent or human can follow this document directly.

## Declaration

```yaml
tracks:
  estimate:
    mode: registered            # frontier is the default
    kind: estimate              # optional per-track override of the study kind
    metric: {name: k_kms_per_mpc, goal: lower}   # the summary scalar every cell prints
predictions:
  - {id: P4, track: estimate, statement: "bootstrap 95% CI lower bound exceeds 70",
     rule: {key: ci_low, op: ">", value: 70}}
```

## Frontier versus registered — the contract diff

| | frontier | registered |
|---|---|---|
| a run is | a candidate | a **cell** of a pre-registered measurement program |
| disposition | keep / discard / crash | **measured** / crash |
| incumbent, headroom, `stop:` | yes | none |
| mutable surface after the run | restored on non-keep | always restored — the candidate commit IS the record |
| identical rerun | refused unless `--allow-rerun` | allowed when `--tests P#` names a prediction (a replication is evidence) |
| `minimum_delta` | the keep bar | the resolution at which a prediction's rule is decided |
| guardrails | flip the disposition | recorded on the manifest (`guardrails_ok: false`), reported in findings, never hidden |
| sealed access | one look at the held-out partition | per kind — see `inquiry-model.md` |
| the printed block | canonical block | canonical block + `artifact:` lines + `split_fingerprint:` |

`results.tsv` gains the status `measured`; nothing else about the ledger changes.

## The printed block of a cell

```
primary_metric: 454.16
ci_low: 336.4
ci_high: 571.9
n: 24
wall_seconds: 0.31
split_fingerprint: 3f9c…
artifact: tables/bootstrap_k.tsv
artifact: figures/bootstrap_k.png
```

- `artifact:` paths are study-relative, POSIX, and must exist when the child exits;
  the engine hashes each into `manifest.artifacts` with `role: declared`. A missing
  path or a path that escapes the study directory is a **crash** (a cell that cannot
  produce its table has not measured anything).
- `evaluate_estimate(value, ci_low, ci_high, n)`, `evaluate_test(stat, p_value,
  effect, n, n_comparisons)` and `evaluate_table(path, summary)` in `kleinlib.eval`
  print the block for the three common cell shapes; `evaluate_scalar` still works for
  anything else.
- A table can be the measurement. One cell whose artifact is a 42-row table is
  lawful and often better than 42 cells: the table is hashed, the summary scalar is in
  the ledger, and the predictions' rules read printed keys. Choose the granularity at
  which a prediction is adjudicated.

## Cells, slates, and predictions

The phase ritual still runs — but a slate proposes **cells**, not diffs: which
measurement, on which partition, adjudicating which prediction, at what cost. A cell
runs through the same notary:

```bash
uv run --locked klein run-one --study studies/NN-slug --track estimate \
  --tests P4 --description "bootstrap CI of K (1000 resamples, seed block A)"
```

`--tests` evaluates each named prediction's rule on the printed block inside the
transaction and records the verdict (`supported | refuted | inconclusive`) in the
manifest, in `study_state.json`, and as the event `prediction_adjudicated`. A missing
key yields `inconclusive`, never a guess.

## What registered mode is not

- Not a sweep escape hatch: a search still runs through `sweep-rules.md`, and a
  measurement sweep is registered with `klein sweep register <name>` so its sidecar is
  hashed and citable as `sweep:<name>`.
- Not a way to skip predictions: a registered track with no predictions is a table
  with no question; CONSULT refuses it.
- Not exempt from the floor: a registered cell that compares two things needs the
  paired floor like any comparison, and its rule's tolerance says so.

## Worked example — study 09's permission map, restated

Study 09 asked whether any of 42 candidate cells (7 families × 6 feature sets) had
permission to contest the anchor. In schema 2 the map lived in
`sweeps/rq0_map.sidecar.tsv`, cited from prose. In schema 3 it is one registered cell:
the entrypoint builds the 42-row table, prints `primary_metric:` as the count of cells
with permission, pins the table with `artifact: sweeps/rq0_map.tsv`, and `--tests P1`
adjudicates "at most 3 of 7 families clear the floor" by the rule
`{key: primary_metric, op: "<=", value: 3}`. The claim in the lock then cites `E0002`
and `art:rq0_map`, and the numbers law finds every count in the table.
