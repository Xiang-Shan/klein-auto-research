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

## Phase slates

At every phase start, run the slate ritual (references/phase-ritual.md):
propose 4-6 falsifiable candidates, score novelty / testability / expected
information 1-3, record the table and the chosen candidate here, and mirror
the ranked survivors into playbook.md "Next-best candidates".
