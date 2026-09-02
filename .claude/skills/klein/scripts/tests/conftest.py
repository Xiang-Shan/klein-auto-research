"""Shared fixtures for the klein skill scripts test suite.

Scripts under ``.claude/skills/klein/scripts/`` are deliberately not a
package (no ``__init__.py``) — the skill must remain usable by copying the
directory alone into a foreign repo — so tests load ``summarize_results.py``
directly via ``importlib.util`` rather than a normal ``import``.
"""

from __future__ import annotations

import importlib.util
import sys
import types

import pytest
from _helpers import SCRIPTS_DIR


def _load_module(name: str, filename: str) -> types.ModuleType:
    path = SCRIPTS_DIR / filename
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def summarize_module() -> types.ModuleType:
    return _load_module("klein_summarize", "summarize_results.py")
