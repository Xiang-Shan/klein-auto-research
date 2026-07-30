"""Shared palette + font setup for the canonical Klein diagrams.

Values copied verbatim from the dataviz skill's reference palette
(references/palette.md) — categorical hues, status colors, chart chrome/ink,
surfaces. Do not hand-pick new colors; if a new role is needed, pull it from
that file.
"""
from __future__ import annotations

import matplotlib.font_manager as fm
import matplotlib.pyplot as plt

# ---- Light-mode chart chrome & ink (we ship light-surface PNGs) ----
SURFACE = "#fcfcfb"
PAGE = "#f9f9f7"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
TEXT_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
BASELINE = "#c3c2b7"
BORDER = "#0b0b0b1a"  # 10% alpha ring

# ---- Categorical (fixed order, never cycled) ----
BLUE = "#2a78d6"
AQUA = "#1baf7a"
YELLOW = "#eda100"
GREEN_CAT = "#008300"
VIOLET = "#4a3aa7"
RED_CAT = "#e34948"
MAGENTA = "#e87ba4"
ORANGE = "#eb6834"

# ---- Status (fixed, reserved meaning, always icon+label) ----
GOOD = "#0ca30c"
WARNING = "#fab219"
SERIOUS = "#ec835a"
CRITICAL = "#d03b3b"

# Study-loop status mapping (semantic, not arbitrary):
#   keep    -> good      (the idea earned its place)
#   discard -> serious    (an honest negative result, not a bug)
#   crash   -> critical   (a process failure, logged loudly)
STATUS_COLOR = {"keep": GOOD, "discard": SERIOUS, "crash": CRITICAL}

# ---- Sequential (blue ramp, light -> dark), used sparingly for tints ----
SEQ_100 = "#cde2fb"
SEQ_150 = "#b7d3f6"
SEQ_200 = "#9ec5f4"


def setup_fonts(lang: str) -> None:
    """Configure matplotlib's font stack. lang: 'en' or 'zh'."""
    if lang == "zh":
        candidates = ["PingFang SC", "Hiragino Sans GB", "Arial Unicode MS", "DejaVu Sans"]
    else:
        candidates = ["Helvetica Neue", "Arial", "DejaVu Sans"]
    available = {f.name for f in fm.fontManager.ttflist}
    family = [c for c in candidates if c in available] or ["DejaVu Sans"]
    plt.rcParams["font.family"] = family
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["svg.fonttype"] = "none"


def new_fig(w_in: float, h_in: float, dpi: int = 200):
    fig = plt.figure(figsize=(w_in, h_in), dpi=dpi)
    fig.patch.set_facecolor(SURFACE)
    return fig
