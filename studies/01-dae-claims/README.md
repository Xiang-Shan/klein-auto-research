# 01 — Denoising autoencoder on insurance claims

**The "does deep learning pay on MY tabular data?" study.** Swap-noise denoising
autoencoder (Porto-Seguro/Jahrer style) representations vs. tuned gradient boosting
on 58,592 real claims records — 8 experiments, honest verdicts:

- **Headline (RQ1): the DAE does NOT pay for ranking here** — DAE→LGBM 0.6683 vs
  GBDT 0.6701 at this data size.
- **Surprise: a plain supervised MLP (0.6706) ties tuned GBDT** — a result the
  ancestor campaign never tested.
- **Second act: the DAE pays 3.4× over median-imputation at cell-level recovery**
  — representation learning helps *data repair* before it helps *ranking*.

Full verdicts with evidence experiment IDs: `findings.md`. Teaching write-up:
`report/index.html` (self-contained, open from `file://`).

## Running it

```bash
uv sync --locked --extra deep --extra gbdt  # torch + lightgbm — required here
uv run --locked python prepare.py            # prints "data source: bundled"
uv run --locked python bootstrap_caches.py   # rebuild ignored E3 caches + hash manifest
uv run --locked python ../../scripts/run_with_log.py --timeout-seconds 3600 \
  --log run.log -- uv run --locked python -u train.py
```

The bootstrap step is required on a fresh clone because model payloads are local,
trusted artifacts and are deliberately excluded from Git. It reconstructs the exact
E3 recipe needed by the committed E7 state and writes
`models/e3_cache_manifest.json` with data, lockfile, environment, and artifact hashes.
For a cheap structural smoke check, use a separate output directory with
`--device cpu --max-epochs 1 --limit-rows 500`; that mode does **not** claim the
reference metric.

Wall-clock is small (the whole ladder was ~minutes of compute, see
`aux_metrics.tsv` `wall_seconds`), but note two things:

- **Device-dependence:** experiments 2–8 ran on Apple-silicon MPS. The pipelines
  rerun end-to-end on any device (CUDA/CPU included), and the sklearn E1 anchor is
  guaranteed within ±0.001 anywhere — but exact regeneration of the *torch* rows
  is only expected on the reference MPS setup.
- **The libomp war story:** torch and LightGBM in one process SIGSEGV on macOS
  arm64 (dual bundled OpenMP). `train.py` uses two-stage process isolation — read
  it before "simplifying" it; details in
  `.claude/skills/klein/references/war-stories.md`.

## Note for cloners — provenance of hashes and anchors

Executed in the Klein development lab before this repo's public history began: the
`commit` column in `results.tsv` refers to the lab's git history (your own runs in
this clone write resolvable hashes). Baseline anchors (GBDT 0.6701, soft-vote
0.6715) come from the 215-experiment ancestor campaign, whose distilled findings
ship in `knowledge/`. Ledger, findings, and program notebook are immutable
exhibits — continue only via new experiments on an `experiments/…` branch.
