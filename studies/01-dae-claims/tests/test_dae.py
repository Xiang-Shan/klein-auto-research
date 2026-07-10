"""Unit tests for the study-01 SwapNoiseDAE (studies/01-dae-claims/dae.py).

Run:  MPLBACKEND=Agg uv run pytest studies/01-dae-claims/tests -q

These are fast, self-contained tests on a synthetic toy frame (no data_hub, no MPS —
device is forced to CPU) that pin the four load-bearing properties of the DAE:

  (a) swap noise corrupts ~p of ELIGIBLE cells and ZERO is_* cells,
  (b) the DAE trains a few epochs and yields a (n, 768) deep-stack rep with std > 0,
  (c) inductive mode never touches the val rows (a fairness-rule canary),
  (d) reconstruct() returns finite values.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import torch

# import the study-local dae.py (studies/01-dae-claims/) — pytest runs from repo root
_STUDY_DIR = Path(__file__).resolve().parents[1]
if str(_STUDY_DIR) not in sys.path:
    sys.path.insert(0, str(_STUDY_DIR))

import dae as dae_mod  # noqa: E402
from dae import SwapNoiseDAE, apply_swap_noise  # noqa: E402

CPU = torch.device("cpu")


def _toy_frame(n: int = 500, seed: int = 0) -> pd.DataFrame:
    """A toy frame with the same STRUCTURE as the prepared claims data:
    continuous numerics, 0/1 ``is_*`` binaries, and string categoricals."""
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        {
            # numerics (eligible for swap noise)
            "num_a": rng.normal(size=n),
            "num_b": rng.gamma(2.0, size=n),
            "num_c": rng.integers(0, 20, size=n).astype(float),
            # is_* binaries (PASSTHROUGH — excluded from swap noise)
            "is_esc": rng.integers(0, 2, size=n),
            "is_tpms": rng.integers(0, 2, size=n),
            "is_speed_alert": rng.integers(0, 2, size=n),
            # string categoricals (eligible; OHE at fit time)
            "region_code": rng.choice(list("ABCDEF"), size=n),
            "fuel_type": rng.choice(["Petrol", "Diesel", "CNG"], size=n),
        }
    )


def test_swap_noise_fraction_and_is_star_untouched():
    """(a) ~p of eligible cells flagged; ZERO is_* cells corrupted."""
    X = _toy_frame(n=600, seed=1)
    rate = 0.2

    d = SwapNoiseDAE(swap_rate=rate, device=CPU)
    d._route_columns(X)

    is_star = [c for c in X.columns if c.startswith("is_")]
    assert d.is_star_cols_ == is_star
    # is_* must NOT be eligible for corruption
    assert all(c not in d.eligible_cols_ for c in is_star)
    assert set(d.eligible_cols_) == {"num_a", "num_b", "num_c", "region_code", "fuel_type"}

    Xc, mask = apply_swap_noise(
        X, d.eligible_cols_, rate=rate, rng=np.random.default_rng(7)
    )
    # ~p fraction of eligible cells flagged (600 rows x 5 cols = 3000 draws → tight)
    assert 0.15 < mask.mean() < 0.25
    # every is_* column is byte-identical (never touched)
    for c in is_star:
        assert np.array_equal(Xc[c].to_numpy(), X[c].to_numpy())


def test_dae_trains_and_representation_shape():
    """(b) trains 3 epochs on 500 rows (CPU), rep is (n, 768), std > 0, finite."""
    X = _toy_frame(n=500, seed=2)
    d = SwapNoiseDAE(swap_rate=0.15, max_epochs=3, device=CPU)
    rep = d.fit_transform(X)

    assert sum(dae_mod.HIDDEN_DIMS) == 768  # deep-stack = concat of 3x256 hidden layers
    assert rep.shape == (500, 768)
    assert np.isfinite(rep).all()
    assert float(rep.std()) > 0.0
    assert d.input_dim_ is not None and d.input_dim_ > 0
    assert d.history_["epochs_run"] >= 1


def test_inductive_mode_never_touches_val():
    """(c) inductive fit sees ONLY train rows; the val frame is left unchanged."""
    X_tr = _toy_frame(n=400, seed=3)
    X_va = _toy_frame(n=150, seed=99)  # disjoint 'val' features
    X_va_before = X_va.copy(deep=True)
    hash_before = int(pd.util.hash_pandas_object(X_va, index=True).sum())

    d = SwapNoiseDAE(swap_rate=0.15, max_epochs=2, device=CPU, fit_mode="inductive")
    d.fit_transform(X_tr)  # val is NOT passed

    # canary 1: the encoder was fit on EXACTLY the train rows (val not concatenated in)
    assert d.n_fit_rows_ == len(X_tr)
    # canary 2: the val frame object is byte-for-byte unchanged (no in-place mutation)
    assert X_va.equals(X_va_before)
    assert int(pd.util.hash_pandas_object(X_va, index=True).sum()) == hash_before

    # transform on val works AFTER fit, without ever having fit on it
    rep_va = d.transform(X_va)
    assert rep_va.shape == (150, 768)

    # positive control: transductive mode DOES fold val features into the fit set,
    # which is exactly why it is a labeled 'Kaggle-style' aside, not the headline
    d2 = SwapNoiseDAE(swap_rate=0.15, max_epochs=2, device=CPU, fit_mode="transductive")
    d2.fit(X_tr, X_transductive=X_va)
    assert d2.n_fit_rows_ == len(X_tr) + len(X_va)


def test_reconstruct_is_finite():
    """(d) reconstruct() returns finite values shaped (n, input_dim)."""
    X = _toy_frame(n=300, seed=4)
    d = SwapNoiseDAE(swap_rate=0.15, max_epochs=2, device=CPU)
    d.fit(X)
    recon = d.reconstruct(X)

    assert recon.shape == (300, d.input_dim_)
    assert np.isfinite(recon).all()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
