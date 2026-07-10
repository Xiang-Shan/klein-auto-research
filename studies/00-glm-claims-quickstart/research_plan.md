---
type: research-plan
domain: "insurance"
status: draft
concepts: []
related: []
---

# Research plan — 00-glm-claims-quickstart

> CONSULT (Gate 0) output. Human-readable companion to `study.yaml`. Drafted from the
> ≤6 interview answers; confirmed with the user before the DATA gate.
> Protocol: `.claude/skills/klein/references/consult-protocol.md`.

## The question

Does THIS framework (Klein Auto Research — prepare.py + kleinlib.data/eval/encoders +
the loop contract) reproduce the model-survey campaign's known-good anchors EXACTLY?
If yes, the framework is trustworthy for every later study built on it (01-dae-claims,
02-rqls-pv-severity). If no, something in the port (data.py split, encoders, eval
formulas) has drifted from the campaign and must be fixed before those studies run.

Decision this changes: whether we trust `kleinlib` enough to build 01/02 on it without
re-deriving every baseline from scratch. This is also the CI smoke study (bundled 2k
fixture) that keeps that trust continuously verified.

## Why now / why this method

- This is the fully-worked quickstart study of Klein Auto Research, and the
  framework's own dogfood proof (the first real study run end-to-end).
- LR (GLM) and sklearn's HistGradientBoostingClassifier are FAMILIAR methods here — no
  frontier pedagogy is needed; the honest prior is that a faithful port reproduces the
  campaign's numbers within the stated tolerances (the whole point of the split-identity
  gate is that this is checkable, not assumed).

## Data

- **Source:** `data_hub:insurance-claims` (kaggle litvinenko630/insurance-claims,
  Apache-2.0, 58,592 policies, ~6.4% claim rate). Already downloaded in data_hub
  (`datasets/insurance-claims/data/Insurance claims data.csv`) — no network needed for
  this run; `prepare.py --sample` exists for the committed CI fixture path.
- Known issues (from the campaign's war stories, re-verified by this study's own DATA
  gate): 17 `is_*` Yes/No columns read as non-numeric dtype (value-pattern hazard,
  handled via `kleinlib.data.detect_yes_no_columns`/`yes_no_to_int`, never a dtype
  check); `max_torque`/`max_power` are text specs ("113Nm@4400rpm") needing regex
  parsing; several engine-spec columns are near-deterministic functions of `model`.

## Method

- **Under study:** plain LogisticRegression (GLM family) as the split-identity anchor
  and calibration-doctrine smoke; sklearn `HistGradientBoostingClassifier` as the
  campaign's non-linear reference point (E3) that the LR recipes are measured against.
- Both are well-understood, familiar methods — `method_card.md` is a short study-local
  card pointing to `../../knowledge/method_cards/glm-pricing.md` for the full pedagogy,
  per the METHOD gate protocol's treatment of familiar (non-frontier) methods.

## Metric & decision use

- **Primary metric:** `val_auc` (higher is better) — rank-ordering quality, the
  contract every one of the campaign's 215 experiments optimized.
- Decision use: an actuary would use the ranking to prioritize underwriting review /
  triage; the aux `val_brier`/`val_logloss` sidecar metrics map to whether the raw
  probability is fit to use directly in a rate (calibration matters more than rank
  there) — this is exactly RQ2's calibration-doctrine question.

## Experiment ladder (sketch)

A rough ordered list — the loop ADAPTS, this is not a batch script. All four fit inside
Phase 0 (budget 1h; the whole study is Phase 0 by design — this is a quickstart, not a
multi-phase exploration).

1. E1 — split-identity anchor: campaign's exact Phase-0 LR (OHE min_freq=20,
   `class_weight=balanced`) — GATE: STOP everything if `|val_auc - 0.6255| > 0.001`.
2. E2 — campaign's winning Phase-1 LR recipe: splines(5 knots, deg 3) on
   subscription_length/vehicle_age/customer_age + log1p(region_density) + 2
   interaction terms + isotonic-calibrated `class_weight=balanced` LR → target 0.6528.
3. E3 — campaign's tuned Phase-0 HGBT: OHE + 7 deterministic-model-derivative column
   drops + shrinkage (lr=0.05, max_iter=500, early_stopping) → target 0.6629.
4. E4 — doctrine smoke: E1's exact config with `class_weight=None` + isotonic
   calibration instead of `balanced` — expect AUC within noise of E1 but a dramatically
   better (near-diagonal) reliability curve — the calibration-vs-rank tradeoff made
   concrete on the same anchor config.

## Budgets & stop rule

- Per-phase budgets in `study.yaml:phases` — one phase (id 0), budget_h 1, 1-4
  experiments. Stop rule: keep going until the user stops or the phase max is hit; here
  the natural stop is "all 4 anchors logged, gate passed."

## Deliverables

- `findings.md` (7-section synthesis) and `report/index.html` (tutorial) — ALWAYS.
- No additional study-specific docs planned; the always-on deliverables cover this
  quickstart's scope.

## Risks & unknowns

- **Non-reproduction risk (the whole point of E1):** if `kleinlib`'s ported split/
  encoders/eval differ from the campaign's `lib/` in any way (even a default kwarg),
  E1's AUC will miss 0.6255 — that is exactly the failure this study exists to catch
  before studies 01/02 build on the same library.
- **E2 reconstruction risk:** E2's exact recipe was never committed in the campaign
  (a `discard`-status experiment reverts `train.py`), so it is reconstructed from the
  campaign's `results.tsv` descriptions + `docs/insights_and_framework.md`, not
  `git show`'d verbatim like E1/E3. Tolerance is deliberately looser (±0.003, "STOP
  only if wildly off >0.01") to absorb this reconstruction uncertainty honestly.
- Would abandon/escalate if E1 misses gate by a wide margin — that means fixing
  `kleinlib` (out of this study's file scope) before any further study can trust it.

## Outcome (all 4 experiments run — see `program.md` log + `results.tsv` for detail)

Both risks named above materialized exactly as anticipated, which is itself the main
finding:

- **Non-reproduction risk did NOT materialize where the recipe was recoverable.** E1
  (0.625462, gate `|Δ|=0.000038`) and E3 (0.662897, `|Δ|=0.000003`) both reproduced the
  campaign to within noise — `kleinlib` is a faithful port, confirmed two independent
  ways (a GLM anchor and an HGBT anchor).
- **The E2 reconstruction risk DID materialize.** Despite assembling every documented
  recipe element (splines, log1p, interactions, isotonic calibration) and testing 7
  variants (knot count up to 50, regularization strength, column-drop and
  feature-restricted variants), the best reproducible ceiling found was ~0.641 —
  short of the target 0.6528, and outside the "wildly off >0.01" caution. This was not
  treated as a framework defect (E1/E3 already rule that out) but logged honestly as
  the irreducible cost of reconstructing a `discard`-status historical experiment from
  prose alone. The study proceeded rather than escalating, per the task's own softer
  tolerance language for E2 specifically (as opposed to E1's hard STOP-everything gate).
- Net verdict: the framework is trustworthy for studies 01/02 to build on (the thing
  this study exists to prove); the one shortfall is data about the campaign's own
  history, not about `kleinlib`.
