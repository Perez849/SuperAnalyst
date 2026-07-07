"""Discounted cash flow engine (unlevered / FCFF).

FCFF_t = EBIT_t*(1-tax) + D&A_t - Capex_t - ΔNWC_t

Enterprise value = Σ PV(FCFF_t) + PV(terminal value)
Equity value     = EV - net debt - minority interest + non-op investments
Per share        = equity value / diluted shares

Terminal value computed two ways and reported side by side:
  - Gordon growth:  TV = FCFF_{n+1} / (WACC - g)
  - Exit multiple:  TV = EBITDA_n * exit_EV/EBITDA
The Gordon method drives the headline; the exit multiple is a sanity cross-check.

Mid-year convention is supported (discount at t-0.5) — standard on sell-side
because cash flows arrive through the year, not as a year-end bullet.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .assumptions import DriverSet
from .schema import CompanyData


@dataclass
class ForecastYear:
    year: int
    revenue: float
    ebit: float
    ebit_margin: float
    nopat: float
    da: float
    capex: float
    d_nwc: float
    fcff: float
    discount_factor: float
    pv_fcff: float


@dataclass
class DCFResult:
    forecast: list[ForecastYear]
    tv_gordon: float
    tv_exit: Optional[float]
    pv_tv: float
    pv_explicit: float
    enterprise_value: float
    net_debt: float
    minority: float
    equity_value: float
    shares: float
    value_per_share: float
    upside: float
    price: float
    wacc: float
    terminal_growth: float
    tv_pct_of_ev: float
    scenario: str
    exit_multiple: Optional[float] = None
    notes: list[str] = field(default_factory=list)


def run_dcf(
    data: CompanyData,
    drivers: DriverSet,
    wacc: float,
    exit_multiple: Optional[float] = None,
    mid_year: bool = True,
    non_operating_assets: float = 0.0,
) -> DCFResult:
    base = data.latest
    rev = base.revenue
    forecast: list[ForecastYear] = []
    pv_explicit = 0.0

    for i in range(drivers.horizon):
        g = drivers.revenue_growth[i]
        rev = rev * (1 + g)
        margin = drivers.ebit_margin[i]
        ebit = rev * margin
        nopat = ebit * (1 - drivers.tax_rate)
        da = rev * drivers.da_pct[i]
        capex = rev * drivers.capex_pct[i]
        # incremental NWC investment on the revenue delta this year
        prev_rev = forecast[i - 1].revenue if i > 0 else base.revenue
        d_nwc = (rev - prev_rev) * drivers.nwc_pct_delta
        fcff = nopat + da - capex - d_nwc

        t = (i + 1) - (0.5 if mid_year else 0.0)
        df = 1 / (1 + wacc) ** t
        pv = fcff * df
        pv_explicit += pv
        forecast.append(ForecastYear(
            year=base.year + i + 1, revenue=rev, ebit=ebit, ebit_margin=margin,
            nopat=nopat, da=da, capex=capex, d_nwc=d_nwc, fcff=fcff,
            discount_factor=df, pv_fcff=pv,
        ))

    last = forecast[-1]
    g = drivers.terminal_growth
    if wacc <= g:
        raise ValueError(f"WACC ({wacc:.2%}) must exceed terminal growth ({g:.2%}).")

    # Terminal reinvestment tied to growth and ROIC (Damodaran consistency):
    # in perpetuity, growth must be *funded*, so reinvestment rate = g / ROIC.
    # This prevents the classic error of assuming perpetual growth with no
    # reinvestment (which implies infinite incremental returns on capital).
    ic = base.invested_capital or (base.total_debt + base.total_equity - base.cash_and_sti)
    ic_term = ic * (last.revenue / base.revenue) if (ic and base.revenue) else ic
    roic_term = (last.nopat / ic_term) if ic_term else wacc
    roic_term = max(roic_term, wacc)                    # floor: growth at least earns its cost
    reinvest_rate = min(max(g / roic_term, 0.0), 0.85) if roic_term > 0 else 0.0
    nopat_next = last.nopat * (1 + g)
    fcff_terminal = nopat_next * (1 - reinvest_rate)
    tv_gordon = fcff_terminal / (wacc - g)

    tv_exit = None
    if exit_multiple is not None:
        ebitda_n = last.ebit + last.da
        tv_exit = ebitda_n * exit_multiple

    tv = tv_gordon
    t_last = drivers.horizon - (0.5 if mid_year else 0.0)
    # terminal value is a year-end figure -> discount at full final period
    df_tv = 1 / (1 + wacc) ** (drivers.horizon if not mid_year else drivers.horizon - 0.5)
    pv_tv = tv * df_tv

    ev = pv_explicit + pv_tv
    net_debt = data.net_debt
    minority = base.minority_interest
    equity_value = ev - net_debt - minority + non_operating_assets
    shares = data.shares_diluted
    vps = equity_value / shares if shares else 0.0
    upside = (vps / data.price - 1) if data.price else 0.0

    return DCFResult(
        forecast=forecast, tv_gordon=tv_gordon, tv_exit=tv_exit, pv_tv=pv_tv,
        pv_explicit=pv_explicit, enterprise_value=ev, net_debt=net_debt,
        minority=minority, equity_value=equity_value, shares=shares,
        value_per_share=vps, upside=upside, price=data.price, wacc=wacc,
        terminal_growth=g, tv_pct_of_ev=(pv_tv / ev if ev else 0.0),
        scenario=drivers.label, exit_multiple=exit_multiple,
    )


def sensitivity_grid(
    data: CompanyData, drivers: DriverSet, base_wacc: float,
    wacc_range: float = 0.015, g_range: float = 0.010, steps: int = 5,
) -> dict:
    """2-D sensitivity of value-per-share: WACC (rows) x terminal g (cols)."""
    import copy
    waccs = [base_wacc + (i - steps // 2) * (wacc_range / (steps // 2)) for i in range(steps)]
    gs = [drivers.terminal_growth + (j - steps // 2) * (g_range / (steps // 2)) for j in range(steps)]
    grid = []
    for w in waccs:
        row = []
        for gg in gs:
            d = copy.deepcopy(drivers)
            d.terminal_growth = gg
            try:
                res = run_dcf(data, d, w)
                row.append(res.value_per_share)
            except ValueError:
                row.append(None)
        grid.append(row)
    return {"waccs": waccs, "growths": gs, "grid": grid}


# --------------------------------------------------------------------------- #
#  Diagnostics & reverse DCF — the Wall-Street cross-checks
# --------------------------------------------------------------------------- #
def model_diagnostics(data: CompanyData, drivers, dcf, wacc: float) -> dict:
    """Implied returns, terminal-multiple cross-checks and reinvestment sanity."""
    last = dcf.forecast[-1]
    term_ebitda = last.ebit + last.da
    # terminal value expressed as implied multiples (sell-side sanity check)
    tv = dcf.tv_gordon
    implied_ev_ebitda = tv / term_ebitda if term_ebitda else None
    implied_fcf_mult = tv / (last.fcff * (1 + drivers.terminal_growth)) if last.fcff else None

    # steady-state invested capital & ROIC
    ic = data.latest.invested_capital
    if not ic:
        ic = data.latest.total_debt + data.latest.total_equity - data.latest.cash_and_sti
    roic_now = (data.latest.ebit * (1 - drivers.tax_rate)) / ic if ic else None
    # terminal ROIC: NOPAT_terminal / invested capital grown with the business
    ic_term = ic * (last.revenue / data.latest.revenue) if ic and data.latest.revenue else None
    roic_term = last.nopat / ic_term if ic_term else None

    # reinvestment rate and fundamental (self-funding) growth check.
    # Terminal reinvestment is g/ROIC by construction (see run_dcf), so the
    # self-funding growth equals the terminal growth — the model is consistent.
    g = drivers.terminal_growth
    roic_floor = max(roic_term, wacc) if roic_term else wacc
    reinvest_rate = min(max(g / roic_floor, 0.0), 0.85) if roic_floor > 0 else None
    fundamental_g = (reinvest_rate * roic_floor) if (reinvest_rate is not None and roic_floor) else None

    flags = []
    if implied_ev_ebitda is not None:
        cur_ev_ebitda = (data.market_cap + data.net_debt) / (data.latest.ebit + data.latest.depreciation_amort) \
            if (data.latest.ebit + data.latest.depreciation_amort) else None
        if cur_ev_ebitda:
            flags.append(("Terminal EV/EBITDA vs today",
                          f"{implied_ev_ebitda:.1f}x implied vs {cur_ev_ebitda:.1f}x current",
                          "ok" if implied_ev_ebitda <= cur_ev_ebitda * 1.15 else "rich"))
    if roic_term is not None:
        flags.append(("Terminal ROIC vs WACC",
                      f"{roic_term:.1%} vs {wacc:.1%}",
                      "ok" if roic_term >= wacc else "value-destructive"))
    if dcf.tv_pct_of_ev > 0.80:
        flags.append(("Terminal value share of EV", f"{dcf.tv_pct_of_ev:.0%}", "high"))
    return dict(
        implied_ev_ebitda=implied_ev_ebitda, implied_fcf_mult=implied_fcf_mult,
        roic_now=roic_now, roic_term=roic_term, reinvest_rate=reinvest_rate,
        fundamental_g=fundamental_g, invested_capital=ic, flags=flags,
        term_ebitda=term_ebitda,
    )


def reverse_dcf(data: CompanyData, base_drivers, wacc: float,
                target_price: Optional[float] = None) -> dict:
    """Solve for the parallel shift in revenue growth that reproduces the price.

    Answers: 'what growth is the market pricing in?' Holds margins/reinvestment
    fixed and bisects a uniform add-on to every year's growth (and terminal)
    until the DCF equals the current (or supplied) price.
    """
    import copy
    price = target_price or data.price
    if not price:
        return {}

    def value_at(delta):
        d = copy.deepcopy(base_drivers)
        d.revenue_growth = [g + delta for g in base_drivers.revenue_growth]
        d.terminal_growth = min(base_drivers.terminal_growth + delta * 0.4, wacc - 0.005)
        try:
            return run_dcf(data, d, wacc).value_per_share
        except ValueError:
            return None

    lo, hi = -0.25, 0.50
    v_lo, v_hi = value_at(lo), value_at(hi)
    if v_lo is None or v_hi is None or not (min(v_lo, v_hi) <= price <= max(v_lo, v_hi)):
        # price outside solvable band; report nearest
        return {"solved": False}
    for _ in range(60):
        mid = (lo + hi) / 2
        vm = value_at(mid)
        if vm is None:
            hi = mid
            continue
        if (vm - price) * (value_at(lo) - price) <= 0:
            hi = mid
        else:
            lo = mid
    delta = (lo + hi) / 2
    implied_y1 = base_drivers.revenue_growth[0] + delta
    implied_term = min(base_drivers.terminal_growth + delta * 0.4, wacc - 0.005)
    return {"solved": True, "delta": delta, "implied_y1_growth": implied_y1,
            "implied_terminal_growth": implied_term,
            "base_y1_growth": base_drivers.revenue_growth[0]}
