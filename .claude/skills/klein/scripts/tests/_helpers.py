"""Shared non-fixture helpers for the klein skill scripts test suite.

Lives in a distinctively-named module (NOT conftest.py) on purpose: test files
import these with ``from _helpers import ...``, and importing from ``conftest``
is what broke combined pytest runs — with multiple bare ``conftest.py`` files
in one collection (this suite's + a study's), whichever loads first owns the
``conftest`` name in ``sys.modules`` and the other suite's imports resolve
against the wrong module. conftest.py keeps only pytest fixtures.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = Path(__file__).resolve().parents[5]


def run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
