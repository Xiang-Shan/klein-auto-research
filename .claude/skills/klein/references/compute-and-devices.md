# Compute and devices — one bounded subprocess, on whatever you have

Klein does not schedule, parallelize, or learn; it notarizes. The unit of compute is
one foreground subprocess per run, and everything else — a laptop, a GPU, a cluster —
is arranged so that unit stays honest.

Role: the driving agent; `klein doctor` reports the environment.

## The unit

`klein run-one` launches the entrypoint unbuffered, in its own process group, with
`max_run_seconds` enforced by the notary (exit 124 on timeout), the real exit code
preserved, stdout streamed to the run log, and the environment fingerprint (python,
platform, device, lockfile hash) written to the manifest. A declared verifier is a
second such subprocess. No `| tee`, no daemon, no retry.

## Budgets: seconds for cheap runs, steps for long ones

A cheap run is budgeted in seconds (`max_run_seconds`, tightened after the anchor). A
long run — a network, a large simulation — is budgeted in **steps, tokens, or
evaluations** printed as a guardrail (`max_steps`, `n_evaluations`) so that two
machines agree within the floor; `wall_seconds` stays informational and
`max_run_seconds` is set generously as the runaway stop. Matched compute is a
scientific condition, not a convenience, and it is stated in units the hardware cannot
change.

## The environment variables that move a budget or a device

| Variable | Default | What it changes |
|---|---|---|
| `KLEIN_DEVICE` | auto (`mps` → `cuda` → `cpu`) | the device `pick_device()` returns |
| `KLEIN_REPLICATE_SETUP_SECONDS` | `1800` | the budget for `klein replicate`'s environment-setup step (`uv sync --locked …` in the detached worktree). Building a project is not the experiment, so it is never charged to `max_run_seconds` or `--timeout-seconds`. |
| `KLEIN_OFFLINE` | unset | `1` refuses every network data source before any request |

The child's own flags — `KLEIN_SMOKE`, `KLEIN_SEALED_DRYRUN`, `KLEIN_REPLICATION`,
`KLEIN_EXPERIMENT_ID`, `KLEIN_TRACK`, `KLEIN_EVALUATION_KIND` — are set by the notary,
not by you.

## Devices

`kleinlib.torch_device.pick_device()` chooses `mps` → `cuda` → `cpu`; `KLEIN_DEVICE`
overrides it. The device is in every manifest. Measure the floor on the device that
will run the study; expect CPU and accelerator results to differ within `fit_noise`,
and treat a larger gap as a finding to explain. Torch loops use streamed index-shuffle
batching (war story 2); torch and LightGBM never share a process (war story 5 — two
stages, one launcher).

## Clusters and remote compute

An entrypoint may be a blocking submit-and-wait wrapper: it submits the job, polls or
waits, then prints the canonical block when the job returns, pinning the job's own
logs and outputs as `artifact:` lines. The wrapper is the mutable surface's boundary
and the manifest records what it printed; Klein neither knows nor cares what ran
behind it. `max_run_seconds` bounds the wait. From a terminal this is still the
default and usually the right answer (`ssh host …`, `sbatch --wait`, `modal run` all
block).

**Detached runs (Klein 2.3, opt-in) — the one exception.** When the compute is driven
by a host the notary cannot spawn as a child — a Claude Science SSH/Slurm or Modal job
card, or a run that outlives the session driving it — declare
`entrypoint.execution: [local, detached]` and split the transaction in two:

1. `klein run-one --detach` runs every pre-run check, files the candidate commit, then a
   DETACH commit holding `runs/E####/job.json` (command, environment, seeds, timeout,
   the candidate commit and the sha256 of every mutable-surface file) and the
   `.klein-detached` sentinel. The study is now FROZEN: every other verb that would
   lock or commit refuses, so the ledger order stays the execution order.
2. The host checks out that commit and runs `klein job exec runs/E####/job.json`
   (`--executor here` in a dedicated clone; `--executor local` runs it in a throwaway
   worktree of this repository). It writes `job_result/` — the log, the usage record,
   every output file, and `receipt.json` with the job's sha256, the surface hashes it
   actually executed, the log and file hashes, the exit status and the hardware.
3. Copy `job_result/` back beside the job bundle and run `klein run-one --collect
   E####`: the receipt is checked against the committed job (a mismatch is refused),
   then the run is judged LOCALLY by the same code as a foreground run — partition
   check, declared verifier, disposition, predictions — and filed with
   `execution: {mode: detached, observed_by_notary: false, receipt_sha256, hardware}`.
   The referee weighs it as attested, not observed; `klein replicate` can re-run it
   locally at any time.

`klein run-one --abandon E#### --reason …` closes a detached run that will never come
back as a crash, on the record. `klein recover` never crashes a detached run.

## Seed arrays, budgets and usage (Klein 2.3)

`entrypoint.seeds: [0, 1, 2]` makes one candidate one seed array: the notary runs the
entrypoint once per seed (`KLEIN_SEED`), aggregates the blocks (mean, std, min, max)
and decides on the mean; `runs/E####/seeds.tsv` is pinned. A child may report usage
with `kleinlib.dl.report_usage(steps=…, tokens_in=…, usd=…)` (the call ledger does it
for model calls); `klein run-one` folds `runs/E####/usage.json` into the manifest for
every exit status, and `phases[].budget_steps` / `budget_tokens` / `budget_usd` are
enforced on those totals beside `budget_seconds`.

## Reproduction is a floor statement

Bitwise reproduction is not the bar; the floor is. `klein replicate` compares within a
tolerance and records both blocks; document the known sources of nondeterminism
(seeds, threads, GPU kernels, hash ordering) in the method card so a replication that
differs can be read. The worktree it re-runs in is prepared before the clock starts
(`replication-protocol.md`, "What the worktree receives"), so a study with an honest
60-second budget can still be replicated.

## Long sessions

Keep a laptop awake with the stdlib tool (`caffeinate -i uv run --locked klein
run-one ...` on macOS); after any interruption, `klein recover` reconciles the
transaction that was in flight. A run that outlives the driving session is still
notarized — the candidate was committed before it started.
