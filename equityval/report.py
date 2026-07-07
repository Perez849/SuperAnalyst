"""Assemble the sector-aware, Wall-Street-detailed research report (standalone HTML)."""
from __future__ import annotations

from datetime import date

from jinja2 import Template

from . import charts
from .schema import CompanyData
from .sectors import Profile


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


def derive_rating(u):
    if u >= 0.20:  return "OVERWEIGHT", "up"
    if u >= 0.05:  return "ADD", "up"
    if u > -0.05:  return "NEUTRAL", "flat"
    if u > -0.20:  return "REDUCE", "down"
    return "UNDERWEIGHT", "down"


_METHOD_ORDER = ["fcff_dcf", "residual_income", "ddm", "pb_roe", "ffo_multiple",
                 "affo_yield", "normalized", "comps"]


def build_thesis(data, spec, methods, target, upside, blend, discount_rate,
                 dcf, diagnostics, reverse):
    cur = data.currency_symbol
    y = data.latest
    primary = max(blend, key=blend.get) if blend else None
    pm = methods.get(primary)
    direction = "undervalued" if upside > 0.05 else ("overvalued" if upside < -0.05 else "fairly valued")
    rating, _ = derive_rating(upside)
    paras = []

    p1 = (f"We initiate our independent valuation of <b>{data.name} ({data.ticker})</b> with a "
          f"<b>{rating}</b> stance and a fair value of <b>{fmt_ps(target, cur)}</b>, "
          f"{spct(upside,0)} against the current {fmt_ps(data.price, cur)}. We frame the company "
          f"under a {spec.label.lower()} approach — the model set that fits how this business "
          f"actually creates value.")
    if pm:
        p1 += (f" The lead method, {pm.label.lower()}, returns {fmt_ps(pm.value_per_share, cur)} "
               f"({spct(pm.upside,0)}); the target is a probability-weighted blend across "
               f"{len(blend)} methods.")
    paras.append(p1)

    growth = data.cagr("revenue")
    p2 = (f"{data.name} generated {fmt_money(y.revenue, cur)} of revenue at a {pct(y.ebit_margin,0)} "
          f"EBIT margin in the latest fiscal year, having compounded the top line at "
          f"{pct(growth,1) if growth else 'n/a'} over the historical window. "
          f"Market capitalisation stands at {fmt_money(data.market_cap, cur)} with "
          f"{fmt_money(abs(data.net_debt), cur)} of net {'debt' if data.net_debt>=0 else 'cash'}, "
          f"and we discount at a {pct(discount_rate,1)} "
          f"{'WACC' if spec.discount=='wacc' else 'cost of equity'}.")
    paras.append(p2)

    if dcf and diagnostics:
        roic_t = diagnostics.get("roic_term")
        creates = (roic_t is not None and roic_t > discount_rate)
        p3 = (f"Our base case carries {pct(dcf.tv_pct_of_ev,0)} of enterprise value in the terminal "
              f"value, implying a terminal EV/EBITDA of "
              f"{diagnostics['implied_ev_ebitda']:.1f}x" if diagnostics.get('implied_ev_ebitda') else
              f"Our base case carries {pct(dcf.tv_pct_of_ev,0)} of enterprise value in the terminal value")
        if roic_t is not None:
            p3 += (f". At maturity the business earns a {pct(roic_t,1)} return on invested capital "
                   f"against a {pct(discount_rate,1)} cost of capital — a "
                   f"{'positive' if creates else 'negative'} spread of "
                   f"{abs(roic_t-discount_rate)*10000:.0f}bps, so incremental growth is "
                   f"{'value-accretive' if creates else 'value-dilutive'} and "
                   f"{'deserves' if creates else 'does not deserve'} a premium multiple.")
        paras.append(p3)

    if reverse and reverse.get("solved"):
        imp = reverse["implied_y1_growth"]; base = reverse["base_y1_growth"]
        gap = "more optimistic" if imp > base else "more conservative"
        paras.append(
            f"Reverse-engineering the current price, the market is discounting roughly "
            f"{pct(imp,1)} near-term revenue growth versus our {pct(base,1)} base assumption — "
            f"the tape is {gap} than our forecast, which is the crux of the {spct(upside,0)} gap to "
            f"fair value.")
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
<title>{{ d.ticker }} — Equity Research</title>
<style>
  :root{--ink:#0E1116;--paper:#FBFBF9;--teal:#0F6466;--up:#1B7A5A;--down:#B23A48;
    --hair:#C9C9C2;--muted:#6B6F76;--gold:#B9892E;--hist:#F1F0EA;}
  *{box-sizing:border-box}
  body{margin:0;background:var(--paper);color:var(--ink);
    font-family:"Helvetica Neue",Arial,system-ui,sans-serif;font-size:14.5px;line-height:1.55;}
  .wrap{max-width:900px;margin:0 auto;padding:48px 42px 80px;}
  .serif{font-family:"Iowan Old Style",Palatino,"Palatino Linotype",Georgia,serif;}
  .mono{font-family:ui-monospace,"SF Mono","Menlo",monospace;font-variant-numeric:tabular-nums;}
  .eyebrow{font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:var(--muted);font-weight:600;}
  h1{font-size:34px;line-height:1.08;margin:.15em 0 .1em;font-weight:600;}
  h2{font-size:12.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--teal);font-weight:700;
    margin:42px 0 12px;padding-bottom:8px;border-bottom:1.5px solid var(--ink);}
  h3{font-size:14.5px;margin:22px 0 4px;font-weight:600;}
  .masthead{border-top:3px solid var(--ink);padding-top:14px;}
  .topline{display:flex;justify-content:space-between;align-items:baseline;font-size:12px;color:var(--muted);}
  .hero{display:flex;gap:10px;flex-wrap:wrap;margin:22px 0 6px;}
  .pill{display:inline-block;padding:5px 14px;border-radius:2px;font-weight:700;font-size:13px;
    letter-spacing:.08em;color:#fff;}
  .pill.up{background:var(--up)} .pill.down{background:var(--down)} .pill.flat{background:var(--muted)}
  .profiletag{display:inline-block;padding:3px 10px;border:1px solid var(--teal);color:var(--teal);
    font-size:11px;letter-spacing:.08em;text-transform:uppercase;font-weight:600;border-radius:2px;margin-top:10px;}
  .stat{flex:1;min-width:140px;border:1px solid var(--hair);padding:11px 14px;background:#fff;}
  .stat .k{font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted)}
  .stat .v{font-size:25px;font-weight:600;margin-top:2px}
  .stat .v.up{color:var(--up)} .stat .v.down{color:var(--down)}
  p{margin:0 0 13px} .lead p:first-child{font-size:16px}
  table{width:100%;border-collapse:collapse;font-size:12.5px;margin:6px 0 4px}
  th,td{padding:6px 8px;text-align:right;border-bottom:1px solid var(--hair)}
  th:first-child,td:first-child{text-align:left}
  thead th{border-bottom:1.5px solid var(--ink);font-size:10.5px;letter-spacing:.05em;
    text-transform:uppercase;color:var(--muted)}
  tr.total td{border-top:1.5px solid var(--ink);font-weight:700;border-bottom:none}
  tr.hist td{background:var(--hist);color:var(--muted)}
  tr.divider td{border-bottom:1.5px solid var(--ink);padding:0;height:0}
  img.chart{width:100%;margin:10px 0 4px;border:1px solid var(--hair);background:#fff}
  .two{display:table;width:100%;table-layout:fixed;border-spacing:22px 0;margin-left:-22px;
    width:calc(100% + 44px);}
  .two>div{display:table-cell;vertical-align:top;}
  .note{font-size:11.5px;color:var(--muted);margin-top:6px}
  ul{margin:6px 0 13px;padding-left:20px} li{margin:3px 0}
  .kv{display:flex;justify-content:space-between;border-bottom:1px solid var(--hair);padding:5px 0;font-size:12.5px}
  .kv .mono{font-weight:600}
  .methodcard{border:1px solid var(--hair);background:#fff;padding:16px 18px;margin:14px 0;}
  .methodcard.primary{border-left:3px solid var(--teal);}
  .assum td:last-child{text-align:left;color:var(--ink);font-size:12px;line-height:1.5}
  .assum td.path{white-space:nowrap;color:var(--teal);font-weight:600}
  .callout{border:1px solid var(--teal);background:#fff;padding:14px 16px;margin:14px 0;
    border-left:3px solid var(--teal);}
  .callout .big{font-size:22px;font-weight:600;}
  .tag{display:inline-block;font-size:10px;padding:1px 7px;border-radius:2px;font-weight:700;
    letter-spacing:.04em;text-transform:uppercase;}
  .tag.ok{background:#E3F0E9;color:var(--up)} .tag.warn{background:#F6E7E3;color:var(--down)}
  .tag.neutral{background:#EDEDE7;color:var(--muted)}
  .cols{display:table;width:100%;table-layout:fixed;border-spacing:0;}
  .cols>div{display:table-cell;vertical-align:top;padding-right:26px;}
  .cols>aside{display:table-cell;vertical-align:top;width:255px;}
  .sidebar{border:1px solid var(--hair);background:#fff;padding:12px 14px;margin-top:24px;}
  .sidetitle{font-size:10.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--teal);
    font-weight:700;border-bottom:1.5px solid var(--ink);padding-bottom:6px;margin-bottom:4px;}
  tr.grptop td{border-top:1.5px solid var(--ink);}
  .exh{font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);
    font-weight:700;margin:14px 0 2px;}
  @media(max-width:760px){.cols,.cols>div,.cols>aside{display:block;width:auto;padding-right:0}}
  .keep{page-break-inside:avoid;}
  .hsp{height:150px;margin-bottom:-150px;}
  .tag.high{background:#F6E7E3;color:var(--down)} .tag.med{background:#F5EEDC;color:var(--gold)}
  .tag.low{background:#E3F0E9;color:var(--up)}
  .disc{font-size:11px;color:var(--muted);margin-top:40px;border-top:1px solid var(--hair);padding-top:14px;line-height:1.5}
  .pdfbtn{position:fixed;right:20px;bottom:20px;background:var(--ink);color:#fff;border:none;padding:11px 18px;
    font-size:13px;font-weight:600;border-radius:3px;cursor:pointer;box-shadow:0 2px 8px rgba(0,0,0,.2);z-index:99;}
  @media(max-width:660px){.two,.two>div{display:block;width:auto;margin-left:0}.wrap{padding:28px 18px 60px}h1{font-size:27px}}
  @media print{.wrap{max-width:100%}body{font-size:11px}.pdfbtn{display:none}h2{margin-top:24px}
    .methodcard,.callout,img.chart{page-break-inside:avoid}tr{page-break-inside:avoid}thead{display:table-header-group}}
</style></head><body>
<button class="pdfbtn" onclick="window.print()">Save as PDF</button>
<div class="wrap">

  <div class="masthead">
    <div class="topline"><span class="eyebrow">Equity Research · Independent Valuation</span>
      <span class="mono">{{ report_date }}</span></div>
    <div class="eyebrow" style="margin-top:18px">{{ d.sector }}{% if d.industry %} · {{ d.industry }}{% endif %}</div>
    <h1 class="serif">{{ d.name }} <span class="mono" style="font-size:22px;color:var(--muted)">{{ d.ticker }}</span></h1>
    <div><span class="profiletag">{{ spec.label }}</span></div>
    <div class="hero">
      <div class="stat"><div class="k">Rating</div><div class="v"><span class="pill {{ rating_dir }}">{{ rating }}</span></div></div>
      <div class="stat"><div class="k">Fair value</div><div class="v mono">{{ fmt_ps(target) }}</div></div>
      <div class="stat"><div class="k">Price</div><div class="v mono">{{ fmt_ps(d.price) }}</div></div>
      <div class="stat"><div class="k">Upside</div>
        <div class="v mono {{ 'up' if upside>=0 else 'down' }}">{{ spct(upside,0) }}</div></div>
    </div>
    <div class="note mono">Discount rate {{ pct(discount_rate,2) }} · data: {{ d.provider }}</div>
  </div>

  <div class="cols">
    <div>
      <h2 style="margin-top:24px">Investment thesis</h2>
      <div class="lead">{% for p in thesis %}<p>{{ p|safe }}</p>{% endfor %}</div>
      <p class="note">{{ spec.rationale }}</p>
    </div>
    <aside class="sidebar">
      <div class="sidetitle">Key data</div>
      {% for k,v in key_data %}<div class="kv"><span>{{ k }}</span><span class="mono">{{ v }}</span></div>{% endfor %}
    </aside>
  </div>

  {% if finsum %}
  <div class="keep"><h2>Financial summary &amp; valuation</h2><div class="hsp"></div></div>
  <table><thead><tr><th>{{ d.currency_symbol }}, per share where noted</th>
    {% for c in finsum.cols %}<th>{{ c }}</th>{% endfor %}</tr></thead><tbody>
  {% for label, vals in finsum.rows.items() %}
    <tr {% if label in ['EV/EBITDA'] %}class="grptop"{% endif %}>
      <td{% if label in ['growth'] %} style="color:var(--muted);padding-left:18px"{% endif %}>{{ label }}</td>
      {% for v in vals %}<td class="mono">{{ v }}</td>{% endfor %}</tr>
  {% endfor %}</tbody></table>
  <p class="note">{{ finsum.note }}</p>
  {% endif %}

  <div class="keep"><div class="keep"><h2>Valuation summary — football field</h2><div class="hsp"></div></div>
  <div class="exh">Exhibit 1 · Valuation football field</div>
  <img class="chart" src="{{ ff_chart }}" alt="Football field"></div>
  <table><thead><tr><th>Method</th><th>Value / share</th><th>Upside</th><th>Weight</th></tr></thead><tbody>
  {% for r in summary_rows %}
    <tr><td>{{ r.label }}</td><td class="mono">{{ fmt_ps(r.value) }}</td>
    <td class="mono {{ 'up' if r.up>=0 else 'down' }}">{{ spct(r.up,0) }}</td>
    <td class="mono">{{ '%.0f'|format(r.weight*100)+'%' if r.weight else '—' }}</td></tr>
  {% endfor %}
    <tr class="total"><td>Blended fair value</td><td class="mono">{{ fmt_ps(target) }}</td>
    <td class="mono {{ 'up' if upside>=0 else 'down' }}">{{ spct(upside,0) }}</td><td></td></tr>
  </tbody></table>

  {% if assumptions %}
  <div class="keep"><h2>Key assumptions & rationale</h2><div class="hsp"></div></div>
  <p>Each forward driver is anchored to history or consensus, sanity-checked for internal
     consistency, and justified below. These are the levers that move the valuation.</p>
  <table class="assum"><thead><tr><th style="width:16%">Driver</th><th style="width:20%">Trajectory</th>
    <th>Rationale</th></tr></thead><tbody>
  {% for drv,path,why in assumptions %}
    <tr><td><b>{{ drv }}</b></td><td class="path mono">{{ path }}</td><td>{{ why }}</td></tr>
  {% endfor %}</tbody></table>
  {% endif %}

  <div class="keep"><div class="keep"><h2>Cost of capital</h2><div class="hsp"></div></div>
  <div class="two"><div>
    {% for k,v in wacc_rows %}<div class="kv"><span>{{ k }}</span><span class="mono">{{ v }}</span></div>{% endfor %}
  </div><div>
    <p class="note">Operative discount rate: <b>{{ pct(discount_rate,2) }}</b>
      ({{ 'WACC' if spec.discount=='wacc' else 'cost of equity — the correct rate for a balance-sheet-driven model' }}).</p>
    <p class="note">Cost of equity via CAPM: Rf + β\u00b7ERP. {% for n in wacc.notes %}{{ n }} {% endfor %}
      Cost of debt from a synthetic rating off interest coverage ({{ wacc.credit_label }}).</p>
  </div></div></div>

  {% if model_rows %}
  <div class="keep"><h2>Financial model — historicals & forecast</h2><div class="hsp"></div></div>
  <div class="keep"><div class="exh">Exhibit 2 · Revenue &amp; free cash flow projection</div>
  <img class="chart" src="{{ proj_chart }}" alt="Projection"></div>
  {% if margins_chart %}<div class="exh">Exhibit 3 · Margin trajectory, actual vs estimate</div>
  <img class="chart" src="{{ margins_chart }}" alt="Margins">{% endif %}
  <table><thead><tr><th>Fiscal year</th><th>Revenue</th><th>Growth</th><th>EBIT</th><th>Margin</th>
    <th>NOPAT</th><th>FCFF</th><th>FCF conv.</th></tr></thead><tbody>
  {% for r in model_rows %}
    <tr class="{{ 'hist' if r.hist else '' }}"><td class="mono">{{ r.year }}{{ 'A' if r.hist else 'E' }}</td>
    <td class="mono">{{ fmt_money(r.revenue) }}</td><td class="mono">{{ spct(r.growth,1) }}</td>
    <td class="mono">{{ fmt_money(r.ebit) }}</td><td class="mono">{{ pct(r.margin,1) }}</td>
    <td class="mono">{{ fmt_money(r.nopat) }}</td><td class="mono">{{ fmt_money(r.fcff) }}</td>
    <td class="mono">{{ pct(r.conv,0) }}</td></tr>
    {% if r.last_hist %}<tr class="divider"><td colspan="8"></td></tr>{% endif %}
  {% endfor %}</tbody></table>
  <p class="note">Shaded rows are reported actuals (A); unshaded are our estimates (E). NOPAT = EBIT × (1 − tax);
     FCFF = NOPAT + D&A − capex − ΔNWC; FCF conversion = FCFF / NOPAT.</p>

  <div class="keep"><h3>Discounted cash flow build</h3><div class="hsp" style="height:110px;margin-bottom:-110px"></div></div>
  <table><thead><tr><th>Year</th><th>FCFF</th><th>Disc. factor</th><th>PV of FCFF</th></tr></thead><tbody>
  {% for f in dcf.forecast %}
    <tr><td class="mono">{{ f.year }}E</td><td class="mono">{{ fmt_money(f.fcff) }}</td>
    <td class="mono">{{ '%.3f'|format(f.discount_factor) }}</td><td class="mono">{{ fmt_money(f.pv_fcff) }}</td></tr>
  {% endfor %}
    <tr class="total"><td>PV of explicit FCFF</td><td></td><td></td><td class="mono">{{ fmt_money(dcf.pv_explicit) }}</td></tr>
  </tbody></table>
  <div class="two" style="margin-top:14px"><div>
    <div class="kv"><span>PV of explicit FCFF</span><span class="mono">{{ fmt_money(dcf.pv_explicit) }}</span></div>
    <div class="kv"><span>PV of terminal value</span><span class="mono">{{ fmt_money(dcf.pv_tv) }}</span></div>
    <div class="kv"><span>Enterprise value</span><span class="mono">{{ fmt_money(dcf.enterprise_value) }}</span></div>
    <div class="kv"><span>− Net debt</span><span class="mono">{{ fmt_money(dcf.net_debt) }}</span></div>
    {% if dcf.minority %}<div class="kv"><span>− Minority interest</span><span class="mono">{{ fmt_money(dcf.minority) }}</span></div>{% endif %}
    <div class="kv"><span><b>Equity value</b></span><span class="mono"><b>{{ fmt_money(dcf.equity_value) }}</b></span></div>
    <div class="kv"><span><b>Value per share</b></span><span class="mono"><b>{{ fmt_ps(dcf.value_per_share) }}</b></span></div>
  </div><div>
    <img class="chart" src="{{ bridge_chart }}" alt="EV bridge" style="margin:0">
  </div></div>

  {% if ratios %}
  <div class="keep"><h2>Ratio analysis — leverage, coverage &amp; returns</h2><div class="hsp"></div></div>
  <table><thead><tr><th>Metric</th>{% for c in ratios.cols %}<th>{{ c }}</th>{% endfor %}</tr></thead><tbody>
  {% for label, vals in ratios.rows %}
    <tr><td>{{ label }}</td>{% for v in vals %}<td class="mono">{{ v }}</td>{% endfor %}</tr>
  {% endfor %}</tbody></table>
  {% endif %}

  <div class="keep"><div class="keep"><h2>Terminal value & implied multiples</h2><div class="hsp"></div></div>
  <div class="two"><div>
    <div class="kv"><span>Terminal value (Gordon, g={{ pct(dcf.terminal_growth,1) }})</span><span class="mono">{{ fmt_money(dcf.tv_gordon) }}</span></div>
    <div class="kv"><span>PV of terminal value</span><span class="mono">{{ fmt_money(dcf.pv_tv) }}</span></div>
    <div class="kv"><span>Terminal value as % of EV</span><span class="mono">{{ pct(dcf.tv_pct_of_ev,0) }}</span></div>
    {% if diagnostics.implied_ev_ebitda %}<div class="kv"><span>Implied terminal EV/EBITDA</span><span class="mono">{{ '%.1f'|format(diagnostics.implied_ev_ebitda) }}x</span></div>{% endif %}
    {% if diagnostics.implied_fcf_mult %}<div class="kv"><span>Implied terminal P/FCF</span><span class="mono">{{ '%.1f'|format(diagnostics.implied_fcf_mult) }}x</span></div>{% endif %}
  </div><div>
    <p class="note">A large terminal value is normal, but it must be defensible. We cross-check the
      Gordon perpetuity against the exit multiple it implies — if the implied terminal EV/EBITDA
      sits far above where the stock trades today, the perpetuity growth is doing too much work.</p>
    {% for label,val,status in diagnostics.flags %}
      <div class="kv"><span>{{ label }}</span><span><span class="mono">{{ val }}</span>
        <span class="tag {{ 'ok' if status=='ok' else ('warn' if status in ['rich','value-destructive'] else 'neutral') }}">{{ status }}</span></span></div>
    {% endfor %}
  </div></div></div>

  <div class="keep"><div class="keep"><h2>Returns analysis — ROIC vs cost of capital</h2><div class="hsp"></div></div>
  <div class="two"><div>
    <div class="kv"><span>Current ROIC</span><span class="mono">{{ pct(diagnostics.roic_now,1) }}</span></div>
    <div class="kv"><span>Terminal ROIC</span><span class="mono">{{ pct(diagnostics.roic_term,1) }}</span></div>
    <div class="kv"><span>Cost of capital (WACC)</span><span class="mono">{{ pct(discount_rate,1) }}</span></div>
    <div class="kv"><span>Reinvestment rate (terminal)</span><span class="mono">{{ pct(diagnostics.reinvest_rate,0) }}</span></div>
    <div class="kv"><span>Implied self-funding growth</span><span class="mono">{{ pct(diagnostics.fundamental_g,1) }}</span></div>
  </div><div>
    <p class="note">{{ returns_comment|safe }}</p>
  </div></div></div>

  {% if reverse and reverse.solved %}
  <div class="keep"><div class="keep"><h2>What the market is pricing in</h2><div class="hsp"></div></div>
  <div class="callout">
    <div>At the current {{ fmt_ps(d.price) }}, a reverse-DCF implies the market is discounting
      <span class="big mono">{{ pct(reverse.implied_y1_growth,1) }}</span> near-term revenue growth
      and <span class="mono">{{ pct(reverse.implied_terminal_growth,1) }}</span> in perpetuity.</div>
    <p class="note" style="margin-top:8px">Our base case assumes {{ pct(reverse.base_y1_growth,1) }} near-term growth.
      {% if reverse.implied_y1_growth < reverse.base_y1_growth %}The market is <b>more conservative</b> than our
      forecast — if the company merely executes to our base plan, the shares re-rate upward.
      {% else %}The market is <b>more optimistic</b> than our forecast — the shares already embed an
      aggressive growth path, leaving little margin for error.{% endif %}</p>
  </div></div>
  {% endif %}

  {% if scenarios %}
  <div class="keep"><h2>Scenario & sensitivity analysis</h2><div class="hsp"></div></div>
  <table><thead><tr><th>Scenario</th><th>Yr-1 growth</th><th>Exit margin</th><th>Terminal g</th>
    <th>Value / share</th><th>Upside</th></tr></thead><tbody>
  {% for s in scen_rows %}
    <tr{% if s.name=='Base' %} class="total"{% endif %}><td>{{ s.name }}</td><td class="mono">{{ spct(s.g1,0) }}</td>
    <td class="mono">{{ pct(s.margin,0) }}</td><td class="mono">{{ pct(s.term,1) }}</td>
    <td class="mono">{{ fmt_ps(s.vps) }}</td>
    <td class="mono {{ 'up' if s.up>=0 else 'down' }}">{{ spct(s.up,0) }}</td></tr>
  {% endfor %}</tbody></table>
  {% if sens_chart %}<div class="exh">Exhibit 4 · Sensitivity heat map</div><img class="chart" src="{{ sens_chart }}" alt="Sensitivity" style="max-width:580px;margin-top:14px">{% endif %}
  {% endif %}
  {% endif %}

  {% for m in method_cards %}
  <div class="keep"><h2>{{ m.label }}</h2><div class="hsp"></div></div>
  <div class="methodcard {{ 'primary' if m.is_primary else '' }}">
    <div class="two"><div>
      {% for k,v in m.rows %}<div class="kv"><span>{{ k }}</span><span class="mono">{{ v }}</span></div>{% endfor %}
    </div><div>
      <p class="note">{{ m.note }}</p>
      {% if m.forecast %}<table style="margin-top:4px"><thead><tr>{% for h in m.fc_head %}<th>{{ h }}</th>{% endfor %}</tr></thead>
      <tbody>{% for row in m.fc_rows %}<tr>{% for c in row %}<td class="mono">{{ c }}</td>{% endfor %}</tr>{% endfor %}</tbody></table>{% endif %}
    </div></div>
  </div>
  {% endfor %}

  {% if comps and comps.multiples %}
  <div class="keep"><h2>Relative valuation — comparable companies</h2><div class="hsp"></div></div>
  <table><thead><tr><th>Multiple</th><th>Peer median</th><th>Implied value / share</th></tr></thead><tbody>
  {% for k,v in comps.multiples.items() %}
    <tr><td>{{ k }}</td><td class="mono">{{ '%.1f'|format(v.median) }}x</td><td class="mono">{{ fmt_ps(v.implied_vps) }}</td></tr>{% endfor %}
  </tbody></table>
  <table style="margin-top:14px"><thead><tr><th>Peer</th><th>EV/EBITDA</th><th>EV/Sales</th><th>P/E</th></tr></thead><tbody>
  {% for p in comps.peers %}<tr><td>{{ p.ticker }}</td>
    <td class="mono">{{ '%.1f'|format(p.ev_ebitda)+'x' if p.ev_ebitda else '—' }}</td>
    <td class="mono">{{ '%.1f'|format(p.ev_sales)+'x' if p.ev_sales else '—' }}</td>
    <td class="mono">{{ '%.1f'|format(p.pe)+'x' if p.pe else '—' }}</td></tr>{% endfor %}
  </tbody></table>
  {% endif %}

  {% if factors %}
  <div class="keep"><h2>Factor sensitivity map — what moves this stock</h2><div class="hsp"></div></div>
  <p>Exposure levels are scored from the model and the historicals, with the mechanism spelled out.</p>
  <table><thead><tr><th style="width:8%">Type</th><th style="width:20%">Factor</th>
    <th style="width:9%">Exposure</th><th style="width:24%">Evidence</th><th>Why / mechanism</th></tr></thead><tbody>
  {% for f in factors %}
    <tr><td>{{ f.cat }}</td><td><b>{{ f.factor }}</b></td>
    <td><span class="tag {{ 'high' if f.level=='High' else ('med' if f.level=='Medium' else 'low') }}">{{ f.level }}</span></td>
    <td class="mono" style="text-align:left;font-size:11.5px">{{ f.evidence }}</td>
    <td style="text-align:left;font-size:12px;line-height:1.5">{{ f.why }}</td></tr>
  {% endfor %}</tbody></table>
  {% endif %}

  {% if catalysts %}
  <div class="keep"><h2>Catalysts &amp; what each lever is worth</h2><div class="hsp"></div></div>
  <ul>{% for c in catalysts %}<li>{{ c|safe }}</li>{% endfor %}</ul>
  {% endif %}

  <div class="keep"><h2>Key risks</h2><div class="hsp"></div></div>
  <ul>{% for r in risks %}<li>{{ r }}</li>{% endfor %}</ul>

  <div class="disc"><b>Methodology & disclaimer.</b> Generated by an automated, sector-aware valuation
    engine from public data ({{ d.provider }}). {{ d.ticker }} was classified as <b>{{ spec.label }}</b>
    and valued with the models appropriate to that profile; the target is a weighted blend. Forward
    assumptions are derived from historical financials and available consensus, mean-reverted and
    sanity-checked for internal consistency (reinvestment, ROIC, terminal multiples), then tilted for
    scenarios — they are not a substitute for fundamental judgement. Nothing here is investment
    advice, a recommendation, or an offer to transact. Do your own due diligence.</div>
</div></body></html>""")


def build_report(data, profile, spec, wacc, discount_rate, methods, dcf, scenarios,
                 sens, comps, base_drivers, diagnostics, reverse, target, upside, blend, risks):
    cur = data.currency_symbol
    primary = max(blend, key=blend.get) if blend else None

    ff_rows, summary_rows = [], []
    for key in _METHOD_ORDER:
        if key not in methods: continue
        m = methods[key]
        if key == "fcff_dcf" and scenarios:
            lo, hi, pt = scenarios["bear"].value_per_share, scenarios["bull"].value_per_share, m.value_per_share
        elif key == "comps" and comps:
            imp = [v["implied_vps"] for v in comps.multiples.values() if v["implied_vps"]]
            lo, hi, pt = (min(imp), max(imp), m.value_per_share) if imp else (m.value_per_share*0.9, m.value_per_share*1.1, m.value_per_share)
        else:
            lo, hi, pt = m.value_per_share*0.9, m.value_per_share*1.1, m.value_per_share
        ff_rows.append({"label": m.label, "low": lo, "high": hi, "point": pt})
        summary_rows.append({"label": m.label, "value": m.value_per_share, "up": m.upside, "weight": blend.get(key, 0)})
    if data.estimates.target_price_mean:
        tp = data.estimates.target_price_mean
        ff_rows.append({"label": "Street target", "low": tp*0.9, "high": tp*1.1, "point": tp})
        summary_rows.append({"label": "Street consensus", "value": tp, "up": tp/data.price-1, "weight": 0})

    rating, rdir = derive_rating(upside)
    thesis = build_thesis(data, spec, methods, target, upside, blend, discount_rate, dcf, diagnostics, reverse)

    # assumptions rationale (FCFF profiles)
    assumptions = base_drivers.rationale if base_drivers else None

    # combined historical + forecast model rows
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
            growth = (y.revenue / prev.revenue - 1) if prev else None
            model_rows.append({"year": y.year, "hist": True, "revenue": y.revenue,
                               "growth": growth, "ebit": y.ebit, "margin": y.ebit_margin,
                               "nopat": nopat, "fcff": fcff, "conv": (fcff/nopat if nopat else None),
                               "last_hist": idx == len(hist)-1})
            prev = y
        prev_rev = hist[-1].revenue
        for f in dcf.forecast:
            model_rows.append({"year": f.year, "hist": False, "revenue": f.revenue,
                               "growth": f.revenue/prev_rev-1, "ebit": f.ebit, "margin": f.ebit_margin,
                               "nopat": f.nopat, "fcff": f.fcff, "conv": (f.fcff/f.nopat if f.nopat else None),
                               "last_hist": False})
            prev_rev = f.revenue

    # returns commentary
    returns_comment = ""
    if diagnostics:
        rt, wc = diagnostics.get("roic_term"), discount_rate
        if rt is not None:
            spread = (rt - wc) * 10000
            if rt > wc:
                returns_comment = (f"The business earns <b>{pct(rt,1)}</b> on incremental capital versus a "
                    f"<b>{pct(wc,1)}</b> cost of capital — a positive spread of <b>{spread:.0f}bps</b>. "
                    f"Growth therefore creates value and the model rightly capitalises it at a premium to book. "
                    f"The implied self-funding growth of {pct(diagnostics.get('fundamental_g'),1)} "
                    f"(reinvestment {pct(diagnostics.get('reinvest_rate'),0)} × ROIC) frames how much "
                    f"of our terminal growth is organically financed rather than assumed.")
            else:
                returns_comment = (f"The business earns <b>{pct(rt,1)}</b> on capital against a <b>{pct(wc,1)}</b> "
                    f"cost of capital — a negative spread of <b>{abs(spread):.0f}bps</b>. Growth here "
                    f"<b>destroys</b> value, so the terminal assumptions deserve scrutiny: a company that cannot "
                    f"out-earn its capital cost should not trade above replacement value.")

    method_cards = []
    for key in _METHOD_ORDER:
        if key in ("fcff_dcf", "comps") or key not in methods: continue
        m = methods[key]
        card = {"label": m.label, "rows": m.rows, "note": m.note,
                "is_primary": key == primary, "forecast": bool(m.forecast)}
        if m.forecast:
            if key == "residual_income":
                card["fc_head"] = ["Year", "Opening BV", "ROE", "Resid. inc.", "PV"]
                card["fc_rows"] = [[f["year"], fmt_ps(f["bv"], cur), f"{f['roe']:.1%}",
                                    fmt_ps(f["ri"], cur), fmt_ps(f["pv"], cur)] for f in m.forecast]
            elif key == "ddm":
                card["fc_head"] = ["Year", "DPS", "Growth", "PV"]
                card["fc_rows"] = [[f["year"], fmt_ps(f["dps"], cur), f"{f['g']:.1%}", fmt_ps(f["pv"], cur)] for f in m.forecast]
        method_cards.append(card)

    scen_rows = []
    if scenarios:
        for name, sc in [("Bear", "bear"), ("Base", "base"), ("Bull", "bull")]:
            s = scenarios[sc]
            scen_rows.append({"name": name, "g1": s.forecast[0].revenue/data.latest.revenue-1,
                              "margin": s.forecast[-1].ebit_margin, "term": s.terminal_growth,
                              "vps": s.value_per_share, "up": s.upside})

    key_data = build_key_data(data, dcf, base_drivers)
    finsum = build_finsum(data, dcf, base_drivers)
    ratios = build_ratios(data, base_drivers)
    catalysts = build_catalysts(data, dcf, base_drivers, sens, wacc)
    factors = build_factor_exposure(data, profile, dcf, base_drivers, sens, diagnostics, reverse, discount_rate)

    kw = dict(
        key_data=key_data, finsum=finsum, ratios=ratios, catalysts=catalysts, factors=factors,
        d=data, spec=spec, report_date=date.today().strftime("%d %b %Y"),
        rating=rating, rating_dir=rdir, target=target, upside=upside, thesis=thesis,
        wacc=wacc, wacc_rows=wacc.as_rows(), discount_rate=discount_rate,
        summary_rows=summary_rows, assumptions=assumptions, model_rows=model_rows,
        method_cards=method_cards, comps=comps, risks=risks, dcf=dcf, scenarios=scenarios,
        scen_rows=scen_rows, diagnostics=diagnostics or {}, reverse=reverse or {},
        returns_comment=returns_comment,
        ff_chart=charts.football_field(ff_rows, data.price, cur),
        fmt_money=lambda v: fmt_money(v, cur), fmt_ps=lambda v: fmt_ps(v, cur),
        pct=pct, spct=spct,
    )
    if dcf:
        hist = data.years[-4:] if len(data.years) >= 4 else data.years
        kw["margins_chart"] = charts.margins_returns_chart(
            [y.year for y in hist], [y.ebit_margin or 0 for y in hist],
            [f.year for f in dcf.forecast], [f.ebit_margin for f in dcf.forecast], cur)
        kw["proj_chart"] = charts.projection_chart([f.year for f in dcf.forecast],
            [f.revenue for f in dcf.forecast], [f.fcff for f in dcf.forecast], cur)
        kw["bridge_chart"] = charts.ev_bridge(dcf.pv_explicit, dcf.pv_tv, dcf.net_debt,
            dcf.minority, dcf.equity_value, cur)
        kw["sens_chart"] = charts.sensitivity_heatmap(sens, cur) if sens else None
    else:
        kw["proj_chart"] = kw["bridge_chart"] = kw["sens_chart"] = kw["margins_chart"] = None
    return TEMPLATE.render(**kw)
