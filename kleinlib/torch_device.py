"""Pick a torch device with MPS preference and CPU fallback.

Ported from the model-survey campaign's ``lib/torch_device.py``, then
extended for Klein 2.0 (``references/compute-and-devices.md``): a
``KLEIN_DEVICE`` environment override that wins over everything (the
documented last-resort human override — e.g. forcing ``cpu`` to reproduce a
floor measurement identically across machines), and ``prefer="auto"`` (now
the default), which cascades mps -> cuda -> cpu. ``prefer="mps"``/``"cuda"``
keep their original single-backend semantics byte-for-byte: that backend or
bust to cpu, never cascading to the other accelerator — existing callers that
pass one of those two values explicitly see no behaviour change.
"""

from __future__ import annotations

import os

import torch


def pick_device(prefer: str = "auto") -> torch.device:
    override = os.environ.get("KLEIN_DEVICE")
    if override:
        return torch.device(override)
    if prefer == "auto":
        if torch.backends.mps.is_available() and torch.backends.mps.is_built():
            return torch.device("mps")
        if torch.cuda.is_available():
            return torch.device("cuda")
        return torch.device("cpu")
    if prefer == "mps":
        if torch.backends.mps.is_available() and torch.backends.mps.is_built():
            return torch.device("mps")
    if prefer == "cuda" and torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def device_name(device: torch.device) -> str:
    return str(device)
