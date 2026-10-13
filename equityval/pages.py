"""Composes the paged research note: for each page the prose (narrative.py) plus its exhibits.

Exhibits sit in the side column (about 246px wide) or in a full-width band at the foot of the page.
They are numbered in reading order; prose refers to them with `[[ex:key]]` placeholders that this
module resolves (the page script re-numbers if it has to hide one to make a page fit).
"""
from __future__ import annotations

import math
import re
from html import escape
from types import SimpleNamespace as NS

from . import analysis as A
from . import charts, charts_side as cs, clockdata
from . import narrative as N
from .clockdata import PHASE_EN
from .prose import fix_articles, fix_typography, money, ok, pct, ps, spct, xm

SW = 246                      # side-exhibit drawing width (px)


# --------------------------------------------------------------------------- #
#  small building blocks
# --------------------------------------------------------------------------- #
def ex(key, title, html, source=None, opt=False, more=False) -> dict:
    return {"key": key, "title": title, "html": html, "source": source, "opt": opt, "more": more}


def _c(cell):
    """cell -> (text, class)"""
    if isinstance(cell, tuple):
        return cell[0], cell[1]
    return cell, ""


def table(head, rows, cls="", fc_from=None, left_cols=()) -> str:
    """Compact exhibit table. head[0] labels the first column; rows: dicts {label, cells, cls} or
    {sec: title}; cells are str or (str, css-class). Columns >= fc_from are shaded as forecasts."""
    out = [f'<table class="xt {cls}">']
    if head:
        out.append("<thead><tr>" + "".join(
            f'<th class="{"fc" if (fc_from is not None and i >= fc_from) else ""}">{escape(str(h))}</th>' for i, h in enumerate(head)) + "</tr></thead>")
    out.append("<tbody>")
    ncols = (len(head) if head else 1 + max((len(r.get("cells", [])) for r in rows), default=0))
    for r in rows:
        if "sec" in r:
            out.append(f'<tr class="sec"><td colspan="{ncols}">{escape(r["sec"])}</td></tr>')
            continue
        cells = "".join(
            f'<td class="{" ".join(x for x in (_c(c)[1], "fc" if (fc_from is not None and i + 1 >= fc_from) else "", "l" if (i + 1) in left_cols else "") if x)}">{_c(c)[0]}</td>'
            for i, c in enumerate(r["cells"]))
        out.append(f'<tr class="{r.get("cls", "")}"><td>{r["label"]}</td>{cells}</tr>')
    out.append("</tbody></table>")
    return "".join(out)


def kv(rows, cols=2) -> str:
    """Label/value tiles (xk)."""
    return '<div class="xk">' + "".join(f'<div><div class="k">{escape(str(k))}</div><div class="v">{escape(str(v))}</div></div>' for k, v in rows) + "</div>"


def _legend(items) -> str:
    return '<div class="legend">' + "".join(f'<span><i class="{c}"></i>{escape(t)}</span>' for c, t in items) + "</div>"


def _take(text) -> str:
    return f'<p class="take">{text}</p>'


def ft_rows(ft, title_prefix, only=None, skip=None):
    """Rows of one statement section (by title prefix) from the formatted financial table."""
    sec = next((s for s in ft.sections if s.title.lower().startswith(title_prefix.lower())), None)
    if not sec:
        return []
    rows = []
    for r in sec.rows:
        if only and r.label not in only:
            continue
        if skip and r.label in skip:
            continue
        cls = ("sub " if r.sub else "") + ("b" if r.bold else "")
        rows.append({"label": escape(r.label), "cells": [(c["t"], c["cls"]) for c in r.cells], "cls": cls.strip()})
    return rows


def ft_table(ft, title_prefix, only=None, skip=None, cls="wide", hist_only=False) -> str:
    head = [ft.unit_label] + ft.cols
    rows = ft_rows(ft, title_prefix, only, skip)
    if hist_only:
        head = head[:1 + ft.n_hist]
        rows = [dict(r, cells=r["cells"][:ft.n_hist]) for r in rows]
        return table(head, rows, cls=cls)
    return table(head, rows, cls=cls, fc_from=1 + ft.n_hist)


# --------------------------------------------------------------------------- #
#  levers (value per share of the DCF's main dials)
# --------------------------------------------------------------------------- #
def compute_levers(data, dcf, drivers, sens) -> dict:
    out = {}
    if not (dcf and sens and drivers):
        return out
    grid, waccs, gs = sens["grid"], sens["waccs"], sens["growths"]
    ci, cj = len(waccs) // 2, len(gs) // 2
    try:
        base = grid[ci][cj]
        out["wacc_ps"] = abs((grid[ci - 1][cj] - grid[ci + 1][cj]) / 2)
        out["wacc_bps"] = (waccs[1] - waccs[0]) * 1e4
        out["wacc_pct"] = out["wacc_ps"] / base
        out["g_ps"] = abs((grid[ci][cj + 1] - grid[ci][cj - 1]) / 2)
        out["g_bps"] = (gs[1] - gs[0]) * 1e4
    except (TypeError, IndexError, ZeroDivisionError):
        pass
    try:
        import copy
        from .dcf import run_dcf
        d2 = copy.deepcopy(drivers)
        d2.ebit_margin = [m + 0.01 for m in drivers.ebit_margin]
        out["margin_ps"] = abs(run_dcf(data, d2, dcf.wacc).value_per_share - dcf.value_per_share)
    except Exception:
        pass
    return out


def stress_rows(data, dcf, drivers, wacc_res):
    """Single-factor shocks to the DCF: value per share and change against the base case."""
    if not (dcf and drivers):
        return []
    import copy
    from .dcf import run_dcf
    base = dcf.value_per_share
    out = []

    def run(label, wacc=None, mut=None):
        try:
            dr = copy.deepcopy(drivers)
            if mut:
                mut(dr)
            v = run_dcf(data, dr, wacc if wacc is not None else dcf.wacc).value_per_share
            out.append((label, v, (v - base) / abs(base) if base else None))
        except Exception:
            pass

    run("WACC +100bps", dcf.wacc + 0.01)
    run("WACC −100bps", dcf.wacc - 0.01)
    run("Terminal growth −50bps", None, lambda d: setattr(d, "terminal_growth", d.terminal_growth - 0.005))
    run("Terminal growth +50bps", None, lambda d: setattr(d, "terminal_growth", d.terminal_growth + 0.005))
    run("EBIT margin −300bps", None, lambda d: setattr(d, "ebit_margin", [m - 0.03 for m in d.ebit_margin]))
    run("EBIT margin +300bps", None, lambda d: setattr(d, "ebit_margin", [m + 0.03 for m in d.ebit_margin]))
    run("Revenue growth 20% lower", None, lambda d: setattr(d, "revenue_growth", [g * 0.8 for g in d.revenue_growth]))
    run("Revenue growth 20% higher", None, lambda d: setattr(d, "revenue_growth", [g * 1.2 for g in d.revenue_growth]))
    run("Capex +5 points of revenue", None, lambda d: setattr(d, "capex_pct", [c + 0.05 for c in d.capex_pct]))
    return out


def tilt_ranking(clock, probs) -> list:
    """Probability-weighted excess return (pp/yr) for every sector sleeve the Reloj tracks."""
    out = []
    for name in clockdata.ETF_MAP:
        st = (clock["assets"].get(name) or {}).get("phases") or {}
        if not st:
            continue
        t = sum((probs.get(p, 0) or 0) * ((st.get(p) or {}).get("rel_shrunk") or 0) for p in clockdata.PHASES)
        out.append((name, t))
    return sorted(out, key=lambda r: -r[1])


def tilt_bars(rows, mine, width=SW) -> str:
    rh, top, lab_w = 15, 2, 96
    height = top + rh * len(rows) + 10
    m = max(abs(t) for _, t in rows) * 1.2 or 1.0
    x0, x1 = lab_w, width - 6
    cx = x0 + (x1 - x0) / 2
    half = (x1 - x0) / 2 - 18
    out = [f'<svg class="cs" viewBox="0 0 {width} {height}" role="img" aria-label="Tilt by sector">']
    out.append(f'<line class="grid" x1="{cx:.1f}" y1="{top}" x2="{cx:.1f}" y2="{height - 10}"/>')
    for i, (name, t) in enumerate(rows):
        yy = top + i * rh
        mine_ = name in mine
        w = abs(t) / m * half
        bx = cx if t >= 0 else cx - w
        out.append(f'<text class="t" x="4" y="{yy + 10}" style="font-weight:{700 if mine_ else 500};{"fill:var(--accent-ink)" if mine_ else ""}">{escape(clockdata.en(name).replace("Consumer ", "Cons. "))}</text>')
        out.append(f'<rect class="{"wf-up" if t >= 0 else "wf-down"}" x="{bx:.1f}" y="{yy + 3}" width="{max(w, 1):.1f}" height="8" rx="1" style="opacity:{1 if mine_ else .5}"/>')
        tx = (bx + w + 3) if t >= 0 else (bx - 3)
        out.append(f'<text class="v" x="{tx:.1f}" y="{yy + 10}" text-anchor="{"start" if t >= 0 else "end"}">{t:+.1f}</text>')
    out.append(f'<text class="ax" x="{width / 2:.1f}" y="{height - 1}" text-anchor="middle">pp/yr vs US market · weighted by phase probability</text>')
    out.append("</svg>")
    return "".join(out)


def _num(txt):
    m = re.search(r"-?\d+(?:\.\d+)?", str(txt).replace(",", ""))
    return float(m.group()) if m else None


def lens_grid(f):
    """5x5 sensitivity of the lead multiples/book lens: (title, row label, col label, rows, cols, grid)."""
    pel = f.lens_by_key.get("pe_fwd")
    if pel and pel.eff_weight > 0 and f.eps_ntm and f.eps_ntm > 0:
        tm = _num(next((v for k, v in pel.rows if "target p/e" in k.lower()), None))
        if tm:
            fs_ = [-0.2, -0.1, 0.0, 0.1, 0.2]
            grid = [[tm * (1 + a) * f.eps_ntm * (1 + b) for b in fs_] for a in fs_]
            return dict(title="Forward P/E value per share: target multiple × NTM EPS", corner="Multiple \\ EPS", rows=[f"{tm * (1 + a):.1f}x" for a in fs_],
                        cols=[f"{b:+.0%}" if b else "base" for b in fs_], grid=grid, base=(2, 2), kind="pe",
                        d_mult=abs(grid[3][2] - grid[2][2]), d_eps=abs(grid[2][3] - grid[2][2]), lo=grid[0][0], hi=grid[4][4])
    pbl = f.lens_by_key.get("pb_roe")
    if pbl and pbl.eff_weight > 0:
        from . import models as M
        d = f.data
        bv, roe0 = M._bvps(d), M._norm_roe(d)
        for k, v in pbl.rows:
            if "cost of equity" in k.lower():
                ke0 = _num(v) / 100
        g = min(0.03, ke0 - 0.005)
        roes = [roe0 + x for x in (-0.04, -0.02, 0.0, 0.02, 0.04)]
        kes = [ke0 + x for x in (-0.01, -0.005, 0.0, 0.005, 0.01)]
        grid = [[((r_ - g) / (k_ - g)) * bv if k_ > g else None for k_ in kes] for r_ in roes]
        return dict(title="Justified P/B value per share: ROE × cost of equity", corner="ROE \\ Ke", rows=[f"{r_:.1%}" for r_ in roes], cols=[f"{k_:.1%}" for k_ in kes],
                    grid=grid, base=(2, 2), kind="pb", d_mult=abs(grid[3][2] - grid[2][2]), d_eps=abs(grid[2][3] - grid[2][2]), lo=min(x for r_ in grid for x in r_ if x), hi=max(x for r_ in grid for x in r_ if x))
    return None


def heat_table(g, price, cur) -> str:
    out = ['<table class="sens"><thead><tr><th>' + escape(g["corner"]) + "</th>" + "".join(f"<th>{escape(c)}</th>" for c in g["cols"]) + "</tr></thead><tbody>"]
    for i, (rl, row) in enumerate(zip(g["rows"], g["grid"])):
        cells = [f"<th>{escape(rl)}</th>"]
        for j, v in enumerate(row):
            if v is None:
                cells.append('<td class="na">—</td>')
                continue
            ratio = v / price if price else 1
            cls = "up2" if ratio >= 1.25 else "up" if ratio >= 1.05 else "flat" if ratio > 0.95 else "down" if ratio > 0.75 else "down2"
            cells.append(f'<td class="{cls}{" base" if (i, j) == g["base"] else ""}">{charts._fmt(v, cur)}</td>')
        out.append("<tr>" + "".join(cells) + "</tr>")
    out.append("</tbody></table>")
    return "".join(out)


def stack_bar(parts) -> str:
    """parts: [(label, share)] -> a 100% bar with a legend."""
    spans = "".join(f'<span class="s{i + 1}" style="width:{sh * 100:.1f}%"></span>' for i, (_, sh) in enumerate(parts))
    leg = "".join(f'<span><i class="s{i + 1}" style="background:var(--{["refl", "rec", "over", "ink-faint"][i % 4]})"></i>{escape(lab)} {sh:.0%}</span>' for i, (lab, sh) in enumerate(parts))
    return f'<div class="sb">{spans}</div><div class="sbl">{leg}</div>'


# --------------------------------------------------------------------------- #
#  the pages
# --------------------------------------------------------------------------- #
def _groups(blocks):
    groups, cur = [], []
    for blk in blocks:
        if blk.get("t") == "h" and cur:
            groups.append(cur)
            cur = []
        cur.append(blk)
    if cur:
        groups.append(cur)
    return groups


def _page(spec: dict, side=None, band=None, source=None, wide=False) -> NS:
    return NS(groups=_groups(spec["main"]), key=spec["key"], nav=spec.get("nav"), cover=spec.get("cover"), kicker=spec.get("kicker"), title=spec.get("title"),
              sub=spec.get("sub"), main=spec["main"], side=side or [], band=band or [], source=source, wide=wide or spec.get("wide", False),
              cols2=spec.get("cols2", False))


def _short(v) -> str:
    """Compact a lens-input value for the narrow side column: drop the em-dash gloss and long parentheticals."""
    t = str(v).split(" — ")[0].split("  — ")[0]
    t = re.sub(r"\s*\((?=[^)]{15,})[^)]*\)", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _first(v) -> str:
    return str(v).split("—")[0].split("(")[0].strip() if v is not None else "—"


def _lens_row(l, *keys):
    for k, v in (l.rows or []):
        if all(x in k.lower() for x in keys):
            return v
    return None


def _fade_ymax(g: list[float]):
    """Cap the growth chart's axis when the consensus years are spikes far above the rest of the path,
    so the fade itself stays readable (clipped points are labelled on the chart)."""
    ref = max(g[len(g) // 2], 0.04)
    kept = [v for v in g if v <= 4 * ref]
    if kept and len(kept) < len(g):
        return max(kept) * 1.2
    return None


def compose(f) -> list[NS]:
    cx = f.ctx
    d, tr, cur = f.data, f.tr, f.cur
    ft = cx["ft"]
    n_hist = ft.n_hist
    rows_by = {r.label: r for s in cx["ft_raw"].sections for r in s.rows}
    R = lambda name: rows_by[name].values if name in rows_by else []
    labels = ft.cols
    unit = ft.unit_label.replace(cur, "")
    pages: list[NS] = []
    src_model = "Source: SuperAnalyst valuation model."
    src_data = f"Source: {d.provider}; SuperAnalyst."
    src_reloj = "Source: Reloj de inversión (Perez849/reloj-inversion); SuperAnalyst."
    lv = cx.get("levers") or {}
    stress = stress_rows(d, f.dcf, f.drivers, f.wacc_res) if f.has_dcf else []
    cx["stress"] = stress
    grid = lens_grid(f)
    cx["lens_grid"] = grid
    lrows2 = []
    if lv.get("wacc_ps"):
        lrows2 = [{"label": f"WACC ±{lv['wacc_bps']:.0f}bps", "cells": [ps(lv["wacc_ps"], cur), pct(lv["wacc_pct"], 0)]},
                  {"label": f"Terminal growth ±{lv['g_bps']:.0f}bps", "cells": [ps(lv["g_ps"], cur), pct(lv["g_ps"] / f.dcf_vps, 0)]}]
        if lv.get("margin_ps"):
            lrows2.append({"label": "EBIT margin +100bps", "cells": [ps(lv["margin_ps"], cur), pct(lv["margin_ps"] / f.dcf_vps, 0)]})
    stress_ex = None
    if stress:
        stress_ex = table(["Shock to the DCF", "Per share", "vs base"], [{"label": escape(l_), "cells": [ps(v, cur), (spct(c_), "up" if (c_ or 0) >= 0 else "down")]} for l_, v, c_ in stress])

    # ======================= p1 · cover =================================================
    p1 = N.cover(f)
    p1["cover"] = NS(headline=N.headline(f))
    steps = A.target_bridge(tr)
    short = {"Ke carry (12m)": "Cost of equity (12m)", "12M target": "12-month target"}
    steps = [dict(s_, label=short.get(s_["label"], s_["label"])) for s_ in steps]
    side = [
        ex("dial", "12-month expected return and target", cx["clock_svg"], "Bear–bull range from the lens ranges; S marks the Street mean."),
        ex("keydata", "Key data", table(None, [{"label": escape(k), "cells": [v]} for k, v in cx["key_data"]]), src_data),
        ex("bridge", "From price to target", cs.waterfall_h(steps, cur, SW), src_model),
    ]
    band = []
    fs = cx.get("finsum")
    if fs:
        rows = []
        for lab, vals in fs["rows"].items():
            rows.append({"label": ("growth" if lab == "growth" else escape(lab)), "cells": vals, "cls": "sub" if lab == "growth" else ("b" if lab in ("Revenue", "EPS") else "")})
        band = [ex("finsum", "Summary financials and valuation at the current price", table([cur + " per share where noted"] + fs["cols"], rows, cls="wide", fc_from=1 + 2),
                   "Multiples struck at the current price/EV against each year's estimates. Forecast EPS approximates net income as (EBIT − LTM interest) × (1 − t).")]
    pages.append(_page(p1, side, band, source=f"{src_data[:-1]}. Prices and fundamentals as of the report date; analyst consensus. See page 15 for methodology and disclosures."))

    # ======================= p2 · thesis ==================================================
    p2 = N.thesis(f)
    ff_rows = [dict(r, sub={"lens": r.get("sub", "").replace(" weight", ""), "street": "Street", "target": "bear–bull"}[r.get("kind", "lens")]) for r in cx["football_rows"]]
    side = [ex("football", "Value per share by lens", cs.football_stack(ff_rows, d.price, tr.target if tr.rated else None, cur, SW) + _take(cx["ff_take"]), src_model)]
    axes = cx.get("scorecard") or []
    if axes:
        side.append(ex("radar", "Factor scorecard (0–100)", charts.radar(axes, SW, 190, 56) + kv([(a["axis"], a["score"]) for a in axes]), "Heuristic scales, defined in the appendix."))
    if f.street:
        st = f.street
        srows = [{"label": "Street mean target", "cells": [ps(st.mean, cur)]}, {"label": "Upside to Street mean", "cells": [(spct(st.upside), "up" if st.upside >= 0 else "down")]}]
        if st.low and st.high:
            srows.append({"label": "Street range", "cells": [f"{ps(st.low, cur)}–{ps(st.high, cur).replace(cur, '')}"]})
        if st.n:
            srows.append({"label": "Analysts", "cells": [str(st.n)]})
        if st.rec_mean:
            srows.append({"label": "Mean recommendation (1 = buy)", "cells": [f"{st.rec_mean:.1f}"]})
        srows += [{"label": "Our model-only target", "cells": [ps(tr.model_target, cur)]}, {"label": "Divergence vs Street", "cells": [spct(tr.divergence)]},
                  {"label": "Street weight in our target", "cells": [pct(tr.street_weight, 0)]}, {"label": "Published target", "cells": [ps(tr.target, cur)], "cls": "tot"}]
        side.append(ex("street", "Model versus Street", table(None, srows), f"Source: {d.provider}; SuperAnalyst."))
    rr_ = [{"label": "ROIC / WACC", "cells": [f"{pct(f.roic, 1)} / {pct(f.wacc, 1)}"]}, {"label": "ROE", "cells": [pct(f.roe, 1)]},
           {"label": "EBIT margin (latest)", "cells": [pct(f.margin_last, 1)]}, {"label": "Net debt / EBITDA", "cells": ["net cash" if f.net_cash else xm(f.nd_ebitda)]},
           {"label": "FCF yield", "cells": [pct(f.fcf_yield, 1)]}, {"label": "P/E NTM", "cells": [xm(f.pe_ntm)]}, {"label": "EV/EBITDA (LTM)", "cells": [xm(f.ev_ebitda_ltm)]}]
    side.append(ex("ratios", "Key ratios", table(None, rr_), src_data, more=True))
    band = []
    if len(d.price_history) >= 30:
        band = [ex("price", "Five years of price against our 12-month target", charts.price_chart(d.price_history, d.price, tr.target, tr.bear, tr.bull, cur, 690, 170),
                   f"Source: {d.provider}. Weekly closes; shaded cone = bear–bull range for the 12-month target.")]
    pages.append(_page(p2, side, band))

    # ======================= p3 · valuation framework ======================================
    p3 = N.valuation_framework(f)
    lrows = []
    for l in f.lenses:
        wt = f"{l.eff_weight:.0%}" if l.eff_weight > 0 else "—"
        if l.status == "ok" and l.status_note and l.eff_weight > 0:
            wt += "*"
        lrows.append({"label": escape(l.label), "cells": [ps(l.value, cur), f"{ps(l.low, cur)}–{ps(l.high, cur).replace(cur, '')}", wt]})
    lrows.append({"label": "Fair value today", "cells": [ps(f.fv, cur), "", "100%"], "cls": "tot"})
    arith = [{"label": "Fair value today", "cells": [ps(f.fv, cur)]}, {"label": f"× (1 + {pct(f.ke, 2)} cost of equity)", "cells": [ps(f.fv * (1 + f.ke), cur)]}]
    if f.dps:
        arith.append({"label": "− dividends", "cells": ["−" + ps(f.dps, cur)]})
    arith.append({"label": "Model target", "cells": [ps(tr.model_target, cur)], "cls": "b"})
    if tr.street:
        arith.append({"label": f"Street mean ({pct(tr.street_weight, 0)} weight)", "cells": [ps(tr.street.mean, cur)]})
    arith.append({"label": "Published target" if tr.rated else "Indicative value", "cells": [ps(tr.target if tr.rated else f.fv, cur)], "cls": "tot"})
    fam = {}
    for l in f.used:
        fam[l.family] = fam.get(l.family, 0) + l.eff_weight
    famlab = {"relative": "Multiples", "intrinsic": "Cash flow", "sector": "Sector models"}
    side = [ex("lenses", "The lenses, weights and ranges", table(["Lens", "Value", "Range", "Weight"], lrows), src_model + " * = down-weighted by the guardrail."),
            ex("famw", "Weight by family of lens", stack_bar([(famlab[k], v) for k, v in fam.items()]) if fam else "", src_model),
            ex("arith", "From fair value to published target", table(None, arith), src_model)]
    for i, l in enumerate(f.used[:3]):
        side.append(ex(f"lens_{l.key}", f"{l.label}: inputs", table(None, [{"label": escape(k_), "cells": [(escape(_short(v_)), "w")]} for k_, v_ in l.rows[:8]]), src_model, opt=i >= 1))
    if tr.confidence_reasons:
        side.append(ex("conf", f"Confidence: {tr.confidence}", '<ul class="chk">' + "".join(f'<li class="u"><i></i>{escape(r_)}</li>' for r_ in tr.confidence_reasons) + "</ul>",
                       "Grade from lens agreement, dispersion, distance to the Street and data-quality flags.", opt=True))
    pages.append(_page(p3, side))

    # ======================= p4 · relative valuation =======================================
    p4 = N.relative_valuation(f)
    mrows = [{"label": escape(m["metric"]), "cells": [(m["now"], ""), m["ref"], (m["prem"], m["tone"]), m["target"]]} for m in cx["mult_rows"]]
    leg = _legend([("l-bar", "company today"), ("l-ref", "sector reference")] + ([("l-peer", "peer median")] if cx.get("has_peers") else []) + [("l-tgt", "at our target")])
    side = [ex("mults", "Valuation multiples against the sector", cs.multiples_stack(f.mult, SW) + leg, f"Source: {d.provider}; sector reference table; SuperAnalyst."),
            ex("multtbl", "Multiples today, sector reference and at our target", table(["Multiple", "Today", "Sector", "Prem.", "At target"], mrows), src_model)]
    pel, evl = f.lens_by_key.get("pe_fwd"), f.lens_by_key.get("ev_ebitda_fwd")
    if pel or evl:
        def col(l, *k):
            return _first(_lens_row(l, *k)) if l and _lens_row(l, *k) else "—"
        side.append(ex("multbridge", "From sector anchor to target multiple", table(["", "P/E", "EV/EBITDA"], [
            {"label": "Sector / peer anchor", "cells": [col(pel, "anchor"), col(evl, "anchor")]},
            {"label": "× growth", "cells": [col(pel, "growth"), col(evl, "growth")]},
            {"label": "× earnings durability", "cells": [col(pel, "durab"), col(evl, "durab")]},
            {"label": "× leverage", "cells": [col(pel, "leverage"), "—"]},
            {"label": "= Target multiple", "cells": [col(pel, "target"), col(evl, "target")], "cls": "tot"},
            {"label": "Value per share", "cells": [col(pel, "value per"), col(evl, "value per")]}]), src_model))
    if cx.get("peer_rows"):
        prow = [{"label": escape(p_["name"]), "cells": [p_["pe"], p_["ev"], p_["evs"], p_["pb"]], "cls": "tot" if p_["med"] else ""} for p_ in cx["peer_rows"]]
        side.append(ex("peers", "Trading comparables", table(["Peer", "P/E", "EV/EBITDA", "EV/Sales", "P/B"], prow), src_data, more=True))
    ref = f.ref
    side.append(ex("refs", f"Sector reference: {ref.label}", table(None, [{"label": "P/E", "cells": [xm(ref.pe)]}, {"label": "EV/EBITDA", "cells": [xm(ref.ev_ebitda)]}, {"label": "EV/Sales", "cells": [xm(ref.ev_sales)]},
                                                                     {"label": "P/B", "cells": [xm(ref.pb)]}, {"label": "Sector growth", "cells": [pct(ref.growth, 0)]}, {"label": "Sector EBIT margin", "cells": [pct(ref.margin, 0)]}]),
                   "Source: SuperAnalyst sector reference table.", more=True))
    band = []
    if fs:
        mrows2 = [{"label": ("growth" if lab == "growth" else escape(lab)), "cells": vals, "cls": "sub" if lab == "growth" else ""} for lab, vals in fs["rows"].items() if lab in ("EPS", "EV/EBITDA", "P/E", "FCF yield", "FCFF/share")]
        band = [ex("multyr", "Multiples at the current price, by fiscal year", table([cur + " per share where noted"] + fs["cols"], mrows2, cls="wide", fc_from=1 + 2), None)]
    pages.append(_page(p4, side, band))

    # ======================= p5 · scenarios ================================================
    p5 = N.scenarios_page(f)
    sc = cx["scen"]
    srows_ = [{"name": r.name, "p": r.p, "pt": r.pt, "ret": r.ret, "dcf": r.dcf} for r in sc.rows]
    strows = [{"label": r.name, "cells": [f"{r.p:.0%}", ps(r.pt, cur), (spct(r.ret), "up" if r.ret >= 0 else "down")] + ([ps(r.dcf, cur) if r.dcf else "—"] if sc.has_dcf else [])} for r in sc.rows]
    side = [ex("scen", "Bear, base and bull target", charts.scenario_strip(d.price, srows_, cur, SW, 122), src_model),
            ex("scentbl", "Scenario table", table(["Case", "Prob.", "Target", "Return"] + (["DCF"] if sc.has_dcf else []), strows) + _take(cx["scen_take"]), src_model)]
    if cx.get("sens_html"):
        side.append(ex("sens", "DCF value per share: WACC × terminal growth", '<div class="sens-wrap">' + cx["sens_html"] + "</div>", "Shaded against the current price: green above, terracotta below; outlined = base case."))
    if grid:
        side.append(ex("multsens", grid["title"], '<div class="sens-wrap">' + heat_table(grid, d.price, cur) + "</div>", "Shaded against the current price; outlined = base case.", more=f.has_dcf))
    if stress_ex:
        side.append(ex("stress", "Stress tests on the DCF", stress_ex, src_model, opt=True))
    if f.scen:
        arows = []
        for nm_, key_ in (("Bear", "bear"), ("Base", "base"), ("Bull", "bull")):
            r_ = f.scen[key_]
            arows.append({"label": nm_, "cells": [pct(r_.forecast[0].revenue / f.last.revenue - 1, 0), pct(r_.forecast[-1].ebit_margin, 0), ps(r_.value_per_share, cur)]})
        side.append(ex("scenassump", "What the DCF scenarios assume", table(["Case", "Yr-1 growth", "Terminal margin", "Per share"], arows), src_model, more=True))
    pages.append(_page(p5, side))

    # ======================= p6 · growth and margins =======================================
    p6 = N.growth_margins(f)
    side = [ex("combo", "Revenue and EBIT margin", charts.combo_chart(labels, R("Revenue"), R("EBIT margin"), n_hist, "Revenue", "EBIT margin", unit, width=SW, height=178) + _take(cx.get("combo_take", "")), src_data),
            ex("eps", "Diluted EPS, actual and consensus", charts.bars_chart(labels, R("Diluted EPS"), n_hist, "Diluted EPS", cur, width=SW, height=158) + _take(cx.get("eps_take", "")), src_data)]
    yrs_h = [f"FY{y}" for y in f.years[-5:]]
    grow_rows = [{"label": "Revenue growth", "cells": [(spct(g, 0) if ok(g) else "—") for g in f.growth[-5:]]},
                 {"label": "Gross margin", "cells": [pct(m, 0) for m in f.gross_m[-5:]]},
                 {"label": "EBIT margin", "cells": [pct(m, 0) for m in f.ebit_m[-5:]]},
                 {"label": "Net margin", "cells": [pct(m, 0) for m in f.net_m[-5:]]}]
    side.append(ex("gm", "Growth and margin by fiscal year", table([""] + yrs_h, grow_rows), src_data, more=True))
    band = [ex("incstmt", "Income statement", ft_table(ft, "Income"), cx["ft_note"])]
    pages.append(_page(p6, side, band))

    # ======================= p7 · cash flow and balance sheet ===============================
    p7 = N.cash_balance(f)
    side = [ex("cash", "Cash generation", charts.grouped_bars(labels, [("OCF", R("Operating cash flow"), "s-ocf"), ("Capex", R("Capex"), "s-capex"), ("FCF", R("Free cash flow"), "s-fcf")], unit, width=SW, height=170) + _take(cx.get("cf_take", "")), src_data),
            ex("roic", "ROIC and ROE against WACC", charts.line_chart([f"’{str(y_)[-2:]}" for y_ in f.rs["years"]], [("ROIC", f.rs["roic"], "lc-roic"), ("ROE", f.rs["roe"], "lc-roe"), ("WACC", [f.wacc] * len(f.rs["years"]), "lc-wacc")], pct=True, width=SW, height=158) + _take(cx.get("roic_take", "")), "Source: SuperAnalyst; NOPAT = EBIT × (1 − tax).")]
    rr = cx["ret"]
    side.append(ex("returns", "Returns on capital by fiscal year", table([""] + [f"FY{y_}" for y_ in rr.years], [{"label": lab, "cells": vals} for lab, vals in rr.rows]), src_model, more=True))
    band = [ex("bs", "Balance sheet", ft_table(ft, "Balance", cls="wide", hist_only=True), "Reported fiscal years; providers do not forecast the balance sheet."),
            ex("cfs", "Cash flow", ft_table(ft, "Cash", cls="wide", hist_only=True), "Reported fiscal years; forecast free cash flow is shown in the DCF build.")]
    pages.append(_page(p7, side, band))

    # ======================= p8 · quality ===================================================
    p8 = N.quality(f)
    side = []
    pio = cx["pio"]
    if pio.available:
        side.append(ex("pio", f"Piotroski F-score: {pio.score} of {pio.available}", '<ul class="chk">' + "".join(f'<li class="{"y" if ok_ is True else ("n" if ok_ is False else "u")}"><i></i>{escape(l_)}{" (n/a)" if ok_ is None else ""}</li>' for l_, ok_ in pio.items) + "</ul>",
                       "Nine binary tests; green = pass, red = fail, grey = not computable."))
    alt = cx.get("alt")
    if alt:
        side.append(ex("altman", f"Altman Z-score: {alt.z_txt} ({alt.zone})", alt.meter + kv([("Sloan accruals", cx["accr_txt"]), ("OCF / net income", cx["conv_txt"])]), "Original industrial form: > 2.99 safe, 1.81–2.99 grey, < 1.81 distress."))
    wc = cx.get("wc") or {}
    if wc:
        side.append(ex("wc", "Working-capital cycle", kv(list(wc.items())), src_data))
    ci = f.cyc_info
    side.append(ex("durab", "Earnings durability", table(None, [{"label": "Trailing EPS", "cells": [ps(f.fwd.eps_ltm, cur)]}, {"label": f"Consensus EPS FY{f.fy1}", "cells": [ps(f.eps_fy1, cur)]},
                                                                 {"label": f"Consensus EPS FY{f.fy1 + 1}", "cells": [ps(f.eps_fy2, cur)]}, {"label": "NTM EPS used", "cells": [ps(f.eps_ntm, cur)], "cls": "b"},
                                                                 {"label": "Through-cycle EPS", "cells": [ps(ci.norm_eps, cur)]}, {"label": "Forward ÷ through-cycle", "cells": [xm(f.peak_ratio)]},
                                                                 {"label": "Durable EPS growth used", "cells": [pct(f.fwd.growth, 1)]}, {"label": "Durability factor on multiples", "cells": [f"×{f.durab:.2f}"], "cls": "tot"}]), src_model))
    dp = cx.get("dupont")
    if dp:
        side.append(ex("dupont", f"DuPont decomposition, FY{dp.year}", table(None, [{"label": "Net margin", "cells": [dp.nm]}, {"label": "× Asset turnover", "cells": [dp.at]}, {"label": "× Equity multiplier", "cells": [dp.em]}, {"label": "= ROE", "cells": [dp.roe], "cls": "tot"}]), src_model, more=True))
    pages.append(_page(p8, side))

    # ======================= p9/p10 · DCF ===================================================
    if f.has_dcf:
        p9 = N.dcf_assumptions(f)
        w = f.wacc_res
        wrows = [{"label": "Risk-free rate", "cells": [pct(w.risk_free, 2)]}, {"label": "Equity risk premium", "cells": [pct(w.erp, 2)]}, {"label": "Beta used", "cells": [f"{w.beta_used:.2f}"]}]
        if w.country_premium:
            wrows.append({"label": "Country premium", "cells": [pct(w.country_premium, 2)]})
        wrows += [{"label": "Cost of equity", "cells": [pct(w.cost_of_equity, 2)], "cls": "b"}, {"label": "Cost of debt (after tax)", "cells": [pct(w.cost_of_debt_after_tax, 2)]},
                  {"label": "Equity / debt weights", "cells": [f"{w.weight_equity:.0%} / {w.weight_debt:.0%}"]}, {"label": "WACC", "cells": [pct(w.wacc, 2)], "cls": "tot"}]
        fc = f.dcf.forecast
        prev_rev = [f.last.revenue] + [x.revenue for x in fc]
        idx = sorted(set(i for i in [0, 2, 4, len(fc) - 1] if i < len(fc)))
        drows = [{"label": "Revenue growth", "cells": [pct(fc[i].revenue / prev_rev[i] - 1, 0) for i in idx]}, {"label": "EBIT margin", "cells": [pct(fc[i].ebit_margin, 0) for i in idx]},
                 {"label": "Capex / revenue", "cells": [pct(abs(fc[i].capex) / fc[i].revenue, 0) for i in idx]}, {"label": "FCFF margin", "cells": [pct(fc[i].fcff / fc[i].revenue, 0) for i in idx]}]
        yl = [f"’{str(x.year)[-2:]}" for x in fc]
        gser = [fc[i].revenue / prev_rev[i] - 1 for i in range(len(fc))]
        side = [ex("wacc", "Cost of capital build", table(None, wrows) + _take(f"Beta: {w.beta_method}."), src_model),
                ex("drivers", "DCF drivers along the forecast", table([""] + [f"{fc[i].year}E" for i in idx], drows), src_model),
                ex("fade", "Revenue growth: consensus, then fade to terminal", charts.line_chart(yl, [("Revenue growth", gser, "lc-roic")], pct=True, width=SW, height=150, ymax=_fade_ymax(gser)), src_model),
                ex("reinv", "Reinvestment and profitability path", charts.line_chart(yl, [("EBIT margin", [x.ebit_margin for x in fc], "lc-roic"), ("Capex/rev", [abs(x.capex) / x.revenue for x in fc], "lc-roe"),
                                                                                              ("FCFF/rev", [x.fcff / x.revenue for x in fc], "lc-wacc")], pct=True, width=SW, height=150), src_model, opt=True)]
        band = [ex("fcff", f"Free-cash-flow build · {ft.unit_label}", table([""] + [f"{r_['year']}E" for r_ in cx["fcff_rows"]], [{"label": lab, "cells": [r_[key] for r_ in cx["fcff_rows"]], "cls": cls} for lab, key, cls in cx["fcff_lines"]], cls="wide"), src_model)]
        pages.append(_page(p9, side, band))

        p10 = N.dcf_results(f)
        side = [ex("proj", "Revenue and free cash flow to the firm", cx["proj_svg_side"], src_model), ex("margin", "EBIT margin path", cx["margin_svg_side"], src_model), ex("evb", "Enterprise value to equity value", cx["evbridge_svg_side"], src_model)]
        band = [ex("dcfstats", "DCF outputs", kv(cx["dcf_stats"]), src_model)]
        diag = f.diag.get("flags") or []
        if diag:
            band.append(ex("diag", "Model diagnostics", table(["Check", "Reading", "Status"], [{"label": escape(k_), "cells": [v_, (st_, "")]} for k_, v_, st_ in diag]), src_model))
        pages.append(_page(p10, side, band))

    # ======================= p11/p12 · cycle ================================================
    if f.cyc:
        c = f.cyc
        p11 = N.cycle_macro(f)
        trail = c["trail"]
        current = {"phase": c["phase"], "growth": c["growth"], "inflation": c["inflation"], "sigma_g": c["sigma_g"], "sigma_i": c["sigma_i"]}
        side = [ex("plane", "Growth × inflation plane, last 36 months", charts.phase_plane(trail, current, c["probs"], "en", SW, 232), src_reloj),
                ex("probs", "Phase probabilities", charts.prob_bars(c["probs"], c["phase"], "en"), src_reloj),
                ex("cyfacts", "The reading in numbers", kv(cx["cycle"].facts), src_reloj + f" Data: {cx['cycle'].fetched}, {c['asof']}.")]
        pbk = c.get("playbook_all") or {}
        if pbk:
            lead_rows = []
            for ph_ in clockdata.PHASES:
                top3 = sorted(pbk.get(ph_) or [], key=lambda r_: -(r_[1] or 0))[:3]
                lead_rows.append({"label": ("<b>" if ph_ == c["phase"] else "") + PHASE_EN[ph_] + ("</b>" if ph_ == c["phase"] else ""), "cells": [(escape(", ".join(clockdata.en(n_) for n_, _ in top3)), "l")], "cls": ""})
            side.append(ex("leaders", "What the Reloj's playbook leans on, by phase", table(None, lead_rows, left_cols=(1,)), src_reloj))
        pages.append(_page(p11, side, source=src_reloj + " 28 FRED series; robust z-scores and PCA."))
        p12 = N.cycle_sector(f)
        side = []
        if c["stats"]:
            side.append(ex("edge", f"{f.asset_en}: excess return by phase", cs.edge_stack(c["stats"], c["phase"], c["probs"], SW), src_reloj))
            side.append(ex("evidence", f"Historical evidence for {f.asset_en}", table(["Phase", "Ann.", "vs mkt", "t", "Hit", "n"], [{"label": escape(r_.phase), "cells": [r_.ann, (r_.rel, r_.tone), r_.t, r_.hit, str(r_.n)]} for r_ in cx["cycle"].table]),
                           "Ann. = sector annual return in the phase; vs mkt = shrunk excess return (pp); t = Newey-West; n = months."))
        pb = cx["cycle"].playbook
        if pb:
            side.append(ex("playbook", f"The Reloj's playbook now: {PHASE_EN[c['phase']]}", table(["Allocation", "Weight"], [{"label": escape(n_) + (" ◂" if mine else ""), "cells": [w_], "cls": "b" if mine else ""} for n_, w_, mine in pb]), src_reloj + f" Scheme: {cx['cycle'].playbook_label}."))
        clk = cx.get("cycle_raw")
        if clk:
            tr_rows = tilt_ranking(clk, c["probs"])
            if tr_rows:
                side.append(ex("tiltrank", "Probability-weighted tilt, all sectors", tilt_bars(tr_rows, {c["asset"], c["parent"]}), src_reloj + " Highlighted = this company's sector.", opt=True))
        side.append(ex("etf", "ETF exposure", kv(cx["cycle"].etf_facts), src_reloj, more=True))
        pages.append(_page(p12, side, source=src_reloj))

    # ======================= p13 · risks ====================================================
    p13 = N.risks_page(f)
    fac = cx.get("factors") or []
    side = []
    if fac:
        side.append(ex("factors", "Factor exposure", table(["Factor", "Exposure"], [{"label": escape(x["factor"]), "cells": [(f'<span class="tag {"high" if x["level"] == "High" else ("med" if x["level"] == "Medium" else "low")}">{x["level"]}</span>', "")]} for x in fac]), src_model))
    if stress_ex:
        side.append(ex("stress2", "Stress tests on the DCF", stress_ex, src_model))
    if lrows2:
        side.append(ex("levers2", "What each lever is worth (DCF)", table(["Lever", "Per share", "% of DCF"], lrows2), src_model, more=True))
    pages.append(_page(p13, side))

    # ======================= p14/p15 · appendix =============================================
    p14 = N.appendix_statements(f)
    main = [{"t": "ex", **ex("a_inc", "Income statement", ft_table(ft, "Income", cls="wide app"), None)}, {"t": "ex", **ex("a_bs", "Balance sheet", ft_table(ft, "Balance", cls="wide app"), None)},
            {"t": "ex", **ex("a_cf", "Cash flow", ft_table(ft, "Cash", cls="wide app"), cx["ft_note"])}]
    rr2 = cx["ret"]
    main.append({"t": "ex", **ex("a_ret", "Returns on capital by fiscal year", table([""] + [f"FY{y_}" for y_ in rr2.years], [{"label": lab, "cells": vals} for lab, vals in rr2.rows], cls="wide"), src_model, more=True)})
    if fs:
        main.append({"t": "ex", **ex("a_mult", "Multiples at the current price, by fiscal year", table([cur + " per share where noted"] + fs["cols"], [{"label": ("growth" if lab == "growth" else escape(lab)), "cells": vals, "cls": "sub" if lab == "growth" else ""} for lab, vals in fs["rows"].items()], cls="wide", fc_from=1 + 2), None, more=True)})
    main.append({"t": "ex", **ex("a_lens", "Valuation lenses, weights and ranges", table(["Lens", "Value", "Range", "Weight"], lrows, cls="wide"), src_model, more=True)})
    if fac:
        main.append({"t": "ex", **ex("a_fact", "Factor map: evidence and mechanism", table(["Type / factor", "Evidence", "Why it matters"], [{"label": f'<b>{escape(x["factor"])}</b><br><span style="color:var(--ink-faint)">{x["cat"]} · {x["level"]}</span>', "cells": [(escape(x["evidence"]), "l"), (escape(x["why"]), "l")]} for x in fac], left_cols=(1, 2), cls="wide"), src_model, opt=True)})
    p14["main"] = main
    pages.append(_page(p14, wide=True))
    pages.append(_page(N.appendix_method(f)))

    nav = {"p1": "Summary", "p2": "Thesis", "p3": "Valuation", "p6": "Financials", "p9": "DCF", "p11": "Cycle", "p13": "Risks", "p14": "Appendix"}
    for pg in pages:
        pg.nav = nav.get(pg.key)
    _number(pages)
    return pages


def _number(pages):
    """Number exhibits in reading order and resolve [[ex:key]] references."""
    nums, n = {}, 0
    for pg in pages:
        for e in list(pg.side) + [b for b in pg.main if b.get("t") == "ex"] + list(pg.band):
            n += 1
            e["num"] = n
            nums[e["key"]] = n

    pnums = {pg.key: i + 1 for i, pg in enumerate(pages)}

    def sub(text):
        if not isinstance(text, str):
            return text
        text = fix_typography(fix_articles(text))
        text = re.sub(r"\[\[ex:([a-z0-9_]+)\]\]", lambda m: f"Exhibit {nums[m.group(1)]}" if m.group(1) in nums else "the exhibit", text)
        return re.sub(r"\[\[pg:([a-z0-9_]+)\]\]", lambda m: str(pnums[m.group(1)]) if m.group(1) in pnums else "—", text)

    for pg in pages:
        pg.sub = sub(pg.sub)
        pg.groups = _groups(pg.main)
        for blk in pg.main:
            if "html" in blk:
                blk["html"] = sub(blk["html"])
            if "items" in blk and blk["items"] and isinstance(blk["items"][0], str):
                blk["items"] = [sub(i) for i in blk["items"]]
    return nums
