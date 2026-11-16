"""Plug-ins: how code outside the kernel adds to Klein.

The kernel judges; a plug-in may only ADD — a verb group on the command line, an
audience profile, an evidence modality, a read-only MCP tool.  It can never change
how a run is judged: kinds, dispositions, the claims law and the receipts are not
on this surface, and a study that uses no plug-in is untouched by any of them.

A plug-in is one callable::

    def register(api: PluginAPI) -> None:
        api.add_profile(ProfileSpec("climate", doc=Path(__file__).parent / "climate.md"))
        api.add_cli(my_cli.register)            # my_cli.register(subparsers)

advertised under the ``klein.plugins`` entry-point group of its distribution::

    [project.entry-points."klein.plugins"]
    climate = "klein_climate:register"

The opt-in generation layer ships in this repository and is loaded the same way
(:data:`BUILTIN`), which is what keeps the seam honest.  A plug-in that fails to
load is reported by ``klein doctor`` and never breaks a core verb.  Set
``KLEIN_NO_PLUGINS=1`` to load the built-ins only.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass, field
from importlib import import_module
from typing import Any

__all__ = [
    "BUILTIN",
    "ENTRY_POINT_GROUP",
    "PluginAPI",
    "cli_registrars",
    "ensure_loaded",
    "load_errors",
    "loaded_plugins",
    "mcp_tools",
    "register_plugin",
    "reset",
]

ENTRY_POINT_GROUP = "klein.plugins"

#: Plug-ins that ship inside this distribution, as ``module:callable``.
BUILTIN: tuple[str, ...] = ("kleinlib.generation.plugin:register",)

CliRegistrar = Callable[[Any], None]
#: ``(study_or_root, arguments) -> (text, structured)``; must not write.
McpHandler = Callable[[Any, Any], tuple[str, Any]]


@dataclass
class _State:
    loaded: bool = False
    loading: bool = False
    names: list[str] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)
    cli: list[CliRegistrar] = field(default_factory=list)
    mcp: dict[str, tuple[dict[str, Any], McpHandler]] = field(default_factory=dict)


_STATE = _State()


class PluginAPI:
    """What a plug-in may add.  Everything here is additive and read-only for the kernel."""

    def __init__(self, name: str) -> None:
        self.name = name

    def add_cli(self, register: CliRegistrar) -> None:
        """``register(subparsers)`` adds verbs; each sets ``handler=`` like a core group."""
        _STATE.cli.append(register)

    def add_profile(self, spec: Any) -> None:
        from .inquiry import register_profile

        register_profile(spec)

    def add_modality(self, spec: Any) -> None:
        from .inquiry import register_modality

        register_modality(spec)

    def add_mcp_tool(self, definition: dict[str, Any], handler: McpHandler) -> None:
        """A read-only MCP tool.  ``definition`` is the MCP tool object (name, description, inputSchema)."""
        name = str(definition.get("name") or "")
        if not name:
            raise ValueError("an MCP tool needs a name")
        if name in _STATE.mcp:
            raise ValueError(f"MCP tool {name!r} is already registered")
        _STATE.mcp[name] = (definition, handler)


def register_plugin(name: str, register: Callable[[PluginAPI], None]) -> None:
    """Run one plug-in's ``register``; a failure is recorded, never raised."""
    try:
        register(PluginAPI(name))
    except Exception as exc:  # noqa: BLE001 - a broken plug-in must not break the kernel
        _STATE.errors[name] = f"{type(exc).__name__}: {exc}"
        return
    _STATE.names.append(name)


def _resolve(target: str) -> Callable[[PluginAPI], None]:
    module, _, attribute = target.partition(":")
    return getattr(import_module(module), attribute or "register")


def ensure_loaded() -> None:
    """Load the built-in and installed plug-ins once per process."""
    if _STATE.loaded or _STATE.loading:
        return
    _STATE.loading = True
    try:
        for target in BUILTIN:
            try:
                register_plugin(target.partition(":")[0], _resolve(target))
            except Exception as exc:  # noqa: BLE001
                _STATE.errors[target] = f"{type(exc).__name__}: {exc}"
        if os.environ.get("KLEIN_NO_PLUGINS") != "1":
            from importlib.metadata import entry_points

            for entry in sorted(entry_points(group=ENTRY_POINT_GROUP), key=lambda e: e.name):
                try:
                    register_plugin(entry.name, entry.load())
                except Exception as exc:  # noqa: BLE001
                    _STATE.errors[entry.name] = f"{type(exc).__name__}: {exc}"
    finally:
        _STATE.loading = False
        _STATE.loaded = True


def cli_registrars() -> tuple[CliRegistrar, ...]:
    ensure_loaded()
    return tuple(_STATE.cli)


def mcp_tools() -> dict[str, tuple[dict[str, Any], McpHandler]]:
    ensure_loaded()
    return dict(_STATE.mcp)


def loaded_plugins() -> tuple[str, ...]:
    ensure_loaded()
    return tuple(_STATE.names)


def load_errors() -> dict[str, str]:
    ensure_loaded()
    return dict(_STATE.errors)


def reset() -> None:
    """Forget every loaded plug-in's verbs and tools (tests only; profiles stay registered)."""
    _STATE.loaded = False
    _STATE.loading = False
    _STATE.names.clear()
    _STATE.errors.clear()
    _STATE.cli.clear()
    _STATE.mcp.clear()
