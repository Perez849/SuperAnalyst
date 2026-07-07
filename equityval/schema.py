"""Unified financial data schema.

Every provider (FMP, yfinance, demo) normalizes into these dataclasses so the
valuation engine never has to care where the numbers came from.

All monetary values are in the company's reporting currency, absolute units
(not millions), unless explicitly noted. Years are ordered OLDEST -> NEWEST.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class YearFinancials:
    """One fiscal year of the three statements, already cleaned."""
    year: int
    # Income statement
    revenue: float
    ebit: float                       # operating income
    ebitda: float
    depreciation_amort: float         # D&A (positive)
    interest_expense: float           # positive number
    pretax_income: float
    tax_expense: float
    net_income: float
    eps_diluted: float
    # Cash flow
    capex: float                      # positive number (cash outflow)
    change_in_nwc: float              # increase in NWC = cash outflow (positive)
    operating_cash_flow: float
    # Balance sheet (point-in-time, end of year)
    total_debt: float
    cash_and_sti: float               # cash + short-term investments
    total_equity: float
    minority_interest: float = 0.0
    invested_capital: Optional[float] = None

    @property
    def effective_tax_rate(self) -> Optional[float]:
        if self.pretax_income and self.pretax_income != 0:
            return self.tax_expense / self.pretax_income
        return None

    @property
    def ebit_margin(self) -> Optional[float]:
        return self.ebit / self.revenue if self.revenue else None

    @property
    def ebitda_margin(self) -> Optional[float]:
        return self.ebitda / self.revenue if self.revenue else None


@dataclass
class Estimates:
    """Forward-looking consensus, all optional (None if provider lacks them)."""
    revenue_growth_next: Optional[float] = None   # y+1 revenue growth
    revenue_growth_2y: Optional[float] = None     # y+2 revenue growth
    eps_next: Optional[float] = None
    eps_growth_lt: Optional[float] = None         # long-term growth estimate
    target_price_mean: Optional[float] = None
    num_analysts: Optional[int] = None


@dataclass
class CompanyData:
    ticker: str
    name: str
    currency: str
    sector: str
    industry: str
    price: float
    shares_diluted: float
    market_cap: float
    beta: Optional[float]
    dividend_per_share: float
    years: list[YearFinancials]
    estimates: Estimates = field(default_factory=Estimates)
    peers: list[str] = field(default_factory=list)
    provider: str = "unknown"
    # full reported statements: {'income'|'balance'|'cashflow': [(label, {year: value}), ...]}
    raw_statements: dict = field(default_factory=dict)

    @property
    def latest(self) -> YearFinancials:
        return self.years[-1]

    @property
    def net_debt(self) -> float:
        y = self.latest
        return y.total_debt - y.cash_and_sti

    @property
    def currency_symbol(self) -> str:
        return {"USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥",
                "CHF": "CHF ", "CAD": "C$", "AUD": "A$"}.get(self.currency, self.currency + " ")

    def cagr(self, attr: str, n: Optional[int] = None) -> Optional[float]:
        """Historical CAGR of any per-year attribute over the last n periods."""
        vals = [getattr(y, attr) for y in self.years]
        if n is not None:
            vals = vals[-(n + 1):]
        vals = [v for v in vals if v is not None and isinstance(v,(int,float)) and math.isfinite(v)]
        if len(vals) < 2 or vals[0] <= 0 or vals[-1] <= 0:
            return None
        periods = len(vals) - 1
        return (vals[-1] / vals[0]) ** (1 / periods) - 1

    def mean_of(self, prop: str, n: Optional[int] = None) -> Optional[float]:
        vals = []
        for y in self.years:
            v = getattr(y, prop)
            if callable(v):
                v = v
            if v is not None:
                vals.append(v)
        if n is not None:
            vals = vals[-n:]
        vals = [v for v in vals if v is not None and isinstance(v,(int,float)) and math.isfinite(v)]
        return sum(vals) / len(vals) if vals else None


@dataclass
class PeerData:
    """Light-weight peer snapshot for relative valuation."""
    ticker: str
    name: str
    market_cap: float
    ev: float
    ebitda: float
    ebit: float
    revenue: float
    net_income: float
    eps: float
    price: float
    fcf: float

    @property
    def ev_ebitda(self):
        return self.ev / self.ebitda if self.ebitda else None

    @property
    def ev_ebit(self):
        return self.ev / self.ebit if self.ebit else None

    @property
    def ev_sales(self):
        return self.ev / self.revenue if self.revenue else None

    @property
    def pe(self):
        return self.price / self.eps if self.eps and self.eps > 0 else None

    @property
    def p_fcf(self):
        return self.market_cap / self.fcf if self.fcf and self.fcf > 0 else None
