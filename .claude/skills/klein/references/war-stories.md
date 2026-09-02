# War stories — why the guards exist

Nine failures — four from the ancestor campaign, one earned live by study 01, one by
study 05, one by study 07, and two by study 09 — each of which cost real time and each of which hardened into a guard you
now inherit for free. Read them once; they explain rules that otherwise look like
paranoia.

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

## 2. The MPS prediction collapse (→ streamed index-shuffle batching + diagnostics)

**What happened.** A torch model on Apple MPS used the obvious `DataLoader` +
`TensorDataset`. On MPS this silently collapsed the validation predictions to a near
constant — every row got almost the same probability. The AUC looked plausibly mediocre,
so it read as "the model just isn't good" rather than "the eval is broken."

**The guard.** Torch loops use MPS-safe streamed INDEX-SHUFFLE batching (shuffle
indices, slice only the current batch onto the accelerator), evaluate from a best state
kept on CPU, and `kleinlib.eval` rejects non-finite or near-constant prediction vectors
from their finite range and unique-value count. This avoids a brittle absolute standard-
deviation threshold while still making collapse loud. See `kleinlib.torch_loop` and
`kleinlib.eval`.

## 3. The 4-vs-5-column schema drift (→ single-sourced schema)

**What happened.** Two documents described `results.tsv` — one said 4 columns, one said
5. The positional `printf` append wrote fields under the wrong columns; metrics landed in
the description, statuses in the commit field. The ledger corrupted silently and the
history became unrecoverable.

**The guard.** The schema lives in ONE place: `kleinlib/schema.py`. Templates, preflight,
summarize, and `new_study.py` POINT there — they import it and fail loudly if the
engine is absent. A drift-test guards the round-trip. No document restates the column list. See
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
caches, and runs the GBDT head (torch bound passively, never operated). Run the launcher
through `klein run-one` (or `scripts/run_with_log.py` for v1): it enforces unbuffered
output, process-group timeout, and the real child exit status without a masking tee
pipeline. Prove isolation preserved determinism with one
bit-exact rerun (study 01: E3 = sweep trial 2 = 0.668271). Pattern: `main()`
dispatches each framework's fit into its own `stage_*` subprocess, so torch and
OpenMP never share a process (reference implementation: the archived study 01
`train.py`, tag v1.0.0).

## 6. The unprinted guardrail (→ wall_seconds prints + preflight visibility check)

**The failure.** Study 05's first run printed the anchor-exact metric (0.454861) and
was dispositioned `discard` anyway — "guardrail metric 'wall_seconds' missing". The
contract declared a `wall_seconds` guardrail; the evaluator wrote `wall_seconds` to
the aux sidecar but never PRINTED it, and the runner's guardrail arithmetic reads
the printed block only. A healthy candidate burned a real slot on a bookkeeping
mismatch — and study 06 avoided a repeat only because a human remembered the lesson.

**The guard.** Every evaluator now prints `wall_seconds:` itself (a caller that
already routes it through `extra=` keeps byte-identical output), and
`klein preflight` warns when any declared guardrail key is neither auto-printed nor
named anywhere in the study's Python sources. Declare guardrails on keys the run
will print.

## 7. The sub-zero keep bar (→ metric.bound + headroom disclosure + `klein headroom ack`)

**The failure.** Study 07 measured its floor honestly (split-lottery, k=20,
2×std → delta = 0.033) — against an anchor whose whole Brier was 0.026744. The
keep rule therefore demanded `challenger <= 0.026744 − 0.033 = −0.006256`, below
the metric's hard zero: every challenger in the parade was arithmetically dead
before it ran, and no check said so. The impossibility was found BY HAND between
rounds (the repo owner did the subtraction), a full study later. The figure
legend even printed "below zero: unreachable" — the prose never drew the
conclusion.

**The guard.** Declare `metric.bound.ideal` (0.0 for brier/logloss, 1.0 for AUC)
and klein computes headroom `h = (incumbent − ideal) / minimum_delta` wherever an
incumbent exists: disclosed at preflight/verify (`[WARN] ... NO keep is
arithmetically possible`), enforced at run-one — the default posture refuses
development transactions until `klein headroom ack` records the closed door with
a registered branch (`re-scope: ...` or `run-anyway: ...`, study-08 style). Two
wording clauses ride along: `h >= 1` is "not excluded", never "plausible"
(study 08: h = 1.015, twenty-one challengers, zero keeps), and the floor must
name its estimand (`marginal-resplit` | `paired-comparison`) — study 07's own
sidecar shows the paired spread EXCEEDING the marginal for five of six families,
so neither is "the sharp one" by default.

## 8. The hardcoded retired seed (→ contract-driven splits + printed split fingerprint)

**The failure.** Study 09's `train.py` line 78 hardcoded a split seed the contract had
retired (`20260909`; the contract said `20260912`). Every ledger-lane run measured the
wrong partition; the sweeps, which read the contract, were clean; the sealed
partition was untouched. Nothing in the engine noticed: `klein verify` checked the
CONTRACT's split policy, not the split the evaluator had actually used. The tutorial's
unsourced-numeral scan caught it — a number on the page had no home — a full study
later. Erratum E1 was filed on the ledger table; the numbers were re-scoped, never
deleted.

**The guard.** The split is produced by the contract, not by the entrypoint:
`kleinlib.data.contract_split(study_dir)` / `load_partition(kind)` read `study.yaml`,
every evaluator prints `split_fingerprint:`, and `run-one` compares it with the
fingerprint frozen at the DATA gate — a mismatch is a **crash** with a named reason,
because a number measured on the wrong partition is not evidence. Preflight warns
when no study source calls the helper, and the DATA gate treats a literal seed in an
evaluator as a BLOCKER. See `data-gate-protocol.md`.

## 9. The seal spent by a crash (→ the sealed dry-run)

**The failure.** Study 09's one sealed access per track was consumed by a
`RuntimeError` raised before a single row of sealed data had been read — a
group-aware coda entry that the development path had never exercised. By the law of
one look, the seal was spent (备而不用: prepared, and never used); the study closed
exploratory along its pre-registered Branch B. The law held; the study paid for a
bug with its only confirmation.

**The guard.** `klein run-one --final-test --dry-run` executes the sealed entrypoint
with `KLEIN_SEALED_DRYRUN=1`: the partition helper substitutes development data, the
child prints `sealed_dryrun: 1`, and nothing is spent — no id, no commit, no manifest,
no row, no seal. It is mandatory before every real sealed run (the experimenter
prompt refuses to proceed without its log). See `inquiry-model.md` on what "sealed"
means per kind.

## The meta-lesson

Every one of these failed SILENTLY — a wrong number that looked plausible, not a crash
(story 5 is the loud-but-mute variant: a crash below Python that erased its own
evidence; story 6 the plausible-but-wrong verdict: a healthy run scored discard by
bookkeeping; story 8 the wrong-partition number that looked exactly right; story 9
the crash that spent an irreplaceable look).
That is the expensive kind. The guards all convert a silent lie into a loud failure:
inspect values (not dtypes), raise on collapsed preds, single-source the schema, weigh
calibration beside rank. When a guard fires, thank it — it just saved a campaign.
