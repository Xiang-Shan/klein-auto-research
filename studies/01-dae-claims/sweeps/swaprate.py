"""sweeps/swaprate.py — Experiment 5: swap-rate sweep via kleinlib.sweep.

Sweeps ONE axis — `swap_rate` in {0.10, 0.15, 0.25} — of the E3 recipe: inductive
SwapNoiseDAE(rate) fit on the TRAIN fold only (fairness rule), frozen 768-dim
deep-stack reps -> LGBM (gbdt-tabular.md recipe: num_leaves=15, min_child_samples=20,
lr=0.05, sub/col=0.7, reg_lambda=1, n_est=2000, early_stopping=50). Baseline: exp 3,
val_auc=0.668271 (swap_rate=0.15). The FIXED split is loaded once and reused for every
trial — a sweep tunes the model, never the data contract.

Protocol: `.claude/skills/klein/references/sweep-rules.md`. Every trial is appended to
`sweeps/swaprate.sidecar.tsv` by `kleinlib.sweep.SweepRunner` as it finishes; this
script does NOT touch `results.tsv`, does NOT commit, and does NOT pickle a model —
those stay manual, applied by hand around this script per the rules (winner snapshotted
into `train.py` + rerun once for the official eval side-effects IF it improves; else
the rule-7 discard row).

LIBOMP WAR STORY (program.md 2026-07-10): torch + LightGBM segfault when sharing a
process on macOS arm64, so each trial is TWO-STAGE: the DAE fits in a torch-only child
subprocess (`--stage dae --rate R`, never imports lightgbm) that dumps rate-tagged
caches under models/; the LGBM head runs in THIS parent (lightgbm imported first,
torch bound passively by kleinlib but never operated). Sequential, foreground.

Each trial applies the same `min_proba_std` guard threshold as kleinlib.eval.evaluate
(0.01) — a collapsed-prediction trial records as `crash` in the sidecar, never silent.

Usage: cd studies/01-dae-claims && uv run python sweeps/swaprate.py
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

_SELF = Path(__file__).resolve()
_STUDY = _SELF.parents[1]
if str(_STUDY) not in sys.path:  # so the torch-only child can `import dae`
    sys.path.insert(0, str(_STUDY))

RANDOM_SEED = 42
BASELINE_VAL_AUC = 0.668271  # exp 3: inductive DAE(0.15) -> LGBM recipe
SWAP_RATES = [0.10, 0.15, 0.25]
MIN_PROBA_STD = 0.01         # guard parity with kleinlib.eval.evaluate

PREPARED = _STUDY / "data/prepared/insurance_claims_prepared.csv"
TARGET = "claim_status"


def _tag(rate: float) -> str:
    return f"{rate:.2f}"


def dae_cache(rate: float) -> Path:
    return _STUDY / f"models/dae_e5_swap{_tag(rate)}.cache.pkl"


def reps_cache(rate: float) -> Path:
    return _STUDY / f"models/reps_e5_swap{_tag(rate)}.cache.pkl"


def stage_dae(rate: float) -> None:
    """CHILD (torch-only world; lightgbm NEVER imported): fit + cache DAE(rate)."""
    import joblib
    import torch

    import dae
    import kleinlib

    X, y = kleinlib.data.load_xy(PREPARED, TARGET)
    X_tr, X_va, _y_tr, _y_va = kleinlib.data.fixed_split(X, y)

    t0 = time.time()
    m = dae.SwapNoiseDAE(swap_rate=rate, seed=RANDOM_SEED)  # inductive default
    m.fit(X_tr)
    fit_seconds = time.time() - t0
    assert m.fit_mode == "inductive" and m.n_fit_rows_ == len(X_tr), \
        "FAIRNESS RULE violated: inductive DAE must fit on exactly the train fold"
    m.net_ = m.net_.to(torch.device("cpu"))
    m.device_ = torch.device("cpu")
    rep_tr, rep_va = m.transform(X_tr), m.transform(X_va)

    joblib.dump(m, dae_cache(rate))
    joblib.dump({"rep_tr": rep_tr, "rep_va": rep_va, "swap_rate": rate,
                 "input_dim": m.input_dim_, "n_fit_rows": m.n_fit_rows_,
                 "dae_fit_seconds": fit_seconds, "history": m.history_},
                reps_cache(rate))
    print(f"  dae-stage rate={rate}: epochs_run={m.history_['epochs_run']} "
          f"best_es_mse={m.history_['best_es']:.5f} fit_seconds={fit_seconds:.1f}",
          flush=True)


def main() -> None:
    # PARENT world: lightgbm first (war story), torch never operated here.
    from lightgbm import LGBMClassifier, early_stopping

    import joblib
    import numpy as np
    from sklearn.metrics import roc_auc_score

    import kleinlib
    from kleinlib.sweep import SweepRunner

    X, y = kleinlib.data.load_xy(PREPARED, TARGET)
    X_tr, X_va, y_tr, y_va = kleinlib.data.fixed_split(X, y)

    def trial_fn(params: dict) -> dict:
        rate = params["swap_rate"]
        r = subprocess.run(
            [sys.executable, str(_SELF), "--stage", "dae", "--rate", str(rate)]
        )
        if r.returncode != 0:
            return {"status": "crash", "error": f"dae stage rc={r.returncode}"}
        cache = joblib.load(reps_cache(rate))
        rep_tr, rep_va = cache["rep_tr"], cache["rep_va"]
        assert rep_tr.shape == (len(X_tr), 768) and rep_va.shape == (len(X_va), 768)

        clf = LGBMClassifier(
            n_estimators=2000, learning_rate=0.05,
            num_leaves=15, min_child_samples=20,
            subsample=0.7, subsample_freq=1, colsample_bytree=0.7, reg_lambda=1.0,
            random_state=RANDOM_SEED, n_jobs=-1, verbose=-1,
        )
        clf.fit(rep_tr, y_tr, eval_set=[(rep_va, y_va)],
                callbacks=[early_stopping(50, verbose=False)])
        p = clf.predict_proba(rep_va)[:, 1]
        std = float(np.std(p))
        if std < MIN_PROBA_STD:
            return {"status": "crash", "error": f"collapsed preds std={std:.6g}"}
        auc = float(roc_auc_score(y_va, p))
        return {"primary_metric": auc,
                "dae_epochs_run": cache["history"]["epochs_run"],
                "dae_best_es_mse": round(float(cache["history"]["best_es"]), 6),
                "dae_fit_seconds": round(cache["dae_fit_seconds"], 1),
                "lgbm_best_iteration": clf.best_iteration_,
                "proba_std": round(std, 6)}

    runner = SweepRunner(
        "swaprate", study_dir=_STUDY, trial_fn=trial_fn,
        params_list=[{"swap_rate": r} for r in SWAP_RATES],
        metric_goal="higher",
    )
    summary = runner.run()

    print("\n--- swaprate sweep summary ---", flush=True)
    for t in summary.trials:
        metric = "NA" if t.primary_metric is None else f"{t.primary_metric:.6f}"
        print(f"trial {t.trial}  rate={t.params['swap_rate']:<5} val_auc={metric} "
              f"({t.wall_seconds:.1f}s, {t.status}) extra={t.extra}", flush=True)
    w = summary.winner
    if w is None:
        print("winner: NONE (all trials crashed)", flush=True)
        return
    improved = summary.improved_over(BASELINE_VAL_AUC)
    print(f"winner: rate={w.params['swap_rate']} val_auc={w.primary_metric:.6f} | "
          f"baseline(E3)={BASELINE_VAL_AUC:.6f} | delta={w.primary_metric - BASELINE_VAL_AUC:+.6f} | "
          f"improved={improved}", flush=True)
    print(f"sidecar: {runner.sidecar_path}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["dae"], default=None)
    parser.add_argument("--rate", type=float, default=None)
    args = parser.parse_args()
    if args.stage == "dae":
        assert args.rate is not None, "--stage dae requires --rate"
        stage_dae(args.rate)
    else:
        main()
