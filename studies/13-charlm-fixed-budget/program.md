# Program — 13-charlm-fixed-budget

## Roster

Who is doing what, and on what. REFEREE cites this table for the independence rung
(`references/referee-protocol.md`); a blank `experimenter` row caps the achievable
rung at "fresh session", because no artifact then says what ran the loop. Fill the
experimenter row at CONSULT and update a row whenever its model, tool or session
changes.

| Role | Who (model · tool · session) | Since |
| --- | --- | --- |
| experimenter | Claude Code general-purpose subagent · model `claude-opus-5[1m]` · session `session_016HefKjsAszSh9M5FJ8Zw4g` — drives CONSULT, DATA, METHOD, every `klein run-one`, the sweeps and SYNTHESIZE | 2026-09-03 |
| data-gate auditor | the same agent, self-performed in a clean-room pass: the leakage audit was run AFTER `prepare.py` and the profile were finished, reading only `study.yaml`, `prepare.py`, the prepared artifacts and the index table — never this file | 2026-09-03 |
| referee | (left blank until the referee runs) | |
| lead | Claude Fable 5.1, orchestrating the Klein 2.0 exhibit set | 2026-09-03 |

Gate acknowledgements for this exhibit are **delegated by the lead to the driving
agent**: gates are recorded with `--acknowledged-by lead-agent`, and the delegation is
recorded here rather than inferred. The same delegation covers the phase
acknowledgements.

This is the living lab notebook. `study.yaml` is the machine contract;
`study_state.json`, `events.jsonl`, and `runs/E####/manifest.json` are generated audit
state and must not be hand-edited.

## Goal and track contract

- Goal: Under a fixed 2000-step training budget on a character-level corpus, which
  single-change training-recipe edits to a small char transformer improve held-out
  validation loss by more than the measured run-to-run floor, when every checkpoint is
  scored by a verifier the training script cannot touch?
- Track: `primary` (frontier)
- Primary metric: `val_loss` — mean next-character cross-entropy in **nats per
  character** (natural log), lower is better. `bpc` is printed alongside. The minimum
  meaningful delta is 0 until Phase 0 measures it; a consult re-record then sets it.
- Budget in STEPS: `max_steps = 2000`. The verifier reads the step count out of the
  checkpoint and prints it; the guardrail `steps == 2000` makes matched compute a
  disposition, not a promise. `eval_context == 128` does the same for matched
  measurement. `wall_seconds` is informational (ml-research profile §6).
- Verifier: `verify.py` — outside `entrypoint.mutable`, hashed at the METHOD gate,
  run by the notary in its own process, tolerance 0.01 nats. Its number decides every
  disposition; `train.py`'s own reported loss is recorded beside it and a disagreement
  beyond tolerance is a crash.
- Results are exploratory until the track's one sealed final-test run confirms them.
  A small delta without uncertainty must not be described as real or decisive.

## Data and split

- Source: `bundled:tinyshakespeare/tinyshakespeare.txt.gz` (1,115,394 characters,
  65-character vocabulary; public-domain text, MIT-declared packaging).
- Contiguous-block time split over character offsets, in 1024-character blocks:
  train = blocks 0–870 (891,904 characters), development = blocks 871–979 (111,616),
  sealed = blocks 980–1088 (111,874). No window ever straddles a partition boundary.
- Adaptive work uses train + development only. The sealed partition stays sealed
  until one `--final-test` run, after the mandatory dry-run.
- Gate 1 records the prepared-data SHA-256 and the split-policy fingerprint; every
  run prints back the realized `split_fingerprint`.

## Research questions and priors (mirrored from study.yaml)

- **RQ1** — which of warmup / weight tying / dropout / width clears the measured
  floor at 2000 steps, and which is indistinguishable from a re-seed?
  Prior: at most one (width) clears it; warmup and tying land inside the floor;
  dropout costs. `(source: uninformed)`
- **RQ2** — does the verifier agree with the training script, and does the same
  checkpoint survive a device change? Prior: same-device agreement two or more orders
  of magnitude inside the 0.01-nat tolerance; a device change moves a full
  re-execution by less than one fit-noise standard deviation. `(source: scouted — S3)`
- **RQ3** — how large is the largest recipe effect against the seed spread: is this
  study measuring recipes or measuring noise? Prior: a small multiple, not an order of
  magnitude. `(source: uninformed)`

## Registered predictions (mirrored from study.yaml)

| id | Lever | Rule on the verifier's printed block | Pre-scripted branch |
|---|---|---|---|
| P1 | anchor at a sixth seed | `anchor_z <= 2` | supported → the anchor recipe is reproducible and the floor is usable as registered; refuted → the floor is re-measured with a larger k before any candidate is scored, on the record |
| P2 | linear LR warmup | `delta_in_floors >= 1` | supported → warmup joins the incumbent recipe; refuted → warmup is recorded as within-floor at this budget and not carried forward |
| P3 | weight tying | `abs(delta_in_floors) < 1` | supported → tying is a free parameter saving, recommended on that ground alone; refuted → the direction it moved is reported, and a within-floor claim is not made |
| P4 | dropout 0.1 | `delta_in_floors <= -1` | supported → dropout is recorded as a cost at this budget; refuted → the doctrine prior is wrong here and findings say so in §③ |
| P5 | width 128 → 256 | `delta_in_floors >= 1` | supported → width is the candidate for confirmation; refuted → capacity is not the binding constraint at 2000 steps, which is itself the headline |
| P6 | sealed final tenth | `abs(sealed_gap_in_fit_noise) <= 2` | supported → the development number generalizes to unseen text at the same scale; refuted → the gap is reported as a partition effect, and the claim's strength stays exploratory |

## Workflow

1. `uv run --locked klein gate record consult --study . --acknowledged-by lead-agent`
2. Prepare data and write a `Decision: GO` data card; record the DATA gate.
3. Write the method card and the verifier; record the METHOD gate (it hashes
   `verify.py`).
4. Run the two Phase-0 measurement sweeps, register them, set `minimum_delta` and the
   `fit_noise` / `noise_floor` / `bound` blocks through a consult RE-RECORD with a
   reason, then `uv run --locked klein preflight --study .`.
5. Edit `model.py` / `train.py` with ONE idea, then
   `uv run --locked klein run-one --study . --track primary --tests P# --description ...`.

Every candidate is committed before execution. Discards and crashes remain resolvable
commits; the evidence transaction then restores the mutable surface to the
pre-candidate base commit.

## Decisions (append-only)

- 2026-09-03 — study scaffolded with `klein new` (schema 3, `predict` · `text` ·
  `ml-research`); contract drafted; gates pending.
- 2026-09-03 — **Decision: the keep bar will come from a PAIRED floor, not from the
  5-seed level spread.** The brief asked for a `seed-sweep` floor with estimand
  `fit-noise`; the engine records that estimand under `fit_noise:` and deliberately
  emits no `minimum_delta` line for it, because a seed-only spread measures how much
  the FIT moves, not how much a COMPARISON moves
  (`kleinlib/noise_floor.py:block_key`, consult protocol "Real data has more than one
  floor"). The protocol wins over the brief. Phase 0 therefore runs the 5-seed sweep
  the brief asked for AND derives, from the same five checkpoints, the ten paired
  differences between seed pairs re-scored on identical validation windows — a
  `paired-comparison` estimand. `fit_noise` is recorded as provenance; the paired
  spread sets `minimum_delta`. A `split-lottery` floor was retired before the gate
  (scouting ledger, Retirements): this study never re-draws its split.
- 2026-09-03 — **Decision: the verifier tolerance is a fixed 0.01 nats, declared
  a priori, not `2 × fit_noise`.** The brief suggested scaling it to the fit noise;
  the two numbers the tolerance compares are the SAME deterministic full-coverage
  cross-entropy computed twice from the same checkpoint, so the drift it must survive
  is float and device arithmetic (~1e-6 nats), not fit variance. A fit-noise-sized
  tolerance would be roughly a hundred times too loose and would let a checkpoint
  saved at the wrong step pass. 0.01 nats is fixed before any floor and never moved;
  the observed disagreement is reported in findings.
- 2026-09-03 — **Decision: the mutable surface is `[model.py, train.py]` and the
  architecture family is fixed by the verifier.** `verify.py` carries its own
  implementation of the family and loads the checkpoint with `strict=True`, so a
  candidate that leaves the family produces an artifact the checker cannot score —
  a crash, and honest evidence. Recipe knobs (warmup, tying, dropout, width, seed)
  all stay inside the family by construction.

- 2026-09-03 — **Decision: two harness-control EXPECTATIONS were corrected before the
  DATA gate, not the numbers.** The first run of `sweeps/harness_controls.py` reported
  FAIL twice: `uniform` at 4.174388 against a 1e-6 tolerance on ln 65 (float32 logits
  summed over 111k characters reproduce the constant to about 1e-6, so the tolerance
  was wrong, not the harness) and `untrained_network` at 4.305432 against an
  "within 0.05 of chance" expectation that rested on a wrong theory — a randomly
  initialized network is not a uniform predictor, and its unnormalized head makes it
  slightly WORSE than chance, which is the honest expectation and a stronger control.
  Both expectations were rewritten and the sweep re-run; no measured value changed and
  no prediction was involved. The sweep was registered afterwards, so the registered
  sidecar is the corrected run.
- 2026-09-03 — **Decision: the DATA gate was re-recorded to correct one transcription
  on the card.** The card quoted `sha256(prepared.csv)` under the heading "fingerprints
  frozen at this gate"; the engine actually freezes a name-salted `fingerprint_path`
  digest. Both numbers are now on the card, each labelled for what it is. No run
  exists, no partition or policy changed, and the split fingerprints are byte-identical
  across the two records.

- 2026-09-03 — **Phase 0 measured.** `sweep:fit_noise` (5 seeds, the anchor recipe,
  identical partition): mean 1.56915 nats, std 0.00802952, range 0.021485.
  `sweep:paired_floor` (the ten unordered pairs of those five checkpoints, re-scored on
  identical validation windows): std 0.00747623, range 0.026494 →
  **`minimum_delta` = 0.0149525 nats**. Two things worth recording. (a) Re-scoring a
  saved checkpoint is exactly deterministic here — every paired difference equals the
  difference of the two `fit_noise` values to the last printed digit — so the paired
  spread is a spread of TRAINING outcomes, not of measurement. (b) The paired mean is
  −0.0088684 rather than 0 because the five seeds happen to order with their index and
  the sign convention is i < j; only `std` and `range` enter the bar and both are
  translation-invariant.
- 2026-09-03 — **Decision: `metric.bound.ideal` is declared at 0.0 and disclosed as
  loose.** A cross-entropy in nats cannot go below zero, so the bound is true, but
  natural English has positive entropy and nothing reaches it. h at the anchor is about
  105 floors. The bound is declared so the headroom disclosure runs and so findings can
  say plainly that the detection-limit law does no work in this study — `h >= 1` here
  means only "not arithmetically excluded", exactly as the SKILL warns.
- 2026-09-03 — **Note on the verifier tolerance now that the floor exists.** The brief
  suggested `2 x fit_noise`; that would be 0.0161 nats. The a-priori 0.01 nats declared
  at CONSULT is TIGHTER, so the check is strictly stricter than the brief asked for,
  and it was fixed before any of these numbers were known.
- 2026-09-03 — **Note on the design-time anchor values.** The scouting ledger's S3 runs
  reported 1.567907 / 1.553969 / 1.567601 for seeds 1-3 with a throwaway script; the
  registered sweep reports 1.564806 / 1.559798 / 1.568690 for the same seeds through
  the study's own code. The two agree in level and spread but not digit-for-digit,
  which is why S3 was disclosed as provenance and never as evidence. Whether the
  residual is implementation or device nondeterminism is exactly what `klein replicate
  E0001` is instrumented to answer (RQ2).

- 2026-09-03 — **Decision: the phase ids were aligned with the ladder the machine
  recorded, not the other way round.** `klein new` writes
  `study_state.json:current_phase` from the TEMPLATE's phase ids at scaffold time —
  before the consult protocol tells you to author your own phases — so a study that
  renames them leaves the state pointing at a phase the contract no longer declares,
  and `klein preflight` refuses with "amend the contract to match the recorded state".
  That refusal is the guard doing its job for a study with runs. Here there are no runs
  and no phase acknowledgements, so the cheapest honest fix is the one the engine
  prescribes: the ladder is now `adaptive-1` / `adaptive-2` / `confirmation`, keeping
  this study's own descriptions and budgets. Nothing else changed — no budget, no
  prediction, no rule. (Reported to the lead as an engine papercut: `current_phase`
  could be re-derived from the contract while no run and no phase acknowledgement
  exists, the same doctrine the DATA gate already uses for fingerprints. Not patched
  here: it changes shared state handling and this study is not the place to guess.)

## Phase slates

At every phase start, run the slate ritual (references/phase-ritual.md):
propose 4-6 falsifiable candidates, score novelty / testability / expected
information 1-3, record the table and the chosen candidate here, and mirror
the ranked survivors into playbook.md "Next-best candidates".

### Phase adaptive-1 slate

Phase `adaptive-1` has `max_experiments: 1` and one pre-registered job — the identity
anchor — so the slate is a record of what else was weighed for that single slot, not a
tournament. Re-read `playbook.md` first: it is empty of ruled-out directions, because
nothing has run.

| # | Candidate (one hypothesis, one transaction) | Nov | Test | Info | Σ |
|---|---|---|---|---|---|
| 1 | The anchor recipe at seed 20260903 — a seed the floor sweep never used: `anchor_z <= 2`, i.e. the recipe reproduces within the measured fit noise | 3 | 3 | 3 | 9 |
| 2 | The anchor recipe at seed 5 — one of the floor's own seeds; would reproduce 1.58128 exactly if the pipeline is deterministic | 2 | 3 | 2 | 7 |
| 3 | An untrained (0-step) checkpoint through the entrypoint as a live negative control | 2 | 1 | 2 | 5 |
| 4 | The anchor at 200 steps, to price the budget's marginal value before spending the phase | 3 | 1 | 2 | 6 |
| 5 | The anchor with a fixed batch order instead of sampled offsets | 2 | 3 | 1 | 6 |

Chosen: **#1** — it is the only candidate that adjudicates P1 as registered, and it
answers the question the floor cannot answer about itself: whether a sixth,
never-swept seed lands inside the spread the first five described. #2 scores lower on
information because a within-sweep seed tests determinism, which the paired sweep
already showed (every paired difference equalled the difference of the two recorded
losses to the last digit). #3 is already covered off-ledger by `sweep:harness_controls`
and would spend the phase's only slot on a control that has passed. #4 and #5 are
testable but decide nothing registered; #5 stays in the playbook's queue as the
cheapest way to ask whether the sampled-offset stream contributes to the floor.

E0001 is run with `--allow-rerun`: the anchor configuration is exactly what the METHOD
gate committed, so its candidate diff is empty by construction. That is the sanctioned
flag for an intentional identical execution of a committed configuration, and it is
what an identity anchor is.

### Phase adaptive-1 summary (for the boundary acknowledgement)

- **Floor.** `sweep:fit_noise` (k = 5, the anchor recipe, seeds 1–5): mean 1.56915
  nats, std 0.00802952, range 0.021485 — recorded as provenance.
  `sweep:paired_floor` (k = 10, the ten unordered pairs re-scored on identical
  windows): std 0.00747623, range 0.026494 → `minimum_delta` = 0.0149525 nats.
- **Anchor.** E0001, the same recipe at seed 20260903, `keep` at val_loss = 1.572174
  nats (2.268167 bits/char), `steps` 2000 and `eval_context` 128 read by the checker
  out of the checkpoint. `anchor_z` = 0.3766 → **P1 supported**. The searcher and the
  checker agreed to `verifier_gap` = 0.00000000 from two independent implementations
  of both the model and the loss sweep.
- **Reproduction.** `rep:E0001@20260903T121129Z` — a full re-execution in a detached
  worktree at the candidate commit: **reproduced**, primary-metric difference 0.000962
  nats against a 0.0149525 tolerance. Same seed, same device, different process: MPS
  training is not bit-deterministic, and the residual is about an eighth of the
  fit-noise standard deviation. Two `verify:E0001@…` records re-score the pinned
  checkpoint with difference 0.
- **Device.** `sweep:device_check` runs the checker on E0001's checkpoint (sha256
  f1408df06f0a…, the hash the manifest pinned) under `KLEIN_DEVICE=cpu` and
  `KLEIN_DEVICE=mps`: both print 1.572174 nats, agreeing to the printed 1e-6
  resolution. The replication record's environment fingerprint does not carry the
  torch device, which is why this needed its own registered instrument.
- **Headroom.** `h = (1.572174 - 0) / 0.0149525 ≈ 105` floors. The bound is the
  information-theoretic zero of a cross-entropy and is unreachable, so this says only
  "a keep is not arithmetically excluded". The detection-limit law does no work here
  and findings will say so.
- **Budget.** 1 of 1 experiments used; the phase's registered job is done.

### Phase adaptive-2 slate

Playbook re-read first. Ruled out before this phase: a split-lottery floor and sampled
validation batches (both retired pre-gate). Open hypotheses H1–H4 map one-to-one onto
the four registered levers, and H3 is live AGAINST the registered P4.

| # | Candidate (one hypothesis, one transaction) | Nov | Test | Info | Σ |
|---|---|---|---|---|---|
| 1 | 200-step linear LR warmup: `delta_in_floors >= 1` (adjudicates **P2**, tests H2) | 3 | 3 | 3 | 9 |
| 2 | Weight tying, head shares `tok_emb`: `abs(delta_in_floors) < 1` (adjudicates **P3**, tests H4) | 3 | 3 | 3 | 9 |
| 3 | Dropout 0.1: `delta_in_floors <= -1` (adjudicates **P4**, tests H3 against the registered prior) | 3 | 3 | 3 | 9 |
| 4 | Width 128 → 256: `delta_in_floors >= 1` (adjudicates **P5**, tests H1) | 3 | 3 | 3 | 9 |
| 5 | Cosine LR decay to 10% of peak over the 2000 steps: expected −0.02 nats, an untouched lever with no registered prediction | 3 | 3 | 2 | 8 |
| 6 | Batch 32 → 64 at the same 2000 steps: doubles the tokens seen while holding the STEP budget — the honest probe of what a step budget actually holds fixed | 3 | 3 | 2 | 8 |

All four registered candidates tie at 9 because each decides a pre-registered
prediction either way; the tie-break is expected information, and it is genuinely equal
— so they run in the contract's order (#1 → #4), and the phase's sixth slot goes to
whichever of #5 / #6 the first four make most informative. #5 and #6 are mirrored into
the playbook's queue.

Chosen first: **#1**, warmup — `xiong2020` says a Pre-LN stack should not need it, so a
refutation confirms the doctrine cheaply and a support would say the constant 3e-3 is
too aggressive early, which would change the anchor recipe for everything after.

### Phase adaptive-2 log

- 2026-09-03 — **E0002 (200-step linear warmup) — discard, val_loss 1.584747,
  `delta_in_floors` = −1.0431. Decision: P2 is REFUTED and warmup is not carried
  forward.** The registered rule was `delta_in_floors >= 1`; the run landed a full
  floor on the WRONG side, so warmup did not merely fail to help at this budget — it
  cost more than the measured floor. The pre-scripted branch said "refuted → warmup is
  recorded as within-floor at this budget and not carried forward"; the observed
  direction is stronger than that branch anticipated, so the record is corrected here:
  warmup is recorded as a measured COST, not as within-floor. The anchor's constant
  3e-3 schedule stands as the incumbent recipe for every later candidate. Reading:
  `xiong2020` says a Pre-LN stack does not need warmup to be stable; this adds that
  when the budget is 2000 steps, the ~200 steps spent below the target learning rate
  are steps not spent learning, and the model does not get them back.
- 2026-09-03 — **E0003 (weight tying) — discard, val_loss 1.739149,
  `delta_in_floors` = −11.3693, `anchor_z` = 21.17. Decision: P3 is REFUTED and tying
  is not carried forward.** The registered rule was `abs(delta_in_floors) < 1` — "tying
  is free" — and the run missed it by an order of magnitude in the losing direction.
  This is the largest single effect measured anywhere in the study, and it is a cost.
  The pre-scripted branch said "refuted → the direction it moved is reported, and a
  within-floor claim is not made"; that is what happens. Reading: the parameter
  arithmetic on the method card (8,320 of 824,320, 1.0%) predicted the change would be
  invisible, and it was wrong about WHY the term matters. `press2017`'s mechanism is
  about sharing a large, sparsely-updated embedding table; here the table is tiny and
  densely updated, and forcing one 65×128 matrix to be both the input lookup and the
  output classifier — with no logit scaling to reconcile the two very different norms
  they want — removes a degree of freedom the model was using. A widely-repeated "free
  win" is not free at this scale, and a study that had only read the paper would have
  shipped it.
