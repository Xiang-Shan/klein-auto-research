"""``klein probe`` — exploration on the record.

Research starts with looking: a histogram, a quick fit, "what happens if".  A
``run-one`` transaction is the wrong tool for that — it needs three gates and
decides a disposition — and looking off the record is how forking paths begin.
A probe is the third thing:

* **cheap** — one bounded subprocess, no gate, no disposition, no result row;
* **recorded** — ``probes.jsonl`` is append-only and hash-chained (the command,
  the hash of every study file it named, the hash of its output, a note), and
  each probe also leaves a ``probe_recorded`` event in the study's own event
  chain, so a ledger that was truncated, deleted or rewritten no longer agrees
  with ``events.jsonl``;
* **fenced** — the child runs with ``KLEIN_PROBE=1``, under which
  :func:`kleinlib.data.load_partition` refuses the sealed partition and
  :func:`kleinlib.data.contract_split` returns it empty.  The fence covers
  Klein's row-partition loaders, nothing else: a script that opens raw files,
  or a simulator that picks its own sealed seeds, is recorded, not stopped;
* **never evidence** — a probe id (``X0001``) is not an evidence id the claims
  law resolves, and nothing under ``probes/`` may be pinned as an artifact.  A
  probe earns a *prediction*: what it suggested is registered, then tested by a
  run that did not know the answer.

The variable is set ONLY in a probe's child: every other child the engine
launches has it removed (:func:`kleinlib.runner.run_logged`), and the command
line and the API clear it from their own process, so an exported
``KLEIN_PROBE=1`` can never empty the sealed partition a gate fingerprints.

``references/exploration-protocol.md``.
"""

from __future__ import annotations

import json
import os
import shutil
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .contract import load_contract
from .errors import WorkflowError
from .primitives import StudyLock, canonical_json, sha256_bytes, sha256_file, utc_now

__all__ = [
    "PROBE_ENV",
    "PROBE_ENV_KEYS",
    "PROBES_DIR",
    "PROBES_FILE",
    "clear_probe_environment",
    "is_probe_path",
    "probe_chain_problems",
    "probe_head",
    "probes_before_consult",
    "read_probes",
    "run_probe",
]

PROBES_FILE = "probes.jsonl"
PROBES_DIR = "probes"
#: Set to ``1`` in a probe's child process; the data loaders read it.
PROBE_ENV = "KLEIN_PROBE"
PROBE_ENV_KEYS: tuple[str, ...] = ("KLEIN_PROBE", "KLEIN_PROBE_ID", "KLEIN_PROBE_DIR")
EVENT_TYPE = "probe_recorded"


def clear_probe_environment(env: dict[str, str] | None = None) -> dict[str, str]:
    """Remove the probe variables from ``env`` (default: this process).  Returns what was removed."""
    target = os.environ if env is None else env
    return {key: target.pop(key) for key in PROBE_ENV_KEYS if key in target}


def is_probe_path(relative: str) -> bool:
    """True for ``probes.jsonl`` and anything under ``probes/`` (study-relative POSIX)."""
    return relative == PROBES_FILE or relative.split("/", 1)[0] == PROBES_DIR


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


def _probe_events(study_dir: Path) -> tuple[list[tuple[str, str]], int | None]:
    """``[(probe id, hash), …]`` as the study's event chain recorded them, and how
    many preceded the FIRST consult-gate record (None while there is none)."""
    from .events import read_events

    recorded: list[tuple[str, str]] = []
    before_consult: int | None = None
    for event in read_events(Path(study_dir)):
        kind = event.get("type")
        if kind == EVENT_TYPE:
            recorded.append((str(event.get("probe")), str(event.get("probe_hash"))))
        elif (
            before_consult is None
            and kind in {"gate_recorded", "gate_overridden"}
            and event.get("gate") == "consult"
        ):
            before_consult = len(recorded)
    return recorded, before_consult


def probes_before_consult(study_dir: Path) -> int | None:
    """How many probes the event chain places before the first consult gate (None: no gate yet)."""
    try:
        return _probe_events(study_dir)[1]
    except WorkflowError:
        return None


def probe_chain_problems(study_dir: Path, *, recorded: Mapping[str, Any] | None = None) -> list[str]:
    """Every way the probe ledger fails to be the append-only record it claims to be.

    Three independent witnesses: the ledger's own hash chain, the logs it names,
    and the ``probe_recorded`` events in the study's event chain — which is what
    catches a truncated, deleted or wholesale-rewritten ledger.  ``recorded`` is
    the ``{"count", "head"}`` the consult gate stored: the ledger must still
    begin with exactly those probes.
    """
    study = Path(study_dir)
    try:
        rows = read_probes(study)
        events, _before = _probe_events(study)
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

    ledger = [(str(row.get("id")), str(row.get("hash"))) for row in rows]
    if len(ledger) < len(events):
        missing = ", ".join(name for name, _hash in events[len(ledger) :])
        problems.append(
            f"{len(events) - len(ledger)} probe(s) the event chain recorded are missing from "
            f"{PROBES_FILE} ({missing}) — the ledger is append-only"
        )
    elif len(ledger) > len(events):
        extra = ", ".join(name for name, _hash in ledger[len(events) :])
        problems.append(f"{extra}: in {PROBES_FILE} but never recorded in events.jsonl")
    for (name, digest), (event_name, event_digest) in zip(ledger, events, strict=False):
        if (name, digest) != (event_name, event_digest):
            problems.append(f"{name}: differs from the probe events.jsonl recorded as {event_name}")
            break
    if recorded and recorded.get("count"):
        count = int(recorded["count"])
        if len(rows) < count or rows[count - 1].get("hash") != recorded.get("head"):
            problems.append(
                f"the first {count} probe(s) are not the ones the consult gate recorded — "
                "the ledger is append-only"
            )
    known = {f"{name}.log" for name, _hash in ledger} | {name for name, _hash in ledger}
    folder = study / PROBES_DIR
    if folder.is_dir():
        orphans = sorted(path.name for path in folder.iterdir() if path.name not in known)
        if orphans:
            problems.append(
                f"{PROBES_DIR}/ holds file(s) no ledger entry names: {', '.join(orphans[:5])}"
            )
    return problems


def _named_files(study: Path, command: Sequence[str]) -> tuple[dict[str, str], list[str]]:
    """sha256 of every study file the command names, and the files it names OUTSIDE the study.

    The first is the script that did the looking, pinned; the second is what the
    record could not pin — a referee is told so instead of left to assume.
    """
    hashes: dict[str, str] = {}
    outside: list[str] = []
    root = study.resolve()
    for argument in command[1:] if len(command) > 1 else command:
        candidate = (study / argument) if not os.path.isabs(argument) else Path(argument)
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if not resolved.is_file():
            continue
        if root in resolved.parents:
            hashes[resolved.relative_to(root).as_posix()] = sha256_file(resolved)
        else:
            outside.append(str(argument))
    return hashes, outside


def _commit(study: Path, paths: Sequence[str], message: str) -> None:
    """Commit exactly ``paths`` (study-relative) and nothing else; a no-op outside git."""
    from .transaction import git, git_commit, relative

    top = git(study, ["rev-parse", "--show-toplevel"], check=False)
    if top.returncode:
        return
    repo = Path(top.stdout.strip()).resolve()
    existing = [relative(repo, study / name) for name in paths if (study / name).exists()]
    if not existing:
        return
    git(repo, ["add", "-f", "--", *existing])
    if git(repo, ["diff", "--cached", "--quiet", "--", *existing], check=False).returncode == 0:
        return
    git_commit(repo, message, only=existing)


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
    from .events import append_event
    from .primitives import open_detached_run
    from .runner import run_logged
    from .transaction import git

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
    detached = open_detached_run(study)
    if detached is not None:
        raise WorkflowError(
            f"detached run {detached} is open: the study is frozen until "
            f"`klein run-one --collect {detached}` (or `--abandon`) closes it"
        )
    in_git = git(study, ["rev-parse", "--show-toplevel"], check=False).returncode == 0
    head = git(study, ["rev-parse", "--verify", "HEAD"], check=False) if in_git else None
    if commit and in_git and (head is None or head.returncode != 0):
        raise WorkflowError(
            "this repository has no commit yet: commit the scaffolded study first "
            "(`git add -A && git commit -m 'scaffold'`), so a probe is never the root of its history"
        )

    with StudyLock(study):
        existing = read_probes(study)
        problems = probe_chain_problems(study)
        if problems:
            raise WorkflowError("the probe ledger is damaged: " + "; ".join(problems))
        probe_id = f"X{len(existing) + 1:04d}"
        out_dir = study / PROBES_DIR / probe_id
        log_rel = f"{PROBES_DIR}/{probe_id}.log"
        named, outside = _named_files(study, command)
        # A look must not rewrite the study's records: they are restored
        # byte-for-byte afterwards, and the attempt is said on the record.
        guarded = {
            name: (study / name).read_bytes()
            for name in ("study_state.json", "events.jsonl")
            if (study / name).is_file()
        }
        out_dir.mkdir(parents=True, exist_ok=True)
        started = utc_now()
        try:
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
        except OSError as exc:
            # The command could not be started: nothing was looked at, so nothing
            # is recorded and nothing is left behind to dirty the tree.
            (study / log_rel).unlink(missing_ok=True)
            shutil.rmtree(out_dir, ignore_errors=True)
            folder = study / PROBES_DIR
            if folder.is_dir() and not any(folder.iterdir()):
                folder.rmdir()
            raise WorkflowError(f"klein probe could not start {command[0]!r}: {exc}") from exc
        touched = sorted(
            name
            for name, original in guarded.items()
            if not (study / name).is_file() or (study / name).read_bytes() != original
        )
        for name in touched:
            (study / name).write_bytes(guarded[name])
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
            "unpinned": outside,
            "log": {"path": log_rel, "sha256": sha256_file(study / log_rel)},
            "git_head": head.stdout.strip() if head is not None and head.returncode == 0 else None,
            "previous_hash": existing[-1].get("hash") if existing else None,
        }
        if touched:
            body["restored_state"] = touched
        record = {**body, "hash": _hash_of(body)}
        with (study / PROBES_FILE).open("a", encoding="utf-8") as handle:
            handle.write(canonical_json(record) + "\n")
        if not any(out_dir.iterdir()):
            out_dir.rmdir()
        append_event(study, EVENT_TYPE, probe=probe_id, probe_hash=record["hash"])
        if commit:
            _commit(
                study,
                [PROBES_FILE, log_rel, f"{PROBES_DIR}/{probe_id}", "events.jsonl"],
                f"klein: probe {probe_id}",
            )
    return record
