"""``klein`` never crashes on a console encoding that cannot carry its arrows (the Windows lane)."""

from __future__ import annotations

import io
import sys

from kleinlib import cli


def _pipe(raw: io.BytesIO, encoding: str) -> io.TextIOWrapper:
    # newline="\n": the assertions are about the encoding, not the platform's line ending
    return io.TextIOWrapper(raw, encoding=encoding, errors="strict", newline="\n", write_through=True)


def test_a_cp1252_pipe_escapes_the_arrow_instead_of_raising(monkeypatch) -> None:
    raw = io.BytesIO()
    monkeypatch.setattr(sys, "stdout", _pipe(raw, "cp1252"))
    cli.utf8_streams()
    print("ci_low 336.4 > 70 \u2192 supported")
    sys.stdout.flush()
    assert raw.getvalue() == b"ci_low 336.4 > 70 \\u2192 supported\n"
    assert sys.stdout.encoding == "cp1252"  # readers on that platform decode what they always did


def test_a_cp1252_pipe_still_carries_the_dash_natively(monkeypatch) -> None:
    raw = io.BytesIO()
    monkeypatch.setattr(sys, "stderr", _pipe(raw, "cp1252"))
    cli.utf8_streams()
    print("fit noise \u2014 NOT a keep bar", file=sys.stderr)
    sys.stderr.flush()
    assert raw.getvalue() == "fit noise \u2014 NOT a keep bar\n".encode("cp1252")


def test_a_utf8_stream_is_left_alone(monkeypatch) -> None:
    raw = io.BytesIO()
    pipe = _pipe(raw, "utf-8")
    monkeypatch.setattr(sys, "stdout", pipe)
    cli.utf8_streams()
    assert sys.stdout is pipe
    assert pipe.errors == "strict"


def test_a_stream_without_reconfigure_is_tolerated(monkeypatch) -> None:
    monkeypatch.setattr(sys, "stdout", io.StringIO())
    cli.utf8_streams()  # must not raise
