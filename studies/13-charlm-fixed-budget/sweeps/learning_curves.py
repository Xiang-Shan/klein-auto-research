"""Validation loss against optimizer steps, for the anchor and for the incumbent.

The ledger runs record ONE number each — the validation loss at step 2000 — because
that is what the contract's budget is about. The ml-research profile also asks for the
curve, and a curve cannot be reconstructed after the fact, so it is measured here as a
registered MEASUREMENT sweep: two trials, one per recipe, each re-training from scratch
and evaluating the full validation tiling at a fixed ladder of step counts.

This promotes no winner and writes no `results.tsv` row (`references/sweep-rules.md`
carve-out). Its purpose is descriptive: it shows WHERE in the budget the cosine
schedule earns its 3.3 floors, which the endpoint numbers alone cannot say.

Both recipes are rebuilt here from the immutable `verify.py` architecture and a loop
written out in this file — the same construction `sweeps/noise_floor.py` uses — so
editing the mutable surface cannot change what the curves describe. The final points
are therefore a second, independent estimate of each recipe's endpoint; they will not
match the ledger runs digit for digit, because a full re-execution of the same recipe
at the same seed moves about 0.001 nats on this backend (`rep:E0001@…`).

Writes `tables/learning_curves.tsv` (recipe, step, val_nats_per_char, val_bits_per_char)
and a two-row sidecar carrying each recipe's endpoint.
"""

from __future__ import annotations

import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kleinlib.data import load_partition  # noqa: E402
from kleinlib.torch_device import pick_device  # noqa: E402
from verify import (  # noqa: E402
    EVAL_CONTEXT,
    VOCAB_SIZE,
    CharTransformer,
    load_tokens,
    partition_range,
    score_model,
    windows,
)

SEED = 20260903
MAX_STEPS = 2000
BATCH = 32
LR = 3.0e-3
#: Where the curve is sampled. Dense early, where a schedule difference shows.
LADDER = (25, 50, 100, 150, 200, 300, 400, 500, 600, 800, 1000, 1200, 1400, 1600, 1800, 2000)

RECIPES = {
    # The E0001 anchor: a constant learning rate.
    "anchor": {"schedule": "constant", "lr_final_frac": 1.0},
    # The E0006 incumbent: cosine decay to 10% of peak.
    "cosine": {"schedule": "cosine", "lr_final_frac": 0.1},
}


def _curve(recipe: str) -> list[tuple[int, float]]:
    spec = RECIPES[recipe]
    X_fit, X_eval, y_fit, y_eval = load_partition("development", study_dir=".", echo=False)
    tokens = load_tokens()
    fit_low, fit_high = partition_range(X_fit, y_fit)
    eval_low, eval_high = partition_range(X_eval, y_eval)
    x_eval, y_eval_windows = windows(tokens, eval_low, eval_high)

    device = pick_device()
    torch.manual_seed(SEED)
    net = CharTransformer(
        vocab_size=VOCAB_SIZE,
        n_layer=4,
        n_head=4,
        n_embd=128,
        block_size=EVAL_CONTEXT,
        tie_weights=False,
    ).to(device)
    optimizer = torch.optim.AdamW(
        net.parameters(), lr=LR, betas=(0.9, 0.99), weight_decay=0.1
    )
    rng = np.random.default_rng(SEED)
    span = fit_high - fit_low - EVAL_CONTEXT - 1
    final_frac = float(spec["lr_final_frac"])
    points: list[tuple[int, float]] = []
    net.train()
    for step in range(MAX_STEPS):
        if spec["schedule"] == "cosine":
            progress = step / max(1, MAX_STEPS)
            scale = final_frac + (1.0 - final_frac) * 0.5 * (1.0 + math.cos(math.pi * progress))
        else:
            scale = 1.0
        for group in optimizer.param_groups:
            group["lr"] = LR * scale
        offsets = fit_low + rng.integers(0, span, size=BATCH)
        xb = np.stack([tokens[s : s + EVAL_CONTEXT] for s in offsets]).astype(np.int64)
        yb = np.stack([tokens[s + 1 : s + 1 + EVAL_CONTEXT] for s in offsets]).astype(np.int64)
        logits = net(torch.from_numpy(xb).to(device))
        loss = F.cross_entropy(
            logits.reshape(-1, logits.shape[-1]),
            torch.from_numpy(yb).to(device).reshape(-1),
        )
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()
        if (step + 1) in LADDER:
            points.append((step + 1, score_model(net, device, x_eval, y_eval_windows)))
            net.train()
    return points


def main() -> int:
    from kleinlib.sweep import SweepRunner

    curves: dict[str, list[tuple[int, float]]] = {}

    def trial(params: dict) -> dict:
        t0 = time.time()
        name = str(params["recipe"])
        curves[name] = _curve(name)
        return {
            "primary_metric": float(curves[name][-1][1]),
            "status": "ok",
            "wall_seconds": time.time() - t0,
        }

    SweepRunner(
        "learning_curves",
        ".",
        trial,
        [{"recipe": name} for name in RECIPES],
        metric_goal="lower",
        overwrite=True,
    ).run()

    rows = [
        {
            "recipe": recipe,
            "step": step,
            "val_nats_per_char": round(value, 6),
            "val_bits_per_char": round(value / math.log(2), 6),
        }
        for recipe, points in curves.items()
        for step, value in points
    ]
    Path("tables").mkdir(exist_ok=True)
    pd.DataFrame(rows).to_csv("tables/learning_curves.tsv", sep="\t", index=False)
    for recipe, points in curves.items():
        print(f"{recipe}: {points[0][0]} steps -> {points[0][1]:.6f} … "
              f"{points[-1][0]} steps -> {points[-1][1]:.6f} nats")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
