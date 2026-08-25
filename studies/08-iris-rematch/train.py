"""The only per-candidate mutable surface in a Klein v2 study.

Study 08 — the rematch. E0001 re-establishes the 1936 anchor on the FRESH declared
split (seed 20260907); the parade then edits exactly one line (FAMILY) per
transaction across the 21-family challenger roster. Candidate selection happens
ONLY through FAMILY (families.py registry); feature columns come from the registry
so `species` (a perfect target proxy) and `group_id` can never leak in.
Sealed-coda wrapper families (`<family>@n<k>`) are ordinary registry entries whose
factories bake pre-registered train positions — this file never grows a second knob.
"""

from __future__ import annotations

import os
import time

import kleinlib
from kleinlib.data import load_prepared, three_way_split

import families

#: The registered family this candidate runs. The ONE line the ladder edits.
FAMILY = "tabpfn"

RANDOM_SEED = 20260907
SMOKE = os.environ.get("KLEIN_SMOKE") == "1"
EXPERIMENT_ID = os.environ.get("KLEIN_EXPERIMENT_ID") or ("SMOKE" if SMOKE else None)
TRACK = os.environ.get("KLEIN_TRACK") or ("primary" if SMOKE else None)

PREPARED = "data/prepared/iris_hard_pair.csv"
TARGET = "is_virginica"


def load_split(evaluation_kind: str):
    """Select development or the sealed final-test partition explicitly.

    Split = study.yaml's declaration verbatim: kind group (twins iris-102/143 share
    one group id and always travel together), seed 20260907, 0.20/0.20 — the
    pre-committed fresh seed, disjoint from every study-07 namespace; NO redraw
    under any outcome. ``final_test`` fits the same train-only candidate and
    evaluates the sealed 20 (procedurally fresh only — all 100 values were public
    in study 07's ledger). Band-check role per program.md: the arena is the
    evidence; the seal is the discipline.
    """
    if evaluation_kind not in {"development", "final_test"}:
        raise RuntimeError(f"invalid KLEIN_EVALUATION_KIND={evaluation_kind!r}")
    df = load_prepared(PREPARED)
    y = df[TARGET]
    x_tr, x_dev, x_te, y_tr, y_dev, y_te = three_way_split(
        df,
        y,
        task="classification",
        strategy="group",
        development_size=0.20,
        test_size=0.20,
        seed=20260907,
        groups=df["group_id"],
    )
    columns = families.columns_for(FAMILY)
    g_tr = x_tr["group_id"]
    if evaluation_kind == "development":
        return x_tr[columns], x_dev[columns], y_tr, y_dev, g_tr
    return x_tr[columns], x_te[columns], y_tr, y_te, g_tr


def build_model(y_tr, g_tr):
    # CV families receive group-aware inner splits (twins never straddle an
    # inner boundary — the gate law applied inside the estimators).
    return families.build(FAMILY, y=y_tr, groups=g_tr)


def main() -> None:
    t0 = time.time()
    evaluation_kind = os.environ.get("KLEIN_EVALUATION_KIND")
    if SMOKE:
        evaluation_kind = evaluation_kind or "development"
    missing = [
        name
        for name, value in (
            ("KLEIN_EVALUATION_KIND", evaluation_kind),
            ("KLEIN_EXPERIMENT_ID", EXPERIMENT_ID),
            ("KLEIN_TRACK", TRACK),
        )
        if value is None
    ]
    if missing:
        raise RuntimeError(
            "train.py must be invoked through `klein run-one`. For a pre-run "
            "syntax/shape check use `KLEIN_SMOKE=1 python train.py` — it prints "
            "the canonical block, writes no sidecars or snapshots, and is not "
            "evidence. Missing: " + ", ".join(missing)
        )
    X_tr, X_dev, y_tr, y_dev, g_tr = load_split(evaluation_kind)
    model = build_model(y_tr, g_tr)
    fit_start = time.time()
    model.fit(X_tr, y_tr)
    fit_seconds = time.time() - fit_start
    kleinlib.eval.evaluate(
        model,
        X_dev,
        y_dev,
        exp_id=EXPERIMENT_ID,
        study_dir=".",
        t0=t0,
        fit_seconds=fit_seconds,
        train_n=len(X_tr),
        val_n=len(X_dev),
        metric_name="val_brier",
        metric_goal="lower",
    )


if __name__ == "__main__":
    main()
