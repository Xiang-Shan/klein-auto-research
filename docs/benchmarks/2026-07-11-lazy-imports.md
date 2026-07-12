# Performance acceptance benchmarks

Date: 2026-07-11
Baseline: v0.1 commit `8f0ff4660a2c540bd7f45b008211595221d8d026`
Candidate: local `codex/v0.2-hardening` working tree

## Decision

Accept lazy package imports. A bare `import kleinlib` no longer imports the full
matplotlib/scikit-learn/Torch engine eagerly, while public submodules remain available
through module `__getattr__`. The isolated-process median fell from 9,914.6 ms to
14.8 ms on the measured machine. This is a material startup improvement and the engine
test suite verifies the public imports.

## Method

- Platform: Apple arm64, Darwin 25.5.0 (`RELEASE_ARM64_T6041`).
- Python: CPython 3.13.3, Clang 20.1.0.
- Environment: the same locked v0.2 virtual environment for both source trees.
- Fixture: package import only (`python -c "import kleinlib"`).
- Baseline source was exported directly from the reviewed commit with `git archive`.
- Seven fresh subprocesses per source tree; no warmup was discarded, so these are cold
  interpreter/package-import measurements.
- Wall time was measured around each subprocess with `time.perf_counter()`; subprocess
  output was suppressed.

## Results

| Source | Median | Minimum | Maximum | n |
|---|---:|---:|---:|---:|
| v0.1 eager imports | 9,914.6 ms | 9,646.1 ms | 10,372.2 ms | 7 |
| v0.2 lazy imports | 14.8 ms | 13.6 ms | 15.5 ms | 7 |

## Threshold-metric decision

Accept the vectorized F1 threshold scan. On a seeded 58,592-row binary fixture with
the fixed 99 thresholds, five repeats produced:

| Implementation | Median | Minimum | Maximum | n |
|---|---:|---:|---:|---:|
| 99 `sklearn.metrics.f1_score` calls | 238.1 ms | 232.6 ms | 242.5 ms | 5 |
| vectorized confusion counts | 10.9 ms | 10.8 ms | 12.4 ms | 5 |

The candidate was about 21.8x faster and matched every reference F1 value, including
the first-index tie rule used by `numpy.argmax`. A regression test compares both
calculations on 1,003 seeded observations.

## Preprocessing-reuse decision

Document and permit reuse inside a boxed sweep when the preprocessing configuration
is fixed; do not add an implicit engine cache. The benchmark used 20,000 synthetic rows,
six numeric columns, six 30-level categorical columns, OHE, and five trials. Five
repeats produced:

| Five-trial workload | Median | Minimum | Maximum | n |
|---|---:|---:|---:|---:|
| rebuild and refit preprocessing per trial | 276.0 ms | 273.5 ms | 284.0 ms | 5 |
| fit/transform once and reuse the matrix | 54.5 ms | 54.1 ms | 56.2 ms | 5 |

The observed speedup was about 5.1x and all matrices had identical shape and nonzero
counts. Reuse remains explicit because a trial that changes encoding, imputation, or
feature selection must fit its own transformer; an automatic cache could silently
compare different scientific treatments on stale features.

These results are specific to this machine and installed optional stack. They are
evidence for the recorded implementation decisions, not general latency guarantees.
