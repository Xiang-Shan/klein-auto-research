"""The release's wheel check must look at the installed wheel, never the checkout."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _module():
    spec = importlib.util.spec_from_file_location(
        "check_installed_wheel", REPO / "scripts" / "check_installed_wheel.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _wheel_like(tmp_path: Path, module) -> Path:
    root = tmp_path / "site-packages" / "kleinlib"
    for sub in module.REQUIRED_DIRS:
        folder = root.joinpath(*sub.split("/"))
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "x.md").write_text("x\n")
    return root


def test_the_source_checkout_is_refused():
    found = _module().problems(REPO / "kleinlib")
    assert len(found) == 1 and "source checkout" in found[0]


def test_a_complete_installed_package_passes(tmp_path):
    module = _module()
    assert module.problems(_wheel_like(tmp_path, module)) == []


def test_a_missing_folder_and_shipped_tests_are_reported(tmp_path):
    module = _module()
    root = _wheel_like(tmp_path, module)
    (root / "_schemas" / "x.md").unlink()
    (root / "tests").mkdir()
    found = module.problems(root)
    assert any("kleinlib/_schemas" in line for line in found)
    assert any("kleinlib/tests" in line for line in found)


def test_both_workflows_run_the_check_from_outside_the_checkout():
    for name in ("release.yml", "ci.yml"):
        text = (REPO / ".github" / "workflows" / name).read_text()
        lines = [line for line in text.splitlines() if "check_installed_wheel.py" in line]
        assert lines, f"{name} does not run scripts/check_installed_wheel.py"
        for line in lines:
            assert re.search(r'cd "\$RUNNER_TEMP" &&', line), (name, line)
            assert "$GITHUB_WORKSPACE/scripts/check_installed_wheel.py" in line, (name, line)
