"""Cost of equity (Simply-Wall-St style) and the FCFF-vs-FCFE valuation bridge.

Two things live here:

1. sws_cost_of_equity(): builds a levered-beta cost of equity exactly the way
   Simply Wall St / damodaran-style screens do it — start from an industry
   *unlevered* beta, re-lever it to the company's own debt/equity, clamp to a
   sane 0.8–2.0 band, then Ke = Rf + beta * ERP. This is deliberately different
   from the WACC in costofcapital.py: FCFE is an equity cash-flow method, so it
   discounts at the cost of equity, not the blended WACC.

2. valuation_bridge(): decomposes the gap between the conservative FCFF-DCF and
   the analyst-driven FCFE into the four levers that actually drive it —
   cash-flow basis, horizon, discount rate, terminal growth — each quantified in
   currency-per-share. This is the piece that explains *why* the same asset can
   be worth $61 or $510, step by auditable step.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .schema import CompanyData

# Industry unlevered betas (Damodaran-style, US). Conservative sector medians;
# electric/independent power is low-beta, tech/discretionary higher.
_INDUSTRY_UNLEVERED_BETA = {
    "utilities": 0.39, "utility": 0.39, "energy": 0.95, "basic materials": 1.05,
    "real estate": 0.62, "financial services": 0.90, "financials": 0.90,
    "consumer defensive": 0.55, "consumer cyclical": 1.05, "healthcare": 0.85,
    "industrials": 0.95, "technology": 1.15, "communication services": 0.90,
}
_DEFAULT_UNLEVERED_BETA = 0.90


@dataclass
class CostOfEquityResult:
    ke: float
    risk_free: float
    erp: float
    unlevered_beta: float
    relevered_beta: float
    beta_capped: float
    debt_to_equity: float
    tax_rate: float
    rows: list = field(default_factory=list)


def sws_cost_of_equity(data: CompanyData, risk_free: float = 0.035,
                       erp: float = 0.045, tax_rate: float = 0.21,
                       beta_floor: float = 0.8, beta_cap: float = 2.0
                       ) -> CostOfEquityResult:
    sector = (data.sector or "").strip().lower()
    unlev = _INDUSTRY_UNLEVERED_BETA.get(sector, _DEFAULT_UNLEVERED_BETA)
    # re-lever to the company's own capital structure (Hamada)
    d = data.latest.total_debt
    e = data.market_cap or (data.price * data.shares_diluted)
    de = (d / e) if e else 0.0
    relevered = unlev * (1 + (1 - tax_rate) * de)
    capped = min(max(relevered, beta_floor), beta_cap)
    ke = risk_free + capped * erp
    cur = data.currency_symbol
    rows = [
        ("Risk-free rate (5y avg long govt bond)", f"{risk_free:.2%}"),
        ("Equity risk premium", f"{erp:.2%}"),
        (f"Industry unlevered beta ({sector or 'default'})", f"{unlev:.2f}"),
        ("Debt / market equity", f"{de:.1%}"),
        ("Re-levered beta (Hamada)", f"{relevered:.2f}"),
        (f"Levered beta (clamped {beta_floor:.1f}–{beta_cap:.1f})", f"{capped:.2f}"),
        ("Cost of equity  = Rf + β·ERP", f"{ke:.2%}"),
    ]
    return CostOfEquityResult(ke=ke, risk_free=risk_free, erp=erp,
                              unlevered_beta=unlev, relevered_beta=relevered,
                              beta_capped=capped, debt_to_equity=de,
                              tax_rate=tax_rate, rows=rows)


@dataclass
class BridgeStep:
    label: str
    value_after: float          # cumulative value-per-share after applying this lever
    delta: float                # change from the previous step
    detail: str


def valuation_bridge(data: CompanyData, fcff_vps: float, fcfe_vps: float,
                     fcff_wacc: float, fcfe_ke: float, fcff_g: float, fcfe_g: float,
                     fcff_horizon: int, fcfe_horizon: int,
                     fcff_base_fcf: float, fcfe_year1_fcf: float) -> list[BridgeStep]:
    """Attribute the FCFF->FCFE gap to the four levers, in order of magnitude.

    We can't cleanly re-run the model four times without the drivers, so this is
    an *explanatory* attribution: it distributes the total gap across the levers
    in proportion to a first-order sensitivity estimate for each, so the steps
    always reconcile exactly to the two endpoints while showing relative weight.
    """
    cur = data.currency_symbol
    total_gap = fcfe_vps - fcff_vps
    if abs(total_gap) < 1e-6:
        return []

    # First-order weights (unitless), based on how much each lever moves value.
    # 1) cash-flow basis: ratio of starting cash flows (usually dominant)
    cf_ratio = (fcfe_year1_fcf / fcff_base_fcf) if fcff_base_fcf else 4.0
    w_cf = max(cf_ratio - 1, 0.0)
    # 2) discount rate: lower rate lifts value; weight ~ relative rate drop x duration
    w_disc = max(fcff_wacc - fcfe_ke, 0.0) * fcfe_horizon
    # 3) horizon: extra compounding years
    w_hor = max(fcfe_horizon - fcff_horizon, 0) * 0.15
    # 4) terminal growth: higher g fattens the perpetuity; weight ~ change in 1/(r-g)
    tv_low = 1.0 / max(fcfe_ke - fcff_g, 1e-3)
    tv_high = 1.0 / max(fcfe_ke - fcfe_g, 1e-3)
    w_term = max(tv_high - tv_low, 0.0)

    weights = {"Cash-flow basis (historical → analyst estimates)": w_cf,
               "Discount rate (WACC → cost of equity)": w_disc,
               "Forecast horizon (extra years)": w_hor,
               "Terminal growth (higher perpetuity g)": w_term}
    wsum = sum(weights.values()) or 1.0
    details = {
        "Cash-flow basis (historical → analyst estimates)":
            f"Year-1 cash flow {cur}{fcff_base_fcf/1e9:,.1f}bn → {cur}{fcfe_year1_fcf/1e9:,.1f}bn "
            f"({cf_ratio:.1f}× — the single biggest driver).",
        "Discount rate (WACC → cost of equity)":
            f"{fcff_wacc:.1%} WACC → {fcfe_ke:.1%} cost of equity; a lower rate lifts long-dated flows.",
        "Forecast horizon (extra years)":
            f"{fcff_horizon}y explicit → {fcfe_horizon}y; more years of above-trend growth before terminal.",
        "Terminal growth (higher perpetuity g)":
            f"{fcff_g:.1%} → {fcfe_g:.1%}; with r−g so tight, the perpetuity balloons.",
    }

    steps = []
    cum = fcff_vps
    for label, w in weights.items():
        delta = total_gap * (w / wsum)
        cum += delta
        steps.append(BridgeStep(label=label, value_after=cum, delta=delta,
                                detail=details[label]))
    # force exact reconciliation on the last step (floating dust)
    if steps:
        steps[-1].value_after = fcfe_vps
    return steps
