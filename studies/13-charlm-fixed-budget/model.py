"""The architecture half of the mutable surface.

`CONFIG` is what a candidate edits when its one idea is architectural (width,
weight tying, dropout). The class below must keep producing a `state_dict` that
`verify.py`'s own independent copy of the same family can load with
`strict=True` — the checkpoint format IS the contract between the searcher and
the checker, and a candidate that leaves the family produces an artifact the
checker cannot score.

Dropout lives here because it is an architectural switch, but it has no
parameters, so a checkpoint trained with dropout loads into the checker
unchanged and is scored — as it must be — with dropout off.
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

#: The anchor recipe's architecture. 4 layers x 4 heads x 128 wide over a
#: 128-character context = 824,320 parameters at vocab 65.
CONFIG: dict[str, object] = {
    "vocab_size": 65,
    "n_layer": 4,
    "n_head": 4,
    "n_embd": 128,
    "block_size": 128,
    "tie_weights": False,
    "dropout": 0.0,
}


class Block(nn.Module):
    """Pre-norm transformer block: causal self-attention, then a 4x MLP."""

    def __init__(self, n_embd: int, n_head: int, dropout: float = 0.0) -> None:
        super().__init__()
        self.ln1 = nn.LayerNorm(n_embd)
        self.attn_qkv = nn.Linear(n_embd, 3 * n_embd, bias=False)
        self.attn_proj = nn.Linear(n_embd, n_embd, bias=False)
        self.ln2 = nn.LayerNorm(n_embd)
        self.mlp_fc = nn.Linear(n_embd, 4 * n_embd)
        self.mlp_proj = nn.Linear(4 * n_embd, n_embd)
        self.n_head = n_head
        self.dropout = dropout
        self.attn_drop = nn.Dropout(dropout)
        self.mlp_drop = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        B, T, C = x.shape
        h = self.ln1(x)
        q, k, v = self.attn_qkv(h).split(C, dim=2)
        head_dim = C // self.n_head
        q = q.view(B, T, self.n_head, head_dim).transpose(1, 2)
        k = k.view(B, T, self.n_head, head_dim).transpose(1, 2)
        v = v.view(B, T, self.n_head, head_dim).transpose(1, 2)
        y = F.scaled_dot_product_attention(
            q, k, v, is_causal=True, dropout_p=self.dropout if self.training else 0.0
        )
        y = y.transpose(1, 2).contiguous().view(B, T, C)
        x = x + self.attn_drop(self.attn_proj(y))
        return x + self.mlp_drop(self.mlp_proj(F.gelu(self.mlp_fc(self.ln2(x)))))


class CharTransformer(nn.Module):
    def __init__(
        self,
        *,
        vocab_size: int,
        n_layer: int,
        n_head: int,
        n_embd: int,
        block_size: int,
        tie_weights: bool = False,
        dropout: float = 0.0,
    ) -> None:
        super().__init__()
        self.block_size = block_size
        self.tok_emb = nn.Embedding(vocab_size, n_embd)
        self.pos_emb = nn.Parameter(torch.zeros(1, block_size, n_embd))
        self.drop = nn.Dropout(dropout)
        self.blocks = nn.ModuleList(
            [Block(n_embd, n_head, dropout) for _ in range(n_layer)]
        )
        self.ln_f = nn.LayerNorm(n_embd)
        self.head = nn.Linear(n_embd, vocab_size, bias=False)
        if tie_weights:
            self.head.weight = self.tok_emb.weight

    def forward(self, idx: torch.Tensor) -> torch.Tensor:
        x = self.drop(self.tok_emb(idx) + self.pos_emb[:, : idx.shape[1]])
        for block in self.blocks:
            x = block(x)
        return self.head(self.ln_f(x))


def build(config: dict[str, object] | None = None) -> CharTransformer:
    """Build the model on CPU under whatever torch seed the caller set.

    Building on CPU and moving afterwards is deliberate: it makes the initial
    weights identical on every backend, so a CPU run and an MPS run of the same
    recipe differ only in arithmetic.
    """
    cfg = dict(CONFIG if config is None else config)
    return CharTransformer(
        vocab_size=int(cfg["vocab_size"]),
        n_layer=int(cfg["n_layer"]),
        n_head=int(cfg["n_head"]),
        n_embd=int(cfg["n_embd"]),
        block_size=int(cfg["block_size"]),
        tie_weights=bool(cfg["tie_weights"]),
        dropout=float(cfg["dropout"]),
    )
