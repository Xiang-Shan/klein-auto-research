"""``klein`` writes UTF-8 whatever the console's locale says (the Windows lane)."""

from __future__ import annotations

import io
import sys

from kleinlib import cli


def test_utf8_streams_reconfigures_a_cp1252_pipe(monkeypatch) -> None:
    raw = io.BytesIO()
    pipe = io.TextIOWrapper(raw, encoding="cp1252", errors="strict", write_through=True)
    monkeypatch.setattr(sys, "stdout", pipe)
    cli.utf8_streams()
    print("ci_low 336.4 > 70 \u2192 supported")
    sys.stdout.flush()
    assert raw.getvalue() == "ci_low 336.4 > 70 \u2192 supported\n".encode("utf-8")


def test_utf8_streams_leaves_a_utf8_stream_alone(monkeypatch) -> None:
    raw = io.BytesIO()
    pipe = io.TextIOWrapper(raw, encoding="utf-8", errors="strict", write_through=True)
    monkeypatch.setattr(sys, "stderr", pipe)
    cli.utf8_streams()
    assert sys.stderr is pipe
    assert pipe.encoding == "utf-8"
    assert pipe.errors == "strict"


def test_utf8_streams_tolerates_a_stream_without_reconfigure(monkeypatch) -> None:
    monkeypatch.setattr(sys, "stdout", io.StringIO())
    cli.utf8_streams()  # must not raise
