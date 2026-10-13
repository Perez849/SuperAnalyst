"""Valuation lenses.

A *lens* is one independent way of answering "what is a share worth?", returned as a
value per share, a low/high range and a full audit trail. The triangulation step
(triangulate.py) weights the lenses a profile calls for; no single lens is ever the
answer. The lenses mirror how a sell-side desk actually builds a target:

  relative    target multiple x forward earnings / EBITDA / sales / book
              (peer-anchored, then adjusted for growth, leverage and earnings durability)
  intrinsic   10-year FCFF DCF with decaying growth and mean-reverting margins
  sector      residual income, justified P/B, FFO/AFFO, dividends, mid-cycle EBITDA
              (the models in models.py, wrapped so they share the same shape)
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from typing import Optional

from .estimates import Forward
from .models import MethodResult
from .reference import SectorRef
from .schema import CompanyData, PeerData


@dataclass
class Lens:
    key: str
    label: str
    family: str                     # 'relative' | 'intrinsic' | 'sector'
    value: float                    # fair value per share, today
    low: float
    high: float
    rows: list[tuple] = field(default_factory=list)
    note: str = ""
    weight: float = 0.0             # base profile weight (set by the triangulator)
    status: str = "ok"              # 'ok' | 'winsorized' | 'excluded'
    status_note: str = ""
    eff_weight: float = 0.0         # final normalised weight after guardrails


def _fin(x) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(x)


def _bn(v: float, cur: str) -> str:
    """$1.23bn / ($1.23bn) -- negatives in parentheses, never '$-1.23bn'."""
    body = f"{cur}{abs(v)/1e9:,.2f}bn"
    return f"({body})" if v < 0 else body


def _net_debt_row(data) -> tuple:
    nd = data.net_debt
    return (("\u2212 Net debt" if nd >= 0 else "+ Net cash"), _bn(abs(nd), data.currency_symbol))


# --------------------------------------------------------------------------- #
#  Multiple anchoring
# --------------------------------------------------------------------------- #
_RANGES = {"pe": (3.0, 90.0), "ev_ebitda": (2.0, 70.0), "ev_sales": (0.15, 60.0), "pb": (0.2, 40.0)}


def _peer_stat(peers: list[PeerData], kind: str) -> tuple[Optional[float], int]:
    lo, hi = _RANGES[kind]
    getter = {"pe": lambda p: p.fwd_pe or p.pe, "ev_ebitda": lambda p: p.ev_ebitda,
              "ev_sales": lambda p: p.ev_sales, "pb": lambda p: p.pb}[kind]
    vals = []
    for p in peers or []:
        try:
            v = getter(p)
        except Exception:
            v = None
        if _fin(v) and lo <= v <= hi:
            vals.append(v)
    if len(vals) < 3:
        return None, len(vals)
    return statistics.median(vals), len(vals)


def anchor_multiple(kind: str, ref: SectorRef, peers: list[PeerData]) -> tuple[float, str]:
    """Peer median blended 60/40 with the sector reference (stability vs freshness)."""
    base = {"pe": ref.pe, "ev_ebitda": ref.ev_ebitda, "ev_sales": ref.ev_sales, "pb": ref.pb}[kind]
    med, n = _peer_stat(peers, kind)
    if med is None:
        return base, f"{ref.label or 'sector'} reference {base:.1f}x (no usable peer set)"
    blend = 0.6 * med + 0.4 * base
    return blend, (f"60% peer median {med:.1f}x (n={n}) + 40% {ref.label or 'sector'} "
                   f"reference {base:.1f}x")


def growth_adjustment(growth: float, ref: SectorRef, k: float = 0.35) -> float:
    """PEG-style premium/discount for durable growth above/below the sector's."""
    adj = 1.0 + k * (growth - ref.growth) / max(ref.growth, 0.05)
    return min(max(adj, 0.80), 1.35)


def leverage_adjustment(data: CompanyData) -> float:
    y = data.latest
    ebitda = y.ebitda or (y.ebit + y.depreciation_amort)
    if not ebitda or ebitda <= 0:
        return 1.0
    lev = data.net_debt / ebitda
    if lev > 4.5:
        return 0.85
    if lev > 3.0:
        return 0.92
    return 1.0


def _tax(data: CompanyData) -> float:
    eff = [y.effective_tax_rate for y in data.years if y.effective_tax_rate is not None]
    eff = [e for e in eff if 0 <= e <= 0.6]
    t = sum(eff) / len(eff) if eff else 0.22
    return min(max(t, 0.10), 0.35)


# --------------------------------------------------------------------------- #
#  Relative lenses
# --------------------------------------------------------------------------- #
def pe_forward(data: CompanyData, ref: SectorRef, fwd: Forward,
               peers: list[PeerData]) -> Optional[Lens]:
    if not fwd.eps_ntm or fwd.eps_ntm <= 0:
        return None
    anchor, anchor_src = anchor_multiple("pe", ref, peers)
    g_adj = growth_adjustment(fwd.growth, ref)
    lev = leverage_adjustment(data)
    dur = fwd.cycle.durability
    mult = anchor * g_adj * lev * dur
    value = mult * fwd.eps_ntm
    cur = data.currency_symbol
    eps_txt = (f"{cur}{fwd.eps_fy1:,.2f} (FY{fwd.fy1_year})" + (f" / {cur}{fwd.eps_fy2:,.2f} (FY{fwd.fy1_year + 1})"
               if fwd.eps_fy2 else ""))
    rows = [
        ("Consensus EPS", eps_txt),
        ("NTM EPS (blend of the two years)" if fwd.eps_fy2 else "Forward EPS", f"{cur}{fwd.eps_ntm:,.2f}"),
        ("Anchor P/E", f"{anchor:.1f}x  — {anchor_src}"),
        ("Growth adjustment", f"×{g_adj:.2f}  ({fwd.growth:.1%} durable growth vs {ref.growth:.1%} sector)"),
        ("Earnings-durability factor", f"×{dur:.2f}" + ("" if dur >= 0.999 else "  (forward EPS far above through-cycle)")),
        ("Leverage adjustment", f"×{lev:.2f}"),
        ("Target P/E", f"{mult:.1f}x"),
        ("Value per share", f"{cur}{value:,.2f}"),
    ]
    return Lens("pe_fwd", "Forward P/E", "relative", value, value * 0.82, value * 1.18, rows,
                note=("Target multiple x NTM EPS. The multiple is anchored on peers/sector, "
                      "then scaled for durable growth, leverage and how far forward earnings "
                      "sit above what the business has historically earned."))


def _ebitda_ntm(data: CompanyData, fwd: Forward) -> Optional[float]:
    y = data.latest
    da_last = max(y.depreciation_amort, 0.0)
    if fwd.ni_ntm and fwd.ni_ntm > 0:
        t = _tax(data)
        ebit = fwd.ni_ntm / (1 - t) + y.interest_expense
        da = da_last
        if fwd.rev_ntm and y.revenue and y.revenue > 0:
            da = min(da_last * fwd.rev_ntm / y.revenue, 2.0 * da_last) if da_last else 0.0
        return ebit + da
    base = y.ebitda or (y.ebit + y.depreciation_amort)
    if base and base > 0 and fwd.rev_ntm and y.revenue:
        return base * fwd.rev_ntm / y.revenue
    return base if base and base > 0 else None


def ev_ebitda_forward(data: CompanyData, ref: SectorRef, fwd: Forward,
                      peers: list[PeerData]) -> Optional[Lens]:
    ebitda = _ebitda_ntm(data, fwd)
    if not ebitda or ebitda <= 0:
        return None
    anchor, anchor_src = anchor_multiple("ev_ebitda", ref, peers)
    g_adj = growth_adjustment(fwd.growth, ref)
    dur = fwd.cycle.durability
    mult = anchor * g_adj * dur
    ev = mult * ebitda
    y = data.latest
    equity = ev - data.net_debt - (y.minority_interest or 0.0)
    if equity <= 0 or not data.shares_diluted:
        return None
    value = equity / data.shares_diluted
    cur = data.currency_symbol
    rows = [
        ("NTM EBITDA (from consensus earnings)", f"{cur}{ebitda/1e9:,.2f}bn"),
        ("Anchor EV/EBITDA", f"{anchor:.1f}x  — {anchor_src}"),
        ("Growth adjustment", f"×{g_adj:.2f}"),
        ("Earnings-durability factor", f"×{dur:.2f}"),
        ("Target EV/EBITDA", f"{mult:.1f}x"),
        ("Enterprise value", f"{cur}{ev/1e9:,.2f}bn"),
        ("− Net debt", f"{cur}{data.net_debt/1e9:,.2f}bn"),
        ("Value per share", f"{cur}{value:,.2f}"),
    ]
    lo_eq = (ev * 0.82 - data.net_debt - (y.minority_interest or 0)) / data.shares_diluted
    hi_eq = (ev * 1.18 - data.net_debt - (y.minority_interest or 0)) / data.shares_diluted
    return Lens("ev_ebitda_fwd", "Forward EV/EBITDA", "relative", value, max(lo_eq, 0.0), hi_eq, rows,
                note="Capital-structure-neutral cross-check to forward P/E: it values the operating "
                     "business and then bridges to equity through net debt.")


def ev_sales_forward(data: CompanyData, ref: SectorRef, fwd: Forward,
                     peers: list[PeerData]) -> Optional[Lens]:
    if not fwd.rev_ntm or fwd.rev_ntm <= 0 or not data.shares_diluted:
        return None
    y = data.latest
    g_rev = fwd.rev_ntm / y.revenue - 1 if y.revenue else 0.0
    g_rev = min(max(g_rev, -0.30), 0.60)
    anchor, anchor_src = anchor_multiple("ev_sales", ref, peers)
    g_f = min(max(1.0 + 2.0 * (g_rev - ref.growth), 0.5), 2.5)
    m_f = 0.70 if (y.ebit_margin is not None and y.ebit_margin < 0) else 1.0
    dur = fwd.cycle.durability
    mult = anchor * g_f * m_f * dur
    ev = mult * fwd.rev_ntm
    equity = ev - data.net_debt - (y.minority_interest or 0.0)
    if equity <= 0:
        return None
    value = equity / data.shares_diluted
    cur = data.currency_symbol
    rows = [
        ("NTM revenue", f"{cur}{fwd.rev_ntm/1e9:,.2f}bn  ({g_rev:+.0%} vs last year)"),
        ("Anchor EV/Sales", f"{anchor:.1f}x  — {anchor_src}"),
        ("Growth factor", f"×{g_f:.2f}"),
        ("Profitability factor", f"×{m_f:.2f}" + ("  (loss-making)" if m_f < 1 else "")),
        ("Target EV/Sales", f"{mult:.1f}x"),
        ("Value per share", f"{cur}{value:,.2f}"),
    ]
    lo = max((ev * 0.75 - data.net_debt - (y.minority_interest or 0)) / data.shares_diluted, 0.0)
    hi = (ev * 1.30 - data.net_debt - (y.minority_interest or 0)) / data.shares_diluted
    return Lens("ev_sales_fwd", "Forward EV/Sales", "relative", value, lo, hi, rows,
                note="For companies where earnings do not yet measure value: a sales multiple sized "
                     "to growth and (lack of) profitability.")


def pb_book(data: CompanyData, ref: SectorRef, fwd: Forward, ke: float,
            peers: list[PeerData]) -> Optional[Lens]:
    y = data.latest
    bv = (y.total_equity - (y.minority_interest or 0)) / data.shares_diluted if data.shares_diluted else 0
    if bv <= 0:
        return None
    anchor, anchor_src = anchor_multiple("pb", ref, peers)
    roe = y.net_income / y.total_equity if y.total_equity > 0 else 0.0
    f = 0.60 if roe < 0 else min(max(roe / max(ke, 0.05), 0.60), 1.60)
    mult = anchor * f
    value = bv * mult
    cur = data.currency_symbol
    rows = [
        ("Book value / share", f"{cur}{bv:,.2f}"),
        ("Anchor P/B", f"{anchor:.1f}x  — {anchor_src}"),
        ("Returns factor (ROE / Ke)", f"×{f:.2f}  (ROE {roe:.1%})"),
        ("Target P/B", f"{mult:.2f}x"),
        ("Value per share", f"{cur}{value:,.2f}"),
    ]
    return Lens("pb_book", "Price / Book", "relative", value, value * 0.75, value * 1.30, rows,
                note="Asset-based anchor for loss-making or early-stage companies: book value times "
                     "a multiple scaled by returns on equity relative to the cost of equity.")


# --------------------------------------------------------------------------- #
#  Intrinsic lens
# --------------------------------------------------------------------------- #
def dcf_lens(scenarios: dict, data: CompanyData) -> Optional[Lens]:
    if not scenarios:
        return None
    base, bear, bull = scenarios["base"], scenarios["bear"], scenarios["bull"]
    if not _fin(base.value_per_share) or base.value_per_share <= 0:
        return None
    if sum(f.ebit for f in base.forecast) <= 0:
        return None
    cur = data.currency_symbol
    rows = [
        ("WACC", f"{base.wacc:.2%}"),
        ("Terminal growth", f"{base.terminal_growth:.2%}"),
        ("PV of explicit FCFF", f"{cur}{base.pv_explicit/1e9:,.2f}bn"),
        ("PV of terminal value", f"{cur}{base.pv_tv/1e9:,.2f}bn  ({base.tv_pct_of_ev:.0%} of EV)"),
        ("Enterprise value", f"{cur}{base.enterprise_value/1e9:,.2f}bn"),
        ("− Net debt & minorities", f"{cur}{(base.net_debt + base.minority)/1e9:,.2f}bn"),
        ("Equity value", f"{cur}{base.equity_value/1e9:,.2f}bn"),
        ("Value per share", f"{cur}{base.value_per_share:,.2f}"),
    ]
    lo = max(min(bear.value_per_share, base.value_per_share), 0.0)
    hi = max(bull.value_per_share, base.value_per_share)
    note = ("10-year FCFF DCF: consensus for the near years, geometric growth decay, mean-reverting "
            "margins, terminal reinvestment tied to growth/ROIC. Range = bear/bull scenarios.")
    if base.tv_pct_of_ev > 0.80:
        note += f" Terminal value is {base.tv_pct_of_ev:.0%} of EV — treat as less reliable."
    return Lens("dcf", "Discounted cash flow (FCFF)", "intrinsic", base.value_per_share, lo, hi,
                rows, note=note)


# --------------------------------------------------------------------------- #
#  Sector lenses (wrap models.py results into the common shape)
# --------------------------------------------------------------------------- #
_SPREAD = {"ddm": 0.20, "residual_income": 0.18, "pb_roe": 0.20, "ffo_multiple": 0.18,
           "affo_yield": 0.20, "normalized": 0.22}


def from_method(m: MethodResult, family: str = "sector") -> Optional[Lens]:
    if m is None or not _fin(m.value_per_share) or m.value_per_share <= 0:
        return None
    s = _SPREAD.get(m.key, 0.20)
    return Lens(m.key, m.label, family, m.value_per_share, m.value_per_share * (1 - s),
                m.value_per_share * (1 + s), list(m.rows), note=m.note)
