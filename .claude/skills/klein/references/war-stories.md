# War stories — why the guards exist

Five failures — four from the ancestor campaign, one earned live by study 01 — each of
which cost real time and each of which hardened into a guard you now inherit for free.
Read them once; they explain rules that otherwise look like paranoia.

## 1. The string-dtype boolean (→ value-pattern check)

**What happened.** The insurance dataset had ~19 `is_*` columns holding `"Yes"`/`"No"`.
They arrived as pandas *string* dtype. Preprocessing keyed categorical handling on
`dtype == "object"` — string-dtype is not object-dtype, so those columns were silently
skipped: never encoded, fed to models raw or dropped. Every metric for the first stretch
of the campaign was quietly wrong. Finding and fixing it cost ~2 hours and retroactively
invalidated comparisons made before the fix.

**The guard.** Never trust `dtype`. The DATA gate's mandatory value-pattern check
inspects ACTUAL values for every column — string-encoded booleans, numbers-in-strings,
sentinels — and prepare.py fixes encodings deterministically. See
`data-gate-protocol.md`.

## 2. The MPS prediction collapse (→ index-shuffle batching + min_proba_std)

**What happened.** A torch model on Apple MPS used the obvious `DataLoader` +
`TensorDataset`. On MPS this silently collapsed the validation predictions to a near
constant — every row got almost the same probability. The AUC looked plausibly mediocre,
so it read as "the model just isn't good" rather than "the eval is broken."

**The guard.** Torch loops use MPS-safe INDEX-SHUFFLE batching (shuffle indices, slice
tensors — never a DataLoader on MPS), evaluate on CPU, and `kleinlib.eval` enforces a
`min_proba_std` hard guard that RAISES on collapsed predictions after the first val
batch. A collapsed run crashes loudly instead of lying quietly. See `kleinlib.torch_loop`
and `train.py`'s build_model hint.

## 3. The 4-vs-5-column schema drift (→ single-sourced schema)

**What happened.** Two documents described `results.tsv` — one said 4 columns, one said
5. The positional `printf` append wrote fields under the wrong columns; metrics landed in
the description, statuses in the commit field. The ledger corrupted silently and the
history became unrecoverable.

**The guard.** The schema lives in ONE place: `kleinlib/schema.py`. Templates, preflight,
summarize, and `new_study.py` POINT there or carry a fallback that is ASSERTED equal to
it at runtime. A drift-test fails loudly. No document restates the column list. See
`kleinlib.schema`.

## 4. Imbalance reweighting vs calibration (→ cw=None + isotonic)

**What happened.** On weak-signal insurance data (~6% positive), the reflex fix
`class_weight="balanced"` (and SMOTE/ADASYN) improved nothing on rank and RUINED
calibration — predicted probabilities no longer matched observed frequencies, which is
exactly what an actuary needs them to do.

**The guard.** Default to `class_weight=None` + isotonic calibration + threshold tuning
for weak-signal imbalanced targets. Resampling the TRAIN fold is allowed as an
experiment; resampling the val split is forbidden. Calibration is a first-class metric in
`aux_metrics.tsv`, weighed against rank in SYNTHESIZE — not an afterthought. See
`synthesis-protocol.md` (rank-vs-calibration tradeoff).

## 5. The dual-libomp SIGSEGV (→ two-stage process isolation)

**What happened.** Study 01 mixed torch (the DAE) and LightGBM (the head) in one
process on macOS arm64. The run died at `LGBMClassifier.fit` with SIGSEGV (exit 139),
no Python traceback, and an *empty* run.log — tee had masked the exit code and
block-buffered stdout died with the process. The armed `min_proba_std` guard never
fired: the failure was below Python. Cause: torch and lightgbm wheels each bundle their
own `libomp`; whichever framework engages OpenMP heavily SECOND segfaults the process.
Import order only moves the victim (lightgbm-first survived toy loads, then died inside
the full-scale torch stage).

**The detection recipe** (the three-step isolation diagnostic — run it whenever a
mixed-framework process dies with exit 139 and no traceback):
(A) run the GBDT alone in a torch-free process on cached inputs — if it passes, the
GBDT is innocent; (B) add one tiny torch op before the GBDT fit in the same process —
if it now dies, you have the dual-runtime clash; (C) flip the import order — if the
crash just moves to the other framework's heavy stage, it is confirmed: two OpenMP
runtimes, one process, no fix by ordering.

**The guard.** Two-stage process isolation INSIDE one train.py (the launcher pattern
SKILL.md sanctions): a torch-only child subprocess fits the net and dumps CPU-numpy
`.pkl` caches (never imports lightgbm); the parent imports lightgbm FIRST, loads the
caches, and runs the GBDT head (torch bound passively, never operated). Corollaries:
`set -o pipefail` on every tee'd run and `PYTHONUNBUFFERED=1`, or a hard crash eats
both the exit code and the log. Prove isolation preserved determinism with one
bit-exact rerun (study 01: E3 = sweep trial 2 = 0.668271). See
`studies/01-dae-claims/train.py` (`stage_*`/`main`) for the reference implementation.

## The meta-lesson

Every one of these failed SILENTLY — a wrong number that looked plausible, not a crash
(story 5 is the loud-but-mute variant: a crash below Python that erased its own
evidence).
That is the expensive kind. The guards all convert a silent lie into a loud failure:
inspect values (not dtypes), raise on collapsed preds, single-source the schema, weigh
calibration beside rank. When a guard fires, thank it — it just saved a campaign.
