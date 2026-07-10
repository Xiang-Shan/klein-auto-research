"""Pick a torch device with MPS preference and CPU fallback.

Ported as-is from the model-survey campaign's ``lib/torch_device.py``.
"""

from __future__ import annotations

import torch


def pick_device(prefer: str = "mps") -> torch.device:
    if prefer == "mps":
        if torch.backends.mps.is_available() and torch.backends.mps.is_built():
            return torch.device("mps")
    if prefer == "cuda" and torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def device_name(device: torch.device) -> str:
    return str(device)
