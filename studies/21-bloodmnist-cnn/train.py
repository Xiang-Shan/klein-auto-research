"""The per-candidate training recipe (mutable surface with model.py; recipe cv-classify).

One run of this file is ONE seed of the candidate: `klein run-one` runs every seed
in `entrypoint.seeds` (setting KLEIN_SEED) and decides on the aggregate. Training
chatter may be printed freely before the final block (`entrypoint.printed: block`).
The budget is in optimizer STEPS, so CPU and GPU runs are comparable.
"""

from __future__ import annotations

import os
import time

import numpy as np
import torch

from kleinlib.data import load_items
from kleinlib.dl import report_usage, seed_everything
from kleinlib.eval_multiclass import evaluate_multiclass
from kleinlib.torch_device import pick_device
from kleinlib.torch_loop import iterate_minibatches
from torch import nn

SMOKE = os.environ.get("KLEIN_SMOKE") == "1"
EXPERIMENT_ID = os.environ.get("KLEIN_EXPERIMENT_ID") or ("SMOKE" if SMOKE else None)
SEED = int(os.environ.get("KLEIN_SEED", "0"))

RECIPE = {"steps": 200 if SMOKE else 1500, "batch_size": 64, "lr": 3e-3, "weight_decay": 1e-4, "width": 32}


def load(ids: list[str]) -> tuple[np.ndarray, np.ndarray]:
    import pandas as pd

    index = pd.read_csv("data/prepared/index.csv", dtype={"id": str})
    images = np.load("data/prepared/images.npy", mmap_mode="r")
    rows = index.reset_index().set_index("id").loc[ids, "index"].to_numpy()
    x = np.asarray(images[rows], dtype=np.float32)
    if images.dtype == np.uint8:
        x /= 255.0  # prepare.py keeps the source's uint8 pixels
    if x.ndim == 3:
        x = x[:, None, :, :]  # (N, 1, H, W)
    elif x.shape[-1] in (1, 3, 4):
        x = np.moveaxis(x, -1, 1)
    return x, index.set_index("id").loc[ids, "label"].to_numpy()


def main() -> None:
    if EXPERIMENT_ID is None:
        raise SystemExit("run through `klein run-one` (or KLEIN_SMOKE=1 for a shape check)")
    t0 = time.time()
    seed_everything(SEED)
    fit_ids, eval_ids = load_items()
    x_fit, y_fit = load(fit_ids)
    x_eval, y_eval = load(eval_ids)
    classes = np.unique(np.concatenate([y_fit, y_eval]))
    device = pick_device()
    model = nn.Sequential(nn.Flatten(), nn.Linear(int(np.prod(x_fit.shape[1:])), len(classes))).to(device)  # P1: linear softmax on flattened pixels
    optimizer = torch.optim.AdamW(model.parameters(), lr=RECIPE["lr"], weight_decay=RECIPE["weight_decay"])
    loss_fn = torch.nn.CrossEntropyLoss()
    xt, yt = torch.from_numpy(x_fit), torch.from_numpy(y_fit.astype(np.int64))
    rng = np.random.default_rng(SEED)
    step, fit_start = 0, time.time()
    while step < RECIPE["steps"]:
        for batch in iterate_minibatches(len(xt), RECIPE["batch_size"], shuffle=True, generator=rng):
            optimizer.zero_grad()
            loss = loss_fn(model(xt[batch].to(device)), yt[batch].to(device))
            loss.backward()
            optimizer.step()
            step += 1
            if step % 250 == 0:
                print(f"step: {step} loss: {loss.item():.4f}")  # chatter: outside the final block
            if step >= RECIPE["steps"]:
                break
    model.eval()
    with torch.no_grad():
        proba = torch.softmax(model(torch.from_numpy(x_eval).to(device)), dim=1).cpu().numpy().astype(np.float64)
    proba /= proba.sum(axis=1, keepdims=True)
    report_usage(steps=step)
    evaluate_multiclass(
        y_eval,
        proba,
        labels=classes.tolist(),
        exp_id=EXPERIMENT_ID,
        metric_name="val_macro_f1",
        t0=t0,
        fit_seconds=time.time() - fit_start,
        train_n=len(fit_ids),
        extra={"steps": step, "seed": SEED},
        study_dir=".",
    )


if __name__ == "__main__":
    main()
