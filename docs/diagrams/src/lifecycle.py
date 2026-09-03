"""Canonical diagram: the seven-stage study lifecycle, as a vertical checkpoint flow.

Regenerate whenever the lifecycle or a stage description changes.

The canonical lifecycle string (byte-identical in AGENTS.md, SKILL.md, README.md and here;
scripts/tests/test_docs_integrity.py enforces it):

new ─▶ CONSULT ─▶ DATA ─▶ METHOD ═══▶ EXPERIMENT/SWEEP ─▶ SYNTHESIZE ─▶ REFEREE ─▶ TUTORIAL
        Gate 0   Gate 1   Gate 2      └ the honest loop ┘    findings.md    Gate 3     report/

Gate stages get a hazard-stripe top band + numbered badge to read as a
checkpoint you must clear. The last three stages are bracketed with a
callout: "these three make it research, not just experiment-running."

Usage: uv run --no-sync python docs/diagrams/src/lifecycle.py en <out.png>
"""
from __future__ import annotations

import sys

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Polygon

sys.path.insert(0, ".")
from klein_palette import (
    AQUA,
    BLUE,
    GOOD,
    GRIDLINE,
    SURFACE,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    new_fig,
    setup_fonts,
)

CARDS_EN = [
    dict(kind="gate", num="0", title="CONSULT", sub="Gate 0",
         body="At most 6 questions turn a vague goal into a\nfalsifiable research question, before anything runs."),
    dict(kind="gate", num="1", title="DATA", sub="Gate 1",
         body="GIGO guard: profiles the dataset, writes ranked\ngo / no-go issues. Never trust dtype alone."),
    dict(kind="gate", num="2", title="METHOD", sub="Gate 2",
         body="Forces understanding before compute: intuition ->\nmath core -> minimal from-scratch implementation."),
    dict(kind="loop", num=None, title="EXPERIMENT / SWEEP", sub=None,
         body="Edit the entrypoint with one falsifiable idea -> klein run-one:\ncommit candidate, bounded run, honest keep / discard / measured / crash."),
    dict(kind="funnel", num=None, title="SYNTHESIZE", sub=None,
         body="Mines the full trajectory - manifests, predictions ledger,\nprogram.md - into findings.md + claims.lock, evidence-cited."),
    dict(kind="gate", num="3", title="REFEREE", sub="Gate 3",
         body="A fresh context on a different model: mechanical verifiers,\na fixed ten-check rubric, a verdict finalize cannot skip."),
    dict(kind="book", num=None, title="TUTORIAL", sub=None,
         body="Closes the loop with a teaching artifact:\nreport/index.html, opens from file://."),
]

TITLE_EN = "The Klein study lifecycle — seven stages, four checkpoints"
CAPTION_EN = "These last three stages are what make it research — not just experiment-running."
FOOT_EN = "CONSULT -> DATA -> METHOD are pre-flight checkpoints; REFEREE is the post-flight one. Modeling is blocked until DATA says go and METHOD exists; finalize waits for the referee."

def draw_gate_badge(ax, cx, cy, r, num):
    ax.add_patch(Circle((cx, cy), r, facecolor=BLUE, edgecolor=SURFACE, linewidth=2.5, zorder=5))
    ax.text(cx, cy + 0.15, num, ha="center", va="center", fontsize=22, fontweight="bold",
             color="white", zorder=6)
    ax.text(cx, cy - r - 1.3, "GATE", ha="center", va="top", fontsize=9.5, fontweight="bold",
             color=BLUE, zorder=6, family="DejaVu Sans")


def draw_loop_icon(ax, cx, cy, r):
    ax.add_patch(Circle((cx, cy), r, facecolor=AQUA, edgecolor=SURFACE, linewidth=2.5, zorder=5))
    arc = plt.matplotlib.patches.Arc((cx, cy), r * 1.15, r * 1.15, angle=0,
                                      theta1=25, theta2=320, color="white", linewidth=2.6, zorder=6)
    ax.add_patch(arc)
    import math
    ang = math.radians(320)
    tip = (cx + r * 0.575 * math.cos(ang), cy + r * 0.575 * math.sin(ang))
    ax.add_patch(Polygon([
        (tip[0] - 0.9, tip[1] + 0.55), (tip[0] + 0.75, tip[1] + 0.15), (tip[0] - 0.15, tip[1] - 0.85),
    ], closed=True, facecolor="white", edgecolor="white", zorder=6))


def draw_funnel_icon(ax, cx, cy, r):
    ax.add_patch(Circle((cx, cy), r, facecolor=GOOD, edgecolor=SURFACE, linewidth=2.5, zorder=5))
    pts = [(cx - r * 0.62, cy + r * 0.55), (cx + r * 0.62, cy + r * 0.55),
           (cx + r * 0.14, cy - r * 0.15), (cx + r * 0.14, cy - r * 0.6),
           (cx - r * 0.14, cy - r * 0.6), (cx - r * 0.14, cy - r * 0.15)]
    ax.add_patch(Polygon(pts, closed=True, facecolor="white", edgecolor="none", zorder=6))


def draw_book_icon(ax, cx, cy, r):
    """A simple report/document glyph: a page with text lines + folded corner."""
    ax.add_patch(Circle((cx, cy), r, facecolor=GOOD, edgecolor=SURFACE, linewidth=2.5, zorder=5))
    pw, ph = r * 1.15, r * 1.35
    x0, y0 = cx - pw / 2, cy - ph / 2
    fold = pw * 0.34
    page = Polygon([
        (x0, y0), (x0 + pw, y0), (x0 + pw, y0 + ph - fold), (x0 + pw - fold, y0 + ph),
        (x0, y0 + ph),
    ], closed=True, facecolor="white", edgecolor="none", zorder=6)
    ax.add_patch(page)
    ax.add_patch(Polygon([
        (x0 + pw - fold, y0 + ph), (x0 + pw, y0 + ph - fold), (x0 + pw - fold, y0 + ph - fold),
    ], closed=True, facecolor=GOOD, edgecolor="white", linewidth=0.8, zorder=7))
    for k, frac in enumerate((0.32, 0.5, 0.68)):
        ly = y0 + ph * frac
        lw = pw * (0.62 if k else 0.7)
        ax.plot([x0 + pw * 0.16, x0 + pw * 0.16 + lw], [ly, ly], color=GOOD, linewidth=1.6,
                 solid_capstyle="round", zorder=7)


def hazard_stripe(ax, x0, y0, w, h, color):
    """Diagonal checkpoint stripe band clipped to a rounded card top edge."""
    band = FancyBboxPatch((x0, y0), w, h, boxstyle="round,pad=0,rounding_size=1.6",
                            facecolor=color, edgecolor="none", zorder=4.2)
    ax.add_patch(band)
    clip_patch = FancyBboxPatch((x0, y0), w, h, boxstyle="round,pad=0,rounding_size=1.6",
                                  transform=ax.transData)
    step = 3.2
    n = int(w / step) + 6
    for i in range(-3, n):
        xi = x0 + i * step
        stripe = Polygon([
            (xi, y0), (xi + step * 0.55, y0), (xi + step * 0.55 - h * 0.9, y0 + h), (xi - h * 0.9, y0 + h),
        ], closed=True, facecolor=SURFACE, edgecolor="none", alpha=0.9, zorder=4.3)
        stripe.set_clip_path(clip_patch)
        ax.add_patch(stripe)


def build(lang: str, out_path: str):
    setup_fonts(lang)
    cards = CARDS_EN
    title = TITLE_EN
    caption = CAPTION_EN
    foot = FOOT_EN

    W = 100.0
    margin_x = 9.0
    card_w = W - 2 * margin_x
    card_h = 16.0
    gap = 6.5
    top_margin = 12.0
    bottom_margin = 13.0

    n = len(cards)
    H = top_margin + n * card_h + (n - 1) * gap + bottom_margin

    fig = new_fig(9.2, 9.2 * H / W, dpi=200)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.axis("off")
    ax.set_facecolor(SURFACE)

    # Title
    ax.text(W / 2, H - top_margin / 2 + 1.5, title, ha="center", va="center",
             fontsize=21, fontweight="bold", color=TEXT_PRIMARY)

    cursor_top = H - top_margin

    centers = []
    for _card in cards:
        y0 = cursor_top - card_h
        x0 = margin_x
        centers.append((x0, y0, card_w, card_h))
        cursor_top = y0 - gap

    # Highlight bracket behind cards 5, 6 & 7 (index 4 .. 6)
    bx0, by0, bw, bh4 = centers[4]
    _, by1, _, bh5 = centers[6]
    bracket_pad = 3.2
    bracket_x0 = bx0 - bracket_pad
    bracket_y0 = by1 - bracket_pad
    bracket_w = bw + 2 * bracket_pad
    bracket_h = (by0 + bh4) - by1 + 2 * bracket_pad
    ax.add_patch(FancyBboxPatch((bracket_x0, bracket_y0), bracket_w, bracket_h,
                                  boxstyle="round,pad=0,rounding_size=3.2",
                                  facecolor=GOOD, alpha=0.07, edgecolor=GOOD, linewidth=1.6,
                                  linestyle=(0, (5, 3)), zorder=1))

    # Draw cards
    for card, (x0, y0, w, h) in zip(cards, centers, strict=True):
        is_gate = card["kind"] == "gate"
        card_bg = "white"
        ax.add_patch(FancyBboxPatch((x0, y0), w, h, boxstyle="round,pad=0,rounding_size=2.2",
                                      facecolor=card_bg, edgecolor=GRIDLINE, linewidth=1.3, zorder=4))

        badge_r = 4.6
        badge_cx = x0 + 8.5
        badge_cy = y0 + h / 2 + (1.6 if is_gate else 0)

        if is_gate:
            hazard_stripe(ax, x0, y0 + h - 3.0, w, 3.0, BLUE)
            draw_gate_badge(ax, badge_cx, y0 + h / 2 - 0.2, badge_r, card["num"])
        elif card["kind"] == "loop":
            draw_loop_icon(ax, badge_cx, badge_cy, badge_r)
        elif card["kind"] == "funnel":
            draw_funnel_icon(ax, badge_cx, badge_cy, badge_r)
        elif card["kind"] == "book":
            draw_book_icon(ax, badge_cx, badge_cy, badge_r)

        text_x = x0 + 16.5
        title_y = y0 + h - 4.6 if is_gate else y0 + h - 4.3
        ax.text(text_x, title_y, card["title"], ha="left", va="center",
                 fontsize=16.5, fontweight="bold", color=TEXT_PRIMARY, zorder=6)
        body_y = title_y - 4.4
        ax.text(text_x, body_y, card["body"], ha="left", va="top",
                 fontsize=10.8, color=TEXT_SECONDARY, linespacing=1.55, zorder=6)

    # Arrows between cards
    for i in range(n - 1):
        x0, y0, w, h = centers[i]
        x1, y1, w1, h1 = centers[i + 1]
        ax.add_patch(FancyArrowPatch((x0 + w / 2, y0 - 0.3), (x1 + w1 / 2, y1 + h1 + 0.3),
                                       arrowstyle="-|>", mutation_scale=16,
                                       color=TEXT_MUTED, linewidth=1.8, zorder=3))

    # Callout under the bracket
    star_y = bracket_y0 - 3.2
    ax.add_patch(Circle((margin_x + 2.0, star_y), 1.0, facecolor=GOOD, edgecolor="none", zorder=6))
    ax.text(margin_x + 4.4, star_y, caption, ha="left", va="center",
             fontsize=12.2, fontweight="bold", color=TEXT_PRIMARY, zorder=6)

    # Footnote at very bottom
    ax.text(W / 2, 3.2, foot, ha="center", va="center", fontsize=9.6, color=TEXT_MUTED,
             wrap=True)

    fig.savefig(out_path, dpi=200, facecolor=SURFACE, bbox_inches=None)
    plt.close(fig)
    print(f"wrote {out_path}  size(in)={fig.get_size_inches()}  dpi=200")


if __name__ == "__main__":
    lang = sys.argv[1] if len(sys.argv) > 1 else "en"
    out = sys.argv[2] if len(sys.argv) > 2 else f"lifecycle-{lang}.png"
    build(lang, out)
