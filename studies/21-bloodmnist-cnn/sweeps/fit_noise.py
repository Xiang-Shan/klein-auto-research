"""Phase-0 fit noise: the anchor configuration on three further seed blocks.

Estimand fit-noise (provenance, never the keep bar). One trial = one block of three
seeds; its primary_metric is the block's mean development macro-F1 (the same aggregate
the notary decides on). The recipe is train.py's own (RECIPE, SmallCNN, loop copied
verbatim) at the committed anchor surface; macro-F1 uses the same rule as
kleinlib.eval_multiclass. Nothing is written to results/state; the sidecar is the record.
Run from the study directory.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import torch

STUDY = Path(__file__).resolve().parents[1]
os.chdir(STUDY)
sys.path.insert(0, str(STUDY))

from kleinlib.data import load_items  # noqa: E402
from kleinlib.dl import seed_everything  # noqa: E402
from kleinlib.sweep import SweepRunner  # noqa: E402
from kleinlib.torch_device import pick_device  # noqa: E402
from kleinlib.torch_loop import iterate_minibatches  # noqa: E402

import train  # noqa: E402  (the anchor surface; importing has no side effects)
from model import SmallCNN  # noqa: E402

BLOCKS = [[10, 11, 12], [20, 21, 22], [30, 31, 32]]


def one_seed(seed: int, data) -> float:
    x_fit, y_fit, x_eval, y_eval, classes = data
    R = train.RECIPE
    seed_everything(seed)
    device = pick_device()
    model = SmallCNN(x_fit.shape[1], len(classes), R["width"]).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=R["lr"], weight_decay=R["weight_decay"])
    loss_fn = torch.nn.CrossEntropyLoss()
    xt, yt = torch.from_numpy(x_fit), torch.from_numpy(y_fit.astype(np.int64))
    rng = np.random.default_rng(seed)
    step = 0
    while step < R["steps"]:
        for batch in iterate_minibatches(len(xt), R["batch_size"], shuffle=True, generator=rng):
            opt.zero_grad()
            loss_fn(model(xt[batch].to(device)), yt[batch].to(device)).backward()
            opt.step()
            step += 1
            if step >= R["steps"]:
                break
    model.eval()
    with torch.no_grad():
        pred = model(torch.from_numpy(x_eval).to(device)).argmax(1).cpu().numpy()
    k = len(classes)
    M = np.zeros((k, k))
    np.add.at(M, (np.searchsorted(classes, y_eval), pred), 1)
    tp = np.diag(M)
    den = 2 * tp + (M.sum(0) - tp) + (M.sum(1) - tp)
    f1 = np.divide(2 * tp, den, out=np.zeros(k), where=den > 0)
    return float(f1[M.sum(1) > 0].mean())


def main() -> None:
    assert train.RECIPE == {"steps": 1500, "batch_size": 64, "lr": 3e-3, "weight_decay": 1e-4, "width": 32}
    fit_ids, eval_ids = load_items()
    x_fit, y_fit = train.load(fit_ids)
    x_eval, y_eval = train.load(eval_ids)
    classes = np.unique(np.concatenate([y_fit, y_eval]))
    data = (x_fit, y_fit, x_eval, y_eval, classes)

    def trial(params):
        vals = []
        for s in params["seeds"]:
            vals.append(one_seed(s, data))
            print(f"seed {s}: val_macro_f1 {vals[-1]:.6f}", flush=True)
        return {"primary_metric": float(np.mean(vals)), "status": "ok"}

    SweepRunner("fit_noise", study_dir=STUDY, trial_fn=trial,
                params_list=[{"seeds": b} for b in BLOCKS], metric_goal="higher").run()


if __name__ == "__main__":
    main()
