from __future__ import annotations

import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
VERIFY = REPO_ROOT / "scripts" / "verify_e2e.sh"
VERIFY_PY = REPO_ROOT / "scripts" / "verify_e2e.py"
RUN_WITH_LOG = REPO_ROOT / "scripts" / "run_with_log.py"


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=check,
        text=True,
        capture_output=True,
    )


def test_runner_preserves_nonzero_exit_and_combined_output(tmp_path: Path) -> None:
    log = tmp_path / "run.log"
    result = subprocess.run(
        [
            sys.executable,
            str(RUN_WITH_LOG),
            "--timeout-seconds",
            "5",
            "--log",
            str(log),
            "--",
            sys.executable,
            "-c",
            "import sys; print('before crash'); print('stderr line', file=sys.stderr); sys.exit(7)",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 7
    contents = log.read_text(encoding="utf-8")
    assert "before crash" in contents
    assert "stderr line" in contents
    assert "runner_status: crash" in contents
    assert "runner_exit_code: 7" in contents


def test_runner_times_out_and_records_timeout(tmp_path: Path) -> None:
    log = tmp_path / "run.log"
    started = time.monotonic()
    result = subprocess.run(
        [
            sys.executable,
            str(RUN_WITH_LOG),
            "--timeout-seconds",
            "0.1",
            "--log",
            str(log),
            "--",
            sys.executable,
            "-c",
            "import time; print('started', flush=True); time.sleep(30)",
        ],
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )

    assert time.monotonic() - started < 10
    assert result.returncode == 124
    contents = log.read_text(encoding="utf-8")
    assert "started" in contents
    assert "runner_status: timeout" in contents
    assert "runner_exit_code: 124" in contents


@pytest.mark.skipif(os.name != "posix", reason="POSIX process-group assertion")
def test_runner_timeout_terminates_descendants(tmp_path: Path) -> None:
    marker = tmp_path / "descendant-survived"
    child = f"import time; time.sleep(0.5); open({str(marker)!r}, 'w').write('alive')"
    parent = (
        "import subprocess,sys,time; "
        f"subprocess.Popen([sys.executable, '-c', {child!r}]); "
        "time.sleep(30)"
    )
    result = subprocess.run(
        [
            sys.executable,
            str(RUN_WITH_LOG),
            "--timeout-seconds",
            "0.1",
            "--log",
            str(tmp_path / "group.log"),
            "--",
            sys.executable,
            "-c",
            parent,
        ],
        check=False,
        timeout=10,
    )
    assert result.returncode == 124
    time.sleep(0.7)
    assert not marker.exists(), "a timed-out run left its descendant alive"


def test_verifier_refuses_to_delete_preexisting_branch(tmp_path: Path) -> None:
    branch = f"e2e-collision-test-{uuid.uuid4().hex}"
    _git("branch", branch, "HEAD")
    try:
        env = os.environ.copy()
        env["KLEIN_E2E_BRANCH_NAME"] = branch
        env["KLEIN_E2E_TMP_PARENT"] = str(tmp_path)
        result = subprocess.run(
            ["bash", str(VERIFY)],
            cwd=REPO_ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
            timeout=10,
        )
        assert result.returncode == 2
        assert "refusing to reuse or delete pre-existing branch" in result.stderr
        assert _git("show-ref", "--verify", f"refs/heads/{branch}", check=False).returncode == 0
    finally:
        _git("branch", "-D", "--", branch, check=False)


def test_verifier_cleans_owned_worktree_branch_and_temp_root(tmp_path: Path) -> None:
    branch = f"e2e-owned-test-{uuid.uuid4().hex}"
    env = os.environ.copy()
    env["KLEIN_E2E_BRANCH_NAME"] = branch
    env["KLEIN_E2E_TMP_PARENT"] = str(tmp_path)
    env["KLEIN_E2E_TEST_STOP_AFTER_WORKTREE"] = "1"
    result = subprocess.run(
        ["bash", str(VERIFY)],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=15,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert _git("show-ref", "--verify", f"refs/heads/{branch}", check=False).returncode != 0
    assert list(tmp_path.iterdir()) == []
    assert branch not in _git("worktree", "list", "--porcelain").stdout


def test_shim_is_a_thin_delegator_with_no_platform_specific_sed() -> None:
    contents = VERIFY.read_text(encoding="utf-8")
    assert "sed -i" not in contents
    assert "uv run --locked python" in contents
    # Documented as a two-line shim: shebang + one exec line, no logic of its own.
    non_blank_lines = [line for line in contents.splitlines() if line.strip()]
    assert len(non_blank_lines) == 2
    assert non_blank_lines[0].startswith("#!")
    assert non_blank_lines[1].startswith("exec ")


def test_verify_e2e_py_has_no_platform_specific_invocation() -> None:
    contents = VERIFY_PY.read_text(encoding="utf-8")
    assert "sed -i" not in contents
    assert "shell=True" not in contents
    assert "uv sync --locked" in contents
