#!/usr/bin/env python3
"""Rebuild the local E3 DAE caches required by the committed Study 01 state.

The executed v0.1 ledger is an immutable exhibit and its model payloads are not
committed.  A fresh clone therefore runs this command once before ``train.py``:

    uv run python bootstrap_caches.py

The defaults reproduce the canonical E3 recipe (inductive swap-rate 0.15,
seed 42, full prepared dataset).  The test-only knobs make the same path cheap
to exercise on a small CPU fixture without claiming reference metrics.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
import torch

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import dae  # noqa: E402

import kleinlib  # noqa: E402

DEFAULT_PREPARED = _HERE / "data/prepared/insurance_claims_prepared.csv"
TARGET = "claim_status"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _pick_device(name: str) -> torch.device:
    if name == "auto":
        if torch.backends.mps.is_available() and torch.backends.mps.is_built():
            return torch.device("mps")
        if torch.cuda.is_available():
            return torch.device("cuda")
        return torch.device("cpu")
    device = torch.device(name)
    if device.type == "mps" and not torch.backends.mps.is_available():
        raise RuntimeError("MPS requested but unavailable")
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    return device


def build_caches(
    prepared: Path,
    output_dir: Path,
    *,
    max_epochs: int,
    limit_rows: int | None,
    device_name: str,
) -> dict[str, object]:
    """Fit the canonical E3 encoder and write relocatable local cache payloads."""
    X, y = kleinlib.data.load_xy(prepared, TARGET)
    if limit_rows is not None:
        if limit_rows < 20:
            raise ValueError("--limit-rows must be at least 20")
        X, y = X.iloc[:limit_rows].copy(), y.iloc[:limit_rows].copy()
    X_tr, X_va, _y_tr, _y_va = kleinlib.data.fixed_split(X, y)

    device = _pick_device(device_name)
    model = dae.SwapNoiseDAE(
        swap_rate=0.15,
        seed=42,
        max_epochs=max_epochs,
        device=device,
    )
    model.fit(X_tr)
    if model.fit_mode != "inductive" or model.n_fit_rows_ != len(X_tr):
        raise RuntimeError("fairness rule violated: DAE did not fit exactly the train fold")

    model.net_ = model.net_.to(torch.device("cpu"))
    model.device_ = torch.device("cpu")
    rep_tr, rep_va = model.transform(X_tr), model.transform(X_va)
    if not np.isfinite(rep_tr).all() or not np.isfinite(rep_va).all():
        raise RuntimeError("non-finite representation generated")

    output_dir.mkdir(parents=True, exist_ok=True)
    dae_path = output_dir / "dae_e3_swap015.cache.pkl"
    reps_path = output_dir / "reps_e3_swap015.cache.pkl"
    manifest_path = output_dir / "e3_cache_manifest.json"
    joblib.dump(model, dae_path)
    joblib.dump(
        {
            "rep_tr": rep_tr,
            "rep_va": rep_va,
            "swap_rate": 0.15,
            "input_dim": model.input_dim_,
            "n_fit_rows": model.n_fit_rows_,
            "history": model.history_,
        },
        reps_path,
    )

    lock_path = _ROOT / "uv.lock"
    manifest: dict[str, object] = {
        "schema_version": 1,
        "legacy_study": "01-dae-claims",
        "recipe": "E3 inductive SwapNoiseDAE swap_rate=0.15 seed=42",
        "created_utc": datetime.now(UTC).isoformat(),
        "prepared_path": str(prepared.resolve()),
        "prepared_sha256": _sha256(prepared),
        "uv_lock_sha256": _sha256(lock_path) if lock_path.exists() else None,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "requested_device": device_name,
        "fit_device": str(device),
        "max_epochs": max_epochs,
        "limit_rows": limit_rows,
        "train_rows": len(X_tr),
        "validation_rows": len(X_va),
        "representation_shape_train": list(rep_tr.shape),
        "representation_shape_validation": list(rep_va.shape),
        "artifacts": {
            dae_path.name: {"sha256": _sha256(dae_path), "bytes": dae_path.stat().st_size},
            reps_path.name: {"sha256": _sha256(reps_path), "bytes": reps_path.stat().st_size},
        },
        "reference_metric_claimed": (
            prepared.resolve() == DEFAULT_PREPARED.resolve()
            and limit_rows is None
            and max_epochs == dae.MAX_EPOCHS
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, default=DEFAULT_PREPARED)
    parser.add_argument("--output-dir", type=Path, default=_HERE / "models")
    parser.add_argument("--max-epochs", type=int, default=dae.MAX_EPOCHS)
    parser.add_argument("--limit-rows", type=int)
    parser.add_argument("--device", default="auto", choices=("auto", "cpu", "mps", "cuda"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.prepared.exists():
        raise FileNotFoundError(
            f"prepared data missing: {args.prepared}. Run `uv run python prepare.py` first."
        )
    manifest = build_caches(
        args.prepared,
        args.output_dir,
        max_epochs=args.max_epochs,
        limit_rows=args.limit_rows,
        device_name=args.device,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    print("next: uv run python train.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
