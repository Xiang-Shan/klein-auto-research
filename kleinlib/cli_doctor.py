"""CLI verb: `klein doctor` — environment and data-source readiness report.

One of the per-verb-group modules named by the WP-E convention (see
`common.md`): `register(subparsers)` adds the argparse subparser and hangs
its handler off the parsed namespace (`set_defaults(handler=run)`), and
`kleinlib.cli.build_parser` carries a single registration line
(`register_doctor(sub)`). `kleinlib.cli.main`'s generic
`if (handler := getattr(args, "handler", None)) is not None: return
handler(args)` dispatches `doctor` to `run` here without any per-verb
`if args.command_name == ...` block — so parallel packages adding their own
new verbs never collide inside `cli.py` (see `kleinlib/cli_claims.py` for the
same convention on a verb group with sub-subcommands).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .doctor import format_report, run_doctor


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "doctor",
        help="report environment and data-source readiness — never fetches, never mutates a study",
    )
    parser.add_argument(
        "--study",
        type=Path,
        default=None,
        help="also check this study's data.source tag (default: environment-only report)",
    )
    parser.add_argument("--json", action="store_true", help="emit the report as JSON")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit 1 if any check is not ok (default: exit 0 always — this is a report, not a gate)",
    )
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    report = run_doctor(study_dir=args.study)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=False))
    else:
        print(format_report(report), end="")
    if args.strict and not report["ok"]:
        return 1
    return 0
