"""Check that the INSTALLED klein wheel carries its package data.

Run it with the interpreter of the environment the wheel was installed into, from a
directory outside the repository::

    cd "$RUNNER_TEMP" && "$venv/bin/python" "$GITHUB_WORKSPACE/scripts/check_installed_wheel.py"

The release workflow and CI's wheel job both run this one file, so the check that guards
a release is exercised on every pull request. It refuses to pass when ``kleinlib``
resolves to a source checkout: the 3.0.0 release failed because the check then ran from
the repository root and inspected the source tree, which has no ``_skill`` folder.
"""

from __future__ import annotations

import importlib.resources
import sys
from pathlib import Path

# An installed Klein must carry its recipes, its skill (protocols, profiles, templates,
# report scripts), the worker agents and the JSON Schemas.
REQUIRED_DIRS = (
    "recipes",
    "_skill/references",
    "_skill/references/profiles",
    "_skill/references/generation",
    "_skill/assets",
    "_skill/assets/generation",
    "_skill/scripts",
    "_agents",
    "_schemas",
)


def problems(root: Path) -> list[str]:
    """What is wrong with the package at ``root``; empty when it is a complete wheel."""
    found: list[str] = []
    if (root.parent / "pyproject.toml").is_file():
        found.append(
            f"kleinlib resolves to a source checkout ({root}), not an installed wheel — "
            "run this check from a directory outside the repository"
        )
        return found
    for sub in REQUIRED_DIRS:
        path = root.joinpath(*sub.split("/"))
        if not path.is_dir() or not any(path.iterdir()):
            found.append(f"package data missing from the wheel: kleinlib/{sub}")
    if (root / "tests").is_dir():
        found.append("the test suite must not ship in the wheel: kleinlib/tests")
    return found


def main() -> int:
    root = Path(str(importlib.resources.files("kleinlib")))
    found = problems(root)
    for line in found:
        print(f"FAIL: {line}", file=sys.stderr)
    if not found:
        print(f"OK: {root} carries {len(REQUIRED_DIRS)} package-data folders and no tests")
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main())
