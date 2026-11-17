"""A study's command is launched from the CHILD's PATH, on every platform.

Windows searches the running program's own directory before PATH, and inside a
virtual environment that is the base interpreter's directory. A contract that says
``python -u train.py`` therefore ran the base Python — no ``kleinlib``, none of
the study's libraries — and ``klein demo`` crashed on its first probe there. The
first full Windows run of the suite on 3.0 found it (22 tests, one cause).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from kleinlib.runner import _resolved, run_logged


def _tool(directory: Path, name: str, says: str) -> Path:
    """A tiny program ``name`` that prints ``says``, runnable on this platform."""
    directory.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        path = directory / f"{name}.cmd"
        path.write_text(f"@echo {says}\r\n", encoding="utf-8")
    else:
        path = directory / name
        path.write_text(f"#!/bin/sh\necho {says}\n", encoding="utf-8")
        path.chmod(0o755)
    return path


def test_a_bare_program_name_is_resolved_on_the_given_path(tmp_path: Path) -> None:
    tool = _tool(tmp_path / "bin", "klein-test-tool", "hello")
    argv = _resolved(["klein-test-tool", "-u", "train.py"], {"PATH": str(tmp_path / "bin")})
    assert Path(argv[0]).resolve() == tool.resolve()
    assert argv[1:] == ["-u", "train.py"]  # only the program is resolved


def test_a_path_and_an_unknown_program_are_launched_as_written(tmp_path: Path) -> None:
    env = {"PATH": str(tmp_path)}
    assert _resolved([sys.executable, "-c", "pass"], env) == [sys.executable, "-c", "pass"]
    assert _resolved(["./tools/run.sh"], env) == ["./tools/run.sh"]
    assert _resolved(["no-such-program-anywhere"], env) == ["no-such-program-anywhere"]


def test_the_child_path_decides_which_program_runs(tmp_path: Path) -> None:
    # Two programs with one name. The one on the CHILD's PATH must win, whatever
    # this process's own PATH or program directory would have picked.
    _tool(tmp_path / "wrong", "klein-test-tool", "the-wrong-one")
    _tool(tmp_path / "right", "klein-test-tool", "the-right-one")
    child_path = os.pathsep.join([str(tmp_path / "right"), str(tmp_path / "wrong"), os.environ.get("PATH", "")])
    log = tmp_path / "run.log"
    result = run_logged(
        ["klein-test-tool"],
        cwd=tmp_path,
        log_path=log,
        timeout_seconds=30,
        echo=False,
        env_overrides={"PATH": child_path},
    )
    text = log.read_text(encoding="utf-8")
    assert result.exit_code == 0, text
    assert "the-right-one" in text and "the-wrong-one" not in text
