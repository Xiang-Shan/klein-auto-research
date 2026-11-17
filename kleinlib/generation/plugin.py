"""The generation layer's plug-in entry: how the kernel learns it exists.

``kleinlib.plugins`` calls :func:`register` once per process.  Nothing in the kernel
imports this package by name — it is loaded through the same seam a third-party
plug-in uses, which is what keeps the layer optional.
"""

from __future__ import annotations

from typing import Any


def _register_cli(subparsers: Any) -> None:
    from .cli import register

    register(subparsers)


def register(api: Any) -> None:
    api.add_cli(_register_cli)
