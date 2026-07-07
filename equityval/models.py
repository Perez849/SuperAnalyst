"""Sector-specific valuation models.

Each returns a MethodResult with a value-per-share, an upside, a human label,
and detail rows (and optional projection rows) that the report renders.

Models:
  residual_income  -> banks / insurers (excess return over cost of equity)
  multistage_ddm   -> utilities / financials (explicit dividend forecast)
  pb_roe           -> financials (justified price-to-book from ROE)
  ffo_multiple     -> REITs (price to funds from operations)
  affo_yield       -> REITs (adjusted FFO capitalised like a dividend)
  normalized_cyclical -> commodities (mid-cycle margins x through-cycle multiple)
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Optional

from .schema import CompanyData, PeerData


@dataclass
class MethodResult:
    key: str
    label: str
    value_per_share: float
    upside: float
    rows: list[tuple] = field(default_factory=list)          # (label, formatted value)
    forecast: list[dict] = field(default_factory=list)        # optional projection table
    note: str = ""


def _clean(vals, lo, hi):
    vals = [v for v in vals if v is not None and lo <= v <= hi]
    return vals


def _norm_roe(data: CompanyData) -> float:
    roes = _clean([y.net_income / y.total_equity for y in data.years if y.total_equity > 0],
                  -0.5, 0.6)
    return statistics.mean(roes) if roes else 0.10


def _payout(data: CompanyData) -> float:
    eps = data.latest.eps_diluted
    if eps and eps > 0 and data.dividend_per_share:
        return min(max(data.dividend_per_share / eps, 0.0), 1.0)
    return 0.0


def _bvps(data: CompanyData) -> float:
    eq = data.latest.total_equity - data.latest.minority_interest
    return eq / data.shares_diluted if data.shares_diluted else 0.0


# --------------------------------------------------------------------------- #
def residual_income(data: CompanyData, ke: float, horizon: int = 6,
                    terminal_growth: float = 0.03) -> Optional[MethodResult]:
    bv = _bvps(data)
    if bv <= 0:
        return None
    roe = _norm_roe(data)
    payout = _payout(data)
    b = 1 - payout
    g = min(b * roe, terminal_growth + 0.02)      # book-value growth, capped
    g = max(g, 0.0)
    if ke <= terminal_growth:
        ke = terminal_growth + 0.01

    pv_ri = 0.0
    bv_t = bv
    fc = []
    for t in range(1, horizon + 1):
        ri = (roe - ke) * bv_t                     # residual income on opening book
        pv = ri / (1 + ke) ** t
        pv_ri += pv
        fc.append({"year": data.latest.year + t, "bv": bv_t, "roe": roe,
                   "ri": ri, "pv": pv})
        bv_t = bv_t * (1 + g)
    # continuing residual income (grows at terminal g)
    ri_next = (roe - ke) * bv_t
    tv = ri_next / (ke - terminal_growth)
    pv_tv = tv / (1 + ke) ** horizon
    value = bv + pv_ri + pv_tv
    up = value / data.price - 1 if data.price else 0.0
    return MethodResult(
        "residual_income", "Residual income (excess return)", value, up,
        rows=[
            ("Book value / share", f"{data.currency_symbol}{bv:,.2f}"),
            ("Normalised ROE", f"{roe:.1%}"),
            ("Cost of equity (Ke)", f"{ke:.2%}"),
            ("Payout / retention", f"{payout:.0%} / {b:.0%}"),
            ("Book-value growth", f"{g:.1%}"),
            ("PV of excess returns", f"{data.currency_symbol}{pv_ri:,.2f}"),
            ("PV of continuing value", f"{data.currency_symbol}{pv_tv:,.2f}"),
            ("Value per share", f"{data.currency_symbol}{value:,.2f}"),
        ], forecast=fc,
        note="Value = current book value + present value of returns earned above "
             "the cost of equity. The correct anchor for a balance-sheet business.")


def pb_roe(data: CompanyData, ke: float, terminal_growth: float = 0.03,
           peers: Optional[list[PeerData]] = None) -> Optional[MethodResult]:
    bv = _bvps(data)
    if bv <= 0:
        return None
    roe = _norm_roe(data)
    g = min(terminal_growth, ke - 0.005)
    justified_pb = (roe - g) / (ke - g) if ke > g else None
    if not justified_pb or justified_pb <= 0:
        return None
    value = justified_pb * bv
    up = value / data.price - 1 if data.price else 0.0
    return MethodResult(
        "pb_roe", "Justified P/B (ROE-driven)", value, up,
        rows=[
            ("Normalised ROE", f"{roe:.1%}"),
            ("Cost of equity (Ke)", f"{ke:.2%}"),
            ("Sustainable growth", f"{g:.1%}"),
            ("Justified P/B", f"{justified_pb:.2f}x"),
            ("Book value / share", f"{data.currency_symbol}{bv:,.2f}"),
            ("Value per share", f"{data.currency_symbol}{value:,.2f}"),
        ],
        note="Justified price-to-book = (ROE − g) / (Ke − g). A bank earning its "
             "cost of equity is worth exactly book value.")


def multistage_ddm(data: CompanyData, ke: float, horizon: int = 6,
                   terminal_growth: float = 0.025) -> Optional[MethodResult]:
    dps = data.dividend_per_share
    if not dps or dps <= 0:
        return None
    roe = _norm_roe(data)
    b = 1 - _payout(data)
    g1 = min(max(b * roe, 0.0), 0.15)
    if ke <= terminal_growth:
        ke = terminal_growth + 0.01
    pv, d_t, fc = 0.0, dps, []
    for t in range(1, horizon + 1):
        g = g1 + (terminal_growth - g1) * (t - 1) / max(horizon - 1, 1)
        d_t = d_t * (1 + g)
        p = d_t / (1 + ke) ** t
        pv += p
        fc.append({"year": data.latest.year + t, "dps": d_t, "g": g, "pv": p})
    tv = d_t * (1 + terminal_growth) / (ke - terminal_growth)
    pv_tv = tv / (1 + ke) ** horizon
    value = pv + pv_tv
    up = value / data.price - 1 if data.price else 0.0
    return MethodResult(
        "ddm", "Multi-stage dividend discount", value, up,
        rows=[
            ("Current DPS", f"{data.currency_symbol}{dps:,.2f}"),
            ("Near-term div growth", f"{g1:.1%}"),
            ("Terminal growth", f"{terminal_growth:.1%}"),
            ("Cost of equity (Ke)", f"{ke:.2%}"),
            ("PV of explicit dividends", f"{data.currency_symbol}{pv:,.2f}"),
            ("PV of terminal value", f"{data.currency_symbol}{pv_tv:,.2f}"),
            ("Value per share", f"{data.currency_symbol}{value:,.2f}"),
        ], forecast=fc,
        note="Dividends grow from the retention-implied rate and fade to a "
             "sustainable terminal growth, discounted at the cost of equity.")


def _ffo_per_share(data: CompanyData) -> float:
    y = data.latest
    ffo = y.net_income + y.depreciation_amort      # simplified FFO
    return ffo / data.shares_diluted if data.shares_diluted else 0.0


def ffo_multiple(data: CompanyData, peers: Optional[list[PeerData]] = None,
                 default_mult: float = 15.0) -> Optional[MethodResult]:
    ffops = _ffo_per_share(data)
    if ffops <= 0:
        return None
    mult = default_mult
    src = "sector default"
    if peers:
        pes = [p.pe for p in peers if p.pe and p.pe > 0]
        if pes:
            mult = statistics.median(pes)
            src = "peer median (P/E proxy)"
    value = mult * ffops
    up = value / data.price - 1 if data.price else 0.0
    return MethodResult(
        "ffo_multiple", "Price / FFO", value, up,
        rows=[
            ("FFO per share", f"{data.currency_symbol}{ffops:,.2f}"),
            ("P/FFO multiple", f"{mult:.1f}x ({src})"),
            ("Value per share", f"{data.currency_symbol}{value:,.2f}"),
        ],
        note="FFO = net income + real-estate depreciation. Removes the non-cash "
             "depreciation that makes REIT GAAP earnings and DCF misleading.")


def affo_yield(data: CompanyData, ke: float, terminal_growth: float = 0.02,
               affo_ratio: float = 0.88) -> Optional[MethodResult]:
    ffops = _ffo_per_share(data)
    if ffops <= 0:
        return None
    affops = ffops * affo_ratio
    req = ke - terminal_growth
    if req <= 0:
        return None
    value = affops * (1 + terminal_growth) / req
    up = value / data.price - 1 if data.price else 0.0
    return MethodResult(
        "affo_yield", "AFFO capitalisation", value, up,
        rows=[
            ("AFFO per share", f"{data.currency_symbol}{affops:,.2f}"),
            ("Required return (Ke)", f"{ke:.2%}"),
            ("Terminal growth", f"{terminal_growth:.1%}"),
            ("Implied AFFO yield", f"{req:.2%}"),
            ("Value per share", f"{data.currency_symbol}{value:,.2f}"),
        ],
        note="Adjusted FFO (after recurring capex) capitalised like a growing "
             "perpetuity — the cash a REIT can actually distribute.")


def normalized_cyclical(data: CompanyData, peers: Optional[list[PeerData]] = None,
                        default_mult: float = 6.5) -> Optional[MethodResult]:
    margins = _clean([y.ebit_margin for y in data.years], -0.3, 0.6)
    if not margins:
        return None
    mid_margin = statistics.mean(margins)          # through-cycle margin
    rev = data.latest.revenue
    norm_ebit = rev * mid_margin
    norm_ebitda = norm_ebit + data.latest.depreciation_amort
    mult = default_mult
    src = "through-cycle default"
    if peers:
        evs = [p.ev_ebitda for p in peers if p.ev_ebitda and p.ev_ebitda > 0]
        if evs:
            mult = statistics.median(evs)
            src = "peer median"
    ev = norm_ebitda * mult
    equity = ev - data.net_debt - data.latest.minority_interest
    value = equity / data.shares_diluted if data.shares_diluted else 0.0
    up = value / data.price - 1 if data.price else 0.0
    cur = data.currency_symbol
    return MethodResult(
        "normalized", "Mid-cycle normalized EV/EBITDA", value, up,
        rows=[
            ("Through-cycle EBIT margin", f"{mid_margin:.1%}"),
            ("Spot EBIT margin", f"{(data.latest.ebit_margin or 0):.1%}"),
            ("Normalized EBITDA", f"{cur}{norm_ebitda/1e9:,.2f}bn"),
            ("EV/EBITDA multiple", f"{mult:.1f}x ({src})"),
            ("Enterprise value", f"{cur}{ev/1e9:,.2f}bn"),
            ("− Net debt", f"{cur}{data.net_debt/1e9:,.2f}bn"),
            ("Value per share", f"{cur}{value:,.2f}"),
        ],
        note="Commodity spot margins mislead at cycle peaks and troughs; this "
             "normalises to the through-cycle average margin and multiple.")
