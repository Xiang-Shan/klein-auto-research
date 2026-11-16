"""Boilerplate the capability modules share.

Each capability's verify family builds :class:`~kleinlib.generation.verify.Check`
rows with the same three one-line constructors; they live here once.
(:mod:`kleinlib.generation.verify` keeps its own copies: it DEFINES ``Check``, so it
cannot import this module without a cycle.)
"""

from __future__ import annotations

from .verify import Check


def _fail(name: str, detail: str) -> Check:
    return Check(name, "FAIL", detail)


def _warn(name: str, detail: str) -> Check:
    return Check(name, "WARN", detail)


def _pass(name: str, detail: str) -> Check:
    return Check(name, "PASS", detail)
