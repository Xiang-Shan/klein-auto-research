"""``append_event`` reads the journal's tail, not the whole journal.

The extraction of :mod:`kleinlib.events` replaced a full re-parse of
``events.jsonl`` on every append with :func:`kleinlib.events._tail_event`.  The
BYTES written must not move, so these tests keep a private copy of the previous
implementation and diff the two journals byte for byte, then pin the fallback,
the chain verifier, and tamper detection.
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from kleinlib import events as events_module
from kleinlib.errors import WorkflowError
from kleinlib.events import (
    _tail_event,
    append_event,
    events_path,
    read_events,
    verify_event_chain,
)
from kleinlib.primitives import canonical_json, sha256_bytes

# --------------------------------------------------------------------------
# The pre-refactor implementation, verbatim, as the byte-level oracle.
# --------------------------------------------------------------------------


def legacy_append_event(study_dir: Path, event_type: str, **payload: Any) -> dict[str, Any]:
    events = read_events(study_dir)
    previous = events[-1].get("event_hash") if events else None
    event: dict[str, Any] = {
        "sequence": len(events) + 1,
        "timestamp": events_module.utc_now(),
        "type": event_type,
        "previous_hash": previous,
        **payload,
    }
    event["event_hash"] = sha256_bytes(canonical_json(event).encode())
    path = events_path(study_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(canonical_json(event) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return event


@contextmanager
def frozen_clock():
    """A deterministic timestamp: byte equality is otherwise unprovable."""
    stamps = iter(f"2026-09-02T00:00:{index:02d}Z" for index in range(10_000))
    original = events_module.utc_now
    events_module.utc_now = lambda: next(stamps)
    try:
        yield
    finally:
        events_module.utc_now = original


def build_chain(study_dir: Path, appender, count: int) -> list[dict[str, Any]]:
    study_dir.mkdir(parents=True, exist_ok=True)
    return [
        appender(
            study_dir,
            "run_started" if index % 2 else "gate_recorded",
            experiment=f"E{index:04d}",
            note=f"event {index} — unicode ok: naïve",
            nested={"b": index, "a": [1, 2, {"z": None}]},
        )
        for index in range(1, count + 1)
    ]


# --------------------------------------------------------------------------
# 1. byte identity against the old algorithm
# --------------------------------------------------------------------------


@pytest.mark.parametrize("count", [1, 2, 50])
def test_tail_append_writes_the_same_bytes_as_the_full_parse(tmp_path, count: int) -> None:
    for name, appender in (("new", append_event), ("old", legacy_append_event)):
        with frozen_clock():
            build_chain(tmp_path / name, appender, count)

    new_bytes = (tmp_path / "new" / "events.jsonl").read_bytes()
    old_bytes = (tmp_path / "old" / "events.jsonl").read_bytes()
    assert new_bytes == old_bytes
    assert new_bytes.count(b"\n") == count
    assert verify_event_chain(tmp_path / "new") == []


def test_returned_events_match_the_old_algorithm(tmp_path) -> None:
    with frozen_clock():
        new = build_chain(tmp_path / "new", append_event, 5)
    with frozen_clock():
        old = build_chain(tmp_path / "old", legacy_append_event, 5)
    assert new == old
    assert [event["sequence"] for event in new] == [1, 2, 3, 4, 5]


# --------------------------------------------------------------------------
# 2. the fast path really is the tail, and it really validates
# --------------------------------------------------------------------------


def test_tail_event_returns_the_last_record_of_a_healthy_journal(tmp_path) -> None:
    written = build_chain(tmp_path, append_event, 3)
    assert _tail_event(events_path(tmp_path)) == written[-1]


def test_tail_event_declines_an_absent_or_empty_journal(tmp_path) -> None:
    assert _tail_event(tmp_path / "events.jsonl") is None
    (tmp_path / "events.jsonl").write_bytes(b"")
    assert _tail_event(tmp_path / "events.jsonl") is None


def test_append_reads_only_the_tail(tmp_path, monkeypatch) -> None:
    build_chain(tmp_path, append_event, 4)

    def explode(_study_dir):
        raise AssertionError("append_event must not re-parse the whole journal")

    monkeypatch.setattr(events_module, "read_events", explode)
    event = append_event(tmp_path, "study_finalized", label="exploratory")
    assert event["sequence"] == 5


# --------------------------------------------------------------------------
# 3. torn / invalid tails fall back to the full parse
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "corrupt",
    [
        pytest.param(lambda raw: raw[:-1], id="no-trailing-newline"),
        pytest.param(lambda raw: raw + b"\n", id="blank-last-line"),
        pytest.param(lambda raw: raw + b'{"sequence": 4, "tr\n', id="partial-json"),
        pytest.param(lambda raw: raw + b'["not", "an", "object"]\n', id="not-an-object"),
        pytest.param(lambda raw: raw + b'{"sequence": 4}\n', id="no-event-hash"),
    ],
)
def test_torn_tail_falls_back_to_the_full_parse(tmp_path, corrupt) -> None:
    build_chain(tmp_path, append_event, 3)
    path = events_path(tmp_path)
    path.write_bytes(corrupt(path.read_bytes()))
    assert _tail_event(path) is None


def test_tampered_tail_is_not_trusted_for_the_next_sequence(tmp_path) -> None:
    build_chain(tmp_path, append_event, 3)
    path = events_path(tmp_path)
    lines = path.read_text(encoding="utf-8").splitlines()
    tampered = json.loads(lines[-1])
    tampered["note"] = "edited after the fact"
    lines[-1] = canonical_json(tampered)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # the recorded event_hash no longer matches the content -> slow path
    assert _tail_event(path) is None
    # ... and the slow path counts lines, so the chain keeps its numbering
    assert append_event(tmp_path, "run_finished", experiment="E0004")["sequence"] == 4
    assert any("event 3: event_hash does not match" in p for p in verify_event_chain(tmp_path))


def test_fallback_still_raises_on_an_invalid_final_line(tmp_path) -> None:
    build_chain(tmp_path, append_event, 2)
    path = events_path(tmp_path)
    path.write_bytes(path.read_bytes() + b"not json at all\n")
    with pytest.raises(WorkflowError, match="line 3 is invalid JSON"):
        append_event(tmp_path, "run_started", experiment="E0003")


def test_a_giant_record_beyond_the_window_takes_the_slow_path(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(events_module, "_TAIL_WINDOW", 64)
    build_chain(tmp_path, append_event, 2)
    assert _tail_event(events_path(tmp_path)) is None
    assert verify_event_chain(tmp_path) == []
    assert append_event(tmp_path, "run_finished", experiment="E0002")["sequence"] == 3
    assert verify_event_chain(tmp_path) == []


# --------------------------------------------------------------------------
# 4. tamper detection is unchanged
# --------------------------------------------------------------------------


def test_verify_event_chain_still_detects_every_tamper_shape(tmp_path) -> None:
    build_chain(tmp_path, append_event, 4)
    path = events_path(tmp_path)
    healthy = path.read_text(encoding="utf-8").splitlines()
    assert verify_event_chain(tmp_path) == []

    edited = [*healthy]
    payload = json.loads(edited[1])
    payload["note"] = "silently rewritten"
    edited[1] = canonical_json(payload)
    path.write_text("\n".join(edited) + "\n", encoding="utf-8")
    assert "event 2: event_hash does not match content" in verify_event_chain(tmp_path)

    path.write_text("\n".join(healthy[:1] + healthy[2:]) + "\n", encoding="utf-8")
    problems = verify_event_chain(tmp_path)
    assert any("sequence is" in problem for problem in problems)
    assert any("previous_hash does not match" in problem for problem in problems)

    path.write_text("\n".join(healthy) + "\n", encoding="utf-8")
    assert verify_event_chain(tmp_path) == []
