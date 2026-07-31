# 04 — freMTPL2 claim frequency: GLM vs GBDT under an honest floor

**The real-data soak exhibit.** The first study on full-scale real data (678k
French Motor TPL policies) under the v0.3 contract — run deliberately as a
newcomer walk of the whole lifecycle, logging every friction; those frictions
became the v0.4.0 release (`docs/reviews/2026-07-31-v0.3-soak.md`). Every
candidate commit resolves in this repository.

The question: does a gradient-boosted tree beat a spline-shaped Poisson GLM at
claim frequency — by more than an honestly measured noise floor?

## The ledger at a glance

| Exp | Config | val_poisson_deviance (dev) | Disposition |
|---|---|---|---|
| E0001 | Poisson GLM, OHE (anchor) | 0.454861 | keep — null-deviance reference cell reproduced to 1e-9 |
| E0002 | GLM + log-density + splines | 0.453073 | keep — **by 0.000002 over the floor**; closed only 18% of the gap |
| E0003 | **HGBT (Poisson loss), OHE** | **0.444689** | **keep** — Δ 0.010172 = 11.4 paired SEs |
| E0004 | HGBT, native categoricals | 0.445343 | discard — 0.37× floor from OHE: the predicted tie |
| E0005 | (accidental empty diff) | 0.444689 | discard — bit-identical rerun of E0003; determinism proven by mistake |
| E0006 | incumbent, sealed test | 0.449667 | sealed confirmation — level replicates (0.65× fold SE) |

**The floor is three floors** — the study's methodological headline: fit-seed
std 0.000210 (k=5), paired-difference bootstrap SE 0.000893, marginal fold SE
0.005391 — a 25× spread. Under the naive marginal floor the headline gap looks
borderline; under the correct **paired** floor (same dev rows, per-row
difference resampling) it is 11.4 SEs. `minimum_delta = 0.001786` (= 2× the
paired SE). The incumbent's LEVEL is confirmed by the sealed run; the
GLM-vs-GBDT GAP is exploratory-by-construction (one sealed access per track —
the v0.4.0 consult protocol now makes that choice explicit up front).

The DATA gate earned its keep pre-loop: the raw hub table ships a `Frequency`
column (the answer key) plus four more derived columns — the allowlist +
clean-room audit is where that leak died.

Full verdicts with citable claim IDs (`04-fremtpl2-frequency#C1…C7`):
[`findings.md`](findings.md). The teaching write-up:
[`report/index.html`](report/) (self-contained, opens from `file://`). An
underwriting-ready eval card built from this study's incumbent:
[`docs/integrations/pricing-eval-example/`](../../docs/integrations/pricing-eval-example/).

## Reproduce

Data comes from a local data hub (not bundled — 678k rows):

```bash
export DATA_HUB=~/data_hub          # any hub exposing loaders/python/hub.py
uv run --no-sync python prepare.py  # writes data/prepared/ + the reference cell
KLEIN_SMOKE=1 uv run --no-sync python train.py   # sanctioned smoke re-run of the
                                                 # committed incumbent (E0003 config)
```

Historical note: this study predates the registry's deviance metrics (its own
soak friction F1), so its frozen contract declares `task_type: simulation` with
the exposure-weighted Poisson deviance computed in `pipeline.py`. As of v0.4.0
a new study writes `task_type: regression` with
`metric.name: val_poisson_deviance` and gets the same arithmetic from
`kleinlib.eval` — plus a leakage audit that runs on this study's shape as-is.
