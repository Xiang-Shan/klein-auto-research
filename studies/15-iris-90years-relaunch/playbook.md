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
| modern | — | — | no run yet — Phase `parade` seeds it with E0002 | — |
| ablation | — | — | no run yet — Phase `ablation-map` | — |

`fisher` is `mode: registered` — "measured", never "keep"; there is no frontier to
climb here, only a level to report and confirm sealed later.

## Ruled out (evidence, not opinion)

| Direction | Evidence (exp IDs) | Why it lost (one line) |
| --- | --- | --- |
| "25 flowers cannot pin the separation" (P3's literal claim) | E0001 | REFUTED — `ci_width=0.0`: the dev sample is perfectly rank-separated, so the percentile bootstrap has no resampling variability to show (a bootstrap blind spot, not evidence the split is well-determined at the population level). |

## Open hypotheses

| ID | Hypothesis | Prior | Cheapest next test |
| --- | --- | --- | --- |
| H1 | The `modern` track's measured paired floor (`lda_all4` vs `hgbt`) is exactly 0 (std=0, range=0 over 1000 reps) because both recipes achieve AUC≈1.0 on this dev block — same phenomenon as E0001/P3. | Measured (sweep:floor_modern), not yet acted on. | Phase `parade` must decide how to proceed before E0002: `h` will read `None` forever at `minimum_delta=0` (`track_headroom` short-circuits `<=0` to `None`), so P4/P5-P8/P10/P11 are structurally INCONCLUSIVE unless something changes. This is a phase-boundary decision, not a code fix. |
| H2 | Sealed 25-row block may NOT be as cleanly separated as train/development (P10, P11, RQ4) — the perfect dev-side separation could be a lucky draw. | Uninformed (per study.yaml). | The `fisher`/`modern`/`ablation` sealed cells, Phase `confirmation` — not before then; adaptive work never reads the sealed 25. |
| H3 (M2 from method_card.md) | The parade's best-minus-worst spread will be tight given `modern`'s measured floor is 0 — ANY nonzero measured spread among challengers would already exceed "0 floors" trivially, so `delta_in_floors` (if ever printed) would be enormous even for a tiny raw AUC gap. Framing challengers' wins/losses in floor units may be misleading here; report raw AUC deltas too. | New, prompted by H1. | Decide in Phase `parade`'s slate ritual alongside H1. |
| H4 (RQ2 / P12-P13) | Petal-only carries the signal; sepal-only carries meaningfully less. `floor_ablation`'s real, resolvable floor (0.28125) suggests the ablation track's comparisons ARE decidable, unlike `modern`. | Scouted/uninformed per study.yaml (both disclosed, unscored). | E0007/E0008 in Phase `ablation-map` — untouched this phase. |

## Next-best candidates (ranked — mirror of the phase slate, see references/phase-ritual.md)

Phase `anchor-and-floor` ran its whole planned slate (E0001 + 4 sweeps) with nothing
deferred — see `program.md`'s "Phase anchor-and-floor slate". The next slate belongs to
Phase `parade`, and per H1 above its first item is NOT a challenger run — it is
resolving how the `modern` track proceeds with `minimum_delta=0`:

1. **Resolve H1 before E0002**: with the modern-track floor measured at exactly 0,
   decide (with the orchestrator/user) whether to (a) accept that `gap_in_floors`/
   `delta_in_floors` will never print and treat P4-P8/P10-P11 as structurally
   inconclusive, reporting raw AUC deltas as the substantive evidence instead; (b)
   re-scope the prediction ledger via a disclosed erratum; or (c) some other
   documented path — NOT a silent code change to `lib/iris.py`'s zero-guard.
2. E0002 (`modern`): seed the frontier with `lda_all4` itself (the pre-scripted step
   research_plan.md names regardless of H1's resolution) — first real read of whether
   `primary_metric` matches E0001's 1.000000 to floating point (research_plan.md's own
   consistency check for the two tracks).
3. E0003-E0006: `logreg_l2`, `knn5`, `svm_rbf`, `hgbt` — each paired against `lda_all4`
   refit in the same cell (P5-P8). Given H1, expect every raw delta to be ~0 (all
   recipes already show AUC≈1.0 territory per `fit_noise`); the informative number may
   be the raw `delta_vs_reference`, not `delta_in_floors`.
4. E0007/E0008 (`ablation`): petal-only vs all-four (P12), sepal-only vs all-four
   (P13) — fully decidable, floor=0.28125, untouched by H1.
