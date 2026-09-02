"""Canonical diagram: one candidate transaction under the v2 loop contract.

REGENERATE WHENEVER THE LOOP CONTRACT CHANGES — labels below are derived from
AGENTS.md "The experiment loop contract" and SKILL.md Hard Rules; if those
files change semantics, this drawing is wrong until rerun.

Five steps, three layers: the loop is yours (judgment) -> klein run-one is the
crash boundary (notary) -> the state files are receipts. Status colors are
reserved for the keep/discard/crash chips.

Usage: uv run --no-sync python docs/diagrams/src/loop_transaction.py en <out.png>
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Polygon

sys.path.insert(0, str(Path(__file__).resolve().parent))
from klein_palette import (
    AQUA,
    BLUE,
    CRITICAL,
    GOOD,
    GRIDLINE,
    PAGE,
    SERIOUS,
    SURFACE,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    VIOLET,
    new_fig,
    setup_fonts,
)

# ---- vertical block sizes (data units), shared by every card ----
TOP_PAD = 3.4
TITLE_H = 5.0
BODY_LINE_H = 2.5
CALLOUT_GAP = 2.4
CALLOUT_H = 7.4
CHIP_GAP = 2.2
CHIP_ROW_H = 2.7
BOTTOM_PAD = 2.4

# Layer tags: whose hands is this step in?
LAYER_YOURS = ("your judgment", AQUA)
LAYER_NOTARY = ("run-one, the notary", BLUE)
LAYER_RECEIPTS = ("receipts", VIOLET)

STEPS = [
    dict(n="1", title="EDIT the mutable surface — one falsifiable idea", kind="body",
         layer=LAYER_YOURS,
         body=["Only the files entrypoint.mutable names (train.py by default).",
               "One idea per candidate; the verifier is never among them."]),
    dict(n="2", title="COMMIT the candidate — BEFORE it runs", kind="callout",
         layer=LAYER_NOTARY,
         body=["Even a future discard or crash stays resolvable."],
         callout="Negative evidence is evidence —\nthe exact losing code is never destroyed."),
    dict(n="3", title="ONE bounded foreground run", kind="body",
         layer=LAYER_NOTARY,
         body=["Unbuffered, max_run_seconds, process-group timeout.",
               "The real exit code is kept — 124 means timeout."]),
    dict(n="4", title="HONEST disposition — arithmetic, not vibes", kind="chips",
         layer=LAYER_NOTARY,
         body=["Judged only by the contract YOU declared:",
               "metric, direction, minimum_delta, guardrails."],
         chips=[("keep", "a frontier improvement ≥ minimum_delta"),
                ("discard", "an honest no — surface restored, commit kept"),
                ("measured", "a registered cell — its pinned table is the evidence"),
                ("crash", "NA metric, logged loud — never silently retried")]),
    dict(n="5", title="RECEIPTS filed", kind="callout",
         layer=LAYER_RECEIPTS,
         body=["manifest.json + events.jsonl are the evidence."],
         callout="results.tsv is a DERIVED view — never hand-edited.\nInterrupted? klein recover finishes the filing."),
]
LOOP_LABEL = "repeat — the loop is yours"
TITLE = "One candidate transaction"
SUB = "You think; run-one notarizes; the files remember. No exceptions."


def card_height(step):
    h = TOP_PAD + TITLE_H + len(step["body"]) * BODY_LINE_H + BOTTOM_PAD
    if step["kind"] == "callout":
        h += CALLOUT_GAP + CALLOUT_H
    elif step["kind"] == "chips":
        h += CHIP_GAP + len(step["chips"]) * CHIP_ROW_H
    return h


def build(out_path: str):
    setup_fonts("en")
    steps = STEPS

    W = 100.0
    margin_x = 9.0
    right_lane = 13.0
    card_w = W - 2 * margin_x - right_lane
    gap = 6.5
    top_margin = 15.5
    bottom_margin = 4.0

    heights = [card_height(s) for s in steps]
    n = len(steps)
    H = top_margin + sum(heights) + (n - 1) * gap + bottom_margin

    fig = new_fig(9.6, 9.6 * H / W, dpi=200)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.axis("off")
    ax.set_facecolor(SURFACE)

    ax.text(W / 2, H - 5.2, TITLE, ha="center", va="center",
            fontsize=21, fontweight="bold", color=TEXT_PRIMARY)
    ax.text(W / 2, H - 9.6, SUB, ha="center", va="center",
            fontsize=11.5, color=TEXT_SECONDARY)

    cursor_top = H - top_margin
    centers = []
    for h in heights:
        y0 = cursor_top - h
        centers.append((margin_x, y0, card_w, h))
        cursor_top = y0 - gap

    chip_colors = {"keep": GOOD, "discard": SERIOUS, "measured": BLUE, "crash": CRITICAL}

    for step, (x0, y0, w, h) in zip(steps, centers, strict=True):
        ax.add_patch(FancyBboxPatch((x0, y0), w, h, boxstyle="round,pad=0,rounding_size=2.2",
                                    facecolor="white", edgecolor=GRIDLINE, linewidth=1.3, zorder=4))
        top = y0 + h
        badge_r = 4.6
        layer_label, layer_color = step["layer"]
        bcx, bcy = x0 + 8.3, top - TOP_PAD - TITLE_H / 2 + 0.6
        ax.add_patch(Circle((bcx, bcy), badge_r, facecolor=layer_color,
                            edgecolor=SURFACE, linewidth=2.5, zorder=5))
        ax.text(bcx, bcy + 0.1, step["n"], ha="center", va="center", fontsize=19,
                fontweight="bold", color="white", zorder=6)

        # layer tag, top-right of the card
        ax.text(x0 + w - 2.4, top - 2.6, layer_label, ha="right", va="center",
                fontsize=8.6, fontweight="bold", color=layer_color, zorder=6)

        text_x = x0 + 16.0
        cursor = top - TOP_PAD
        ax.text(text_x, cursor, step["title"], ha="left", va="top",
                fontsize=15.0, fontweight="bold", color=TEXT_PRIMARY, zorder=6)
        cursor -= TITLE_H

        for line in step["body"]:
            ax.text(text_x, cursor, line, ha="left", va="top",
                    fontsize=10.8, color=TEXT_SECONDARY, zorder=6)
            cursor -= BODY_LINE_H

        if step["kind"] == "callout":
            cursor -= CALLOUT_GAP - BODY_LINE_H + 0.4
            cw = w - (text_x - x0) - 4.0
            ax.add_patch(FancyBboxPatch((text_x, cursor - CALLOUT_H), cw, CALLOUT_H,
                                        boxstyle="round,pad=0,rounding_size=1.4",
                                        facecolor=PAGE, edgecolor=BLUE, linewidth=1.2,
                                        linestyle=(0, (4, 2)), zorder=6))
            gx, gy = text_x + 2.0, cursor - CALLOUT_H / 2
            ax.plot([gx, gx], [gy - 1.7, gy + 1.7], color=BLUE, linewidth=1.4, zorder=7)
            ax.add_patch(Circle((gx, gy + 1.7), 0.5, facecolor=BLUE, edgecolor="none", zorder=7))
            ax.add_patch(Circle((gx, gy - 1.7), 0.5, facecolor=BLUE, edgecolor="none", zorder=7))
            ax.text(gx + 2.6, gy, step["callout"], ha="left", va="center",
                    fontsize=10.4, fontweight="bold", color=BLUE, linespacing=1.5, zorder=7)

        elif step["kind"] == "chips":
            cursor -= CHIP_GAP - BODY_LINE_H + 0.4
            desc_x = text_x + 15.5
            for label, desc in step["chips"]:
                ry = cursor - CHIP_ROW_H / 2 + 0.6
                ax.add_patch(Circle((text_x + 0.9, ry), 0.85, facecolor=chip_colors[label],
                                    edgecolor="none", zorder=7))
                ax.text(text_x + 2.3, ry, label, ha="left", va="center",
                        fontsize=11.2, fontweight="bold", color=TEXT_PRIMARY, zorder=7)
                ax.text(desc_x, ry, desc, ha="left", va="center",
                        fontsize=9.4, color=TEXT_MUTED, zorder=7)
                cursor -= CHIP_ROW_H

    for i in range(n - 1):
        x0, y0, w, h = centers[i]
        x1, y1, w1, h1 = centers[i + 1]
        ax.add_patch(FancyArrowPatch((x0 + w / 2, y0 - 0.3), (x1 + w1 / 2, y1 + h1 + 0.3),
                                     arrowstyle="-|>", mutation_scale=16,
                                     color=TEXT_MUTED, linewidth=1.8, zorder=3))

    # Loop-back bus line: right edge of the last card -> lane -> card 1
    x0, y0, w, h = centers[-1]
    xf0, yf0, wf, hf = centers[0]
    p0 = (x0 + w, y0 + h * 0.5)
    p3 = (xf0 + wf, yf0 + hf * 0.5)
    lane_x = W - right_lane / 2 + 1.2
    r = 1.6
    lw = 2.0
    ax.plot([p0[0], lane_x - r], [p0[1], p0[1]], color=TEXT_SECONDARY, linewidth=lw,
            zorder=8, solid_capstyle="round")
    ax.plot([lane_x, lane_x], [p0[1] + r, p3[1] - r], color=TEXT_SECONDARY, linewidth=lw,
            zorder=8, solid_capstyle="round")
    ax.plot([lane_x - r, p3[0] + 3.2], [p3[1], p3[1]], color=TEXT_SECONDARY, linewidth=lw,
            zorder=8, solid_capstyle="round")
    corner1 = plt.matplotlib.patches.Arc((lane_x - r, p0[1] + r), 2 * r, 2 * r, angle=0,
                                         theta1=270, theta2=360, color=TEXT_SECONDARY,
                                         linewidth=lw, zorder=8)
    corner2 = plt.matplotlib.patches.Arc((lane_x - r, p3[1] - r), 2 * r, 2 * r, angle=0,
                                         theta1=0, theta2=90, color=TEXT_SECONDARY,
                                         linewidth=lw, zorder=8)
    ax.add_patch(corner1)
    ax.add_patch(corner2)
    ax.add_patch(Polygon([
        (p3[0] + 3.6, p3[1] + 1.1), (p3[0] + 3.6, p3[1] - 1.1), (p3[0] + 0.9, p3[1]),
    ], closed=True, facecolor=TEXT_SECONDARY, edgecolor="none", zorder=8))
    mid_y = (p0[1] + p3[1]) / 2
    ax.text(lane_x + 3.4, mid_y, LOOP_LABEL, ha="center", va="center", fontsize=10.5,
            fontweight="bold", color=TEXT_SECONDARY, rotation=90, zorder=8)

    fig.savefig(out_path, dpi=200, facecolor=SURFACE, bbox_inches=None)
    plt.close(fig)
    print(f"wrote {out_path}  size(in)={fig.get_size_inches()}  dpi=200")


if __name__ == "__main__":
    _lang = sys.argv[1] if len(sys.argv) > 1 else "en"  # accepted for interface parity
    out = sys.argv[2] if len(sys.argv) > 2 else "loop-transaction.png"
    build(out)
