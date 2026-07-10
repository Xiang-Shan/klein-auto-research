"""figures_extra.py — study 02 bespoke figures (kleinlib.figures lacks these forms).

Five figures for the RQLS PV-severity study, per the Phase-2 pre-registration and
steer 3 (dataviz-clean: validated colorblind-safe palette, entity-stable colors,
ink-token text, dpi 150, MC-floor reference everywhere):

  1. breakdown_curve.png   — premium error vs eps, single-family (E3) + realistic (E7),
                             log-y (naive MLE reaches 352%), MC floor line.
  2. efficiency_cost.png   — E2 relative efficiency vs MLE at eps=0 (premium-MSE and
                             sigma-MSE ratios), err-ratio annotations.
  3. window_qq.png         — E4 representative rep: conditional empirical quantiles vs
                             fitted model quantiles; truncated/censored regions shaded.
  4. premium_tornado.png   — THE money slide: E7 signed premium bias per estimator x eps,
                             diverging blue/red (under/over), +-4.28% floor band,
                             overcharging direction annotated.
  5. severity_fan.png      — E5 realistic cell: true mixture log-density vs per-estimator
                             fitted fans (10-90% band over the first 100 reps).

Deterministic (seeds 42+r, same as the experiments); reads aux_metrics.tsv and the two
sweep sidecars; refits only for the QQ and fan panels. Not an experiment — no ledger
writes. Palette: skill-validated subset (worst adjacent CVD dE 47.2; aqua/yellow carry
direct-label relief).

Run:  uv run python studies/02-rqls-pv-severity/figures_extra.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import scipy.stats as st  # noqa: E402

_STUDY_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_STUDY_DIR))

from generator import STD_DEDUCTIBLE as D, STD_LIMIT as U, PVLossGenerator  # noqa: E402
from estimators import default_p_grid, mle_full, mle_truncated_censored, mtm, qls  # noqa: E402

FIG_DIR = _STUDY_DIR / "figures"
FLOOR = 4.28  # single-family n=2000 MC sampling floor (E1, 200 reps)

# --- validated palette (dataviz skill reference instance; subset re-validated) ----
SURFACE, INK, INK2, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#898781"
GRID, BASELINE = "#e1e0d9", "#c3c2b7"
ENTITY = {  # entity-stable across every figure
    "mle": "#e34948", "mle_naive": "#e34948",
    "mle_tc": "#2a78d6",
    "qls_ols": "#1baf7a", "qls_window_trim": "#1baf7a", "qls_window": "#1baf7a",
    "qls_gls": "#eda100",
    "mtm": "#4a3aa7",
}
DIV_OVER, DIV_UNDER = "#e34948", "#2a78d6"  # diverging pair (polarity, tornado only)
NAME = {
    "mle": "naive MLE", "mle_naive": "naive MLE", "mle_tc": "trunc/cens MLE",
    "qls_ols": "QLS-OLS", "qls_window_trim": "window-QLS (trimmed)",
    "qls_window": "window-QLS", "qls_gls": "QLS-GLS", "mtm": "MTM",
}
# E3's QLS variants ran on the TRIMMED grid (E2's on the default grid) — label per context.
NAME_E3 = {**NAME, "qls_ols": "QLS-OLS (trimmed)", "qls_gls": "QLS-GLS (trimmed)"}

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": BASELINE, "axes.linewidth": 1.0,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "xtick.color": MUTED, "ytick.color": MUTED, "text.color": INK,
    "axes.labelcolor": INK2, "axes.titlecolor": INK,
    "font.family": "sans-serif", "font.size": 9,
    "axes.spines.top": False, "axes.spines.right": False,
})


def read_aux() -> dict[tuple[int, str], str]:
    rows: dict[tuple[int, str], str] = {}
    for line in (_STUDY_DIR / "aux_metrics.tsv").read_text().splitlines()[1:]:
        parts = line.split("\t")
        if len(parts) == 3:
            rows[(int(parts[0]), parts[1])] = parts[2]
    return rows


def read_sidecar(name: str) -> list[dict]:
    out = []
    for line in (_STUDY_DIR / "sweeps" / f"{name}.sidecar.tsv").read_text().splitlines()[1:]:
        trial, params_json, metric, wall, status = line.split("\t")
        rec = json.loads(params_json)
        rec.update(err=float(metric) if metric != "NA" else np.nan, status=status)
        out.append(rec)
    return out


def _floor_line(ax, x=0.98, label=True):
    ax.axhline(FLOOR, color=MUTED, lw=1.2, ls=(0, (4, 3)), zorder=1)
    if label:
        ax.text(x, FLOOR * 1.08, f"MC floor {FLOOR}%", transform=ax.get_yaxis_transform(),
                ha="right", va="bottom", fontsize=7.5, color=MUTED)


def _dodge_log(values: list[float], min_gap_dec: float = 0.075) -> list[float]:
    """Nudge label y-positions apart (log10 space) until adjacent gaps clear min_gap_dec."""
    order = np.argsort(values)
    logs = np.log10(np.asarray(values, float))[order]
    for i in range(1, len(logs)):
        if logs[i] - logs[i - 1] < min_gap_dec:
            logs[i] = logs[i - 1] + min_gap_dec
    out = np.empty_like(logs)
    out[order] = 10 ** logs
    return list(out)


# --- 1. breakdown curve ------------------------------------------------------
def fig_breakdown():
    e3, e7 = read_sidecar("e3_breakdown"), read_sidecar("e7_decision")
    panels = [
        ("Single-family lognormal (E3)", e3, ["mle", "qls_ols", "qls_gls", "mtm"], NAME_E3),
        ("Realistic mixture + d/u (E7)", e7, ["mle_naive", "mle_tc", "qls_window_trim", "mtm"], NAME),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 4.1), sharey=True)
    for ax, (title, rows, ests, names) in zip(axes, panels):
        ends = []
        for est in ests:
            pts = sorted([(r["eps"] * 100, r["err"]) for r in rows if r["estimator"] == est])
            xs, ys = zip(*pts)
            ax.plot(xs, ys, "-o", color=ENTITY[est], lw=2, ms=4.5,
                    mec=SURFACE, mew=0.8, zorder=3)
            ends.append(ys[-1])
        for est, y_lab in zip(ests, _dodge_log(ends)):
            ax.annotate(names[est], (10, y_lab), xytext=(6, 0),
                        textcoords="offset points", fontsize=7.5, color=INK2, va="center")
        ax.set_yscale("log")
        ax.set_xticks([0, 1, 2, 5, 10])
        ax.set_xlim(-0.4, 13.6)
        ax.set_xlabel("contamination ε (%)")
        ax.set_title(title, fontsize=10, loc="left")
        _floor_line(ax, x=0.55 if "E3" in title else 0.98)
    axes[0].set_ylabel("mean premium error % vs truth (log)")
    fig.suptitle("Breakdown under contamination — premium error vs ε  (500 MC reps/cell, n=2,000)",
                 fontsize=11, x=0.01, ha="left", color=INK)
    fig.text(0.01, 0.03, "Left: clean single family — trimmed estimators stay bounded while naive MLE diverges to 352%.",
             fontsize=7.5, color=INK2)
    fig.text(0.01, 0.008, "Right: realistic lab — misspecification (23–42% at ε=0) dominates until contamination cancels it.",
             fontsize=7.5, color=INK2)
    fig.tight_layout(rect=(0, 0.06, 1, 0.94))
    fig.savefig(FIG_DIR / "breakdown_curve.png", dpi=150)
    plt.close(fig)


# --- 2. efficiency cost bar --------------------------------------------------
def fig_efficiency():
    aux = read_aux()
    ests = ["qls_ols", "qls_gls", "mtm"]
    prem = [float(aux[(2, f"rel_eff_premium_{e}_vs_mle")]) for e in ests]
    sig = [float(aux[(2, f"rel_eff_sigma_{e}_vs_mle")]) for e in ests]
    ratio = [float(aux[(2, f"err_ratio_{e}_vs_mle")]) for e in ests]

    x = np.arange(len(ests))
    w = 0.38
    fig, ax = plt.subplots(figsize=(6.4, 3.9))
    ax.bar(x - w / 2, prem, w, color=[ENTITY[e] for e in ests],
           edgecolor=SURFACE, lw=2, zorder=3)
    ax.bar(x + w / 2, sig, w, color=[ENTITY[e] for e in ests], alpha=0.45,
           edgecolor=SURFACE, lw=2, zorder=3)
    for xi, (p, r) in enumerate(zip(prem, ratio)):
        ax.text(xi - w / 2, p + 0.02, f"{p:.2f}\n(err ×{r:.3f})", ha="center",
                fontsize=7.5, color=INK2)
    for xi, s in enumerate(sig):
        ax.text(xi + w / 2, s + 0.02, f"{s:.2f}", ha="center", fontsize=7.5, color=INK2)
    ax.axhline(1.0, color=INK, lw=1.2, ls=(0, (4, 3)))
    ax.text(len(ests) - 0.52, 1.015, "MLE = 1.0 (efficiency ceiling)", ha="right",
            fontsize=7.5, color=INK2)
    ax.set_xticks(x, [NAME[e] for e in ests])
    ax.set_ylim(0, 1.12)
    ax.set_ylabel("relative efficiency vs MLE  (MSE$_{MLE}$ / MSE)")
    ax.set_title("The price of robustness on clean data (E2: ε=0, single family, 1,000 MC reps)",
                 fontsize=10.5, loc="left")
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(facecolor=INK2, label="premium-MSE ratio"),
                       Patch(facecolor=INK2, alpha=0.45, label=r"$\hat\sigma$-MSE ratio")],
              frameon=False, fontsize=8, loc="lower right")
    fig.text(0.01, 0.045, "QLS-OLS keeps ~85% of MLE's premium efficiency; the diagonal plug-in GLS adds none;",
             fontsize=7.5, color=INK2)
    fig.text(0.01, 0.018, "MTM's 10% trim costs the most. Solid = premium MSE ratio, faded = $\\hat\\sigma$ MSE ratio.",
             fontsize=7.5, color=INK2)
    fig.tight_layout(rect=(0, 0.075, 1, 1))
    fig.savefig(FIG_DIR / "efficiency_cost.png", dpi=150)
    plt.close(fig)


# --- 3. window QQ ------------------------------------------------------------
def fig_window_qq():
    gen = PVLossGenerator(mu=9.0, sigma=1.1, single_family=True, deductible=D, limit=U)
    s = gen.sample(2000, seed=42, incomplete=True, contaminate=False)
    z = np.log(s.losses[~s.censored])
    p = np.linspace(0.02, 0.98, 49)
    qhat = np.quantile(z, p)

    naive = mle_full(s.losses, "lognormal").params
    q_naive = naive["mu"] + naive["sigma"] * st.norm.ppf(p)  # UNconditional quantiles
    wfit = qls(s.losses, D, U, default_p_grid(), "lognormal", censored=s.censored).params
    a, b = (np.log(D) - wfit["mu"]) / wfit["sigma"], (np.log(U) - wfit["mu"]) / wfit["sigma"]
    lo, hi = st.norm.cdf(a), st.norm.cdf(b)
    q_win = wfit["mu"] + wfit["sigma"] * st.norm.ppf(lo + p * (hi - lo))  # conditional

    fig, ax = plt.subplots(figsize=(6.2, 5.4))
    lim = (7.4, 12.4)
    ax.axvspan(lim[0], np.log(D), color=GRID, alpha=0.55, zorder=0)
    ax.text(np.log(D) - 0.07, 11.9, "truncated: losses < $5k never filed", rotation=90,
            fontsize=7.5, color=INK2, ha="right", va="top")
    ax.plot(lim, lim, color=INK, lw=1.2, ls=(0, (4, 3)), zorder=2)
    ax.text(11.15, 11.42, "y = x (perfect fit)", fontsize=7.5, color=INK2, rotation=41)
    ax.plot(q_naive, qhat, "o", ms=4.5, mfc="none", mec=ENTITY["mle_naive"], mew=1.4,
            label="naive MLE (pretends data complete)", zorder=3)
    ax.plot(q_win, qhat, "o", ms=4.5, mfc=ENTITY["qls_window"], mec=SURFACE, mew=0.6,
            label="window-QLS (conditional quantiles)", zorder=4)
    ax.set_xlim(lim)
    ax.set_ylim(lim)
    ax.set_aspect("equal")
    ax.set_xlabel("fitted model quantile of log-loss")
    ax.set_ylabel("empirical quantile of observed log-loss")
    ax.set_title("Window-QQ under truncation (E4 cell, one rep: seed 42, n_obs=1,322;\n"
                 "d=\\$5k trunc, u=\\$2M cens — censoring boundary ln u=14.5 lies off-plot)",
                 fontsize=10, loc="left")
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    fig.text(0.01, 0.03, "Naive MLE's quantile curve bends off the diagonal (it spends mass below the deductible);",
             fontsize=7.5, color=INK2)
    fig.text(0.01, 0.008, "the window fit lies on it. MC verdict: E4, 500 reps (window-QLS 4.83% vs floor).",
             fontsize=7.5, color=INK2)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(FIG_DIR / "window_qq.png", dpi=150)
    plt.close(fig)


# --- 4. premium tornado (money slide) ----------------------------------------
def fig_tornado():
    aux = read_aux()
    ests = ["mle_naive", "mle_tc", "qls_window_trim", "mtm"]
    eps = [0, 1, 2, 5, 10]
    rows = [(e, k, float(aux[(7, f"prem_bias_pct_{e}_eps{k}")])) for e in ests for k in eps]

    XCAP = 70.0
    fig, ax = plt.subplots(figsize=(7.6, 6.4))
    ax.axvspan(-FLOOR, FLOOR, color=GRID, alpha=0.55, zorder=0)
    ys = []
    for i, (est, k, v) in enumerate(rows):
        y = len(rows) - 1 - i - (ests.index(est)) * 0.6  # gap between estimator groups
        ys.append(y)
        vv = np.clip(v, -XCAP, XCAP)
        ax.barh(y, vv, height=0.72, color=(DIV_OVER if v > 0 else DIV_UNDER),
                edgecolor=SURFACE, lw=1.2, zorder=3)
        lbl = f"{v:+.1f}" + ("  (off-scale)" if abs(v) > XCAP else "")
        ax.text(vv + (1.2 if v > 0 else -1.2), y, lbl, va="center",
                ha="left" if v > 0 else "right", fontsize=7.2, color=INK2)
    for est in ests:  # group headers
        idx = [y for (e, k, v), y in zip(rows, ys) if e == est]
        ax.text(-XCAP - 24, np.mean(idx), NAME[est], fontsize=8.5, color=INK,
                ha="left", va="center", fontweight="bold")
    ax.axvline(0, color=INK, lw=1.2, zorder=2)
    ax.set_yticks(ys, [f"ε={k}%" for (_, k, _) in rows], fontsize=7.5)
    ax.set_xlim(-XCAP - 25, XCAP + 8)
    ax.set_ylim(min(ys) - 1.6, max(ys) + 1.6)
    ax.text(0, min(ys) - 1.25, f"±{FLOOR}% MC floor", ha="center", fontsize=7.5, color=MUTED)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("signed premium bias % vs truth ($62,346 layer premium)")
    top = max(ys) + 1.05
    ax.annotate("underprices (reserve risk)", xy=(-XCAP - 20, top), xytext=(-14, top),
                fontsize=8.5, color=DIV_UNDER, va="center", ha="right",
                arrowprops=dict(arrowstyle="->", color=DIV_UNDER, lw=1.4))
    ax.annotate("OVERCHARGES policyholders", xy=(XCAP + 5, top), xytext=(16, top),
                fontsize=8.5, color=DIV_OVER, va="center", ha="left",
                arrowprops=dict(arrowstyle="->", color=DIV_OVER, lw=1.4))
    ax.set_title("The money slide — how wrong is the premium? (E7 decision grid: realistic\n"
                 "mixture + d/u, 500 MC reps/cell; naive MLE @ ε=10% = +188.9%, off-scale)",
                 fontsize=10.5, loc="left")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "premium_tornado.png", dpi=150)
    plt.close(fig)


# --- 5. severity fan ---------------------------------------------------------
def fig_severity_fan():
    gen = PVLossGenerator(contam_eps=0.05, deductible=D, limit=U)  # E5 realistic cell
    comps = gen._components()
    zg = np.linspace(5.5, 16.0, 400)
    truth_pdf = np.zeros_like(zg)
    for w, c in comps:  # every tail-off component is lognormal => normal in log space
        mu_c, sg_c = np.log(c.kwds["scale"]), c.kwds["s"]
        truth_pdf += w * st.norm.pdf(zg, mu_c, sg_c)

    fits = {"mle_naive": [], "mle_tc": [], "qls_window_trim": [], "mtm": []}
    trim_grid = default_p_grid(trim=0.15)
    for r in range(100):  # fan = first 100 of E5's 500 reps (same seeds)
        s = gen.sample(2000, seed=42 + r, incomplete=True, contaminate=True)
        fits["mle_naive"].append(mle_full(s.losses, "lognormal").params)
        fits["mle_tc"].append(mle_truncated_censored(s.losses, D, U, s.censored, "lognormal").params)
        fits["qls_window_trim"].append(
            qls(s.losses, D, U, trim_grid, "lognormal", censored=s.censored).params)
        fits["mtm"].append(mtm(s.losses, trim=0.10, family="lognormal").params)

    fig, axes = plt.subplots(2, 2, figsize=(9.2, 6.6), sharex=True, sharey=True)
    ticks = [1e3, 1e4, 1e5, 1e6]
    for ax, (est, plist) in zip(axes.flat, fits.items()):
        dens = np.array([st.norm.pdf(zg, p["mu"], p["sigma"]) for p in plist])
        lo, med, hi = np.percentile(dens, [10, 50, 90], axis=0)
        ax.fill_between(zg, lo, hi, color=ENTITY[est], alpha=0.28, lw=0, zorder=2)
        ax.plot(zg, med, color=ENTITY[est], lw=2, zorder=3)
        ax.plot(zg, truth_pdf, color=INK, lw=1.8, ls=(0, (5, 2)), zorder=4)
        for x0, lbl in ((np.log(D), "d=$5k"), (np.log(U), "u=$2M")):
            ax.axvline(x0, color=MUTED, lw=1.0, ls=(0, (2, 2)), zorder=1)
            ax.text(x0 + 0.08, 0.55, lbl, fontsize=7, color=MUTED)
        ax.set_title(NAME[est], fontsize=9.5, loc="left", color=INK)
        ax.set_xticks(np.log(ticks), ["$1k", "$10k", "$100k", "$1M"])
        ax.set_ylim(0, 0.60)
    for ax in axes[:, 0]:
        ax.set_ylabel("density of log-loss")
    handles = [plt.Line2D([], [], color=INK, ls=(0, (5, 2)), lw=1.8, label="TRUE mixture (hail shoulder at right)"),
               plt.Line2D([], [], color=MUTED, lw=6, alpha=0.4, label="fitted single lognormal: 10–90% fan + median (100 reps)")]
    fig.legend(handles=handles, frameon=False, fontsize=8, ncols=2, loc="lower left",
               bbox_to_anchor=(0.005, 0.0))
    fig.suptitle("Severity fan at the realistic cell (E5: mixture, ε=5%, trunc+cens) — every single-family fit\n"
                 "misses the hail shoulder; trimmed fits miss it worst (the −19% to −36% underpricing)",
                 fontsize=10.5, x=0.01, ha="left", color=INK)
    fig.tight_layout(rect=(0, 0.045, 1, 0.925))
    fig.savefig(FIG_DIR / "severity_fan.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    FIG_DIR.mkdir(exist_ok=True)
    for fn in (fig_breakdown, fig_efficiency, fig_window_qq, fig_tornado, fig_severity_fan):
        fn()
        print(f"wrote figures/{fn.__name__.replace('fig_', '')}*.png")
    print(f"figures dir: {FIG_DIR}")
