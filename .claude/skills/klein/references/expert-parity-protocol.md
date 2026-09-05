# EXPERT PARITY — one registered vector comparison, decided once

"The AI matched the expert" is the cheapest sentence in AI for science and the
most expensive one to earn. Made loosely it costs nothing: quote the metric that
moved, mention the one that did not, call a non-significant loss "no difference",
and give the newer pipeline the budget the older one never had. The `parity`
capability closes each of those routes with an artifact locked before the
evidence exists, and it does so on ONE sealed evaluation that scores both
pipelines together.

Opt-in, schema-3 only, inert unless `generation/manifest.yaml` declares `parity`
(`references/generation-protocol.md`). `parity` requires `expertise`: the
"expert" side of the comparison is the recipe the domain card froze and the
notary reproduced (`references/expert-protocol.md`), not a re-implementation
whose weakness nobody measured.

> **Passing establishes that on this population, at this sampling unit, under
> this budget rule, these metrics did not fall below their preregistered margins
> in one sealed evaluation.** It does not establish that the AI pipeline is as
> good as the expert in general, that the metrics are the right metrics, or that
> the AI CAUSED the difference. **Causal AI value requires a matched frozen-2.0
> ablation arm; the contribution ledger establishes recorded attribution and
> outcomes** — a different and smaller thing.

Role: the driving agent at CONSULT (lock), after METHOD (bind), at the sealed
cell (measure), and once afterwards (assess). Any agent or human can follow this
document directly.

## Verbs

```bash
uv run --locked klein generation parity lock   --study studies/NN-slug [--allow-late]
uv run --locked klein generation parity amend  --study studies/NN-slug
uv run --locked klein generation parity bind   --study studies/NN-slug \
    [--floor-run E0002] --ai-snapshot pipelines/ai.py --expert-snapshot pipelines/expert.py
uv run --locked klein generation parity assess --study studies/NN-slug --run E0007
uv run --locked klein generation parity show   --study studies/NN-slug

uv run --locked klein generation contribution record --study studies/NN-slug \
    --kind proposal --subject NN-slug#H3 --origin ai --actor <name> \
    [--decision accepted --human-acceptor <name>] [--implementation-ref E0005] \
    [--refs P2,E0005] [--outcome "…"] [--cost "…"] [--transcript-hash <sha>]
uv run --locked klein generation contribution show --study studies/NN-slug
```

Every one takes the four testimony flags `--actor --tool --model --session`
(recorded, never authenticated); on `contribution record`, `--actor` is both the
envelope's actor and the ledger line's. Exit codes follow the layer's
convention: `0` did it, `1` the study is not in a state where the question can be
asked, `2` the question was asked and answered no. **`parity assess` exits `2` on
`refuted` and `inconclusive`** — the assessment is recorded either way, because
negative evidence is evidence.

## 1. `parity.yaml`, locked before CONSULT

Copy `assets/parity-template.yaml` to the study as `parity.yaml`, fill it, and
lock it **before `klein gate record consult`**. Criteria registered after the
study is under way constrain nothing they did not already know; `--allow-late`
records the lock anyway and `parity lock` FAILs for the life of the study.

| Key | Rule at lock |
|---|---|
| `type`, `study` | `parity`, and the study's own id |
| `comparison_track` | a track declared in `study.yaml` with `mode: registered`. The comparison is a CELL, not a frontier candidate (`references/registered-mode.md`) |
| `sampling_unit` | the paired unit, in words (policy-year, patient, site-season) |
| `block_column` | the dependence block the bootstrap resamples, or `null` for iid units. Required either way — the dependence structure is preregistered, not chosen when the bounds are seen |
| `pipelines.ai`, `pipelines.expert` | each `{name, description, owner, selection_rule}`, all non-empty. `selection_rule` says how the object being scored was chosen, written before anything was scored |
| `budget_rule` | the matched resources both pipelines get. An expert beaten under a budget it never had was not beaten |
| `metrics[]` | ≥ 1, each `{key, name, direction, units, estimand, floor_ref, margin, margin_rationale, undefined_handling}` — see below |
| `uncertainty` | `{method: block_bootstrap_maxt, n_boot: >= 200, seed: <int>, alpha: (0,1)}` |
| `aggregation` | `conjunction` — the only value in this version |
| `scorer.path` | a study-relative path (conventionally `lib/parity_score.py`). It need not exist yet; `bind` pins its hash |
| `margins_set_by` | `{name, session_receipt}`. `name` may **not** be the `experimenter` row of `program.md`'s roster — the actor being compared cannot set the bar it is measured against. String comparison, never authentication |
| `scoring` | `{masked: true|false, scorer_name}` — testimony about how the scoring was done (R-PAR-6), recorded and never verified |
| `predictions` | one registered `P#` per metric key — see §2 |
| `ablation_study` | a matched frozen-2.0 study id, or `null`. Required as a key: a study with no ablation says so |

Per metric:

| Field | Rule |
|---|---|
| `key` | a short alphanumeric id. The printed keys are `ai_<key>`, `expert_<key>`, `d_<key>`, `L_<key>`, `U_<key>`, `defined_<key>` |
| `direction` | `higher` or `lower`. It fixes `sign_j`, so a positive `d_j` ALWAYS favours the AI |
| `units`, `estimand` | what the number is, and of what population. Gini, KS and a top-to-bottom ratio have different denominators and different floors; say which |
| `floor_ref` | `run:E####` — a Phase-0 `--action calibration` run that PRINTED `floor_<key>` — or `sweep:<name>`. See §3 for why `sweep:` is refused at bind today |
| `margin` | `ε_j ≥ 0`, the noninferiority margin |
| `margin_rationale` | required prose. **A margin justified only by the measured floor is resolution sold as acceptability** (R-INV-4, `knowledge/research-discipline.md` lesson 1). Say what decision tolerates this much give-back |
| `undefined_handling` | `cannot_pass` — the only value in this version |

`parity amend` records a new version with `parent_ids`. Only **version 1** has to
precede CONSULT; amendments are *labelled* late (a WARN), never failed. Frozen at
version 1 and refused in an amendment: `comparison_track`, `sampling_unit`,
`block_column`, `aggregation`, `uncertainty`, the metric key set, and per metric
its `direction`, `margin`, `estimand` and `undefined_handling`. An amendment
after the bind is refused outright.

## 2. The margin and the prediction rule are the same inequality

Each metric names the registered prediction that adjudicates it, and that
prediction's rule must be **exactly**

```yaml
- id: P1
  track: <comparison_track>
  statement: "the AI pipeline is noninferior on gini"
  rule: {key: L_gini, op: ">=", value: -0.01}   # value == -margin, numerically
```

If the rule and the margin could disagree, the notary's verdict and the parity
assessment would be two different comparisons wearing one name. The lock refuses
the mismatch, and `generation verify` re-checks it against `study.yaml` at every
audit — so a prediction edited afterwards fails.

## 3. Floors are measured, before anything is compared

`δ_j` is the paired floor of metric `j`: how much `d_j` moves when nothing
changed. Measure it in Phase 0 with the paired recipe
(`kleinlib.metrology.paired_bootstrap`, estimand `paired-comparison`) on
**development data**, and have the floor run print one key per metric:

```python
evaluate_table(..., extra={"floor_gini": 0.011, "floor_calib": 0.004, "floor_ratio": 0.08})
```

Then `floor_ref: run:E0002` reads `floor_gini` out of that run's manifest, or
`--floor-run E0002` points every metric at the same run.

`sweep:<name>` is accepted in the lock and **refused at bind in this version**:
`klein sweep register` pins a sidecar and a script by hash, not a number, so
there is nothing numeric to read. The refusal says so rather than inventing a
`δ`. Register the floor as a calibration RUN that prints the key.

A margin is justified **separately** from the floor. Noise does not authorize a
generous equivalence margin (B §3); resolution is not materiality.

## 4. Bind before any sealed access, on any track

```bash
uv run --locked klein generation parity bind --study studies/NN-slug \
    --ai-snapshot models/ai_pipeline.json --expert-snapshot lib/expert_glm.py
```

`bind` requires the METHOD gate (the scorer is frozen at METHOD), a `reproduced`
`expert bind`, at least one snapshot per side, and a numeric floor for every
metric. It pins the scorer's sha256, both pipelines' file hashes, and the floors
into a `parity_bound` object — and that object's anchor is the line every sealed
run must fall after.

**The rule (deferral D-2).** The core still grants each track its own single
look; what the extension can refuse is the ADMISSION, and it does:
`klein generation check --action sealed` on **any** track is refused while
`parity` is declared and no bind exists. A study that spends a frontier seal
before the pipelines and floors are frozen cannot earn the parity outcome, and
`parity bind` FAILs afterwards naming the run and the two sequence numbers.

**The scorer is never in the mutable surface** (R-INV-3). It is study library
code, hashed at the bind and re-read at the sealed cell's candidate commit; a
scorer retuned between the two is a checker tuned to the answer, and it FAILs.

## 5. The sealed comparison cell

One registered cell, the comparison track's **sole** sealed evaluation:

```bash
uv run --locked klein run-one --study studies/NN-slug --track comparison \
    --final-test --dry-run                      # mandatory rehearsal
uv run --locked klein generation check --study studies/NN-slug \
    --action sealed --track comparison --tests P1 P2 P3
uv run --locked klein run-one --study studies/NN-slug --track comparison \
    --final-test --tests P1,P2,P3 --description "AI vs expert, joint comparison"
```

The entrypoint calls the study's `lib/parity_score.py`
(`assets/parity_score_template.py` is the skeleton). It must:

1. Score BOTH pipelines on the SAME units, in the SAME order.
2. Write `tables/parity_units.tsv` — one row per sampling unit, columns
   `unit`, `block`, then `ai_<key>` and `expert_<key>` for every locked metric.
   Those columns are the metric's **per-unit contributions**, so the metric IS
   their mean; a metric that is not a unit mean is expressed through per-unit
   contributions by the scorer, and the estimand says so.
3. Compute the bounds with `kleinlib.generation.stats.simultaneous_bounds`.
4. Print, through `kleinlib.eval.evaluate_table` — the evaluator that pins an
   `artifact:` line, which is what makes the table citable evidence
   (`references/registered-mode.md`) — the block:
   `ai_<key>`, `expert_<key>`, `d_<key>`, `L_<key>`, `U_<key>` and
   `defined_<key>` for every metric, plus `n_units` and `n_blocks`, and the
   `artifact:` line for `tables/parity_units.tsv`.

An **undefined** metric prints `NA` for its numbers (a non-finite line aborts the
notary's parser) and declares `defined_<key>: 0`. That declaration may not be
omitted: silence about a metric is not the same as saying it could not be
computed, and `parity cell` FAILs on a metric that is in the lock and neither
printed nor declared undefined.

## 6. The decision rule

With `D_j = sign_j × (AI_j − expert_j)` and simultaneous bounds `[L_j, U_j]`:

| Outcome | Condition |
|---|---|
| **exceeds** | every `L_j ≥ 0`, and some `L_j ≥ δ_j` |
| **at least parity** | every `L_j ≥ −ε_j` — explicitly noninferiority, never equality |
| **refuted** | some `U_j < −ε_j` |
| **inconclusive** | otherwise |

They are mutually exclusive by construction: `U_j < −ε_j` contradicts
`L_j ≥ −ε_j` on that same `j`. An **undefined** metric — A4 §7's top-to-bottom
ratio on a zero-loss bottom decile — can never pass: the verdict is `refuted`
when some other metric refutes and `inconclusive` otherwise, and the undefined
metric is named in the record rather than dropped from the conjunction.

The conjunction is the point. Three metrics must describe **one model on one
population**; three independently selected winners establish nothing jointly. A
ranking gain bought with a calibration loss beyond its margin is not parity, and
the whole capability exists so that sentence is arithmetic rather than taste.

**`agreement_within_floor` is not parity.** A4 §7's alternative — every
`|d_j| ≤ δ_j` — is computed and reported under that name, in the assessment
object and in the capability outcome. It is a statement about **resolution**:
"the two pipelines differ by less than this measurement can see". Selling it as
parity is the non-significance-as-equivalence move the plan rejects (N-4). An
undefined metric never agrees either.

## 7. Assessment and verification

```bash
uv run --locked klein generation parity assess --study studies/NN-slug --run E0007
```

`assess` re-reads `tables/parity_units.tsv` (checking its sha256 against the one
the run pinned), recomputes `ai`, `expert`, `d`, `L` and `U` per metric with the
declared uncertainty rule, applies §6, and records a `parity_assessed` object
carrying every number, the verdict, `agreement_within_floor`, the undefined
metrics and the reasons. **It never reads the printed bounds** — the scorer's
arithmetic is checked against the table, not trusted by it.

`klein generation verify` runs the `parity` and `contribution` families beside
the spine's eight.

| Check | FAILs when |
|---|---|
| `parity lock` | not locked; **version 1** late; `parity.yaml`'s sha256 differs from the newest lock; a metric's prediction rule no longer tests `L_<key> >= -margin`. (A late amendment is a WARN) |
| `parity bind` | a `final_test` run exists with no bind; any `final_test` run on **any** track started before the bind's core anchor; more than one bind; a metric with no numeric floor; the scorer or a pinned snapshot differs from its recorded hash at the sealed cell's candidate commit |
| `parity cell` | the comparison track has more than one `final_test` run; that run's admission checkpoint is not `sealed`; a locked metric was neither printed nor declared undefined |
| `parity assessment` | the recorded assessment does not recompute from the pinned table. (A WARN when the printed bounds differ from the table's own — the assessment used the TABLE; and a WARN when the expertise obligation is still open, which scopes the outcome to an unreproduced baseline) |
| `contribution ledger` | the file and the chain disagree in length, in order, or in any line's hash |
| `contribution coverage` | a slate row id or an admitted/refused hypothesis id has no ledger line |

The capability entries in `generation/verify_receipt.json` are

```json
"parity":       {"integrity": "PASS", "outcome": "refuted", "agreement_within_floor": false,
                 "review": "source-reconstructed", "undefined_metrics": ["ratio"]}
"contribution": {"integrity": "PASS", "outcome": "descriptive", "coverage": 1.0,
                 "agent_accepted": 2}
```

and `generation/label.json` copies each **outcome** into its `capabilities`
column. Integrity is not outcome: a `refuted` parity with an intact record is
`generation-verified`; a `parity` outcome with one unadmitted run is not.

## 8. The contribution ledger

`ai_value.jsonl` is an append-only ledger at the study root: one line per
proposal, decision, rejection or error, each naming its `subject` (a
`<study>#Hn`, an `E####`, an artifact), its `origin` (`ai` or `human`), the
actor, the decision, and — on an accepted row — the **human** who accepted it.
`contribution record` appends the line and seals its sha256 into the generation
chain in the same transaction, so the file and the chain are two witnesses to one
record; either one alone is a FAIL.

Three rules carry the weight:

- **Coverage includes rejections.** Every slate row and every hypothesis an
  admission named — admitted or refused — needs at least one line. A ledger of
  only the accepted proposals is a highlight reel, and the denominator is the
  work, not the wins (R-PAR-5).
- **Agent acceptance never becomes human acceptance.** `decision: accepted` with
  `human_acceptor: null` is counted and reported as agent-accepted. It stays in
  the record and is never promoted.
- **Attribution is not causation.** The outcome is `descriptive` unless
  `parity.yaml` cites an `ablation_study`, in which case it is `ablation-cited`
  — and even then the outcome names the citation, it does not assert the effect.

Rejection alone is not evidence of wrongness, and partial transcripts earn
partial attribution. **Recorded activity is not all activity**: work in scratch
copies, other checkouts and chat sessions is invisible to this ledger.

## 9. Reporting it

- Findings §① states the outcome with its scope word: "at least parity on the
  registered vector, on the sealed 2019 cohort, at the policy-year unit" — never
  a bare "matched the expert". When the expertise outcome is `incomplete`, say
  "against an unreproduced baseline"; verify WARNs about exactly that.
- `agreement_within_floor` is reported under its own name or not at all.
- The per-unit table is pinned; cite it as `art:parity_units` and let
  `claims.lock` give the numbers their homes (`references/claims-protocol.md`).
  Generation ids stay in prose and sidecars (deferral D-4).
- A parity outcome on a non-winning object is a **capability** outcome and an
  `exploratory` core claim; core `finalize` labels stay keep-linked (D-3).

## What this establishes, and what it does not

- **Establishes:** that criteria, margins and floors registered before the
  evidence were applied by arithmetic to one sealed evaluation of two pipelines
  frozen beforehand; that the scorer that produced the table is the scorer that
  was hashed at METHOD; that no sealed look on any track preceded the freeze; and
  which proposals and rejections were recorded, by whom, and what happened to
  them.
- **Does not establish:** that the metrics are the right metrics; that the expert
  pipeline is a strong expert (an under-tuned control is not detected here — that
  is a referee obligation, `references/referee-protocol.md`); that the budget rule
  was honoured in fact; that the scoring was really masked (testimony); that the
  AI *caused* the difference (that needs the matched ablation arm); or that the
  ledger is complete with respect to work nobody recorded.
