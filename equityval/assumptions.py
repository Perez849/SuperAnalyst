"""Assumption engine -- with explicit, defensible reasoning.

Every projection driver is derived from consensus and history, sanity-checked, and paired
with an analyst-style rationale explaining *why* it is what it is.

Design principles that keep the forecast honest (these are the guardrails whose absence
produced $34,000 targets for a $950 stock):

  - Consensus is used for what it is good at -- the next one or two fiscal years. Beyond
    that, growth DECAYS GEOMETRICALLY toward a terminal rate at or below long-run nominal
    GDP, so a +100% step can never be compounded for a decade.
  - EBIT margin MEAN-REVERTS toward the company's through-cycle average (strongly for
    cyclicals, gently for compounders), and the consensus-implied margin is capped at
    1.5x the highest margin the company has ever reported.
  - Capex converges to a sustainable multiple of D&A, so the terminal year is neither
    starved of reinvestment nor weighed down by growth capex it no longer needs.
  - Terminal growth must sit below the discount rate (enforced in dcf.run_dcf).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from .estimates import Forward, forward_numbers
from .reference import SectorRef, lookup
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
    vals = [v for v in vals if v is not None and isinstance(v, (int, float))
            and math.isfinite(v) and lo <= v <= hi]
    return sum(vals) / len(vals) if vals else None


def _lin(start: float, end: float, n: int) -> list[float]:
    if n <= 0:
        return []
    if n == 1:
        return [end]
    return [start + (end - start) * i / (n - 1) for i in range(n)]


def _implied_ebit_margin(data: CompanyData, eps: Optional[float], rev: Optional[float],
                         tax: float) -> Optional[float]:
    """EBIT margin implied by consensus EPS and revenue for one fiscal year."""
    if not eps or not rev or rev <= 0 or not data.shares_diluted:
        return None
    ni = eps * data.shares_diluted
    pretax = ni / (1 - tax) if ni > 0 else ni
    ebit = pretax + data.latest.interest_expense
    return ebit / rev


def build_drivers(data: CompanyData, horizon: int = 10, terminal_growth: float = 0.025,
                  scenario: str = "base", fwd: Optional[Forward] = None,
                  ref: Optional[SectorRef] = None) -> DriverSet:
    yrs = data.years
    cur = data.currency_symbol
    ref = ref or lookup(data.sector, data.industry)
    fwd = fwd or forward_numbers(data, ref)
    cyc = fwd.cycle
    last = yrs[-1]
    H = max(int(horizon), 3)

    # --- historical anchors -------------------------------------------------
    hist_cagr = data.cagr("revenue")
    hist_cagr_c = min(max(hist_cagr if hist_cagr is not None else 0.05, -0.10), 0.40)
    margins_hist = [y.ebit_margin for y in yrs if y.ebit_margin is not None]
    margin_mean = cyc.mid_margin if cyc.mid_margin is not None else \
        (_clean_mean(margins_hist, -0.5, 0.7) or ref.margin)
    last_margin = last.ebit_margin if last.ebit_margin is not None else margin_mean
    max_margin = max([m for m in margins_hist if m is not None and m < 0.9] or [ref.margin])
    margin_cap = min(0.80, max(0.35, 1.5 * max_margin))
    da_pct = _clean_mean([y.depreciation_amort / y.revenue for y in yrs if y.revenue], 0, 0.5) or 0.05
    capex_pct = _clean_mean([y.capex / y.revenue for y in yrs if y.revenue], 0, 0.5) or 0.05

    nwc_ratios = []
    for a, b in zip(yrs[:-1], yrs[1:]):
        d_rev = b.revenue - a.revenue
        if d_rev > 0:
            nwc_ratios.append(b.change_in_nwc / d_rev)
    nwc_pct = _clean_mean(nwc_ratios, -0.5, 0.5)
    nwc_pct = 0.05 if nwc_pct is None else min(max(nwc_pct, -0.10), 0.35)

    tax = _clean_mean([y.effective_tax_rate for y in yrs], 0, 0.6) or 0.25
    tax = min(max(tax, 0.10), 0.35)

    # --- scenario tilts -----------------------------------------------------
    tilt = {"bear": -1, "base": 0, "bull": +1}[scenario]
    term_g = min(terminal_growth, LONG_RUN_NOMINAL_GDP)
    term_g_s = min(max(term_g + tilt * 0.003, 0.0), LONG_RUN_NOMINAL_GDP)

    # --- revenue: explicit consensus years, then geometric decay -------------
    explicit: list[float] = []
    growth_src = ""
    if fwd.rev_fy1 and last.revenue and -0.6 < fwd.rev_fy1 / last.revenue - 1 < 3.0:
        explicit.append(fwd.rev_fy1 / last.revenue - 1)
        if fwd.rev_fy2 and fwd.rev_fy1 and -0.6 < fwd.rev_fy2 / fwd.rev_fy1 - 1 < 2.0:
            explicit.append(fwd.rev_fy2 / fwd.rev_fy1 - 1)
        growth_src = (f"consensus revenue for FY{fwd.fy1_year}"
                      + (f" and FY{fwd.fy1_year + 1}" if len(explicit) > 1 else ""))
    if not explicit:
        g1 = hist_cagr_c
        if data.estimates.revenue_growth_next is not None and \
                -0.3 < data.estimates.revenue_growth_next < 0.6:
            g1 = 0.6 * data.estimates.revenue_growth_next + 0.4 * hist_cagr_c
            growth_src = (f"year-1 consensus of {data.estimates.revenue_growth_next:.1%} blended "
                          f"60/40 with the {len(yrs)-1}-yr historical CAGR of {hist_cagr_c:.1%}")
        else:
            growth_src = f"the {len(yrs)-1}-yr historical revenue CAGR of {hist_cagr_c:.1%}"
        explicit = [min(max(g1, -0.05), 0.25)]
    explicit = explicit[:H]
    explicit = [g + tilt * max(0.02, 0.08 * abs(g)) for g in explicit]

    g_start = min(max(explicit[-1], term_g_s), 0.22)
    if cyc.is_cyclical:
        g_start = min(g_start, ref.growth + 0.02)       # the recovery year is not a trend
    n_tail = H - len(explicit)
    tail: list[float] = []
    if n_tail > 0:
        decay = 0.05 ** (1.0 / max(n_tail, 1))           # ~95% of the excess gone by the last year
        for j in range(1, n_tail + 1):
            tail.append(term_g_s + (g_start - term_g_s) * decay ** j)
        tail[-1] = term_g_s
    rev_growth = explicit + tail

    # --- EBIT margin: consensus-implied (capped), then mean reversion --------
    m_cons1 = _implied_ebit_margin(data, fwd.eps_fy1, fwd.rev_fy1, tax)
    m_cons2 = _implied_ebit_margin(data, fwd.eps_fy2, fwd.rev_fy2, tax) if fwd.eps_fy2 else None
    cons_note = ""
    explicit_m: list[float] = []
    if m_cons1 is not None and len(explicit) >= 1:
        m1 = min(max(m_cons1, -0.5), margin_cap)
        if m_cons1 > margin_cap:
            cons_note = (f" (consensus implies {m_cons1:.0%}; capped at {margin_cap:.0%}, 1.5x the "
                         f"highest margin ever reported)")
        explicit_m.append(m1)
        if m_cons2 is not None and len(explicit) >= 2:
            explicit_m.append(min(max(m_cons2, -0.5), margin_cap))
    if not explicit_m:
        explicit_m = [last_margin]
    explicit_m = [m + tilt * 0.015 for m in explicit_m]
    explicit_m = explicit_m + [explicit_m[-1]] * max(0, len(explicit) - len(explicit_m))

    rho = 0.60 if cyc.is_cyclical else 0.30
    m_anchor = explicit_m[-1]
    margin_end = m_anchor + rho * (margin_mean - m_anchor) + tilt * 0.01
    margin_end = min(max(margin_end, -0.5 if m_anchor < 0 else 0.0), margin_cap)
    k = len(explicit_m)
    ramp_n = max(H - k - 2, 1)
    margins = list(explicit_m[:H])
    if H - k > 0:
        margins += _lin(m_anchor, margin_end, ramp_n + 1)[1:][:H - k]
        while len(margins) < H:
            margins.append(margin_end)
    margins = margins[:H]

    # --- reinvestment: capex converges to a sustainable multiple of D&A ------
    capex_end = da_pct * 1.10
    capex_path = _lin(capex_pct, capex_end, H)

    # --- terminal-year revenue base for context -----------------------------
    term_rev = last.revenue
    for g in rev_growth:
        term_rev *= (1 + g)

    ds = DriverSet(
        revenue_growth=rev_growth, ebit_margin=margins, da_pct=[da_pct] * H,
        capex_pct=capex_path, nwc_pct_delta=nwc_pct, tax_rate=tax,
        terminal_growth=term_g_s, horizon=H, label=scenario,
        anchors=dict(hist_cagr=hist_cagr_c, consensus=fwd.rev_fy1, margin_mean=margin_mean,
                     last_margin=last_margin, capex_pct=capex_pct, da_pct=da_pct,
                     nwc_pct=nwc_pct, tax=tax, term_rev=term_rev, margin_cap=margin_cap,
                     cyclical=cyc.is_cyclical),
    )

    if scenario == "base":
        margin_dir = ("expands" if margins[-1] > last_margin + 0.002 else
                      "compresses" if margins[-1] < last_margin - 0.002 else "holds broadly flat")
        shape = ("a cyclical business, so we revert " if cyc.is_cyclical else
                 "a compounder, so we revert only ")
        ds.rationale = [
            ("Revenue growth",
             f"{rev_growth[0]:.1%} → {rev_growth[-1]:.1%} over {H}y",
             f"{'Year 1 follows' if len(explicit) == 1 else 'Years 1–' + str(len(explicit)) + ' follow'} {growth_src}. Growth then decays geometrically "
             f"from {g_start:.1%} to the {term_g_s:.1%} terminal rate as revenue compounds toward "
             f"{(cur + format(term_rev / 1e9, ',.0f') + 'bn') if term_rev >= 1e10 else (cur + format(term_rev / 1e9, ',.2f') + 'bn') if term_rev >= 1e9 else (cur + format(term_rev / 1e6, ',.0f') + 'mn')} — competitive entry and the law of large numbers "
             f"compress incremental growth; no single year's step is ever extrapolated."),
            ("EBIT margin",
             f"{last_margin:.1%} → {margins[0]:.1%} → {margins[-1]:.1%} ({margin_dir})",
             f"Reported margin is {last_margin:.1%}; year-1 margin is {margins[0]:.1%}{cons_note}. "
             f"This is {shape}{rho:.0%} of the way toward the through-cycle average of "
             f"{margin_mean:.1%}, landing at {margins[-1]:.1%} — crediting some but not all "
             f"of current profitability as durable."),
            ("Reinvestment (capex)",
             f"{capex_pct:.1%} → {capex_end:.1%} of sales",
             f"Starts at the historical capex intensity ({capex_pct:.1%}) against D&A of "
             f"{da_pct:.1%}, converging to 1.10x D&A by the terminal year — a steady state that "
             f"funds growth without permanent over- or under-investment."),
            ("Working capital",
             f"{nwc_pct:.1%} of Δrevenue",
             f"Incremental working capital {'absorbs' if nwc_pct > 0 else 'releases'} {abs(nwc_pct):.1%} of each year's revenue increase "
             f"(historical median) — "
             f"{'a cash drag as the business scales' if nwc_pct > 0 else 'a source of cash (negative working-capital model)'}."),
            ("Tax rate",
             f"{tax:.1%}",
             f"Normalised to the trailing effective rate of {tax:.1%}, applied to EBIT to derive NOPAT."),
            ("Terminal growth",
             f"{term_g_s:.1%}",
             f"At or below long-run nominal GDP ({LONG_RUN_NOMINAL_GDP:.1%}); a mature going concern "
             f"cannot outgrow the economy in perpetuity. Terminal reinvestment is g/ROIC."),
        ]
    return ds
