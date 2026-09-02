"""Shared fixtures for kleinlib tests.

``ready_study`` lives in ``test_workflow_v2``; re-exporting it here makes it
injectable by name in sibling modules without imports that shadow fixture
parameters (ruff F811).
"""

import sys

import pytest
from test_workflow_v2 import ready_study  # noqa: F401


def _forget_loaders_module() -> None:
    for name in ("loaders.python.hub", "loaders.python", "loaders"):
        sys.modules.pop(name, None)


@pytest.fixture(autouse=True)
def _isolated_loaders_module():
    """Undo `sys.path`/`sys.modules` mutation from the `loaders.python.hub` dotted name.

    Several tests (``test_data_hub_resolution.py``, ``test_sources.py``,
    ``test_doctor.py``) bind that name to a FRESH temp directory via
    ``$DATA_HUB`` (which `resolve()`/`_probe_data_hub` turn into
    ``sys.path.insert(0, ...)``). Two separate contamination vectors follow
    a plain "clear sys.modules" fix, and both need closing:

    1. **Import cache**: Python caches an import by its dotted name in
       ``sys.modules`` regardless of which directory produced it — cleared
       before AND after so neither a prior nor this test's import survives.
    2. **Path search order**: even with the cache cleared, an EARLIER test's
       ``sys.path.insert(0, ...)`` entry is still on ``sys.path`` (nothing
       ever removed it) — just no longer at index 0 once a later test
       inserts its own. A fresh import search still walks the REST of
       ``sys.path`` and can find that stale directory's real
       ``loaders/python/hub.py``. Snapshotting and restoring ``sys.path``
       closes this: every insertion a test makes (directly or through
       `resolve`/`_probe_data_hub`) is undone at teardown.

    Autouse and session-wide on purpose: the bug this guards against is
    test-order-dependent, so scoping it to only "the tests that seem to need
    it" would silently reintroduce the flake the moment a new test starts
    touching this name.
    """
    original_path = list(sys.path)
    _forget_loaders_module()
    yield
    sys.path[:] = original_path
    _forget_loaders_module()
