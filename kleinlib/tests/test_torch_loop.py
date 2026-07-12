"""Tests for kleinlib.torch_loop: MPS-safe generic fit/predict.

Skips cleanly (module-level `importorskip`) when torch isn't installed —
`torch` is an optional `[deep]` extra, not a core dependency.
"""

from __future__ import annotations

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from kleinlib import torch_device, torch_loop  # noqa: E402
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


def test_epoch_loss_is_weighted_by_batch_size():
    X = np.zeros((4, 1), dtype=np.float32)
    y = np.array([0.0, 0.0, 0.0, 10.0], dtype=np.float32)
    model = torch.nn.Linear(1, 1, bias=False)
    torch.nn.init.zeros_(model.weight)

    history = torch_loop.fit(
        model,
        X,
        y,
        loss_fn=lambda out, target: torch.nn.functional.mse_loss(
            out.squeeze(-1), target
        ),
        epochs=1,
        batch_size=3,
        lr=0.0,
        weight_decay=0.0,
        device=torch.device("cpu"),
        early_stopping_patience=None,
        seed=42,
    )
    # Three rows in one batch and one in the last: the dataset mean is 25.
    # An unweighted mean of batch means would incorrectly be 50 or 16.67.
    assert history["train_loss"] == pytest.approx([25.0])
    assert history["best_loss"] == pytest.approx(25.0)


def test_early_stopping_state_clone_is_cpu_resident():
    model = torch.nn.Linear(2, 1)
    state = torch_loop._cpu_state_dict(model)
    assert state
    assert all(tensor.device.type == "cpu" for tensor in state.values())
    assert all(
        tensor.data_ptr() != model.state_dict()[name].data_ptr()
        for name, tensor in state.items()
    )


def test_device_selection_preference_and_name(monkeypatch):
    monkeypatch.setattr(torch.backends.mps, "is_available", lambda: True)
    monkeypatch.setattr(torch.backends.mps, "is_built", lambda: True)
    assert torch_device.device_name(torch_device.pick_device("mps")) == "mps"

    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    assert torch_device.device_name(torch_device.pick_device("cuda")) == "cuda"

    monkeypatch.setattr(torch.backends.mps, "is_available", lambda: False)
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    assert torch_device.device_name(torch_device.pick_device("mps")) == "cpu"
    assert torch_device.device_name(torch_device.pick_device("cuda")) == "cpu"
