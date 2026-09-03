"""Phase 0 metrology: the two floors this study is allowed to quote.

Two recipes, two estimands, one script, five training runs. They answer
different questions and only one of them may ever become a keep bar:

* ``fit_noise`` (recipe ``seed-sweep``, estimand ``fit-noise``, k = 5) trains
  the ANCHOR recipe five times on the same contract partition, changing nothing
  but the seed, and records the five validation losses. It says how much the FIT
  moves. It is provenance, never the bar — `kleinlib.noise_floor.block_key`
  records a fit-noise estimand under ``fit_noise:`` and emits no
  ``minimum_delta`` line for it, deliberately.

* ``paired_floor`` (method ``seed-pair-difference``, estimand
  ``paired-comparison``, k = 10) takes the five checkpoints the first recipe
  saved and, for each of the ten unordered pairs (i < j), RE-SCORES both on the
  identical validation windows and records the paired mean difference
  ``L_i - L_j``. That difference is exactly the quantity a candidate-versus-
  anchor comparison produces, so its spread is what a keep must clear. It sets
  ``minimum_delta`` through a consult re-record.

Why not a split lottery? Because this study never re-draws its split: the
partitions are contiguous ranges of an ordered corpus fixed by the contract, and
every candidate is measured on exactly the same validation characters. The
spread of a re-drawn validation block would be a number about a counterfactual
the study never runs (`scouting_ledger.md`, Retirements).

The anchor is rebuilt HERE — architecture imported from the immutable
``verify.py``, training loop written out below — rather than imported from
``train.py``, so that editing the mutable surface can never silently change what
the floor was measured on. The two loops are init-identical by construction: the
model is built on CPU under ``torch.manual_seed(seed)`` and the parameter-owning
modules are created in the same order, so the same seed gives the same initial
weights and the same batch sequence in both.

Neither recipe touches ``results.tsv``: a measurement sweep promotes no winner
(`references/sweep-rules.md`) and is made citable with ``klein sweep register``.
"""

from __future__ import annotations

import itertools
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kleinlib.data import load_partition, split_fingerprint  # noqa: E402
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

#: The ANCHOR recipe, written out here so the floor is a fixed target.
SEEDS = (1, 2, 3, 4, 5)
ANCHOR = {
    "n_layer": 4,
    "n_head": 4,
    "n_embd": 128,
    "block_size": EVAL_CONTEXT,
    "tie_weights": False,
    "max_steps": 2000,
    "batch_size": 32,
    "lr": 3.0e-3,
    "weight_decay": 0.1,
    "beta1": 0.9,
    "beta2": 0.99,
}
CHECKPOINTS = Path("models")


def _development():
    X_fit, X_eval, y_fit, y_eval = load_partition("development", study_dir=".", echo=False)
    tokens = load_tokens()
    fit_low, fit_high = partition_range(X_fit, y_fit)
    eval_low, eval_high = partition_range(X_eval, y_eval)
    x, y = windows(tokens, eval_low, eval_high)
    return tokens, (fit_low, fit_high), (x, y), split_fingerprint(X_fit, X_eval)


def _train_anchor(seed: int):
    tokens, (fit_low, fit_high), (x_eval, y_eval), fingerprint = _development()
    device = pick_device()
    torch.manual_seed(seed)
    net = CharTransformer(
        vocab_size=VOCAB_SIZE,
        n_layer=ANCHOR["n_layer"],
        n_head=ANCHOR["n_head"],
        n_embd=ANCHOR["n_embd"],
        block_size=ANCHOR["block_size"],
        tie_weights=ANCHOR["tie_weights"],
    ).to(device)
    optimizer = torch.optim.AdamW(
        net.parameters(),
        lr=ANCHOR["lr"],
        betas=(ANCHOR["beta1"], ANCHOR["beta2"]),
        weight_decay=ANCHOR["weight_decay"],
    )
    rng = np.random.default_rng(seed)
    context = int(ANCHOR["block_size"])
    span = fit_high - fit_low - context - 1
    net.train()
    for _ in range(int(ANCHOR["max_steps"])):
        offsets = fit_low + rng.integers(0, span, size=int(ANCHOR["batch_size"]))
        xb = np.stack([tokens[s : s + context] for s in offsets]).astype(np.int64)
        yb = np.stack([tokens[s + 1 : s + 1 + context] for s in offsets]).astype(np.int64)
        logits = net(torch.from_numpy(xb).to(device))
        loss = F.cross_entropy(
            logits.reshape(-1, logits.shape[-1]),
            torch.from_numpy(yb).to(device).reshape(-1),
        )
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()
    val = score_model(net, device, x_eval, y_eval)
    CHECKPOINTS.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "config": {
                "vocab_size": VOCAB_SIZE,
                "n_layer": ANCHOR["n_layer"],
                "n_head": ANCHOR["n_head"],
                "n_embd": ANCHOR["n_embd"],
                "block_size": ANCHOR["block_size"],
                "tie_weights": ANCHOR["tie_weights"],
                "dropout": 0.0,
            },
            "state_dict": {k: v.detach().cpu() for k, v in net.state_dict().items()},
            "steps": int(ANCHOR["max_steps"]),
            "evaluation_kind": "development",
            "split_fingerprint": fingerprint,
            "reported_val_loss": val,
            "recipe": "anchor",
            "seed": seed,
            "lr": ANCHOR["lr"],
            "batch_size": ANCHOR["batch_size"],
            "warmup_steps": 0,
        },
        CHECKPOINTS / f"floor_seed{seed}.pt",
    )
    return val


def _fit_noise_trial(params: dict) -> dict:
    """Same rows, same recipe, a different seed — how much does the FIT move?"""
    t0 = time.time()
    val = _train_anchor(int(params["seed"]))
    return {"primary_metric": float(val), "status": "ok", "wall_seconds": time.time() - t0}


def _paired_trial(params: dict) -> dict:
    """Two seeds of the SAME recipe, re-scored on identical windows: L_i - L_j.

    The sign is fixed by the seed order (i < j), never by the outcome, so the
    ten values are a spread around zero and not a folded absolute deviation.
    """
    t0 = time.time()
    _, _, (x_eval, y_eval), _ = _development()
    device = pick_device()
    losses = []
    for seed in (int(params["seed_i"]), int(params["seed_j"])):
        checkpoint = torch.load(
            CHECKPOINTS / f"floor_seed{seed}.pt", map_location="cpu", weights_only=True
        )
        config = checkpoint["config"]
        net = CharTransformer(
            vocab_size=int(config["vocab_size"]),
            n_layer=int(config["n_layer"]),
            n_head=int(config["n_head"]),
            n_embd=int(config["n_embd"]),
            block_size=int(config["block_size"]),
            tie_weights=bool(config["tie_weights"]),
        ).to(device)
        net.load_state_dict(checkpoint["state_dict"], strict=True)
        losses.append(score_model(net, device, x_eval, y_eval))
    return {
        "primary_metric": float(losses[0] - losses[1]),
        "status": "ok",
        "wall_seconds": time.time() - t0,
    }


RECIPES = {
    "fit_noise": (_fit_noise_trial, [{"seed": s} for s in SEEDS]),
    "paired_floor": (
        _paired_trial,
        [{"seed_i": i, "seed_j": j} for i, j in itertools.combinations(SEEDS, 2)],
    ),
}


def main() -> int:
    from kleinlib.sweep import SweepRunner

    which = sys.argv[1] if len(sys.argv) > 1 else "fit_noise"
    trial, params_list = RECIPES[which]
    summary = SweepRunner(
        which, ".", trial, params_list, metric_goal="lower", overwrite=True
    ).run()
    values = [t.primary_metric for t in summary.trials if t.status == "ok"]
    print(f"{which}: k={len(values)} ok trials")
    for t in summary.trials:
        print(f"  {t.params} -> {t.primary_metric:.6f} ({t.wall_seconds:.1f}s, {t.status})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
