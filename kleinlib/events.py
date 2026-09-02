"""The append-only, self-verifying study journal (``events.jsonl``).

Extracted verbatim from :mod:`kleinlib.workflow`, with one mechanical change:
``append_event`` no longer re-reads and re-parses the whole journal to learn the
next sequence number and the previous hash.  :func:`_tail_event` seeks to the end
of the file, validates the last record against its own hash, and returns it; a
torn, blank, or self-inconsistent tail falls back to the full :func:`read_events`
parse.  The BYTES written are identical either way — the fast path only changes
how the two inputs (``sequence`` and ``previous_hash``) are obtained.

One narrow consequence of the fast path: a corrupt line in the MIDDLE of an
otherwise healthy journal no longer raises at append time (the tail alone cannot
see it).  It is still caught by :func:`verify_event_chain`, which ``klein
run-one`` runs before it appends anything, and by ``klein preflight``/``verify``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .errors import WorkflowError
from .primitives import canonical_json, sha256_bytes, utc_now

__all__ = [
    "append_event",
    "events_path",
    "read_events",
    "verify_event_chain",
]

def events_path(study_dir: Path) -> Path:
    return study_dir / "events.jsonl"


def read_events(study_dir: Path) -> list[dict[str, Any]]:
    path = events_path(study_dir)
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise WorkflowError(f"events.jsonl line {lineno} is invalid JSON: {exc}") from exc
        if not isinstance(value, dict):
            raise WorkflowError(f"events.jsonl line {lineno} is not an object")
        events.append(value)
    return events


def verify_event_chain(study_dir: Path) -> list[str]:
    problems: list[str] = []
    previous: str | None = None
    try:
        events = read_events(study_dir)
    except WorkflowError as exc:
        return [str(exc)]
    for index, event in enumerate(events, start=1):
        given = event.get("event_hash")
        body = dict(event)
        body.pop("event_hash", None)
        expected = sha256_bytes(canonical_json(body).encode())
        if event.get("sequence") != index:
            problems.append(f"event {index}: sequence is {event.get('sequence')!r}")
        if event.get("previous_hash") != previous:
            problems.append(f"event {index}: previous_hash does not match")
        if given != expected:
            problems.append(f"event {index}: event_hash does not match content")
        previous = given if isinstance(given, str) else None
    return problems


#: How far back from EOF :func:`_tail_event` reads.  Klein's events are small
#: (ids, hashes, short notes); a record larger than this simply takes the slow
#: path, which is always correct.
_TAIL_WINDOW = 65536


def _tail_event(path: Path) -> dict[str, Any] | None:
    """The journal's last event, read from the end — or None to fall back.

    Returns None (meaning "use the full parse") when the file is missing or
    empty, when the tail is torn (no terminating newline, a possibly truncated
    single line, a blank line in the window), or when the last record is not a
    JSON object whose recorded ``event_hash`` matches its own content.  A
    record that passes every check was written by :func:`append_event` itself,
    so its ``sequence`` is the journal's event count.
    """
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            if size == 0:
                return None
            window = min(size, _TAIL_WINDOW)
            handle.seek(size - window)
            chunk = handle.read(window)
    except OSError:
        return None
    if not chunk.endswith(b"\n"):
        return None  # a torn append: the last line was never terminated
    lines = chunk.split(b"\n")
    lines.pop()  # the empty string after the final newline
    if not lines or any(not line.strip() for line in lines):
        # read_events SKIPS blank lines, so a blank tail means the last line is
        # not the last event: take the slow path rather than guess.
        return None
    if len(lines) == 1 and window < size:
        return None  # the only line in the window may itself be truncated
    try:
        event = json.loads(lines[-1])
    except json.JSONDecodeError:
        return None
    if not isinstance(event, dict):
        return None
    sequence = event.get("sequence")
    given = event.get("event_hash")
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
        return None
    if not isinstance(given, str):
        return None
    body = dict(event)
    body.pop("event_hash", None)
    if sha256_bytes(canonical_json(body).encode()) != given:
        return None
    return event


def append_event(study_dir: Path, event_type: str, **payload: Any) -> dict[str, Any]:
    path = events_path(study_dir)
    last = _tail_event(path)
    if last is not None:
        count = int(last["sequence"])
        previous = last["event_hash"]
    else:
        events = read_events(study_dir)
        count = len(events)
        previous = events[-1].get("event_hash") if events else None
    event: dict[str, Any] = {
        "sequence": count + 1,
        "timestamp": utc_now(),
        "type": event_type,
        "previous_hash": previous,
        **payload,
    }
    event["event_hash"] = sha256_bytes(canonical_json(event).encode())
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(canonical_json(event) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return event
