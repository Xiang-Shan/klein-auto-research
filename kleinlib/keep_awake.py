"""Move the mouse a pixel back and forth every few seconds to stop macOS from
sleeping during long-running experiment ladders (multi-hour studies like
Klein 01/02).

Honest description of what this does, since "keep awake" utilities are
sometimes dressed up as something fancier: this calls macOS CoreGraphics via
`ctypes` to synthesize a mouse-moved event a couple of pixels from wherever
the cursor already is, on a fixed interval. That's it — it is a caffeinate-
style presence signal, not a real interaction, and it will visibly twitch
your cursor. It is macOS-only (CoreGraphics/CoreFoundation) and does nothing
useful on Linux/Windows. Zero third-party dependencies.

Usage:  uv run python -m kleinlib.keep_awake
Stop:   Ctrl+C

Prefer the stdlib `caffeinate` command when you just need to prevent sleep
without a mouse-nudge side effect (`caffeinate -i uv run train.py`); this
module exists for environments where `caffeinate` is unavailable or
insufficient (e.g. display-sleep policies not covered by `-i`).
"""

from __future__ import annotations

import ctypes
import ctypes.util
import time

#: Seconds between nudges.
INTERVAL = 5

_cg = None
_cf = None


class CGPoint(ctypes.Structure):
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]


_KCG_EVENT_MOUSE_MOVED = 5
_KCG_HID_EVENT_TAP = 0
_KCG_MOUSE_BUTTON_LEFT = 0


def _load_coregraphics() -> None:
    """Lazily bind the CoreGraphics/CoreFoundation functions we need.

    Deferred so importing this module on non-macOS platforms doesn't crash
    at import time — only calling `nudge_mouse`/`main` does.
    """
    global _cg, _cf
    if _cg is not None:
        return

    cg_path = ctypes.util.find_library("CoreGraphics")
    cf_path = ctypes.util.find_library("CoreFoundation")
    if not cg_path or not cf_path:
        raise RuntimeError(
            "kleinlib.keep_awake requires macOS CoreGraphics/CoreFoundation "
            "(not found on this platform) — it is a macOS-only utility."
        )

    cg = ctypes.cdll.LoadLibrary(cg_path)
    cf = ctypes.cdll.LoadLibrary(cf_path)

    cg.CGEventCreate.restype = ctypes.c_void_p
    cg.CGEventCreate.argtypes = [ctypes.c_void_p]

    cg.CGEventGetLocation.restype = CGPoint
    cg.CGEventGetLocation.argtypes = [ctypes.c_void_p]

    cg.CGEventCreateMouseEvent.restype = ctypes.c_void_p
    cg.CGEventCreateMouseEvent.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        CGPoint,
        ctypes.c_uint32,
    ]

    cg.CGEventPost.argtypes = [ctypes.c_uint32, ctypes.c_void_p]

    cf.CFRelease.argtypes = [ctypes.c_void_p]

    _cg, _cf = cg, cf


def get_mouse_pos() -> tuple[float, float]:
    """Return the current on-screen cursor position `(x, y)`."""
    _load_coregraphics()
    event = _cg.CGEventCreate(None)
    pos = _cg.CGEventGetLocation(event)
    _cf.CFRelease(event)
    return pos.x, pos.y


def nudge_mouse() -> None:
    """Post a synthetic mouse-moved event a pixel left, then a pixel right."""
    _load_coregraphics()
    x, y = get_mouse_pos()
    for dx in (1, -1):
        pt = CGPoint(x + dx, y)
        evt = _cg.CGEventCreateMouseEvent(
            None, _KCG_EVENT_MOUSE_MOVED, pt, _KCG_MOUSE_BUTTON_LEFT
        )
        _cg.CGEventPost(_KCG_HID_EVENT_TAP, evt)
        _cf.CFRelease(evt)


def main() -> None:
    print(f"keep-awake: nudging mouse every {INTERVAL}s. Ctrl+C to stop.")
    try:
        while True:
            nudge_mouse()
            time.sleep(INTERVAL)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
