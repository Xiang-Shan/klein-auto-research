# Sweep rules — the ONE escape-hatch

The agent IS the loop: normally each experiment is a hand-edited `train.py` diff — run,
recorded, committed. The single sanctioned exception is a SWEEP: a parameter search too
mechanical to hand-drive. Sweeps are tightly boxed so they never corrupt the ledger.

Role: sweeper. Any agent or human can execute this protocol directly — it is the
source of truth; Claude Code ships it pre-wired as the `klein-sweeper` worker.
Uses `kleinlib.sweep.SweepRunner`.

## The rules (all of them)

1. **Location.** A sweep lives ONLY at `studies/NN/sweeps/<name>.py`. Never at study
   root, never a meta-runner over the whole study.
2. **Every trial → sidecar.** EVERY trial appends one line to
   `sweeps/<name>.sidecar.tsv`. The authoritative columns live in
   `kleinlib.sweep.SIDECAR_COLUMNS`; current sidecars include persisted error details
   for crashes as well as parameters, metric, timing, and status.

   ```text
   trial   params_json   primary_metric   wall_seconds   status   error
   ```

   No trial is silent. The sidecar is the full search record. (Sidecar writes are
   NOT gated by `KLEIN_SMOKE` — they are explicit named artifacts with overwrite
   protection; smoke-test a sweep script by slicing its `params_list` instead.)
   When the sweep does not vary preprocessing, fit/transform the fixed train and
   development matrices once outside `trial_fn` and reuse them. A 20k-row fixture
   measured about 5.1× lower median sweep preprocessing time (276.0 ms → 54.5 ms for
   five trials) with identical shape/nnz. Do not cache when a trial changes any
   preprocessing parameter.
3. **Exactly ONE derived result.** The sweep contributes one candidate transaction —
   the winner rerun through `klein run-one`. Its description references the sidecar
   (for example, "swap-rate sweep, 9 trials; see sweeps/swaprate.sidecar.tsv; best
   rate=0.15"). Never append a v2 `results.tsv` row by hand.
4. **Snapshot the winner into train.py.** Copy the winning config back into `train.py` so
   the committed mutable surface reproduces the winner with NO sweep machinery.
5. **Record the winner artifact safely.** Persist the winning model locally via
   `kleinlib.snapshot`; commit its relocatable manifest (metric identity, track,
   availability, and SHA-256), never the unsafe/large joblib payload itself.
6. **Commit the sweep evidence, then transact the winner.** Commit the sweep script and
   completed sidecar, copy the winner into `train.py`, and invoke `klein run-one`. It
   commits the candidate before its confirmation run, creates the immutable manifest,
   and derives the one v2 ledger row transactionally.
7. **No improving trial → `discard`.** Put the best trial in `train.py` and let
   `klein run-one` compare its confirmation metric with the track frontier. If it does
   not clear the configured minimum delta and guardrails, it is a `discard` and the
   workflow restores `train.py`. The candidate commit and sidecar remain resolvable —
   a null result is a result. If the winning trial EQUALS the incumbent config the
   candidate diff is empty — pass `--allow-rerun` for that confirmation transaction.

## Forbidden

- Touching the split inside a sweep. The split is fixed; a sweep tunes the MODEL, never
  the data contract.
- Multiple derived results from one sweep. Only the confirmed winner earns a manifest /
  derived row; all trials live in the sidecar.
- Unattended multi-experiment meta-runners BEYOND the sweep — no "run all my ideas"
  scripts. A sweep searches ONE axis (or a small grid) of ONE method; it does not replace
  the adaptive hand loop across methods.

## Executable SweepRunner sketch

The block between the test markers is executed in CI. Replace `fit_and_eval` with the
real fixed-split trial body; keep the runner construction and `.run()` contract.

Commit the sweep script before execution. Then, from the study directory, execute it
once with a total sweep timeout (not once per trial):

```bash
uv run --locked python ../../scripts/run_with_log.py \
  --timeout-seconds <total-sweep-seconds> --log sweep.log -- \
  uv run --locked python -u sweeps/<name>.py
```

<!-- test:sweep-runner:start -->
```python
from pathlib import Path

from kleinlib.sweep import SweepRunner


def fit_and_eval(params: dict[str, float]) -> dict[str, float]:
    """Replace with one real trial evaluated on the fixed development split."""
    rate = params["swap_rate"]
    return {"primary_metric": 0.67 - abs(rate - 0.15)}


summary = SweepRunner(
    "swaprate",
    study_dir=Path("."),
    trial_fn=fit_and_eval,
    params_list=[{"swap_rate": rate} for rate in (0.10, 0.15, 0.25)],
    metric_goal="higher",
).run()

winner = summary.winner
assert winner is not None
assert winner.params == {"swap_rate": 0.15}
```
<!-- test:sweep-runner:end -->

Example `sweeps/swaprate.sidecar.tsv`:

```text
trial   params_json           primary_metric   wall_seconds   status   error
1       {"swap_rate":0.1}     0.668900         412.300        ok
2       {"swap_rate":0.15}    0.670100         418.700        ok
3       {"swap_rate":0.25}    0.668300         420.100        ok
```

## Shape of a sweep run

```text
commit sweeps/<name>.py  →  execute it once with scripts/run_with_log.py
  (foreground, budget = trials × per-trial)  →  every trial in sidecar  →
  commit sidecar  →  copy winner into train.py  →  klein run-one reruns winner  →
  one immutable manifest + one derived results row (description points to sidecar)
```

The sidecar is the trial-level audit trail; the run manifest is the winner-decision
audit trail. This keeps each track's frontier honest even when a search ran 50 trials
underneath. A legacy v1 study retains its manual one-row winner discipline, but should
use the same `SweepRunner(...).run()` API and the exit-safe runner.

## Carve-out: measurement sweeps — and how they become citable evidence

A **measurement sweep** (the Phase-0 noise floor, `sweeps/noise_floor.py`; a
split-lottery; a per-candidate paired floor; a permission map) runs identical or
registered configs and therefore promotes **no winner and no `results.tsv` row at
all** — its evidence is the sidecar, the `noise_floor:` block it produces in
`study.yaml`, and the consult-gate re-record event. Rule 7 governs search sweeps; a
measurement is not a search.

In schema 3 a measurement sweep is **registered** so findings and the claims lock can
cite it as `sweep:<name>`:

```bash
uv run --locked klein sweep register --study studies/NN-slug <name> \
  --sidecar sweeps/<name>.sidecar.tsv --script sweeps/<name>.py
```

The verb hashes the sidecar and the script into `state.sweeps`, counts ok and crash
rows, and appends the event `sweep_registered`. Crash rows stay in the sidecar — they
are data about where a method breaks (studies 07 and 08 kept a registered crash rung
for exactly that reason). A sidecar edited after registration fails `klein verify`.
