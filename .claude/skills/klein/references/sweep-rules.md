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
   `sweeps/<name>.sidecar.tsv` with columns:

   ```text
   trial   params_json   primary_metric   wall_seconds   status
   ```

   No trial is silent. The sidecar is the full search record.
3. **Exactly ONE results.tsv row.** The sweep contributes a SINGLE row to the study
   ledger — the WINNER. Its `description` references the sidecar (e.g. "swap-rate sweep,
   9 trials, see sweeps/swaprate.sidecar.tsv; best rate=0.15"). Optionally set the
   `study_id` column to the sweep name.
4. **Snapshot the winner into train.py.** Copy the winning config back into `train.py` so
   the committed mutable surface reproduces the winner with NO sweep machinery.
5. **Pickle the winner.** Persist the winning model via `kleinlib.snapshot` →
   `models/best_<exp>_<metric>.pkl` (+ manifest), same as a normal experiment.
6. **Commit, then the one row.** Commit-or-revert FIRST (train.py now holds the winner),
   THEN append the single results.tsv row, THEN commit results.tsv. Same discipline as
   the hand loop.
7. **No improving trial → the row is a `discard`.** When the sweep's best trial does not
   beat the study's pre-sweep best: revert `train.py` (no snapshot, no pickle), log the
   single row with the best trial's metric and status `discard`, description noting
   "no improvement over exp N (<metric>)". The sidecar still keeps the full trail — a
   null result is a result.

## Forbidden

- Touching the split inside a sweep. The split is fixed; a sweep tunes the MODEL, never
  the data contract.
- Multiple silent results.tsv rows from one sweep. Only the winner earns a row; all
  trials live in the sidecar.
- Unattended multi-experiment meta-runners BEYOND the sweep — no "run all my ideas"
  scripts. A sweep searches ONE axis (or a small grid) of ONE method; it does not replace
  the adaptive hand loop across methods.

## Minimal SweepRunner sketch

```python
from kleinlib.sweep import SweepRunner
runner = SweepRunner("swaprate", metric_name="val_auc", metric_goal="higher")
for rate in (0.10, 0.15, 0.25):
    auc, secs = fit_and_eval(swap_rate=rate)      # your trial body (fixed split!)
    runner.record(trial=rate, params={"swap_rate": rate},
                  primary_metric=auc, wall_seconds=secs, status="ok")
winner = runner.best()   # appends every trial to the sidecar; returns the winning row
```

Example `sweeps/swaprate.sidecar.tsv`:

```text
trial   params_json           primary_metric   wall_seconds   status
0.10    {"swap_rate": 0.10}   0.6689           412.3          ok
0.15    {"swap_rate": 0.15}   0.6701           418.7          ok
0.25    {"swap_rate": 0.25}   0.6683           420.1          ok
```

## Shape of a sweep run

```text
edit sweeps/<name>.py  →  run it (foreground, budget = trials × per-trial)  →
  every trial appended to the sidecar  →  pick winner  →
  snapshot winner config into train.py  →  pickle winner via kleinlib.snapshot  →
  commit train.py  →  ONE results.tsv row (description points to sidecar)  →
  commit results.tsv
```

The sidecar is the audit trail; results.tsv stays one-row-per-decision. That is what
keeps the progress frontier honest even when a search ran 50 trials underneath.
