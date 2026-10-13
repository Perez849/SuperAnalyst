"""Assemble the sector-aware research note (standalone HTML, Investment Clock design)."""
from __future__ import annotations

from datetime import date

from jinja2 import Template

from . import charts, design, theme


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



TEMPLATE = Template(r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ d.ticker }} — Equity Research · SuperAnalyst</title>
<style>{{ design_css|safe }}
.hero-tiles{display:none}
.family-w{font-family:var(--mono);font-size:11px;color:rgba(251,249,243,.5)}
.st{font-family:var(--mono);font-size:9.5px;letter-spacing:.06em;text-transform:uppercase;color:var(--gold);border:1px solid rgba(217,185,120,.35);border-radius:99px;padding:0 7px;margin-left:6px}
.st.bad{color:#E3A596;border-color:rgba(227,165,150,.4)}
.buy-item.off .nm{text-decoration:line-through;color:rgba(251,249,243,.45)}
</style></head><body>
{%- macro head(eyebrow, title, lede=None) -%}
<div class="section-head"><div class="eyebrow">{{ eyebrow }}</div><h2>{{ title }}</h2>{% if lede %}<p class="cap">{{ lede }}</p>{% endif %}</div>
{%- endmacro -%}

<header class="top"><div class="wrap top-inner">
  <a class="brand" href="{{ library_href or '#top' }}">{{ brand|safe }}<span><span class="brand-word">SuperAnalyst</span><br><span class="brand-tag">VALUATION · LENSES · EVIDENCE</span></span></a>
  <nav class="top-nav"><a href="#verdict">Verdict</a><a href="#lenses">Lenses</a><a href="#quality">Earnings quality</a>{% if dcf %}<a href="#dcf">DCF</a>{% endif %}<a href="#risks">Risks</a></nav>
  <div class="top-actions">{% if library_href %}<a class="ghost" href="{{ library_href }}">← Library</a>{% endif %}<button class="pdf-btn" type="button" onclick="window.print()">⬇ Save as PDF</button></div>
</div></header>

<section class="hero" id="top"><div class="wrap hero-grid">
  <div>
    <div class="eyebrow hero-eyebrow">Independent valuation · {{ d.sector }}{% if d.industry %} · {{ d.industry }}{% endif %}</div>
    <h1 class="phase-name">{{ d.name|e }} <span class="tk">{{ d.ticker }}</span></h1>
    <p class="phase-tie {{ rating_dir }}">{{ rating }}{% if tr.rated %} · 12M target {{ fmt_ps(tr.target) }} ({{ spct(tr.upside,0) }}){% else %} · indicative value {{ fmt_ps(tr.fair_value) }}{% endif %}</p>
    <p class="phase-window">{{ report_date }} · 12-month horizon · {{ spec.label }} · confidence {{ tr.confidence }}</p>
    <p class="phase-why">{{ thesis[0]|safe }}</p>
    <div class="conf-block">
      {% for l in tr.lenses %}{% if l.eff_weight > 0 %}
      <div class="conf-row{% if loop.first %} lead{% endif %}"><span class="nm">{{ l.label }}</span>
        <span class="conf-bar"><i class="{{ 'int' if l.family=='intrinsic' else ('sec' if l.family=='sector' else 'rel') }}" style="width:{{ (l.eff_weight*100)|round|int }}%"></i></span>
        <span class="conf-val">{{ pct(l.eff_weight,0) }}</span></div>
      {% endif %}{% endfor %}
    </div>
    <p class="conf-note">Lens weights after guardrails. {{ tr.confidence_reasons|join('; ') }}.</p>
  </div>
  <figure class="plane-card">
    <div class="plane-top"><h3>Expected return · 12 months</h3><span class="small-cap mono">needle = total return</span></div>
    <p class="cap" style="margin-bottom:10px">The arc is the bear–bull range of the target; the marker <b>S</b> is the Street consensus.</p>
    {{ clock_svg|safe }}
  </figure>
</div></section>

<div class="wrap"><dl class="outlook">
  <div class="item"><dt>Price</dt><dd>{{ fmt_ps(d.price) }}</dd><small>Ke {{ pct(tr.ke,2) }} · {{ d.provider }}</small></div>
  <div class="item"><dt>Fair value today</dt><dd>{{ fmt_ps(tr.fair_value) }}</dd><small>{{ fmt_ps(tr.fair_low) }} – {{ fmt_ps(tr.fair_high) }}</small></div>
  {% if tr.rated %}<div class="item"><dt>12M price target</dt><dd>{{ fmt_ps(tr.target) }}</dd><small>bear {{ fmt_ps(tr.bear) }} · bull {{ fmt_ps(tr.bull) }}</small></div>
  <div class="item"><dt>Expected total return</dt><dd class="{{ rating_dir }}">{{ spct(tr.total_return,0) }}</dd><small>price {{ spct(tr.upside,0) }}{% if tr.dps %} + yield {{ pct(tr.dps/d.price,1) }}{% endif %}</small></div>
  {% else %}<div class="item"><dt>Rating</dt><dd>NOT RATED</dd><small>{{ tr.rating_note }}</small></div>{% endif %}
  <div class="item"><dt>Street consensus</dt>{% if tr.street %}<dd>{{ fmt_ps(tr.street.mean) }}</dd><small>{{ spct(tr.street.upside,0) }}{% if tr.street.n %} · {{ tr.street.n }} analysts{% endif %}</small>{% else %}<dd class="muted">n/a</dd><small>no consensus available</small>{% endif %}</div>
</dl></div>

<div class="rule-wrap" style="margin-top:34px"><hr class="rule"></div>

<section class="section tight" id="thesis"><div class="wrap cols">
  <div>
    {{ head('Investment thesis', 'Why this number') }}
    <div class="lede" style="max-width:none">{% for p in thesis[1:] %}<p style="margin-bottom:14px;font-size:{{ '17px' if loop.first else '15px' }}">{{ p|safe }}</p>{% endfor %}</div>
    <p class="note">{{ spec.rationale }}</p>
  </div>
  <aside class="sidebar" style="margin-top:62px">
    <div class="sidetitle">Key data</div>
    {% for k,v in key_data %}<div class="kv"><span class="k">{{ k }}</span><span class="mono">{{ v }}</span></div>{% endfor %}
  </aside>
</div></section>

<section class="section" id="verdict"><div class="wrap"><div class="buy"><div class="buy-inner">
  <div class="eyebrow">The verdict</div>
  <h2>How the 12-month target is built</h2>
  <p class="lede">Each lens answers <i>what is a share worth?</i> independently. They are weighted by what fits the
     business, filtered by plausibility guardrails, rolled forward at the cost of equity and — where it exists —
     lightly anchored to the Street.</p>
  <div class="buy-cols">
  {% for fam in families %}
    <div class="buy-col"><h4><span>{{ fam.title }}</span><span class="family-w">{{ pct(fam.weight,0) }} of target</span></h4>
    {% for l in fam.lenses %}
      <div class="buy-item{% if l.status=='excluded' %} off{% endif %}"><div><span class="nm">{{ l.label }}</span>
        {% if l.status=='excluded' %}<span class="st bad">excluded</span>{% elif l.status=='winsorized' %}<span class="st bad">winsorised</span>{% elif l.status_note %}<span class="st">down-weighted</span>{% endif %}
        <span class="tickers"><span class="tick">{{ fmt_ps(l.low) }} – {{ fmt_ps(l.high) }}</span></span></div>
        <div class="wt">{{ fmt_ps(l.value) }}<br><span class="family-w">{{ pct(l.eff_weight,0) }}</span></div></div>
    {% endfor %}</div>
  {% endfor %}
  </div>
  <div class="total">
    <div><span class="k">Fair value today</span><div class="v">{{ fmt_ps(tr.fair_value) }}</div></div>
    <div style="text-align:right"><span class="k">{{ 'Published 12-month target' if tr.rated else 'Not rated — indicative only' }}</span>
      <div class="v">{{ fmt_ps(tr.target if tr.rated else tr.fair_value) }}{% if tr.rated %}<small class="{{ rating_dir }}">{{ spct(tr.upside,0) }}</small>{% endif %}</div></div>
  </div>
  <p class="buy-foot"><b>The arithmetic.</b> {{ fmt_ps(tr.fair_value) }} × (1 + {{ pct(tr.ke,2) }}){% if tr.dps %} − {{ fmt_ps(tr.dps) }} dividends{% endif %}
    = model target <b>{{ fmt_ps(tr.model_target) }}</b>{% if tr.street %}; Street mean {{ fmt_ps(tr.street.mean) }}
    {% if tr.street_weight>0 %}at {{ pct(tr.street_weight,0) }} weight{% else %}shown for reference (weight 0){% endif %}{% endif %}
    → published <b>{{ fmt_ps(tr.target) }}</b>.</p>
</div></div></div></section>

<section class="section tight"><div class="wrap">
  {{ head('Exhibit 1', 'Value per share by lens, against price, the Street and our target') }}
  <div class="card" style="padding:18px 20px">{{ ff_svg|safe }}</div>
  <div class="two" style="margin-top:22px">
    <div><h3 style="font-size:19px;margin-bottom:8px">Confidence: {{ tr.confidence }}</h3>
      <ul>{% for r in tr.confidence_reasons %}<li>{{ r }}</li>{% endfor %}</ul></div>
    <div><h3 style="font-size:19px;margin-bottom:8px">Guardrails &amp; disclosures</h3>
      {% for g in tr.guardrails %}<div class="guard">{{ g }}</div>{% else %}<p class="note">No guardrail intervened: every lens landed in the plausible band and no Street anchor was applied.</p>{% endfor %}
      {% for f in fwd.flags %}<div class="guard">{{ f }}</div>{% endfor %}</div>
  </div>
</div></section>

<section class="section tight" id="lenses"><div class="wrap">
  {{ head('Por dentro · Inside', 'The lenses in detail', 'Relative lenses apply a target multiple to forward numbers; the DCF values the cash flows; sector lenses use the model that fits the business. Every input is shown so any number can be challenged.') }}
  <div class="lenses">
  {% for l in tr.lenses %}
    <article class="lens"><header><h4>{{ l.label }}<span class="fam">{{ l.family }}</span></h4>
      <span class="tag {{ 'warn' if l.status=='excluded' else ('med' if (l.status!='ok' or l.status_note) else 'ok') }}">{{ 'excluded' if l.status=='excluded' else ('adjusted' if (l.status!='ok' or l.status_note) else pct(l.eff_weight,0) + ' weight') }}</span></header>
      <div class="body"><div class="big mono" style="font-family:var(--serif)">{{ fmt_ps(l.value) }}</div>
        <div class="rng">{{ fmt_ps(l.low) }} – {{ fmt_ps(l.high) }}{% if l.status_note %} · {{ l.status_note }}{% endif %}</div>
        <table><tbody>{% for k,v in l.rows %}<tr><td>{{ k }}</td><td class="mono">{{ v }}</td></tr>{% endfor %}</tbody></table>
        <p class="nt">{{ l.note }}</p></div></article>
  {% endfor %}
  </div>
</div></section>

<section class="section tight" id="quality"><div class="wrap">
  {{ head('Calidad de beneficios · Earnings quality', 'Are the earnings the market is paying for durable?') }}
  <div class="two">
    <div class="tblwrap"><table><tbody>
        <tr><td>Trailing EPS</td><td class="mono">{{ fmt_ps(fwd.eps_ltm) }}</td></tr>
        <tr><td>Consensus EPS FY{{ fwd.fy1_year }}</td><td class="mono">{{ fmt_ps(fwd.eps_fy1) }}</td></tr>
        <tr><td>Consensus EPS FY{{ fwd.fy1_year+1 }}</td><td class="mono">{{ fmt_ps(fwd.eps_fy2) }}</td></tr>
        <tr><td>NTM EPS used</td><td class="mono"><b>{{ fmt_ps(fwd.eps_ntm) }}</b></td></tr>
        <tr><td>Through-cycle (historical average) EPS</td><td class="mono">{{ fmt_ps(fwd.cycle.norm_eps) }}</td></tr>
        <tr><td>Forward ÷ through-cycle</td><td class="mono">{{ ('%.1fx'|format(fwd.cycle.peak_ratio)) if fwd.cycle.peak_ratio else '—' }}</td></tr>
        <tr><td>Durable EPS growth used</td><td class="mono">{{ pct(fwd.growth,1) }}</td></tr>
        <tr><td>Earnings-durability factor on multiples</td><td class="mono">×{{ '%.2f'|format(fwd.cycle.durability) }}</td></tr>
        <tr><td>Basis</td><td>{{ fwd.basis }}</td></tr>
    </tbody></table></div>
    <div>
      <p class="lede" style="font-size:16px"><b>{{ 'Cyclical or in an earnings inflection.' if fwd.cycle.is_cyclical else 'No cyclicality flags.' }}</b>
         {% if fwd.cycle.reasons %}{{ fwd.cycle.reasons|join('; ') }}.{% else %}Revenue and margins show no peak-to-trough pattern in the reported history, so forward earnings are capitalised at the full target multiple.{% endif %}</p>
      <p class="note">Growth source: {{ fwd.growth_src }}. Multiples price <i>durable</i> growth, so a one-year recovery step is never extrapolated, and when forward EPS is far above what the business has historically earned the target multiple is scaled down — the market pays less for peak earnings.</p>
    </div>
  </div>
</div></section>

<section class="section tight" id="clock"><div class="wrap">
  {{ head('Reloj de inversión · Investment Clock', 'Where it sits on the cycle') }}
  <div class="two" style="align-items:center">
    <div style="max-width:320px">{{ wheel_svg|safe }}</div>
    <div>
      <p class="lede" style="font-size:16px"><b>{{ phase_primary_name }}</b>{% if phase_secondary_name %} and <b>{{ phase_secondary_name }}</b>{% endif %}
         are the phases in which {{ d.sector or 'this sector' }} has historically led, on the classic Merrill Lynch Investment Clock sector map
         (growth × inflation, rotating clockwise: Recovery → Overheat → Stagflation → Reflation).</p>
      <p class="note">Illustrative sector affinity, not a call on where the economy is today: this tool reads company fundamentals and consensus,
         not macro data. Use it to ask whether the thesis above needs the cycle to cooperate. The live phase reading lives in the Reloj de inversión project.</p>
    </div>
  </div>
</div></section>

{% if finsum %}
<section class="section tight"><div class="wrap">
  {{ head('Financial summary', 'Multiples at the current price') }}
  <div class="tblwrap"><table><thead><tr><th>{{ d.currency_symbol }}, per share where noted</th>
    {% for c in finsum.cols %}<th>{{ c }}</th>{% endfor %}</tr></thead><tbody>
  {% for label, vals in finsum.rows.items() %}
    <tr><td{% if label in ['growth'] %} style="padding-left:24px" class="muted"{% endif %}>{{ label }}</td>
      {% for v in vals %}<td class="mono">{{ v }}</td>{% endfor %}</tr>
  {% endfor %}</tbody></table></div>
  <p class="note">{{ finsum.note }}</p>
</div></section>
{% endif %}

{% if model_rows %}
<section class="section tight"><div class="wrap">
  {{ head('Modelo', 'Historicals and projected P&L') }}
  <div class="tblwrap"><table><thead><tr><th>Fiscal year</th><th>Revenue</th><th>Growth</th><th>EBIT</th><th>Margin</th>
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
  </tbody></table></div>
  <p class="note">“A” marks figures taken directly from analyst consensus; other forecast rows are the DCF base case with flat interest and the normalised tax rate.</p>
</div></section>
{% endif %}

{% if dcf %}
<section class="section tight" id="dcf"><div class="wrap">
  {{ head('DCF', 'Cross-check — drivers and sensitivity') }}
  <div class="tblwrap"><table class="assum"><thead><tr><th>Driver</th><th>Path</th><th style="text-align:left">Why</th></tr></thead><tbody>
  {% for drv, path, why in assumptions %}
    <tr><td><b>{{ drv }}</b></td><td class="mono" style="white-space:nowrap">{{ path }}</td><td style="text-align:left;font-size:12.5px;line-height:1.5">{{ why }}</td></tr>
  {% endfor %}</tbody></table></div>
  <div class="three" style="margin-top:18px">
    <div class="card" style="padding:14px 16px"><div class="exh" style="margin-top:0">Revenue &amp; FCFF</div>{{ proj_svg|safe }}</div>
    <div class="card" style="padding:14px 16px"><div class="exh" style="margin-top:0">EBIT margin path</div>{{ margin_svg|safe }}</div>
    <div class="card" style="padding:14px 16px"><div class="exh" style="margin-top:0">EV → equity bridge</div>{{ bridge_svg|safe }}</div>
  </div>
  {% if sens_html %}
  <div class="two" style="margin-top:22px">
    <div class="sens-wrap"><div class="exh" style="margin-top:0">DCF value per share · WACC × terminal growth (vs. price)</div>{{ sens_html|safe }}
      <p class="note">Shaded against the current price: green = above, terracotta = below. Outlined cell = base case.</p></div>
    <div>
      {% if returns_comment %}<p class="lede" style="font-size:15px">{{ returns_comment|safe }}</p>{% endif %}
      {% if diagnostics and diagnostics.flags %}<h3 style="font-size:17px;margin:16px 0 6px">Model diagnostics</h3>
      <div class="tblwrap"><table><tbody>{% for k, v, st in diagnostics.flags %}<tr><td>{{ k }}</td><td class="mono">{{ v }}</td>
        <td><span class="tag {{ 'ok' if st=='ok' else 'warn' }}">{{ st }}</span></td></tr>{% endfor %}</tbody></table></div>{% endif %}
    </div>
  </div>
  {% endif %}
</div></section>
{% endif %}

{% if ratios %}
<section class="section tight"><div class="wrap">
  {{ head('Ratios', 'Leverage, coverage and returns') }}
  <div class="tblwrap"><table><thead><tr><th>Metric</th>{% for c in ratios.cols %}<th>{{ c }}</th>{% endfor %}</tr></thead><tbody>
  {% for label, vals in ratios.rows %}
    <tr><td>{{ label }}</td>{% for v in vals %}<td class="mono">{{ v }}</td>{% endfor %}</tr>
  {% endfor %}</tbody></table></div>
</div></section>
{% endif %}

{% if factors %}
<section class="section tight"><div class="wrap">
  {{ head('Factores', 'What moves this stock') }}
  <div class="tblwrap"><table><thead><tr><th style="width:8%">Type</th><th style="width:20%">Factor</th>
    <th style="width:9%">Exposure</th><th style="width:24%;text-align:left">Evidence</th><th style="text-align:left">Why / mechanism</th></tr></thead><tbody>
  {% for f in factors %}
    <tr><td>{{ f.cat }}</td><td><b>{{ f.factor }}</b></td>
    <td><span class="tag {{ 'high' if f.level=='High' else ('med' if f.level=='Medium' else 'low') }}">{{ f.level }}</span></td>
    <td class="mono" style="text-align:left;font-size:11.5px">{{ f.evidence }}</td>
    <td style="text-align:left;font-size:12.5px;line-height:1.5">{{ f.why }}</td></tr>
  {% endfor %}</tbody></table></div>
</div></section>
{% endif %}

{% if catalysts %}
<section class="section tight"><div class="wrap">
  {{ head('Catalizadores', 'What each lever is worth') }}
  <ul>{% for c in catalysts %}<li>{{ c|safe }}</li>{% endfor %}</ul>
</div></section>
{% endif %}

<section class="section tight" id="risks"><div class="wrap">
  {{ head('Riesgos', 'Key risks') }}
  <ul>{% for r in risks %}<li>{{ r }}</li>{% endfor %}</ul>
</div></section>

<div class="foot-bar"><div class="wrap">
  <p class="disclaimer"><b>Methodology &amp; disclaimer.</b> Generated by an automated, sector-aware valuation engine from
    public data ({{ d.provider }}). {{ d.ticker }} was classified as <b>{{ spec.label }}</b>. The 12-month price target
    triangulates several lenses — target multiples on consensus forward earnings (peer/sector-anchored and adjusted for
    durable growth, leverage and earnings durability), a 10-year DCF with decaying growth and mean-reverting margins, and
    sector-specific models — weights them by profile, applies plausibility guardrails, rolls the result forward at the cost
    of equity net of dividends, and lightly anchors it to Street consensus when available. Reference multiples are
    long-run developed-market medians; live peer medians replace them when fetched. Forward numbers come from analyst
    consensus where available and from reported figures otherwise; they are not a substitute for fundamental judgement.
    Nothing here is investment advice, a recommendation, or an offer to transact. Do your own due diligence.</p>
</div></div>
<script>if(location.search.indexOf('print=1')>-1){window.addEventListener('load',function(){setTimeout(function(){window.print()},400)})}</script>
</body></html>""")


def _families(tr):
    """Group lenses for the dark verdict block: relative / intrinsic / sector."""
    titles = {"relative": "Relative \u00b7 multiples", "intrinsic": "Intrinsic \u00b7 cash flows",
              "sector": "Sector models"}
    out = []
    for fam in ("relative", "intrinsic", "sector"):
        ls = [l for l in tr.lenses if l.family == fam]
        if ls:
            out.append({"title": titles[fam], "lenses": ls, "weight": sum(l.eff_weight for l in ls)})
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
                 font_base="../assets/fonts/"):
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
        design_css=design.css(font_base), brand=theme.brand_mark(30), library_href=library_href,
        families=_families(tr),
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
