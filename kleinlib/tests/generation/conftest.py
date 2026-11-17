"""Make the parent tests directory importable from the generation tests.

These tests import helpers from sibling test modules by bare name
(``from test_workflow_v3 import …``).  pytest's default ``prepend`` import mode puts
``kleinlib/tests`` on ``sys.path`` because ``kleinlib/tests/conftest.py`` lives there;
this file states the dependency explicitly so it does not rest on that side effect.
The shared fixtures (``ready_study`` …) still come from ``kleinlib/tests/conftest.py``.
"""

import sys
from pathlib import Path

_TESTS = str(Path(__file__).resolve().parents[1])
if _TESTS not in sys.path:
    sys.path.insert(0, _TESTS)
