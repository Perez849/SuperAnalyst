"""Facts and phrase helpers for the written part of the research note.

`build_facts` turns the valuation objects into one flat namespace of numbers (raw floats, never
strings) so every page of prose draws from the same figures. Nothing here invents data: a fact
that cannot be computed is None and the sentence that would use it is simply not written.
"""
from __future__ import annotations

import math
import statistics
from types import SimpleNamespace as NS
from typing import Iterable, Optional

from . import analysis as A
from . import clockdata
from .clockdata import PHASE_EN


# --------------------------------------------------------------------------- #
#  formatting (kept local so prose reads the same everywhere)
# --------------------------------------------------------------------------- #
def ok(v) -> bool:
    return isinstance(v, (int, float)) and math.isfinite(v)


def _neg(t: str) -> str:
    """Typographic minus for negative figures (and no negative zero)."""
    import re
    if re.fullmatch(r"-0(\.0+)?(%|x| pp)?", t) or re.fullmatch(r"-0(\.0+)?%?", t.lstrip("+")):
        return t[1:]
    return "\u2212" + t[1:] if t.startswith("-") else t


def money(v, cur="$", dp=2):
    if not ok(v):
        return "n/a"
    a = abs(v)
    body = (f"{cur}{a/1e12:,.{dp}f}trn" if a >= 1e12 else f"{cur}{a/1e9:,.{dp}f}bn" if a >= 1e9
            else f"{cur}{a/1e6:,.0f}mn" if a >= 1e6 else f"{cur}{a:,.0f}")
    return f"\u2212{body}" if v < 0 else body


def ps(v, cur="$"):
    if not ok(v):
        return "n/a"
    return f"\u2212{cur}{abs(v):,.2f}" if v < 0 else f"{cur}{v:,.2f}"


def pct(v, dp=1):
    return "n/a" if not ok(v) else _neg(f"{v*100:.{dp}f}%")


def spct(v, dp=0):
    return "n/a" if not ok(v) else _neg(f"{v*100:+.{dp}f}%")


def xm(v, dp=1):
    return "n/a" if not ok(v) else _neg(f"{v:.{dp}f}x")


def pp(v, dp=1):
    return "n/a" if not ok(v) else _neg(f"{v:+.{dp}f} pp")


_VOWEL_ACRONYMS = ("EBIT", "EBITDA", "ROIC", "ROE", "ROA", "EV", "FCFF", "FCF", "NTM", "LTM", "EPS", "AFFO", "FFO", "SOXX", "SMH", "MSCI", "NOPAT")


def fix_articles(text: str) -> str:
    """'a 11.3%' -> 'an 11.3%', 'a EBIT' -> 'an EBIT' (generated prose only; HTML tags are skipped)."""
    import re

    def num_an(m):
        art, tail = m.group(1), m.group(2)
        digits = re.sub(r"\D", "", re.split(r"[.]", tail)[0].replace(",", ""))
        an = (digits.startswith("8") or (digits[:2] in ("11", "18") and (len(digits) == 2 or len(digits) >= 4)))
        if not an:
            return m.group(0)
        return ("An" if art == "A" else "an") + m.group(0)[1:]

    text = re.sub(r"(?<![/\w])([Aa]) ((?:<[^>]+>)*[\u2212+\-$\u20ac\u00a3]?\d[\d,]*(?:\.\d+)?)", num_an, text)
    acr = "|".join(_VOWEL_ACRONYMS)
    text = re.sub(rf"(?<![/\w])([Aa]) ((?:<[^>]+>)*(?:{acr})\b)", lambda m: ("An" if m.group(1) == "A" else "an") + " " + m.group(2), text)
    return text


def join(items: Iterable[str], last="and") -> str:
    items = [i for i in items if i]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + f" {last} " + items[-1]


def b(s) -> str:
    return f"<b>{s}</b>"


def cap(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s


def num_word(n: int) -> str:
    return {0: "no", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine"}.get(n, str(n))


def growth_word(g) -> str:
    if not ok(g):
        return "uncertain"
    if g >= 0.40:
        return "explosive"
    if g >= 0.20:
        return "rapid"
    if g >= 0.10:
        return "double-digit"
    if g >= 0.04:
        return "mid-single-digit"
    if g >= 0.0:
        return "low-single-digit"
    return "negative"


def margin_word(m) -> str:
    if not ok(m):
        return "n/a"
    if m >= 0.35:
        return "exceptional"
    if m >= 0.22:
        return "high"
    if m >= 0.12:
        return "solid"
    if m >= 0.05:
        return "thin"
    if m >= 0:
        return "razor-thin"
    return "loss-making"


def lev_word(nd_ebitda, net_cash: bool) -> str:
    if net_cash:
        return "net cash"
    if not ok(nd_ebitda):
        return "n/a"
    if nd_ebitda < 0.5:
        return "very low leverage"
    if nd_ebitda < 1.5:
        return "modest leverage"
    if nd_ebitda < 3.0:
        return "moderate leverage"
    return "high leverage"


def series_txt(vals, fmt, sep=" → "):
    vals = [v for v in vals if ok(v)]
    return sep.join(fmt(v) for v in vals)


# --------------------------------------------------------------------------- #
def _lens_rows(l) -> dict:
    return {k: v for k, v in (l.rows or [])}


def _find(rows: dict, *keys):
    for k, v in rows.items():
        kl = k.lower()
        if all(x in kl for x in keys):
            return v
    return None


def build_facts(data, profile, spec, wacc, dcf, scenarios, sens, drivers, diagnostics, reverse, tr, fwd, ref,
                fwd_model, peers, cyc, rating, rdir, ctx) -> NS:
    f = NS()
    cur = data.currency_symbol
    y = data.latest
    ys = data.years
    f.cur, f.name, f.tk, f.sector, f.industry = cur, data.name, data.ticker, data.sector, data.industry
    f.profile, f.spec, f.data, f.tr, f.fwd, f.dcf, f.wacc_res, f.ref = profile, spec, data, tr, fwd, dcf, wacc, ref
    f.drivers, f.diag, f.reverse, f.sens, f.scen, f.peers, f.cyc, f.ctx = drivers, diagnostics or {}, reverse, sens, scenarios, peers or [], cyc, ctx
    f.rating, f.rdir, f.rated = rating, rdir, tr.rated
    f.price, f.pt, f.fv, f.bear, f.bull, f.ke = data.price, tr.target, tr.fair_value, tr.bear, tr.bull, tr.ke
    f.upside, f.ret, f.dps = tr.upside, tr.total_return, tr.dps
    f.yld = (tr.dps / data.price) if data.price else 0.0
    f.fv_gap = (tr.fair_value / data.price - 1) if data.price else None
    f.wacc = wacc.wacc
    f.mcap, f.nd, f.shares = data.market_cap, data.net_debt, data.shares_diluted
    f.ev = data.market_cap + data.net_debt
    f.net_cash = data.net_debt < 0
    f.tax = drivers.tax_rate if drivers else (wacc.tax_rate or 0.22)

    # ---- lenses -----------------------------------------------------------------------------
    f.lenses = list(tr.lenses)
    f.used = sorted([l for l in tr.lenses if l.eff_weight > 0], key=lambda l: -l.eff_weight)
    f.excluded = [l for l in tr.lenses if l.status == "excluded"]
    f.adjusted = [l for l in tr.lenses if l.status in ("winsorized",) or (l.status == "ok" and l.status_note)]
    vals = [l.value for l in f.used]
    f.lens_cv = (statistics.pstdev(vals) / statistics.mean(vals)) if len(vals) > 1 and statistics.mean(vals) else 0.0
    f.lens_lo, f.lens_hi = (min(vals), max(vals)) if vals else (None, None)
    f.lens_by_key = {l.key: l for l in tr.lenses}
    f.street = tr.street

    # ---- history -----------------------------------------------------------------------------
    hist = ys[-6:] if len(ys) >= 6 else ys
    f.years = [h.year for h in hist]
    f.rev = [h.revenue for h in hist]
    f.growth = [None] + [(b_.revenue / a.revenue - 1) if a.revenue else None for a, b_ in zip(hist[:-1], hist[1:])]
    f.ebit = [h.ebit for h in hist]
    f.ebit_m = [h.ebit_margin for h in hist]
    f.ebitda_m = [h.ebitda_margin for h in hist]
    f.ni = [h.net_income for h in hist]
    f.net_m = [(h.net_income / h.revenue) if h.revenue else None for h in hist]
    f.eps = [h.eps_diluted for h in hist]
    f.ocf = [h.operating_cash_flow for h in hist]
    f.capex = [h.capex for h in hist]
    f.fcf = [(h.operating_cash_flow - h.capex) for h in hist]
    f.capex_pct = [(h.capex / h.revenue) if h.revenue else None for h in hist]
    f.da = [h.depreciation_amort for h in hist]
    gp = A.line(data, "gross_profit")
    f.gross_m = [(gp.get(h.year) / h.revenue) if (gp.get(h.year) is not None and h.revenue) else None for h in hist]
    f.last = y
    f.rev_last, f.rev_prev = y.revenue, (ys[-2].revenue if len(ys) >= 2 else None)
    f.g_last = f.growth[-1] if f.growth else None
    f.cagr3 = data.cagr("revenue", 3)
    f.cagr_all = data.cagr("revenue")
    f.span = len(hist) - 1
    gs = [(g, yr) for g, yr in zip(f.growth, f.years) if ok(g) and abs(g) < 20]
    f.best_g = max(gs) if gs else None
    f.worst_g = min(gs) if gs else None
    ms = [(m, yr) for m, yr in zip(f.ebit_m, f.years) if ok(m)]
    f.best_m = max(ms) if ms else None
    f.worst_m = min(ms) if ms else None
    f.margin_last = y.ebit_margin
    f.margin_vol = statistics.pstdev([m for m, _ in ms]) if len(ms) >= 2 else None
    f.ebitda = y.ebitda or (y.ebit + y.depreciation_amort)
    f.nd_ebitda = (data.net_debt / f.ebitda) if f.ebitda and f.ebitda > 0 else None
    f.cover = (y.ebit / y.interest_expense) if y.interest_expense else None
    f.fcf_last = f.fcf[-1] if f.fcf else None
    f.fcf_yield = (f.fcf_last / f.mcap) if (f.fcf_last is not None and f.mcap) else None
    f.cash_conv = (y.operating_cash_flow / y.net_income) if y.net_income and y.net_income > 0 else None
    f.capex_da = (y.capex / y.depreciation_amort) if y.depreciation_amort else None
    f.cash, f.debt, f.equity = y.cash_and_sti, y.total_debt, y.total_equity
    rs = A.returns_series(data, f.tax)
    f.rs = rs
    f.roic = next((v for v in reversed(rs["roic"]) if ok(v)), None)
    f.roe = next((v for v in reversed(rs["roe"]) if ok(v)), None)
    f.roa = next((v for v in reversed(rs["roa"]) if ok(v)), None)
    f.roic_spread = (f.roic - f.wacc) if f.roic is not None else None
    ca, cl = A.line(data, "current_assets"), A.line(data, "current_liab")
    f.current_ratio = (ca.get(y.year) / cl.get(y.year)) if (ca.get(y.year) and cl.get(y.year)) else None
    f.pio, f.alt, f.accr = A.piotroski(data), A.altman_z(data), A.accruals(data)
    f.wc = A.working_capital_days(data) or {}
    f.dupont = A.dupont(data)

    # ---- forward -----------------------------------------------------------------------------
    f.eps_ntm, f.eps_fy1, f.eps_fy2, f.fy1 = fwd.eps_ntm, fwd.eps_fy1, fwd.eps_fy2, fwd.fy1_year
    f.rev_fy1, f.rev_fy2 = fwd.rev_fy1, fwd.rev_fy2
    f.g_fy1 = (fwd.rev_fy1 / y.revenue - 1) if (fwd.rev_fy1 and y.revenue) else None
    f.g_fy2 = (fwd.rev_fy2 / fwd.rev_fy1 - 1) if (fwd.rev_fy2 and fwd.rev_fy1) else None
    f.eps_g = (fwd.eps_fy2 / fwd.eps_fy1 - 1) if (fwd.eps_fy1 and fwd.eps_fy2 and fwd.eps_fy1 > 0) else None
    f.pe_ntm = (data.price / fwd.eps_ntm) if (fwd.eps_ntm and fwd.eps_ntm > 0) else None
    f.pe_ltm = (data.price / y.eps_diluted) if (y.eps_diluted and y.eps_diluted > 0) else None
    f.cyc_info = fwd.cycle
    f.durab = fwd.cycle.durability
    f.peak_ratio = fwd.cycle.peak_ratio
    f.ev_ebitda_ltm = (f.ev / f.ebitda) if f.ebitda and f.ebitda > 0 else None
    f.ev_sales_ltm = (f.ev / y.revenue) if y.revenue else None
    f.pb = (data.price * data.shares_diluted / y.total_equity) if y.total_equity and y.total_equity > 0 else None
    f.mult = A.multiples_table(data, fwd, ref, tr, peers)
    f.mult_by = {m["metric"].split(" ")[0]: m for m in f.mult}

    # ---- DCF ---------------------------------------------------------------------------------
    f.has_dcf = dcf is not None
    if dcf:
        fc = dcf.forecast
        f.dcf_g1 = fc[0].revenue / y.revenue - 1 if y.revenue else None
        f.dcf_m = [x.ebit_margin for x in fc]
        f.dcf_m_peak = max(f.dcf_m)
        f.dcf_m_term = f.dcf_m[-1]
        f.dcf_fcff = [x.fcff for x in fc]
        f.dcf_rev_term = fc[-1].revenue
        f.dcf_tv = dcf.tv_pct_of_ev
        f.dcf_vps = dcf.value_per_share
        f.dcf_horizon = len(fc)
        f.dcf_cagr = (fc[-1].revenue / y.revenue) ** (1 / len(fc)) - 1 if y.revenue and fc[-1].revenue > 0 else None
        f.dcf_bear = scenarios["bear"].value_per_share if scenarios else None
        f.dcf_bull = scenarios["bull"].value_per_share if scenarios else None
        f.exit_mult = f.diag.get("implied_ev_ebitda")
        f.roic_term = f.diag.get("roic_term")
        f.reinvest = f.diag.get("reinvest_rate")
        f.fund_g = f.diag.get("fundamental_g")
        f.anch = drivers.anchors if drivers else {}
        f.sens_lo = min(min(r) for r in sens["grid"]) if sens else None
        f.sens_hi = max(max(r) for r in sens["grid"]) if sens else None
    f.rev_dcf = reverse if (reverse and reverse.get("solved")) else None

    # ---- cycle (Reloj) -----------------------------------------------------------------------
    f.cyc = cyc
    if cyc:
        f.phase, f.phase_en = cyc["phase"], PHASE_EN[cyc["phase"]]
        f.asset_en = clockdata.en(cyc["asset"]) if cyc["asset"] else None
    return f


def fix_typography(text: str) -> str:
    """Typographic minus for negative figures in prose (text nodes only, never inside tags)."""
    import re
    parts = re.split(r"(<[^>]*>)", text)
    for i in range(0, len(parts), 2):
        parts[i] = re.sub(r"(?<![\w/\u2212.])-(?=\d)", "\u2212", parts[i])
    return "".join(parts)


def g_txt(g, dp=0):
    """Growth / margin for prose: absurd magnitudes (tiny bases) are capped instead of printed."""
    if not ok(g):
        return "n/a"
    if g > 5:
        return "above +500%"
    if g < -5:
        return "below \u2212500%"
    return spct(g, dp)
