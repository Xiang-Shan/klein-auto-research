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
behind it. `max_run_seconds` bounds the wait. This is the whole integration — no
scheduler, no queue, no remote agent.

## Reproduction is a floor statement

Bitwise reproduction is not the bar; the floor is. `klein replicate` compares within a
tolerance and records both blocks; document the known sources of nondeterminism
(seeds, threads, GPU kernels, hash ordering) in the method card so a replication that
differs can be read.

## Long sessions

Keep a laptop awake with the stdlib tool (`caffeinate -i uv run --locked klein
run-one ...` on macOS); after any interruption, `klein recover` reconciles the
transaction that was in flight. A run that outlives the driving session is still
notarized — the candidate was committed before it started.
