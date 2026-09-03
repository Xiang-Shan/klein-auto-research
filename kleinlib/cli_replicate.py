"""``klein replicate …`` — the verb of the replication protocol.

One module per verb group so packages landing in parallel do not collide in
``cli.py``: :func:`register` builds the whole sub-command and hangs its handler
off the parsed namespace, and ``cli.py`` carries a single registration line.
The surface is the protocol's
(``.claude/skills/klein/references/replication-protocol.md`` "Internal"):

    klein replicate --study <dir> E0003 [--tolerance 0.001]
    klein replicate --study <dir> E0007 --verify-only     # verifier tracks
    klein replicate --study <dir> --list

Exit status: ``0`` when the record says ``reproduced: true``, ``1`` when it says
``false`` (the record is written and kept either way — a failed replication is
evidence, and the shell caller still deserves to be told), ``2`` for a refusal.
"""

from __future__ import annotations

import argparse

from .contract import resolve_study
from .errors import WorkflowError
from .replicate import list_replications, replicate_run

__all__ = ["register"]


def register(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    """Add ``klein replicate`` to a parser built by :func:`kleinlib.cli.build_parser`."""
    parser = subparsers.add_parser(
        "replicate",
        help="re-execute a development run and record whether its number reproduces",
        description=(
            "Internal replication: re-run one of this study's own development runs in a "
            "detached git worktree at its candidate commit, on the same prepared data, and "
            "record whether the printed metric reproduces within the tolerance ladder "
            "(--tolerance > minimum_delta > floor std > exact). Sealed runs and crashes are "
            "refused with no override. The manifest is never touched; the record is "
            "runs/E####/replications/<ts>.json and the evidence id is rep:E####@<ts> "
            "(verify:E####@<ts> for --verify-only). "
            "See .claude/skills/klein/references/replication-protocol.md."
        ),
        epilog=(
            "The worktree is prepared before the clock starts: the prepared DIRECTORY is "
            "copied in (prepare.py writes more than data.prepared_path), and a manifest "
            "command starting with `uv run` gets its own `uv sync --locked [--extra ...]` "
            "step at the worktree root. That setup is NOT charged to --timeout-seconds or "
            "to the manifest's max_run_seconds; its budget is "
            "KLEIN_REPLICATE_SETUP_SECONDS (default 1800s), and it is recorded on the "
            "record as setup_command / setup_extras / setup_seconds / setup_exit_code."
        ),
    )
    parser.add_argument(
        "experiment",
        nargs="?",
        help="the run to replicate, e.g. E0003 (omit with --list)",
    )
    parser.add_argument("--study", default=".", help="study directory (default: .)")
    parser.add_argument(
        "--tolerance",
        type=float,
        help="top rung of the tolerance ladder; overrides minimum_delta / floor std / exact",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="verifier tracks: re-run only the declared verifier on the pinned artifact "
        "in a fresh process (no worktree, no search re-run); records mode: verify",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        dest="list_records",
        help="list this study's replication records instead of making one",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        help="override the per-run timeout (default: the manifest's max_run_seconds); "
        "the environment-setup step has its own budget and is never charged to this",
    )
    parser.add_argument(
        "--quiet", action="store_true", help="do not echo the child's output"
    )
    parser.set_defaults(handler=_run)
    return parser


def _run(args: argparse.Namespace) -> int:
    study = resolve_study(args.study)
    if args.list_records:
        if args.experiment:
            raise WorkflowError("--list lists every record; drop the experiment id")
        return _print_list(study)
    if not args.experiment:
        raise WorkflowError("an experiment id is required, e.g. `klein replicate E0003`")
    record = replicate_run(
        study,
        args.experiment,
        tolerance=args.tolerance,
        verify_only=args.verify_only,
        timeout_seconds=args.timeout_seconds,
        echo=not args.quiet,
    )
    verdict = "reproduced" if record["reproduced"] else "NOT reproduced"
    difference = record.get("difference")
    measured = "difference=NA" if difference is None else f"difference={difference:.6g}"
    print(
        f"{record['experiment']}: {verdict} ({record['mode']}) {measured} "
        f"tolerance={record['tolerance']:.6g} [{record['tolerance_source']}] "
        f"evidence={record['evidence_id']}"
    )
    if record.get("failure_reason"):
        print(f"  reason: {record['failure_reason']}")
    if record.get("mismatched_keys"):
        print("  block keys outside tolerance: " + ", ".join(record["mismatched_keys"]))
    if not record.get("environment_match", True):
        print(
            "  environment fingerprint differs from the original run — compare device, "
            "library versions and thread counts before reading the difference"
        )
    print(f"  record: {record['record']}")
    return 0 if record["reproduced"] else 1


def _print_list(study) -> int:
    rows = list_replications(study)
    if not rows:
        print("no replication records; make one with `klein replicate E0003`")
        return 0
    print(f"{'experiment':<11} {'mode':<10} {'reproduced':<11} {'difference':<13} tolerance  evidence")
    for row in rows:
        difference = row["difference"]
        printed = "NA" if difference is None else f"{float(difference):.6g}"
        tolerance = row["tolerance"]
        tolerance_text = "NA" if tolerance is None else f"{float(tolerance):.6g}"
        print(
            f"{row['experiment']:<11} {str(row['mode']):<10} "
            f"{str(bool(row['reproduced'])).lower():<11} {printed:<13} "
            f"{tolerance_text:<10} {row['evidence_id']}"
        )
    print(f"summary: {len(rows)} records, {sum(1 for r in rows if r['reproduced'])} reproduced")
    return 0
