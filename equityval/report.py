"""Assemble the sector-aware research note (standalone HTML, Investment Clock design)."""
from __future__ import annotations

from datetime import date

from jinja2 import Template

from . import charts, theme


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


def build_thesis(data, spec, tr, fwd, dcf, reverse, rating):
    cur = data.currency_symbol
    y = data.latest
    used = [l for l in tr.lenses if l.eff_weight > 0]
    names = ", ".join(l.label for l in used) or "no lens"
    paras = []

    if tr.rated:
        direction = ("undervalued" if tr.total_return > 0.05 else
                     "overvalued" if tr.total_return < -0.05 else "fairly valued")
        p1 = (f"We rate <b>{data.name} ({data.ticker})</b> <b>{rating}</b> with a 12-month price target of "
              f"<b>{fmt_ps(tr.target, cur)}</b> — a {spct(tr.upside, 0)} move from "
              f"{fmt_ps(data.price, cur)}"
              + (f" and a {spct(tr.total_return, 0)} total return including the dividend" if tr.dps else "")
              + f". The shares look {direction} on {len(used)} lens{'es' if len(used) != 1 else ''}: {names}. "
              f"Their weighted fair value today is <b>{fmt_ps(tr.fair_value, cur)}</b>, rolled forward at the "
              f"{pct(tr.ke, 1)} cost of equity.")
    else:
        p1 = (f"We do <b>not rate {data.name} ({data.ticker})</b>: {tr.rating_note}. The indicative value of "
              f"{fmt_ps(tr.fair_value, cur)} per share is shown for reference only and should not be read "
              f"as a call against the current price of {fmt_ps(data.price, cur)}.")
    paras.append(p1)

    growth = data.cagr("revenue")
    paras.append(
        f"{data.name} generated {fmt_money(y.revenue, cur)} of revenue at a {pct(y.ebit_margin,0)} EBIT margin "
        f"in the latest fiscal year, having compounded the top line at "
        f"{pct(growth,1) if growth is not None else 'n/a'} over the historical window. Market capitalisation "
        f"stands at {fmt_money(data.market_cap, cur)} with {fmt_money(abs(data.net_debt), cur)} of net "
        f"{'debt' if data.net_debt >= 0 else 'cash'}.")

    if fwd.eps_ntm:
        base = (f"Consensus EPS of {fmt_ps(fwd.eps_fy1, cur)}"
                + (f" and {fmt_ps(fwd.eps_fy2, cur)}" if fwd.eps_fy2 else "")
                + f" gives an NTM figure of {fmt_ps(fwd.eps_ntm, cur)}, i.e. {data.price/fwd.eps_ntm:.1f}x at "
                  f"today's price." if fwd.eps_ntm > 0 else
                f"Consensus EPS is negative (\u2212{cur}{abs(fwd.eps_ntm):,.2f}), so earnings-based lenses do not apply.")
        if fwd.cycle.durability < 0.999:
            base += (f" Because forward earnings are {fwd.cycle.peak_ratio:.1f}x what the business has earned "
                     f"through the cycle, we scale target multiples by {fwd.cycle.durability:.2f} — the "
                     f"market pays less for peak earnings, and so do we.")
        paras.append(base)

    if tr.street:
        st = tr.street
        rel = "above" if tr.model_target > st.mean else "below"
        p = (f"For context, the Street's mean 12-month target is {fmt_ps(st.mean, cur)} "
             f"({spct(st.upside, 0)}{', ' + str(st.n) + ' analysts' if st.n else ''}). Our model-only target of "
             f"{fmt_ps(tr.model_target, cur)} sits {abs(tr.divergence):.0%} {rel} it")
        if tr.street_weight > 0:
            p += (f"; the published target gives the consensus a {tr.street_weight:.0%} weight, a deliberate "
                  f"hedge against model error that we disclose rather than hide.")
        else:
            p += "; the published target is purely model-driven."
        paras.append(p)

    if dcf and reverse and reverse.get("solved"):
        paras.append(
            f"A reverse DCF shows the market is discounting year-one revenue growth of "
            f"{pct(reverse['implied_y1_growth'],1)} against our {pct(reverse['base_y1_growth'],1)} base — "
            + ("the price demands less than we model." if reverse["base_y1_growth"] > reverse["implied_y1_growth"]
               else "the price already discounts more than we model."))
    return paras



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


def build_ratios(data, bd):
    """Historical credit & returns ratios."""
    cur = data.currency_symbol
    hist = data.years[-4:] if len(data.years) >= 4 else data.years
    cols = [f"FY{y.year}A" for y in hist]
    def row(fn, fmt):
        out = []
        for y in hist:
            try:
                v = fn(y)
                out.append(fmt(v) if v is not None else "\u2014")
            except ZeroDivisionError:
                out.append("\u2014")
        return out
    ic = lambda y: (y.total_debt + y.total_equity - y.cash_and_sti)
    tax = bd.tax_rate if bd else 0.25
    rows = [
        ("Net debt / EBITDA", row(lambda y: (y.total_debt - y.cash_and_sti)/y.ebitda if y.ebitda else None, lambda v: f"{v:.1f}x")),
        ("EBIT / interest", row(lambda y: y.ebit/y.interest_expense if y.interest_expense else None, lambda v: f"{v:.1f}x")),
        ("ROE", row(lambda y: y.net_income/y.total_equity if y.total_equity else None, lambda v: pct(v,1))),
        ("ROIC (NOPAT/IC)", row(lambda y: y.ebit*(1-tax)/ic(y) if ic(y) else None, lambda v: pct(v,1))),
        ("FCF conversion (FCFF/NOPAT)", row(lambda y: (y.ebit*(1-tax)+y.depreciation_amort-y.capex-y.change_in_nwc)/(y.ebit*(1-tax)) if y.ebit else None, lambda v: pct(v,0))),
        ("Capex / D&A", row(lambda y: y.capex/y.depreciation_amort if y.depreciation_amort else None, lambda v: f"{v:.2f}x")),
    ]
    return {"cols": cols, "rows": rows}


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
            f"ROIC\u2212WACC spread = {spread*10000:,.0f}bps",
            "Excess returns invite entry: the wider the spread, the bigger the prize for competitors "
            "\u2014 but also the bigger the buffer before growth stops creating value. A thin spread "
            "means small competitive slippage flips growth to value destruction.")

    # ---- MICRO: execution vs expectations ----
    if reverse and reverse.get("solved"):
        gap = reverse["base_y1_growth"] - reverse["implied_y1_growth"]
        level = "High" if abs(gap) > 0.03 else ("Medium" if abs(gap) > 0.01 else "Low")
        direction = ("Market expects LESS than our base \u2014 upside on delivery"
                     if gap > 0 else "Market expects MORE than our base \u2014 priced for execution")
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



TEMPLATE = Template(r"""{%- macro colors(t) -%}
body{background:{{t.bg}};color:{{t.ink}}}
a{color:{{t.brass}}}
.eyebrow,.muted,.note,.tile .k,.kv .k,th,.sub,.scale,.axis,.tag.neutral{color:{{t.muted}}}
.topline{color:{{t.muted}}}
.masthead{border-top:3px solid {{t.brass}}}
h1 .tk{color:{{t.muted}}}
h2.sec{color:{{t.brass}};border-bottom:1px solid {{t.hair}}}
h2.sec .num{color:{{t.muted}}}
.card,.tile,.sidebar,.lens,.callout{background:{{t.surface}};border:1px solid {{t.hair}};box-shadow:{{t.shadow}}}
.callout{border-left:3px solid {{t.brass}}}
.profiletag{border:1px solid {{t.brass}};color:{{t.brass}}}
th{border-bottom:1px solid {{t.hair}}} td{border-bottom:1px solid {{t.hair}}}
tr.total td{border-top:1px solid {{t.ink}}}
tr.hist td{background:{{t.surface2}};color:{{t.muted}}}
tr.divider td{border-bottom:1px solid {{t.brass}}}
tr.off td{color:{{t.muted}};text-decoration:line-through;text-decoration-color:{{t.hair}}}
.kv{border-bottom:1px solid {{t.hair}}}
.pill.up{background:{{t.up}};color:#06130D} .pill.down{background:{{t.down}};color:#1B0705} .pill.flat{background:{{t.flat}};color:#0A0F1C}
.up{color:{{t.up}}} .down{color:{{t.down}}} .flat{color:{{t.flat}}}
.tag.ok,.tag.low{background:{{t.ok_bg}};color:{{t.up}}} .tag.warn,.tag.high{background:{{t.bad_bg}};color:{{t.down}}}
.tag.med{background:{{t.warn_bg}};color:{{t.brass}}} .tag.neutral{background:{{t.surface2}}}
.fam{border:1px solid {{t.hair}};color:{{t.muted}}}
.bar-w{background:{{t.surface2}}} .bar-w i{background:{{t.brass}}}
.guard{background:{{t.warn_bg}};border-left:3px solid {{t.brass}}}
.disc{color:{{t.muted}};border-top:1px solid {{t.hair}}}
.pdfbtn{background:{{t.brass}};color:{{t.bg}}}
/* dial */
.dial .tick{stroke:{{t.hair}};stroke-width:1} .dial .tick-major{stroke:{{t.muted}};stroke-width:1.6}
.dial .band{fill:none;stroke-width:15;stroke-linecap:butt}
.dial .b-down2{stroke:{{t.down}}} .dial .b-down{stroke:{{t.down}};opacity:.55} .dial .b-flat{stroke:{{t.flat}};opacity:.7}
.dial .b-up{stroke:{{t.up}};opacity:.6} .dial .b-up2{stroke:{{t.up}}}
.dial .range{fill:none;stroke:{{t.brass}};stroke-width:5;stroke-linecap:round;opacity:.95}
.dial .scale{fill:{{t.muted}};font:600 9.5px {{ font_sans }}}
.dial .street{fill:{{t.brass}}} .dial .street-t{fill:{{t.brass}}}
.dial .hand{stroke-width:4;stroke-linecap:round} .dial .hand-up{stroke:{{t.up}}} .dial .hand-down{stroke:{{t.down}}} .dial .hand-flat{stroke:{{t.ink}}}
.dial .hub-ring{fill:none;stroke:{{t.brass}};stroke-width:1.2} .dial .hub{fill:{{t.surface}}}
.dial .hub-k{fill:{{t.muted}};font:700 7.5px {{ font_sans }};letter-spacing:.14em}
.dial .hub-v{fill:{{t.ink}};font:600 25px {{ font_serif }}}
.dial .hub-r{font:800 11px {{ font_sans }};letter-spacing:.14em}
.dial .hub-up{fill:{{t.up}}} .dial .hub-down{fill:{{t.down}}} .dial .hub-flat{fill:{{t.muted}}}
.dial .hub-s{fill:{{t.muted}};font:500 9px {{ font_mono }}}
/* phase wheel */
.wheel .seg{stroke:{{t.bg}};stroke-width:2}
.wheel .seg-recovery{fill:{{t.recovery}}} .wheel .seg-overheat{fill:{{t.overheat}}}
.wheel .seg-stagflation{fill:{{t.stagflation}}} .wheel .seg-reflation{fill:{{t.reflation}}}
.wheel .seg.lit{opacity:1} .wheel .seg.lit2{opacity:.55} .wheel .seg.dim{opacity:.16}
.wheel .ph-n{font:800 11px {{ font_sans }};letter-spacing:.1em;fill:#08101C}
.wheel .ph-s,.wheel .ph-a{font:500 8.5px {{ font_sans }};fill:#08101C}
.wheel .dim{fill:{{t.muted}}}
.wheel .wheel-hub{fill:{{t.surface}};stroke:{{t.hair}}} .wheel .wheel-arrow{fill:none;stroke:{{t.brass}};stroke-width:2.2}
.wheel .wheel-head{fill:{{t.brass}}} .wheel .wheel-c{fill:{{t.muted}};font:700 9px {{ font_sans }};letter-spacing:.2em}
/* football field + minis */
.ff .grid,.mini .grid{stroke:{{t.hair}};stroke-width:1} .mini .sep{stroke-dasharray:3 3}
.ff .axis,.mini .axis{fill:{{t.muted}};font:500 9.5px {{ font_mono }}}
.ff .lbl{fill:{{t.ink}};font:600 11.5px {{ font_sans }}} .ff .lbl-street,.ff .lbl-target{fill:{{t.brass}}}
.ff .sub{fill:{{t.muted}};font:500 9.5px {{ font_sans }}}
.ff .bar-lens{fill:{{t.reflation}};opacity:.28;stroke:{{t.reflation}}} .ff .bar-street{fill:{{t.brass}};opacity:.22;stroke:{{t.brass}}}
.ff .bar-target{fill:{{t.up}};opacity:.22;stroke:{{t.up}}} .ff .pt-lens{fill:{{t.reflation}}} .ff .pt-street{fill:{{t.brass}}} .ff .pt-target{fill:{{t.up}}}
.ff .val,.mini .val{fill:{{t.ink}};font:600 10.5px {{ font_mono }}}
.ff .v-price{stroke:{{t.down}};stroke-width:1.6;stroke-dasharray:5 4} .ff .v-price-t{fill:{{t.down}};font:700 10px {{ font_sans }}}
.ff .v-target{stroke:{{t.up}};stroke-width:1.8} .ff .v-target-t{fill:{{t.up}};font:700 10px {{ font_sans }}}
.mini .b-pos{fill:{{t.reflation}}} .mini .b-neg{fill:{{t.down}}} .mini .b-tot{fill:{{t.brass}}}
.mini .b-rev{fill:{{t.reflation}}} .mini .b-fcf{fill:{{t.brass}}} .mini .k-rev{fill:{{t.reflation}}} .mini .k-fcf{fill:{{t.brass}}}
.mini .l-act{fill:none;stroke:{{t.ink}};stroke-width:2.2} .mini .l-est{fill:none;stroke:{{t.brass}};stroke-width:2.2;stroke-dasharray:5 3}
.mini .k-act{fill:{{t.ink}}} .mini .k-est{fill:{{t.brass}}}
table.sens th{background:{{t.surface2}}} table.sens td{border:1px solid {{t.bg}}}
table.sens td.up2{background:{{t.up}};color:#06130D} table.sens td.up{background:{{t.ok_bg}};color:{{t.up}}}
table.sens td.flat{background:{{t.surface2}}} table.sens td.down{background:{{t.bad_bg}};color:{{t.down}}} table.sens td.down2{background:{{t.down}};color:#1B0705}
table.sens td.base{outline:2px solid {{t.brass}};outline-offset:-2px;font-weight:800}
{%- endmacro -%}
<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ d.ticker }} — Equity Research · Investment Clock</title>
<style>
  *{box-sizing:border-box}
  @page{size:A4;margin:11mm 9mm}
  body{margin:0;font-family:{{ font_sans }};font-size:14px;line-height:1.55;-webkit-print-color-adjust:exact;print-color-adjust:exact}
  .wrap{max-width:1000px;margin:0 auto;padding:40px 36px 80px}
  .serif{font-family:{{ font_serif }}} .mono{font-family:{{ font_mono }};font-variant-numeric:tabular-nums}
  .eyebrow{font-size:10.5px;letter-spacing:.18em;text-transform:uppercase;font-weight:700}
  h1{font-size:38px;line-height:1.05;margin:.12em 0 .1em;font-weight:600;letter-spacing:-.01em}
  h1 .tk{font-size:20px;letter-spacing:.04em}
  h3{font-size:13.5px;margin:22px 0 6px;font-weight:700}
  h2.sec{font-size:11.5px;letter-spacing:.18em;text-transform:uppercase;font-weight:800;margin:46px 0 14px;padding-bottom:9px}
  h2.sec .num{margin-right:10px;font-weight:600}
  .masthead{padding-top:14px}
  .topline{display:flex;justify-content:space-between;align-items:baseline;font-size:11.5px}
  .hero{display:grid;grid-template-columns:1fr 340px;gap:30px;align-items:center;margin-top:18px}
  .tiles{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;margin-top:18px}
  .tile{padding:13px 16px;border-radius:10px}
  .tile .k{font-size:9.5px;letter-spacing:.14em;text-transform:uppercase;font-weight:700}
  .tile .v{font-size:25px;font-weight:600;margin-top:3px;line-height:1.15}
  .tile .s{font-size:11px;margin-top:2px;opacity:.8}
  .pill{display:inline-block;padding:4px 14px;border-radius:3px;font-weight:800;font-size:12.5px;letter-spacing:.1em}
  .profiletag{display:inline-block;padding:3px 10px;font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;font-weight:700;border-radius:3px;margin-top:10px}
  .dial,.wheel{width:100%;height:auto;display:block}
  p{margin:0 0 13px} .lead p:first-child{font-size:15.5px}
  table{width:100%;border-collapse:collapse;font-size:12.5px;margin:6px 0 4px}
  th,td{padding:6px 8px;text-align:right} th:first-child,td:first-child{text-align:left}
  thead th{font-size:10px;letter-spacing:.06em;text-transform:uppercase;font-weight:700}
  tr.total td{font-weight:700} tr.grptop td{border-top:1px solid currentColor}
  .card,.callout{padding:16px 18px;border-radius:10px;margin:12px 0}
  .cols{display:grid;grid-template-columns:1fr 270px;gap:30px}
  .sidebar{padding:12px 16px;border-radius:10px;margin-top:6px;align-self:start}
  .sidetitle{font-size:10px;letter-spacing:.14em;text-transform:uppercase;font-weight:800;margin-bottom:4px}
  .kv{display:flex;justify-content:space-between;padding:5px 0;font-size:12.5px} .kv .mono{font-weight:600}
  .two{display:grid;grid-template-columns:1fr 1fr;gap:22px} .three{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
  .lenses{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}
  .lens{padding:14px 16px;border-radius:10px;break-inside:avoid}
  .lens h4{margin:0;font-size:13.5px} .lens .big{font-size:24px;font-weight:600;margin:4px 0 2px}
  .lens table{font-size:11.5px} .lens td:last-child{text-align:right}
  .fam{display:inline-block;font-size:9px;letter-spacing:.1em;text-transform:uppercase;padding:1px 6px;border-radius:3px;margin-left:6px;font-weight:700}
  .tag{display:inline-block;font-size:9.5px;padding:1px 7px;border-radius:3px;font-weight:700;letter-spacing:.05em;text-transform:uppercase}
  .bar-w{display:inline-block;width:70px;height:6px;border-radius:3px;vertical-align:middle;margin-right:6px} .bar-w i{display:block;height:6px;border-radius:3px}
  .guard{padding:10px 14px;border-radius:6px;margin:6px 0;font-size:12.5px}
  .note{font-size:11.5px;margin-top:6px}
  .src{display:inline-block;font-size:8px;font-weight:800;border:1px solid currentColor;border-radius:2px;padding:0 2px;vertical-align:middle;line-height:1.3}
  .exh{font-size:10px;letter-spacing:.1em;text-transform:uppercase;font-weight:700;margin:16px 0 4px}
  ul{margin:6px 0 13px;padding-left:20px} li{margin:4px 0}
  .disc{font-size:11px;margin-top:44px;padding-top:14px;line-height:1.55}
  table.sens{table-layout:fixed;text-align:center} table.sens td,table.sens th{text-align:center;padding:7px 4px;font-family:{{ font_mono }};font-size:11.5px}
  .pdfbtn{position:fixed;right:20px;bottom:20px;border:none;padding:11px 18px;font-size:13px;font-weight:700;border-radius:6px;cursor:pointer;z-index:99}
  .keep{break-inside:avoid;page-break-inside:avoid} h2.sec,h3{break-after:avoid;page-break-after:avoid}
  .wheelbox{max-width:300px} svg text{font-family:{{ font_sans }}}
  @media(max-width:820px){.hero,.cols,.two,.three,.lenses{grid-template-columns:1fr}.wrap{padding:24px 16px 60px}h1{font-size:30px}.dial{max-width:340px;margin:auto}}
  @media screen{ {{ colors(s) }} }
  @media print{ {{ colors(p) }} .pdfbtn{display:none} .wrap{max-width:100%;padding:0} body{font-size:11px}
    .hero{grid-template-columns:1fr 280px} h1{font-size:30px} .lens,.card,.callout,tr,svg{break-inside:avoid;page-break-inside:avoid}
    thead{display:table-header-group} .pill.up,.pill.down,.pill.flat{color:#fff}
    table.sens td.up2,table.sens td.down2{color:#fff} .wheel .ph-n,.wheel .ph-s,.wheel .ph-a{fill:#fff} }
</style></head><body>
<button class="pdfbtn" onclick="window.print()">Save as PDF</button>
<div class="wrap">
{% set n = namespace(i=0) %}
{%- macro sec(title) -%}{% set n.i = n.i + 1 %}<h2 class="sec"><span class="num">{{ '%02d'|format(n.i) }}</span>{{ title }}</h2>{%- endmacro -%}

  <div class="masthead">
    <div class="topline"><span class="eyebrow">Equity Research · Investment Clock</span>
      <span class="mono">{{ report_date }}</span></div>
    <div class="eyebrow" style="margin-top:20px">{{ d.sector }}{% if d.industry %} · {{ d.industry }}{% endif %}</div>
    <h1 class="serif">{{ d.name|e }} <span class="mono tk">{{ d.ticker }}</span></h1>
    <span class="profiletag">{{ spec.label }}</span>
    <div class="hero">
      <div>
        <div style="display:flex;gap:14px;align-items:center;flex-wrap:wrap">
          <span class="pill {{ rating_dir }}">{{ rating }}</span>
          <span class="muted mono" style="font-size:12px">12-month horizon · confidence <b>{{ tr.confidence }}</b></span>
        </div>
        <div class="tiles">
          {% if tr.rated %}
          <div class="tile"><div class="k">12M price target</div>
            <div class="v mono">{{ fmt_ps(tr.target) }}</div>
            <div class="s mono">bear {{ fmt_ps(tr.bear) }} · bull {{ fmt_ps(tr.bull) }}</div></div>
          <div class="tile"><div class="k">Expected total return</div>
            <div class="v mono {{ rating_dir }}">{{ spct(tr.total_return,0) }}</div>
            <div class="s mono">price {{ spct(tr.upside,0) }}{% if tr.dps %} + yield {{ pct(tr.dps/d.price,1) }}{% endif %}</div></div>
          {% else %}
          <div class="tile"><div class="k">Indicative value</div>
            <div class="v mono muted">{{ fmt_ps(tr.fair_value) }}</div>
            <div class="s">reference only · not a price target</div></div>
          <div class="tile"><div class="k">Expected total return</div>
            <div class="v mono muted">n/a</div>
            <div class="s">{{ tr.rating_note }}</div></div>
          {% endif %}
          <div class="tile"><div class="k">Fair value today</div>
            <div class="v mono">{{ fmt_ps(tr.fair_value) }}</div>
            <div class="s mono">{{ fmt_ps(tr.fair_low) }} – {{ fmt_ps(tr.fair_high) }}</div></div>
          <div class="tile"><div class="k">Street consensus</div>
            {% if tr.street %}<div class="v mono">{{ fmt_ps(tr.street.mean) }}</div>
            <div class="s mono">{{ spct(tr.street.upside,0) }}{% if tr.street.n %} · {{ tr.street.n }} analysts{% endif %}</div>
            {% else %}<div class="v mono muted">n/a</div><div class="s">no consensus available</div>{% endif %}</div>
        </div>
        <div class="note mono" style="margin-top:12px">Price {{ fmt_ps(d.price) }} · Ke {{ pct(tr.ke,2) }} · discount rate {{ pct(discount_rate,2) }} · data: {{ d.provider }}</div>
      </div>
      <div>{{ clock_svg|safe }}</div>
    </div>
  </div>

  <div class="cols">
    <div>
      {{ sec('Investment thesis') }}
      <div class="lead">{% for p in thesis %}<p>{{ p|safe }}</p>{% endfor %}</div>
      <p class="note">{{ spec.rationale }}</p>
    </div>
    <aside class="sidebar">
      <div class="sidetitle">Key data</div>
      {% for k,v in key_data %}<div class="kv"><span class="k">{{ k }}</span><span class="mono">{{ v }}</span></div>{% endfor %}
    </aside>
  </div>

  {{ sec('Valuation summary — what each lens says') }}
  <div class="keep">
    <div class="exh">Exhibit 1 · Value per share by lens vs. price, Street and our 12-month target</div>
    {{ ff_svg|safe }}
  </div>
  <table><thead><tr><th>Lens</th><th>Type</th><th>Fair value today</th><th>Range</th><th>Weight</th><th>Status</th></tr></thead><tbody>
  {% for l in tr.lenses %}
    <tr{% if l.status=='excluded' %} class="off"{% endif %}>
      <td>{{ l.label }}</td><td><span class="fam">{{ l.family }}</span></td>
      <td class="mono">{{ fmt_ps(l.value) }}</td><td class="mono">{{ fmt_ps(l.low) }} – {{ fmt_ps(l.high) }}</td>
      <td class="mono"><span class="bar-w"><i style="width:{{ (l.eff_weight*100)|round|int }}%"></i></span>{{ pct(l.eff_weight,0) }}</td>
      <td>{% if l.status=='ok' and not l.status_note %}<span class="tag ok">used</span>
          {% elif l.status=='excluded' %}<span class="tag warn">excluded</span>
          {% else %}<span class="tag med">{{ 'winsorised' if l.status=='winsorized' else 'down-weighted' }}</span>{% endif %}
          {% if l.status_note %}<div class="note" style="margin:0;text-align:right">{{ l.status_note }}</div>{% endif %}</td></tr>
  {% endfor %}
    <tr class="total grptop"><td>Blended fair value (today)</td><td></td><td class="mono">{{ fmt_ps(tr.fair_value) }}</td>
      <td class="mono">{{ fmt_ps(tr.fair_low) }} – {{ fmt_ps(tr.fair_high) }}</td><td></td><td></td></tr>
    <tr><td>× (1 + Ke) − dividends → model 12-month target</td><td></td><td class="mono">{{ fmt_ps(tr.model_target) }}</td>
      <td></td><td></td><td></td></tr>
    {% if tr.street %}<tr><td>Street mean target{% if tr.street_weight>0 %} <span class="muted">(weight {{ pct(tr.street_weight,0) }})</span>{% endif %}</td><td></td>
      <td class="mono">{{ fmt_ps(tr.street.mean) }}</td>
      <td class="mono">{% if tr.street.low and tr.street.high %}{{ fmt_ps(tr.street.low) }} – {{ fmt_ps(tr.street.high) }}{% endif %}</td><td></td><td></td></tr>{% endif %}
    {% if tr.rated %}<tr class="total grptop"><td>Published 12-month price target</td><td></td><td class="mono">{{ fmt_ps(tr.target) }}</td>
      <td class="mono">{{ fmt_ps(tr.bear) }} – {{ fmt_ps(tr.bull) }}</td><td></td>
      <td class="{{ rating_dir }}"><b>{{ spct(tr.upside,0) }}</b></td></tr>
    {% else %}<tr class="total grptop"><td>No published target — NOT RATED</td><td></td><td class="mono muted">{{ fmt_ps(tr.fair_value) }}</td>
      <td></td><td></td><td><span class="tag neutral">NR</span></td></tr>{% endif %}
  </tbody></table>
  <div class="two" style="margin-top:14px">
    <div>
      <h3>Confidence: {{ tr.confidence }}</h3>
      <ul>{% for r in tr.confidence_reasons %}<li>{{ r }}</li>{% endfor %}</ul>
    </div>
    <div>
      <h3>Guardrails &amp; disclosures</h3>
      {% for g in tr.guardrails %}<div class="guard">{{ g }}</div>{% else %}<p class="note">No guardrail intervened: every lens landed in the plausible band and no Street anchor was applied.</p>{% endfor %}
      {% for f in fwd.flags %}<div class="guard">{{ f }}</div>{% endfor %}
    </div>
  </div>

  {{ sec('The lenses in detail') }}
  <p>Each lens is an independent answer to <i>what is a share worth?</i> Relative lenses apply a target
     multiple to forward numbers; the DCF values the cash flows; sector lenses use the model that fits
     the business. Every input is shown so any number can be challenged.</p>
  <div class="lenses">
  {% for l in tr.lenses %}
    <div class="lens">
      <h4>{{ l.label }} <span class="fam">{{ l.family }}</span></h4>
      <div class="big mono">{{ fmt_ps(l.value) }}</div>
      <div class="note mono" style="margin:0 0 6px">{{ fmt_ps(l.low) }} – {{ fmt_ps(l.high) }} · {{ pct(l.eff_weight,0) }} weight</div>
      <table><tbody>{% for k,v in l.rows %}<tr><td>{{ k }}</td><td class="mono">{{ v }}</td></tr>{% endfor %}</tbody></table>
      <p class="note">{{ l.note }}</p>
    </div>
  {% endfor %}
  </div>

  {{ sec('Earnings quality & cycle') }}
  <div class="two">
    <div>
      <table class="kvt"><tbody>
        <tr><td>Trailing EPS</td><td class="mono">{{ fmt_ps(fwd.eps_ltm) }}</td></tr>
        <tr><td>Consensus EPS FY{{ fwd.fy1_year }}</td><td class="mono">{{ fmt_ps(fwd.eps_fy1) }}</td></tr>
        <tr><td>Consensus EPS FY{{ fwd.fy1_year+1 }}</td><td class="mono">{{ fmt_ps(fwd.eps_fy2) }}</td></tr>
        <tr><td>NTM EPS used</td><td class="mono"><b>{{ fmt_ps(fwd.eps_ntm) }}</b></td></tr>
        <tr><td>Through-cycle (historical average) EPS</td><td class="mono">{{ fmt_ps(fwd.cycle.norm_eps) }}</td></tr>
        <tr><td>Forward ÷ through-cycle</td><td class="mono">{{ ('%.1fx'|format(fwd.cycle.peak_ratio)) if fwd.cycle.peak_ratio else '—' }}</td></tr>
        <tr><td>Durable EPS growth used</td><td class="mono">{{ pct(fwd.growth,1) }}</td></tr>
        <tr><td>Earnings-durability factor on multiples</td><td class="mono">×{{ '%.2f'|format(fwd.cycle.durability) }}</td></tr>
        <tr><td>Basis</td><td>{{ fwd.basis }}</td></tr>
      </tbody></table>
    </div>
    <div>
      <p><b>{{ 'Cyclical or in an earnings inflection.' if fwd.cycle.is_cyclical else 'No cyclicality flags.' }}</b>
         {% if fwd.cycle.reasons %}{{ fwd.cycle.reasons|join('; ') }}.{% else %}Revenue and margins show no peak-to-trough pattern in the reported history, so forward earnings are capitalised at the full target multiple.{% endif %}</p>
      <p class="note">Growth source: {{ fwd.growth_src }}. Multiples price <i>durable</i> growth, so a one-year recovery step is never extrapolated, and when forward EPS is far above what the business has historically earned the target multiple is scaled down — the market pays less for peak earnings.</p>
    </div>
  </div>

  {{ sec('Where it sits on the Investment Clock') }}
  <div class="two" style="align-items:center">
    <div class="wheelbox">{{ wheel_svg|safe }}</div>
    <div>
      <p><b>{{ phase_primary_name }}</b>{% if phase_secondary_name %} and <b>{{ phase_secondary_name }}</b>{% endif %}
         are the phases in which {{ d.sector or 'this sector' }} has historically led, on the classic Merrill Lynch Investment Clock
         sector map (growth × inflation, rotating clockwise: Recovery → Overheat → Stagflation → Reflation).</p>
      <p class="note">Illustrative sector affinity, not a call on where the economy is today: this tool reads company
         fundamentals and consensus, not macro data. Use it to ask whether the thesis above needs the cycle to cooperate.</p>
    </div>
  </div>

  {% if finsum %}
  {{ sec('Financial summary & valuation') }}
  <table><thead><tr><th>{{ d.currency_symbol }}, per share where noted</th>
    {% for c in finsum.cols %}<th>{{ c }}</th>{% endfor %}</tr></thead><tbody>
  {% for label, vals in finsum.rows.items() %}
    <tr {% if label in ['EV/EBITDA'] %}class="grptop"{% endif %}>
      <td{% if label in ['growth'] %} style="padding-left:18px" class="muted"{% endif %}>{{ label }}</td>
      {% for v in vals %}<td class="mono">{{ v }}</td>{% endfor %}</tr>
  {% endfor %}</tbody></table>
  <p class="note">{{ finsum.note }}</p>
  {% endif %}

  {% if model_rows %}
  {{ sec('Financial model — historicals & projected P&L') }}
  <table><thead><tr><th>Fiscal year</th><th>Revenue</th><th>Growth</th><th>EBIT</th><th>Margin</th>
    <th>Net income</th><th>EPS</th></tr></thead><tbody>
  {% for r in model_rows %}{% if r.hist %}
    <tr class="hist"><td class="mono">{{ r.year }}A</td>
    <td class="mono">{{ fmt_money(r.revenue) }}</td><td class="mono">{{ spct(r.growth,1) }}</td>
    <td class="mono">{{ fmt_money(r.ebit) }}</td><td class="mono">{{ pct(r.margin,1) }}</td>
    <td class="mono">{{ fmt_money(r.nopat) }}</td><td class="mono">{{ fmt_ps(r.eps) if r.eps else '—' }}</td></tr>
  {% endif %}{% endfor %}
  {% if fwd_model %}
    <tr class="divider"><td colspan="7"></td></tr>
    {% for f in fwd_model.years %}
    <tr><td class="mono">{{ f.year }}E</td>
    <td class="mono">{{ fmt_money(f.revenue) }}{% if f.revenue_src=='Analyst' %} <span class="src">A</span>{% endif %}</td>
    <td class="mono">{{ spct(f.revenue_growth,1) }}</td>
    <td class="mono">{{ fmt_money(f.ebit) }}</td><td class="mono">{{ pct(f.ebit_margin,1) }}</td>
    <td class="mono">{{ fmt_money(f.net_income) }}</td>
    <td class="mono">{{ fmt_ps(f.eps) }}{% if f.eps_src=='Analyst' %} <span class="src">A</span>{% endif %}</td></tr>
    {% endfor %}
  {% endif %}
  </tbody></table>
  <p class="note">“A” marks figures taken directly from analyst consensus; other forecast rows are the DCF base case with
     flat interest and the normalised tax rate.</p>
  {% endif %}

  {% if dcf %}
  {{ sec('DCF cross-check — drivers & sensitivity') }}
  <table class="assum"><thead><tr><th>Driver</th><th>Path</th><th style="text-align:left">Why</th></tr></thead><tbody>
  {% for drv, path, why in assumptions %}
    <tr><td><b>{{ drv }}</b></td><td class="mono" style="white-space:nowrap">{{ path }}</td><td style="text-align:left;font-size:12px;line-height:1.5">{{ why }}</td></tr>
  {% endfor %}</tbody></table>
  <div class="three" style="margin-top:14px">
    <div class="keep"><div class="exh">Revenue &amp; FCFF</div>{{ proj_svg|safe }}</div>
    <div class="keep"><div class="exh">EBIT margin path</div>{{ margin_svg|safe }}</div>
    <div class="keep"><div class="exh">EV → equity bridge</div>{{ bridge_svg|safe }}</div>
  </div>
  {% if sens_html %}
  <div class="two" style="margin-top:10px">
    <div><div class="exh">Exhibit · DCF value per share, WACC × terminal growth (vs. price)</div>{{ sens_html|safe }}
      <p class="note">Shaded against the current price: green = above, red = below. Outlined cell = base case.</p></div>
    <div>
      {% if returns_comment %}<p>{{ returns_comment|safe }}</p>{% endif %}
      {% if diagnostics and diagnostics.flags %}<h3>Model diagnostics</h3>
      <table><tbody>{% for k, v, st in diagnostics.flags %}<tr><td>{{ k }}</td><td class="mono">{{ v }}</td>
        <td><span class="tag {{ 'ok' if st=='ok' else 'warn' }}">{{ st }}</span></td></tr>{% endfor %}</tbody></table>{% endif %}
    </div>
  </div>
  {% endif %}
  {% endif %}

  {% if ratios %}
  {{ sec('Ratio analysis — leverage, coverage & returns') }}
  <table><thead><tr><th>Metric</th>{% for c in ratios.cols %}<th>{{ c }}</th>{% endfor %}</tr></thead><tbody>
  {% for label, vals in ratios.rows %}
    <tr><td>{{ label }}</td>{% for v in vals %}<td class="mono">{{ v }}</td>{% endfor %}</tr>
  {% endfor %}</tbody></table>
  {% endif %}

  {% if factors %}
  {{ sec('Factor sensitivity map — what moves this stock') }}
  <table><thead><tr><th style="width:8%">Type</th><th style="width:20%">Factor</th>
    <th style="width:9%">Exposure</th><th style="width:24%">Evidence</th><th style="text-align:left">Why / mechanism</th></tr></thead><tbody>
  {% for f in factors %}
    <tr><td>{{ f.cat }}</td><td><b>{{ f.factor }}</b></td>
    <td><span class="tag {{ 'high' if f.level=='High' else ('med' if f.level=='Medium' else 'low') }}">{{ f.level }}</span></td>
    <td class="mono" style="text-align:left;font-size:11.5px">{{ f.evidence }}</td>
    <td style="text-align:left;font-size:12px;line-height:1.5">{{ f.why }}</td></tr>
  {% endfor %}</tbody></table>
  {% endif %}

  {% if catalysts %}
  {{ sec('Catalysts & what each lever is worth') }}
  <ul>{% for c in catalysts %}<li>{{ c|safe }}</li>{% endfor %}</ul>
  {% endif %}

  {{ sec('Key risks') }}
  <ul>{% for r in risks %}<li>{{ r }}</li>{% endfor %}</ul>

  <div class="disc"><b>Methodology &amp; disclaimer.</b> Generated by an automated, sector-aware valuation engine from
    public data ({{ d.provider }}). {{ d.ticker }} was classified as <b>{{ spec.label }}</b>. The 12-month price target
    triangulates several lenses — target multiples on consensus forward earnings (peer/sector-anchored and adjusted for
    durable growth, leverage and earnings durability), a 10-year DCF with decaying growth and mean-reverting margins, and
    sector-specific models — weights them by profile, applies plausibility guardrails, rolls the result forward at the cost
    of equity net of dividends, and lightly anchors it to Street consensus when available. Reference multiples are
    long-run developed-market medians; live peer medians replace them when fetched. Forward numbers come from analyst
    consensus where available and from reported figures otherwise; they are not a substitute for fundamental judgement.
    Nothing here is investment advice, a recommendation, or an offer to transact. Do your own due diligence.</div>
</div></body></html>""")



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
                 tr, fwd, ref, fwd_model=None, peers=None):
    cur = data.currency_symbol
    price = data.price
    rating, rdir = derive_rating(tr.total_return, tr.rated)
    yld = tr.dps / price if price else 0.0
    bear_ret = tr.bear / price - 1 + yld
    bull_ret = tr.bull / price - 1 + yld
    street_ret = (tr.street.mean / price - 1 + yld) if tr.street else None

    clock = charts.valuation_clock(
        tr.total_return, bear_ret, bull_ret, street_ret, rating, rdir,
        fmt_ps(tr.target, cur) if tr.rated else "n/a", fmt_ps(price, cur), tr.rated, tr.confidence)
    ph1, ph2 = theme.phases_for(data.sector, profile.value)
    wheel = charts.phase_wheel(ph1, ph2)
    ff = charts.football_field(_football_rows(tr, data), price, tr.target if tr.rated else None, cur)

    thesis = build_thesis(data, spec, tr, fwd, dcf, reverse, rating)
    assumptions = base_drivers.rationale if base_drivers else None

    # historical + forecast model rows (DCF base case)
    model_rows = []
    if dcf and base_drivers:
        tax = base_drivers.tax_rate
        hist = data.years[-4:] if len(data.years) >= 4 else data.years
        prev = None
        for idx, y in enumerate(hist):
            eff = y.effective_tax_rate
            eff = eff if (eff is not None and 0 <= eff <= 0.6) else tax
            nopat = y.ebit * (1 - eff)
            fcff = nopat + y.depreciation_amort - y.capex - y.change_in_nwc
            growth = (y.revenue / prev.revenue - 1) if prev and prev.revenue else None
            model_rows.append({"year": y.year, "hist": True, "revenue": y.revenue,
                               "growth": growth, "ebit": y.ebit, "margin": y.ebit_margin,
                               "nopat": y.net_income, "eps": y.eps_diluted, "fcff": fcff,
                               "conv": (fcff / nopat if nopat else None), "last_hist": idx == len(hist) - 1})
            prev = y

    returns_comment = ""
    if diagnostics:
        rt, wc = diagnostics.get("roic_term"), discount_rate
        if rt is not None:
            spread = (rt - wc) * 10000
            if rt > wc:
                returns_comment = (f"The business earns <b>{pct(rt,1)}</b> on capital versus a <b>{pct(wc,1)}</b> "
                    f"cost of capital — a positive spread of <b>{spread:.0f}bps</b>, so growth creates value. "
                    f"Self-funding growth of {pct(diagnostics.get('fundamental_g'),1)} (reinvestment "
                    f"{pct(diagnostics.get('reinvest_rate'),0)} × ROIC) frames how much of the terminal growth is "
                    f"organically financed rather than assumed.")
            else:
                returns_comment = (f"The business earns <b>{pct(rt,1)}</b> on capital against a <b>{pct(wc,1)}</b> cost of "
                    f"capital — a negative spread of <b>{abs(spread):.0f}bps</b>. Growth here <b>destroys</b> value, "
                    f"so terminal assumptions deserve scrutiny.")

    key_data = build_key_data(data, dcf, base_drivers)
    finsum = build_finsum(data, dcf, base_drivers)
    ratios = build_ratios(data, base_drivers)
    catalysts = build_catalysts(data, dcf, base_drivers, sens, wacc)
    factors = build_factor_exposure(data, profile, dcf, base_drivers, sens, diagnostics, reverse, discount_rate)

    kw = dict(
        s=theme.SCREEN, p=theme.PRINT, font_sans=theme.FONT_SANS, font_serif=theme.FONT_SERIF,
        font_mono=theme.FONT_MONO,
        key_data=key_data, finsum=finsum, ratios=ratios, catalysts=catalysts, factors=factors,
        fwd_model=fwd_model, d=data, spec=spec, report_date=date.today().strftime("%d %b %Y"),
        rating=rating, rating_dir=rdir, tr=tr, fwd=fwd, thesis=thesis, discount_rate=discount_rate,
        model_rows=model_rows, risks=risks, dcf=dcf, assumptions=assumptions,
        diagnostics=diagnostics, returns_comment=returns_comment,
        clock_svg=clock, wheel_svg=wheel, ff_svg=ff,
        phase_primary_name=theme.PHASE_NAMES[ph1][0],
        phase_secondary_name=theme.PHASE_NAMES[ph2][0] if ph2 else "",
        fmt_money=lambda v: fmt_money(v, cur), fmt_ps=lambda v: fmt_ps(v, cur),
        pct=pct, spct=spct, sens_html="", proj_svg="", margin_svg="", bridge_svg="",
    )
    if dcf:
        hist = data.years[-4:] if len(data.years) >= 4 else data.years
        kw["margin_svg"] = charts.margin_lines(
            [y.year for y in hist], [y.ebit_margin or 0 for y in hist],
            [f.year for f in dcf.forecast], [f.ebit_margin for f in dcf.forecast])
        kw["proj_svg"] = charts.projection(
            [f.year for f in dcf.forecast], [f.revenue for f in dcf.forecast],
            [f.fcff for f in dcf.forecast], cur)
        kw["bridge_svg"] = charts.ev_bridge(dcf.pv_explicit, dcf.pv_tv, dcf.net_debt, dcf.minority,
                                            dcf.equity_value, cur)
        kw["sens_html"] = charts.sensitivity_table(sens, price, cur) if sens else ""
    return TEMPLATE.render(**kw)
