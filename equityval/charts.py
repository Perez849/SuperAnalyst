"""Inline-SVG charts in the Investment Clock style.

Every chart is plain SVG that takes its colours from CSS classes defined by the report
template (themed per screen / print), so they stay crisp at any size, recolour with the
theme and survive PDF export. No image libraries, no base64 blobs.

  valuation_clock()   the hero dial: 12-month expected return, bear-bull arc, Street marker
  phase_wheel()       the four-phase Investment Clock with the sector's home phases lit
  football_field()    lens-by-lens value ranges against price, target and Street
  sensitivity_table() WACC x g grid, shaded against the current price (HTML table)
  ev_bridge()         PV explicit + PV terminal - net debt = equity
  projection()        revenue and FCFF bars
  margin_lines()      EBIT margin, actual vs estimate
"""
from __future__ import annotations

import math
from html import escape

from .theme import PHASE_NAMES, PHASE_ORDER

CX = CY = 180.0


def _pt(r: float, deg: float, cx: float = CX, cy: float = CY) -> tuple[float, float]:
    a = math.radians(deg)
    return cx + r * math.cos(a), cy + r * math.sin(a)


def _arc(r: float, a0: float, a1: float, cx: float = CX, cy: float = CY) -> str:
    x0, y0 = _pt(r, a0, cx, cy)
    x1, y1 = _pt(r, a1, cx, cy)
    large = 1 if (a1 - a0) % 360 > 180 else 0
    return f"M{x0:.2f},{y0:.2f} A{r:.2f},{r:.2f} 0 {large} 1 {x1:.2f},{y1:.2f}"


def _fmt(v: float, cur: str) -> str:
    if v is None or not math.isfinite(v):
        return "—"
    if abs(v) >= 1000:
        return f"{cur}{v:,.0f}"
    if abs(v) >= 100:
        return f"{cur}{v:,.0f}"
    return f"{cur}{v:,.2f}"


# --------------------------------------------------------------------------- #
#  Hero dial
# --------------------------------------------------------------------------- #
_R_MIN, _R_MAX = -0.50, 1.00             # expected-return range shown on the dial
_A0, _A1 = 135.0, 405.0                  # 270 degree sweep, bottom-left -> bottom-right


def _ang(ret: float) -> float:
    ret = min(max(ret, _R_MIN), _R_MAX)
    return _A0 + (ret - _R_MIN) / (_R_MAX - _R_MIN) * (_A1 - _A0)


def valuation_clock(total_return: float, bear_ret: float, bull_ret: float,
                    street_ret: float | None, rating: str, rdir: str, target_txt: str,
                    price_txt: str, rated: bool = True, confidence: str = "Medium") -> str:
    """The signature element: a gauge whose face is a clock."""
    out = [f'<svg class="dial" viewBox="0 0 360 360" role="img" aria-label="12-month expected '
           f'return {total_return:+.0%}, rating {escape(rating)}">']
    # minute ring (60 ticks) and hour ticks (12) around the full circle: the clock face
    for i in range(60):
        major = i % 5 == 0
        r0, r1 = (162, 170) if major else (166, 170)
        x0, y0 = _pt(r0, i * 6 - 90)
        x1, y1 = _pt(r1, i * 6 - 90)
        out.append(f'<line class="{"tick-major" if major else "tick"}" x1="{x0:.1f}" y1="{y0:.1f}" '
                   f'x2="{x1:.1f}" y2="{y1:.1f}"/>')
    # rating bands on the 270 degree gauge
    bands = [(_R_MIN, -0.15, "b-down2"), (-0.15, -0.05, "b-down"), (-0.05, 0.05, "b-flat"),
             (0.05, 0.15, "b-up"), (0.15, _R_MAX, "b-up2")]
    for lo, hi, cls in bands:
        out.append(f'<path class="band {cls}" d="{_arc(138, _ang(lo) + 0.6, _ang(hi) - 0.6)}"/>')
    # bear-bull range, inner arc
    if rated:
        a_lo, a_hi = _ang(bear_ret), _ang(bull_ret)
        if a_hi - a_lo > 1:
            out.append(f'<path class="range" d="{_arc(118, a_lo, a_hi)}"/>')
    # scale labels
    for ret, txt in ((-0.5, "−50%"), (-0.15, ""), (0.0, "0"), (0.5, "+50%"), (1.0, "+100%")):
        if not txt:
            continue
        x, y = _pt(100, _ang(ret))
        out.append(f'<text class="scale" x="{x:.1f}" y="{y:.1f}" text-anchor="middle" '
                   f'dominant-baseline="middle">{txt}</text>')
    # Street marker (triangle on the outer edge)
    if street_ret is not None:
        a = _ang(street_ret)
        x, y = _pt(152, a)
        xo, yo = _pt(166, a)
        out.append(f'<path class="street" d="M{x:.1f},{y:.1f} L{xo - 4*math.sin(math.radians(a)):.1f},'
                   f'{yo + 4*math.cos(math.radians(a)):.1f} L{xo + 4*math.sin(math.radians(a)):.1f},'
                   f'{yo - 4*math.cos(math.radians(a)):.1f} Z"/>')
        lx, ly = _pt(178, a)
        out.append(f'<text class="scale street-t" x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" '
                   f'dominant-baseline="middle">S</text>')
    # needle (the hand) + hub
    if rated:
        a = _ang(total_return)
        nx, ny = _pt(130, a)
        tx, ty = _pt(-26, a)
        out.append(f'<line class="hand hand-{rdir}" x1="{tx:.1f}" y1="{ty:.1f}" x2="{nx:.1f}" y2="{ny:.1f}"/>')
    out.append('<circle class="hub-ring" cx="180" cy="180" r="62"/>')
    out.append('<circle class="hub" cx="180" cy="180" r="58"/>')
    out.append('<text class="hub-k" x="180" y="152" text-anchor="middle">12M PRICE TARGET</text>')
    out.append(f'<text class="hub-v" x="180" y="186" text-anchor="middle">{escape(target_txt)}</text>')
    out.append(f'<text class="hub-r hub-{rdir}" x="180" y="206" text-anchor="middle">{escape(rating)}</text>')
    out.append(f'<text class="hub-s" x="180" y="222" text-anchor="middle">price {escape(price_txt)}</text>')
    out.append('</svg>')
    return "".join(out)


# --------------------------------------------------------------------------- #
#  Phase wheel
# --------------------------------------------------------------------------- #
# quadrant centres (clock angles, svg degrees): TL, TR, BR, BL
_QUAD = {"recovery": (180, 270), "overheat": (270, 360), "stagflation": (0, 90), "reflation": (90, 180)}


def phase_wheel(primary: str, secondary: str | None = None) -> str:
    out = ['<svg class="wheel" viewBox="0 0 360 360" role="img" aria-label="Investment Clock phases">']
    for ph in PHASE_ORDER:
        a0, a1 = _QUAD[ph]
        r_out, r_in = 150, 78
        x0, y0 = _pt(r_out, a0 + 1.5); x1, y1 = _pt(r_out, a1 - 1.5)
        x2, y2 = _pt(r_in, a1 - 1.5); x3, y3 = _pt(r_in, a0 + 1.5)
        d = (f"M{x0:.1f},{y0:.1f} A{r_out},{r_out} 0 0 1 {x1:.1f},{y1:.1f} "
             f"L{x2:.1f},{y2:.1f} A{r_in},{r_in} 0 0 0 {x3:.1f},{y3:.1f} Z")
        state = "lit" if ph == primary else ("lit2" if ph == secondary else "dim")
        out.append(f'<path class="seg seg-{ph} {state}" d="{d}"/>')
        name, regime, asset = PHASE_NAMES[ph]
        mx, my = _pt(112, (a0 + a1) / 2 + (6 if ph in ('recovery', 'stagflation') else -6))
        out.append(f'<text class="ph-n {state}" x="{mx:.1f}" y="{my - 6:.1f}" text-anchor="middle">{name.upper()}</text>')
        out.append(f'<text class="ph-s {state}" x="{mx:.1f}" y="{my + 8:.1f}" text-anchor="middle">{escape(regime.replace("  ", " \u00b7 "))}</text>')
        out.append(f'<text class="ph-a {state}" x="{mx:.1f}" y="{my + 22:.1f}" text-anchor="middle">best: {asset}</text>')
    # clockwise arrow ring in the centre
    out.append('<circle class="wheel-hub" cx="180" cy="180" r="62"/>')
    out.append(f'<path class="wheel-arrow" d="{_arc(40, -150, 120)}"/>')
    ax, ay = _pt(40, 120)
    out.append(f'<path class="wheel-head" d="M{ax:.1f},{ay:.1f} l-9,-3 l5,-8 z" transform="rotate(30 {ax:.1f} {ay:.1f})"/>')
    out.append('<text class="wheel-c" x="180" y="184" text-anchor="middle">CYCLE</text>')
    out.append('</svg>')
    return "".join(out)


# --------------------------------------------------------------------------- #
#  Football field
# --------------------------------------------------------------------------- #
def football_field(rows: list[dict], price: float, target: float | None, cur: str = "$",
                   width: int = 760) -> str:
    """rows: {'label','low','high','point','kind'} kind in lens|street|target."""
    vals = [price] + [r["low"] for r in rows] + [r["high"] for r in rows] + ([target] if target else [])
    vals = [v for v in vals if v is not None and math.isfinite(v)]
    lo, hi = min(vals), max(vals)
    pad = (hi - lo) * 0.08 or hi * 0.1
    lo, hi = max(lo - pad, 0.0), hi + pad
    left, right, top, rh = 188, 22, 26, 38
    plot_w = width - left - right
    height = top + rh * len(rows) + 34

    def x(v):
        return left + (v - lo) / (hi - lo) * plot_w

    out = [f'<svg class="ff" viewBox="0 0 {width} {height}" role="img" aria-label="Valuation football field">']
    # grid + axis
    steps = 5
    for i in range(steps + 1):
        v = lo + (hi - lo) * i / steps
        gx = x(v)
        out.append(f'<line class="grid" x1="{gx:.1f}" y1="{top - 8}" x2="{gx:.1f}" y2="{height - 26}"/>')
        out.append(f'<text class="axis" x="{gx:.1f}" y="{height - 10}" text-anchor="middle">{_fmt(v, cur)}</text>')
    for i, r in enumerate(rows):
        y = top + i * rh
        kind = r.get("kind", "lens")
        out.append(f'<text class="lbl lbl-{kind}" x="{left - 12}" y="{y + 15}" text-anchor="end">{escape(r["label"])}</text>')
        if r.get("sub"):
            out.append(f'<text class="sub" x="{left - 12}" y="{y + 28}" text-anchor="end">{escape(r["sub"])}</text>')
        x0, x1 = x(r["low"]), x(r["high"])
        out.append(f'<rect class="bar bar-{kind}" x="{x0:.1f}" y="{y + 6}" width="{max(x1 - x0, 2):.1f}" height="16" rx="3"/>')
        if r.get("point") is not None:
            out.append(f'<path class="pt pt-{kind}" d="M{x(r["point"]):.1f},{y + 3} l7,11 l-7,11 l-7,-11 z"/>')
        out.append(f'<text class="val" x="{x1 + 8:.1f}" y="{y + 18}" >{_fmt(r["point"] if r.get("point") is not None else r["high"], cur)}</text>')
    # price + target verticals on top
    px = x(price)
    out.append(f'<line class="v-price" x1="{px:.1f}" y1="{top - 10}" x2="{px:.1f}" y2="{height - 26}"/>')
    out.append(f'<text class="v-price-t" x="{px:.1f}" y="{top - 14}" text-anchor="middle">price {_fmt(price, cur)}</text>')
    if target:
        tx = x(target)
        out.append(f'<line class="v-target" x1="{tx:.1f}" y1="{top - 10}" x2="{tx:.1f}" y2="{height - 26}"/>')
        anchor = "start" if tx - px < 60 else "middle"
        shift = 6 if anchor == "start" else 0
        out.append(f'<text class="v-target-t" x="{tx + shift:.1f}" y="{height - 30}" text-anchor="{anchor}">target {_fmt(target, cur)}</text>')
    out.append('</svg>')
    return "".join(out)


# --------------------------------------------------------------------------- #
#  Sensitivity (HTML table, shaded against price)
# --------------------------------------------------------------------------- #
def sensitivity_table(sens: dict, price: float, cur: str = "$") -> str:
    if not sens:
        return ""
    rows = ['<table class="sens"><thead><tr><th>WACC \\ g</th>'
            + "".join(f"<th>{g:.1%}</th>" for g in sens["growths"]) + "</tr></thead><tbody>"]
    mid_r, mid_c = len(sens["waccs"]) // 2, len(sens["growths"]) // 2
    for i, w in enumerate(sens["waccs"]):
        cells = [f"<th>{w:.1%}</th>"]
        for j, v in enumerate(sens["grid"][i]):
            if v is None:
                cells.append('<td class="na">—</td>')
                continue
            ratio = v / price if price else 1
            cls = "up2" if ratio >= 1.25 else "up" if ratio >= 1.05 else "flat" if ratio > 0.95 else \
                "down" if ratio > 0.75 else "down2"
            base = " base" if (i == mid_r and j == mid_c) else ""
            cells.append(f'<td class="{cls}{base}">{_fmt(v, cur)}</td>')
        rows.append("<tr>" + "".join(cells) + "</tr>")
    rows.append("</tbody></table>")
    return "".join(rows)


# --------------------------------------------------------------------------- #
#  Small charts
# --------------------------------------------------------------------------- #
def _scale(v):
    if v >= 1e12:
        return 1e12, "trn"
    if v >= 1e9:
        return 1e9, "bn"
    if v >= 1e6:
        return 1e6, "mn"
    return 1.0, ""


def ev_bridge(pv_explicit, pv_tv, net_debt, minority, equity_value, cur="$", width=520, height=230) -> str:
    sc, unit = _scale(max(abs(pv_explicit + pv_tv), abs(equity_value), 1))
    steps = [("PV explicit FCFF", pv_explicit / sc, "pos"), ("PV terminal", pv_tv / sc, "pos"),
             ("Net debt", -net_debt / sc, "neg")]
    if minority:
        steps.append(("Minorities", -minority / sc, "neg"))
    steps.append(("Equity value", equity_value / sc, "tot"))
    run, tops = 0.0, []
    for lab, v, kind in steps:
        if kind == "tot":
            tops.append((0.0, v)); continue
        a, b = run, run + v
        tops.append((min(a, b), max(a, b)))
        run = b
    ymax = max(t[1] for t in tops) * 1.1 or 1
    ymin = min(0.0, min(t[0] for t in tops))
    left, bottom, top = 10, 44, 18
    ph = height - bottom - top
    bw = (width - left * 2) / len(steps)

    def y(v):
        return top + (ymax - v) / (ymax - ymin) * ph

    out = [f'<svg class="mini" viewBox="0 0 {width} {height}" role="img" aria-label="Enterprise value to equity bridge">']
    for i, ((lab, v, kind), (lo, hi)) in enumerate(zip(steps, tops)):
        bx = left + i * bw + bw * 0.16
        out.append(f'<rect class="b-{kind}" x="{bx:.1f}" y="{y(hi):.1f}" width="{bw * 0.68:.1f}" '
                   f'height="{max(y(lo) - y(hi), 1.5):.1f}" rx="2"/>')
        out.append(f'<text class="val" x="{bx + bw * 0.34:.1f}" y="{y(hi) - 5:.1f}" text-anchor="middle">{cur}{v:,.1f}{unit}</text>')
        out.append(f'<text class="axis" x="{bx + bw * 0.34:.1f}" y="{height - 22}" text-anchor="middle">{escape(lab)}</text>')
    out.append(f'<line class="grid" x1="{left}" y1="{y(0):.1f}" x2="{width - left}" y2="{y(0):.1f}"/>')
    out.append('</svg>')
    return "".join(out)


def projection(years, revenue, fcff, cur="$", width=520, height=230) -> str:
    sc, unit = _scale(max(max(revenue), 1))
    n = len(years)
    ymax = max(max(revenue), max(fcff)) / sc * 1.12
    ymin = min(0.0, min(fcff) / sc * 1.1)
    left, bottom, top = 34, 30, 22
    ph, pw = height - bottom - top, width - left - 8
    gw = pw / n

    def y(v):
        return top + (ymax - v) / (ymax - ymin) * ph

    out = [f'<svg class="mini" viewBox="0 0 {width} {height}" role="img" aria-label="Revenue and FCFF projection">']
    for i in range(5):
        v = ymin + (ymax - ymin) * i / 4
        out.append(f'<line class="grid" x1="{left}" y1="{y(v):.1f}" x2="{width - 8}" y2="{y(v):.1f}"/>')
        out.append(f'<text class="axis" x="{left - 5}" y="{y(v) + 3:.1f}" text-anchor="end">{v:,.0f}</text>')
    for i, (yr, rv, fc) in enumerate(zip(years, revenue, fcff)):
        gx = left + i * gw
        out.append(f'<rect class="b-rev" x="{gx + gw * 0.12:.1f}" y="{y(rv / sc):.1f}" width="{gw * 0.36:.1f}" height="{y(0) - y(rv / sc):.1f}" rx="1.5"/>')
        h = y(0) - y(fc / sc)
        out.append(f'<rect class="b-fcf" x="{gx + gw * 0.52:.1f}" y="{(y(fc / sc) if fc >= 0 else y(0)):.1f}" width="{gw * 0.36:.1f}" height="{abs(h):.1f}" rx="1.5"/>')
        if n <= 12 or i % 2 == 0:
            out.append(f'<text class="axis" x="{gx + gw / 2:.1f}" y="{height - 10}" text-anchor="middle">{str(yr)[-2:]}E</text>')
    out.append(f'<text class="axis" x="{left}" y="12">{cur}{unit}  —  <tspan class="k-rev">■ revenue</tspan>  <tspan class="k-fcf">■ FCFF</tspan></text>')
    out.append('</svg>')
    return "".join(out)


def margin_lines(years_h, margins_h, years_f, margins_f, width=520, height=230) -> str:
    xs_h = list(range(len(years_h)))
    xs_f = list(range(len(years_h), len(years_h) + len(years_f)))
    allm = [m * 100 for m in margins_h + margins_f]
    lo, hi = min(allm + [0]), max(allm) * 1.12 or 1
    left, bottom, top = 34, 30, 22
    ph, pw = height - bottom - top, width - left - 12
    n = len(xs_h) + len(xs_f)

    def px(i):
        return left + (i + 0.5) / n * pw

    def py(v):
        return top + (hi - v) / (hi - lo) * ph

    out = [f'<svg class="mini" viewBox="0 0 {width} {height}" role="img" aria-label="EBIT margin path">']
    for i in range(5):
        v = lo + (hi - lo) * i / 4
        out.append(f'<line class="grid" x1="{left}" y1="{py(v):.1f}" x2="{width - 8}" y2="{py(v):.1f}"/>')
        out.append(f'<text class="axis" x="{left - 5}" y="{py(v) + 3:.1f}" text-anchor="end">{v:.0f}%</text>')
    pts_h = " ".join(f"{px(i):.1f},{py(m * 100):.1f}" for i, m in zip(xs_h, margins_h))
    pts_f = " ".join(f"{px(i):.1f},{py(m * 100):.1f}" for i, m in zip([xs_h[-1]] + xs_f, [margins_h[-1]] + margins_f))
    out.append(f'<polyline class="l-act" points="{pts_h}"/>')
    out.append(f'<polyline class="l-est" points="{pts_f}"/>')
    sep = left + len(xs_h) / n * pw
    out.append(f'<line class="grid sep" x1="{sep:.1f}" y1="{top}" x2="{sep:.1f}" y2="{height - bottom}"/>')
    for i, yr in zip(xs_h, years_h):
        out.append(f'<text class="axis" x="{px(i):.1f}" y="{height - 10}" text-anchor="middle">{str(yr)[-2:]}A</text>')
    for k, (i, yr) in enumerate(zip(xs_f, years_f)):
        if n <= 12 or k % 2 == 0:
            out.append(f'<text class="axis" x="{px(i):.1f}" y="{height - 10}" text-anchor="middle">{str(yr)[-2:]}E</text>')
    out.append(f'<text class="axis" x="{left}" y="12"><tspan class="k-act">● actual</tspan>  <tspan class="k-est">● estimate</tspan></text>')
    out.append('</svg>')
    return "".join(out)


def mini_gauge(total_return: float, rdir: str, rated: bool = True, size: int = 92) -> str:
    """Tiny text-free version of the hero dial, for library cards."""
    out = [f'<svg class="mg" viewBox="0 0 200 200" width="{size}" height="{size}" role="img" '
           f'aria-label="expected return {total_return:+.0%}">']
    c = 100.0
    bands = [(_R_MIN, -0.15, "b-down2"), (-0.15, -0.05, "b-down"), (-0.05, 0.05, "b-flat"),
             (0.05, 0.15, "b-up"), (0.15, _R_MAX, "b-up2")]
    for lo, hi, cls in bands:
        out.append(f'<path class="mgband {cls}" d="{_arc(78, _ang(lo) + 1, _ang(hi) - 1, c, c)}"/>')
    if rated:
        a = _ang(total_return)
        x, y = _pt(70, a, c, c)
        tx, ty = _pt(-12, a, c, c)
        out.append(f'<line class="mghand mghand-{rdir}" x1="{tx:.1f}" y1="{ty:.1f}" x2="{x:.1f}" y2="{y:.1f}"/>')
    out.append(f'<circle class="mghub" cx="{c}" cy="{c}" r="9"/></svg>')
    return "".join(out)
