# Playbook — 15-iris-90years-relaunch

> Rolling state of play (keep under ~120 lines). RE-READ this file before
> choosing every candidate; refresh at every phase boundary or every 5
> experiments, whichever comes first. `program.md` is the append-only journal;
> THIS is the current map. SYNTHESIZE mines both. Swept into the next state
> commit automatically; its hash is recorded at every phase acknowledgement.

## Current best (per track)

| Track | Exp | Metric | Config one-liner | Held since |
| --- | --- | --- | --- | --- |
| fisher | E0001 | val_auc=1.000000 (ci 1.0-1.0, n_boot=2000) | `lda_all4`, fit on 49 train, scored on 25 dev | 2026-09-04 |
| modern | E0006 | val_auc=1.000000 (raw 0.9999999999999999), val_accuracy=1.0, val_errors=0 | `hgbt`, refit each cell paired vs `lda_all4` reference | 2026-09-04 |
| ablation | — | — | no run yet — Phase `ablation-map` | — |

`fisher` is `mode: registered` — "measured", never "keep"; there is no frontier to
climb here, only a level to report and confirm sealed later. `modern`'s E0006
incumbent is a **printing-artifact keep, not a substantive win** — see the Decision
below; treat "the modern incumbent is hgbt" as a disposition-label fact, not as
"hgbt beat Fisher."

## Ruled out (evidence, not opinion)

| Direction | Evidence (exp IDs) | Why it lost (one line) |
| --- | --- | --- |
| "25 flowers cannot pin the separation" (P3's literal claim) | E0001 | REFUTED — `ci_width=0.0`: the dev sample is perfectly rank-separated, so the percentile bootstrap has no resampling variability to show (a bootstrap blind spot, not evidence the split is well-determined at the population level). |
| "5-NN matches Fisher's LDA on this split" | E0004 | The one genuine loss of the parade: `val_auc=0.990385` vs reference `1.0` — coarse score resolution on 25 rows (only 6 distinct KNN scores) costs a real 0.0096 AUC. `delta_in_floors` still unprintable (`minimum_delta=0`), so P6 itself reads INCONCLUSIVE, not supported — the direction is right, the registered rule cannot certify it. |
| "zero keeps in the whole parade" (P9's literal claim) | E0002-E0006, `klein predict adjudicate` | REFUTED by direct count (4 keeps, not 0) — but see the Decision below: every keep is a printed tie (`delta_vs_reference` 0.0 or -0.0), not a resolvable win. |

## Open hypotheses

| ID | Hypothesis | Prior | Status / cheapest next test |
| --- | --- | --- | --- |
| H1 | The `modern` track's measured paired floor is exactly 0, disarming `gap_in_floors`/`delta_in_floors` for the whole parade. | Measured (sweep:floor_modern). | **RESOLVED, as expected.** The user's explicit decision was to run the parade anyway; P4-P8 all read INCONCLUSIVE by their own `inconclusive_if`, exactly as anticipated. |
| H3 (M2) | Framing challengers' wins/losses in floor units is misleading at `minimum_delta=0`; report raw AUC deltas too. | New, prompted by H1. | **CONFIRMED, and sharper than expected**: it is not just that floor-normalized keys are missing — `choose_disposition`'s frontier arithmetic (`primary_metric >= old + 0`, read off the PRINTED 6-decimal block) turns a printed TIE into a `keep`. 4 of 5 `modern` cells (E0002, E0003, E0005, E0006) disposition `keep` while `delta_vs_reference` is `0.0`/`-0.0` on every one — zero challengers resolvably beat the incumbent. Findings must report both the disposition count (4 keeps) and the substantive count (0 resolvable wins). |
| H2 | Sealed 25-row block may NOT be as cleanly separated as train/development (P10, P11, RQ4) — the perfect dev-side separation could be a lucky draw. | Uninformed (per study.yaml). | Untouched this phase. The `fisher`/`modern`/`ablation` sealed cells, Phase `confirmation` — adaptive work never reads the sealed 25. |
| H4 (RQ2 / P12-P13) | Petal-only carries the signal; sepal-only carries meaningfully less. `floor_ablation`'s real, resolvable floor (0.28125) suggests the ablation track's comparisons ARE decidable, unlike `modern`. | Scouted/uninformed per study.yaml (both disclosed, unscored). | Untouched this phase — E0007/E0008 in Phase `ablation-map`. |
| H5 | Restoring the `modern` track's confirmation-phase sealed cell must use E0006's config (`hgbt`, the disposition incumbent) as "the selected challenger" per P10/P11's wording, even though H3 above says that "selection" is a printed tie, not a real win. | New, prompted by the parade's outcome. | Decide explicitly in the Phase `ablation-map`/`confirmation` slate ritual — do not let the sealed cell silently inherit E0006 without this caveat carried into findings. |

## Next-best candidates (ranked — mirror of the phase slate, see references/phase-ritual.md)

Phase `parade` ran its whole planned slate (E0002-E0006 + the manual P9 count) with
nothing deferred — see `program.md`'s "Phase parade slate". The next slate belongs to
Phase `ablation-map` (orchestrator to run the slate ritual at phase start):

1. E0007 (`ablation`): `lda_petal` vs `lda_all4` refit paired in the same cell → P12.
   Floor is real (0.28125) and resolvable, unlike `modern` — this is the first
   fully-decidable frontier comparison since E0001.
2. E0008 (`ablation`): `lda_sepal` vs `lda_all4` paired → P13, the sanity check that
   makes P12 informative.
3. E0009 (`ablation`): repeat the petal-vs-all4 comparison with the parade's
   "best" modern family → P14. Per H5 above, name explicitly in program.md which
   family is used and why, given the parade produced no resolvable ranking among
   the four keeps.
4. Phase `confirmation` slate (after ablation-map closes): three sealed cells, each
   `--final-test --dry-run` rehearsed first — `fisher` sealed level, `modern` sealed
   gap (P10/P11, config = E0006 per H5's caveat), `ablation` sealed (P15).
