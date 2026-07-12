#!/usr/bin/env python3
# ruff: noqa: E402, I001
"""Run one command once, stream combined output, and retain its real status.

This is intentionally small and dependency-free so shell-facing workflows do not
need a ``command | tee`` pipeline whose status can be misread.  Exit 124 denotes a
timeout; every log ends with a machine-readable runner status and exit code.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from kleinlib.runner import run_logged  # noqa: E402

def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout-seconds", type=float, required=True)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    return parser


def run(command: list[str], *, timeout_seconds: float, log_path: Path) -> int:
    result = run_logged(
        command,
        cwd=None,
        log_path=log_path,
        timeout_seconds=timeout_seconds,
        echo=True,
        write_footer=True,
    )
    return result.exit_code


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    try:
        return run(command, timeout_seconds=args.timeout_seconds, log_path=args.log)
    except (OSError, ValueError) as exc:
        print(f"run_with_log: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
