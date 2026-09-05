# Surprise mining — register the search space, keep the null slices

A materials scientist screens four hundred temperature/composition bins and
reports the one that looked anomalous. Every sentence of the report is true, and
the reader still learns nothing, because the reader never learns the
**denominator**. Anomaly-hunting is how a great deal of science actually starts —
Fleming's contaminated plate, Bell Burnell's scruff — and the honest version of
it differs from the dishonest version in exactly one respect: whether the search
was written down before it ran.

This protocol is that bookkeeping. It is part of the opt-in generation layer
(`references/generation-protocol.md`) and applies to a study whose
`generation/manifest.yaml` declares `surprise`. Because a cell measures something
and the evidence design says what, `surprise` requires `design`, and
`klein generation init` refuses the pair without it.

Nothing here proposes a segmentation, ranks a slice, or explains an anomaly. It
records what the driver registered, recomputes what the run produced, and issues
receipts.

```bash
uv run --locked klein generation surprise register --study studies/NN-slug
uv run --locked klein generation check --study studies/NN-slug \
    --action cell --track discovery --cell cell_residual_by_habitat --tests P4
uv run --locked klein run-one --study studies/NN-slug --track discovery --tests P4 \
    --description "residuals by habitat, all four segments"
uv run --locked klein generation surprise record --study studies/NN-slug --run E0007
```

## The registry — `discovery_cells.yaml`

Study root, authored by hand from `assets/discovery-cells-template.yaml`,
registered **after METHOD and before any cell evidence**. After METHOD because
the adapters a cell freezes are the ones the method card named; before evidence
because a search space written once its outputs are visible is a description of
them.

```yaml
type: discovery-cells
study: NN-slug
adapters:
  - path: lib/habitat.py            # outside entrypoint.mutable; sha256 pinned at register
cells:
  - cell_id: cell_residual_by_habitat     # plain and local; the S ids are allocated later
    track: discovery
    expectation_P: P4                     # a REGISTERED prediction with a rule, on this track
    template: residual_by_segment         # | error_slices | family_disagreement
    statistic: mean_signed_residual       # | mean_loss    | distance   (must match the template)
    input_refs: [{path: data/prepared/observations.csv}]   # sha256 pinned at register
    adapter: lib/habitat.py
    partition: development                # never `sealed`
    unit_policy: one row per observation
    group_policy: null                    # null, or {column: site} when units cluster
    segments: {column: habitat, values: [wet, dry, burned, sparse]}   # COMPLETE, frozen
    units: millimetres
    floor_ref: minimum_delta              # or sweep:<registered name>
    minimum_n: 2
    multiplicity_rule: {method: family_maxt, n_perm: 1024, seed: 0, alpha: 0.05}
    output_columns: [segment, unit, value]   # + the group column, when there is one
    post_observation: false
```

`register` refuses: an adapter inside `entrypoint.mutable`; a missing adapter or
input; a **registered** adapter or `input_ref` carrying no `sha256`; an
`expectation_P` that is unregistered, manual, or on another track; a `sealed`
partition; an empty segment inventory; two segments that render to one printed
key; `minimum_n < 2`; a missing or unknown `multiplicity_rule`; an `n_perm`
above 100 000 (every `verify` re-runs the family, and an audit nobody will wait
for is not an audit); a `group_policy` that is neither `null` nor `{column:
<name>}`; a template and statistic that disagree; a duplicate or malformed
`cell_id`; and any change to a cell that was already registered. It then **pins
the hashes for you** — every adapter and every `input_ref` is hashed from disk,
written back into the file, and frozen — and commits the registry with the
ledger.

Re-registering is an amendment: cells may be ADDED, never restated and never
withdrawn. A cell added once any cell of the study has produced EVIDENCE — an
admitted cell admission a run already consumed, or a pinned table on disk — is
forced `post_observation: true`. Evidence, not the record of it: the label may
not depend on whether the driver got round to `surprise record`. That is lawful
— adaptive slices are how discovery works — and it is labelled, because the one
thing an adaptive slice may never do is acquire preregistration by arriving in
the same file as cells that were registered first. `verify` re-derives
the order for EVERY version from the two witnesses the writer does not control:
the version's core anchor must precede the runs of the cells it introduced, and
its object's commit must be an ancestor of theirs.

## The unit of inference

`group_policy: null` means the rows of the pinned table are independent, and
everything — the segment statistic, the dispersion, the sign flip — acts on
units. `group_policy: {column: site}` says the randomization unit is a SITE: the
table carries a fourth column under that name, the cell is collapsed to one row
per (segment, site) carrying that site's mean, and the family rule flips SITES.
The distinction is not cosmetic. Eight measurements at two sites are two
observations; a sign flip that treats them as eight understates the null spread
and manufactures a violation. The record says which happened
(`unit_of_inference: group | unit`), the family detail repeats it, and a cell
that declared a clustering column whose pinned table does not carry it FAILs.

## The three templates

`kleinlib/generation/templates.py` is **library code a study entrypoint
imports**. It is never in the mutable surface, it is never edited per
experiment, and the checker is never the searcher.

| template | statistic | one unit's value | the expectation |
|---|---|---|---|
| `residual_by_segment` | `mean_signed_residual` | observation − model expectation | `0` — a calibrated expectation has zero mean signed residual |
| `error_slices` | `mean_loss` | the declared per-unit loss | the POOLED mean over every unit — "is this slice served worse than the whole" |
| `family_disagreement` | `distance` | model A − model B, **signed** | `0` — the two families agree |

An adapter (`lib/<adapter>.py`) maps field measurements into the template's
arguments. A mapping the field does not support is declared unsupported and the
cell is not registered — it is never assigned an artificial ML metric because one
was available.

**The pinned table is per unit** (`segment`, `unit`, `value`), not per segment.
A sign-flip max-t acts on units, so a summary-only artifact would leave the
family correction un-recomputable — and an un-recomputable screening correction
is the denominator hiding all over again. Row ORDER is part of the evidence: one
sign vector is applied jointly to the whole family, so which unit of one segment
shares a sign with which unit of another is fixed by position in the file. The
per-segment summary is derived — by `record`, and again by `verify`, from the
same bytes.

The cell's entrypoint (skeleton: `assets/discovery_cell_template.py`) writes
`tables/<cell_id>.tsv`, prints `artifact: tables/<cell_id>.tsv`, and prints the
summaries `templates.printed_summary` returns — `cell_segments`, `cell_units`,
`cell_min_n`, `cell_expected`, `cell_max_abs_deviation`, and one
`cell_deviation_<segment>` each — so the registered `expectation_P` can be
adjudicated by the notary on the printed block, inside the transaction. A cell
whose expectation is decided by prose afterwards has registered nothing.

## Minimum n, and the multiplicity rule

Two rules, applied in that order, to the WHOLE frozen inventory.

**`minimum_n` first.** A segment below it is `inconclusive` — searched, unable to
answer, and still in the family and in the table saying so. It is never reported
as `null`, because "we looked and found nothing" and "we looked and could not
see" are different facts.

**Then the declared family rule.** *A measured effect floor is not a
multiplicity correction.* A floor answers "is this bigger than noise on ONE
comparison"; a screen asks "is this bigger than noise on the largest of many",
and the second question needs its own answer, declared before the cell runs.

| `multiplicity_rule` | what it computes |
|---|---|
| `{method: family_maxt, n_perm: 1024, seed: 0, alpha: 0.05}` | `kleinlib.metrology.family_maxt` over **both signs** of every segment (a two-sided max-t: the null distribution is the maximum over `2m` members, and a segment scores `P(max ≥ |t_obs|)`). Sparse and empty segments stay in the family as never-firing placeholders scoring `1.0` — dropping them once the outcomes are visible would shrink the very denominator the guard corrects for. |
| `{method: bonferroni, alpha: 0.05}` | `min(1, m · P(|Z| ≥ |t|))` over the frozen `m`. The raw score uses a NORMAL approximation to the one-sample t (`erfc`), declared as such: it takes no dependency and it is anti-conservative on small samples, so declare `family_maxt` when the segments are small. |
| `{method: declared, sweep: <registered name>, threshold: 4.0}` | no score: the cell compares `|t|` against a threshold the named registered null sweep (`klein sweep register`) put the family's largest statistic at. |

A segment's `t` is the one-sample t on its unit deviations
(`deviation / (sd / √n)`, `ddof=1` — `kleinlib.metrology`'s own convention). A
zero-spread segment reports an infinite `t`: extreme, not missing.

## The receipts — `<study>#Sn`

`surprise record --run E####` reads the pinned table (its sha256 checked against
the run's manifest), recomputes every segment of the frozen inventory, applies
the two rules, and writes:

- ONE `surprise_recorded` inventory object — run, cell, table hash, every
  segment with `n`, statistic, expected, deviation, `sd`, `t`, `adjusted_p` and
  verdict (`violation | null | inconclusive`), the family size, and the counts —
  plus the derived summary at `generation/tables/surprise_<cell_id>.tsv`;
- ONE `<study>#Sn` receipt per violation, carrying the segment, the deviation
  with its units, the adjusted score, the pinned table's hash, the family size,
  its label (`preregistered` or `post-observation`) and its exposure.

**Ids are always fully qualified.** The scouting ledger uses bare `S#`
ids, and `kleinlib.claims`' sentence scan exempts a bare `S3` as one. Writing
`03-demo#S3` is what keeps a surprise receipt and a scouting note from reading as
the same token; a bare `S#` in findings §③ earns a WARN.

**An explanation is never invented.** `explanation` starts `unresolved` and stays
there until a human writes one; `--explain "<segment>=<mechanism>"` records that
as testimony, nothing more. An anomaly ledger is worth keeping precisely because
the unexplained entries are still in it, and a study that reports the same number
of anomalies as explanations is reporting its imagination.

## What `klein generation verify` checks

The `surprise` family FAILs on: a late first registration (a cell admitted before
its registration anchor); a registration recorded before the METHOD gate;
`discovery_cells.yaml` edited in place; an adapter now inside the mutable
surface; an adapter or input whose hash differs today **or at the run's candidate
commit** ("unchanged now" would pass a file edited before the run and
restored after); a cell run as a sealed final test; a recorded run with no
admitted cell admission, or an admitted cell run that was never recorded; a
recomputation that disagrees with the record in any number; an eligible segment
missing from the table, or a segment the registration never froze; a receipt that
is not `<study>#Sn`, does not carry the run's table hash, or has no explanation
field; a set of receipts that is not exactly one per violating segment (the
multiset, so two receipts for one segment never cover two violations); and a
`confirmed` claim in `claims.lock` that reaches a discovery table by EITHER road
— citing its `art:` alias as evidence, or quoting a number whose `art` is that
alias — or that names an S receipt. Both the pinned per-unit table and the
derived `generation/tables/surprise_<cell>.tsv` are discovery tables; the
derived one is what findings quote. It WARNs on a bare `S#` in findings §③.

The capability outcome is `registered` (or `incomplete` before the first
registration — `n/a` means "this study did not declare it", and comes only from
the label's own defaults) with the cell, run, violation, unresolved and
post-observation counts, and the cells whose inference was at the group level.

## The exploratory ceiling, and the study that lifts it

**A screen selects what to look at. It cannot also confirm it.** The
selection and the evidence are the same rows, and no correction repairs that: the
`discover` kind cannot close a `confirmed` claim
(`references/inquiry-model.md`), and this family enforces the same rule from the
other side by failing a `confirmed` claim that rests on a cell's table or an S
receipt.

The honest continuation is a **separately registered `test` study** on genuinely
fresh observations, in which the surprising segment becomes a registered
hypothesis with its own prediction and its own sealed evidence. Record the link
in the discovery study's `evidence_design.yaml` `decision.successor`, cite the S
receipt in the successor's `research_plan.md`, and declare the exposure the
successor inherits in its own manifest (`predecessor`). A successor id restores
no blindness — what it buys is that the confirmation is measured on rows the
selection never saw.

On a study that also declares `escalation`, that hand-off has a machine record:
`klein generation escalate pivot` files the lineage — both contract hashes, the
inherited exposure, and every `<study>#Hn` / `<study>#Sn` id the predecessor issued
— and the successor cites the receipt back at `generation init --predecessor …
--successor-receipt …` (`references/escalation-protocol.md`). Without that
capability the same link is prose, and the referee reads it as prose.

## What this establishes, and what it does not

It establishes that these cells, these segments, these adapters and these inputs
were registered before this evidence existed; that the table the run pinned is
the table the record read; that every registered segment is accounted for; and
that the reported verdicts follow arithmetically from the declared rules.

It does not establish that the segmentation is scientifically meaningful, that
the statistic measures what its name suggests, that the multiplicity rule's
symmetry assumption holds, or that a violation means anything about the world.
`family_maxt` is a randomization diagnostic under a registered assumption, not
exact family-wise error control and not a statement about a population
(`knowledge/research-discipline.md`, lesson 6). Choosing quantities worth
screening, and explaining an `Sn` once it exists, remain human judgement — which
is why the receipt has a field for the explanation and no opinion about it.
