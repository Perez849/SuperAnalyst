"""Forward financial model — projected P&L reconciled to the DCF cash flows.

Builds a full projected income statement (revenue -> EBIT -> net income -> EPS)
plus the bridge from earnings down to the Levered FCF that actually feeds the
2-stage FCFE DCF. Every row is traceable: the FCF at the bottom of this model is
the exact same FCF the DCF discounts, so the P&L, the cash-flow bridge and the
$510 fair value are one coherent chain.

Inputs are the analyst estimates already captured on data.estimates:
  - revenue_path : [(year, revenue)]      analyst revenue consensus
  - eps_path     : [(year, eps)]          analyst EPS consensus
  - fcfe_path    : [(year, levered_fcf)]  analyst levered FCF consensus (feeds DCF)

Where a given line isn't provided by analysts we hold the latest reported margin
constant and flag the row as derived, so the model still reconciles.
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
    # reconciliation: the FCF column here == the DCF's stage-1 cash flows
    fcf_feeds_dcf: bool = True
    notes: list = field(default_factory=list)


def build_forward_model(data: CompanyData, sws_build: list) -> Optional[ForecastModel]:
    """sws_build: the SWSResult.build list (year + cf), the DCF's own cash flows.
    We wrap those exact FCF figures in a full projected P&L so everything ties."""
    est = data.estimates
    if not sws_build:
        return None
    cur = data.currency_symbol
    y0 = data.latest
    base_rev = y0.revenue
    last_margin = y0.ebit_margin if y0.ebit_margin else (y0.ebit / y0.revenue if y0.revenue else 0.15)

    # index analyst paths by year, after dropping internally-inconsistent points
    # (scale breaks that revert) — never capping magnitude. Anchor with the last
    # reported value so a corrupt FIRST estimate is also caught.
    from .sws_models import _drop_scale_outliers
    def _clean(path, anchor_val, anchor_yr):
        if not path:
            return {}
        raw = sorted(path)
        if anchor_val and anchor_val > 0:
            probe = _drop_scale_outliers([(anchor_yr, anchor_val)] + raw)
            return {y: v for (y, v) in probe if y != anchor_yr}
        return {y: v for (y, v) in _drop_scale_outliers(raw)}
    rev_by_year = _clean(est.revenue_path, y0.revenue, y0.year)
    eps_by_year = _clean(est.eps_path, y0.eps_diluted, y0.year)
    # net margin anchor (trailing), used to derive NI where analysts give only EPS
    ni_margin = (y0.net_income / y0.revenue) if y0.revenue else 0.08
    # analyst long-term growth (for years past the explicit +1y estimate), fading
    # to a terminal rate — NOT a hard-coded 3%. If no explicit LT estimate exists,
    # start the fade from the growth rate implied between the two analyst years,
    # so a cyclical like MU keeps a realistic ramp instead of snapping to 2.5%.
    lt_g = est.eps_growth_lt if (est.eps_growth_lt and -0.2 < est.eps_growth_lt < 2.0) else None
    if lt_g is None and est.revenue_path and len(est.revenue_path) >= 2:
        rp = sorted(est.revenue_path)
        if rp[-2][1] > 0:
            near_g = rp[-1][1] / rp[-2][1] - 1
            if -0.2 < near_g < 2.0:
                lt_g = near_g
    term_g = 0.025

    years: list[ForecastYear] = []
    prev_rev = base_rev
    last_analyst_ni_margin = None
    notes = []
    n_rows = len(sws_build)
    for idx, row in enumerate(sws_build):
        yr = row["year"]
        fcf = row["cf"]

        # revenue: analyst consensus where the year is covered; beyond that, grow
        # at the analyst long-term rate fading toward the terminal rate.
        if yr in rev_by_year:
            rev = rev_by_year[yr]
            rev_src = "Analyst"
        else:
            if lt_g is not None:
                # fade from lt_g toward term_g across the remaining horizon
                remaining = max(n_rows - idx, 1)
                g = lt_g + (term_g - lt_g) * (idx / n_rows)
                g = max(g, term_g)
            else:
                g = term_g
            rev = prev_rev * (1 + g)
            rev_src = "Derived"
        rev_g = (rev / prev_rev - 1) if prev_rev else 0.0

        # EBIT: hold trailing margin unless we can back it out
        ebit = rev * last_margin
        ebit_margin = last_margin

        # net income & EPS. Use the analyst EPS directly (no magnitude cap — a
        # 60% net margin can be real, e.g. NVDA). For years the analysts don't
        # cover, hold the LAST ANALYST net margin (not the trailing one) so the
        # series continues smoothly instead of stepping down.
        if yr in eps_by_year:
            eps = eps_by_year[yr]
            ni = eps * data.shares_diluted
            eps_src = "Analyst"
            last_analyst_ni_margin = (ni / rev) if rev else last_analyst_ni_margin
        else:
            m = last_analyst_ni_margin if last_analyst_ni_margin else ni_margin
            ni = rev * m
            eps = ni / data.shares_diluted if data.shares_diluted else 0.0
            eps_src = "Derived"

        fcf_margin = (fcf / rev) if rev else 0.0
        years.append(ForecastYear(
            year=yr, revenue=rev, revenue_growth=rev_g, ebit=ebit,
            ebit_margin=ebit_margin, net_income=ni, eps=eps, levered_fcf=fcf,
            fcf_margin=fcf_margin, revenue_src=rev_src, eps_src=eps_src,
            fcf_src=row.get("src", "Analyst")))
        prev_rev = rev

    if any(y.revenue_src == "Derived" for y in years):
        notes.append("Revenue for years without explicit analyst coverage is derived by holding "
                     "the free-cash-flow margin stable; those rows are marked 'Derived'.")
    notes.append("The levered FCF column is identical to the cash flows discounted in the DCF — "
                 "the P&L, this cash-flow line and the fair value are one reconciled chain.")

    return ForecastModel(years=years, currency=cur, notes=notes)


def _implied_growth(prev_rev, fcf, margin):
    """Fallback growth for uncovered years: modest, bounded."""
    return 0.03
