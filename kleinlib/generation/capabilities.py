"""The capability modules THIS version ships, and the loader that reads them.

``MODULES`` is the dependency-ordered list of module names under
``kleinlib.generation``; each exports one module-level
``CAPABILITY: Capability``.  A later work package appends its module name here
and ships the module — and touches nothing else in the spine.

Two registries have to agree and neither may derive the other:
:data:`kleinlib.generation.manifest.SUPPORTED_CAPABILITIES` is what a study may
DECLARE, and this module is what the spine can RUN.  ``manifest.py`` cannot
import this module (``registry`` types against ``admission``/``verify``, which
read the manifest), so the agreement is a checked invariant rather than a
computed one: ``kleinlib/tests/test_generation_registry.py`` asserts
``set(load()) == set(SUPPORTED_CAPABILITIES)``.  Adding a name to one list and
forgetting the other fails the suite immediately.

The spine shipped neither: with both lists empty, opting in buys the admission
discipline and nothing that scores research.  Each capability package since then
appends its name to each list — WP-01 added ``expert`` / ``expertise``, WP-02
added ``slate`` / ``slates``, WP-09 added ``design`` / ``design``, WP-03 added
``premortem`` / ``premortem``, WP-04 added ``parity`` and ``contribution``, and
WP-05 added ``benchmark`` under their own names — and edits no other line of
this package.  :mod:`kleinlib.generation.custody` is deliberately NOT here: an
attestation is not a capability, and any generation-enabled study may record one.
"""

from __future__ import annotations

from importlib import import_module

from ..errors import WorkflowError
from .registry import Capability

__all__ = ["MODULES", "load"]

#: Module names under ``kleinlib.generation``, in dependency order.
MODULES: tuple[str, ...] = (
    # --- WP-01: expertise ---
    "expert",
    # --- WP-02: hypothesis slates + calibration ---
    "slate",
    # --- WP-09: evidence design ---
    "design",
    # --- WP-03: slate-time pre-mortem ---
    "premortem",
    # --- WP-04: expert parity + contribution ledger ---
    "parity",
    "contribution",
    # --- WP-05: planted-truth benchmark (custody.py registers nothing) ---
    "benchmark",
)


def load() -> dict[str, Capability]:
    """``{capability name: Capability}`` for everything this version can run.

    Raises :class:`~kleinlib.errors.WorkflowError` when a listed module is
    missing, exports no ``CAPABILITY``, or collides with an already-loaded name
    — all three are defects in this package, not in the study being audited, and
    the callers turn them into a FAIL rather than a traceback.
    """
    loaded: dict[str, Capability] = {}
    for module_name in MODULES:
        try:
            module = import_module(f"{__package__}.{module_name}")
        except ImportError as exc:  # pragma: no cover - a packaging defect
            raise WorkflowError(
                f"capability module {module_name!r} is listed in MODULES but not importable: {exc}"
            ) from exc
        capability = getattr(module, "CAPABILITY", None)
        if not isinstance(capability, Capability):
            raise WorkflowError(
                f"capability module {module_name!r} exports no module-level "
                "`CAPABILITY: Capability`"
            )
        if capability.name in loaded:
            raise WorkflowError(
                f"two capability modules both register {capability.name!r}"
            )
        loaded[capability.name] = capability
    return loaded
