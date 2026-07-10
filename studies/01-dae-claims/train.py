"""train.py — the mutable experiment surface for 01-dae-claims.

THIS is the one file you edit per experiment (5-15 line diffs). Everything stable
(data loading, the fixed split, metrics, model saving) lives in kleinlib; the DAE lives
in this study's dae.py. train.py stays thin — it wires one experiment together.

Loop contract:  repo CLAUDE.md + .claude/skills/klein/SKILL.md Hard Rules
Sweeps (the ONLY escape-hatch):  .claude/skills/klein/references/sweep-rules.md

E7 — DAE-as-imputer vs median under MCAR (Phase 2, RQ4a). Inject MCAR missingness at
{10%, 30%} into VAL copies (eligible columns only: 21 numerics + 6 cats, mirroring the
swap-noise doctrine; is_* excluded; seeds rng(4210)/rng(4230)). Two imputation arms per
rate: (a) median/mode from the TRAIN fold; (b) DAE reconstruction — encode the missing
frame (internal imputers give the median starting point), decode, then write back the
decoder's values at the MASKED cells only (numerics: inverse-RankGauss of the decoder
output; categoricals: argmax over the OHE block). Downstream judge = the E3 LGBM head
refit deterministically from the clean cached rep_tr (bit-exact, proven twice), scoring
each arm's val reps. Ledger primary (pre-registered in program.md 2026-07-10): the
DAE-arm downstream val_auc at 30% MCAR. All arm AUCs, deltas, clean reference, and
imputation diagnostics (RankGauss-space numeric RMSE, categorical accuracy at masked
cells) -> aux. Keep rule: DAE-impute >= median-impute at EITHER rate.

Two-stage per the libomp war story (program.md Ops section): stage "impute" = torch
child (DAE reconstruct + arm reps; never imports lightgbm); parent = lightgbm-first
LGBM head + canonical evaluate.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

# --- experiment knobs (the obvious mutable surface) -------------------------
RANDOM_SEED = 42
EXPERIMENT_ID = 7          # bump per experiment; matches the results.tsv row
RUN_BUDGET_SECONDS = 1800  # keep within the CURRENT phase budget in study.yaml
MCAR_RATES = (0.10, 0.30)  # pre-registered missingness rates
PRIMARY_RATE = 0.30        # pre-registered: primary = DAE arm at 30%

_HERE = Path(__file__).resolve().parent
DAE_CACHE = _HERE / "models/dae_e3_swap015.cache.pkl"     # E3's fitted DAE (canonical)
REPS_CACHE = _HERE / "models/reps_e3_swap015.cache.pkl"   # E3's frozen clean reps
E7_CACHE = _HERE / "models/e7_imputer.cache.pkl"          # per-rate arm reps + diags

PREPARED_PATH = Path("data/prepared/insurance_claims_prepared.csv")
TARGET_COLUMN = "claim_status"


def load_split():
    """Load prepared data and make the FIXED train/val split (via kleinlib.data)."""
    import kleinlib

    X, y = kleinlib.data.load_xy(PREPARED_PATH, TARGET_COLUMN)
    return kleinlib.data.fixed_split(X, y)  # seed=42, test_size=0.2, stratify=True


def stage_impute() -> None:
    """CHILD (torch world; no lightgbm): MCAR injection, both imputation arms,
    imputation diagnostics, and the 768-d reps of every imputed frame."""
    import joblib
    import numpy as np

    X_tr, X_va, _y_tr, _y_va = load_split()
    m = joblib.load(DAE_CACHE)
    eligible = list(m.eligible_cols_)           # 21 numerics + 6 cats, is_* excluded
    num_cols, cat_cols = list(m.numeric_cols_), list(m.categorical_cols_)
    qt = m.transformer_.named_transformers_["num"].named_steps["rankgauss"]
    ohe = m.transformer_.named_transformers_["cat"].named_steps["ohe"]
    widths = [len(c) for c in ohe.categories_]
    n_num = len(num_cols)
    cat_block_start = n_num + len(m.is_star_cols_)  # ColumnTransformer order: num|bin|cat
    assert sum(widths) + cat_block_start == m.input_dim_ == 94

    # train-fold statistics for the median/mode arm
    med = {c: X_tr[c].median() for c in num_cols}
    mode = {c: X_tr[c].mode().iloc[0] for c in cat_cols}

    Z_true = m._encode(X_va)  # clean encoded reference for RankGauss-space RMSE
    out: dict = {"rates": list(MCAR_RATES)}

    for rate in MCAR_RATES:
        rng = np.random.default_rng(4200 + int(rate * 100))  # 4210 / 4230, pre-registered
        mask = {c: rng.random(len(X_va)) < rate for c in eligible}

        X_missing = X_va.copy()
        for c in eligible:
            X_missing.loc[mask[c], c] = np.nan

        # arm (a): TRAIN-fold median / mode
        X_med = X_missing.copy()
        for c in num_cols:
            X_med.loc[mask[c], c] = med[c]
        for c in cat_cols:
            X_med.loc[mask[c], c] = mode[c]

        # arm (b): DAE reconstruction, written back at masked cells only
        Zhat = m.reconstruct(X_missing)          # (n, 94) encoded-space decoder output
        raw_num = qt.inverse_transform(Zhat[:, :n_num])   # back to raw numeric space
        X_dae = X_med.copy()                     # start from the median arm ...
        for j, c in enumerate(num_cols):         # ... then overwrite masked numerics
            X_dae.loc[mask[c], c] = raw_num[mask[c], j]
        off = cat_block_start
        for k, c in enumerate(cat_cols):         # ... and masked categoricals (argmax)
            block = Zhat[:, off:off + widths[k]]
            values = ohe.categories_[k][np.argmax(block, axis=1)]
            X_dae.loc[mask[c], c] = values[mask[c]]
            off += widths[k]

        # imputation diagnostics at the masked cells (aux material)
        diags: dict = {}
        for arm, X_arm in (("dae", X_dae), ("median", X_med)):
            Z_arm = m._encode(X_arm)
            sq = [((Z_arm - Z_true)[mask[c], j] ** 2) for j, c in enumerate(num_cols) if mask[c].any()]
            diags[f"rmse_num_{arm}"] = float(np.sqrt(np.concatenate(sq).mean()))
            hits = [(X_arm[c].to_numpy()[mask[c]] == X_va[c].to_numpy()[mask[c]]) for c in cat_cols if mask[c].any()]
            diags[f"cat_acc_{arm}"] = float(np.concatenate(hits).mean())
        n_masked = int(sum(mask[c].sum() for c in eligible))

        out[f"{rate:.2f}"] = {
            "rep_dae": m.transform(X_dae), "rep_median": m.transform(X_med),
            "n_masked_cells": n_masked, **diags,
        }
        print(f"impute-stage rate={rate:.2f}: masked_cells={n_masked} "
              f"rmse_num dae={diags['rmse_num_dae']:.4f} med={diags['rmse_num_median']:.4f} | "
              f"cat_acc dae={diags['cat_acc_dae']:.4f} med={diags['cat_acc_median']:.4f}",
              flush=True)

    joblib.dump(out, E7_CACHE)
    print(f"impute-stage: cached -> {E7_CACHE.name}", flush=True)


def stage_head(t0: float) -> None:
    """PARENT: lightgbm world — deterministic E3-head refit, score every arm."""
    from lightgbm import LGBMClassifier, early_stopping  # MUST be first (war story)

    import joblib
    from sklearn.metrics import roc_auc_score

    import kleinlib  # binds torch passively; no torch op ever runs in this process

    X_tr, X_va, y_tr, y_va = load_split()
    reps = joblib.load(REPS_CACHE)
    e7 = joblib.load(E7_CACHE)

    clf = LGBMClassifier(
        n_estimators=2000, learning_rate=0.05,
        num_leaves=15, min_child_samples=20,
        subsample=0.7, subsample_freq=1, colsample_bytree=0.7, reg_lambda=1.0,
        random_state=RANDOM_SEED, n_jobs=-1, verbose=-1,
    )
    fit_start = time.time()
    clf.fit(reps["rep_tr"], y_tr, eval_set=[(reps["rep_va"], y_va)],
            callbacks=[early_stopping(50, verbose=False)])
    fit_seconds = time.time() - fit_start

    auc_clean = float(roc_auc_score(y_va, clf.predict_proba(reps["rep_va"])[:, 1]))
    extra: dict = {"auc_clean_reps": round(auc_clean, 6),
                   "lgbm_best_iteration": clf.best_iteration_}
    for rate in MCAR_RATES:
        d = e7[f"{rate:.2f}"]
        auc_dae = float(roc_auc_score(y_va, clf.predict_proba(d["rep_dae"])[:, 1]))
        auc_med = float(roc_auc_score(y_va, clf.predict_proba(d["rep_median"])[:, 1]))
        tag = f"mcar{int(rate * 100)}"
        extra[f"auc_dae_{tag}"] = round(auc_dae, 6)
        extra[f"auc_median_{tag}"] = round(auc_med, 6)
        extra[f"delta_dae_vs_median_{tag}"] = round(auc_dae - auc_med, 6)
        extra[f"rmse_num_dae_{tag}"] = round(d["rmse_num_dae"], 6)
        extra[f"rmse_num_median_{tag}"] = round(d["rmse_num_median"], 6)
        extra[f"cat_acc_dae_{tag}"] = round(d["cat_acc_dae"], 6)
        extra[f"cat_acc_median_{tag}"] = round(d["cat_acc_median"], 6)
        extra[f"n_masked_cells_{tag}"] = d["n_masked_cells"]

    # primary (pre-registered): DAE arm at 30% MCAR through the frozen head
    kleinlib.eval.evaluate(
        clf, e7[f"{PRIMARY_RATE:.2f}"]["rep_dae"], y_va,
        exp_id=EXPERIMENT_ID,
        t0=t0, fit_seconds=fit_seconds,
        train_n=len(X_tr), val_n=len(X_va),
        metric_name="val_auc", metric_goal="higher",
        study_dir=".",
        extra=extra,
    )


def main() -> None:
    t0 = time.time()
    r = subprocess.run([sys.executable, str(_HERE / "train.py"), "--stage", "impute"])
    if r.returncode != 0:
        raise RuntimeError(f"impute stage subprocess failed with rc={r.returncode}")
    stage_head(t0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["impute"], default=None)
    args = parser.parse_args()
    if args.stage == "impute":
        stage_impute()
    else:
        main()
