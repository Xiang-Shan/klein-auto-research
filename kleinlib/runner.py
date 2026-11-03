"""One portable, single-execution subprocess runner for Klein.

Both the packaged workflow and shell-facing helper use this implementation so exit
status, timeout, process-group termination, and log semantics cannot drift.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

TIMEOUT_EXIT_CODE = 124


@dataclass(frozen=True)
class LoggedRun:
    command: tuple[str, ...]
    exit_code: int
    timed_out: bool
    wall_seconds: float


def _stop_process_group(process: subprocess.Popen[str], *, force: bool) -> None:
    """Stop the child and every descendant placed in its dedicated process group."""
    if os.name == "posix":
        sig = signal.SIGKILL if force else signal.SIGTERM
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            pass
    elif force:  # pragma: no cover - exercised by Windows smoke CI
        process.kill()
    else:  # pragma: no cover - exercised by Windows smoke CI
        process.terminate()


def _pump(source: TextIO, log: TextIO, *, echo: bool) -> None:
    for line in iter(source.readline, ""):
        log.write(line)
        log.flush()
        if echo:
            sys.stdout.write(line)
            sys.stdout.flush()


def run_logged(
    command: Sequence[str],
    *,
    cwd: Path | None,
    log_path: Path,
    timeout_seconds: float,
    echo: bool = True,
    env_overrides: Mapping[str, str] | None = None,
    write_footer: bool = True,
    append: bool = False,
) -> LoggedRun:
    """Execute *command* once and return its real status (124 on timeout).

    ``append`` keeps whatever the log already holds: one log file can then carry
    two consecutive sections (``klein replicate`` writes its environment-setup
    step before the run it is judged on). The default truncates, so a run log is
    the log of that run alone.
    """
    if timeout_seconds <= 0:
        raise ValueError("timeout must be greater than zero")
    if not command:
        raise ValueError("a command is required")
    env = os.environ.copy()
    # A stale VIRTUAL_ENV from a driving session makes uv warn into every
    # archived run.log; uv resolves the project env itself, so drop it.
    env.pop("VIRTUAL_ENV", None)
    env["PYTHONUNBUFFERED"] = "1"
    # The pump below decodes UTF-8; on Windows a child's piped stdout would
    # otherwise use the ANSI code page and crash on the first non-ASCII
    # character an entrypoint prints. An explicit setting in the caller's
    # environment wins.
    env.setdefault("PYTHONUTF8", "1")
    env.update(env_overrides or {})
    log_path.parent.mkdir(parents=True, exist_ok=True)
    popen_kwargs: dict[str, object] = {}
    if os.name == "posix":
        popen_kwargs["start_new_session"] = True
    elif os.name == "nt":  # pragma: no cover - exercised by Windows smoke CI
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    started = time.monotonic()
    with log_path.open("a" if append else "w", encoding="utf-8", newline="") as log:
        process = subprocess.Popen(
            list(command),
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            **popen_kwargs,
        )
        assert process.stdout is not None
        pump = threading.Thread(target=_pump, args=(process.stdout, log), kwargs={"echo": echo}, daemon=True)
        pump.start()
        timed_out = False
        try:
            return_code = process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            _stop_process_group(process, force=False)
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                _stop_process_group(process, force=True)
                process.wait()
            return_code = TIMEOUT_EXIT_CODE
        finally:
            pump.join(timeout=5)
            process.stdout.close()
        if write_footer:
            status = "timeout" if timed_out else ("ok" if return_code == 0 else "crash")
            footer = f"runner_status: {status}\nrunner_exit_code: {return_code}\n"
            log.write(footer)
            log.flush()
            if echo:
                sys.stdout.write(footer)
                sys.stdout.flush()
    return LoggedRun(
        command=tuple(command),
        exit_code=return_code,
        timed_out=timed_out,
        wall_seconds=time.monotonic() - started,
    )


def run_seed_array(
    command: Sequence[str],
    seeds: Sequence[int],
    *,
    cwd: Path | None,
    log_path: Path,
    timeout_seconds: float,
    echo: bool = True,
    env_overrides: Mapping[str, str] | None = None,
    append: bool = False,
) -> LoggedRun:
    """Run *command* once per seed into ONE log (Klein 2.3 ``entrypoint.seeds``).

    Each child gets ``KLEIN_SEED`` and is preceded in the log by the header
    ``[KLEIN] seed i/N (KLEIN_SEED=s)`` the notary parses back.  The array shares
    one ``timeout_seconds`` (it is one transaction); the first failing seed stops
    the array and its exit code is the array's.
    """
    started = time.monotonic()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if not append:
        log_path.write_text("", encoding="utf-8")
    exit_code = 0
    timed_out = False
    total = len(seeds)
    for position, seed in enumerate(seeds, start=1):
        remaining = timeout_seconds - (time.monotonic() - started)
        if remaining <= 0:
            exit_code, timed_out = TIMEOUT_EXIT_CODE, True
            break
        header = f"[KLEIN] seed {position}/{total} (KLEIN_SEED={int(seed)})\n"
        with log_path.open("a", encoding="utf-8") as log:
            log.write(header)
        if echo:
            sys.stdout.write(header)
            sys.stdout.flush()
        result = run_logged(
            command,
            cwd=cwd,
            log_path=log_path,
            timeout_seconds=remaining,
            echo=echo,
            env_overrides={**(env_overrides or {}), "KLEIN_SEED": str(int(seed))},
            append=True,
        )
        if result.exit_code != 0:
            exit_code, timed_out = result.exit_code, result.timed_out
            break
    return LoggedRun(
        command=tuple(command),
        exit_code=exit_code,
        timed_out=timed_out,
        wall_seconds=time.monotonic() - started,
    )
