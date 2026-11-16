"""``klein map`` — the study's evidence graph (read-only; ``kleinlib/study_map.py``)."""

from __future__ import annotations

import argparse
from pathlib import Path

from .api import emit
from .contract import resolve_study


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "map",
        help="the study as a map: question → predictions → evidence → claims → decisions, and what is still open",
        description="Derived from the records and read-only. Text by default; --json for the "
        "graph as data; --html writes one self-contained page.",
    )
    parser.add_argument("--study", type=Path, default=Path("."), help="study directory (default: .)")
    parser.add_argument(
        "--html",
        nargs="?",
        const="",
        default=None,
        metavar="PATH",
        help="write the map as one self-contained HTML page (default path: <study>/report/map.html)",
    )
    parser.set_defaults(handler=_run)


def _run(args: argparse.Namespace) -> int:
    from .study_map import build_map, format_map, write_html

    study = resolve_study(args.study)
    data = build_map(study)
    emit(data)
    if args.html is not None:
        target = write_html(study, args.html or None)
        emit({"html": str(target)})
        print(f"wrote {target}")
        return 0
    print(format_map(data), end="")
    return 0
