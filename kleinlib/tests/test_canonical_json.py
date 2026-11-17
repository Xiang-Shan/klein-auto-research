"""One canonical JSON form for everything Klein hashes."""

from __future__ import annotations

from kleinlib import calls, primitives


def test_the_call_ledger_and_the_event_chain_share_one_canonical_form() -> None:
    assert calls.canonical_json is primitives.canonical_json


def test_canonical_bytes_are_pinned() -> None:
    # Stored hashes depend on these exact bytes: sorted keys, no spaces, UTF-8 kept.
    value = {"b": 1, "a": "é", "n": [1.5, None, True]}
    assert primitives.canonical_json(value) == '{"a":"é","b":1,"n":[1.5,null,true]}'
