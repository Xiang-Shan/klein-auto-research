"""Phase-0 keep bar: item bootstrap of the anchor's development macro-F1.

Estimand marginal-resplit. A re-draw of the n development images is a multinomial
re-draw of the confusion table's cells, and macro-F1 is RECOMPUTED on every draw
(it is not a per-item mean). The table is the seed-mean of the anchor E0001's three
pinned per-seed confusion tables (cell probabilities M/n). 1,000 draws; one sidecar row
per draw (primary_metric = the re-drawn macro-F1). Per-seed-table sds are printed as a
cross-check (the method card's conservative variant).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

from kleinlib.sweep import SweepRunner

STUDY = Path(__file__).resolve().parents[1]
EXP = "E0001"
N_BOOT = 1000


def macro_f1(M):
    tp = np.diag(M).astype(float)
    fp = M.sum(0) - tp
    fn = M.sum(1) - tp
    den = 2 * tp + fp + fn
    f1 = np.divide(2 * tp, den, out=np.zeros_like(tp), where=den > 0)
    return f1[M.sum(1) > 0].mean()


def load_tables():
    paths = sorted((STUDY / "tables").glob(f"confusion_{EXP}_s*.tsv"))
    assert len(paths) == 3, paths
    out = []
    for p in paths:
        rows = [ln.rstrip("\n").split("\t") for ln in p.read_text().splitlines()]
        M = np.array([[float(v) for v in r[1:]] for r in rows[1:]])
        out.append(M)
    return paths, out


paths, tables = load_tables()
Mbar = np.mean(tables, axis=0)
n = int(round(Mbar.sum()))
P = (Mbar / Mbar.sum()).ravel()
rngs = np.random.default_rng(20261103).spawn(N_BOOT)


def trial(params):
    b = params["draw"]
    M = rngs[b].multinomial(n, P).reshape(Mbar.shape)
    return {"primary_metric": float(macro_f1(M)), "status": "ok"}


if __name__ == "__main__":
    for p, M in zip(paths, tables):
        rng = np.random.default_rng(1)
        v = [macro_f1(rng.multinomial(int(M.sum()), (M / M.sum()).ravel()).reshape(M.shape)) for _ in range(N_BOOT)]
        print(f"cross-check {p.name}: point={macro_f1(M):.5f} boot_sd={np.std(v, ddof=1):.5f}", file=sys.stderr)
    print(f"seed-mean table point macro-F1 = {macro_f1(Mbar):.5f}, n = {n}", file=sys.stderr)
    SweepRunner("item_bootstrap", study_dir=STUDY, trial_fn=trial,
                params_list=[{"draw": b} for b in range(N_BOOT)], metric_goal="higher").run()
