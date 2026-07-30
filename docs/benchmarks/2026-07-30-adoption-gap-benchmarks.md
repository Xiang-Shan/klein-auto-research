# Adoption-gap acceptance benchmarks (G2, G3)

Date: 2026-07-30
Measured state: local branch at `dbdc46a` (kleinlib `runner.py`, `workflow.py`, and
`torch_loop.py` byte-identical to the v0.3 tip `aadde5a`)
Reference audit: `docs/reviews/2026-07-30-v0.2-adoption-audit.md` §2, rows G2 (B6)
and G3 (B1/B2)

## Environment

- Platform: `macOS-26.5.1-arm64-arm-64bit-Mach-O` (Apple silicon, Darwin 25.5.0).
- Python: CPython 3.13.3 under the locked project environment
  (`uv sync --locked --extra encoders --extra gbdt --extra deep`, then
  `uv run --no-sync`).
- Packages: numpy 2.5.1, pandas 3.0.3, scikit-learn 1.9.0, pyyaml 6.0.3,
  torch 2.13.0.
- All wall times via `time.perf_counter()` around the exact call under test.
- The torch benchmark ran in its own process with no GBDT imports (macOS arm64
  dual-libomp war story); the runner/write benchmarks ran in a torch-free process.

## Runner-overhead decision (G3 / B1)

Accept: the measured `run_logged` overhead is 8.1 ms, well inside the <100 ms
budget. The runner's pipe + pump-thread + log-file + footer machinery costs about
two-thirds of one bare interpreter launch.

Method: `[sys.executable, "-c", "pass"]` executed alternately by a bare
`subprocess.run(cmd, check=True)` and by
`kleinlib.runner.run_logged(cmd, cwd=None, log_path=..., timeout_seconds=60,
echo=False)`; 3 interleaved warmup rounds discarded, then n=30 timed rounds of
each. Overhead = median(run_logged) − median(bare).

| Fixture | Median | Minimum | Maximum | n |
|---|---:|---:|---:|---:|
| bare `subprocess.run` | 11.9 ms | 11.6 ms | 12.8 ms | 30 |
| `run_logged` | 20.0 ms | 19.8 ms | 20.2 ms | 30 |
| overhead (median − median) | **8.1 ms** | — | — | — |

A repeat of the full protocol gave 8.0 ms, so the estimate is stable to ~0.1 ms.
Reproduction:

```python
import statistics, subprocess, sys, tempfile, time
from pathlib import Path
from kleinlib.runner import run_logged

cmd = [sys.executable, "-c", "pass"]
log = Path(tempfile.mkdtemp()) / "bench-run.log"
def bare():
    t0 = time.perf_counter(); subprocess.run(cmd, check=True)
    return (time.perf_counter() - t0) * 1000
def logged():
    t0 = time.perf_counter()
    run_logged(cmd, cwd=None, log_path=log, timeout_seconds=60, echo=False)
    return (time.perf_counter() - t0) * 1000
for _ in range(3): bare(); logged()
b, l = [], []
for _ in range(30): b.append(bare()); l.append(logged())
print(statistics.median(l) - statistics.median(b))
```

## Evidence-write decision (G3 / B2)

Accept: both evidence writers are two orders of magnitude inside the <50 ms
per-write budget.

Method: (a) `kleinlib.workflow.atomic_write_json` of a representative 2,308-byte
manifest dict (experiment/track/disposition, full-hex commits and fingerprints,
eight aux metrics, four artifact records — the `validate_manifest` field set),
overwriting the same path each iteration; (b) `kleinlib.workflow.append_event`
with a small payload on a fixture study scaffolded by `uv run --no-sync klein new`
in a temporary directory, growing the hash chain to 54 events (each append
re-reads and re-verifies-from the whole chain, so this includes that linear cost
at realistic study length). 3 warmups discarded, then n=50 timed iterations each.

| Write | Median | Minimum | Maximum | n |
|---|---:|---:|---:|---:|
| `atomic_write_json` (~2 KB manifest, fsync + rename) | 0.144 ms | 0.131 ms | 0.184 ms | 50 |
| `append_event` (hash-chained, fsync) | 0.109 ms | 0.070 ms | 0.191 ms | 50 |

Reproduction:

```python
# uv run --no-sync klein new 99-bench-fixture --root /tmp/bench-studies \
#   --goal "write-latency benchmark fixture" --domain test --target y \
#   --family linear --metric val_auc --goal-direction higher --data csv:fixture.csv
import statistics, tempfile, time
from pathlib import Path
from kleinlib.workflow import append_event, atomic_write_json

manifest = {...}  # ~2 KB dict shaped like validate_manifest's field set
path = Path(tempfile.mkdtemp()) / "manifest.json"
study = Path("/tmp/bench-studies/99-bench-fixture")
def t(fn):
    t0 = time.perf_counter(); fn(); return (time.perf_counter() - t0) * 1000
for _ in range(3): t(lambda: atomic_write_json(path, manifest))
print(statistics.median([t(lambda: atomic_write_json(path, manifest)) for _ in range(50)]))
for i in range(3): t(lambda: append_event(study, "benchmark_probe", probe=i))
print(statistics.median([t(lambda: append_event(study, "benchmark_probe", probe=i)) for i in range(50)]))
```

## Torch per-batch device-transfer statement (G2 / B6)

**Scope of claim: the v0.2 change that keeps the full dataset on CPU and
transfers only the active batch to the device
(`kleinlib/torch_loop.py::fit`) is a memory-boundedness and correctness
change — it bounds accelerator RAM to one batch — and carries NO speed claim.**
The pre-change variant (whole dataset resident on the device) no longer exists
in the tree, so an A/B comparison is not possible; what follows is a reference
record of the CURRENT fit path only, kept so future changes to the loop have a
number to compare against.

Method: tiny MLP `Linear(32→64) → ReLU → Linear(64→1)`, synthetic float32
tensors 4096×32 with a linear+noise target, `epochs=3`, `batch_size=256`
(= 16 batches/epoch, 48 per-batch CPU→device transfers per fit), AdamW via
`torch_loop.fit`, `device=mps` (`kleinlib.torch_device.pick_device`), seed 42.
2 warmup fits discarded, then n=5 timed fits; fresh identically-seeded model per
fit.

| Fixture | Median | Minimum | Maximum | n |
|---|---:|---:|---:|---:|
| `torch_loop.fit`, MPS, 3 epochs, 48 batch steps | 57.8 ms | 56.6 ms | 58.5 ms | 5 |

That is ≈1.20 ms per optimizer step including the per-batch CPU→MPS transfer —
no evidence of a transfer-dominated loop at this scale. Reproduction:

```python
import numpy as np, statistics, time, torch, torch.nn as nn, torch.nn.functional as F
from kleinlib.torch_device import pick_device
from kleinlib.torch_loop import fit

device = pick_device("mps")
rng = np.random.default_rng(0)
X = rng.normal(size=(4096, 32)).astype("float32")
y = (X @ rng.normal(size=32).astype("float32") + 0.1 * rng.normal(size=4096)).astype("float32")
def one():
    torch.manual_seed(0)
    model = nn.Sequential(nn.Linear(32, 64), nn.ReLU(), nn.Linear(64, 1))
    t0 = time.perf_counter()
    fit(model, X, y, loss_fn=lambda o, t: F.mse_loss(o.squeeze(-1), t), epochs=3,
        batch_size=256, lr=1e-3, weight_decay=0.0, device=device,
        early_stopping_patience=None, seed=42)
    return (time.perf_counter() - t0) * 1000
for _ in range(2): one()
print(statistics.median([one() for _ in range(5)]))
```

## Verdict against the audited budgets

| Budget (audit §2) | Measured | Verdict |
|---|---:|---|
| runner overhead < 100 ms | 8.1 ms | PASS |
| manifest write < 50 ms | 0.144 ms | PASS |
| event append < 50 ms | 0.109 ms | PASS |
| torch device-transfer change | reference only | no speed claim made |

These results are specific to this machine and installed optional stack. They are
evidence for the recorded budgets and implementation decisions, not general
latency guarantees.
