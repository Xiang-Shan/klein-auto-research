"""Canonical concept card: why the framework is called Klein.

A stylised 2D line-art Klein bottle (side view): a round bulb body, a neck that
rises, hooks over the top, comes back down and PLUNGES THROUGH the body wall,
funnelling to the base from the inside — the inside surface is the outside
surface. The pierce is drawn with hidden-line (dashed) segments + a break in the
body rim so the front/back occlusion reads correctly (the thing that makes a
Klein-bottle drawing right).

Two flow annotations trace the research loop along the tube: the neck mouth
("this issue's conclusion") -> where it loops back into the body ("the first
line of next issue's ledger"). Exit reconnects to entrance.

Usage: uv run --no-sync python docs/diagrams/src/klein_bottle.py <out.png>
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, Ellipse, Polygon

sys.path.insert(0, str(Path(__file__).resolve().parent))
from klein_palette import (
    BLUE,
    SEQ_100,
    SEQ_150,
    SURFACE,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    new_fig,
    setup_fonts,
)

TITLE = "Why \u2018Klein\u2019"
SUBTITLE = "The inside is the outside — a research loop whose output feeds its own input"
LABEL_OUT = "a study\u2019s findings"
LABEL_IN = "the next study\u2019s priors\n(knowledge/)"
EASTER = "A true Klein bottle does not fit in 3-D space \u2014 you only ever see its projection."

LW_MAIN = 2.6      # confident vector line for body + neck walls
LW_HIDDEN = 1.9    # dashed hidden-line inside the body
DASH = (0, (5, 4))


# ----------------------------------------------------------------------------
# smooth-curve helpers: centripetal Catmull-Rom + constant-perp tube offset
# ----------------------------------------------------------------------------
def catmull_rom(points, samples=44, alpha=0.5):
    P = np.asarray(points, float)
    P = np.vstack([P[0] + (P[0] - P[1]) * 0.5, P, P[-1] + (P[-1] - P[-2]) * 0.5])
    n = len(P)
    out = []
    for i in range(1, n - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]

        def dt(a, b):
            return max(np.linalg.norm(b - a), 1e-6) ** alpha

        t0 = 0.0
        t1 = t0 + dt(p0, p1)
        t2 = t1 + dt(p1, p2)
        t3 = t2 + dt(p2, p3)
        last = i == n - 3
        for t in np.linspace(t1, t2, samples, endpoint=last):
            a1 = (t1 - t) / (t1 - t0) * p0 + (t - t0) / (t1 - t0) * p1
            a2 = (t2 - t) / (t2 - t1) * p1 + (t - t1) / (t2 - t1) * p2
            a3 = (t3 - t) / (t3 - t2) * p2 + (t - t2) / (t3 - t2) * p3
            b1 = (t2 - t) / (t2 - t0) * a1 + (t - t0) / (t2 - t0) * a2
            b2 = (t3 - t) / (t3 - t1) * a2 + (t - t1) / (t3 - t1) * a3
            out.append((t2 - t) / (t2 - t1) * b1 + (t - t1) / (t2 - t1) * b2)
    return np.array(out)


def widths_along(anchors, w_anchor, curve):
    A = np.asarray(anchors, float)
    sa = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(A, axis=0), axis=1))])
    sa /= sa[-1]
    sc = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(curve, axis=0), axis=1))])
    sc /= sc[-1]
    return np.interp(sc, sa, np.asarray(w_anchor, float))


def tube_edges(curve, hw):
    d = np.gradient(curve, axis=0)
    nrm = np.stack([-d[:, 1], d[:, 0]], axis=1)
    nrm /= (np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-9)
    hw = hw.reshape(-1, 1)
    return curve + nrm * hw, curve - nrm * hw


def draw_tube(ax, anchors, wanchor, *, fill, fill_a, edge, lw, z, dashed=False,
              clip=None):
    curve = catmull_rom(anchors)
    hw = widths_along(anchors, wanchor, curve)
    left, right = tube_edges(curve, hw)
    if fill is not None:
        poly = np.vstack([left, right[::-1]])
        patch = Polygon(poly, closed=True, facecolor=fill, edgecolor="none",
                        alpha=fill_a, zorder=z)
        ax.add_patch(patch)
        if clip is not None:
            patch.set_clip_path(clip)
    ls = DASH if dashed else "-"
    for edge_pts in (left, right):
        (ln,) = ax.plot(edge_pts[:, 0], edge_pts[:, 1], color=edge, linewidth=lw,
                        ls=ls, solid_capstyle="round", zorder=z + 0.15)
        if clip is not None:
            ln.set_clip_path(clip)
    return curve, left, right


def arc_line(ax, C, R, a0, a1, **kw):
    th = np.radians(np.linspace(a0, a1, int(abs(a1 - a0)) * 3 + 4))
    ax.plot(C[0] + R * np.cos(th), C[1] + R * np.sin(th), **kw)


def flow_arrow(ax, tail, tip, rad):
    ax.annotate("", xy=tip, xytext=tail,
                arrowprops=dict(arrowstyle="-|>", color=TEXT_SECONDARY, lw=2.3,
                                shrinkA=0, shrinkB=0, mutation_scale=20,
                                connectionstyle=f"arc3,rad={rad}"),
                zorder=6)


# ----------------------------------------------------------------------------
def build(out_path: str):
    setup_fonts("en")

    W, H = 100.0, 84.0
    fig = new_fig(9.8, 9.8 * H / W, dpi=200)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.axis("off")
    ax.set_facecolor(SURFACE)

    # ---- header ----
    ax.text(W / 2, 79.0, TITLE, ha="center", va="center", fontsize=33,
            fontweight="bold", color=TEXT_PRIMARY)
    ax.text(W / 2, 72.7, SUBTITLE, ha="center", va="center", fontsize=15.5,
            color=TEXT_SECONDARY)

    # ---- body geometry ----
    C = np.array([43.0, 33.0])
    R = 16.5

    # body fill (pale)
    ax.add_patch(Ellipse(C, 2 * R, 2 * R, facecolor=SEQ_100, edgecolor="none",
                         alpha=0.55, zorder=2.0))
    # clip path so everything "inside" the bottle stays inside the wall
    clip = Circle((C[0], C[1]), R, transform=ax.transData, fill=False, lw=0)

    # inside funnel: neck continued through the wall down toward the base,
    # flaring to become the base opening (dashed = hidden behind the front glass)
    funnel_anchors = [(56.2, 24.6), (52.0, 22.6), (47.0, 21.6), (42.8, 21.6)]
    funnel_w = [2.7, 3.5, 4.6, 5.4]
    draw_tube(ax, funnel_anchors, funnel_w, fill=SEQ_100, fill_a=0.32,
              edge=BLUE, lw=LW_HIDDEN, z=2.4, dashed=True, clip=clip)
    # internal mouth (the neck's opening == the base, seen from inside)
    mouth = Ellipse((42.8, 21.9), 11.0, 2.9, facecolor="none", edgecolor=BLUE,
                    linewidth=1.6, linestyle=DASH, zorder=2.6)
    ax.add_patch(mouth)
    mouth.set_clip_path(clip)

    # body rim: circle with two gaps (top = neck emerges, lower-right = neck
    # plunges through). Breaking the rim is half of the occlusion cue.
    arc_line(ax, C, R, 122, 305, color=BLUE, linewidth=LW_MAIN,
             solid_capstyle="round", zorder=3.0)
    arc_line(ax, C, R, 345, 432, color=BLUE, linewidth=LW_MAIN,
             solid_capstyle="round", zorder=3.0)

    # external neck: root (hidden in body) -> up -> hook over -> down -> wall
    neck_anchors = [
        (41.0, 44.0), (40.5, 51.0), (43.0, 58.0), (50.0, 63.0), (60.0, 64.0),
        (69.0, 60.0), (73.5, 52.0), (73.0, 43.0), (68.0, 35.0), (61.0, 29.0),
        (56.2, 24.6),
    ]
    neck_w = [4.3, 4.0, 3.8, 3.4, 3.3, 3.2, 3.1, 3.0, 2.9, 2.8, 2.7]
    draw_tube(ax, neck_anchors, neck_w, fill=SEQ_150, fill_a=0.60,
              edge=BLUE, lw=LW_MAIN, z=4.4)

    # pierce rim: the hole in the surface where the neck enters (on the wall)
    ax.add_patch(Ellipse((56.2, 24.6), 6.0, 2.4, angle=58, facecolor=SEQ_150,
                         edgecolor=BLUE, linewidth=2.1, alpha=0.85, zorder=4.7))

    # ---- flow annotations along the loop ----
    # A: the mouth / this issue's conclusion (upper neck), flow leaving
    flow_arrow(ax, (34.0, 60.2), (45.5, 61.6), rad=-0.28)
    ax.text(22.5, 61.0, LABEL_OUT, ha="center", va="center", fontsize=15,
            fontweight="bold", color=TEXT_PRIMARY, zorder=6)
    # B: loops back into the body / next issue's first line
    flow_arrow(ax, (72.0, 21.2), (59.5, 24.4), rad=0.30)
    ax.text(81.5, 19.6, LABEL_IN, ha="center", va="center", fontsize=15,
            fontweight="bold", color=TEXT_PRIMARY, zorder=6)

    # ---- corner easter egg ----
    ax.text(W / 2, 4.6, EASTER, ha="center", va="center", fontsize=12,
            color=TEXT_MUTED, zorder=6)

    fig.savefig(out_path, dpi=200, facecolor=SURFACE, bbox_inches=None)
    plt.close(fig)
    print(f"wrote {out_path}  size(in)={fig.get_size_inches()}  dpi=200")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "klein-bottle.png"
    build(out)
