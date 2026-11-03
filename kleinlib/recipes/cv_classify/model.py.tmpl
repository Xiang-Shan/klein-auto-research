"""The network (part of the mutable surface, recipe cv-classify)."""

from __future__ import annotations

import torch
from torch import nn


class SmallCNN(nn.Module):
    """Two conv blocks + a linear head — the honest small baseline for small images."""

    def __init__(self, in_channels: int, n_classes: int, width: int = 32) -> None:
        super().__init__()
        self.body = nn.Sequential(
            nn.Conv2d(in_channels, width, 3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(width, 2 * width, 3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool2d(1),
            nn.Flatten(),
            nn.Linear(2 * width, n_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.body(x)
