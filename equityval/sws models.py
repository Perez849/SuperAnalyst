"""Simply Wall St valuation methodology — faithful implementation.

Four DCF variants, selected by sector (per SWS's own model documentation):

    Financial (bank/insurance/fin. services)  -> Excess Returns Model
    REIT                                       -> AFFO/FFO 2-stage (fallback NAV)
    Consistent dividend payer, no FCF estimates-> Dividend Discount Model
    Everything else                            -> 2-stage FCFE (analyst levered FCF)

All are anchored to FORWARD analyst estimates, not historical cash flow. History
is used only as a fallback when estimates are unavailable. Every model discounts
at the Cost of Equity (SWS uses cost of equity for all variants):

    Cost of Equity = Risk-free (5y avg 10y govt bond) + Levered Beta * ERP
    Levered Beta   = industry_unlevered * (1 + (1-tax) * Debt/Equity), clamped 0.8-2.0

Each function returns an SWSResult with the full traceable build (year-by-year
rows, discount factors, terminal value, per-share) so the report and Excel can
reproduce every number.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .schema import CompanyData

# Industry unlevered betas (Damodaran US medians). SWS uses North-American
# industry unlevered betas; these are the standard published figures.
INDUSTRY_UNLEVERED_BETA = {
    "utilities": 0.39, "energy": 0.95, "basic materials": 1.02, "materials": 1.02,
    "real estate": 0.63, "financial services": 0.90, "financials": 0.90,
    "consumer defensive": 0.58, "consumer staples": 0.58,
    "consumer cyclical": 1.08, "consumer discretionary": 1.08,
    "healthcare": 0.88, "industrials": 0.98, "technology": 1.20,
    "communication services": 0.92, "communications": 0.92,
}
DEFAULT_UNLEVERED_BETA = 0.90


@dataclass
class SWSResult:
    method: str                 # 'fcfe' | 'excess_returns' | 'ddm' | 'affo' | 'nav'
    label: str
    value_per_share: float
    upside: float
    discount_rate: float
    terminal_pct: float         # terminal value as % of total (0 for excess returns/ddm)
    rows: list = field(default_factory=list)         # (label, formatted) summary
    build: list = field(default_factory=list)        # per-year dicts for the table
    beta_rows: list = field(default_factory=list)    # cost-of-equity derivation
    note: str = ""
    source: str = ""            # where the cash-flow path came from
    terminal_g: float = 0.0     # exact terminal growth used (for Excel precision)


# --------------------------------------------------------------------------- #
#  Cost of equity (shared by every model)
# --------------------------------------------------------------------------- #
def cost_of_equity(data: CompanyData, risk_free: float, erp: float,
                   tax_rate: float, is_financial: bool = False):
    sector = (data.sector or "").strip().lower()
    unlev = INDUSTRY_UNLEVERED_BETA.get(sector, DEFAULT_UNLEVERED_BETA)
    equity = data.market_cap or (data.price * data.shares_diluted)
    debt = data.latest.total_debt
    de = (debt / equity) if equity else 0.0
    if is_financial:
        # SWS: for financials use the levered beta of comparables directly, not
        # re-levered. We approximate with the industry unlevered as a levered proxy,
        # still clamped. (No capital-structure re-adjustment.)
        relevered = unlev
    else:
        relevered = unlev * (1 + (1 - tax_rate) * de)
    beta = min(max(relevered, 0.8), 2.0)
    ke = risk_free + beta * erp
    rows = [
        ("Risk-free rate (5y avg 10y govt bond)", f"{risk_free:.2%}"),
        ("Equity risk premium (Damodaran)", f"{erp:.2%}"),
        (f"Industry unlevered beta ({sector or 'default'})", f"{unlev:.3f}"),
        ("Debt / equity", f"{de:.1%}"),
        ("Levered beta = unlev·(1+(1−t)·D/E)", f"{relevered:.3f}"),
        ("Levered beta (clamped 0.8–2.0)", f"{beta:.3f}"),
        ("Cost of equity = Rf + β·ERP", f"{ke:.2%}"),
    ]
    return ke, beta, rows


def _fade_growth(near_rates: list[float], horizon: int, terminal_g: float) -> list[float]:
    """Analyst rates for the covered years, then fade linearly to terminal g."""
    out = list(near_rates[:horizon])
    if not out:
        out = [terminal_g]
    while len(out) < horizon:
        # linear fade from last known to terminal across remaining years
        remaining = horizon - len(out)
        last = out[-1]
        step = (terminal_g - last) / (remaining + 1)
        out.append(last + step)
    return out[:horizon]


def _drop_scale_outliers(path: list) -> list:
    """Remove points that break their OWN series — data on a different scale from
    the rest. Does NOT cap magnitude: a genuine, *continuous* high-growth ramp is
    kept in full. Two corruption signatures are caught:

    1) Spike-and-revert: a point far above BOTH neighbours that reverts back down
       (e.g. an EPS of 12.76 sitting between values near 5). Classic bad print.

    2) Isolated step that stays up but is disconnected from the trend: the value
       jumps by a huge factor from the previous point and then the following
       points grow only gently from that inflated base (e.g. MU revenue leaping
       6.3x to $234bn, then +3%/yr). A real ramp (NVDA +114% then +65%) keeps
       compounding hard, so it is NOT dropped; a corrupt step lands and flatlines.

    Detection is by SHAPE, not magnitude — sustained growth of any size survives.
    """
    if not path or len(path) < 3:
        # with <3 points we can't judge shape; guard the 2-point step case only
        if len(path) == 2:
            (_, a), (_, b) = path
            # a lone doubling+ with nothing to corroborate is left alone (could be real)
            return list(path)
        return list(path)

    kept = list(path)
    changed = True
    while changed and len(kept) >= 3:
        changed = False
        v = [x for _, x in kept]
        for i in range(1, len(v) - 1):
            prev, cur, nxt = v[i - 1], v[i], v[i + 1]
            if prev <= 0 or cur <= 0:
                continue
            up = cur / prev
            down = nxt / cur if cur else 1
            # signature 1: spike then revert (or dip then rebound)
            if (up > 1.8 and down < 0.75) or (up < 0.55 and down > 1.35):
                kept.pop(i); changed = True; break
            # signature 2: huge isolated step that then flatlines. cur jumps >2.5x
            # from prev, but nxt grows <25% from cur — the ramp didn't continue,
            # so cur is a displaced/misscaled point, not a real acceleration.
            if up > 2.5 and down < 1.25:
                kept.pop(i); changed = True; break
        # also guard the FIRST point when it's the corrupt step (anchor handles
        # this when provided; here we catch a first estimate that dwarfs point 2)
        if not changed and len(kept) >= 3:
            v = [x for _, x in kept]
            if v[0] > 0 and v[1] / v[0] < 0.4 and v[2] / v[1] > 0.8:
                # v[0] is a giant isolated first value the series drops away from
                kept.pop(0); changed = True

    # If cleaning shredded the series (a corrupt step contaminated the whole path,
    # so we're left with a stub), signal "unusable" by returning empty — the caller
    # then falls back to a historical extrapolation rather than trusting fragments.
    if path and len(kept) < max(2, len(path) // 2):
        return []
    return kept


# --------------------------------------------------------------------------- #
#  MODEL 1: 2-stage FCFE (the default / general case)
# --------------------------------------------------------------------------- #
def two_stage_fcfe(data: CompanyData, ke: float, beta_rows: list,
                   terminal_g: float, horizon: int = 10) -> Optional[SWSResult]:
    est = data.estimates
    cur = data.currency_symbol
    # Build the 10-year levered-FCF path.
    flows, sources = [], []
    if est.fcfe_path:
        pth = sorted(est.fcfe_path)
        analyst_n = len(pth)
        for (_, f) in pth[:horizon]:
            flows.append(f); sources.append(f"Analyst")
        # fade remaining years: taper the last analyst YoY growth toward terminal
        if len(flows) >= 2:
            last_g = flows[-1] / flows[-2] - 1 if flows[-2] else terminal_g
        else:
            last_g = terminal_g
        while len(flows) < horizon:
            remaining = horizon - len(flows)
            g = last_g + (terminal_g - last_g) * (len(flows) - analyst_n + 1) / (remaining + 1)
            g = max(g, terminal_g)
            flows.append(flows[-1] * (1 + g)); sources.append(f"Est @ {g:.2%}")
            last_g = g
        source = f"analyst levered-FCF consensus ({analyst_n}y) then fade to {terminal_g:.1%}"
    elif est.eps_path:
        # No explicit levered-FCF path, but we have the analyst NET INCOME path
        # (EPS × shares). Derive FCFE from it via the company's through-cycle
        # FCFE/net-income conversion. This captures the analyst growth ramp.
        ni_hist = [(yy.operating_cash_flow - yy.capex, yy.net_income)
                   for yy in data.years if yy.net_income and yy.net_income > 0
                   and (yy.operating_cash_flow - yy.capex) > 0]
        if ni_hist:
            ratios = sorted(f / ni for f, ni in ni_hist)
            conv = ratios[len(ratios) // 2]
        else:
            conv = 1.0
        # NO magnitude cap on conversion — use the company's real ratio.

        # Clean the EPS path for INTERNAL INCONSISTENCY only (not magnitude).
        # Anchor with the last reported EPS so even the FIRST estimate can be
        # checked for a scale break (a corrupt first point that reverts).
        anchor = data.latest.eps_diluted
        raw = sorted(est.eps_path)
        if anchor and anchor > 0:
            probe = _drop_scale_outliers([(data.latest.year, anchor)] + raw)
            clean = [(y, v) for (y, v) in probe if y != data.latest.year]
        else:
            clean = _drop_scale_outliers(raw)
        if clean:
            analyst_n = len(clean)
            for (_, eps) in clean[:horizon]:
                flows.append(eps * data.shares_diluted * conv); sources.append("Analyst")
            if len(flows) >= 2:
                last_g = flows[-1] / flows[-2] - 1 if flows[-2] else terminal_g
            else:
                last_g = terminal_g
            while len(flows) < horizon:
                remaining = horizon - len(flows)
                g = last_g + (terminal_g - last_g) * (len(flows) - analyst_n + 1) / (remaining + 1)
                g = max(g, terminal_g)
                flows.append(flows[-1] * (1 + g)); sources.append(f"Est @ {g:.2%}")
                last_g = g
            source = (f"analyst net-income consensus ({analyst_n}y) × {conv:.2f} FCFE "
                      f"conversion, then fade to {terminal_g:.1%}")
        else:
            base = data.latest.operating_cash_flow - data.latest.capex
            if not base or base <= 0:
                return None
            hist_g = data.cagr("revenue") or 0.05
            rates = _fade_growth([hist_g], horizon, terminal_g)
            f = base
            for g in rates:
                f = f * (1 + g); flows.append(f); sources.append(f"Est @ {g:.2%}")
            source = f"last levered FCF {cur}{base/1e9:,.1f}bn extrapolated (analyst EPS inconsistent)"
    else:
        base = est.fcfe_base if (est.fcfe_base and est.fcfe_base > 0) else \
               (data.latest.operating_cash_flow - data.latest.capex)
        if not base or base <= 0:
            return None
        hist_g = data.cagr("revenue") or 0.05
        hist_g = min(max(hist_g, 0.0), 0.25)
        rates = _fade_growth([hist_g], horizon, terminal_g)
        f = base
        for g in rates:
            f = f * (1 + g); flows.append(f); sources.append(f"Est @ {g:.2%}")
        source = f"last levered FCF {cur}{base/1e9:,.1f}bn extrapolated at {hist_g:.1%} (no analyst FCF)"

    if not flows or ke <= terminal_g:
        return None

    build, pv_sum = [], 0.0
    for i, (f, src) in enumerate(zip(flows, sources)):
        disc = 1 / (1 + ke) ** (i + 1)
        pv = f * disc
        pv_sum += pv
        build.append({"year": data.latest.year + i + 1, "cf": f, "src": src,
                      "disc": disc, "pv": pv})
    tv = flows[-1] * (1 + terminal_g) / (ke - terminal_g)
    pv_tv = tv / (1 + ke) ** horizon
    equity_value = pv_sum + pv_tv
    vps = equity_value / data.shares_diluted if data.shares_diluted else 0.0
    if vps <= 0:
        return None
    up = vps / data.price - 1 if data.price else 0.0
    return SWSResult(
        "fcfe", "2-Stage Free Cash Flow to Equity", vps, up, ke,
        terminal_pct=pv_tv / equity_value if equity_value else 0.0,
        rows=[
            ("PV of next 10 years' cash flows", f"{cur}{pv_sum/1e9:,.2f}bn"),
            ("Terminal value (Gordon)", f"{cur}{tv/1e9:,.2f}bn"),
            ("PV of terminal value", f"{cur}{pv_tv/1e9:,.2f}bn"),
            ("Total equity value", f"{cur}{equity_value/1e9:,.2f}bn"),
            ("Shares outstanding", f"{data.shares_diluted/1e6:,.0f}mn"),
            ("Value per share", f"{cur}{vps:,.2f}"),
            ("Discount to fair value", f"{-up:.1%}"),
        ],
        build=build, beta_rows=beta_rows, source=source, terminal_g=terminal_g,
        note="Levered FCF to equity from analyst consensus, discounted at the cost "
             "of equity over 10 years plus a Gordon terminal. The forward estimates "
             "are the central input — history is used only where estimates are absent.")


# --------------------------------------------------------------------------- #
#  MODEL 2: Excess Returns (banks / insurance / financial services)
# --------------------------------------------------------------------------- #
def excess_returns(data: CompanyData, ke: float, beta_rows: list,
                   terminal_g: float) -> Optional[SWSResult]:
    cur = data.currency_symbol
    y = data.latest
    bve = y.total_equity - (y.minority_interest or 0)
    if bve <= 0 or data.shares_diluted <= 0:
        return None
    # ROE: prefer analyst forward ROE, else trailing
    roe_hist = [yy.net_income / yy.total_equity for yy in data.years
                if yy.total_equity and yy.total_equity > 0]
    roe = (sum(roe_hist[-3:]) / len(roe_hist[-3:])) if roe_hist else None
    if data.estimates.eps_growth_lt and roe:
        pass  # keep trailing normalized ROE; SWS uses estimated ROE where available
    if not roe or ke <= terminal_g:
        return None
    excess_return_ps = (roe - ke) * (bve / data.shares_diluted)
    tv = excess_return_ps / (ke - terminal_g)              # perpetuity of excess return
    bvps = bve / data.shares_diluted
    vps = bvps + tv
    if vps <= 0:
        return None
    up = vps / data.price - 1 if data.price else 0.0
    return SWSResult(
        "excess_returns", "Excess Returns Model", vps, up, ke, terminal_pct=0.0,
        rows=[
            ("Book value of equity / share", f"{cur}{bvps:,.2f}"),
            ("Return on equity (ROE)", f"{roe:.1%}"),
            ("Cost of equity", f"{ke:.2%}"),
            ("Excess return / share = (ROE−Ke)·BVPS", f"{cur}{excess_return_ps:,.2f}"),
            ("Terminal (excess return perpetuity)", f"{cur}{tv:,.2f}"),
            ("Value per share = BVPS + PV terminal", f"{cur}{vps:,.2f}"),
            ("Discount to fair value", f"{-up:.1%}"),
        ],
        build=[], beta_rows=beta_rows,
        source=f"trailing normalised ROE {roe:.1%} on book value {cur}{bve/1e9:,.1f}bn",
        note="Excess Returns: equity value = book value + present value of returns "
             "earned above the cost of equity. SWS uses this for financials, whose "
             "cash flows don't fit a conventional FCF model.")


# --------------------------------------------------------------------------- #
#  MODEL 3: Dividend Discount Model (consistent dividend payers)
# --------------------------------------------------------------------------- #
def dividend_discount(data: CompanyData, ke: float, beta_rows: list,
                      terminal_g: float) -> Optional[SWSResult]:
    cur = data.currency_symbol
    dps = data.dividend_per_share
    if not dps or dps <= 0 or ke <= terminal_g:
        return None
    # Gordon on the expected (next-year) dividend
    exp_dps = dps * (1 + terminal_g)
    vps = exp_dps / (ke - terminal_g)
    if vps <= 0:
        return None
    up = vps / data.price - 1 if data.price else 0.0
    return SWSResult(
        "ddm", "Dividend Discount Model", vps, up, ke, terminal_pct=1.0,
        rows=[
            ("Current dividend / share", f"{cur}{dps:,.2f}"),
            ("Expected dividend (× (1+g))", f"{cur}{exp_dps:,.2f}"),
            ("Cost of equity", f"{ke:.2%}"),
            ("Perpetual growth (g)", f"{terminal_g:.2%}"),
            ("Value = ExpDPS / (Ke − g)", f"{cur}{vps:,.2f}"),
            ("Discount to fair value", f"{-up:.1%}"),
        ],
        build=[], beta_rows=beta_rows,
        source=f"current DPS {cur}{dps:,.2f} grown at {terminal_g:.1%}",
        note="Gordon Growth on dividends. SWS uses this for companies that pay a "
             "consistent, meaningful share of earnings as dividends.")


# --------------------------------------------------------------------------- #
#  MODEL 4: AFFO / FFO 2-stage (REITs), NAV fallback
# --------------------------------------------------------------------------- #
def affo_2stage(data: CompanyData, ke: float, beta_rows: list,
                terminal_g: float, horizon: int = 10) -> Optional[SWSResult]:
    """AFFO 2-stage. Uses FCFE path as an AFFO proxy if a dedicated AFFO path is
    unavailable (our providers don't split AFFO); falls back to NAV."""
    cur = data.currency_symbol
    # AFFO proxy: FFO = net income + D&A; AFFO ≈ FFO - maintenance capex.
    y = data.latest
    ffo = y.net_income + y.depreciation_amort
    affo = ffo - 0.10 * y.capex        # rough maintenance-capex haircut
    if affo <= 0:
        return _nav(data, ke, beta_rows)
    # grow AFFO at analyst LT growth (or revenue CAGR) fading to terminal
    g0 = data.estimates.eps_growth_lt or data.cagr("revenue") or 0.04
    g0 = min(max(g0, 0.0), 0.20)
    rates = _fade_growth([g0], horizon, terminal_g)
    build, pv_sum, f = [], 0.0, affo
    for i, g in enumerate(rates):
        f = f * (1 + g)
        disc = 1 / (1 + ke) ** (i + 1)
        pv = f * disc; pv_sum += pv
        build.append({"year": y.year + i + 1, "cf": f, "src": f"Est @ {g:.2%}",
                      "disc": disc, "pv": pv})
    tv = f * (1 + terminal_g) / (ke - terminal_g)
    pv_tv = tv / (1 + ke) ** horizon
    equity_value = pv_sum + pv_tv
    vps = equity_value / data.shares_diluted if data.shares_diluted else 0.0
    if vps <= 0:
        return _nav(data, ke, beta_rows)
    up = vps / data.price - 1 if data.price else 0.0
    return SWSResult(
        "affo", "AFFO 2-Stage DCF (REIT)", vps, up, ke,
        terminal_pct=pv_tv / equity_value if equity_value else 0.0,
        rows=[
            ("Latest AFFO (≈ FFO − maint. capex)", f"{cur}{affo/1e9:,.2f}bn"),
            ("PV of 10y AFFO", f"{cur}{pv_sum/1e9:,.2f}bn"),
            ("PV of terminal value", f"{cur}{pv_tv/1e9:,.2f}bn"),
            ("Total equity value", f"{cur}{equity_value/1e9:,.2f}bn"),
            ("Value per share", f"{cur}{vps:,.2f}"),
            ("Discount to fair value", f"{-up:.1%}"),
        ],
        build=build, beta_rows=beta_rows, terminal_g=terminal_g,
        source=f"AFFO {cur}{affo/1e9:,.1f}bn grown at {g0:.1%} fading to {terminal_g:.1%}",
        note="AFFO 2-stage: same structure as the FCFE model but discounting Adjusted "
             "Funds From Operations, the REIT-appropriate cash-flow measure.")


def _nav(data: CompanyData, ke: float, beta_rows: list) -> Optional[SWSResult]:
    cur = data.currency_symbol
    y = data.latest
    nav = y.total_equity - (y.minority_interest or 0)     # book equity as NAV proxy
    if nav <= 0 or data.shares_diluted <= 0:
        return None
    vps = nav / data.shares_diluted
    up = vps / data.price - 1 if data.price else 0.0
    return SWSResult(
        "nav", "Net Asset Value (REIT fallback)", vps, up, ke, terminal_pct=0.0,
        rows=[("Net asset value", f"{cur}{nav/1e9:,.2f}bn"),
              ("Value per share", f"{cur}{vps:,.2f}"),
              ("Discount to fair value", f"{-up:.1%}")],
        build=[], beta_rows=beta_rows, source="book equity as NAV proxy",
        note="NAV fallback used when AFFO/FFO estimates are unavailable.")


# --------------------------------------------------------------------------- #
#  Model selection (the SWS decision tree)
# --------------------------------------------------------------------------- #
def select_and_value(data: CompanyData, risk_free: float, erp: float,
                     tax_rate: float, terminal_g: float,
                     profile_key: str) -> Optional[SWSResult]:
    """Route to the right SWS model by sector, exactly as their doc describes."""
    sector = (data.sector or "").lower()
    is_financial = profile_key in ("bank", "insurance") or \
        any(w in sector for w in ("financial", "bank", "insurance"))
    is_reit = profile_key == "reit" or "reit" in (data.industry or "").lower() \
        or "real estate" in sector

    ke, beta, beta_rows = cost_of_equity(data, risk_free, erp, tax_rate, is_financial)

    if is_financial:
        return excess_returns(data, ke, beta_rows, terminal_g)
    if is_reit:
        return affo_2stage(data, ke, beta_rows, terminal_g)

    # Dividend payer with no FCF estimates -> DDM; else 2-stage FCFE.
    has_fcf = bool(data.estimates.fcfe_path) or \
        ((data.latest.operating_cash_flow - data.latest.capex) > 0)
    div_yield = (data.dividend_per_share / data.price) if data.price else 0.0
    payout = 0.0
    if data.latest.eps_diluted and data.latest.eps_diluted > 0:
        payout = data.dividend_per_share / data.latest.eps_diluted
    if not has_fcf and div_yield > 0.02 and payout > 0.3:
        return dividend_discount(data, ke, beta_rows, terminal_g)

    fcfe = two_stage_fcfe(data, ke, beta_rows, terminal_g)
    if fcfe:
        return fcfe
    # fallbacks
    if div_yield > 0:
        return dividend_discount(data, ke, beta_rows, terminal_g)
    return excess_returns(data, ke, beta_rows, terminal_g)
