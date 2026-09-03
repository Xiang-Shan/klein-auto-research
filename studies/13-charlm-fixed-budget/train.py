"""The recipe half of the mutable surface — the whole per-experiment diff.

One candidate = one idea, expressed as `RECIPE` here and/or `CONFIG` in
`model.py`, and nothing else. Everything below the recipe block is fixed
machinery.

What this script does NOT do
----------------------------
It does not decide anything. It trains for exactly `max_steps` optimizer steps,
saves a checkpoint, prints its own honest estimate of the validation loss beside
the `checkpoint:` line, and stops. `klein run-one` then runs `verify.py` as a
separate process, re-derives the loss from the saved checkpoint, and it is THAT
number the disposition uses. This script's number exists only so the two can be
compared: a disagreement beyond 0.01 nats is a crash, and the searcher is not
the one to ask which of them is right.

The validation sweep here is written out independently rather than imported from
`verify.py` on purpose. Two implementations that agree are evidence; one
implementation compared with itself is not.

The partition comes from `kleinlib.data.load_partition`, which prints the
`split_fingerprint:` the notary checks against the DATA gate — and, under
`KLEIN_SEALED_DRYRUN=1`, hands back the development rows and prints
`sealed_dryrun: 1` so the mandatory rehearsal spends no seal.
"""

from __future__ import annotations

import math
import os
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

import model as arch
from kleinlib.data import load_partition, split_fingerprint
from kleinlib.eval import evaluate_scalar
from kleinlib.torch_device import pick_device

# --- the candidate: the whole per-experiment diff surface -------------------
RECIPE: dict[str, object] = {
    "name": "cosine_warmup200",
    # E0007: ONE change from the E0006 incumbent — a 200-step linear warmup
    # added to the cosine decay, the pairing warmup is normally used in. Tests
    # whether E0002's verdict on warmup was a verdict on warmup or an artifact
    # of pairing it with a constant learning rate. No registered prediction.
    "seed": 20260903,
    "max_steps": 2000,      # the BUDGET. The verifier reads it back out of the
                            # checkpoint and the `steps` guardrail pins it.
    "batch_size": 32,
    "lr": 3.0e-3,
    "warmup_steps": 200,
    "schedule": "cosine",   # "constant" | "cosine"
    "lr_final_frac": 0.1,
    "weight_decay": 0.1,
    "beta1": 0.9,
    "beta2": 0.99,
}
# ---------------------------------------------------------------------------

SMOKE = os.environ.get("KLEIN_SMOKE") == "1"
DRY_RUN = os.environ.get("KLEIN_SEALED_DRYRUN") == "1"
EXPERIMENT_ID = os.environ.get("KLEIN_EXPERIMENT_ID") or ("SMOKE" if SMOKE else None)
TRACK = os.environ.get("KLEIN_TRACK") or ("primary" if SMOKE else None)

#: Windows per forward pass while scoring. Speed only: the loss is a sum over
#: every predicted character and does not depend on the grouping.
SCORE_BATCH = 64
TOKENS_PATH = Path("data/prepared/tokens.bin")
MODELS = Path("models")


def character_range(X, lengths) -> tuple[int, int]:
    """The contiguous character range of a partition of blocks."""
    starts = np.asarray(X["start_char"], dtype=np.int64)
    low = int(starts.min())
    return low, low + int(np.asarray(lengths, dtype=np.int64).sum())


def eval_windows(tokens: np.ndarray, low: int, high: int, context: int):
    """Every full `context`-character window of `[low, high)` — no sampling."""
    n = (high - low - 1) // context
    starts = low + np.arange(n, dtype=np.int64) * context
    x = np.stack([tokens[s : s + context] for s in starts]).astype(np.int64)
    y = np.stack([tokens[s + 1 : s + 1 + context] for s in starts]).astype(np.int64)
    return x, y


def validation_loss(net, device, x: np.ndarray, y: np.ndarray) -> float:
    net.eval()
    total, count = 0.0, 0
    with torch.no_grad():
        for i in range(0, len(x), SCORE_BATCH):
            logits = net(torch.from_numpy(x[i : i + SCORE_BATCH]).to(device))
            target = torch.from_numpy(y[i : i + SCORE_BATCH]).to(device)
            total += float(
                F.cross_entropy(
                    logits.reshape(-1, logits.shape[-1]),
                    target.reshape(-1),
                    reduction="sum",
                )
            )
            count += int(target.numel())
    net.train()
    return total / count


def main() -> None:
    t0 = time.time()
    evaluation_kind = os.environ.get("KLEIN_EVALUATION_KIND")
    if SMOKE:
        evaluation_kind = evaluation_kind or "development"
    missing = [
        name
        for name, value in (
            ("KLEIN_EVALUATION_KIND", evaluation_kind),
            ("KLEIN_EXPERIMENT_ID", EXPERIMENT_ID),
            ("KLEIN_TRACK", TRACK),
        )
        if value is None
    ]
    if missing:
        raise RuntimeError(
            "train.py must be invoked through `klein run-one`. For a pre-run "
            "syntax/shape check use `KLEIN_SMOKE=1 python train.py` — it prints "
            "the canonical block, writes no evidence, and is not evidence. "
            "Missing: " + ", ".join(missing)
        )

    X_fit, X_eval, y_fit, y_eval = load_partition(evaluation_kind, study_dir=".")
    # Under the sealed rehearsal `load_partition` hands back DEVELOPMENT rows;
    # the checkpoint must say what it was actually scored on, not what was asked.
    scored_kind = "development" if DRY_RUN else evaluation_kind
    fingerprint = split_fingerprint(X_fit, X_eval)

    tokens = np.fromfile(TOKENS_PATH, dtype=np.uint8)
    fit_low, fit_high = character_range(X_fit, y_fit)
    eval_low, eval_high = character_range(X_eval, y_eval)

    config = dict(arch.CONFIG)
    context = int(config["block_size"])
    seed = int(RECIPE["seed"])
    steps = 20 if SMOKE else int(RECIPE["max_steps"])
    batch = int(RECIPE["batch_size"])
    lr = float(RECIPE["lr"])
    warmup = int(RECIPE["warmup_steps"])
    schedule = str(RECIPE.get("schedule", "constant"))
    final_frac = float(RECIPE.get("lr_final_frac", 1.0))

    device = pick_device()
    torch.manual_seed(seed)
    net = arch.build(config).to(device)
    optimizer = torch.optim.AdamW(
        net.parameters(),
        lr=lr,
        betas=(float(RECIPE["beta1"]), float(RECIPE["beta2"])),
        weight_decay=float(RECIPE["weight_decay"]),
    )

    rng = np.random.default_rng(seed)
    span = fit_high - fit_low - context - 1
    fit_start = time.time()
    net.train()
    last_loss = float("nan")
    for step in range(steps):
        if warmup > 0 and step < warmup:
            scale = (step + 1) / warmup
        elif schedule == "cosine":
            progress = (step - warmup) / max(1, steps - warmup)
            scale = final_frac + (1.0 - final_frac) * 0.5 * (1.0 + math.cos(math.pi * progress))
        else:
            scale = 1.0
        for group in optimizer.param_groups:
            group["lr"] = lr * scale
        # Streamed index-shuffle batching (war story 2): no DataLoader, no
        # TensorDataset — offsets drawn straight from the token array.
        offsets = fit_low + rng.integers(0, span, size=batch)
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
        last_loss = float(loss.detach())
    fit_seconds = time.time() - fit_start

    x_eval, y_eval_windows = eval_windows(tokens, eval_low, eval_high, context)
    reported = validation_loss(net, device, x_eval, y_eval_windows)

    MODELS.mkdir(parents=True, exist_ok=True)
    checkpoint_path = MODELS / f"{EXPERIMENT_ID}.pt"
    torch.save(
        {
            "config": config,
            "state_dict": {k: v.detach().cpu() for k, v in net.state_dict().items()},
            "steps": steps,
            "evaluation_kind": scored_kind,
            "split_fingerprint": fingerprint,
            "reported_val_loss": reported,
            "recipe": str(RECIPE["name"]),
            "seed": seed,
            "lr": lr,
            "batch_size": batch,
            "warmup_steps": warmup,
            "schedule": schedule,
            "lr_final_frac": final_frac,
        },
        checkpoint_path,
    )
    posix = checkpoint_path.as_posix()
    # `checkpoint:` is what `tracks.primary.verifier.artifact_key` names;
    # `artifact:` is what the notary hashes into the manifest. Same file.
    print(f"checkpoint: {posix}")
    print(f"artifact: {posix}")

    evaluate_scalar(
        reported,
        exp_id=EXPERIMENT_ID,
        metric_name="val_loss",
        metric_goal="lower",
        extra={
            "train_steps": str(steps),
            "fit_seconds": f"{fit_seconds:.3f}",
            "train_chars": str(fit_high - fit_low),
            "eval_chars": str(eval_high - eval_low),
            "eval_windows": str(len(x_eval)),
            "final_train_batch_loss": f"{last_loss:.6f}",
            "train_bpc": f"{reported / math.log(2):.6f}",
            "recipe_warmup_steps": str(warmup),
            "recipe_cosine": str(int(schedule == "cosine")),
            "recipe_lr_final_frac": f"{final_frac:.4f}",
            "recipe_lr": f"{lr:.6g}",
            "recipe_dropout": f"{float(config['dropout']):.4f}",
            "recipe_n_embd": str(int(config["n_embd"])),
            "recipe_tie_weights": str(int(bool(config["tie_weights"]))),
            "recipe_seed": str(seed),
        },
        study_dir=".",
        t0=t0,
    )


if __name__ == "__main__":
    main()
