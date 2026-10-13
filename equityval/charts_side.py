"""Compact SVG exhibits for the side column of the research note (about 246px wide).

The dashboard charts in charts.py were drawn for wide cards; these are laid out vertically (label
above bar) so they stay legible in a narrow column. Styling comes from the `svg.cs` rules in
design.PAGES.
"""
from __future__ import annotations

import math
from html import escape

from .charts import _cs, _fmtn


def _ok(v) -> bool:
    return isinstance(v, (int, float)) and math.isfinite(v)


def _ps(v, cur):
    return _cs(cur, _fmtn(v)) if _ok(v) else "n/a"


# --------------------------------------------------------------------------- #
def waterfall_h(steps: list[dict], cur: str = "$", width: int = 246) -> str:
    """Price -> target bridge as horizontal bars. steps: {label, value, kind: total|delta}."""
    run, bars = 0.0, []
    for s in steps:
        if s["kind"] == "total":
            bars.append((0.0, s["value"], s["value"], "total"))
            run = s["value"]
        else:
            a, c = run, run + s["value"]
            bars.append((min(a, c), max(a, c), s["value"], "up" if s["value"] >= 0 else "down"))
            run = c
    lab_w, right, rh, top = 98, 46, 19, 3
    height = top + rh * len(bars) + 3
    vmax = max(b[1] for b in bars) * 1.02 or 1.0
    pw = width - lab_w - right

    def x(v):
        return lab_w + max(v, 0) / vmax * pw

    out = [f'<svg class="cs" viewBox="0 0 {width} {height}" role="img" aria-label="Price to target bridge">']
    prev = None
    for i, ((lo, hi, val, kind), s) in enumerate(zip(bars, steps)):
        yy = top + i * rh
        out.append(f'<text class="t" x="{lab_w - 6}" y="{yy + 12.5}" text-anchor="end">{escape(s["label"])}</text>')
        out.append(f'<rect class="track" x="{lab_w}" y="{yy + 4}" width="{pw}" height="10" rx="1"/>')
        cls = {"total": "wf-total", "up": "wf-up", "down": "wf-down"}[kind]
        out.append(f'<rect class="{cls}" x="{x(lo):.1f}" y="{yy + 4}" width="{max(x(hi) - x(lo), 1.6):.1f}" height="10" rx="1"/>')
        sign = "" if kind == "total" else ("+" if val >= 0 else "−")
        out.append(f'<text class="v" x="{x(hi) + 4:.1f}" y="{yy + 12.5}">{sign}{_ps(abs(val), cur)}</text>')
        if prev is not None and kind != "total":
            out.append(f'<line class="lk" x1="{x(prev):.1f}" y1="{yy - 1}" x2="{x(prev):.1f}" y2="{yy + 4}"/>')
        prev = hi if kind in ("total", "up") else lo
    out.append("</svg>")
    return "".join(out)


def football_stack(rows: list[dict], price: float, target, cur: str = "$", width: int = 246) -> str:
    """Football field with the label above each bar. rows: {label, sub, low, high, point, kind}."""
    vals = [price] + [r["low"] for r in rows] + [r["high"] for r in rows] + ([target] if target else [])
    vals = [v for v in vals if _ok(v)]
    lo, hi = min(vals), max(vals)
    pad = (hi - lo) * 0.06 or hi * 0.1
    lo, hi = max(lo - pad, 0.0), hi + pad
    pl, pr, rowh, top, axh = 4, 6, 27, 15, 14
    height = top + rowh * len(rows) + axh
    pw = width - pl - pr

    def x(v):
        return pl + (v - lo) / (hi - lo) * pw

    out = [f'<svg class="cs ff2" viewBox="0 0 {width} {height}" role="img" aria-label="Valuation football field">']
    for i in range(4):
        v = lo + (hi - lo) * i / 3
        gx = x(v)
        out.append(f'<line class="grid" x1="{gx:.1f}" y1="{top - 4}" x2="{gx:.1f}" y2="{height - axh}"/>')
        anchor = "start" if i == 0 else ("end" if i == 3 else "middle")
        out.append(f'<text class="ax" x="{gx:.1f}" y="{height - 3}" text-anchor="{anchor}">{_ps(v, cur)}</text>')
    for i, r in enumerate(rows):
        yy = top + i * rowh
        kind = r.get("kind", "lens")
        out.append(f'<text class="t t-{kind}" x="{pl}" y="{yy + 8}">{escape(r["label"])}</text>')
        val = r["point"] if r.get("point") is not None else r["high"]
        sub = f' · {escape(r["sub"])}' if r.get("sub") else ""
        out.append(f'<text class="v" x="{width - pr}" y="{yy + 8}" text-anchor="end">{_ps(val, cur)}<tspan class="s">{sub}</tspan></text>')
        out.append(f'<rect class="track" x="{pl}" y="{yy + 13}" width="{pw}" height="7" rx="1"/>')
        x0, x1 = x(r["low"]), x(r["high"])
        out.append(f'<rect class="bar-{kind}" x="{x0:.1f}" y="{yy + 12}" width="{max(x1 - x0, 2):.1f}" height="9" rx="1.5"/>')
        if r.get("point") is not None:
            out.append(f'<path class="pt-{kind}" d="M{x(r["point"]):.1f},{yy + 10.5} l4,6 l-4,6 l-4,-6 z"/>')
    px = x(price)
    out.append(f'<line class="v-price" x1="{px:.1f}" y1="{top - 5}" x2="{px:.1f}" y2="{height - axh}"/>')
    out.append(f'<text class="v-price-t" x="{min(max(px, 34), width - 34):.1f}" y="9" text-anchor="middle">price {_ps(price, cur)}</text>')
    if target:
        tx = x(target)
        out.append(f'<line class="v-target" x1="{tx:.1f}" y1="{top - 5}" x2="{tx:.1f}" y2="{height - axh}"/>')
    out.append("</svg>")
    return "".join(out)


def multiples_stack(rows: list[dict], width: int = 246) -> str:
    """Per multiple: bar = company now, tick = sector reference, diamond = at our target."""
    rows = [r for r in rows if r.get("now") is not None and r["fmt"] != "pct"]
    if not rows:
        return ""
    rowh, top = 29, 2
    height = top + rowh * len(rows)
    pl, pr = 4, 6
    pw = width - pl - pr
    out = [f'<svg class="cs" viewBox="0 0 {width} {height}" role="img" aria-label="Multiples versus sector reference">']
    for i, r in enumerate(rows):
        yy = top + i * rowh
        vals = [v for v in (r["now"], r.get("ref"), r.get("target"), r.get("peer")) if v]
        vmax = max(vals) * 1.12

        def x(v):
            return pl + min(max(v, 0), vmax) / vmax * pw

        tone = ""
        if r.get("prem") is not None:
            cheap = (r["prem"] < -0.05) if r["lower_better"] else (r["prem"] > 0.05)
            rich = (r["prem"] > 0.05) if r["lower_better"] else (r["prem"] < -0.05)
            tone = " b-cheap" if cheap else (" b-rich" if rich else "")
        txt = f"{r['now']:.1f}x" if r["fmt"] == "x" else f"{r['now']:.2f}x"
        out.append(f'<text class="t" x="{pl}" y="{yy + 9}">{escape(r["metric"])}</text>')
        sub = (f' <tspan class="s">{"+" if r["prem"] >= 0 else "−"}{abs(r["prem"]):.0%} vs sector</tspan>' if r.get("prem") is not None else "")
        out.append(f'<text class="v" x="{width - pr}" y="{yy + 9}" text-anchor="end">{txt}{sub}</text>')
        out.append(f'<rect class="track" x="{pl}" y="{yy + 14}" width="{pw}" height="9" rx="1"/>')
        out.append(f'<rect class="bul-bar{tone}" x="{pl}" y="{yy + 15.5}" width="{max(x(r["now"]) - pl, 1):.1f}" height="6" rx="1"/>')
        if r.get("ref"):
            out.append(f'<line class="bul-ref" x1="{x(r["ref"]):.1f}" y1="{yy + 12}" x2="{x(r["ref"]):.1f}" y2="{yy + 25}"/>')
        if r.get("peer"):
            out.append(f'<circle class="bul-peer" cx="{x(r["peer"]):.1f}" cy="{yy + 18.5}" r="2.6"/>')
        if r.get("target"):
            xt = x(r["target"])
            out.append(f'<path class="bul-tgt" d="M{xt:.1f},{yy + 13.5} l3.6,5 l-3.6,5 l-3.6,-5 z"/>')
    out.append("</svg>")
    return "".join(out)


_PH_EN = {"Recuperación": "Recovery", "Sobrecalentamiento": "Overheat", "Estanflación": "Stagflation", "Reflación": "Reflation"}
_PH_ORDER = ["Recuperación", "Sobrecalentamiento", "Estanflación", "Reflación"]
_PH_CLS = {"Recuperación": "rec", "Sobrecalentamiento": "over", "Estanflación": "stag", "Reflación": "refl"}
_REL_EN = {"Sin señal": "no signal", "Débil": "weak", "Moderada": "moderate", "Fuerte": "strong"}


def edge_stack(stats: dict, current: str, probs: dict, width: int = 246) -> str:
    """Excess return vs the US market by phase: pale = raw, solid = shrunk estimate."""
    raw = [(stats.get(p) or {}).get("rel") for p in _PH_ORDER]
    shr = [(stats.get(p) or {}).get("rel_shrunk") for p in _PH_ORDER]
    allv = [abs(v) for v in raw + shr if _ok(v)] or [1.0]
    m = max(allv) * 1.15
    rowh, top, pl, pr = 30, 2, 4, 6
    height = top + rowh * 4 + 12
    cx = pl + (width - pl - pr) / 2
    half = (width - pl - pr) / 2 - 22

    def x(v):
        return cx + v / m * half

    out = [f'<svg class="cs" viewBox="0 0 {width} {height}" role="img" aria-label="Sector excess return by phase">']
    for i, p in enumerate(_PH_ORDER):
        yy = top + i * rowh
        st = stats.get(p) or {}
        cls = _PH_CLS[p]
        if p == current:
            out.append(f'<rect class="cur" x="{pl - 2}" y="{yy}" width="{width - pl - pr + 4}" height="{rowh - 2}" rx="2"/>')
        rel, rs_ = st.get("rel"), st.get("rel_shrunk")
        rel_txt = _REL_EN.get(st.get("reliability"), st.get("reliability") or "n/a")
        out.append(f'<text class="t" x="{pl + 2}" y="{yy + 9}">{_PH_EN[p]}<tspan class="s"> · P {probs.get(p, 0):.0%}</tspan></text>')
        tt = f"t {st['t']:+.1f}" if _ok(st.get("t")) else "t n/a"
        out.append(f'<text class="s" x="{width - pr - 2}" y="{yy + 9}" text-anchor="end">{tt} · {rel_txt}</text>')
        out.append(f'<line class="grid" x1="{cx:.1f}" y1="{yy + 12}" x2="{cx:.1f}" y2="{yy + 25}"/>')
        if _ok(rel):
            out.append(f'<rect class="ph-raw ph-{cls}" x="{min(x(0), x(rel)):.1f}" y="{yy + 12}" width="{abs(x(rel) - x(0)):.1f}" height="12" rx="1"/>')
        if _ok(rs_):
            out.append(f'<rect class="ph-shr ph-{cls}" x="{min(x(0), x(rs_)):.1f}" y="{yy + 15}" width="{max(abs(x(rs_) - x(0)), 1):.1f}" height="6" rx="1"/>')
            side = x(rs_) + 3 if rs_ >= 0 else x(rs_) - 3
            out.append(f'<text class="v" x="{side:.1f}" y="{yy + 21.5}" text-anchor="{"start" if rs_ >= 0 else "end"}">{rs_:+.1f}</text>')
    out.append(f'<text class="ax" x="{cx:.1f}" y="{height - 2}" text-anchor="middle">pp/yr vs US market · solid = shrunk, pale = raw</text>')
    out.append("</svg>")
    return "".join(out)
