"""kleinlib — engine package for Klein Auto Research.

The engine: data, encoders, eval, torch_device, torch_loop, figures,
snapshot, sweep, profile_fallback. Re-exported here as submodules
so callers can do
``from kleinlib import data, encoders, eval, figures, ...`` without knowing
file layout.

Submodules are imported lazily, so lightweight helpers do not pay the
matplotlib/sklearn/torch import cost or require unrelated optional extras.
"""

from __future__ import annotations

import importlib
import importlib.metadata
import importlib.util
from types import ModuleType

__all__ = [
    "cli",
    "data",
    "encoders",
    "eval",
    "figures",
    "leakage",
    "noise_floor",
    "profile_fallback",
    "schema",
    "scaffold",
    "snapshot",
    "sweep",
    "workflow",
]

if importlib.util.find_spec("torch") is not None:
    __all__ += ["torch_device", "torch_loop"]

_LAZY_SUBMODULES = frozenset([*__all__, "runner", "torch_device", "torch_loop"])


def __getattr__(name: str) -> ModuleType:
    if name not in _LAZY_SUBMODULES:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = importlib.import_module(f".{name}", __name__)
    globals()[name] = module
    return module


def __dir__() -> list[str]:
    return sorted([*globals(), *_LAZY_SUBMODULES])


try:
    __version__ = importlib.metadata.version("klein-auto-research")
except importlib.metadata.PackageNotFoundError:  # raw checkout without install
    __version__ = "0+uninstalled"
