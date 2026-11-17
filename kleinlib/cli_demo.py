"""``klein demo`` -- a real, runnable walkthrough study (``kleinlib/demo.py``)."""

from __future__ import annotations

import argparse
from pathlib import Path

from .api import emit


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "demo",
        help="watch a real study run: scaffold, a probe, three gates, a measured bar, three notarized runs",
        description="Creates a tiny study in a fresh directory (its own git repository) and runs the first "
        "half of the lifecycle live and offline on scikit-learn's bundled breast-cancer table, "
        "narrating each step. Real gates, real run-one transactions; the gate acknowledgements say "
        "the demo is automated. It never spends the sealed partition and stops where a person "
        "would take over.",
    )
    parser.add_argument(
        "--dir",
        type=Path,
        default=Path("klein-demo"),
        help="a directory that does not exist yet, or is empty (default: ./klein-demo)",
    )
    parser.add_argument("--quiet", action="store_true", help="skip the narration; print one summary line")
    parser.set_defaults(handler=_run)


def _run(args: argparse.Namespace) -> int:
    from .demo import run_demo

    summary = run_demo(args.dir, echo=not args.quiet)
    emit(summary)
    if args.quiet:
        runs = ", ".join(f"{r['experiment']}={r['disposition']}" for r in summary["runs"])
        verdicts = ", ".join(f"{k}={v}" for k, v in summary["predictions"].items())
        print(f"klein demo: {summary['study']} in {summary['seconds']}s -- {runs}; {verdicts}")
    return 0
