"""Relative valuation (comps) and dividend discount model."""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from typing import Optional

from .schema import CompanyData, PeerData


@dataclass
class CompsResult:
    peers: list[PeerData]
    multiples: dict            # multiple -> {'median':..,'mean':.., 'implied_vps':..}
    blended_vps: Optional[float]
    upside: Optional[float]
    notes: list[str] = field(default_factory=list)


def _median(vals):
    vals = [v for v in vals if v is not None and v > 0]
    return statistics.median(vals) if vals else None


def run_comps(data: CompanyData, peers: list[PeerData]) -> CompsResult:
    y = data.latest
    ebitda = y.ebitda
    ebit = y.ebit
    revenue = y.revenue
    eps = y.eps_diluted
    net_debt = data.net_debt
    minority = y.minority_interest
    shares = data.shares_diluted

    def ev_to_vps(ev_multiple, metric):
        implied_ev = ev_multiple * metric
        implied_eq = implied_ev - net_debt - minority
        return implied_eq / shares if shares else None

    multiples = {}
    peers = [p for p in peers if p and p.market_cap]

    m = _median([p.ev_ebitda for p in peers])
    if m and ebitda > 0:
        multiples["EV/EBITDA"] = {"median": m, "implied_vps": ev_to_vps(m, ebitda)}
    m = _median([p.ev_ebit for p in peers])
    if m and ebit > 0:
        multiples["EV/EBIT"] = {"median": m, "implied_vps": ev_to_vps(m, ebit)}
    m = _median([p.ev_sales for p in peers])
    if m and revenue > 0:
        multiples["EV/Sales"] = {"median": m, "implied_vps": ev_to_vps(m, revenue)}
    m = _median([p.pe for p in peers])
    if m and eps > 0:
        multiples["P/E"] = {"median": m, "implied_vps": m * eps}

    implied = [d["implied_vps"] for d in multiples.values() if d["implied_vps"] and math.isfinite(d["implied_vps"]) and d["implied_vps"] > 0]
    blended = statistics.mean(implied) if implied else None
    upside = (blended / data.price - 1) if (blended and data.price) else None
    return CompsResult(peers=peers, multiples=multiples, blended_vps=blended, upside=upside)


@dataclass
class DDMResult:
    value_per_share: float
    method: str
    upside: float
    assumptions: list[str] = field(default_factory=list)


def run_ddm(data: CompanyData, cost_of_equity: float,
            terminal_growth: float = 0.025) -> Optional[DDMResult]:
    """Gordon-growth DDM. Only meaningful for established dividend payers."""
    dps = data.dividend_per_share
    if not dps or dps <= 0:
        return None
    if cost_of_equity <= terminal_growth:
        return None
    # ground dividend growth in payout sustainability; cap at terminal g
    div_growth = min(terminal_growth, cost_of_equity - 0.005)
    vps = dps * (1 + div_growth) / (cost_of_equity - div_growth)
    upside = (vps / data.price - 1) if data.price else 0.0
    return DDMResult(
        value_per_share=vps, method="Gordon growth DDM", upside=upside,
        assumptions=[
            f"Current DPS: {dps:.2f}",
            f"Cost of equity: {cost_of_equity:.2%}",
            f"Perpetual dividend growth: {div_growth:.2%}",
        ],
    )
