"""Forward financial model -- the projected P&L behind the DCF.

Takes the base-case FCFF forecast and wraps it in a full income-statement view
(revenue -> EBIT -> net income -> EPS) plus the bridge down to levered free cash flow, so
that the P&L, the cash-flow line and the DCF value are one reconciled chain.

Where consensus EPS covers a year, that year's net income is the analyst figure (flagged
'Analyst'); everywhere else it is derived from the projected EBIT, flat interest and the
normalised tax rate (flagged 'Derived').
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .schema import CompanyData


@dataclass
class ForecastYear:
    year: int
    revenue: float
    revenue_growth: float
    ebit: float
    ebit_margin: float
    net_income: float
    eps: float
    levered_fcf: float
    fcf_margin: float           # levered FCF / revenue
    revenue_src: str            # 'Analyst' | 'Derived'
    eps_src: str
    fcf_src: str


@dataclass
class ForecastModel:
    years: list                 # list[ForecastYear]
    currency: str
    fcf_feeds_dcf: bool = True
    notes: list = field(default_factory=list)


def build_forward_model(data: CompanyData, dcf, drivers, fwd=None) -> Optional[ForecastModel]:
    """dcf: DCFResult (base case); drivers: the DriverSet it was run with; fwd: Forward."""
    if dcf is None or not getattr(dcf, "forecast", None):
        return None
    y0 = data.latest
    shares = data.shares_diluted or 1.0
    tax = drivers.tax_rate
    interest = y0.interest_expense or 0.0
    eps_by = {}
    rev_by = {}
    if fwd is not None:
        if fwd.eps_fy1 is not None:
            eps_by[fwd.fy1_year] = fwd.eps_fy1
        if fwd.eps_fy2 is not None:
            eps_by[fwd.fy1_year + 1] = fwd.eps_fy2
        if fwd.rev_fy1:
            rev_by[fwd.fy1_year] = fwd.rev_fy1
        if fwd.rev_fy2:
            rev_by[fwd.fy1_year + 1] = fwd.rev_fy2

    years: list[ForecastYear] = []
    prev_rev = y0.revenue
    for f in dcf.forecast:
        pretax = f.ebit - interest
        ni = pretax * (1 - tax) if pretax > 0 else pretax
        eps_src = "Derived"
        if f.year in eps_by and fwd is not None and fwd.basis.startswith("consensus"):
            ni = eps_by[f.year] * shares
            eps_src = "Analyst"
        rev_src = "Analyst" if (f.year in rev_by and fwd is not None and fwd.basis.startswith("consensus")) else "Derived"
        lfcf = f.fcff - interest * (1 - tax)
        years.append(ForecastYear(
            year=f.year, revenue=f.revenue,
            revenue_growth=(f.revenue / prev_rev - 1) if prev_rev else 0.0,
            ebit=f.ebit, ebit_margin=f.ebit_margin, net_income=ni, eps=ni / shares,
            levered_fcf=lfcf, fcf_margin=(lfcf / f.revenue) if f.revenue else 0.0,
            revenue_src=rev_src, eps_src=eps_src, fcf_src="DCF base case"))
        prev_rev = f.revenue

    notes = ["Revenue and EBIT margin are the DCF's own base-case drivers; net income uses flat "
             "interest and the normalised tax rate except where consensus EPS covers the year.",
             "Levered FCF = unlevered FCF less after-tax interest; the unlevered line is what the "
             "DCF discounts."]
    return ForecastModel(years=years, currency=data.currency_symbol, notes=notes)
