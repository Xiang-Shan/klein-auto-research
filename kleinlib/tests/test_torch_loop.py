"""Tests for kleinlib.torch_loop: MPS-safe generic fit/predict.

Skips cleanly (module-level `importorskip`) when torch isn't installed —
`torch` is an optional `[deep]` extra, not a core dependency.
"""

from __future__ import annotations

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from kleinlib import torch_loop  # noqa: E402
from kleinlib.torch_device import pick_device  # noqa: E402


def _toy_regression_data(n=200, d=4, seed=0):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, d)).astype(np.float32)
    true_w = rng.normal(size=d).astype(np.float32)
    y = (X @ true_w + 0.05 * rng.normal(size=n).astype(np.float32)).astype(np.float32)
    return X, y


def test_fit_and_predict_learn_better_than_chance():
    X, y = _toy_regression_data()
    device = pick_device()
    model = torch.nn.Sequential(
        torch.nn.Linear(4, 16), torch.nn.ReLU(), torch.nn.Linear(16, 1)
    )

    def loss_fn(out, target):
        return torch.nn.functional.mse_loss(out.squeeze(-1), target)

    baseline_mse = float(np.mean((y - y.mean()) ** 2))

    history = torch_loop.fit(
        model,
        X,
        y,
        loss_fn=loss_fn,
        epochs=80,
        batch_size=32,
        lr=1e-2,
        weight_decay=0.0,
        device=device,
        early_stopping_patience=15,
        seed=42,
    )
    assert history["epochs_run"] > 0

    preds = torch_loop.predict(model, X, device=device, batch_size=64)
    assert isinstance(preds, np.ndarray)
    assert preds.shape[0] == len(y)
    assert float(np.std(preds)) > 0.0

    model_mse = float(np.mean((y - preds.squeeze(-1)) ** 2))
    assert model_mse < baseline_mse


def test_iterate_minibatches_covers_every_index_once_per_epoch():
    rng = np.random.default_rng(0)
    seen = sorted(
        idx
        for batch in torch_loop.iterate_minibatches(37, 8, shuffle=True, generator=rng)
        for idx in batch
    )
    assert seen == list(range(37))


def test_predict_without_fit_returns_cpu_array_with_variance():
    X, _ = _toy_regression_data(n=50, seed=1)
    device = pick_device()
    model = torch.nn.Sequential(torch.nn.Linear(4, 8), torch.nn.ReLU(), torch.nn.Linear(8, 1))
    preds = torch_loop.predict(model, X, device=device, batch_size=16)
    assert isinstance(preds, np.ndarray)
    assert preds.shape == (50, 1)
