"""``klein probe`` — exploration on the record.

Research starts with looking: a histogram, a quick fit, "what happens if".  A
``run-one`` transaction is the wrong tool for that — it needs three gates and
decides a disposition — and looking off the record is how forking paths begin.
A probe is the third thing:

* **cheap** — one bounded subprocess, no gate, no disposition, no result row;
* **recorded** — ``probes.jsonl`` is append-only and hash-chained: the command,
  the hash of every study file it named, the hash of its output, a note;
* **fenced** — the child runs with ``KLEIN_PROBE=1``, under which
  :func:`kleinlib.data.load_partition` refuses the sealed partition and
  :func:`kleinlib.data.contract_split` returns it empty;
* **never evidence** — a probe id (``X0001``) is not an evidence id the claims
  law resolves, so no claim can rest on one.  A probe earns a *prediction*: what
  it suggested is registered, then tested by a run that did not know the answer.

The consult gate records how many probes existed when the contract was
acknowledged (and the chain head), so "what was looked at before the question
was fixed" rests on a hash.  ``references/exploration-protocol.md``.
"""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .contract import load_contract
from .errors import WorkflowError
from .primitives import StudyLock, canonical_json, sha256_bytes, sha256_file, utc_now

__all__ = [
    "PROBE_ENV",
    "PROBES_DIR",
    "PROBES_FILE",
    "probe_chain_problems",
    "probe_head",
    "read_probes",
    "run_probe",
]

PROBES_FILE = "probes.jsonl"
PROBES_DIR = "probes"
#: Set to ``1`` in a probe's child process; the data loaders read it.
PROBE_ENV = "KLEIN_PROBE"


def read_probes(study_dir: Path) -> list[dict[str, Any]]:
    path = Path(study_dir) / PROBES_FILE
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise WorkflowError(f"{PROBES_FILE} line {lineno} is invalid JSON: {exc}") from exc
        if not isinstance(row, dict):
            raise WorkflowError(f"{PROBES_FILE} line {lineno} is not an object")
        rows.append(row)
    return rows


def _hash_of(body: dict[str, Any]) -> str:
    return sha256_bytes(canonical_json(body).encode())


def probe_head(study_dir: Path) -> dict[str, Any]:
    """``{"count": n, "head": <hash of the last probe or None>}`` — what a gate records."""
    rows = read_probes(Path(study_dir))
    return {"count": len(rows), "head": rows[-1].get("hash") if rows else None}


def probe_chain_problems(study_dir: Path, *, recorded: dict[str, Any] | None = None) -> list[str]:
    """Every way the probe ledger fails to be the append-only record it claims to be.

    ``recorded`` is the ``{"count", "head"}`` a gate stored: the ledger must still
    begin with exactly those probes.
    """
    study = Path(study_dir)
    try:
        rows = read_probes(study)
    except WorkflowError as exc:
        return [str(exc)]
    problems: list[str] = []
    previous: str | None = None
    for index, row in enumerate(rows, start=1):
        label = str(row.get("id") or f"probe {index}")
        body = dict(row)
        given = body.pop("hash", None)
        if row.get("id") != f"X{index:04d}":
            problems.append(f"{label}: id should be X{index:04d}")
        if row.get("previous_hash") != previous:
            problems.append(f"{label}: previous_hash does not match the probe before it")
        if given != _hash_of(body):
            problems.append(f"{label}: hash does not match its content")
        log = row.get("log") if isinstance(row.get("log"), dict) else {}
        log_path = study / str(log.get("path") or "")
        if not log.get("path") or not log_path.is_file():
            problems.append(f"{label}: its log is missing")
        elif sha256_file(log_path) != log.get("sha256"):
            problems.append(f"{label}: its log changed after it was recorded")
        previous = given if isinstance(given, str) else None
    if recorded and recorded.get("count"):
        count = int(recorded["count"])
        if len(rows) < count or rows[count - 1].get("hash") != recorded.get("head"):
            problems.append(
                f"the first {count} probe(s) are not the ones the consult gate recorded — "
                "the ledger is append-only"
            )
    return problems


def _named_files(study: Path, command: Sequence[str]) -> dict[str, str]:
    """sha256 of every study file the command names — the script that did the looking."""
    hashes: dict[str, str] = {}
    root = study.resolve()
    for argument in command:
        candidate = (study / argument) if not os.path.isabs(argument) else Path(argument)
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved.is_file() and (resolved == root or root in resolved.parents):
            hashes[resolved.relative_to(root).as_posix()] = sha256_file(resolved)
    return hashes


def run_probe(
    study_dir: Path,
    command: Sequence[str],
    *,
    note: str = "",
    timeout_seconds: float | None = None,
    echo: bool = True,
    commit: bool = True,
) -> dict[str, Any]:
    """Run one exploratory command and append its record.  Returns the record."""
    from .runner import run_logged
    from .transaction import commit_state_writes, git

    study = Path(study_dir)
    command = [str(part) for part in command]
    if not command:
        raise WorkflowError("klein probe needs a command after `--`, e.g. `klein probe -- python look.py`")
    contract = load_contract(study)
    try:
        limit = float(contract.get("max_run_seconds") or 600)
    except (TypeError, ValueError):
        limit = 600.0
    timeout = float(timeout_seconds) if timeout_seconds is not None else limit
    if timeout <= 0 or timeout > limit:
        raise WorkflowError(f"timeout must be > 0 and <= the contract's max_run_seconds={limit:g}")

    with StudyLock(study):
        existing = read_probes(study)
        problems = probe_chain_problems(study)
        if problems:
            raise WorkflowError("the probe ledger is damaged: " + "; ".join(problems))
        probe_id = f"X{len(existing) + 1:04d}"
        out_dir = study / PROBES_DIR / probe_id
        out_dir.mkdir(parents=True, exist_ok=True)
        log_rel = f"{PROBES_DIR}/{probe_id}.log"
        named = _named_files(study, command)
        started = utc_now()
        result = run_logged(
            command,
            cwd=study,
            log_path=study / log_rel,
            timeout_seconds=timeout,
            echo=echo,
            env_overrides={
                PROBE_ENV: "1",
                "KLEIN_PROBE_ID": probe_id,
                "KLEIN_PROBE_DIR": str(out_dir),
                "KLEIN_EVALUATION_KIND": "development",
                "KLEIN_SMOKE": "",
            },
        )
        head = git(study, ["rev-parse", "HEAD"], check=False)
        body: dict[str, Any] = {
            "id": probe_id,
            "sequence": len(existing) + 1,
            "timestamp": started,
            "command": command,
            "note": " ".join(note.split()),
            "exit_code": result.exit_code,
            "timed_out": result.timed_out,
            "wall_seconds": round(result.wall_seconds, 3),
            "files": named,
            "log": {"path": log_rel, "sha256": sha256_file(study / log_rel)},
            "git_head": head.stdout.strip() if head.returncode == 0 else None,
            "previous_hash": existing[-1].get("hash") if existing else None,
        }
        record = {**body, "hash": _hash_of(body)}
        with (study / PROBES_FILE).open("a", encoding="utf-8") as handle:
            handle.write(canonical_json(record) + "\n")
        if not any(out_dir.iterdir()):
            out_dir.rmdir()
        if commit:
            commit_state_writes(
                study,
                f"klein: probe {probe_id}",
                paths=(PROBES_FILE, log_rel, f"{PROBES_DIR}/{probe_id}"),
                scope="own",
            )
    return record
