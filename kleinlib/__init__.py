"""kleinlib — engine package for Klein Auto Research.

The engine: data, encoders, eval, torch_device, torch_loop, figures,
snapshot, sweep, profile_fallback, keep_awake. Re-exported here as submodules
so callers can do
``from kleinlib import data, encoders, eval, figures, ...`` without knowing
file layout.

`torch_device`/`torch_loop` need the optional `deep` extra (`torch`).
Importing bare `kleinlib` never requires torch: those two submodules are
only bound into this namespace when torch is actually importable, so
``import kleinlib`` still works with core deps only (e.g. in CI).
"""

from kleinlib import (
    data,
    encoders,
    eval,
    figures,
    keep_awake,
    profile_fallback,
    schema,
    snapshot,
)

__all__ = [
    "data",
    "encoders",
    "eval",
    "figures",
    "keep_awake",
    "profile_fallback",
    "schema",
    "snapshot",
]

try:
    from kleinlib import torch_device, torch_loop  # noqa: F401

    __all__ += ["torch_device", "torch_loop"]
except ImportError:
    pass

__version__ = "0.1.0"
