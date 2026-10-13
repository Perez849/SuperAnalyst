"""Forward numbers and earnings-quality diagnostics.

The valuation lenses all start from the same question: *what earnings is the market
paying for, and how durable are they?* This module answers it once, in one place:

  forward_numbers()  consensus FY+1 / FY+2 EPS and revenue (or a clearly-flagged
                     derivation from history when consensus is missing), plus an
                     NTM-style blended EPS.
  cycle_info()       is the business cyclical, and are forward earnings far above
                     what it has historically earned (peak / inflection)? That is what
                     justifies a lower multiple on today's record numbers -- the
                     single biggest source of "target price" error on memory, miners
                     and commodity names.

Nothing here caps or edits analyst numbers; it only measures and flags them.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from typing import Optional

from .reference import SectorRef
from .schema import CompanyData


def _fin(x) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(x)


@dataclass
class CycleInfo:
    is_cyclical: bool
    reasons: list[str]
    norm_eps: Optional[float]          # through-cycle EPS (mean of reported history)
    peak_ratio: Optional[float]        # NTM EPS / through-cycle EPS
    durability: float                  # multiplier on the target multiple, 0.55 - 1.0
    mid_margin: Optional[float]        # through-cycle EBIT margin


@dataclass
class Forward:
    fy1_year: int
    eps_ltm: Optional[float]
    eps_fy1: Optional[float]
    eps_fy2: Optional[float]
    eps_ntm: Optional[float]
    rev_fy1: Optional[float]
    rev_fy2: Optional[float]
    rev_ntm: Optional[float]
    ni_ntm: Optional[float]
    growth: float                      # durable EPS growth (decimal) used for multiple adjustment
    growth_src: str
    basis: str                         # 'consensus' | 'consensus (single year)' | 'derived from history'
    cycle: CycleInfo
    flags: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
def _by_year(path, y0: int) -> dict[int, float]:
    out = {}
    for yr, v in sorted(path or []):
        if _fin(v) and v != 0 and y0 < yr <= y0 + 4:
            out[int(yr)] = float(v)
    return out


def _mean_positive(xs):
    xs = [x for x in xs if _fin(x)]
    return statistics.mean(xs) if xs else None


def cycle_info(data: CompanyData, ref: SectorRef, eps_ntm: Optional[float],
               rev_growth_fy1: Optional[float], eps_ltm: Optional[float]) -> CycleInfo:
    ys = data.years
    reasons: list[str] = []

    # 1) revenue ever fell hard?
    drops = [b.revenue / a.revenue - 1 for a, b in zip(ys[:-1], ys[1:])
             if a.revenue and a.revenue > 0 and b.revenue]
    worst_drop = min(drops) if drops else 0.0
    if worst_drop <= -0.12:
        reasons.append(f"revenue fell {abs(worst_drop):.0%} in a single year")

    # 2) EBIT-margin drawdown from a prior peak (a monotonic ramp like NVDA is NOT cyclical)
    margins = [y.ebit_margin for y in ys
               if y.ebit_margin is not None and _fin(y.ebit_margin) and abs(y.ebit_margin) < 1.5]
    mdd = 0.0
    peak = -9.0
    for m in margins:
        peak = max(peak, m)
        mdd = max(mdd, peak - m)
    if mdd >= 0.10:
        reasons.append(f"EBIT margin has swung {mdd*100:.0f}pts peak-to-trough")

    # 3) profit turnaround: loss-making on a trailing basis, large positive forward earnings
    turnaround = (eps_ltm is not None and eps_ltm <= 0 and eps_ntm is not None and eps_ntm > 0
                  and (rev_growth_fy1 or 0) > 0.60)
    if turnaround:
        reasons.append("swing from trailing losses to large forward profits (cycle inflection)")

    # 4) structurally cyclical industry
    blob = f"{data.sector} {data.industry}".lower()
    if any(k in blob for k in ("memory", "oil & gas", "steel", "gold", "silver", "copper",
                               "uranium", "coal", "aluminum", "chemicals", "airlines",
                               "shipping", "semiconductor equipment", "auto manufacturers",
                               "data storage")):
        reasons.append("commodity / capital-cycle industry")

    cyc = bool(reasons)

    eps_hist = [y.eps_diluted for y in ys if _fin(y.eps_diluted)]
    norm_eps = _mean_positive(eps_hist)
    peak_ratio = None
    durability = 1.0
    if eps_ntm and eps_ntm > 0:
        floor = 0.05 * eps_ntm
        base = max(norm_eps if norm_eps is not None else 0.0, floor)
        peak_ratio = min(eps_ntm / base, 50.0)
        if cyc and peak_ratio > 1.5:
            durability = 1.0 / (1.0 + 0.22 * math.log(peak_ratio))
            durability = min(max(durability, 0.55), 1.0)

    ebit_margins = [m for m in margins if -0.5 < m < 0.8]
    mid_margin = statistics.mean(ebit_margins) if ebit_margins else None
    return CycleInfo(cyc, reasons, norm_eps, peak_ratio, durability, mid_margin)


# --------------------------------------------------------------------------- #
def forward_numbers(data: CompanyData, ref: SectorRef) -> Forward:
    est = data.estimates
    y = data.latest
    y0 = y.year
    flags: list[str] = []

    eps_by = _by_year(est.eps_path, y0)
    rev_by = _by_year(est.revenue_path, y0)
    eps_ltm = y.eps_diluted if _fin(y.eps_diluted) else None

    eps1 = eps_by.get(y0 + 1)
    eps2 = eps_by.get(y0 + 2)
    rev1 = rev_by.get(y0 + 1)
    rev2 = rev_by.get(y0 + 2)

    if eps1 is None and est.forward_eps and est.forward_eps > 0:
        eps1 = est.forward_eps
    basis = "consensus"
    if eps1 is not None and eps2 is None:
        basis = "consensus (single year)"

    # revenue growth for FY+1: consensus first, else derived below
    g_rev1 = (rev1 / y.revenue - 1) if (rev1 and y.revenue) else est.revenue_growth_next
    if g_rev1 is not None and not (-0.6 < g_rev1 < 3.0):
        g_rev1 = None

    # No EPS consensus at all: derive from history, flagged.
    if eps1 is None:
        basis = "derived from history"
        flags.append("No analyst EPS consensus available; forward EPS is derived from "
                     "trailing earnings and revenue growth.")
        if eps_ltm is not None and eps_ltm > 0:
            g = g_rev1 if g_rev1 is not None else (data.cagr("revenue") or 0.04)
            g = min(max(g, -0.10), 0.25)
            eps1 = eps_ltm * (1 + g)
            if rev1 is None and y.revenue:
                rev1 = y.revenue * (1 + g)
        elif eps_ltm is not None:
            flags.append("Trailing EPS is negative and there is no consensus: earnings-based "
                         "lenses are unavailable.")

    if rev1 is None and y.revenue:
        g = g_rev1 if g_rev1 is not None else min(max(data.cagr("revenue") or 0.04, -0.10), 0.25)
        rev1 = y.revenue * (1 + g)
        g_rev1 = g

    # NTM proxy: the blend of the current and next fiscal year (half of FY+1's year is
    # usually already behind us). Unbiased across fiscal calendars, and it stops the
    # target hinging on which side of a fiscal year-end the run date falls.
    eps_ntm = None
    if eps1 is not None and eps2 is not None:
        eps_ntm = 0.5 * (eps1 + eps2)
    elif eps1 is not None:
        eps_ntm = eps1
    rev_ntm = 0.5 * (rev1 + rev2) if (rev1 and rev2) else rev1

    cyc = cycle_info(data, ref, eps_ntm, g_rev1, eps_ltm)

    # durable EPS growth: a published 5y LTG if there is one, else the FY2/FY1 step
    # (bounded), else history -- then pulled toward the sector's long-run growth,
    # because multiples price durable growth, not the shape of one recovery year.
    # Each source has its own ceiling: a published 5y LTG can be high, a one-year EPS step is a
    # recovery/momentum number, and a trailing CAGR describes the past, not the next decade.
    if est.analyst_growth_5y is not None and -0.10 < est.analyst_growth_5y < 0.60:
        g_raw, src = min(est.analyst_growth_5y, 0.35), "analyst 5y growth estimate"
    elif eps1 and eps2 and eps1 > 0 and not (cyc.is_cyclical and cyc.peak_ratio and cyc.peak_ratio > 2):
        g_raw, src = min(eps2 / eps1 - 1, 0.30), "consensus FY+2 / FY+1 EPS step"
    elif data.cagr("revenue") is not None:
        g_raw, src = min(data.cagr("revenue"), 0.15), "historical revenue CAGR (capped at 15%)"
    else:
        g_raw, src = ref.growth, "sector long-run growth"
    g_raw = max(g_raw, -0.10)
    growth = 0.65 * g_raw + 0.35 * ref.growth
    if cyc.is_cyclical:
        growth = min(growth, ref.growth)            # cycle recovery is not durable growth
        src += "; capped at sector growth (cyclical)"

    if eps_ntm and eps_ltm and eps_ltm > 0 and eps_ntm / eps_ltm > 3:
        flags.append(f"Forward EPS is {eps_ntm/eps_ltm:.1f}x trailing: earnings are in a steep "
                     "inflection and carry high forecast risk.")
    if cyc.is_cyclical and cyc.peak_ratio and cyc.peak_ratio > 2:
        flags.append(f"Forward EPS is {cyc.peak_ratio:.1f}x the through-cycle average; target "
                     f"multiples are scaled by {cyc.durability:.2f} for earnings durability.")
    if eps1 and rev1 and data.shares_diluted:
        nm = eps1 * data.shares_diluted / rev1
        if nm > 0.80:
            flags.append(f"Consensus implies a {nm:.0%} net margin; treat revenue-linked "
                         "lenses with caution.")

    ni_ntm = eps_ntm * data.shares_diluted if (eps_ntm and data.shares_diluted) else None
    return Forward(
        fy1_year=y0 + 1, eps_ltm=eps_ltm, eps_fy1=eps1, eps_fy2=eps2, eps_ntm=eps_ntm,
        rev_fy1=rev1, rev_fy2=rev2, rev_ntm=rev_ntm, ni_ntm=ni_ntm,
        growth=growth, growth_src=src, basis=basis, cycle=cyc, flags=flags)
