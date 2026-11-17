"""``klein probe`` — one exploratory look, on the record (``kleinlib/probe.py``)."""

from __future__ import annotations

import argparse
from pathlib import Path

from .api import emit
from .contract import resolve_study
from .errors import WorkflowError


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "probe",
        help="run one exploratory command on the record: logged, hash-chained, never at sealed data, never claim evidence",
        description="klein probe --study <dir> --note 'what I am looking for' -- python look.py. "
        "Allowed before the gates. The child sees KLEIN_PROBE=1 and KLEIN_PROBE_DIR (write "
        "figures there). `klein probe --list` prints the ledger.",
    )
    parser.add_argument("--study", type=Path, default=Path("."), help="study directory (default: .)")
    parser.add_argument("--note", default="", help="one line: what this look is for")
    parser.add_argument("--timeout", type=float, default=None, help="seconds (<= the contract's max_run_seconds)")
    parser.add_argument("--list", action="store_true", help="print the probe ledger and exit")
    parser.add_argument("--quiet", action="store_true", help="do not echo the command's output")
    parser.add_argument("probe_command", nargs=argparse.REMAINDER, metavar="-- COMMAND", help="the command to run")
    parser.set_defaults(handler=_run)


def _run(args: argparse.Namespace) -> int:
    from .probe import probe_chain_problems, read_probes, run_probe

    study = resolve_study(args.study)
    if args.list:
        rows = read_probes(study)
        problems = probe_chain_problems(study)
        emit({"probes": rows, "problems": problems})
        for row in rows:
            status = "ok" if row.get("exit_code") == 0 else f"exit {row.get('exit_code')}"
            print(f"{row.get('id')}  {row.get('timestamp')}  {status:8}  {' '.join(row.get('command', []))}")
            if row.get("note"):
                print(f"       {row['note']}")
        print(f"{len(rows)} probe(s)" + (f"; LEDGER DAMAGED: {'; '.join(problems)}" if problems else ""))
        return 1 if problems else 0
    command = list(args.probe_command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        raise WorkflowError("klein probe needs a command after `--`, e.g. `klein probe -- python look.py`")
    record = run_probe(study, command, note=args.note, timeout_seconds=args.timeout, echo=not args.quiet)
    emit({"probe": record})
    print(
        f"{record['id']}: exit {record['exit_code']} in {record['wall_seconds']}s — recorded in probes.jsonl "
        f"(log {record['log']['path']}); a probe is a lead, not evidence: register what it suggests as a prediction"
    )
    return 0 if record["exit_code"] == 0 else 1
