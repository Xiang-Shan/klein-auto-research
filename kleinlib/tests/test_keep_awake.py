"""The cursor nudge must always return to the exact starting position."""

from __future__ import annotations

import pytest

from kleinlib import keep_awake


class _FakeCoreGraphics:
    def __init__(self, *, fail_first_post=False):
        self.created = []
        self.posts = []
        self.fail_first_post = fail_first_post

    def CGEventCreateMouseEvent(self, source, event_type, point, button):
        event = (point.x, point.y)
        self.created.append(event)
        return event

    def CGEventPost(self, tap, event):
        self.posts.append(event)
        if self.fail_first_post and len(self.posts) == 1:
            raise RuntimeError("post failed")


class _FakeCoreFoundation:
    def __init__(self):
        self.released = []

    def CFRelease(self, event):
        self.released.append(event)


def _install_fakes(monkeypatch, *, fail_first_post=False):
    cg = _FakeCoreGraphics(fail_first_post=fail_first_post)
    cf = _FakeCoreFoundation()
    monkeypatch.setattr(keep_awake, "_load_coregraphics", lambda: None)
    monkeypatch.setattr(keep_awake, "get_mouse_pos", lambda: (10.0, 20.0))
    monkeypatch.setattr(keep_awake, "_cg", cg)
    monkeypatch.setattr(keep_awake, "_cf", cf)
    return cg, cf


def test_nudge_restores_original_cursor(monkeypatch):
    cg, cf = _install_fakes(monkeypatch)
    keep_awake.nudge_mouse()
    assert cg.posts == [(11.0, 20.0), (10.0, 20.0)]
    assert cf.released == cg.created


def test_nudge_attempts_restore_even_when_first_post_fails(monkeypatch):
    cg, cf = _install_fakes(monkeypatch, fail_first_post=True)
    with pytest.raises(RuntimeError, match="post failed"):
        keep_awake.nudge_mouse()
    assert cg.posts == [(11.0, 20.0), (10.0, 20.0)]
    assert cf.released == cg.created
