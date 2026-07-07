"""Chart rendering -> base64 PNG strings, embedded inline in the HTML report.

Palette is intentionally institutional-research, not the AI-default cream:
  ink #0E1116 · paper #FBFBF9 · brand teal #0F6466
  up #1B7A5A · down #B23A48 · hairline #C9C9C2 · muted #6B6F76
"""
from __future__ import annotations

import base64
import io

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager, rcParams

INK = "#0E1116"
PAPER = "#FBFBF9"
TEAL = "#0F6466"
UP = "#1B7A5A"
DOWN = "#B23A48"
HAIR = "#C9C9C2"
MUTED = "#6B6F76"
GOLD = "#B9892E"

rcParams.update({
    "font.family": "DejaVu Sans",
    "axes.edgecolor": INK,
    "axes.linewidth": 0.8,
    "text.color": INK,
    "axes.labelcolor": INK,
    "xtick.color": INK,
    "ytick.color": INK,
    "figure.facecolor": PAPER,
    "axes.facecolor": PAPER,
    "savefig.facecolor": PAPER,
})


def _b64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=140, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return "data:image/png;base64," + base64.b64encode(buf.read()).decode()


def football_field(rows: list[dict], price: float, currency: str = "$") -> str:
    """rows: [{'label','low','high','point'(optional)}] one per method."""
    fig, ax = plt.subplots(figsize=(8.2, 0.62 * len(rows) + 1.1))
    labels = [r["label"] for r in rows]
    ypos = range(len(rows))
    for i, r in enumerate(rows):
        lo, hi = r["low"], r["high"]
        ax.barh(i, hi - lo, left=lo, height=0.5, color=TEAL, alpha=0.22,
                edgecolor=TEAL, linewidth=1.0, zorder=2)
        if r.get("point") is not None:
            ax.plot(r["point"], i, "D", color=TEAL, markersize=7, zorder=4)
        ax.text(lo, i + 0.32, f"{currency}{lo:,.0f}", va="bottom", ha="left",
                fontsize=8, color=MUTED)
        ax.text(hi, i + 0.32, f"{currency}{hi:,.0f}", va="bottom", ha="right",
                fontsize=8, color=MUTED)
    ax.axvline(price, color=DOWN, lw=1.6, ls="--", zorder=5)
    ax.annotate(f"price {currency}{price:,.0f}", xy=(price, -0.55),
                xycoords=("data", "data"), color=DOWN, fontsize=8.5,
                va="bottom", ha="center", fontweight="bold",
                annotation_clip=False)
    ax.set_yticks(list(ypos))
    ax.set_yticklabels(labels, fontsize=10)
    ax.invert_yaxis()
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(left=False)
    ax.set_xlabel(f"Implied value per share ({currency})", fontsize=9)
    ax.grid(axis="x", color=HAIR, lw=0.5, zorder=0)
    return _b64(fig)


def projection_chart(years, revenue, fcff, currency="$") -> str:
    fig, ax1 = plt.subplots(figsize=(8.2, 3.4))
    scale, unit = _scale(max(revenue))
    rev_s = [v / scale for v in revenue]
    fcff_s = [v / scale for v in fcff]
    x = range(len(years))
    ax1.bar([i - 0.2 for i in x], rev_s, width=0.4, color=TEAL, alpha=0.85, label="Revenue")
    ax1.bar([i + 0.2 for i in x], fcff_s, width=0.4, color=GOLD, alpha=0.9, label="FCFF")
    ax1.set_xticks(list(x))
    ax1.set_xticklabels(years, fontsize=9)
    ax1.set_ylabel(f"{currency} {unit}", fontsize=9)
    ax1.spines[["top", "right"]].set_visible(False)
    ax1.grid(axis="y", color=HAIR, lw=0.5)
    ax1.legend(frameon=False, fontsize=9, loc="upper left")
    ax1.set_title("Projected revenue & unlevered free cash flow", fontsize=10,
                  loc="left", color=INK)
    return _b64(fig)


def sensitivity_heatmap(sens: dict, currency="$") -> str:
    import numpy as np
    grid = np.array([[v if v is not None else np.nan for v in row] for row in sens["grid"]])
    fig, ax = plt.subplots(figsize=(6.6, 4.0))
    im = ax.imshow(grid, cmap="BrBG", aspect="auto")
    ax.set_xticks(range(len(sens["growths"])))
    ax.set_xticklabels([f"{g:.1%}" for g in sens["growths"]], fontsize=8)
    ax.set_yticks(range(len(sens["waccs"])))
    ax.set_yticklabels([f"{w:.1%}" for w in sens["waccs"]], fontsize=8)
    ax.set_xlabel("Terminal growth (g)", fontsize=9)
    ax.set_ylabel("WACC", fontsize=9)
    for i in range(grid.shape[0]):
        for j in range(grid.shape[1]):
            if not np.isnan(grid[i, j]):
                ax.text(j, i, f"{currency}{grid[i, j]:,.0f}", ha="center", va="center",
                        fontsize=7.5, color=INK)
    ax.set_title("Value per share sensitivity", fontsize=10, loc="left")
    return _b64(fig)


def ev_bridge(pv_explicit, pv_tv, net_debt, minority, equity_value, currency="$") -> str:
    scale, unit = _scale(max(abs(pv_explicit + pv_tv), abs(equity_value), 1))
    steps = [
        ("PV explicit\nFCFF", pv_explicit / scale, TEAL),
        ("PV terminal\nvalue", pv_tv / scale, TEAL),
        ("Net debt", -net_debt / scale, DOWN),
    ]
    if minority:
        steps.append(("Minority", -minority / scale, DOWN))
    fig, ax = plt.subplots(figsize=(7.4, 3.4))
    cum = 0.0
    for i, (lab, val, col) in enumerate(steps):
        ax.bar(i, val, bottom=cum, color=col, alpha=0.85, width=0.6)
        cum += val
    ax.bar(len(steps), equity_value / scale, color=INK, alpha=0.9, width=0.6)
    labels = [s[0] for s in steps] + ["Equity\nvalue"]
    ax.set_xticks(range(len(steps) + 1))
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel(f"{currency} {unit}", fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color=HAIR, lw=0.5)
    ax.set_title("Enterprise value to equity bridge", fontsize=10, loc="left")
    return _b64(fig)


def _scale(v):
    if v >= 1e12:
        return 1e12, "trn"
    if v >= 1e9:
        return 1e9, "bn"
    if v >= 1e6:
        return 1e6, "mn"
    return 1.0, ""


def margins_returns_chart(years_h, margins_h, years_f, margins_f, currency="$") -> str:
    """EBIT margin, historical vs forecast, with a divider at the estimate boundary."""
    fig, ax = plt.subplots(figsize=(8.2, 2.9))
    xs_h = list(range(len(years_h)))
    xs_f = list(range(len(years_h), len(years_h) + len(years_f)))
    ax.plot(xs_h, [m * 100 for m in margins_h], "-o", color=INK, lw=1.6, ms=4,
            label="EBIT margin (actual)")
    ax.plot([xs_h[-1]] + xs_f, [margins_h[-1] * 100] + [m * 100 for m in margins_f],
            "--o", color=TEAL, lw=1.6, ms=4, label="EBIT margin (estimate)")
    ax.axvline(len(years_h) - 0.5, color=HAIR, lw=1.0)
    ax.text(len(years_h) - 0.45, ax.get_ylim()[1], " E→", fontsize=8, color=MUTED, va="top")
    ax.set_xticks(xs_h + xs_f)
    ax.set_xticklabels([str(y) for y in years_h] + [f"{y}E" for y in years_f], fontsize=8.5)
    ax.set_ylabel("%", fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color=HAIR, lw=0.5)
    ax.legend(frameon=False, fontsize=8.5, loc="best")
    return _b64(fig)
