#!/usr/bin/env python3
"""Compatibility entry point for the packaged ``klein new`` command.

The implementation lives in :mod:`kleinlib.scaffold` so installed wheels and agent
protocols create byte-compatible schema-v2 studies.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from kleinlib.scaffold import scaffold_study  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scaffold a Klein schema-v2 study")
    parser.add_argument("slug", help="NN-lowercase-slug")
    parser.add_argument("--goal")
    parser.add_argument("--domain")
    parser.add_argument("--target")
    parser.add_argument("--task-type", choices=("classification", "regression", "simulation"), default="classification")
    parser.add_argument("--method-depth", choices=("brief", "full"), default="full")
    parser.add_argument("--family")
    parser.add_argument("--track", default="primary")
    parser.add_argument("--metric")
    parser.add_argument("--goal-direction", choices=("higher", "lower"))
    parser.add_argument("--minimum-delta", type=float, default=0.0)
    parser.add_argument("--data")
    parser.add_argument("--prepared-path")
    parser.add_argument("--split-kind", choices=("stratified", "random", "group", "time", "none"), default=None)
    parser.add_argument("--max-run-seconds", type=int, default=600)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        study = scaffold_study(
            REPO_ROOT / "studies",
            args.slug,
            goal=args.goal,
            domain=args.domain,
            target=args.target,
            task_type=args.task_type,
            method_depth=args.method_depth,
            family=args.family,
            track=args.track,
            metric_name=args.metric,
            metric_goal=args.goal_direction,
            minimum_delta=args.minimum_delta,
            data_source=args.data,
            data_path=args.prepared_path,
            split_kind=args.split_kind,
            max_run_seconds=args.max_run_seconds,
        )
    except (FileExistsError, ValueError) as exc:
        print(f"[REFUSE] {exc}", file=sys.stderr)
        return 1
    print(f"[OK] scaffolded {study.relative_to(REPO_ROOT)}/ (schema_version: 2)")
    print(f"Next: git switch -c experiments/{args.slug}")
    print("Then record CONSULT, DATA, and METHOD gates with `klein gate record`.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
