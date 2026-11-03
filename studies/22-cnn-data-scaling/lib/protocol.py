"""The FIXED training protocol of every cell — outside the mutable surface.

`analyze.py` is the per-experiment surface and a cell sets only
`CELL["n_train"]`. Everything that decides HOW a cell trains lives here, so the
diff of a cell can change the data budget N and nothing else; a change to this
file is a deliberate, recorded protocol change, never part of a candidate.

The protocol, in one paragraph
------------------------------
The network is a small 3-conv CNN with global average pooling
(:data:`ARCHITECTURE`, 23,946 parameters): two max-pool stages give each conv3
unit an 18x18-pixel receptive field (3 -> 4 -> 8 -> 10 -> 18, stride 4), averaged by
global pooling over a 7x7 grid that tiles the image — the recipe's
two-block variant pools globally at 14x14 after two 3x3 convolutions, which
leaves it a bag of 6x6 local textures. Pixels are divided by 255; no
augmentation, no normalization layer, no dropout, PyTorch's default
initialization. A seed draws a uniformly random subsample of N items from the
fit pool; 10% of it (:func:`inner_size`) is held out as an INNER validation set
and the remaining 90% is trained on with AdamW (lr 1e-3, weight decay 1e-4),
batch 128, for :func:`steps_for` optimizer steps (20 epochs of the 90%, at least
400, at most 12,000). The inner-validation cross-entropy is measured every
:func:`eval_every` steps and at the last step; the checkpoint with the lowest
inner loss is kept in memory and is the one that is scored. Batches are streamed
index-shuffles (`kleinlib.torch_loop.iterate_minibatches`, war story 2) — no
DataLoader, no TensorDataset. Torch runs on 1 thread (TORCH_THREADS).

Sources of randomness (all from the one integer `KLEIN_SEED`): the subsample and
its inner split (``numpy.random.default_rng(seed).permutation``), the minibatch
order (the same generator, continued), and the weight initialization
(``kleinlib.dl.seed_everything(seed, deterministic=True)``). Within one seed the
subsamples are NESTED across N: the N-item subsample is the first N entries of
the seed's permutation of the pool, and its fit set is the first 90% of those, so
fit(N=500) ⊂ fit(N=1,000) ⊂ … for the same seed (common random numbers along the
learning curve). Different seeds draw different permutations, so data-sampling
variance is inside every cell.

Known nondeterminism: CPU float reductions under a different thread count or
oneDNN build can move a loss in its last digits; the replication tolerance, not
bitwise identity, is the bar (`references/compute-and-devices.md`).
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# --- the protocol constants ---------------------------------------------------
ARCHITECTURE = (
    "cnn3-gap: conv3x3(1->16)+ReLU+maxpool2 -> conv3x3(16->32)+ReLU+maxpool2 -> "
    "conv3x3(32->64)+ReLU -> global average pool -> linear(64->10); 23,946 parameters"
)
CHANNELS: tuple[int, int, int] = (16, 32, 64)
N_PARAMETERS = 23_946
N_CLASSES = 10
IMAGE_SHAPE = (28, 28)
PIXEL_SCALE = 255.0                 # pixels / 255; no augmentation, no normalization

OPTIMIZER = "AdamW"
LEARNING_RATE = 1e-3
WEIGHT_DECAY = 1e-4
BATCH_SIZE = 128
EPOCHS = 20                         # of the 90% fit share
MIN_STEPS = 400
MAX_STEPS = 12_000

INNER_VALIDATION_FRACTION = 0.10    # of the N-item subsample, held out for checkpoint selection
EVAL_EVERY_MIN = 50
EVAL_POINTS = 40                    # eval_every = max(EVAL_EVERY_MIN, steps // EVAL_POINTS)

TORCH_THREADS = 1  # 4 is ~2x faster on a quiet machine but 15-30x slower when sibling studies train (instrument report); 1 is robust
SCORE_BATCH = 1_000                 # items per forward pass when scoring (speed only)

#: The sealed cell trains on the whole fit pool (official train = train + development):
#: 60,000 rows minus the 8 development near-copies prepare.py removes (DATA gate).
N_FULL = 59_992

# --- the smoke budget (KLEIN_SMOKE=1 only — a shape check, never evidence) -----
SMOKE_N_TRAIN = 300
SMOKE_STEPS = 30
SMOKE_EVAL_EVERY = 10

# --- the sealed dry run (KLEIN_SEALED_DRYRUN=1): a rehearsal of the PATH, not a measurement ---
# A full-budget training at N=50,000 would preview the extrapolation on development data; the
# rehearsal needs only that every step of the sealed path runs, so it trains this many steps.
DRYRUN_STEPS = 60


def inner_size(n: int) -> int:
    """Items of an N-item subsample held out as the inner validation set."""
    inner = int(round(INNER_VALIDATION_FRACTION * n))
    if inner < 1 or inner >= n:
        raise ValueError(f"N={n} is too small to hold out an inner validation set")
    return inner


def steps_for(n: int) -> int:
    """``max(400, ceil(20 epochs * 0.9N / 128))``, capped at 12,000."""
    n_fit = n - inner_size(n)
    epochs_steps = -(-EPOCHS * n_fit // BATCH_SIZE)  # integer ceil
    return min(MAX_STEPS, max(MIN_STEPS, epochs_steps))


def eval_every(steps: int) -> int:
    """Inner-validation cadence: every ``max(50, steps // 40)`` steps (and the last step)."""
    return max(EVAL_EVERY_MIN, steps // EVAL_POINTS)


def draw_subsample(n_pool: int, n: int, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """``(fit_positions, inner_positions)`` into a pool of ``n_pool`` items.

    The subsample is the first ``n`` entries of one permutation of the pool; its
    first ``n - inner_size(n)`` are trained on and the rest are the inner
    validation set. Consumes exactly one permutation draw from ``rng``.
    """
    if not 1 < n <= n_pool:
        raise ValueError(f"N={n} must lie in (1, {n_pool}] (the fit pool)")
    chosen = rng.permutation(n_pool)[:n]
    n_fit = n - inner_size(n)
    return chosen[:n_fit], chosen[n_fit:]


class ItemStore:
    """The prepared payload, addressed by item id (`data/prepared/images.npy` + `index.csv`)."""

    def __init__(self, prepared_dir: Path) -> None:
        index = pd.read_csv(prepared_dir / "index.csv", dtype={"id": str}, keep_default_na=False)
        self._row = pd.Series(np.arange(len(index)), index=index["id"].to_numpy())
        self._label = index["label"].to_numpy(dtype=np.int64)
        self._images = np.load(prepared_dir / "images.npy", mmap_mode="r")
        if self._images.shape != (len(index), *IMAGE_SHAPE) or self._images.dtype != np.uint8:
            raise ValueError(
                f"images.npy is {self._images.dtype} {self._images.shape}; expected uint8 "
                f"({len(index)}, {IMAGE_SHAPE[0]}, {IMAGE_SHAPE[1]}) — re-run prepare.py"
            )

    def load(self, ids: Sequence[str]) -> tuple[np.ndarray, np.ndarray]:
        """``(x, y)``: float32 (n, 1, 28, 28) in [0, 1] and int64 labels, in ``ids`` order."""
        rows = self._row.loc[list(ids)].to_numpy()
        x = np.asarray(self._images[np.sort(rows)], dtype=np.float32)
        order = np.argsort(np.argsort(rows))  # mmap reads are fastest sorted; restore ids order
        x = x[order] / np.float32(PIXEL_SCALE)
        return x[:, None, :, :], self._label[rows]


def build_model():
    """The fixed network (:data:`ARCHITECTURE`)."""
    from torch import nn

    c1, c2, c3 = CHANNELS
    model = nn.Sequential(
        nn.Conv2d(1, c1, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),   # 28 -> 14
        nn.Conv2d(c1, c2, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),  # 14 -> 7
        nn.Conv2d(c2, c3, 3, padding=1), nn.ReLU(),
        nn.AdaptiveAvgPool2d(1), nn.Flatten(), nn.Linear(c3, N_CLASSES),
    )
    count = sum(p.numel() for p in model.parameters())
    if count != N_PARAMETERS:
        raise RuntimeError(f"the fixed network has {count} parameters, the protocol states {N_PARAMETERS}")
    return model


def _mean_cross_entropy(model, x, y, device) -> float:
    import torch
    from torch import nn

    total = 0.0
    with torch.no_grad():
        for start in range(0, len(x), SCORE_BATCH):
            logits = model(x[start : start + SCORE_BATCH].to(device))
            target = y[start : start + SCORE_BATCH].to(device)
            total += float(nn.functional.cross_entropy(logits, target, reduction="sum"))
    return total / len(x)


def train(
    x_fit: np.ndarray,
    y_fit: np.ndarray,
    x_inner: np.ndarray,
    y_inner: np.ndarray,
    *,
    steps: int,
    every: int,
    rng: np.random.Generator,
    device: Any,
) -> tuple[Any, dict[str, Any]]:
    """Train the fixed network; return it at its best inner-validation checkpoint.

    The caller seeds torch (``seed_everything``) before calling; ``rng`` orders
    the minibatches.
    """
    import torch
    from torch import nn

    from kleinlib.torch_loop import iterate_minibatches

    torch.set_num_threads(TORCH_THREADS)
    model = build_model().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE, weight_decay=WEIGHT_DECAY)
    xt, yt = torch.from_numpy(x_fit), torch.from_numpy(y_fit)
    xi, yi = torch.from_numpy(x_inner), torch.from_numpy(y_inner)

    best_loss, best_step, best_state = float("inf"), 0, None
    evaluations = 0
    step = 0
    started = time.time()
    model.train()
    while step < steps:
        for batch in iterate_minibatches(len(xt), BATCH_SIZE, shuffle=True, generator=rng):
            index = torch.from_numpy(batch)
            optimizer.zero_grad(set_to_none=True)
            loss = nn.functional.cross_entropy(
                model(xt.index_select(0, index).to(device)), yt.index_select(0, index).to(device)
            )
            if not torch.isfinite(loss):
                raise FloatingPointError(f"non-finite training loss at step {step + 1}")
            loss.backward()
            optimizer.step()
            step += 1
            if step % every == 0 or step == steps:
                model.eval()
                inner = _mean_cross_entropy(model, xi, yi, device)
                model.train()
                evaluations += 1
                if not np.isfinite(inner):
                    raise FloatingPointError(f"non-finite inner-validation loss at step {step}")
                if inner < best_loss:
                    best_loss, best_step = inner, step
                    best_state = {k: v.detach().to("cpu", copy=True) for k, v in model.state_dict().items()}
            if step >= steps:
                break
    if best_state is None:  # pragma: no cover - steps >= 1 always evaluates at the last step
        raise RuntimeError("no inner-validation checkpoint was evaluated")
    model.load_state_dict(best_state)
    model.eval()
    return model, {
        "steps": step,
        "best_step": best_step,
        "best_inner_loss": best_loss,
        "inner_evaluations": evaluations,
        "fit_seconds": time.time() - started,
    }


def predict_proba(model, x: np.ndarray, device: Any) -> np.ndarray:
    """Softmax probabilities (float64, rows renormalized to sum to 1)."""
    import torch

    chunks = []
    with torch.no_grad():
        for start in range(0, len(x), SCORE_BATCH):
            logits = model(torch.from_numpy(x[start : start + SCORE_BATCH]).to(device))
            chunks.append(torch.softmax(logits.double(), dim=1).cpu().numpy())
    proba = np.concatenate(chunks)
    return proba / proba.sum(axis=1, keepdims=True)
