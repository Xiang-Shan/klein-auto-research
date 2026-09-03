"""DATA-gate checklist row 4, on this study's own evaluation path.

`python -m kleinlib.leakage --index` mechanizes split contamination for a text
modality but reports the chance-level rows N/A: an index table carries no target
and no features. Row 4 — "the metric direction matches the contract; a
no-information predictor scores at chance" — therefore has to be reproduced from
the study's own evaluator, which is what this script does.

Four controls, all scored on the development partition through the verifier's
own window enumeration and cross-entropy:

`uniform` (NEGATIVE CONTROL — chance)
    A flat distribution over the 65-character vocabulary. Must score exactly
    ln 65 = 4.174387 nats. Anything better means the harness is showing a
    no-information predictor the answers.

`untrained_network` (NEGATIVE CONTROL — the whole checkpoint path)
    A randomly initialized model of the anchor architecture, saved as a real
    checkpoint and scored by running `verify.py` as a subprocess exactly the way
    `klein run-one` does. Must land at chance. This exercises every link —
    save, load, partition lookup, fingerprint comparison, window enumeration —
    with a model that knows nothing.

`unigram_train_fit` (POSITIVE CONTROL — information is rewarded)
    Add-one character frequencies fitted on the TRAIN partition only. Must score
    strictly better than chance, because it holds real information, and it must
    be far from zero, because it holds very little. A harness that cannot tell
    these two apart cannot measure a language model.

`copy_input` (NEGATIVE CONTROL — the off-by-one leak)
    The predictor that bets the next character equals the CURRENT one. Under the
    classic language-model harness bug (targets aligned with inputs instead of
    shifted by one) this scores ln 2 = 0.693 nats and looks spectacular. With a
    correct harness it must score WORSE than chance, because English characters
    rarely repeat. This is the control that would have caught the bug.

Registered with `klein sweep register` as `sweep:harness_controls` so the data
card and the claims lock can cite it; `tables/harness_controls.tsv` carries the
same numbers with their expectations and verdicts for a human reader.
"""

from __future__ import annotations

import math
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kleinlib.data import load_partition, partition_fingerprints  # noqa: E402
from verify import (  # noqa: E402
    EVAL_CONTEXT,
    VOCAB_SIZE,
    CharTransformer,
    load_tokens,
    partition_range,
    score_logits,
    windows,
)

ANCHOR_CONFIG = {
    "vocab_size": VOCAB_SIZE,
    "n_layer": 4,
    "n_head": 4,
    "n_embd": 128,
    "block_size": EVAL_CONTEXT,
    "tie_weights": False,
    "dropout": 0.0,
}
CONTROL_CHECKPOINT = Path("models/control_untrained.pt")
CHANCE_NATS = math.log(VOCAB_SIZE)


def _development_windows():
    X_fit, X_eval, _, y_eval = load_partition("development", study_dir=".", echo=False)
    low, high = partition_range(X_eval, y_eval)
    tokens = load_tokens()
    x, y = windows(tokens, low, high)
    return tokens, X_fit, x, y


def _uniform(_: dict) -> dict:
    t0 = time.time()
    _, _, x, y = _development_windows()
    loss = score_logits(
        lambda batch: torch.zeros(batch.shape[0], batch.shape[1], VOCAB_SIZE), x, y
    )
    return {"primary_metric": loss, "status": "ok", "wall_seconds": time.time() - t0}


def _unigram(_: dict) -> dict:
    t0 = time.time()
    tokens, X_fit, x, y = _development_windows()
    fit_low = int(np.asarray(X_fit["start_char"], dtype=np.int64).min())
    fit_high = int(np.asarray(X_fit["start_char"], dtype=np.int64).max()) + EVAL_CONTEXT
    counts = np.bincount(tokens[fit_low:fit_high], minlength=VOCAB_SIZE).astype(np.float64)
    log_probs = np.log((counts + 1.0) / (counts.sum() + VOCAB_SIZE))
    row = torch.from_numpy(log_probs).float()
    loss = score_logits(
        lambda batch: row.expand(batch.shape[0], batch.shape[1], VOCAB_SIZE), x, y
    )
    return {"primary_metric": loss, "status": "ok", "wall_seconds": time.time() - t0}


def _copy_input(_: dict) -> dict:
    """Bet 0.5 that the next character repeats the current one."""
    t0 = time.time()
    _, _, x, y = _development_windows()
    hit = math.log(0.5)
    miss = math.log(0.5 / (VOCAB_SIZE - 1))

    def logits(batch: np.ndarray) -> torch.Tensor:
        out = torch.full((batch.shape[0], batch.shape[1], VOCAB_SIZE), miss)
        idx = torch.from_numpy(batch).long().unsqueeze(-1)
        out.scatter_(2, idx, hit)
        return out

    loss = score_logits(logits, x, y)
    return {"primary_metric": loss, "status": "ok", "wall_seconds": time.time() - t0}


def _untrained_network(_: dict) -> dict:
    """Save a random checkpoint and score it by RUNNING `verify.py` itself."""
    t0 = time.time()
    torch.manual_seed(0)
    model = CharTransformer(
        vocab_size=ANCHOR_CONFIG["vocab_size"],
        n_layer=ANCHOR_CONFIG["n_layer"],
        n_head=ANCHOR_CONFIG["n_head"],
        n_embd=ANCHOR_CONFIG["n_embd"],
        block_size=ANCHOR_CONFIG["block_size"],
        tie_weights=False,
    )
    CONTROL_CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "config": dict(ANCHOR_CONFIG),
            "state_dict": model.state_dict(),
            "steps": 0,
            "evaluation_kind": "development",
            "split_fingerprint": partition_fingerprints(".")["development"],
            "reported_val_loss": float("nan"),
            "seed": 0,
            "lr": 0.0,
            "batch_size": 0,
            "warmup_steps": 0,
        },
        CONTROL_CHECKPOINT,
    )
    env = dict(os.environ)
    env.update(
        {
            "KLEIN_ARTIFACT": str(CONTROL_CHECKPOINT.resolve()),
            "KLEIN_EXPERIMENT_ID": "CONTROL",
            "KLEIN_TRACK": "primary",
            "KLEIN_EVALUATION_KIND": "development",
            "KLEIN_SMOKE": "",
            "KLEIN_SEALED_DRYRUN": "",
        }
    )
    proc = subprocess.run(
        ["uv", "run", "--locked", "python", "-u", "verify.py"],
        cwd=str(Path(__file__).resolve().parents[1]),
        env=env,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return {
            "primary_metric": float("nan"),
            "status": "crash",
            "error": proc.stderr.strip()[-400:],
            "wall_seconds": time.time() - t0,
        }
    value = None
    for line in proc.stdout.splitlines():
        if line.startswith("primary_metric:"):
            value = float(line.split(":", 1)[1])
    if value is None:
        return {
            "primary_metric": float("nan"),
            "status": "crash",
            "error": "verify.py printed no primary_metric line",
            "wall_seconds": time.time() - t0,
        }
    return {"primary_metric": value, "status": "ok", "wall_seconds": time.time() - t0}


CONTROLS = {
    "uniform": _uniform,
    "untrained_network": _untrained_network,
    "unigram_train_fit": _unigram,
    "copy_input": _copy_input,
}

EXPECTATIONS = {
    "uniform": ("negative", f"== ln 65 = {CHANCE_NATS:.6f} nats (chance), to float32 resolution"),
    "untrained_network": (
        "negative",
        "no BETTER than chance — a random network holds no information, and its "
        "unnormalized head makes it slightly worse; the band is [chance, chance + 0.5]",
    ),
    "unigram_train_fit": ("positive", "strictly better than chance"),
    "copy_input": ("negative", "strictly WORSE than chance (targets are shifted by one)"),
}

#: Float32 logits summed over ~111k characters reproduce ln 65 to about 1e-6;
#: the check is that the harness returns CHANCE, not that it returns a double.
CHANCE_RESOLUTION = 1e-4


def _verdict(name: str, value: float) -> str:
    if name == "uniform":
        return "PASS" if abs(value - CHANCE_NATS) < CHANCE_RESOLUTION else "FAIL"
    if name == "untrained_network":
        return (
            "PASS"
            if CHANCE_NATS - CHANCE_RESOLUTION <= value <= CHANCE_NATS + 0.5
            else "FAIL"
        )
    if name == "unigram_train_fit":
        return "PASS" if value < CHANCE_NATS else "FAIL"
    return "PASS" if value > CHANCE_NATS else "FAIL"


def main() -> int:
    from kleinlib.sweep import SweepRunner

    def trial(params: dict) -> dict:
        return CONTROLS[params["control"]](params)

    summary = SweepRunner(
        "harness_controls",
        ".",
        trial,
        [{"control": name} for name in CONTROLS],
        metric_goal="lower",
        overwrite=True,
    ).run()

    values = {t.params["control"]: t.primary_metric for t in summary.trials}

    # The off-by-one evidence a reader can check without running anything: how
    # often the character a window predicts is the character it just read.
    _, _, x, y = _development_windows()
    repeat_rate = float(np.mean(x == y))

    rows = [
        {
            "control": name,
            "role": EXPECTATIONS[name][0],
            "expectation": EXPECTATIONS[name][1],
            "val_nats_per_char": round(float(values[name]), 6),
            "val_bits_per_char": round(float(values[name]) / math.log(2), 6),
            "chance_nats_per_char": round(CHANCE_NATS, 6),
            "verdict": _verdict(name, float(values[name])),
        }
        for name in CONTROLS
    ]
    rows.append(
        {
            "control": "target_equals_input_rate",
            "role": "diagnostic",
            "expectation": "far below 1.0 — 1.0 would mean the targets were never shifted",
            "val_nats_per_char": round(repeat_rate, 6),
            "val_bits_per_char": float("nan"),
            "chance_nats_per_char": float("nan"),
            "verdict": "PASS" if repeat_rate < 0.2 else "FAIL",
        }
    )
    Path("tables").mkdir(exist_ok=True)
    pd.DataFrame(rows).to_csv("tables/harness_controls.tsv", sep="\t", index=False)
    for row in rows:
        print(f"{row['verdict']:4s} {row['control']:24s} {row['val_nats_per_char']:>10.6f}"
              f"   ({row['role']}: {row['expectation']})")
    return 0 if all(row["verdict"] == "PASS" for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
