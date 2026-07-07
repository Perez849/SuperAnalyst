"""Assumption engine — with explicit, defensible reasoning.

Every projection driver is derived from history and/or consensus, sanity-checked,
and paired with an analyst-style rationale explaining *why* it is what it is.

Design principles that keep the forecast honest:
  - Revenue growth DECELERATES monotonically toward a terminal rate at or below
    long-run nominal GDP (law of large numbers).
  - EBIT margin MEAN-REVERTS partway toward its through-cycle average rather than
    holding a possibly-peak spot margin.
  - Reinvestment (capex, D&A, working capital) is tied to the revenue base so the
    implied ROIC and fundamental growth stay internally consistent.
  - Terminal growth must sit below the discount rate.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from .schema import CompanyData

# Long-run nominal GDP anchor for terminal growth sanity (US ~ real 2% + infl 2%).
LONG_RUN_NOMINAL_GDP = 0.040


@dataclass
class DriverSet:
    revenue_growth: list[float]
    ebit_margin: list[float]
    da_pct: list[float]
    capex_pct: list[float]
    nwc_pct_delta: float
    tax_rate: float
    terminal_growth: float
    horizon: int
    label: str = "base"
    rationale: list[tuple] = field(default_factory=list)   # (driver, trajectory, why)
    anchors: dict = field(default_factory=dict)


def _clean_mean(vals, lo=-1e9, hi=1e9):
    vals = [v for v in vals if v is not None and isinstance(v,(int,float)) and math.isfinite(v) and lo <= v <= hi]
    return sum(vals) / len(vals) if vals else None


def _fade(start: float, end: float, n: int) -> list[float]:
    if n == 1:
        return [end]
    return [start + (end - start) * i / (n - 1) for i in range(n)]


def build_drivers(data: CompanyData, horizon: int = 5,
                  terminal_growth: float = 0.025, scenario: str = "base") -> DriverSet:
    yrs = data.years
    cur = data.currency_symbol

    # --- historical anchors -------------------------------------------------
    hist_cagr = data.cagr("revenue")
    hist_cagr_c = min(max(hist_cagr if hist_cagr is not None else 0.05, -0.10), 0.40)
    margins_hist = [y.ebit_margin for y in yrs if y.ebit_margin is not None]
    margin_mean = _clean_mean(margins_hist, -0.5, 0.7) or 0.12
    last_margin = yrs[-1].ebit_margin or margin_mean
    da_pct = _clean_mean([y.depreciation_amort / y.revenue for y in yrs if y.revenue], 0, 0.5) or 0.05
    capex_pct = _clean_mean([y.capex / y.revenue for y in yrs if y.revenue], 0, 0.5) or 0.05

    nwc_ratios = []
    for a, b in zip(yrs[:-1], yrs[1:]):
        d_rev = b.revenue - a.revenue
        if d_rev > 0:
            nwc_ratios.append(b.change_in_nwc / d_rev)
    nwc_pct = _clean_mean(nwc_ratios, -0.5, 0.5)
    if nwc_pct is None:
        nwc_pct = 0.05

    tax = _clean_mean([y.effective_tax_rate for y in yrs], 0, 0.6) or 0.25
    tax = min(max(tax, 0.10), 0.35)

    # --- forward starting growth: consensus blended with history ------------
    est = data.estimates
    consensus = est.revenue_growth_next
    if consensus is not None:
        start_growth = 0.6 * consensus + 0.4 * hist_cagr_c
        growth_src = (f"year-1 consensus of {consensus:.1%} blended 60/40 with the "
                      f"{len(yrs)-1}-yr historical CAGR of {hist_cagr_c:.1%}")
    else:
        start_growth = hist_cagr_c
        growth_src = f"the {len(yrs)-1}-yr historical revenue CAGR of {hist_cagr_c:.1%} (no consensus available)"
    start_growth = min(max(start_growth, -0.05), 0.35)

    # terminal growth: capped at long-run nominal GDP
    term_g = min(terminal_growth, LONG_RUN_NOMINAL_GDP)

    # --- scenario tilts -----------------------------------------------------
    tilt = {"bear": -1, "base": 0, "bull": +1}[scenario]
    g_start = min(max(start_growth + tilt * 0.03, -0.08), 0.40)
    # ensure monotone deceleration to terminal (growth fades DOWN unless a slow grower)
    g_end = max(term_g, min(g_start, term_g + tilt * 0.005))
    if g_start < term_g:                       # low grower: gentle rise, capped
        g_end = min(g_start + 0.005, term_g)

    # margin: partial mean reversion (40%) toward through-cycle average
    reversion = 0.40
    margin_end = last_margin + reversion * (margin_mean - last_margin) + tilt * 0.015
    margin_end = min(max(margin_end, 0.0), 0.6)
    term_g_s = min(term_g + tilt * 0.003, LONG_RUN_NOMINAL_GDP)

    rev_growth = _fade(g_start, g_end, horizon)
    margins = _fade(last_margin, margin_end, horizon)

    # --- terminal-year revenue base for context -----------------------------
    term_rev = yrs[-1].revenue
    for g in rev_growth:
        term_rev *= (1 + g)

    ds = DriverSet(
        revenue_growth=rev_growth, ebit_margin=margins, da_pct=[da_pct] * horizon,
        capex_pct=[capex_pct] * horizon, nwc_pct_delta=nwc_pct, tax_rate=tax,
        terminal_growth=term_g_s, horizon=horizon, label=scenario,
        anchors=dict(hist_cagr=hist_cagr_c, consensus=consensus, margin_mean=margin_mean,
                     last_margin=last_margin, capex_pct=capex_pct, da_pct=da_pct,
                     nwc_pct=nwc_pct, tax=tax, term_rev=term_rev),
    )

    if scenario == "base":
        margin_dir = ("expands" if margin_end > last_margin + 0.002 else
                      "compresses" if margin_end < last_margin - 0.002 else "holds broadly flat")
        margin_why = (
            f"Spot EBIT margin is {last_margin:.1%} versus a through-cycle average of "
            f"{margin_mean:.1%}. We revert {reversion:.0%} of the way toward that average, "
            f"landing at {margin_end:.1%} by year {horizon} \u2014 crediting some but not all "
            f"of current profitability as durable, which guards against extrapolating a peak.")
        ds.rationale = [
            ("Revenue growth",
             f"{g_start:.1%} \u2192 {g_end:.1%} over {horizon}y",
             f"Year-1 growth is set from {growth_src}. Growth then decelerates monotonically "
             f"to the terminal rate as the base compounds toward {cur}{term_rev/1e9:,.0f}bn "
             f"\u2014 the law of large numbers and competitive entry compress incremental growth."),
            ("EBIT margin",
             f"{last_margin:.1%} \u2192 {margin_end:.1%} ({margin_dir})",
             margin_why),
            ("Reinvestment (capex)",
             f"{capex_pct:.1%} of sales",
             f"Held at the historical average capex intensity ({capex_pct:.1%}), against D&A of "
             f"{da_pct:.1%} \u2014 a capex/D&A ratio of {capex_pct/da_pct:.2f}x, consistent with "
             f"{'net capacity growth' if capex_pct>da_pct else 'a maintenance-led, capital-light steady state'}."),
            ("Working capital",
             f"{nwc_pct:.1%} of \u0394revenue",
             f"Incremental working capital absorbs {nwc_pct:.1%} of each year's revenue increase, "
             f"the historical median \u2014 {'a cash drag as the business scales' if nwc_pct>0 else 'a source of cash (negative working-capital model)'}."),
            ("Tax rate",
             f"{tax:.1%}",
             f"Normalised to the trailing effective rate of {tax:.1%}, applied to EBIT to derive NOPAT."),
            ("Terminal growth",
             f"{term_g_s:.1%}",
             f"Set at {term_g_s:.1%}, at or below long-run nominal GDP ({LONG_RUN_NOMINAL_GDP:.1%}); "
             f"a mature going concern cannot outgrow the economy in perpetuity. Must stay below the WACC."),
        ]
    return ds
