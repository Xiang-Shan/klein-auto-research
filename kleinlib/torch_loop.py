"""Generic MPS-safe train/predict loop for torch models, Klein Auto Research.

Adapted from the model-survey campaign's ``lib/ftt_runner.py``, which was
FT-Transformer-specific (dual numeric/categorical tensor inputs, a
`rtdl_revisiting_models` dependency). This module extracts the generic,
model-agnostic pieces every torch model in a Klein study needs: index-shuffle
minibatching, and a `(model, X, y) -> fit / predict` pair for any model whose
`forward` takes a single feature tensor (an MLP, an autoencoder, a linear
probe head, ...). Multi-input architectures like FT-Transformer still need
their own runner in the study's own `lib/` — see `ftt_runner.py` for the
pattern this module generalizes.

Why no `torch.utils.data.DataLoader` / `TensorDataset` (the war story): on
Apple Silicon (the MPS backend), the campaign found that DataLoader +
TensorDataset silently collapsed every prediction to a near-constant value —
no error, no warning, just a wrecked val_auc that only surfaced because
`kleinlib.eval.evaluate`'s `min_proba_std` guard caught it downstream.
Plain-numpy index-shuffle batching (`iterate_minibatches` below — a shuffled
index array, sliced against tensors already resident on-device) sidesteps
whatever MPS/DataLoader interaction caused the collapse. Every torch training
loop in this project uses this pattern instead of DataLoader, full stop.

None of the functions in this module have default values for their
keyword-only parameters — every call site must state its epoch count,
batch size, device, and seed explicitly. That is a deliberate reproducibility
choice (thin, explicit train.py diffs), not an oversight.
"""

from __future__ import annotations

from typing import Any, Callable, Iterator

import numpy as np
import torch
import torch.nn as nn

RANDOM_SEED_DEFAULT = 42


def iterate_minibatches(
    n: int,
    batch_size: int,
    *,
    shuffle: bool,
    generator: np.random.Generator | None,
) -> Iterator[np.ndarray]:
    """Yield index arrays covering `range(n)` in batches of `batch_size`.

    Pure-numpy index shuffle — the MPS-safe alternative to
    `DataLoader`/`TensorDataset` (see module docstring). Pass a seeded
    `np.random.Generator` for reproducible shuffling; pass `None` to fall
    back to the global `np.random` state (fine for `shuffle=False`, or when
    the caller has already seeded globally via `np.random.seed`).
    """
    idx = np.arange(n)
    if shuffle:
        (generator if generator is not None else np.random).shuffle(idx)
    for start in range(0, n, batch_size):
        yield idx[start : start + batch_size]


def fit(
    model: nn.Module,
    X: np.ndarray,
    y: np.ndarray,
    *,
    loss_fn: Callable[[torch.Tensor, torch.Tensor], torch.Tensor],
    epochs: int,
    batch_size: int,
    lr: float,
    weight_decay: float,
    device: torch.device,
    early_stopping_patience: int | None,
    seed: int,
) -> dict[str, Any]:
    """Train `model` in place with AdamW + index-shuffle batching.

    `loss_fn(model_output, target_batch)` receives both tensors exactly as
    produced by `model(Xt[batch])` and `yt[batch]` — any shape reconciliation
    (e.g. squeezing a trailing singleton dimension for a scalar-output head)
    is the caller's responsibility, so this stays correct for both
    single-output heads and multi-dim outputs (e.g. autoencoder
    reconstructions).

    Early stopping (when `early_stopping_patience` is not None) tracks the
    *training* loss plateau — this function takes no validation split, by
    design, to keep it a simple, composable primitive. Callers that need
    validation-based early stopping should drive their own epoch loop using
    this module's `iterate_minibatches` plus `predict`, the way
    `ftt_runner.py` drives FT-Transformer's.

    Mutates `model`'s weights in place (restoring the best-training-loss
    epoch's weights on early stop) and returns a small history dict:
    `{"train_loss": [...], "best_epoch": int, "epochs_run": int}`.
    """
    torch.manual_seed(seed)
    np.random.seed(seed)
    if device.type == "mps":
        torch.mps.manual_seed(seed)

    model.to(device)
    optim = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)

    Xt = torch.as_tensor(np.asarray(X), dtype=torch.float32, device=device)
    yt = torch.as_tensor(np.asarray(y), dtype=torch.float32, device=device)
    n = Xt.shape[0]
    rng = np.random.default_rng(seed)

    train_losses: list[float] = []
    best_loss = float("inf")
    best_state: dict[str, torch.Tensor] | None = None
    best_epoch = -1
    bad_epochs = 0

    for epoch in range(epochs):
        model.train()
        epoch_losses = []
        for batch_idx in iterate_minibatches(
            n, batch_size, shuffle=True, generator=rng
        ):
            b = torch.as_tensor(batch_idx, device=device)
            optim.zero_grad()
            out = model(Xt[b])
            loss = loss_fn(out, yt[b])
            loss.backward()
            optim.step()
            epoch_losses.append(float(loss.detach().cpu()))

        mean_loss = float(np.mean(epoch_losses))
        train_losses.append(mean_loss)

        if mean_loss < best_loss - 1e-6:
            best_loss = mean_loss
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
            best_epoch = epoch
            bad_epochs = 0
        else:
            bad_epochs += 1
            if (
                early_stopping_patience is not None
                and bad_epochs >= early_stopping_patience
            ):
                break

    if best_state is not None:
        model.load_state_dict(best_state)

    return {
        "train_loss": train_losses,
        "best_epoch": best_epoch,
        "epochs_run": len(train_losses),
    }


def predict(
    model: nn.Module,
    X: np.ndarray,
    *,
    device: torch.device,
    batch_size: int,
) -> np.ndarray:
    """Run `model` over `X` in batches; always returns CPU numpy.

    The CPU-return guarantee matters on MPS: leaving tensors device-resident
    across a study script's control flow risks a silent device-mismatch bug
    downstream (e.g. handing a Tensor to an sklearn metric). This detaches to
    CPU numpy before returning, every time.
    """
    model.to(device)
    model.eval()
    Xt = torch.as_tensor(np.asarray(X), dtype=torch.float32, device=device)
    n = Xt.shape[0]
    outputs = []
    with torch.no_grad():
        for batch_idx in iterate_minibatches(n, batch_size, shuffle=False, generator=None):
            b = torch.as_tensor(batch_idx, device=device)
            out = model(Xt[b])
            outputs.append(out.detach().cpu().numpy())
    return np.concatenate(outputs, axis=0)
