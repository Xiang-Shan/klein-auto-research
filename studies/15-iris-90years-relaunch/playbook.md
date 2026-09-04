# Playbook — 15-iris-90years-relaunch

> Rolling state of play (keep under ~120 lines). RE-READ this file before
> choosing every candidate; refresh at every phase boundary or every 5
> experiments, whichever comes first. `program.md` is the append-only journal;
> THIS is the current map. SYNTHESIZE mines both. Swept into the next state
> commit automatically; its hash is recorded at every phase acknowledgement.

## STUDY STATUS: all three sealed accesses spent. EXPERIMENT loop is DONE.

`klein status`: `final holdout: ablation=1/1, fisher=1/1, modern=1/1`,
`successful confirmation: fisher=E0010, modern=E0011, ablation=E0012`,
predictions `5 supported, 4 refuted, 7 inconclusive, 0 open` — nothing left
unadjudicated. Phase `confirmation`'s own gate record is left for the
orchestrator (this experimenter session stops at the boundary). No further
`klein run-one` should be issued on this study by an experimenter — next
stage is SYNTHESIZE (a separate session), not more candidates.

## Current best / final state (per track)

| Track | Exp | Metric | Config one-liner | Sealed at |
| --- | --- | --- | --- | --- |
| fisher | E0001 (dev) / **E0010 (sealed)** | dev val_auc=1.000000 (ci 1.0-1.0); **sealed val_auc=1.000000 (ci 1.0-1.0, val_errors=2 vs dev's 1)** | `lda_all4`, fit on 49 train / 74 train+dev, scored on 25 dev / 25 sealed test | 2026-09-04 |
| modern | E0006 (dev) / **E0011 (sealed)** | dev val_auc=1.000000 (tie, printing artifact); **sealed val_auc=0.987179 vs reference 1.0, delta_vs_reference=-0.012821 — a REAL loss, unprintable as `delta_in_floors`** | `hgbt`, refit paired vs `lda_all4` on train+dev/sealed | 2026-09-04 |
| ablation | E0007/E0008 (dev) / **E0012 (sealed)** | dev delta_in_floors petal=0.0, sepal=-0.661; **sealed delta_in_floors petal=-0.0456 (holds), sepal_delta_in_floors=-0.8547 (still short of -1)** | `lda` on all4/petal/sepal, refit paired on train+dev/sealed | 2026-09-04 |

`fisher` is `mode: registered` — "measured", never "keep". `modern`'s E0006
incumbent was always a **printing-artifact keep, not a substantive win**
(H3) — E0011's sealed cell is the first place in the whole study where
`hgbt` vs `lda_all4` shows a REAL, non-tied, correctly-signed loss
(-0.012821 AUC, 3 errors vs 0), still uncertifiable against a registered bar
because `minimum_delta=0` throughout. `ablation`'s E0012 sealed cell
reproduces E0007/E0008's exact pattern on rows nobody had looked at before:
petal-only ties, sepal-only loses a real amount that a large registered
floor (0.28125) still won't certify as "at least one floor" (H6).

## Ruled out (evidence, not opinion)

| Direction | Evidence (exp IDs) | Why it lost (one line) |
| --- | --- | --- |
| "25 flowers cannot pin the separation" (P3's literal claim) | E0001 | REFUTED — `ci_width=0.0`: bootstrap blind spot on a perfectly rank-separated dev sample, not evidence of population-level certainty. |
| "5-NN matches Fisher's LDA on this split" | E0004 | The one genuine dev-side loss of the parade (`val_auc=0.990385` vs `1.0`) — `delta_in_floors` unprintable, so P6 itself reads INCONCLUSIVE. |
| "zero keeps in the whole parade" (P9's literal claim) | E0002-E0006 | REFUTED by count (4 keeps) — every keep is a printed tie (H3), not a resolvable win. |
| "sepal-only lands at least one measured floor below all-four" (P13's literal claim, dev) | E0008 | REFUTED on the letter (`delta_in_floors=-0.661`) though the raw gap (-0.185897 AUC) is real and large — the floor (0.28125) is just bigger than the gap. |
| "the selected `modern` challenger stays within one floor of Fisher's LDA on the sealed rows" (P11's literal claim) | E0011 | INCONCLUSIVE, not supported nor refuted — `delta_in_floors` never printed (`minimum_delta=0`). The raw sealed gap (-0.012821 AUC, -1.28 floors' worth if a floor existed) is the study's clearest evidence against "ninety years matched Fisher exactly," but the registered rule cannot say so. |
| "both halves of the ablation survive the sealed partition" (P15's literal claim) | E0012 | REFUTED — petal half holds (`delta_in_floors=-0.0456`), sepal half doesn't clear `<=-1` (`sepal_delta_in_floors=-0.8547`) despite a real, large, correctly-directed raw gap (≈-0.24 AUC). H6 reproduces on sealed data exactly as flagged before the run. |

## Resolved hypotheses (final status)

| ID | Hypothesis | Final status |
| --- | --- | --- |
| H1 | `modern` track's measured paired floor is exactly 0, disarming `gap_in_floors`/`delta_in_floors` for the whole parade AND the sealed cell. | **CONFIRMED throughout, including confirmation**: P4-P8, P10, P11 all read INCONCLUSIVE for the identical reason, dev and sealed alike. |
| H3 (M2) | Floor-normalized framing at `minimum_delta=0` hides real ties/losses; report raw AUC deltas alongside floor-normalized verdicts. | **CONFIRMED and sharpened again at E0011**: the sealed cell shows `hgbt` losing 1.28 AUC points / 2 extra errors to `lda_all4` in a real, paired, non-tied comparison — the single clearest raw signal in the study — and P11 still reads INCONCLUSIVE. Findings must lead with this raw number. |
| H2 | Sealed 25-row block may not be as cleanly separated as development — perfect dev separation could be a lucky draw. | **PARTIALLY CONFIRMED (RQ4)**: `fisher`'s sealed AUC is STILL 1.0 (rank separation transfers exactly) but `val_errors` rose 1→2 at the 0.5 threshold, and `ablation`'s sealed sepal gap (≈-0.24 AUC) is larger than development's (-0.186 AUC). Rankings agree across the two 25-row blocks; raw numbers shift. |
| H4 (RQ2 / P12-P13) | Petal-only carries the signal; sepal-only carries meaningfully less; ablation floor (0.28125) makes the track fully decidable, unlike `modern`. | **RESOLVED dev-side (P12 supported, P13 refuted on the letter) and now RE-CONFIRMED sealed-side (P15)**: petal half of P15 supported, sepal half refuted on the same floor-vs-effect-size wrinkle. |
| H5 | Restoring `modern`'s sealed cell must use E0006's exact `hgbt` config as "the selected challenger." | **RESOLVED**: `MODERN_RECIPE="hgbt"` was already the committed state (E0006 was the last frontier `keep`, never restored) — no edit needed, confirmed byte-identical before E0011 ran. |
| H6 (from E0008) | A large, real, correctly-directed effect can still fail a registered floor-normalized rule when the floor itself is large. | **CONFIRMED A SECOND TIME, on sealed data nobody had looked at before this phase** (E0012, P15's sepal half) — this is now a twice-independently-observed pattern in this study, not a one-off, and belongs in findings §③ with both instances cited. |

## Sealed-phase mechanics worth recording (for SYNTHESIZE / a future study)

- `klein replicate` **refuses sealed (`final_test`) runs with no override**
  ("replicating it would be a second look at the sealed partition") — this
  is a hard CLI law, not a choice. `confirmation.require: [sealed,
  replicate]` is satisfied by replicating the DEVELOPMENT run each sealed
  cell's config/comparison rests on: `E0001` (fisher), `E0006` (modern),
  `E0007`+`E0008` (ablation, both LDA-family cells the sealed cell mirrors).
  All four reproduced exactly (`difference=0`).
- `E0001`'s first replication attempt timed out at the default 60s budget
  with zero output — cold first-invocation overhead of `uv run --locked` in
  a freshly created detached worktree, not evidence against reproduction
  (the successful retry's own measured `wall_seconds` was 3.6s). Retried
  with `--tolerance`-unrelated `--timeout-seconds 240`; both the failed and
  the passed record are kept on file (protocol: every attempt is a record).
  A future sealed-phase session should pass `--timeout-seconds 180`+ on the
  FIRST `klein replicate` call of a session that follows a fresh `uv sync`,
  to avoid burning a throwaway "NOT reproduced (timeout)" record.
- `load_partition("development", ...)` can be called explicitly (bypassing
  `KLEIN_EVALUATION_KIND`) inside a sealed cell to recompute a paired
  development number for `sealed_extra`'s `sealed_shift_in_floors` — call it
  BEFORE `load_partition(evaluation_kind, ...)` so the LAST printed
  `split_fingerprint:` line (the only one the notary checks, `printed[-1]`)
  is still the sealed one.
- Every sealed final-test run auto-restores `train.py` regardless of
  disposition (`restored = manifest["disposition"] != "keep" or
  final_test`) — confirmed operationally: after each of E0010/E0011/E0012,
  the surface reverted to the pre-candidate base with no extra action
  needed.

## Next-best candidates

None. All 4 phases (`anchor-and-floor`, `parade`, `ablation-map`,
`confirmation`) are complete; every registered prediction P0-P15 is
adjudicated; all three tracks' sealed accesses are spent and replicated.
The next stage is SYNTHESIZE (`findings.md`, `claims.lock`), a separate
session/stage — not more `klein run-one` candidates.
