"""Inline-SVG charts in the Investment Clock style.

Every chart is plain SVG that takes its colours from CSS classes defined by the report
template (themed per screen / print), so they stay crisp at any size, recolour with the
theme and survive PDF export. No image libraries, no base64 blobs.

  valuation_clock()   the hero dial: 12-month expected return, bear-bull arc, Street marker
  football_field()    lens-by-lens value ranges against price, target and Street
  sensitivity_table() WACC x g grid, shaded against the current price (HTML table)
  ev_bridge()         PV explicit + PV terminal - net debt = equity
  projection()        revenue and FCFF bars
  margin_lines()      EBIT margin, actual vs estimate
"""
from __future__ import annotations

import math
from html import escape


CX = CY = 180.0


def _pt(r: float, deg: float, cx: float = CX, cy: float = CY) -> tuple[float, float]:
    a = math.radians(deg)
    return cx + r * math.cos(a), cy + r * math.sin(a)


def _arc(r: float, a0: float, a1: float, cx: float = CX, cy: float = CY) -> str:
    x0, y0 = _pt(r, a0, cx, cy)
    x1, y1 = _pt(r, a1, cx, cy)
    large = 1 if (a1 - a0) % 360 > 180 else 0
    return f"M{x0:.2f},{y0:.2f} A{r:.2f},{r:.2f} 0 {large} 1 {x1:.2f},{y1:.2f}"


def _cs(cur: str, txt: str) -> str:
    """Currency prefix that keeps the minus sign in front of the symbol: -$5.34, not $-5.34."""
    return f"-{cur}{txt[1:]}" if txt.startswith("-") else f"{cur}{txt}"


def _fmt(v: float, cur: str) -> str:
    if v is None or not math.isfinite(v):
        return "—"
    if abs(v) >= 1000:
        return _cs(cur, f"{v:,.0f}")
    if abs(v) >= 100:
        return _cs(cur, f"{v:,.0f}")
    return _cs(cur, f"{v:,.2f}")


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
                    price_txt: str, rated: bool = True, confidence: str = "Medium", view: str = "0 0 360 360") -> str:
    """The signature element: a gauge whose face is a clock."""
    out = [f'<svg class="dial" viewBox="{view}" role="img" aria-label="12-month expected '
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
        out.append(f'<line class="hand" x1="{tx:.1f}" y1="{ty:.1f}" x2="{nx:.1f}" y2="{ny:.1f}"/>')
        out.append(f'<circle class="tip" cx="{nx:.1f}" cy="{ny:.1f}" r="5"/>')
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
    narrow = width < 320
    steps = [("PV FCFF" if narrow else "PV explicit FCFF", pv_explicit / sc, "pos"), ("PV TV" if narrow else "PV terminal", pv_tv / sc, "pos"),
             ("Net debt" if net_debt >= 0 else "Net cash", -net_debt / sc, "neg")]
    if minority:
        steps.append(("Minorities", -minority / sc, "neg"))
    steps.append(("Equity" if narrow else "Equity value", equity_value / sc, "tot"))
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
        out.append(f'<text class="val" x="{bx + bw * 0.34:.1f}" y="{y(hi) - 5:.1f}" text-anchor="middle">{_cs(cur, f"{v:,.1f}")}{unit}</text>')
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
    clamp = lambda m: max(min(m, 1.5), -1.0)
    margins_h = [clamp(m) for m in margins_h]
    margins_f = [clamp(m) for m in margins_f]
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
    thin = width < 320
    for k, (i, yr) in enumerate(zip(xs_h, years_h)):
        if not thin or k % 2 == 1:
            out.append(f'<text class="axis" x="{px(i):.1f}" y="{height - 10}" text-anchor="middle">{str(yr)[-2:]}A</text>')
    for k, (i, yr) in enumerate(zip(xs_f, years_f)):
        if (n <= 12 and not thin) or k % 2 == 0:
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
        out.append(f'<line class="mghand" x1="{tx:.1f}" y1="{ty:.1f}" x2="{x:.1f}" y2="{y:.1f}"/>')
    out.append(f'<circle class="mghub" cx="{c}" cy="{c}" r="9"/></svg>')
    return "".join(out)


# =========================================================================== #
#  Tear-sheet charts (Reloj de inversión visual language)
# =========================================================================== #
def _nice_ticks(lo: float, hi: float, n: int = 4) -> list[float]:
    if hi == lo:
        return [lo]
    raw = (hi - lo) / n
    mag = 10 ** math.floor(math.log10(raw))
    step = min((m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw), default=raw)
    start = math.floor(lo / step) * step
    ticks, v = [], start
    while v <= hi + step * 0.01:
        if v >= lo - step * 0.01:            # never draw a tick label below the plot area
            ticks.append(round(v, 10))
        v += step
    return ticks


def _fmtn(v: float, unit: str = "", dp: int | None = None) -> str:
    if v is None or not math.isfinite(v):
        return "—"
    a = abs(v)
    d = dp if dp is not None else (0 if a >= 100 else 1 if a >= 10 else 2)
    s = f"{v:,.{d}f}"
    return s + unit


def sparkline(values: list, width: int = 84, height: int = 26) -> str:
    vals = [v for v in values if v is not None and math.isfinite(v)]
    if len(vals) < 2:
        return ""
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1.0
    pts = [(2 + i * (width - 4) / (len(vals) - 1), height - 3 - (v - lo) / rng * (height - 6)) for i, v in enumerate(vals)]
    d = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    x, y = pts[-1]
    return (f'<svg class="spark" viewBox="0 0 {width} {height}" width="{width}" height="{height}" aria-hidden="true">'
            f'<polyline points="{d}"/><circle cx="{x:.1f}" cy="{y:.1f}" r="2.4"/></svg>')


def waterfall(steps: list[dict], cur: str = "$", width: int = 440, height: int = 250) -> str:
    """Price -> 12m target bridge. steps: {label, value, kind: total|delta}."""
    run, bars = 0.0, []
    for s in steps:
        if s["kind"] == "total":
            bars.append((0.0, s["value"], s["value"], "total"))
            run = s["value"]
        else:
            a, b = run, run + s["value"]
            bars.append((min(a, b), max(a, b), s["value"], "up" if s["value"] >= 0 else "down"))
            run = b
    ymax = max(b[1] for b in bars) * 1.14
    ymin = 0.0
    left, bottom, top, right = 8, 46, 24, 8
    ph = height - bottom - top
    bw = (width - left - right) / len(bars)

    def y(v):
        return top + (ymax - v) / (ymax - ymin) * ph

    out = [f'<svg class="mini wf" viewBox="0 0 {width} {height}" role="img" aria-label="Price to target bridge">']
    out.append(f'<line class="grid" x1="{left}" y1="{y(0):.1f}" x2="{width - right}" y2="{y(0):.1f}"/>')
    prev_top = None
    for i, ((lo, hi, val, kind), s) in enumerate(zip(bars, steps)):
        bx = left + i * bw + bw * 0.16
        w = bw * 0.68
        out.append(f'<rect class="wf-{kind}" x="{bx:.1f}" y="{y(hi):.1f}" width="{w:.1f}" height="{max(y(lo) - y(hi), 1.5):.1f}" rx="2"/>')
        if prev_top is not None:
            out.append(f'<line class="wf-link" x1="{bx - bw * 0.32 + w:.1f}" y1="{y(prev_top):.1f}" x2="{bx:.1f}" y2="{y(prev_top):.1f}"/>')
        prev_top = hi if (kind in ("total", "up")) else lo
        if kind == "total":
            prev_top = hi
        lab = _fmtn(val, "", None)
        sign = "" if kind == "total" else ("+" if val >= 0 else "−")
        shown = f"{_cs(cur, _fmtn(abs(val)))}" if kind == "total" else f"{sign}{_cs(cur, _fmtn(abs(val)))}"
        out.append(f'<text class="val" x="{bx + w / 2:.1f}" y="{y(hi) - 5:.1f}" text-anchor="middle">{shown}</text>')
        words = s["label"].split(" ")
        mid = (len(words) + 1) // 2
        for j, part in enumerate((" ".join(words[:mid]), " ".join(words[mid:]))):
            if part:
                out.append(f'<text class="axis" x="{bx + w / 2:.1f}" y="{height - 28 + j * 11}" text-anchor="middle">{escape(part)}</text>')
    out.append("</svg>")
    return "".join(out)


def combo_chart(labels: list[str], bars: list, line: list, n_hist: int, bar_name: str, line_name: str,
                bar_unit: str = "", width: int = 520, height: int = 230) -> str:
    """Bars (left axis) with a line (right axis, %). Forecast bars are lighter and dashed."""
    n = len(labels)
    bv = [b if (b is not None and math.isfinite(b)) else 0.0 for b in bars]
    ymax = max(max(bv), 0.001) * 1.15
    ymin = min(0.0, min(bv) * 1.15)
    lv = [v for v in line if v is not None and math.isfinite(v)]
    l_lo = min(lv + [0.0]) * 100 if lv else 0
    l_hi = (max(lv) * 100 * 1.15) if lv else 1
    left, right, bottom, top = 38, 36, 30, 26
    ph, pw = height - bottom - top, width - left - right
    gw = pw / n

    def y(v):
        return top + (ymax - v) / (ymax - ymin) * ph

    def y2(v):
        return top + (l_hi - v) / (l_hi - l_lo) * ph if l_hi != l_lo else top + ph / 2

    out = [f'<svg class="mini" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(bar_name)} and {escape(line_name)}">']
    for t in _nice_ticks(ymin, ymax, 4):
        out.append(f'<line class="grid" x1="{left}" y1="{y(t):.1f}" x2="{width - right}" y2="{y(t):.1f}"/>')
        out.append(f'<text class="axis" x="{left - 5}" y="{y(t) + 3:.1f}" text-anchor="end">{_fmtn(t)}</text>')
    for i, v in enumerate(bars):
        if v is None or not math.isfinite(v):
            continue
        cls = "cb-hist" if i < n_hist else "cb-fc"
        x0 = left + i * gw + gw * 0.18
        top_y, bot_y = y(max(v, 0)), y(min(v, 0))
        out.append(f'<rect class="{cls}" x="{x0:.1f}" y="{top_y:.1f}" width="{gw * 0.64:.1f}" height="{max(bot_y - top_y, 1):.1f}" rx="2"/>')
    pts = [(left + i * gw + gw / 2, y2(v * 100)) for i, v in enumerate(line) if v is not None and math.isfinite(v)]
    if len(pts) > 1:
        out.append('<polyline class="cl-line" points="' + " ".join(f"{x:.1f},{yy:.1f}" for x, yy in pts) + '"/>')
        for x, yy in pts:
            out.append(f'<circle class="cl-dot" cx="{x:.1f}" cy="{yy:.1f}" r="2.6"/>')
    for t in _nice_ticks(l_lo, l_hi, 4):
        out.append(f'<text class="axis ax2" x="{width - right + 5}" y="{y2(t) + 3:.1f}">{t:.0f}%</text>')
    for i, lab in enumerate(labels):
        out.append(f'<text class="axis" x="{left + i * gw + gw / 2:.1f}" y="{height - 10}" text-anchor="middle">{escape(lab.replace("FY", "").replace("20", "’", 1))}</text>')
    sep = left + n_hist * gw
    if 0 < n_hist < n:
        out.append(f'<line class="grid sep" x1="{sep:.1f}" y1="{top - 4}" x2="{sep:.1f}" y2="{height - bottom}"/>')
    out.append(f'<text class="axis" x="{left}" y="13"><tspan class="k-bar">■ {escape(bar_name)}{(" (" + bar_unit + ")") if bar_unit else ""}</tspan>  <tspan class="k-line">● {escape(line_name)}</tspan></text>')
    out.append("</svg>")
    return "".join(out)


def bars_chart(labels: list[str], values: list, n_hist: int, title: str, cur: str = "$", ps: bool = True,
               width: int = 520, height: int = 230, hl: list | None = None) -> str:
    """Simple bars (e.g. EPS) with estimate bars hatched; negative values supported."""
    n = len(labels)
    vv = [v if (v is not None and math.isfinite(v)) else None for v in values]
    nums = [v for v in vv if v is not None] or [0.0]
    ymax = max(max(nums), 0.001) * 1.18
    ymin = min(0.0, min(nums) * 1.18)
    left, right, bottom, top = 38, 8, 30, 26
    ph, pw = height - bottom - top, width - left - right
    gw = pw / n

    def y(v):
        return top + (ymax - v) / (ymax - ymin) * ph

    out = [f'<svg class="mini" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">']
    for t in _nice_ticks(ymin, ymax, 4):
        out.append(f'<line class="grid" x1="{left}" y1="{y(t):.1f}" x2="{width - right}" y2="{y(t):.1f}"/>')
        out.append(f'<text class="axis" x="{left - 5}" y="{y(t) + 3:.1f}" text-anchor="end">{_cs(cur if ps else "", _fmtn(t))}</text>')
    for i, v in enumerate(vv):
        if v is None:
            continue
        cls = ("cb-hist" if i < n_hist else "cb-fc") + (" neg" if v < 0 else "")
        x0 = left + i * gw + gw * 0.2
        out.append(f'<rect class="{cls}" x="{x0:.1f}" y="{y(max(v, 0)):.1f}" width="{gw * 0.6:.1f}" height="{max(y(min(v, 0)) - y(max(v, 0)), 1):.1f}" rx="2"/>')
        ty = y(v) - 5 if v >= 0 else y(v) + 11
        out.append(f'<text class="val" x="{x0 + gw * 0.3:.1f}" y="{ty:.1f}" text-anchor="middle">{_cs(cur if ps else "", _fmtn(v))}</text>')
    for i, lab in enumerate(labels):
        out.append(f'<text class="axis" x="{left + i * gw + gw / 2:.1f}" y="{height - 10}" text-anchor="middle">{escape(lab.replace("FY", "").replace("20", "’", 1))}</text>')
    if 0 < n_hist < n:
        sep = left + n_hist * gw
        out.append(f'<line class="grid sep" x1="{sep:.1f}" y1="{top - 4}" x2="{sep:.1f}" y2="{height - bottom}"/>')
    out.append(f'<text class="axis" x="{left}" y="13">{escape(title)}</text>')
    out.append("</svg>")
    return "".join(out)


def grouped_bars(labels: list[str], series: list[tuple[str, list, str]], unit: str = "", width: int = 520,
                 height: int = 230) -> str:
    """Grouped bars, one group per label. series: [(name, values, css_class)]."""
    n, k = len(labels), len(series)
    nums = [v for _, vals, _ in series for v in vals if v is not None and math.isfinite(v)] or [0.0]
    ymax, ymin = max(max(nums), 0.001) * 1.15, min(0.0, min(nums) * 1.15)
    left, right, bottom, top = 38, 8, 30, 26
    ph, pw = height - bottom - top, width - left - right
    gw = pw / n

    def y(v):
        return top + (ymax - v) / (ymax - ymin) * ph

    out = [f'<svg class="mini" viewBox="0 0 {width} {height}" role="img" aria-label="grouped bars">']
    for t in _nice_ticks(ymin, ymax, 4):
        out.append(f'<line class="grid" x1="{left}" y1="{y(t):.1f}" x2="{width - right}" y2="{y(t):.1f}"/>')
        out.append(f'<text class="axis" x="{left - 5}" y="{y(t) + 3:.1f}" text-anchor="end">{_fmtn(t)}</text>')
    bw = gw * 0.78 / k
    for si, (name, vals, cls) in enumerate(series):
        for i, v in enumerate(vals):
            if v is None or not math.isfinite(v):
                continue
            x0 = left + i * gw + gw * 0.11 + si * bw
            out.append(f'<rect class="{cls}" x="{x0:.1f}" y="{y(max(v, 0)):.1f}" width="{bw * 0.92:.1f}" height="{max(y(min(v, 0)) - y(max(v, 0)), 1):.1f}" rx="1.5"/>')
    for i, lab in enumerate(labels):
        out.append(f'<text class="axis" x="{left + i * gw + gw / 2:.1f}" y="{height - 10}" text-anchor="middle">{escape(lab.replace("FY", "").replace("20", "’", 1))}</text>')
    legend = "  ".join(f'<tspan class="k-{cls}">■ {escape(name)}</tspan>' for name, _, cls in series)
    out.append(f'<text class="axis" x="{left}" y="13">{legend}{("  (" + unit + ")") if unit else ""}</text>')
    out.append("</svg>")
    return "".join(out)


def line_chart(labels: list[str], series: list[tuple[str, list, str]], pct: bool = True, width: int = 520,
               height: int = 230, fill_between: tuple[int, int] | None = None) -> str:
    n = len(labels)
    nums = [v for _, vals, _ in series for v in vals if v is not None and math.isfinite(v)]
    if not nums:
        return ""
    scale = 100 if pct else 1
    lo, hi = min(nums + [0.0]) * scale, max(nums) * scale * 1.15
    left, right, bottom, top = 38, 12, 30, 26
    ph, pw = height - bottom - top, width - left - right

    def x(i):
        return left + (i + 0.5) / n * pw

    def y(v):
        return top + (hi - v * scale) / (hi - lo) * ph

    out = [f'<svg class="mini" viewBox="0 0 {width} {height}" role="img" aria-label="line chart">']
    for t in _nice_ticks(lo, hi, 4):
        yy = top + (hi - t) / (hi - lo) * ph
        out.append(f'<line class="grid" x1="{left}" y1="{yy:.1f}" x2="{width - right}" y2="{yy:.1f}"/>')
        out.append(f'<text class="axis" x="{left - 5}" y="{yy + 3:.1f}" text-anchor="end">{t:.0f}{"%" if pct else ""}</text>')
    if fill_between:
        a, b = series[fill_between[0]][1], series[fill_between[1]][1]
        top_pts = [(x(i), y(a[i])) for i in range(n) if a[i] is not None and b[i] is not None]
        bot_pts = [(x(i), y(b[i])) for i in range(n) if a[i] is not None and b[i] is not None][::-1]
        if len(top_pts) > 1:
            out.append('<polygon class="lc-fill" points="' + " ".join(f"{px:.1f},{py:.1f}" for px, py in top_pts + bot_pts) + '"/>')
    for name, vals, cls in series:
        pts = [(x(i), y(v)) for i, v in enumerate(vals) if v is not None and math.isfinite(v)]
        if len(pts) > 1:
            out.append(f'<polyline class="{cls}" points="' + " ".join(f"{px:.1f},{py:.1f}" for px, py in pts) + '"/>')
        for px, py in pts:
            out.append(f'<circle class="{cls}-dot" cx="{px:.1f}" cy="{py:.1f}" r="2.6"/>')
    for i, lab in enumerate(labels):
        if width >= 320 or n <= 6 or i % 2 == 0:
            out.append(f'<text class="axis" x="{x(i):.1f}" y="{height - 10}" text-anchor="middle">{escape(str(lab))}</text>')
    legend = "  ".join(f'<tspan class="k-{cls}">● {escape(name)}</tspan>' for name, _, cls in series)
    out.append(f'<text class="axis" x="{left}" y="13">{legend}</text></svg>')
    return "".join(out)


def multiples_bullets(rows: list[dict], width: int = 560) -> str:
    """For each multiple: bar = company now, tick = sector reference, diamond = at our target."""
    rows = [r for r in rows if r.get("now") is not None and r["fmt"] != "pct"]
    if not rows:
        return ""
    rh, left, right, top = 40, 132, 104, 8
    height = top + rh * len(rows) + 4
    out = [f'<svg class="bul" viewBox="0 0 {width} {height}" role="img" aria-label="Multiples versus sector reference">']
    for i, r in enumerate(rows):
        yy = top + i * rh
        vals = [v for v in (r["now"], r.get("ref"), r.get("target"), r.get("peer")) if v]
        vmax = max(vals) * 1.15
        pw = width - left - right

        def x(v):
            return left + min(max(v, 0), vmax) / vmax * pw

        tone = ""
        if r.get("prem") is not None:
            cheap = (r["prem"] < -0.05) if r["lower_better"] else (r["prem"] > 0.05)
            rich = (r["prem"] > 0.05) if r["lower_better"] else (r["prem"] < -0.05)
            tone = " b-cheap" if cheap else (" b-rich" if rich else "")
        out.append(f'<text class="lbl" x="{left - 10}" y="{yy + 20}" text-anchor="end">{escape(r["metric"])}</text>')
        out.append(f'<rect class="bul-bg" x="{left}" y="{yy + 10}" width="{pw}" height="14" rx="3"/>')
        out.append(f'<rect class="bul-bar{tone}" x="{left}" y="{yy + 13}" width="{max(x(r["now"]) - left, 1):.1f}" height="8" rx="2"/>')
        if r.get("ref"):
            out.append(f'<line class="bul-ref" x1="{x(r["ref"]):.1f}" y1="{yy + 7}" x2="{x(r["ref"]):.1f}" y2="{yy + 27}"/>')
        if r.get("peer"):
            out.append(f'<circle class="bul-peer" cx="{x(r["peer"]):.1f}" cy="{yy + 17}" r="3.4"/>')
        if r.get("target"):
            xt = x(r["target"])
            out.append(f'<path class="bul-tgt" d="M{xt:.1f},{yy + 9} l5,8 l-5,8 l-5,-8 z"/>')
        txt = f"{r['now']:.1f}x" if r["fmt"] == "x" else f"{r['now']:.2f}x"
        out.append(f'<text class="val" x="{width - right + 8}" y="{yy + 20}">{txt}</text>')
        if r.get("prem") is not None:
            sign = "+" if r["prem"] >= 0 else "−"
            out.append(f'<text class="sub" x="{width - right + 8}" y="{yy + 33}">{sign}{abs(r["prem"]):.0%} vs sector</text>')
    out.append("</svg>")
    return "".join(out)


def scenario_strip(price: float, rows: list[dict], cur: str = "$", width: int = 420, height: int = 130) -> str:
    vals = [price] + [r["pt"] for r in rows]
    lo, hi = min(vals) * 0.9, max(vals) * 1.08
    left, right = 18, 18
    pw = width - left - right

    def x(v):
        return left + (v - lo) / (hi - lo) * pw

    cy = 62
    out = [f'<svg class="mini" viewBox="0 0 {width} {height}" role="img" aria-label="Scenarios">']
    out.append(f'<line class="grid" x1="{left}" y1="{cy}" x2="{width - right}" y2="{cy}"/>')
    bear, base, bull = rows[0]["pt"], rows[1]["pt"], rows[2]["pt"]
    out.append(f'<rect class="sc-range" x="{x(bear):.1f}" y="{cy - 9}" width="{max(x(bull) - x(bear), 2):.1f}" height="18" rx="9"/>')
    names = {"Bear": "sc-bear", "Base": "sc-base", "Bull": "sc-bull"}
    for r in rows:
        out.append(f'<circle class="{names[r["name"]]}" cx="{x(r["pt"]):.1f}" cy="{cy}" r="{6 if r["name"] == "Base" else 5}"/>')
        ly = cy - 20 - (11 if (width < 320 and r["name"] == "Base") else 0)
        out.append(f'<text class="lbl2" x="{x(r["pt"]):.1f}" y="{ly}" text-anchor="middle">{r["name"].upper()} · {int(r["p"] * 100)}%</text>')
        out.append(f'<text class="val" x="{x(r["pt"]):.1f}" y="{cy + 28}" text-anchor="middle">{_cs(cur, _fmtn(r["pt"]))}</text>')
        out.append(f'<text class="sub" x="{x(r["pt"]):.1f}" y="{cy + 41}" text-anchor="middle">{r["ret"]:+.0%}</text>')
    px = x(price)
    out.append(f'<line class="v-price" x1="{px:.1f}" y1="{cy - 36}" x2="{px:.1f}" y2="{cy + 14}"/>')
    out.append(f'<text class="v-price-t" x="{px:.1f}" y="{height - 8}" text-anchor="middle">price {_cs(cur, _fmtn(price))}</text>')
    out.append("</svg>")
    return "".join(out)


# --- the Reloj plane and phase evidence ------------------------------------------------------
_PH = ["Recuperación", "Sobrecalentamiento", "Estanflación", "Reflación"]
_PHC = {"Recuperación": "rec", "Sobrecalentamiento": "over", "Estanflación": "stag", "Reflación": "refl"}


def phase_plane(trail: list, current: dict, probs: dict, lang: str = "en", width: int = 560, height: int = 440) -> str:
    """Growth x inflation plane exactly as in the Reloj: x = growth z, y = inflation z."""
    names = {"Recuperación": "RECUPERACIÓN", "Sobrecalentamiento": "SOBRECALENTAMIENTO",
             "Estanflación": "ESTANFLACIÓN", "Reflación": "REFLACIÓN"} if lang == "es" else \
        {"Recuperación": "RECOVERY", "Sobrecalentamiento": "OVERHEAT", "Estanflación": "STAGFLATION", "Reflación": "REFLATION"}
    padL, padR, padT, padB = 44, 18, 16, 40
    gm = max([2.2] + [abs(p[0]) for p in trail]) * 1.1
    im = max([2.2] + [abs(p[1]) for p in trail]) * 1.1

    def x(g):
        return padL + (g + gm) / (2 * gm) * (width - padL - padR)

    def y(i):
        return (height - padB) - (i + im) / (2 * im) * (height - padT - padB)

    cx, cy = x(0), y(0)
    cur_phase = current.get("phase")
    out = [f'<svg class="plane" viewBox="0 0 {width} {height}" role="img" aria-label="Growth by inflation plane">']
    quads = [("Sobrecalentamiento", cx, width - padR, padT, cy, "end", "top"), ("Recuperación", cx, width - padR, cy, height - padB, "end", "bottom"),
             ("Estanflación", padL, cx, padT, cy, "start", "top"), ("Reflación", padL, cx, cy, height - padB, "start", "bottom")]
    for name, x0, x1, y0, y1, ax, ay in quads:
        out.append(f'<rect class="q q-{_PHC[name]}{" on" if name == cur_phase else ""}" x="{x0:.1f}" y="{y0:.1f}" width="{x1 - x0:.1f}" height="{y1 - y0:.1f}"/>')
    for v in range(-3, 4):
        if v == 0:
            continue
        if abs(v) < gm:
            out.append(f'<line class="grid" x1="{x(v):.1f}" y1="{padT}" x2="{x(v):.1f}" y2="{height - padB}"/>')
        if abs(v) < im:
            out.append(f'<line class="grid" x1="{padL}" y1="{y(v):.1f}" x2="{width - padR}" y2="{y(v):.1f}"/>')
    out.append(f'<line class="axis-l" x1="{padL}" y1="{cy:.1f}" x2="{width - padR}" y2="{cy:.1f}"/><line class="axis-l" x1="{cx:.1f}" y1="{padT}" x2="{cx:.1f}" y2="{height - padB}"/>')
    for name, x0, x1, y0, y1, ax, ay in quads:
        tx = x1 - 10 if ax == "end" else x0 + 10
        ty = y0 + 20 if ay == "top" else y1 - 24
        out.append(f'<text class="ql ql-{_PHC[name]}{" on" if name == cur_phase else ""}" x="{tx:.1f}" y="{ty:.1f}" text-anchor="{ax}">{names[name]}</text>')
        p = probs.get(name)
        if p is not None:
            out.append(f'<text class="qp ql-{_PHC[name]}" x="{tx:.1f}" y="{ty + (14 if ay == "top" else 13):.1f}" text-anchor="{ax}">{p:.0%}</text>')
    if len(trail) > 1:
        out.append('<polyline class="trail" points="' + " ".join(f"{x(g):.1f},{y(i):.1f}" for g, i, *_ in trail) + '"/>')
    for k, (g, i, ph, *_rest) in enumerate(trail):
        rel = (k + 1) / len(trail)
        out.append(f'<circle class="pt-{_PHC.get(ph, "rec")}" cx="{x(g):.1f}" cy="{y(i):.1f}" r="{2.2 + 2.4 * rel:.1f}" opacity="{0.12 + 0.72 * rel:.2f}"/>')
    g, i = current.get("growth", 0), current.get("inflation", 0)
    rx = abs(x(current.get("sigma_g", 0.5)) - x(0)) * 1.96
    ry = abs(y(current.get("sigma_i", 0.3)) - y(0)) * 1.96
    c = _PHC.get(cur_phase, "rec")
    out.append(f'<ellipse class="halo halo-{c}" cx="{x(g):.1f}" cy="{y(i):.1f}" rx="{rx:.1f}" ry="{ry:.1f}"/>')
    out.append(f'<circle class="ring ring-{c}" cx="{x(g):.1f}" cy="{y(i):.1f}" r="8"/><circle class="now now-{c}" cx="{x(g):.1f}" cy="{y(i):.1f}" r="4.2"/>')
    xl = "growth →" if lang != "es" else "crecimiento →"
    xr = "← contraction" if lang != "es" else "← contracción"
    out.append(f'<text class="axis" x="{width - padR}" y="{height - padB + 24}" text-anchor="end">{xl}</text>')
    out.append(f'<text class="axis" x="{padL}" y="{height - padB + 24}" text-anchor="start">{xr}</text>')
    yt = "inflation →" if lang != "es" else "inflación →"
    yb = "← disinflation" if lang != "es" else "← desinflación"
    out.append(f'<text class="axis" transform="rotate(-90 {padL - 28} {padT + 4})" x="{padL - 28}" y="{padT + 4}" text-anchor="end">{yt}</text>')
    out.append(f'<text class="axis" transform="rotate(-90 {padL - 28} {height - padB - 4})" x="{padL - 28}" y="{height - padB - 4}" text-anchor="start">{yb}</text>')
    out.append("</svg>")
    return "".join(out)


REL_EN = {"Sin señal": "no signal", "Débil": "weak", "Moderada": "moderate", "Fuerte": "strong"}


def phase_edge_bars(stats: dict, current: str, probs: dict, lang: str = "en", width: int = 520, height: int = 250) -> str:
    """Excess return of the sector vs the market in each phase (pp/yr), with t-stat labels."""
    rows = []
    for p in _PH:
        s = stats.get(p) or {}
        rows.append((p, s.get("rel_shrunk"), s.get("rel"), s.get("t"), s.get("reliability"), s.get("n")))
    vals = [abs(v) for _, v, r, *_ in rows for v in (v, r) if v is not None]
    vmax = max(vals + [1.0]) * 1.2
    left, right, top, bottom = 118, 70, 22, 8
    rh = (height - top - bottom) / 4
    pw = width - left - right
    zx = left + pw / 2

    def x(v):
        return zx + v / vmax * (pw / 2)

    out = [f'<svg class="mini edge" viewBox="0 0 {width} {height}" role="img" aria-label="Sector excess return by phase">']
    out.append(f'<line class="axis-l" x1="{zx:.1f}" y1="{top - 6}" x2="{zx:.1f}" y2="{height - bottom}"/>')
    out.append(f'<text class="axis" x="{zx:.1f}" y="12" text-anchor="middle">0 pp/yr vs US market</text>')
    en = {"Recuperación": "Recovery", "Sobrecalentamiento": "Overheat", "Estanflación": "Stagflation", "Reflación": "Reflation"}
    for i, (p, shr, raw, t, rel, n) in enumerate(rows):
        yy = top + i * rh
        label = p if lang == "es" else f"{en[p]}"
        cls = "lbl" + (" on" if p == current else "")
        out.append(f'<text class="{cls}" x="{left - 12}" y="{yy + rh / 2 + 1:.1f}" text-anchor="end">{escape(label)}</text>')
        out.append(f'<text class="sub" x="{left - 12}" y="{yy + rh / 2 + 13:.1f}" text-anchor="end">P = {probs.get(p, 0):.0%}</text>')
        if raw is not None:
            out.append(f'<rect class="eb-raw b-{_PHC[p]}" x="{min(x(0), x(raw)):.1f}" y="{yy + 6:.1f}" width="{abs(x(raw) - x(0)):.1f}" height="{rh - 14:.1f}" rx="2"/>')
        if shr is not None:
            out.append(f'<rect class="eb-shr b-{_PHC[p]}" x="{min(x(0), x(shr)):.1f}" y="{yy + 11:.1f}" width="{abs(x(shr) - x(0)):.1f}" height="{rh - 24:.1f}" rx="2"/>')
        v = shr if shr is not None else 0.0
        anchor, tx = ("start", x(max(v, raw or 0)) + 6) if v >= 0 else ("end", x(min(v, raw or 0)) - 6)
        out.append(f'<text class="val" x="{tx:.1f}" y="{yy + rh / 2 + 4:.1f}" text-anchor="{anchor}">{v:+.1f}</text>')
        out.append(f'<text class="sub" x="{width - right + 10}" y="{yy + rh / 2 - 2:.1f}">t {t:+.1f}</text>' if t is not None else "")
        out.append(f'<text class="sub" x="{width - right + 10}" y="{yy + rh / 2 + 10:.1f}">{escape(str(rel or "") if lang == "es" else REL_EN.get(rel, rel or ""))}</text>')
        if p == current:
            out.append(f'<rect class="cur-band" x="2" y="{yy + 1:.1f}" width="{width - 4}" height="{rh - 2:.1f}" rx="4"/>')
    out.append("</svg>")
    return "".join(out)


def prob_bars(probs: dict, current: str, lang: str = "en") -> str:
    en = {"Recuperación": "Recovery", "Sobrecalentamiento": "Overheat", "Estanflación": "Stagflation", "Reflación": "Reflation"}
    out = ['<div class="pbars">']
    for p in _PH:
        v = probs.get(p, 0) or 0
        name = p if lang == "es" else en[p]
        out.append(f'<div class="pb{" on" if p == current else ""}"><span class="nm">{name}</span>'
                   f'<span class="bar"><i class="c-{_PHC[p]}" style="width:{v * 100:.0f}%"></i></span><span class="v">{v:.0%}</span></div>')
    out.append("</div>")
    return "".join(out)


def radar(axes: list[dict], width: int = 400, height: int = 310, R: int = 98) -> str:
    n = len(axes)
    if n < 3:
        return ""
    cx, cy = width / 2, height / 2 + 4
    P = lambda k, r: (cx + r * math.cos(-math.pi / 2 + 2 * math.pi * k / n), cy + r * math.sin(-math.pi / 2 + 2 * math.pi * k / n))
    out = [f'<svg class="radar" viewBox="0 0 {width} {height}" role="img" aria-label="Factor scorecard">']
    for ring in (25, 50, 75, 100):
        out.append('<polygon class="rg" points="' + " ".join("%.1f,%.1f" % P(k, R * ring / 100) for k in range(n)) + '"/>')
    for k, a in enumerate(axes):
        x2, y2 = P(k, R)
        out.append(f'<line class="rg" x1="{cx}" y1="{cy}" x2="{x2:.1f}" y2="{y2:.1f}"/>')
        lx, ly = P(k, R + 16)
        c = math.cos(-math.pi / 2 + 2 * math.pi * k / n)
        anchor = "middle" if abs(c) < 0.3 else ("start" if c > 0 else "end")
        dy = -4 if math.sin(-math.pi / 2 + 2 * math.pi * k / n) < -0.5 else (12 if math.sin(-math.pi / 2 + 2 * math.pi * k / n) > 0.5 else 4)
        out.append(f'<text class="rl" x="{lx:.1f}" y="{ly + dy - 6:.1f}" text-anchor="{anchor}">{escape(a["axis"])}</text>')
        out.append(f'<text class="rv" x="{lx:.1f}" y="{ly + dy + 6:.1f}" text-anchor="{anchor}">{a["score"]}</text>')
    pts = [P(k, R * a["score"] / 100) for k, a in enumerate(axes)]
    out.append('<polygon class="rpoly" points="' + " ".join("%.1f,%.1f" % p for p in pts) + '"/>')
    for x, y in pts:
        out.append(f'<circle class="rdot" cx="{x:.1f}" cy="{y:.1f}" r="3"/>')
    out.append("</svg>")
    return "".join(out)


def price_chart(history: list, price: float, target: float, bear: float, bull: float, cur: str = "$",
                width: int = 760, height: int = 280) -> str:
    """5-year weekly closes with 50/200-week-equivalent averages and the 12m target band."""
    if len(history) < 30:
        return ""
    closes = [c for _, c in history]
    n = len(closes)

    def sma(k):
        out = []
        for i in range(n):
            out.append(sum(closes[i - k + 1:i + 1]) / k if i >= k - 1 else None)
        return out

    s10, s40 = sma(10), sma(40)          # ~50-day and ~200-day on weekly bars
    ext = n // 6                         # room on the right for the forward target band
    lo, hi = min(closes + [bear]) * 0.95, max(closes + [bull]) * 1.05
    left, right, top, bottom = 52, 78, 14, 26
    pw, ph = width - left - right, height - top - bottom

    def x(i):
        return left + i / (n - 1 + ext) * pw

    def y(v):
        return top + (hi - v) / (hi - lo) * ph

    out = [f'<svg class="mini px" viewBox="0 0 {width} {height}" role="img" aria-label="Price history">']
    for t in _nice_ticks(lo, hi, 5):
        out.append(f'<line class="grid" x1="{left}" y1="{y(t):.1f}" x2="{width - right}" y2="{y(t):.1f}"/>')
        out.append(f'<text class="axis" x="{left - 6}" y="{y(t) + 3:.1f}" text-anchor="end">{_cs(cur, _fmtn(t))}</text>')
    out.append('<polyline class="px-line" points="' + " ".join(f"{x(i):.1f},{y(c):.1f}" for i, c in enumerate(closes)) + '"/>')
    for ser, cls in ((s10, "px-s10"), (s40, "px-s40")):
        pts = [(x(i), y(v)) for i, v in enumerate(ser) if v is not None]
        out.append(f'<polyline class="{cls}" points="' + " ".join(f"{a:.1f},{b:.1f}" for a, b in pts) + '"/>')
    xe = x(n - 1 + ext)
    xn = x(n - 1)
    out.append(f'<polygon class="px-cone" points="{xn:.1f},{y(price):.1f} {xe:.1f},{y(bull):.1f} {xe:.1f},{y(bear):.1f}"/>')
    out.append(f'<line class="px-tgt" x1="{xn:.1f}" y1="{y(price):.1f}" x2="{xe:.1f}" y2="{y(target):.1f}"/>')
    for v, lab, cls in ((bull, "bull", "up"), (target, "target", "tg"), (bear, "bear", "down")):
        out.append(f'<text class="val {cls}" x="{xe + 6:.1f}" y="{y(v) + 3:.1f}">{lab} {_cs(cur, _fmtn(v))}</text>')
    yrs = {}
    for i, (d, _) in enumerate(history):
        yrs.setdefault(d[:4], i)
    for yv, i in yrs.items():
        out.append(f'<text class="axis" x="{x(i):.1f}" y="{height - 8}" text-anchor="start">{yv}</text>')
    out.append(f'<text class="axis" x="{left + 4}" y="{top + 11}"><tspan class="k-px">─ weekly close</tspan>  <tspan class="k-s10">─ 10w avg</tspan>  <tspan class="k-s40">─ 40w avg</tspan></text>')
    out.append("</svg>")
    return "".join(out)


def meter(value: float, lo: float, hi: float, bands: list[tuple[float, str]], marker_label: str = "", width: int = 180) -> str:
    """Horizontal meter with colour bands: bands = [(upper_bound, css_class)]."""
    h = 12
    out = [f'<svg class="meter" viewBox="0 0 {width} 30" width="{width}" height="30" aria-hidden="true">']
    prev = lo
    for ub, cls in bands:
        a = (prev - lo) / (hi - lo) * width
        b = (min(ub, hi) - lo) / (hi - lo) * width
        out.append(f'<rect class="m-{cls}" x="{a:.1f}" y="6" width="{max(b - a, 0):.1f}" height="{h}" rx="1"/>')
        prev = ub
    mx = (min(max(value, lo), hi) - lo) / (hi - lo) * width
    out.append(f'<path class="m-mark" d="M{mx:.1f},3 l4,-3 l-8,0 z"/><line class="m-mark" x1="{mx:.1f}" y1="3" x2="{mx:.1f}" y2="24"/>')
    out.append("</svg>")
    return "".join(out)
