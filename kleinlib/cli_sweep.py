"""``klein sweep …`` — registering a measurement sweep as citable evidence.

A **search** sweep ends in exactly one winner transaction (``sweep-rules.md``
rules 3-7): its evidence is the run manifest.  A **measurement** sweep — the
Phase-0 noise floor, a split lottery, a per-candidate paired floor, a permission
map — promotes no winner and writes no ``results.tsv`` row at all, so before
schema 3 its only trace was a sidecar cited from prose.  Study 09 kept a 42-cell
permission map that way and had to invent ``claims.lock`` to re-anchor it.

``klein sweep register`` closes that gap::

    klein sweep register --study studies/NN-slug <name> \\
        --sidecar sweeps/<name>.sidecar.tsv --script sweeps/<name>.py

It hashes the sidecar and the script into ``state.sweeps[<name>]``, counts the
ok and crash rows (crash rows are DATA — where a method breaks is a finding:
studies 07 and 08 both kept a registered crash rung), appends the event
``sweep_registered`` and files its own state commit.  Findings and the claims
lock can then cite the sweep as ``sweep:<name>``, and
``kleinlib.checks.sweep_registry_problems`` re-hashes it at ``klein verify`` —
a sidecar edited after registration fails.

One module per verb group so packages landing in parallel do not collide in
``cli.py``: ``register(subparsers)`` builds the whole ``sweep`` sub-command and
hangs its handler off the parsed namespace.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

from .contract import load_contract, resolve_study
from .errors import WorkflowError
from .events import append_event
from .primitives import StudyLock, sha256_file, utc_now
from .state import load_state, save_state
from .sweep import SIDECAR_COLUMNS
from .transaction import commit_state_writes

__all__ = ["register", "register_sweep", "sidecar_row_counts"]

#: The keys ``state.sweeps[<name>]`` carries.  ``sidecar``/``script`` are the
#: study-relative paths the verify-time re-hash reads; the rest is the receipt.
SWEEP_RECORD_KEYS: tuple[str, ...] = (
    "sidecar",
    "sidecar_sha256",
    "script",
    "script_sha256",
    "rows_ok",
    "rows_crash",
    "registered_at",
)


def sidecar_row_counts(path: Path) -> tuple[int, int]:
    """``(ok, crash)`` row counts of a sweep sidecar.

    Crash rows are kept and counted, never filtered: a trial that broke is
    evidence about where the method breaks (``sweep-rules.md``, the measurement
    carve-out).  A row with any other status is counted as neither and reported
    by :func:`register_sweep` as a problem, so a hand-edited sidecar cannot be
    registered as if it were a clean run.
    """
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        header = tuple(reader.fieldnames or ())
        if header[: len(SIDECAR_COLUMNS)] != SIDECAR_COLUMNS:
            raise WorkflowError(
                f"{path.name} is not a sweep sidecar: header {list(header)} does not "
                f"start with {list(SIDECAR_COLUMNS)}"
            )
        ok = crash = other = 0
        for row in reader:
            status = (row.get("status") or "").strip()
            if status == "ok":
                ok += 1
            elif status == "crash":
                crash += 1
            else:
                other += 1
    if other:
        raise WorkflowError(
            f"{path.name} has {other} row(s) whose status is neither 'ok' nor "
            "'crash' — a sidecar is the full search record, written by "
            "kleinlib.sweep.SweepRunner, not by hand"
        )
    return ok, crash


def _study_relative(study: Path, path: Path, *, label: str) -> Path:
    """Resolve a study-relative or absolute path and refuse one outside the study."""
    resolved = (path if path.is_absolute() else study / path).resolve()
    try:
        resolved.relative_to(study.resolve())
    except ValueError as exc:
        raise WorkflowError(
            f"--{label} {path.as_posix()!r} lies outside the study directory — a "
            "registered sweep's evidence must live inside the study that cites it"
        ) from exc
    if not resolved.is_file():
        raise WorkflowError(f"--{label} does not exist: {path.as_posix()}")
    return resolved


def register_sweep(
    study_dir: Path,
    name: str,
    *,
    sidecar: Path,
    script: Path,
) -> dict[str, Any]:
    """Hash a measurement sweep into ``state.sweeps`` and file the state commit.

    Re-registering the same name is allowed and OVERWRITES the record: a sweep
    legitimately gets re-run (a longer ladder, a corrected seed domain), and the
    event log keeps both registrations, so nothing is lost by taking the latest
    hashes as current.
    """
    if not name.strip():
        raise WorkflowError("a sweep needs a name — findings cite it as sweep:<name>")
    contract = load_contract(study_dir)
    study = study_dir.resolve()
    sidecar_path = _study_relative(study, Path(sidecar), label="sidecar")
    script_path = _study_relative(study, Path(script), label="script")
    rows_ok, rows_crash = sidecar_row_counts(sidecar_path)
    if rows_ok + rows_crash == 0:
        raise WorkflowError(
            f"{sidecar_path.name} has no trial rows — there is no measurement to register"
        )

    with StudyLock(study_dir):
        state = load_state(study_dir, contract)
        record = {
            "sidecar": sidecar_path.relative_to(study).as_posix(),
            "sidecar_sha256": sha256_file(sidecar_path),
            "script": script_path.relative_to(study).as_posix(),
            "script_sha256": sha256_file(script_path),
            "rows_ok": rows_ok,
            "rows_crash": rows_crash,
            "registered_at": utc_now(),
        }
        state.setdefault("sweeps", {})[name] = record
        append_event(study_dir, "sweep_registered", sweep=name, **record)
        save_state(study_dir, state)
        commit_state_writes(study_dir, f"klein: measurement sweep registered ({name})")
    return record


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def register(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    """Add ``klein sweep`` to a parser built by :func:`kleinlib.cli.build_parser`."""
    sweep = subparsers.add_parser(
        "sweep",
        help="register a measurement sweep so findings can cite it as sweep:<name>",
        description=(
            "A measurement sweep promotes no winner and writes no results.tsv row; "
            "registering it hashes the sidecar and the script into study_state.json "
            "so the evidence is citable and tamper-evident. See "
            ".claude/skills/klein/references/sweep-rules.md (the measurement carve-out)."
        ),
    )
    actions = sweep.add_subparsers(dest="sweep_action", required=True)

    register_cmd = actions.add_parser(
        "register",
        help="hash a sweep's sidecar + script into state.sweeps and log the event",
    )
    register_cmd.add_argument(
        "--study", type=Path, default=Path("."), help="study directory (default: .)"
    )
    register_cmd.add_argument("name", help="the name findings cite, e.g. noise_floor")
    register_cmd.add_argument(
        "--sidecar",
        type=Path,
        required=True,
        help="study-relative sidecar TSV, e.g. sweeps/<name>.sidecar.tsv",
    )
    register_cmd.add_argument(
        "--script",
        type=Path,
        required=True,
        help="study-relative sweep script, e.g. sweeps/<name>.py",
    )
    register_cmd.set_defaults(handler=_run_register)
    return sweep


def _run_register(args: argparse.Namespace) -> int:
    study = resolve_study(args.study)
    record = register_sweep(
        study, args.name, sidecar=args.sidecar, script=args.script
    )
    print(
        f"registered sweep:{args.name} — {record['sidecar']} "
        f"sha256={record['sidecar_sha256'][:12]}… "
        f"({record['rows_ok']} ok, {record['rows_crash']} crash), "
        f"script {record['script']} sha256={record['script_sha256'][:12]}…"
    )
    if record["rows_crash"]:
        print(
            "note: crash rows are retained evidence about where the method breaks — "
            "cite them, do not re-run them away"
        )
    return 0
