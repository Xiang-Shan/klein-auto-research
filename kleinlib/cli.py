"""Command-line interface for the Klein v0.2 research workflow."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .scaffold import scaffold_study
from .workflow import (
    WorkflowError,
    finalize,
    migration_report,
    preflight_checks,
    record_gate,
    recover,
    resolve_study,
    run_one,
    status_summary,
    verify_study,
)


def _study_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--study", type=Path, default=Path("."), help="study directory (default: .)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="klein", description="Auditable single-machine ML research")
    parser.add_argument("--version", action="version", version="klein 0.2.0")
    sub = parser.add_subparsers(dest="command_name", required=True)

    new = sub.add_parser("new", help="scaffold a schema-v2 study")
    new.add_argument("slug", help="study id, e.g. 03-calibration")
    new.add_argument("--root", type=Path, default=Path("studies"))
    new.add_argument("--goal")
    new.add_argument("--domain")
    new.add_argument("--target")
    new.add_argument("--task-type", choices=("classification", "regression"), default="classification")
    new.add_argument("--method-depth", choices=("brief", "full"), default="full")
    new.add_argument("--family")
    new.add_argument("--track", default="primary")
    new.add_argument("--metric")
    new.add_argument("--goal-direction", choices=("higher", "lower"))
    new.add_argument("--minimum-delta", type=float, default=0.0)
    new.add_argument("--data")
    new.add_argument("--prepared-path")
    new.add_argument(
        "--split-kind",
        choices=("stratified", "random", "group", "time"),
        help="default: stratified for classification, random for regression",
    )
    new.add_argument("--group-column")
    new.add_argument("--time-column")
    new.add_argument("--max-run-seconds", type=int, default=600)

    gate = sub.add_parser("gate", help="record or explicitly override a gate")
    gate_sub = gate.add_subparsers(dest="gate_action", required=True)
    for action in ("record", "override"):
        p = gate_sub.add_parser(action)
        choices = ("consult", "data", "method", "phase") if action == "record" else (
            "consult",
            "data",
            "method",
        )
        p.add_argument("gate", choices=choices)
        _study_arg(p)
        p.add_argument("--acknowledged-by", required=True)
        p.add_argument("--note", default="")
        p.add_argument("--phase")
        if action == "override":
            p.add_argument("--reason", required=True)

    preflight = sub.add_parser("preflight", help="enforce gates, git, fingerprints, and ledger integrity")
    _study_arg(preflight)
    preflight.add_argument("--allow-dirty", action="store_true", help=argparse.SUPPRESS)

    run = sub.add_parser("run-one", help="commit and execute exactly one candidate transaction")
    _study_arg(run)
    run.add_argument("--track")
    run.add_argument("--description", default="")
    run.add_argument("--timeout-seconds", type=float)
    run.add_argument("--final-test", action="store_true")
    run.add_argument("--quiet", action="store_true")
    run.add_argument(
        "--command",
        nargs=argparse.REMAINDER,
        help="test/debug override; default is: uv run --locked python -u train.py",
    )

    recovery = sub.add_parser("recover", help="finish an interrupted evidence transaction")
    _study_arg(recovery)
    status = sub.add_parser("status", help="show gates, frontiers, transactions, and sealed-test use")
    _study_arg(status)
    final = sub.add_parser("finalize", help="mark findings exploratory or confirmed")
    _study_arg(final)
    final.add_argument("--allow-exploratory", action="store_true")

    migrate = sub.add_parser("migrate", help="report v1 compatibility without rewriting evidence")
    _study_arg(migrate)
    migrate.add_argument("--dry-run", action="store_true", required=True)
    migrate.add_argument("--report", type=Path)

    verify = sub.add_parser("verify", help="validate a v1 or v2 study")
    _study_arg(verify)
    return parser


def _print_checks(checks) -> int:
    failures = 0
    for check in checks:
        marker = "OK" if check.ok else "FAIL"
        print(f"[{marker}] {check.name}: {check.message}")
        failures += not check.ok
    print(f"summary: {len(checks)} checks, {failures} failed")
    return int(failures)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command_name == "new":
            study = scaffold_study(
                args.root,
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
                group_column=args.group_column,
                time_column=args.time_column,
                max_run_seconds=args.max_run_seconds,
            )
            print(f"scaffolded {study}")
            print(f"next: git switch -c experiments/{args.slug}")
            return 0
        study = resolve_study(args.study)
        if args.command_name == "gate":
            record_gate(
                study,
                args.gate,
                acknowledged_by=args.acknowledged_by,
                note=args.note,
                override_reason=getattr(args, "reason", None),
                phase=args.phase,
            )
            print(f"{args.gate_action}ed gate {args.gate}")
            return 0
        if args.command_name == "preflight":
            return _print_checks(preflight_checks(study, require_clean=not args.allow_dirty))
        if args.command_name == "run-one":
            manifest = run_one(
                study,
                track=args.track,
                description=args.description,
                timeout_seconds=args.timeout_seconds,
                final_test=args.final_test,
                command=args.command or None,
                echo=not args.quiet,
            )
            print(
                f"{manifest['experiment']}: {manifest['disposition']} "
                f"metric={manifest['primary_metric']} commit={manifest['candidate_commit']}"
            )
            return 0 if manifest["disposition"] != "crash" else 1
        if args.command_name == "recover":
            recovered = recover(study)
            print("recovered: " + (", ".join(recovered) if recovered else "none"))
            return 0
        if args.command_name == "status":
            print(status_summary(study), end="")
            return 0
        if args.command_name == "finalize":
            label = finalize(study, allow_exploratory=args.allow_exploratory)
            print(f"finalized: {label}")
            return 0
        if args.command_name == "migrate":
            report = migration_report(study)
            if args.report:
                args.report.write_text(report, encoding="utf-8")
                print(f"report: {args.report}")
            else:
                print(report, end="")
            return 0
        if args.command_name == "verify":
            return _print_checks(verify_study(study))
    except (WorkflowError, FileExistsError, ValueError) as exc:
        print(f"klein: error: {exc}", file=sys.stderr)
        return 2
    raise AssertionError(f"unhandled command {args.command_name}")


if __name__ == "__main__":
    raise SystemExit(main())
