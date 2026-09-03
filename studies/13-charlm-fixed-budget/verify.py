"""The declared verifier — the checker, and never the searcher.

`klein run-one` runs this file as a SECOND bounded subprocess after the
entrypoint exits, with `KLEIN_ARTIFACT` pointing at the checkpoint the run
printed on its `checkpoint:` line. The number this file prints is the number the
disposition uses; `train.py`'s own reported loss is recorded beside it in the
manifest, and a disagreement beyond `tracks.primary.verifier.tolerance`
(0.01 nats) is a crash. This file is outside `entrypoint.mutable`, is hashed at
the METHOD gate, and never changes again.

Why it re-implements the architecture
-------------------------------------
It would be easier to `import model` and reuse the searcher's own class. That is
exactly the door this study exists to close: a training loop that grades its own
checkpoint is the oldest way to be wrong without lying. So the architecture
FAMILY lives here, in the immutable half of the study, and `model.py` must
produce a `state_dict` this file can load with `strict=True`. The family is
therefore part of the contract: recipes may vary (warmup, tying, dropout, width,
seed), the family may not. A candidate that leaves it produces an artifact the
checker cannot score — a crash, and honest evidence.

What it re-derives from scratch
-------------------------------
* the partition, from `kleinlib.data.load_partition` — which prints the
  `split_fingerprint:` this file then compares with the one the checkpoint
  claims, so a checkpoint scored against the wrong rows is a hard failure;
* the evaluation windows: every full 128-character window of the partition's
  contiguous character range, no sampling, no seed;
* the cross-entropy itself, in nats per character.

What it reads out of the artifact (and prints, so the manifest records it)
-------------------------------------------------------------------------
`steps` — the optimizer-step count the checkpoint was saved at. This is the
matched-compute guardrail: the CHECKER enforces the budget, not the searcher.
`eval_context` is the same idea for matched measurement.
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from kleinlib.contract import load_contract
from kleinlib.data import load_partition, split_fingerprint
from kleinlib.eval import evaluate_scalar
from kleinlib.torch_device import pick_device

#: The evaluation context length is a CONTRACT constant, not a candidate knob:
#: a model graded on a different window predicts a different set of characters.
#: `tracks.primary.guardrails.eval_context` pins it at this value.
EVAL_CONTEXT = 128

#: The 65-character vocabulary `prepare.py` derived from the corpus.
VOCAB_SIZE = 65

#: Windows per forward pass while scoring. Affects speed only: the loss is a
#: sum over every predicted character and does not depend on the grouping.
SCORE_BATCH = 64

TOKENS_PATH = Path("data/prepared/tokens.bin")
TRACK = "primary"


# ---------------------------------------------------------------------------
# The architecture family (the checker's own copy)
# ---------------------------------------------------------------------------
class Block(nn.Module):
    """Pre-norm transformer block: causal self-attention, then a 4x MLP."""

    def __init__(self, n_embd: int, n_head: int) -> None:
        super().__init__()
        self.ln1 = nn.LayerNorm(n_embd)
        self.attn_qkv = nn.Linear(n_embd, 3 * n_embd, bias=False)
        self.attn_proj = nn.Linear(n_embd, n_embd, bias=False)
        self.ln2 = nn.LayerNorm(n_embd)
        self.mlp_fc = nn.Linear(n_embd, 4 * n_embd)
        self.mlp_proj = nn.Linear(4 * n_embd, n_embd)
        self.n_head = n_head

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        B, T, C = x.shape
        h = self.ln1(x)
        q, k, v = self.attn_qkv(h).split(C, dim=2)
        head_dim = C // self.n_head
        q = q.view(B, T, self.n_head, head_dim).transpose(1, 2)
        k = k.view(B, T, self.n_head, head_dim).transpose(1, 2)
        v = v.view(B, T, self.n_head, head_dim).transpose(1, 2)
        y = F.scaled_dot_product_attention(q, k, v, is_causal=True)
        y = y.transpose(1, 2).contiguous().view(B, T, C)
        x = x + self.attn_proj(y)
        return x + self.mlp_proj(F.gelu(self.mlp_fc(self.ln2(x))))


class CharTransformer(nn.Module):
    """The family. Dropout is a TRAINING knob and has no parameters, so a
    checkpoint trained with dropout loads here unchanged and is scored, as it
    must be, with dropout off."""

    def __init__(
        self,
        *,
        vocab_size: int,
        n_layer: int,
        n_head: int,
        n_embd: int,
        block_size: int,
        tie_weights: bool = False,
    ) -> None:
        super().__init__()
        self.block_size = block_size
        self.tok_emb = nn.Embedding(vocab_size, n_embd)
        self.pos_emb = nn.Parameter(torch.zeros(1, block_size, n_embd))
        self.blocks = nn.ModuleList([Block(n_embd, n_head) for _ in range(n_layer)])
        self.ln_f = nn.LayerNorm(n_embd)
        self.head = nn.Linear(n_embd, vocab_size, bias=False)
        if tie_weights:
            self.head.weight = self.tok_emb.weight

    def forward(self, idx: torch.Tensor) -> torch.Tensor:
        x = self.tok_emb(idx) + self.pos_emb[:, : idx.shape[1]]
        for block in self.blocks:
            x = block(x)
        return self.head(self.ln_f(x))


def build_from_config(config: dict[str, Any]) -> CharTransformer:
    return CharTransformer(
        vocab_size=int(config["vocab_size"]),
        n_layer=int(config["n_layer"]),
        n_head=int(config["n_head"]),
        n_embd=int(config["n_embd"]),
        block_size=int(config["block_size"]),
        tie_weights=bool(config.get("tie_weights", False)),
    )


# ---------------------------------------------------------------------------
# The measurement
# ---------------------------------------------------------------------------
def load_tokens() -> np.ndarray:
    return np.fromfile(TOKENS_PATH, dtype=np.uint8)


def partition_range(X_eval, y_eval) -> tuple[int, int]:
    """The contiguous character range of an evaluation partition.

    `y_eval` is the contract's target column (`n_chars`), which is why the block
    lengths survive `contract_split` dropping it from the feature frame.
    """
    starts = np.asarray(X_eval["start_char"], dtype=np.int64)
    lengths = np.asarray(y_eval, dtype=np.int64)
    low = int(starts.min())
    total = int(lengths.sum())
    high = low + total
    order = np.argsort(starts)
    expected = low + np.concatenate([[0], np.cumsum(lengths[order])[:-1]])
    if not np.array_equal(starts[order], expected):
        raise SystemExit(
            "verifier: the evaluation partition is not a contiguous character range — "
            "the contract's time split did not order the blocks by offset"
        )
    return low, high


def windows(tokens: np.ndarray, low: int, high: int, context: int = EVAL_CONTEXT):
    """Every full `context`-character window of `[low, high)`, no sampling.

    Window i reads characters `low + i*context ... low + (i+1)*context - 1` and
    predicts the character one position later. Windows do not overlap, no window
    crosses the partition boundary, and the last `context` characters of the
    range are not predicted because their successors lie outside it.
    """
    n = (high - low - 1) // context
    starts = low + np.arange(n, dtype=np.int64) * context
    x = np.stack([tokens[s : s + context] for s in starts]).astype(np.int64)
    y = np.stack([tokens[s + 1 : s + 1 + context] for s in starts]).astype(np.int64)
    return x, y


def score_logits(logits_fn, x: np.ndarray, y: np.ndarray) -> float:
    """Mean next-character cross-entropy in nats, summed in double precision."""
    total = 0.0
    count = 0
    for i in range(0, len(x), SCORE_BATCH):
        logits = logits_fn(x[i : i + SCORE_BATCH])
        target = torch.from_numpy(y[i : i + SCORE_BATCH]).to(logits.device)
        total += float(
            F.cross_entropy(
                logits.reshape(-1, logits.shape[-1]), target.reshape(-1), reduction="sum"
            )
        )
        count += int(target.numel())
    return total / count


def score_model(model: nn.Module, device: torch.device, x: np.ndarray, y: np.ndarray) -> float:
    model.eval()
    with torch.no_grad():
        return score_logits(
            lambda batch: model(torch.from_numpy(batch).to(device)), x, y
        )


# ---------------------------------------------------------------------------
# The entrypoint the notary runs
# ---------------------------------------------------------------------------
def _fail(message: str) -> None:
    print(f"verifier: {message}", file=sys.stderr)
    raise SystemExit(2)


def _development_incumbent(track: str) -> float | None:
    """The last development `keep` on this track, read from the run manifests.

    The same rule `kleinlib.decision` uses for the frontier. Read here rather
    than passed in from `train.py`, so the number P6 is judged against comes
    from the notarized ledger and not from the mutable surface.
    """
    best: float | None = None
    runs = Path("runs")
    if not runs.is_dir():
        return None
    for path in sorted(runs.glob("E*/manifest.json")):
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if (
            manifest.get("track") == track
            and manifest.get("disposition") == "keep"
            and manifest.get("evaluation_kind", "development") == "development"
            and isinstance(manifest.get("primary_metric"), (int, float))
        ):
            best = float(manifest["primary_metric"])
    return best


def main() -> int:
    t0 = time.time()
    raw = os.environ.get("KLEIN_ARTIFACT") or (sys.argv[1] if len(sys.argv) > 1 else "")
    if not raw:
        _fail("no KLEIN_ARTIFACT and no path argument — nothing to check")
    artifact = Path(raw)
    if not artifact.is_file():
        _fail(f"the artifact does not exist: {raw}")

    checkpoint = torch.load(artifact, map_location="cpu", weights_only=True)
    for key in ("config", "state_dict", "steps", "evaluation_kind", "split_fingerprint"):
        if key not in checkpoint:
            _fail(f"the checkpoint carries no {key!r} — it cannot be checked")
    config = checkpoint["config"]
    if int(config["block_size"]) != EVAL_CONTEXT:
        _fail(
            f"block_size {config['block_size']} != the contract's evaluation context "
            f"{EVAL_CONTEXT}; a model graded on a different window predicts different "
            "characters and is not comparable"
        )
    if int(config["vocab_size"]) != VOCAB_SIZE:
        _fail(f"vocab_size {config['vocab_size']} != {VOCAB_SIZE}")

    kind = os.environ.get("KLEIN_EVALUATION_KIND") or str(checkpoint["evaluation_kind"])
    if kind not in {"development", "final_test"}:
        _fail(f"invalid evaluation kind {kind!r}")

    X_fit, X_eval, _, y_eval = load_partition(kind, study_dir=".", echo=True)
    realized = split_fingerprint(X_fit, X_eval)
    if realized != str(checkpoint["split_fingerprint"]):
        _fail(
            "the checkpoint claims split_fingerprint "
            f"{checkpoint['split_fingerprint']} but the contract's {kind} partition is "
            f"{realized} — the training run and this check are not looking at the same rows"
        )

    device = pick_device()
    model = build_from_config(config).to(device)
    try:
        model.load_state_dict(checkpoint["state_dict"], strict=True)
    except (RuntimeError, KeyError) as exc:
        _fail(f"the checkpoint does not fit the declared architecture family: {exc}")

    low, high = partition_range(X_eval, y_eval)
    tokens = load_tokens()
    x, y = windows(tokens, low, high)
    val_loss = score_model(model, device, x, y)

    contract = load_contract(".")
    metric = contract["tracks"][TRACK]["metric"]
    minimum_delta = float(metric.get("minimum_delta") or 0.0)
    fit_noise = metric.get("fit_noise") or {}
    anchor_mean = fit_noise.get("mean")
    anchor_std = fit_noise.get("std")

    extra: dict[str, str] = {
        # matched compute and matched measurement, read out of the artifact
        "steps": str(int(checkpoint["steps"])),
        "eval_context": str(EVAL_CONTEXT),
        # what was scored
        "n_val_windows": str(len(x)),
        "n_scored_chars": str(int(x.size)),
        "n_partition_chars": str(high - low),
        "n_params": str(sum(p.numel() for p in model.parameters())),
        "bpc": f"{val_loss / math.log(2):.6f}",
        # the searcher's own claim, kept beside the checker's number
        "reported_val_loss": f"{float(checkpoint.get('reported_val_loss', float('nan'))):.6f}",
        "verifier_gap": f"{abs(val_loss - float(checkpoint.get('reported_val_loss', float('nan')))):.8f}",
        # the recipe, as the checker read it from the artifact
        "cfg_n_layer": str(int(config["n_layer"])),
        "cfg_n_head": str(int(config["n_head"])),
        "cfg_n_embd": str(int(config["n_embd"])),
        "cfg_tie_weights": str(int(bool(config.get("tie_weights", False)))),
        "cfg_dropout": f"{float(config.get('dropout', 0.0)):.4f}",
        "cfg_warmup_steps": str(int(checkpoint.get("warmup_steps", 0))),
        "cfg_lr": f"{float(checkpoint.get('lr', float('nan'))):.6g}",
        "cfg_batch_size": str(int(checkpoint.get("batch_size", 0))),
        "cfg_seed": str(int(checkpoint.get("seed", -1))),
    }

    if kind == "development":
        if anchor_mean is not None and minimum_delta > 0:
            extra["anchor_mean"] = f"{float(anchor_mean):.6f}"
            extra["delta_vs_anchor"] = f"{float(anchor_mean) - val_loss:.6f}"
            extra["delta_in_floors"] = f"{(float(anchor_mean) - val_loss) / minimum_delta:.4f}"
        if anchor_mean is not None and anchor_std not in (None, 0):
            extra["anchor_z"] = f"{abs(val_loss - float(anchor_mean)) / float(anchor_std):.4f}"
    else:
        incumbent = _development_incumbent(TRACK)
        if incumbent is not None:
            extra["dev_incumbent_val_loss"] = f"{incumbent:.6f}"
            extra["sealed_minus_dev_incumbent"] = f"{val_loss - incumbent:.6f}"
            if anchor_std not in (None, 0):
                extra["sealed_gap_in_fit_noise"] = (
                    f"{abs(val_loss - incumbent) / float(anchor_std):.4f}"
                )

    evaluate_scalar(
        val_loss,
        exp_id=os.environ.get("KLEIN_EXPERIMENT_ID") or "VERIFY",
        metric_name="val_loss",
        metric_goal="lower",
        extra=extra,
        study_dir=None,  # the run's own evaluator owns aux_metrics.tsv
        t0=t0,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
