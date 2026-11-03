---
type: findings
domain: "LLM evaluation (grade-school math reasoning)"
profile: "llm"
kind: "test"
status: synthesized
concepts: [chain-of-thought, direct-answer, exact-match, paired-comparison, cluster-bootstrap, template-twins, contamination-gap, ceiling, prompt-compliance, call-ledger, salted-requery, replay-is-not-replication]
related: [study.yaml, program.md, playbook.md, method_card.md, data_card.md, references.yaml, results.tsv, aux_metrics.tsv, claims.lock, lib/synthesis.py, tables/synthesis_arms.tsv, tables/synthesis_paired.tsv, tables/synthesis_quantities.tsv]
---

# Findings — 20-llm-cot-contamination

> SYNTHESIZE stage output, written 2026-11-03 by the `klein-synthesist` subagent, which
> ran no experiment and never referees these findings. Every claim cites evidence ids
> from the immutable run manifests, the replication records and the pinned tables; the
> same ids live in `claims.lock` with a class, a strength and a home for every number.
> Protocol: `.claude/skills/klein/references/synthesis-protocol.md`; the lock and the
> numbers law: `references/claims-protocol.md`.
>
> **Scope of every sentence below.** One model, `qwen-flash-2025-07-28` (the dated
> snapshot on DashScope's OpenAI-compatible endpoint; every ledger record re-read for
> this synthesis, study and re-query shards alike, names exactly that `model_served`,
> `art:arms`), queried on 2026-11-03 at temperature 0 with thinking off, through two
> registered prompt arms (`lib/prompts.py`). Nothing here is a claim about another
> model, another snapshot, a thinking-mode configuration, or another prompt wording.
>
> **Trajectory mined.** Six ledger rows on two registered tracks (no frontier exists on
> either; every row is a measured cell or a crash): one crash (E0001, HTTP 429 after
> 599 calls), three development cells (E0002, E0003, E0004), two sealed cells
> (E0005, E0006), two salted re-query replications (`rep:E0002@20261103T082725Z`,
> `rep:E0003@20261103T084446Z`) and one offline replay (`replay:E0002@20261103T085311Z`).
> Six registered predictions, all adjudicated by the notary: 2 supported, 4 refuted.
>
> **Derived tables.** `lib/synthesis.py` (written at this stage; it calls no model)
> re-scores the committed call shards and replication shards with the fixed scorer and
> writes `tables/synthesis_arms.tsv` (`art:arms`: compliance and token diagnostics per
> cell and arm), `tables/synthesis_paired.tsv` (`art:paired`: the paired outcome tables)
> and `tables/synthesis_quantities.tsv` (`art:quant`: every derived quantity below). Its
> re-scored exact-match equals the notarized value in every cell-arm, and the method
> card's mechanical identities hold: E0004 `em_cot` 0.96 equals E0003 `em_twins` 0.96,
> and E0005 `em_cot` 0.97 equals E0006 `em_twins` 0.97.

## ① Research-question verdicts

Both tracks are `test` tracks with `confirmation.require: [sealed, replicate]`, and both
requirements exist on both tracks — sealed cells E0005 (`cot_gain`) and E0006
(`contamination`), salted re-queries of E0002 and E0003 — so a description of what was
measured may be `confirmed`, scoped to this snapshot and these prompts. Mechanisms stay
`exploratory` by class.

| Claim | RQ | Track | Verdict | Strength | Class | Evidence | Delta + uncertainty |
|---|---|---|---|---|---|---|---|
| **[C1]** | RQ1 | cot_gain | prior **refuted**: no loss detected | confirmed | empirical-description | E0002, E0004, E0005, rep:E0002@20261103T082725Z | direct EM 0.95 / 0.985 / 0.97; the direct arm is not number-only (C5) |
| **[C2]** | RQ2 | cot_gain | **refuted** | confirmed | empirical-description | E0002, E0005, rep:E0002@20261103T082725Z | em_gain +0.01, 95% CI [-0.01, 0.03]; re-query -0.0067 |
| **[C3]** | RQ3 | contamination | **inconclusive at 5 points**: no gap detected, a 5-point gap not excluded | confirmed | empirical-description | E0003, E0006, rep:E0003@20261103T084446Z | em_gap 0.02 [-0.015, 0.06] dev; 0.01 [-0.04, 0.065] sealed; re-query -0.025 |
| **[C4]** | RQ4 | cot_gain | **refuted** (there is no gain to survive) | confirmed | empirical-description | E0004, E0005 | em_gain -0.025 [-0.065, 0.005] dev twins; 0.000 [-0.055, 0.045] sealed twins |

**[C1]** Under the registered number-only instruction, qwen-flash scored 0.95 direct exact-match on 300 items of public GSM8K (E0002), 0.985 on the development twins (E0004) and 0.97 on the sealed twins (E0005), so the RQ1 prior of a direct score between 0.55 and 0.85 is refuted; the salted re-query of the anchor scored 0.9533.

What RQ1 asked — how much is lost when the model must answer with the number only — the
study cannot answer as posed, because the direct arm did not answer with the number only
(C5). What it measured is the loss under the registered *instruction*, and that loss is
not detectably different from zero (C2, C4). The lead recorded the non-compliance before
any score was computed (program.md, 2026-11-03: "The registered prompt is NOT changed")
and kept the prompt, so this is a property of the measurement, not a post-hoc rescue.

**[C2]** On 300 items of public GSM8K, chain-of-thought exceeded the registered direct prompt by +0.01 exact-match, paired item-bootstrap 95% interval [-0.01, 0.03] (E0002); the interval excludes the registered 0.10, and the salted re-query gave -0.0067, a shift of 0.0167 inside the pre-registered 0.03 tolerance.

The paired outcome table (`art:paired`) is 282 both right, 6 CoT only, 3 direct only, 9
both wrong; McNemar's exact p is 0.5078 on these independent public items. The
re-query's table is 280 / 4 / 6 / 10: the sign of a difference resting on 9 and 10
discordant items is not stable under re-query, which is what a true gain near zero
predicts.

**[C3]** With chain-of-thought, exact-match on the 50 template originals exceeded their development twins by 0.02 (95% interval over templates [-0.015, 0.06], E0003) and the sealed twins by 0.01 ([-0.04, 0.065], E0006); no measurement detected a gap, but both upper ends exceed 0.05, so a 5-point contamination gap is not excluded, and the salted re-query of E0003 gave -0.025.

RQ3 asked whether the gap exceeds 5 points. Every point estimate says no (0.02, 0.01,
-0.025); no interval excludes a gap of 0.05. The verdict is therefore "no contamination
signature detected at this instrument's resolution", not "no contamination". Three limits
travel with it: (a) the two sealed cells share ledger entries — E0006 made no new call,
reusing E0003's 50 original answers and E0005's 200 sealed CoT twin answers (all 50
`score_original` values are identical across the two tables, `art:quant`), so E0006 is a
re-scoring of answers already recorded, not an independent query of the model; (b) the
probe sees instance memorization only (a twin is a fresh string, not a fresh kind of
problem; method_card.md §4); (c) twin answers run larger than their originals' (median
ratio 1.13 on the development block and 1.29 on the sealed block, method_card.md §4),
which pushes the gap upward, so the null is conservative in that respect.

**[C4]** The chain-of-thought gain does not appear on fresh twins either: -0.025 exact-match on the development twins (cluster bootstrap over 50 templates [-0.065, 0.005], E0004) and 0.000 on the sealed twins ([-0.055, 0.045], E0005), both intervals excluding the registered 0.10.

The direct arm scored *above* CoT on the development twins (0.985 vs 0.96; 1 CoT-only vs
6 direct-only discordant twins) and level with it on the sealed twins (0.97 vs 0.97; 6
vs 6). McNemar's p on these blocks (0.125, 1.0) treats the four twins of a template as
independent and overstates the evidence; the cluster interval is the inference.

**[C15]** The notary adjudicated all six registered predictions — P1, P2, P4 and P5 refuted, P3 and P6 supported — and every refuted prediction carries a dated Decision line in program.md.

## ② Registered predictions (from the ledger)

Copied from `klein predict list` (2 supported, 4 refuted, 0 inconclusive, 0 open). The
method card's pre-run P(holds) stands beside each, so the card's calibration is on the
record.

| P# | Statement | Rule | Observed | Verdict (ledger) | Card P(holds) | Evidence | Decision |
|---|---|---|---|---|---|---|---|
| P1 | public direct EM ≤ 0.85 | `{em_direct, <=, 0.85}` | 0.95 | **refuted** | 0.93 | E0002 | program.md 2026-11-03: "P1 refuted ... the prior that a small model loses much under number-only answering is dropped for qwen-flash ... P1 stays as registered." |
| P2 | public CoT gain ≥ 0.10, paired | `{primary_metric, >=, 0.10}` | 0.01 | **refuted** | 0.90 | E0002 | program.md 2026-11-03: "P2 refuted ... CoT-over-direct gain on the public sample is treated as absent, not as a small positive effect." |
| P3 | dev-twin gap ≤ 0.05 (CoT, template-paired) | `{primary_metric, <=, 0.05}` | 0.02 | **supported** | 0.64 | E0003 | — (interval upper end 0.06 exceeds 0.05) |
| P4 | dev-twin CoT gain ≥ 0.10 | `{primary_metric, >=, 0.10}` | -0.025 | **refuted** | 0.90 | E0004 | program.md 2026-11-03: "P4 refuted ... the CoT gain does not appear on development twins either." |
| P5 | sealed-twin CoT gain ≥ 0.10 | `{primary_metric, >=, 0.10}` | 0 | **refuted** | 0.90 | E0005 | program.md 2026-11-03: "P5 refuted ... the null gain is confirmed on the sealed twin block, with findings scoped to this model and this registered direct prompt." |
| P6 | sealed-twin gap ≤ 0.05 | `{primary_metric, <=, 0.05}` | 0.01 | **supported** | 0.64 | E0006 | — (interval upper end 0.065 exceeds 0.05; E0006's answers are E0003's and E0005's ledger entries) |

**What the two supported verdicts mean.** P3 and P6 are point-estimate rules and the
notary applied them as written. Both are supported, and neither interval sits below the
0.05 bound: E0003's upper end is 0.06 and E0006's is 0.065. "P6 supported" must not be
read as "the gap is below 5 points with 95% confidence"; it says the point estimate is.
The method card said as much before any run: with twins scoring 0.95 or more, "P3 can
then fail only by noise" and no gap is detectable at 80% power.

**The method card's own priors (not registered; scored here from `art:quant` and the
aux metrics).**

| M | Expectation | Observed | Verdict |
|---|---|---|---|
| M1 | public em_gain ≥ +0.20 | +0.01 (E0002) | **falsified** |
| M2 | direct EM drops ≥ 0.05 from public items to dev twins | -0.035 (direct rose, 0.95 → 0.985) | **falsified** |
| M3 | CoT drop smaller than direct drop | CoT drop 0.000, direct drop -0.035 | **falsified** |
| M4 | E0003 interval width ≥ 0.100 | 0.075 | **falsified** (the card had named twins scoring about 0.95 or more as the likely way out; they scored 0.96) |
| M5 | salted re-query changes between 1 and 36 of 600 item-arm scores | 9 of 600 (rep:E0002@20261103T082725Z) | **held** |
| M6 | CoT output tokens ≥ 20× direct | 1.85× public, 1.91× dev twins, 1.92× sealed twins | **falsified** — the most informative miss (C5) |
| M7 | 45-template gap within 0.03 of the 50-template gap | 0.0033 dev, 0.0011 sealed | **held** |

Two of seven held. Every falsified prior missed in the same direction: the card expected
a model that needs its scratch paper and loses without it, and this snapshot writes its
scratch paper whatever the instruction says.

## ③ Surprises and why

**[C5]** The registered direct arm did not comply with the number-only instruction: 4 of 300 public replies were a bare number (0 of 200 on each twin block), its median output was 112.5 tokens against 243 for chain-of-thought, and chain-of-thought wrote only 1.85 times the direct arm's mean output tokens on public items (1.92 on the sealed twins), so em_gain here compares chain-of-thought with a terse chain-of-thought, not with answering without written steps.

Evidence: E0002, E0004, E0005 and the re-query shards (`art:arms`; the re-query's direct
arm also had 4 of 300 bare replies). The experimenter saw this in E0001's crashed shard
before any score existed; the lead declined to change the prompt so the instrument would
not adapt to observed outputs (program.md, 2026-11-03). The method card had named this
failure mode in advance ("the direct arm writing steps anyway"), and M6's ≥20×
expectation is the quantitative form of the prior it broke. The fact is an
empirical description; that it is *why* the gain vanished is C6's interpretation.

**[C6]** The chain-of-thought gain is near-unmeasurable here because both arms sit at the ceiling: direct and chain-of-thought exact-match lie between 0.95 and 0.985 in every cell, so the largest gain the public cell could have shown is 0.05, and only 9 of 300 public items (E0002) and 12 of 200 sealed twins (E0005) were discordant.

Class: mechanism-interpretation, exploratory. The arithmetic is fixed (a gain cannot
exceed 1 minus em_direct), but whether a compliant direct arm would open headroom is an
untested hypothesis (playbook H3; ⑦ item 1). The ceiling also explains M4: with twins at
0.96 the gap's variance shrinks (the card's §2 ceiling row), so the interval came out
narrower than the 0.100 the card expected.

**[C7]** The salted re-query of the development contamination cell flipped the sign of the gap, from 0.02 to -0.025, a shift of 0.045 inside the pre-registered 0.05 tolerance: 3 of 50 originals went from right to wrong and 1 from wrong to right, moving em_original from 0.98 to 0.94, while 7 of 200 twin scores changed.

Class: mechanism-interpretation, exploratory. Mechanism: temperature 0 is not
determinism on a hosted model (`ref:he2025`, `ref:atil2024`); the anchor re-query changed
9 of 600 item-arm scores (M5). One original is worth 0.02 of em_gap, so a handful of
flipped originals is enough to reverse a gap this small. The replication reproduced by
its pre-registered arithmetic, and that is the correct procedural verdict; it is also a
demonstration that the *sign* of a gap below about 0.05 is set by serving noise on 50
originals. The record lists `ci_low` (-0.015 → -0.08) as outside tolerance, descriptively.

**[C8]** On the development twins the direct arm scored above chain-of-thought (0.985 vs 0.96, gain -0.025, E0004), and on the sealed twins the two arms tied at 0.97 (E0005); the reversal did not survive fresh instances of the same templates, which is most consistent with noise on 7 discordant twins.

Class: mechanism-interpretation, exploratory; `unresolved` beyond "noise". Neither
interval excludes zero. Three CoT twin replies on the development block were cut at
`max_tokens` against two direct replies (`art:arms`) — too few to explain six
direct-only wins, so truncation is not the mechanism.

**Not a surprise, recorded for completeness.** The five templates whose number-swapped
variants are public in GSM-Symbolic did not drive the gap: on the development block they
gave 0.05 against 0.0167 for the other 45 (one template, t1088, carries the five's gap),
and on the sealed block 0.000 against 0.0111 (`art:quant`; n = 5 is descriptive only, M7
held). The magnitude-matched subset (dropping t1281 and t0466) gave 0.0208 on the
development block and 0.0104 on the sealed block. The method card's suggested regression
of the per-template gap on answer size was not run: only 5 of 50 development templates
(3 sealed) have any gap at all, too few points for a slope.

## ④ Practical advice

**[C9]** Before reading any CoT-vs-direct gain, audit the direct arm's compliance from the ledger — the share of bare-number replies and the output tokens per item against the CoT arm — because here only 4 of 300 direct replies were bare and the CoT arm wrote only 1.85 times the direct arm's tokens, which turns the comparison into CoT versus terse CoT.

Evidence: E0002, `art:arms`. A recent instruct model may ignore "number only"; a scorer
that falls back to the last number will still score it, so the arm silently becomes a
different arm.

**[C10]** Before registering a gain threshold, check the headroom the direct arm leaves: a gain cannot exceed 1 minus the direct score, so at a direct score of 0.95 a registered gain of at least 0.10 was arithmetically unreachable on the public items.

Evidence: E0002, P2. Register the threshold from a pilot direct score or from items off
the ceiling (a harder benchmark, longer chains); otherwise the refutation is guaranteed
by arithmetic, not learned from the model.

**[C11]** Size a template-paired contamination probe to the gap it must resolve: with 50 templates the 95% interval on the gap was 0.075 wide on the development twins and 0.105 wide on the sealed twins, so a 5-point gap can be neither detected nor excluded; plan on roughly four times the templates to halve the interval.

Evidence: E0003, E0006, method_card.md §2 ("Halving the SE would take about four times
as many templates").

**[C12]** Treat cells that share ledger entries as one measurement: the sealed contamination cell made no new model call and re-scored the 50 original and 200 sealed chain-of-thought answers that E0003 and E0005 had already recorded, so its agreement with them is by construction; an independent check needs a salted re-query.

Evidence: E0006 (`calls_cached` 250 of `calls_total` 250), `art:quant`. The ledger's
de-duplication is what makes a study cheap and replayable; it is also what couples the
cells, and findings must say which cells are coupled.

**[C13]** Never count a ledger replay as a replication of a model result: the offline replay of E0002 reproduced with a difference of 0 because it re-scored the same recorded answers, while the salted re-query of the same cell changed 9 of 600 item-arm scores and moved the gain by 0.0167.

Evidence: replay:E0002@20261103T085311Z, rep:E0002@20261103T082725Z. The replay audits
parsing, scoring and aggregation; only the re-query says anything about the model.

**[C14]** On twin blocks, report the cluster bootstrap over templates, not McNemar's test: the four twins of one template share their wording and structure, and McNemar's p (0.125 on the development twins) treats them as independent and overstates the evidence.

Evidence: E0004, E0005, method_card.md §2 eq. (3). On the independent public items
(E0002) McNemar is valid.

## ⑤ What changes in practice — for whoever prompts, evaluates or deploys this model

- **The change measured:** "Solve the problem step by step, then give the final number
  after 'Answer:'." against "Answer with the final number only.", both at temperature 0,
  `max_tokens` 1024, thinking off.
- **Model and date:** `qwen-flash-2025-07-28`, DashScope compatible-mode endpoint, queried
  2026-11-03; every record's `model_served` is that string.
- **Item set and contamination status:** 300 public GSM8K test items (presumed
  contaminated: public since 2021, training cutoff undisclosed), plus 200 development
  and 200 sealed procedurally generated twins of 50 GSM8K templates. Five templates have
  public number-swapped variants (GSM-Symbolic). No contamination signature was detected
  at the probe's resolution (C3).
- **Paired effect:** +0.01 [-0.01, 0.03] on public items; -0.025 [-0.065, 0.005] on
  development twins; 0.000 [-0.055, 0.045] on sealed twins (C2, C4).
- **Token cost per item:** mean output tokens 265.7 (CoT) vs 143.5 (direct) on public
  items; 295.4 vs 154.1 on the sealed twins (`art:arms`). No price is pinned
  (`calls.price` is unset), so no dollar figure is given.
- **Implication.** For this snapshot, on GSM8K-style arithmetic, an explicit
  step-by-step instruction bought no detectable exact-match over the registered direct
  instruction while roughly doubling output tokens; the cheaper prompt scored the same.
  This is not evidence that written steps are unnecessary — the "direct" arm wrote them
  too (C5). No `materiality:` block is registered, so nothing here is priced.

## ⑥ Literature tie-back

- **Wei et al. 2022 and Kojima et al. 2022 (`ref:wei2022`, `ref:kojima2022`).** Their
  large CoT gains came from models that answered tersely unless told otherwise. This
  snapshot writes steps unprompted (C5), so the contrast those papers measured is absent
  from the direct arm; the null gain does not contradict them, it sits outside their
  regime.
- **Sprague et al. 2024 (`ref:sprague2024`).** Their Table 7 anchored P1 and P2. This
  study's direct score of 0.95 lies far above every direct score in that table, which is
  where their own trend points: among strong models, the smallest CoT gains belonged to
  those with the best direct answers. The card's P1 and P2 priors (0.93, 0.90) leaned on
  that table and were wrong for this model — a 2024 table is not a prior for a 2025
  instruct snapshot whose direct arm is not direct.
- **Mirzadeh et al. 2024, GSM-Symbolic (`ref:mirzadeh2024`).** They reported drops when
  only the numbers change. Here the template-paired gap was 0.02 and 0.01 with intervals
  reaching 0.06 and 0.065: consistent with a small drop or none, and unable to tell them
  apart. Długosz et al. 2026 (`ref:dlugosz2026`) — many such drops are within noise and
  partly number size — is the frame this result fits.
- **Zhang et al. 2024, GSM1k (`ref:zhang2024`).** Fresh human-written items found little
  overfitting in many frontier models; this study's null points the same way, with the
  weaker control (fresh strings, not fresh problem types).
- **He 2025 and Atil et al. 2024 (`ref:he2025`, `ref:atil2024`).** Temperature-0
  nondeterminism was observed directly: 9 of 600 item-arm scores changed on re-query (M5
  held), enough to flip the sign of the development gap (C7).
- **Priors scorecard (knowledge vs uninformed).** No RQ prior is labelled `scouted`, so
  all four are eligible. Knowledge-sourced: RQ2 (CoT gain of at least 10 points, 0.65)
  was wrong; RQ3 (gap within 5 points, about even) was right at the point estimate.
  Uninformed: RQ4 (the gain survives on twins, 0.6) was wrong — there was no gain. RQ1
  mixes both sources and was wrong. Four priors cannot rank the sources. The knowledge
  they leaned on ("CoT gains on GSM8K are large") needs a qualifier at promotion: large
  for models whose direct answers are terse.

## ⑦ What to try next

1. **Make the direct arm direct, then re-measure the gain (playbook H3).** A new study
   with an enforced bare-number arm (a `max_tokens` cap of a few tokens, or a
   response-format constraint) and compliance itself as a registered prediction (a
   minimum bare-reply share), on the same public items and twin blocks. This is the
   cheapest test of whether C6's ceiling belongs to the instrument or to the model.
2. **Move off the ceiling.** Repeat the paired comparison on items where the direct arm
   scores well below 0.95 (longer GSM-style chains, or harder re-instantiations), so a
   registered gain of 0.10 is reachable.
3. **Power the contamination probe.** Roughly four times the templates (C11), with
   magnitude-matched twins, and the direct arm also run on the originals (the method
   card notes a memorized answer would show most clearly there, and this contract never
   ran it). Register the gap rule on the interval's upper end, not the point estimate.
4. **Measure serving noise as the floor.** Run at least three salted re-queries of one
   cell (`--recipe resample`) and record the flip rate as `fit_noise`; this study's
   `minimum_delta` values are pre-registered replication tolerances, not measured floors
   (`klein verify` reports both tracks' noise floor as not measured).

## Caveats that limit every conclusion

- **One snapshot.** `qwen-flash-2025-07-28` only; nothing here extends to another model,
  snapshot, decoding setting or thinking mode.
- **Ceiling.** Both arms at 0.95 to 0.985 make any CoT gain near-unmeasurable (C6).
- **Non-compliance.** The registered direct arm is a terse CoT (C5); P1 and P2 measure
  the instruction, not answering without written steps.
- **Coupled sealed cells.** E0005 and E0006 share ledger entries; the two sealed cells
  are one query of the model on the sealed twins, scored two ways (C12).
- **P6 supported with an interval past the bound.** Upper end 0.065, above 0.05.
- **Sign flip under re-query.** E0003's re-query reversed the gap's sign while
  reproducing within tolerance (C7).
- **Replay is not replication.** `replay:E0002@20261103T085311Z` says nothing about the
  model and satisfies no confirmation requirement (C13).
- **McNemar on twins** treats twins as independent (C14).
- **Crash.** E0001 crashed on HTTP 429, an infrastructure fault (eight workers on an
  account shared with study 24), not a bad idea; it was re-run as E0002, which answered
  599 of its requests from E0001's pinned shard and made 1 new call. The crashed
  direction was retried, so it leaves no gap.
- **Procedural notes for the referee.** Every manifest records an empty candidate diff
  (the cell choice was committed in `analyze.py` before each run, or set by the sealed
  flag; program.md discloses this for E0004). `aux_metrics.tsv` carries `DRYRUN` rows
  from the sealed contamination rehearsal — development-twin values replayed from the
  ledger, not evidence. The data card dates GSM-Symbolic's public release to October
  2024, the method card to the data commit of 8 December 2024; the five-template caveat
  holds under either date for a July 2025 snapshot.
- **Evidence use.** All six non-keep rows (the E0001 crash; E0002 to E0006 measured) are
  cited above.
