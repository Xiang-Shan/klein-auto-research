# Provenance — third-party source files committed under this study

Read-only evidence. Nothing here is modified; `prepare.py` never reads these files
(the study's data source is `sklearn.datasets.load_iris`). They exist so the DATA
gate's provenance diff is reproducible from committed bytes rather than from a live
network fetch.

## `uci_iris.data`

| Field | Value |
|---|---|
| URL | `https://archive.ics.uci.edu/ml/machine-learning-databases/iris/iris.data` |
| Retrieved | 2026-08-24T19:11:06Z |
| HTTP | 200, 4551 bytes, no redirect away from the requested URL |
| SHA-256 | `6f608b71a7317216319b4d27b4d9bc84e6abd734eda7872b71a458569e2656c0` |
| Rows | 150 (no header) |

## `uci_iris.names`

| Field | Value |
|---|---|
| URL | `https://archive.ics.uci.edu/ml/machine-learning-databases/iris/iris.names` |
| Retrieved | 2026-08-24T19:11:06Z |
| HTTP | 200, 2998 bytes |
| SHA-256 | `71a09fb3ee237614cdb9c09d06e8ae1f610ce2a274c0d77272fea8a233e5eea3` |

Its header line reads `Updated Sept 21 by C.Blake - Added discrepency information`,
and the body carries the errata verbatim (quoted in `data_card.md`).

## Comparison target

`sklearn.datasets.load_iris`, scikit-learn **1.9.0** (the locked environment;
`uv.lock`). Its `DESCR` states: *"The dataset is taken from Fisher's paper. Note that
it's the same as in R, but not as in the UCI Machine Learning Repository, which has
two wrong data points."*

## Scope of the diff

Deliberately narrow: a **cell-level diff of the 150×4 measurement matrix** between the
two files. This is NOT a transcription of Fisher's 1936 Table I, and no claim in this
study rests on one.
