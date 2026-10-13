"""Assemble the sector-aware research note (standalone HTML, Investment Clock design)."""
from __future__ import annotations

from datetime import date

from . import analysis as A
from . import charts, clockdata, design, notectx, pages as pages_mod, prose, theme
from .pages_template import TEMPLATE


def fmt_money(v, cur="$"):
    if v is None: return "—"
    a = abs(v)
    if a >= 1e12: body = f"{cur}{a/1e12:,.2f}trn"
    elif a >= 1e9: body = f"{cur}{a/1e9:,.2f}bn"
    elif a >= 1e6: body = f"{cur}{a/1e6:,.0f}mn"
    else: body = f"{cur}{a:,.0f}"
    return f"({body})" if v < 0 else body

def fmt_ps(v, cur="$"):
    if v is None: return "—"
    return f"({cur}{abs(v):,.2f})" if v < 0 else f"{cur}{v:,.2f}"

def pct(v, dp=1):
    return "—" if v is None else f"{v*100:.{dp}f}%"

def spct(v, dp=1):
    return "—" if v is None else f"{v*100:+.{dp}f}%"


def derive_rating(u, rated: bool = True):
    """Rating from the 12-month expected total return (price move + dividend yield)."""
    return theme.rating_for(u, rated)


def build_key_data(data, dcf, bd):
    """Right-hand sidebar: the stats box every sell-side note carries."""
    y = data.latest
    cur = data.currency_symbol
    ev = data.market_cap + data.net_debt
    ebitda = y.ebitda or (y.ebit + y.depreciation_amort)
    fcff_ltm = None
    if bd:
        eff = y.effective_tax_rate
        eff = eff if (eff is not None and 0 <= eff <= 0.6) else bd.tax_rate
        fcff_ltm = y.ebit * (1 - eff) + y.depreciation_amort - y.capex - y.change_in_nwc
    rows = [
        ("Market cap", fmt_money(data.market_cap, cur)),
        ("Enterprise value", fmt_money(ev, cur)),
        ("Net debt", fmt_money(data.net_debt, cur)),
        ("Net debt / EBITDA",
         ("net cash" if data.net_debt < 0 else f"{data.net_debt/ebitda:.1f}x") if ebitda else "\u2014"),
        ("EV / EBITDA (LTM)", f"{ev/ebitda:.1f}x" if ebitda else "\u2014"),
        ("P/E (LTM)", f"{data.price/y.eps_diluted:.1f}x" if y.eps_diluted and y.eps_diluted > 0 else "\u2014"),
        ("FCF yield (LTM)", pct(fcff_ltm/ev, 1) if (fcff_ltm and ev) else "\u2014"),
        ("Dividend yield", pct(data.dividend_per_share/data.price, 1) if (data.dividend_per_share and data.price) else "\u2014"),
        ("Beta", f"{data.beta:.2f}" if data.beta else "\u2014"),
        ("Diluted shares", f"{data.shares_diluted/1e6:,.0f}mn"),
    ]
    return rows


def build_finsum(data, dcf, bd):
    """Front-page financial summary & valuation banner: 2 actuals + forecast years,
    with multiples computed AT THE CURRENT PRICE for each year's estimates."""
    if not (dcf and bd):
        return None
    cur = data.currency_symbol
    ev = data.market_cap + data.net_debt
    interest = data.latest.interest_expense
    cols, rows = [], {k: [] for k in
        ["Revenue", "growth", "EBITDA", "EBIT margin", "EPS", "FCFF/share",
         "EV/EBITDA", "P/E", "FCF yield"]}
    hist = data.years[-2:]
    prevrev = data.years[-3].revenue if len(data.years) >= 3 else None
    for y in hist:
        ebitda = y.ebitda or (y.ebit + y.depreciation_amort)
        eff = y.effective_tax_rate
        eff = eff if (eff is not None and 0 <= eff <= 0.6) else bd.tax_rate
        fcff = y.ebit * (1 - eff) + y.depreciation_amort - y.capex - y.change_in_nwc
        cols.append(f"FY{y.year}A")
        rows["Revenue"].append(fmt_money(y.revenue, cur))
        rows["growth"].append(spct(y.revenue/prevrev - 1, 1) if prevrev else "\u2014")
        rows["EBITDA"].append(fmt_money(ebitda, cur))
        rows["EBIT margin"].append(pct(y.ebit_margin, 1))
        rows["EPS"].append(fmt_ps(y.eps_diluted, cur))
        rows["FCFF/share"].append(fmt_ps(fcff/data.shares_diluted, cur))
        rows["EV/EBITDA"].append(f"{ev/ebitda:.1f}x" if ebitda else "\u2014")
        rows["P/E"].append(f"{data.price/y.eps_diluted:.1f}x" if y.eps_diluted > 0 else "\u2014")
        rows["FCF yield"].append(pct(fcff/ev, 1) if ev else "\u2014")
        prevrev = y.revenue
    for f in dcf.forecast[:4]:
        ebitda = f.ebit + f.da
        ni = (f.ebit - interest) * (1 - bd.tax_rate)
        eps = ni / data.shares_diluted
        cols.append(f"FY{f.year}E")
        rows["Revenue"].append(fmt_money(f.revenue, cur))
        rows["growth"].append(spct(f.revenue/prevrev - 1, 1))
        rows["EBITDA"].append(fmt_money(ebitda, cur))
        rows["EBIT margin"].append(pct(f.ebit_margin, 1))
        rows["EPS"].append(fmt_ps(eps, cur))
        rows["FCFF/share"].append(fmt_ps(f.fcff/data.shares_diluted, cur))
        rows["EV/EBITDA"].append(f"{ev/ebitda:.1f}x")
        rows["P/E"].append(f"{data.price/eps:.1f}x" if eps > 0 else "\u2014")
        rows["FCF yield"].append(pct(f.fcff/ev, 1))
        prevrev = f.revenue
    return {"cols": cols, "rows": rows,
            "note": ("Multiples struck at the current price/EV against each year's estimates. "
                     "Forecast EPS approximates net income as (EBIT \u2212 LTM interest) \u00d7 (1\u2212t).")}


def build_catalysts(data, dcf, bd, sens, wacc_res):
    """Quantified value levers: what each lever is worth per share, from the model itself."""
    if not (dcf and sens and bd):
        return []
    cur = data.currency_symbol
    out = []
    grid, waccs, gs = sens["grid"], sens["waccs"], sens["growths"]
    ci, cj = len(waccs)//2, len(gs)//2
    base = grid[ci][cj]
    try:
        dw = (grid[ci-1][cj] - grid[ci+1][cj]) / 2       # per step in wacc
        step_w = (waccs[1]-waccs[0]) * 10000
        out.append(f"<b>Cost of capital:</b> every {step_w:.0f}bps of WACC moves fair value by "
                   f"\u2248{fmt_ps(abs(dw), cur)}/share ({abs(dw)/base:.0%}). Rate path and the "
                   f"equity risk premium are the single biggest swing factor.")
    except (TypeError, IndexError):
        pass
    try:
        dg = (grid[ci][cj+1] - grid[ci][cj-1]) / 2
        step_g = (gs[1]-gs[0]) * 10000
        out.append(f"<b>Terminal growth:</b> {step_g:.0f}bps of perpetuity growth is worth "
                   f"\u2248{fmt_ps(abs(dg), cur)}/share \u2014 the market's read on the company's "
                   f"long-run competitive position.")
    except (TypeError, IndexError):
        pass
    # margin lever: rerun quickly at +100bps exit margin
    try:
        import copy
        from .dcf import run_dcf
        d2 = copy.deepcopy(bd)
        d2.ebit_margin = [m + 0.01 for m in bd.ebit_margin]
        v2 = run_dcf(data, d2, dcf.wacc).value_per_share
        out.append(f"<b>Operating margin:</b> each 100bps of EBIT margin across the forecast is "
                   f"worth \u2248{fmt_ps(abs(v2 - dcf.value_per_share), cur)}/share \u2014 watch "
                   f"pricing power, mix and cost discipline in quarterly prints.")
    except Exception:
        pass
    g1 = dcf.forecast[0].revenue / data.latest.revenue - 1
    out.append(f"<b>Top-line delivery:</b> our base assumes {pct(g1,1)} year-one growth fading to "
               f"{pct(bd.terminal_growth,1)}; sustained beats/misses versus that glide path are the "
               f"cleanest re-rating trigger either way.")
    return out




def build_factor_exposure(data, profile, dcf, bd, sens, diagnostics, reverse, discount_rate):
    """Macro/micro factor sensitivity map: level + numeric evidence + mechanism.
    Levels are scored from the model and the historicals, not asserted."""
    from .sectors import Profile
    cur = data.currency_symbol
    out = []
    y = data.latest

    def add(cat, factor, level, evidence, why):
        out.append(dict(cat=cat, factor=factor, level=level, evidence=evidence, why=why))

    # ---- shared statistics ----
    import math, statistics as st
    def _finite(xs):
        return [x for x in xs if x is not None and isinstance(x, (int, float))
                and math.isfinite(x)]
    growths = []
    for a, b in zip(data.years[:-1], data.years[1:]):
        if a.revenue and math.isfinite(a.revenue) and a.revenue != 0:
            r = b.revenue / a.revenue - 1
            if math.isfinite(r) and abs(r) < 20:   # drop absurd swings from ~0 bases
                growths.append(r)
    g_vol = st.pstdev(growths) if len(growths) >= 2 else None
    margins = _finite([yy.ebit_margin for yy in data.years])
    m_vol = st.pstdev(margins) if len(margins) >= 2 else None
    ebitda = y.ebitda or (y.ebit + y.depreciation_amort)
    lev = data.net_debt / ebitda if ebitda else None
    cov = y.ebit / y.interest_expense if y.interest_expense else None

    # ---- MACRO: interest rates / duration ----
    if dcf and sens:
        grid, waccs = sens["grid"], sens["waccs"]
        ci, cj = len(waccs)//2, len(sens["growths"])//2
        try:
            dw = abs((grid[ci-1][cj] - grid[ci+1][cj]) / 2)
            pctmove = dw / grid[ci][cj]
            step = (waccs[1]-waccs[0]) * 10000
            level = "High" if pctmove > 0.08 else ("Medium" if pctmove > 0.04 else "Low")
            add("Macro", "Interest rates / discount rate", level,
                f"{step:.0f}bps of WACC \u2248 {fmt_ps(dw, cur)}/sh ({pctmove:.0%}); TV = {pct(dcf.tv_pct_of_ev,0)} of EV",
                "Long-duration cash flows: the further out the value sits (terminal-heavy), the more a "
                "shift in rates or the equity risk premium re-prices the stock, independent of operations.")
        except (TypeError, IndexError):
            pass
    elif profile in (Profile.BANK, Profile.INSURANCE):
        add("Macro", "Interest rates (NIM & book)", "High",
            f"Ke {pct(discount_rate,1)}; leverage is the business model",
            "Rates cut both ways: higher rates lift net interest margins but raise the discount on book "
            "value and can stress credit; the curve's shape matters as much as its level.")

    # ---- MACRO: economic cycle ----
    if g_vol is not None:
        level = "High" if (g_vol > 0.08 or profile == Profile.CYCLICAL) else ("Medium" if g_vol > 0.04 else "Low")
        add("Macro", "Economic cycle / demand", level,
            f"Revenue growth volatility \u03c3 = {pct(g_vol,1)} over {len(growths)}y",
            "Historical top-line dispersion is the cleanest read on cyclicality: a stable compounding "
            "base decouples from GDP; a volatile one imports the macro cycle into earnings.")

    # ---- MACRO: inflation / input costs ----
    if m_vol is not None and dcf:
        try:
            import copy
            from .dcf import run_dcf
            d2 = copy.deepcopy(bd); d2.ebit_margin = [m - 0.01 for m in bd.ebit_margin]
            hit = abs(run_dcf(data, d2, dcf.wacc).value_per_share - dcf.value_per_share)
            level = "High" if hit/dcf.value_per_share > 0.05 else ("Medium" if hit/dcf.value_per_share > 0.025 else "Low")
            add("Macro", "Inflation / input costs", level,
                f"\u2212100bps EBIT margin \u2248 \u2212{fmt_ps(hit, cur)}/sh; margin \u03c3 = {pct(m_vol,1)}",
                "Cost pass-through is the test: firms with pricing power hold margin through inflation; "
                "historical margin volatility shows how much of past cost shocks reached the P&L.")
        except Exception:
            pass

    # ---- MACRO: credit / refinancing ----
    if lev is not None and profile not in (Profile.BANK, Profile.INSURANCE):
        if data.net_debt < 0:
            add("Macro", "Credit & refinancing", "Low",
                f"Net cash position; EBIT/interest = {cov:.1f}x" if cov else "Net cash position",
                "A net-cash balance sheet removes refinancing risk and turns higher rates into "
                "interest income rather than a cost.")
        else:
            level = "High" if lev > 3 else ("Medium" if lev > 1.5 else "Low")
            add("Macro", "Credit & refinancing", level,
                f"Net debt/EBITDA = {lev:.1f}x; EBIT/interest = {cov:.1f}x" if cov else f"Net debt/EBITDA = {lev:.1f}x",
                "Leverage converts operating shortfalls into equity stress: the higher the stack, the "
                "more a slowdown or a repricing of debt costs flows straight to the equity holder.")

    # ---- sector-specific macro ----
    if profile == Profile.CYCLICAL:
        add("Macro", "Commodity prices", "High",
            f"Spot margin {pct(y.ebit_margin,0)} vs through-cycle {pct(bd.anchors.get('margin_mean') if bd else None,0)}",
            "Realised prices set margins more than management does; the gap between spot and mid-cycle "
            "margin is the mean-reversion risk embedded in today's earnings.")
    if profile == Profile.REIT:
        add("Macro", "Cap rates & property values", "High",
            f"Ke {pct(discount_rate,1)} vs terminal growth",
            "Asset values move inversely with required yields; a 50\u2013100bps cap-rate expansion "
            "typically outweighs several years of rent growth.")
    if profile == Profile.UTILITY:
        add("Macro", "Regulation & allowed returns", "High",
            "Regulated revenue model",
            "The regulator, not the market, sets the achievable ROE; rate-case outcomes and allowed "
            "WACC resets dominate long-run value.")

    # ---- MICRO: competitive position / moat ----
    if diagnostics and diagnostics.get("roic_term") is not None:
        spread = diagnostics["roic_term"] - discount_rate
        level = "Low" if spread > 0.10 else ("Medium" if spread > 0.02 else "High")
        add("Micro", "Competitive erosion", level,
            f"Terminal ROIC\u2212WACC spread = {spread*10000:,.0f}bps",
            "Excess returns invite entry: the wider the spread, the bigger the prize for competitors "
            "\u2014 but also the bigger the buffer before growth stops creating value. A thin spread "
            "means small competitive slippage flips growth to value destruction.")

    # ---- MICRO: execution vs expectations ----
    if reverse and reverse.get("solved"):
        gap = reverse["base_y1_growth"] - reverse["implied_y1_growth"]
        level = "High" if abs(gap) > 0.03 else ("Medium" if abs(gap) > 0.01 else "Low")
        direction = ("The market expects less than our base \u2014 upside on delivery"
                     if gap > 0 else "The market expects more than our base \u2014 priced for execution")
        add("Micro", "Execution vs expectations", level,
            f"Implied y1 growth {pct(reverse['implied_y1_growth'],1)} vs base {pct(reverse['base_y1_growth'],1)}",
            direction + ". The equity reprices on the gap between delivery and what the tape already "
            "discounts, not on absolute results.")

    # ---- MICRO: capital intensity ----
    if bd:
        cap_da = bd.anchors.get("capex_pct", 0) / bd.anchors.get("da_pct", 1) if bd.anchors.get("da_pct") else None
        if cap_da is not None:
            level = "High" if cap_da > 1.4 else ("Medium" if cap_da > 1.05 else "Low")
            add("Micro", "Capital intensity", level,
                f"Capex/D&A = {cap_da:.2f}x; capex = {pct(bd.anchors.get('capex_pct'),1)} of sales",
                "Above 1x, the business must keep buying its own growth \u2014 FCF conversion stays "
                "hostage to the reinvestment cycle; below 1x, depreciation overstates true capital needs "
                "and cash conversion runs ahead of earnings.")

    # ---- MICRO: pricing power ----
    if m_vol is not None and margins:
        level = "Low" if m_vol < 0.02 else ("Medium" if m_vol < 0.05 else "High")
        add("Micro", "Pricing power / margin stability", level,
            f"EBIT margin \u03c3 = {pct(m_vol,1)} (range {pct(min(margins),0)}\u2013{pct(max(margins),0)})",
            "Stable margins across cycles are the fingerprint of pricing power; wide swings say the "
            "company is a price-taker whose profitability belongs to the environment, not the franchise.")

    return out



def _football_rows(tr, data):
    rows = []
    for l in tr.lenses:
        if l.status == "excluded":
            continue
        rows.append({"label": l.label, "sub": f"{l.eff_weight:.0%} weight", "low": l.low,
                     "high": l.high, "point": l.value, "kind": "lens"})
    if tr.street:
        lo = tr.street.low or tr.street.mean * 0.85
        hi = tr.street.high or tr.street.mean * 1.15
        rows.append({"label": "Street targets (12m)", "sub": f"{tr.street.n} analysts" if tr.street.n else "consensus",
                     "low": lo, "high": hi, "point": tr.street.mean, "kind": "street"})
    rows.append({"label": "Our 12-month target", "sub": "bear – bull", "low": tr.bear,
                 "high": tr.bull, "point": tr.target, "kind": "target"})
    return rows


def build_report(data, profile, spec, wacc, discount_rate, methods, dcf, scenarios,
                 sens, comps, base_drivers, diagnostics, reverse, target, upside, blend, risks,
                 tr, fwd, ref, fwd_model=None, peers=None, library_href=None,
                 font_base="../assets/fonts/", cycle_raw=None):
    cur = data.currency_symbol
    price = data.price
    rating, rdir = derive_rating(tr.total_return, tr.rated)
    yld = tr.dps / price if price else 0.0
    bear_ret = tr.bear / price - 1 + yld
    bull_ret = tr.bull / price - 1 + yld
    street_ret = (tr.street.mean / price - 1 + yld) if tr.street else None
    clock = charts.valuation_clock(
        tr.total_return, bear_ret, bull_ret, street_ret, rating, rdir,
        fmt_ps(tr.target, cur) if tr.rated else "n/a", fmt_ps(price, cur), tr.rated, tr.confidence, view="0 6 360 300")

    football = _football_rows(tr, data)
    ctx = dict(notectx.build(data, profile, spec, wacc, dcf, scenarios, sens, base_drivers, diagnostics, reverse,
                             tr, fwd, ref, fwd_model, peers, cycle_raw, football))
    levers = pages_mod.compute_levers(data, dcf, base_drivers, sens)
    ctx.update(
        clock_svg=clock, key_data=build_key_data(data, dcf, base_drivers), finsum=build_finsum(data, dcf, base_drivers),
        catalysts=build_catalysts(data, dcf, base_drivers, sens, wacc),
        factors=build_factor_exposure(data, profile, dcf, base_drivers, sens, diagnostics, reverse, discount_rate),
        risks=risks, football_rows=football, levers=levers, cycle_raw=cycle_raw, margin_lever=levers.get("margin_ps"),
        ft_raw=A.financial_tables(data, dcf, fwd_model, fwd))
    if dcf:
        sw = pages_mod.SW
        hist = data.years[-4:] if len(data.years) >= 4 else data.years
        ctx["margin_svg_side"] = charts.margin_lines([y.year for y in hist], [y.ebit_margin or 0 for y in hist],
                                                     [f.year for f in dcf.forecast], [f.ebit_margin for f in dcf.forecast], sw, 158)
        ctx["proj_svg_side"] = charts.projection([f.year for f in dcf.forecast], [f.revenue for f in dcf.forecast],
                                                 [f.fcff for f in dcf.forecast], cur, sw, 168)
        ctx["evbridge_svg_side"] = charts.ev_bridge(dcf.pv_explicit, dcf.pv_tv, dcf.net_debt, dcf.minority, dcf.equity_value, cur, sw, 170)
        ctx["sens_html"] = charts.sensitivity_table(sens, price, cur) if sens else ""

    cyc = clockdata.cycle_view(data.sector, data.industry, data.ticker, cycle_raw) if cycle_raw else None
    facts = prose.build_facts(data, profile, spec, wacc, dcf, scenarios, sens, base_drivers, diagnostics, reverse, tr, fwd, ref,
                              fwd_model, peers, cyc, rating, rdir, ctx)
    pages = pages_mod.compose(facts)
    report_date = date.today().strftime("%d %b %Y")
    return TEMPLATE.render(
        design_css=design.css(font_base, doc=True), brand=theme.brand_mark(30), brand_small=theme.brand_mark(15), library_href=library_href,
        d=data, pages=pages, rating=rating, rating_dir=rdir, tr=tr, pt_txt=fmt_ps(tr.target if tr.rated else tr.fair_value, cur),
        price_date=getattr(data, "asof", None) or report_date, report_date=report_date,
        fmt_ps=lambda v: fmt_ps(v, cur), spct=spct, pct=pct,
        default_source=f"Source: SuperAnalyst valuation model; {data.provider}; analyst consensus. Methodology and disclosures on page {len(pages)}.")
