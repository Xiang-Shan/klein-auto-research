# Remote compute: SSH / Slurm hosts and Modal

Claude Science can run a job on a host you added (Settings → Compute → SSH hosts; Slurm's
`sbatch` when present, a detached process otherwise) or on your Modal account. Those jobs
are spawned by the app, not by `klein run-one`, so the notary cannot watch the process.
Klein 2.3's **detached runs** close that gap without weakening the transaction:

```
local study                         remote host / Modal                local study
──────────────────────────          ─────────────────────────          ─────────────────────────
klein run-one --detach   ──job──▶   klein job exec … --executor here   klein run-one --collect E####
 candidate + DETACH commit           runs the job, writes               receipt checked against the
 runs/E####/job.json                 job_result/ + receipt.json  ──▶    committed job; judged locally;
 study FROZEN                                                           execution: attested
```

The full doctrine is in `.claude/skills/klein/references/compute-and-devices.md`
("Detached runs"). From a terminal with plain `ssh`, `sbatch --wait` or `modal run`, a
blocking wrapper entrypoint is still simpler — use detached runs when the *app* runs the
job, or when a run must outlive the session.

## 0. Opt in (once, at CONSULT)

```yaml
entrypoint:
  command: ["uv", "run", "--locked", "python", "-u", "train.py"]
  mutable: ["train.py", "model.py"]
  printed: block
  execution: [local, detached]
```

The contract then says, before any evidence, that a run may execute outside the notary's
sight. A study that never declares it cannot detach.

## 1. Detach (local)

```bash
klein run-one --study studies/NN-slug --detach --tests P2
git bundle create /tmp/klein-NN.bundle HEAD
```

`--detach` runs every pre-run check (gates, branch, preflight, budgets, unchanged-surface
refusal), files the candidate commit, then a DETACH commit holding
`runs/E####/job.json` — command, environment, seeds, timeout, the candidate commit and the
sha256 of each mutable-surface file — and the `.klein-detached` sentinel. Until collect or
abandon, every other locking or committing verb refuses: the ledger's order stays the
execution order.

The git bundle carries the repository at the detach commit to the host as one input file
(Modal takes ≤ 1 GiB of inputs per submit; a bundle of this repository is tens of MB). A
host that can reach your git remote can `git clone` instead — push the study branch first.

## 2. The job script (remote)

Ask Claude to submit this as the job (it shows on the **Run this job on `<host>`?** or
**Start a Modal job?** card). Set the job's time limit above the study's `max_run_seconds`
times the number of seeds, plus setup — SSH jobs default to 30 minutes.

```bash
#!/usr/bin/env bash
set -euo pipefail
STUDY=studies/NN-slug
RUN=E0007
git clone --quiet klein-NN.bundle klein && cd klein
# The environment: uv when the host has it, otherwise a venv with the PyPI wheel.
if command -v uv >/dev/null; then
  uv sync --locked --extra deep
  KLEIN="uv run --locked klein"; PY="uv run --locked python"
else
  python -m venv .venv && . .venv/bin/activate
  pip install --quiet "klein-auto-research[deep]==2.3.*"
  KLEIN="klein"; PY="python"
fi
# data/ is gitignored: regenerate it exactly as the DATA gate froze it.
(cd "$STUDY" && $PY -u prepare.py)
$KLEIN job exec "$STUDY/runs/$RUN/job.json" --executor here
mkdir -p "${OUT:-out}"
tar czf "${OUT:-out}/job_result-$RUN.tgz" -C "$STUDY/runs/$RUN" job_result
```

For a study scaffolded with `--runner python`, the job's command is `python -u …` and the
`uv` branch only installs the environment.

`klein job exec` refuses a checkout whose mutable surface differs from the job's hashes,
runs the command (once per seed for a seed array) under the job's timeout, and writes
`job_result/`: `run.log`, `usage.json` (with the host's torch / CUDA / GPU), every output
file, and `receipt.json` with the job's sha256, the executed surface hashes, the log and
file hashes, the exit status and the hardware.

On Modal, outputs written to `./out/` (≤ 5 GiB) come back with the logs; on an SSH host the
job directory's outputs are pulled back (files over ~100 MB stay on the host — keep model
weights that are evidence below that, or pin them by hash).

## 3. Collect (local)

```bash
mkdir -p studies/NN-slug/runs/E0007
tar xzf job_result-E0007.tgz -C studies/NN-slug/runs/E0007
klein run-one --study studies/NN-slug --collect E0007
```

Collect refuses unless HEAD is still the detach commit and the receipt matches the
committed job bundle, the surface hashes, the log and every file. It then judges the run
**locally, by the same code as a foreground run**: the printed `split_fingerprint` against
the one frozen at the DATA gate (a host that regenerated different data is a crash), the
declared guardrails, the disposition, the predictions named with `--tests`. The manifest
records `execution: {mode: detached, executor, host, receipt_sha256, hardware,
observed_by_notary: false}` — attested, not observed — and the referee weighs it that way.
`klein replicate E0007` re-executes it locally whenever an observed record is wanted.

A job that will never come back:

```bash
klein run-one --study studies/NN-slug --abandon E0007 --reason "node preempted twice"
```

records a crash with that reason and restores the surface. `klein recover` never crashes a
detached run on its own, and `klein next` names the pending collect.

## Same machine, background

`klein job exec studies/NN-slug/runs/E0007/job.json` (default `--executor local`) runs the
job in a throwaway worktree of this repository and writes `job_result/` back in place —
useful for a long CPU run you want off the session's critical path (`nohup … &`). The
study stays frozen until you collect.
