---
type: findings
domain: "language modeling"
profile: "ml-research"
kind: "predict"
status: complete
concepts: [fixed-step-budget, checkpoint-verification, paired-noise-floor, contiguous-block-split]
related: [13-charlm-fixed-budget]
---

# Findings — 13-charlm-fixed-budget

> SYNTHESIZE stage output. Every claim cites evidence ids from the immutable run
> manifests, the registered sweeps and the replication records. Protocol:
> `.claude/skills/klein/references/synthesis-protocol.md`; the lock and the numbers
> law: `references/claims-protocol.md`.
>
> The one-paragraph result: eight notarized runs of a 4-layer character transformer at
> a fixed 2000-step budget, every checkpoint scored by a verifier the training script
> could not touch. Four textbook recipe levers were registered as predictions before
> any of them ran — warmup, weight tying, dropout, width — and **not one of them
> cleared the measured floor**; two of them cost multiple floors. The only improvement
> came from the one lever that carried no prediction at all: when the learning rate is
> spent. The sealed final tenth then came back 3.140679 measured floors harder than
> development, so the study confirms a level and not a gap, and says so.

## ① Research-question verdicts

| Claim | RQ | Track | Verdict | Strength | Class | Evidence | Delta + uncertainty |
|---|---|---|---|---|---|---|---|
| **[C1]** | RQ1 | primary | supported, with the direction reversed | exploratory | empirical-description | E0001, E0002, E0003, E0004, E0005, E0006, E0007, `sweep:paired_floor` | The prior said "at most one of the four edits clears the floor — width". At most one did clear it, but it was none of the four: warmup −1.0431, weight tying −11.3693, dropout 0.1 −4.7255 and width −0.4742 floors against the anchor's five-seed mean, with one floor = 0.0149525 nats. The single keep is cosine decay at +3.3326 floors (E0006), which carried no registered prediction. |
| **[C2]** | RQ2 | primary | supported | exploratory | empirical-description | E0001, E0008, `rep:E0001@20260903T121129Z`, `verify:E0001@20260903T121358Z`, `verify:E0001@20260903T121401Z`, `sweep:device_check` | The trainer's own reported loss and the checker's independently recomputed loss never differed by a printable amount on any of the eight runs (largest `verifier_gap` 0.0 nats, declared tolerance 0.01). The same checkpoint re-scored on CPU and on MPS gives 1.572174 nats both times. A full re-execution of E0001 at the same seed on the same backend moved 0.000962 nats — 0.119808 fit-noise standard deviations. |
| **[C3]** | RQ3 | primary | supported | exploratory | empirical-description | E0003, E0006, `sweep:fit_noise`, `sweep:paired_floor` | This study measured recipes rather than noise, but only just: the largest effect is a cost of 11.3693 floors (weight tying, E0003) and the only gain is 3.53486 floors (E0006 over E0001). The prior said "a small multiple, not an order of magnitude" of the seed spread; the gain is a small multiple and the largest cost is an order of magnitude. |
| **[C4]** | RQ1 (sealed) | primary | measured | confirmed | empirical-description | E0008 | On the sealed final tenth of the corpus, never read before, the selected cosine-decay recipe retrained on train + development scores 1.566280 nats per character (2.259664 bits per character). |
| **[C5]** | — | primary | held | confirmed | procedural-verdict | E0001, E0008, `sweep:harness_controls` | The checker decided every disposition and the searcher never graded itself; the matched-compute guardrails held at 2000 steps and 128 evaluation context on all eight runs; and the four eval-harness controls behaved as a correct harness must, including the copy-the-input negative control at 4.750043 nats — worse than the chance level of 4.174388, where an off-by-one target alignment would have scored 0.693147. |
| **[C6]** | RQ1 | primary | interpretation | exploratory | mechanism-interpretation | E0003, `art:frontier` | Weight tying fails here because one matrix is asked to do two jobs at a scale where it has no slack: it removes 8320 parameters, 1.009317 per cent of the model, and the two roles want very different norms with no logit scale to reconcile them. The parameter COUNT was the wrong quantity to reason about. |
| **[C7]** | RQ1 (sealed) | primary | interpretation | exploratory | mechanism-interpretation | E0006, E0008, `art:neardup` | The sealed block is harder because a contiguous final tenth of a concatenation of plays is a different sample of the corpus's own nonstationarity, not because the model overfitted: the sealed run trained on 111616 more characters than the development incumbent did and still scored 0.046961 nats worse, while the cross-partition audit found nothing to memorise (largest Jaccard similarity 0.030059). |

Strength note. `confirmation.require` for this track is `[sealed]`, and the one sealed
access was spent on the selected candidate. That confirms **[C4]**'s level and
**[C5]**'s procedure; every comparison in **[C1]**, **[C2]**, **[C3]**, **[C6]** and
**[C7]** is a development-partition measurement and stays exploratory. The reason is
arithmetic, not modesty, and it is recorded in `program.md` (2026-09-03, "Scope
limitation"): one track means one sealed number, and a gap needs two.

## ② Registered predictions (from the ledger)

Copied from `klein predict list`; nothing here is re-decided. **`n_comparisons` = 6**,
all six registered in `study.yaml` before any run existed and adjudicated by the notary
on the checker's printed block. There was no post-hoc selection: P2–P5 were assigned to
E0002–E0005 in the order the contract lists them, one lever per run, and no prediction
was reassigned, re-scoped or re-run. No family-wise correction is applied and none is
claimed — each rule is a single pre-registered threshold in units of the measured
floor. Read the family accordingly: the two largest effects (P3 at -11.3693 floors, P4
at -4.7255 floors) are far outside any plausible multiplicity correction, while P5 at
-0.4742 floors sits inside the floor and would not survive one.

| P# | Statement | Rule | Observed | Verdict (ledger) | Evidence | Decision |
|---|---|---|---|---|---|---|
| P1 | the anchor recipe at a seed the floor sweep never used lands within two fit-noise standard deviations of the anchor's five-seed mean | `{key: anchor_z, op: le, value: 2}` | `anchor_z` 0.3766 | **supported** | E0001 | — |
| P2 | a linear learning-rate warmup improves val_loss by at least one measured floor at the same 2000 steps | `{key: delta_in_floors, op: ge, value: 1}` | `delta_in_floors` −1.0431 | **refuted** | E0002 | program.md 2026-09-03, "E0002 … Decision: P2 is REFUTED and warmup is not carried forward" |
| P3 | weight tying leaves val_loss within one measured floor of the anchor | `{key: delta_in_floors, op: abs_lt, value: 1}` | `delta_in_floors` −11.3693 | **refuted** | E0003 | program.md 2026-09-03, "E0003 … Decision: P3 is REFUTED and tying is not carried forward" |
| P4 | dropout 0.1 is at least one measured floor WORSE than the anchor | `{key: delta_in_floors, op: le, value: −1}` | `delta_in_floors` −4.7255 | **supported** | E0004 | — |
| P5 | doubling the width improves val_loss by at least one measured floor at the same 2000 steps | `{key: delta_in_floors, op: ge, value: 1}` | `delta_in_floors` −0.4742 | **refuted** | E0005 | program.md 2026-09-03, "E0005 … Decision: P5 is REFUTED; width is not carried forward" |
| P6 | on the sealed final tenth the selected candidate scores within two fit-noise standard deviations of the development incumbent | `{key: sealed_gap_in_fit_noise, op: abs_le, value: 2}` | `sealed_gap_in_fit_noise` 5.8485 | **refuted** | E0008 | program.md 2026-09-03, "E0008 (sealed) … Decision: P6 is REFUTED" |

Two supported, four refuted, none inconclusive, none open. The method card staked an
expectation on each of P2–P5 before they ran and got two of the four right: P2 refuted
as expected and P4 supported as expected; P3 was expected to be supported and was
refuted; P5 was marked "genuinely uncertain" and was refuted.

## ③ Surprises and why

**1. Weight tying is not free — it is the most expensive thing this study did.** The
method card computed that tying touches 8320 of 824320 parameters, 1.009317 per cent,
and concluded the change would be invisible. It cost 11.3693 floors (E0003) — the
largest single effect measured anywhere here, in the losing direction, and 21.1718
fit-noise standard deviations from the anchor mean. The mechanism (**[C6]**, and
exploratory by class) is that the parameter count was the wrong quantity to reason
about. `press2017` ties a large, sparsely-updated word embedding, where the same matrix
is most of the model and each row is seen rarely; here the table is 65 rows seen
constantly, and tying forces one matrix to serve as both the input lookup and the
output classifier with no logit scale to reconcile the very different norms the two
roles want. A study that had only read the paper would have shipped this as a free
parameter saving.

**2. Width bought nothing at a fixed step budget.** Multiplying the parameter count by
3.908075 moved val_loss by −0.4742 floors (E0005) — inside the floor, and in the wrong
direction. This is not a contradiction of `kaplan2020`: that work grows the model while
holding FLOPs fixed, and `hoffmann2022` grows tokens alongside it. This study grew
neither. Holding STEPS fixed is a harsher condition than holding compute fixed, and it
is the condition a practitioner with a wall-clock deadline and a fixed dataset actually
faces. The honest statement is that at 2000 steps on 891904 training characters,
capacity was not the binding constraint.

**3. The only thing that worked carried no prediction.** Four registered levers, four
failures; the keep came from candidate #5 on the phase slate, cosine decay, at +3.3326
floors (E0006). That asymmetry is a finding about the priors, not about the machinery.
The four registered levers are the ones the literature discusses most; the lever that
paid is the one a practitioner usually treats as a default rather than as a hypothesis.
`sweep:learning_curves` shows where it pays: the two schedules are indistinguishable
for the first few hundred steps and separate only once the decay bites, ending at
1.563815 (anchor) and 1.518369 (cosine) nats.

**4. Warmup's verdict flipped when its partner was present.** E0002 put warmup on a
CONSTANT learning rate and it landed -1.0431 floors from the anchor. E0007 put the same warmup on the
cosine schedule and it landed 0.103528 floors from the incumbent — inside the floor,
neither cost nor benefit. The registered P2 stands exactly as adjudicated, but the
honest advice is "decay, and warmup is then optional", not "warmup is harmful". This is
what a fixed step budget does to an ablation: a lever tested against the wrong partner
answers a different question than the one you meant to ask.

**5. The sealed tenth is 3.140679 floors harder than development.** P6 predicted the
sealed score would land within two fit-noise standard deviations of the development
incumbent; it landed 5.8485 away (**[C7]**). The sealed run had MORE training data than
the development incumbent — it retrained on train + development — so this is not
overfitting. A contiguous-block split protects against the leak a shuffled split would
create (the cross-partition audit found a largest Jaccard similarity of 0.030059,
i.e. nothing to memorise) and pays for that protection with a distribution shift
between the blocks. Both halves of the trade are real and neither is usually reported.

**6. The one thing that never surprised anyone: the checker.** Two independently
written implementations of the same architecture and the same loss sweep, in separate
processes, agreed to 0.0 nats on all eight runs against a tolerance of 0.01. The
mechanism cost one extra script, and it is the reason every number above can be read as
a measurement rather than as a claim.

## ④ Practical advice

**[C8]** Measure your floor on the quantity your decision actually uses. The five-seed
level spread here has standard deviation 0.00802952; the ten paired differences between
two seeds of the same recipe have standard deviation 0.00747623 and range 0.026494, and
it is the paired spread a candidate-versus-anchor comparison has to clear. The bar
`max(2·std, range/2)` = 0.0149525 nats came from the paired sweep, not from the level
sweep (evidence: `sweep:fit_noise`, `sweep:paired_floor`).

**[C9]** At a fixed step budget, spend the schedule before you spend the capacity. The
only keep in this study was a pure schedule change worth 0.052855 nats, while
multiplying the parameters by 3.908075 was worth −0.4742 floors (evidence: E0005,
E0006).

**[C10]** Never let the training script grade its own checkpoint. It costs one extra
file: a checker that loads the artifact, asks the contract which rows are the
validation set, rebuilds the model from the checkpoint's own config with its own
implementation, and recomputes the loss. Here the two never disagreed by a printable
amount, which is the outcome you want and cannot assume (evidence: E0001, E0008,
`sweep:harness_controls`).

**[C11]** Put a copy-the-input control in your language-model harness. It bets the next
character equals the current one, so a correct harness scores it WORSE than chance —
4.750043 against 4.174388 nats here — while the classic off-by-one target alignment
would score it 0.693147. No other control in this study could have caught that bug
(evidence: `sweep:harness_controls`).

**[C12]** If you split ordered text into contiguous blocks, measure the distribution
shift you just bought instead of assuming it away. The same recipe with more training
data scored 0.046961 nats worse on the sealed block than on the development block
(evidence: E0006, E0008).

**[C13]** Decide at design time how a comparison gets its sealed number. One track and
one sealed access can confirm a level and never a difference; this study's contract
declared one track and said nothing about the gap, so its headline improvement stays
exploratory by arithmetic. Either give each family its own track or pre-register the
gap as exploratory-by-construction — choosing afterwards is how sealed vocabulary gets
stretched (evidence: E0006, E0008).

## ⑤ Practitioner impact — what to change in a training recipe, and at what cost

**The change.** Replace a constant learning rate with a cosine decay to a tenth of the
peak over the whole budget. **The matched-compute condition.** 2000 AdamW steps of 32
windows of 128 characters, a 4-layer 4-head 128-wide causal transformer (824320
parameters), on 891904 training characters of tiny Shakespeare — every candidate at
exactly the same step count, enforced by the checker reading `steps` out of the
checkpoint rather than promised by the training script. **The seed spread it was
measured against.** Five identically-configured runs of the anchor recipe, standard
deviation 0.00802952 nats, and the ten paired differences among them, standard
deviation 0.00747623 nats, giving a keep bar of 0.0149525. **The size of the change.**
0.052855 nats, or 3.53486 floors — it clears the bar by more than three times, and it
is the only one of six single changes that clears it at all. **The hardware.** Apple
silicon, `pick_device` selecting MPS; the same checkpoint re-scores identically on CPU,
and one 2000-step run costs well under a minute on either. **What it does not say.** It
does not say cosine decay is better than a schedule this study never ran, and it does
not say the improvement survives to unseen text: the sealed block was 3.140679 floors
harder than development for the same recipe, and with one track and one sealed access
there is no sealed measurement of the anchor to difference against.

Nothing here is priced. This study registers no `materiality:` block, so "improvement"
means only that a pre-registered, measured bar was cleared.

## ⑥ Literature tie-back

- `xiong2020` (ICML 2020) predicted the P2 result and for the right reason: a Pre-LN
  stack does not need warmup for stability. This study adds the part the paper does not
  address — at a fixed STEP budget, warmup on a constant learning rate is not merely
  unnecessary but costly (-1.0431 floors), because the steps spent below the target
  rate are never given back; paired with decay it is free again (0.103528 floors from
  the incumbent).
- `press2017` (EACL 2017) is the clearest miss. Its result is real at word-level
  vocabularies; transplanted to a 65-symbol vocabulary it inverts, at −11.3693 floors.
  The transferable lesson is that the mechanism, not the technique, is what travels.
- `srivastava2014` behaved exactly as the regime table said it would at this budget
  (P4 supported, −4.7255 floors), and the open hypothesis that 9.2 passes over the data
  would leave the model regularization-limited was refuted by the same run.
- `kaplan2020` and `hoffmann2022` frame the width result rather than being contradicted
  by it: neither claims that width pays at fixed steps, and this study is evidence that
  it does not (−0.4742 floors at a parameter ratio of 3.908075).
- `picard2021` and `bouthillier2021` are why the study measured a floor before it
  compared anything, and both were vindicated in a specific way: a single seed of the
  anchor would have landed anywhere in a 0.021485-nat range, which is wider than the
  entire width effect this study measured.
- **Prior scorecard.** RQ2's prior was `(source: scouted)` and is excluded. That leaves
  two `uninformed` priors and no knowledge-sourced ones, because
  `knowledge/domains/ml-research/` was empty when this study opened — this study is its
  first entry. Of the two uninformed priors, RQ1's was half right (at most one lever
  cleared the floor, but not the one it named) and RQ3's was right in magnitude for the
  gain and wrong for the largest cost. There is no knowledge-versus-uninformed
  comparison to settle yet; the next ml-research study will have one.

## ⑦ What to try next

1. **A second schedule setting, since the schedule is the only lever that paid.**
   Cosine to zero rather than to a tenth of the peak, and a higher peak paid for by the
   decay. This is the cheapest test of whether E0006 found the lever or merely one point
   on it.
2. **Weight tying WITH a learned logit scale.** **[C6]** blames the shared-norm
   constraint rather than the parameter sharing; a single scalar multiplying the tied
   logits separates those two explanations in one run.
3. **Width at matched FLOPs instead of matched steps** — the wider model with
   proportionally fewer steps, which is the `kaplan2020` condition this study
   deliberately did not run. It converts "capacity does not pay at fixed steps" into a
   statement about where the exchange rate actually sits.
4. **A two-track version of this study**, one track per schedule family, so the gap
   between them gets two sealed numbers instead of one. **[C13]** is the reason, and it
   is the cheapest way to turn this study's exploratory headline into a confirmed one.
