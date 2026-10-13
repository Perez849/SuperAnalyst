"""Builds the pre-formatted context the note template draws (numbers -> strings, charts -> SVG).

Kept apart from report.py so the template stays dumb: everything here is a pure function of the
valuation result. Nothing is invented; missing inputs produce missing panels, not placeholders.
"""
from __future__ import annotations

import math
import statistics
from types import SimpleNamespace as NS
from typing import Optional

from . import analysis as A
from . import charts, clockdata
from .clockdata import PHASE_EN, PHASES

STRENGTH_EN = {"Débil": "weak", "Moderada": "moderate", "Fuerte": "strong"}
REL_EN = {"Sin señal": "no signal", "Débil": "weak", "Moderada": "moderate", "Fuerte": "strong"}
PHASE_CLS = {"Recuperación": "rec", "Sobrecalentamiento": "over", "Estanflación": "stag", "Reflación": "refl"}


# --------------------------------------------------------------------------- #
#  formatting
# --------------------------------------------------------------------------- #
def f_money(v, cur="$"):
    if v is None or not math.isfinite(v):
        return "—"
    a = abs(v)
    body = (f"{cur}{a/1e12:,.2f}trn" if a >= 1e12 else f"{cur}{a/1e9:,.2f}bn" if a >= 1e9
            else f"{cur}{a/1e6:,.0f}mn" if a >= 1e6 else f"{cur}{a:,.0f}")
    return f"({body})" if v < 0 else body


def f_ps(v, cur="$"):
    if v is None or not math.isfinite(v):
        return "—"
    return f"({cur}{abs(v):,.2f})" if v < 0 else f"{cur}{v:,.2f}"


def f_pct(v, dp=1):
    return "—" if v is None or not math.isfinite(v) else f"{v*100:.{dp}f}%"


def f_spct(v, dp=0):
    return "—" if v is None or not math.isfinite(v) else f"{v*100:+.{dp}f}%"


def f_x(v, dp=1):
    return "—" if v is None or not math.isfinite(v) else f"{v:.{dp}f}x"


def _num(v):
    if v is None or not math.isfinite(v):
        return "—", ""
    a = abs(v)
    s = f"{a:,.0f}" if a >= 1000 else f"{a:,.1f}" if a >= 100 else f"{a:,.2f}"
    return (f"({s})", "neg") if v < 0 else (s, "")


def _cell(v, fmt, cur):
    if v is None or not math.isfinite(v):
        return {"t": "—", "cls": ""}
    if fmt == "money":
        t, c = _num(v)
        return {"t": t, "cls": c}
    if fmt == "pct":
        return {"t": f"{v*100:.1f}%" if v >= 0 else f"−{abs(v)*100:.1f}%", "cls": "neg" if v < 0 else ""}
    if fmt == "x":
        return {"t": f"{v:.1f}x" if v >= 0 else "net cash", "cls": ""}
    if fmt == "ps":
        return {"t": f"{cur}{v:,.2f}" if v >= 0 else f"({cur}{abs(v):,.2f})", "cls": "neg" if v < 0 else ""}
    return {"t": f"{v:,.2f}", "cls": ""}


def _fmt_series(v, fmt):
    return v


# --------------------------------------------------------------------------- #
def build(data, profile, spec, wacc, dcf, scenarios, sens, base_drivers, diagnostics, reverse, tr, fwd, ref,
          fwd_model, peers, cycle_raw, football_rows) -> dict:
    cur = data.currency_symbol
    price = data.price
    tax = base_drivers.tax_rate if base_drivers else 0.22
    out: dict = {}

    # ---- statements ----------------------------------------------------------------
    ft = A.financial_tables(data, dcf, fwd_model, fwd)
    rows_by_label = {r.label: r for s in ft.sections for r in s.rows}
    t = NS(unit_label=f"{cur}{ft.unit}", cols=ft.cols, n_hist=ft.n_hist, sections=[])
    for sec in ft.sections:
        rr = []
        for r in sec.rows:
            spark = charts.sparkline(r.spark) if (r.fmt == "money" and len(r.spark) >= 3 and not r.sub) else ""
            rr.append(NS(label=r.label, cells=[_cell(v, r.fmt, cur) for v in r.values], sub=r.sub, bold=r.bold, spark=spark))
        t.sections.append(NS(title=sec.title, rows=rr))
    out["ft"] = t
    out["ft_note"] = ("Forecast columns: revenue, EBIT and capex are the DCF base case; net income and EPS use consensus where it "
                      "covers the year; free cash flow in forecast years is unlevered (FCFF). Dashes mean the provider does not report the line.")

    # ---- KPI tiles -------------------------------------------------------------------
    kp = []
    for k in A.kpi_tiles(data, fwd, ref, tr, tax):
        v = k["value"]
        if k["fmt"] == "money":
            txt = f_money(v, cur)
        elif k["fmt"] == "pct":
            txt = f_pct(v, 1)
        else:
            txt = "net cash" if (v is not None and v < 0 and "debt" in k["label"].lower()) else f_x(v, 1)
        kp.append({"label": k["label"], "text": txt, "sub": k["sub"], "tone": k["tone"], "spark": charts.sparkline(k["spark"])})
    out["kpis"] = kp[:8]

    # ---- bridge ------------------------------------------------------------------------
    steps = A.target_bridge(tr)
    out["bridge_svg"] = charts.waterfall(steps, cur)
    fvgap = tr.fair_value - price
    out["bridge_take"] = (f"Fair value sits <b>{f_ps(abs(fvgap), cur)} {'above' if fvgap >= 0 else 'below'}</b> the price. Carrying it forward at the "
                          f"{f_pct(tr.ke, 1)} cost of equity adds <b>{f_ps(tr.fair_value * tr.ke, cur)}</b>"
                          + (f", dividends take back {f_ps(tr.dps, cur)}" if tr.dps else "")
                          + (f"; the Street anchor / guardrail moves it {f_ps(abs(tr.target - tr.model_target), cur)} "
                             f"{'up' if tr.target >= tr.model_target else 'down'}." if abs(tr.target - tr.model_target) > 0.005 * price else "."))

    # ---- football + scenarios ----------------------------------------------------------
    out["ff_svg"] = charts.football_field(football_rows, price, tr.target if tr.rated else None, cur)
    used = [l for l in tr.lenses if l.eff_weight > 0]
    vals = [l.value for l in used]
    cv = statistics.pstdev(vals) / statistics.mean(vals) if len(vals) > 1 and statistics.mean(vals) else 0
    out["ff_take"] = (f"<b>{len(used)} lenses</b> blend to a fair value of <b>{f_ps(tr.fair_value, cur)}</b> (dispersion {cv:.0%}). "
                      + (f"Street mean {f_ps(tr.street.mean, cur)} over {tr.street.n} analysts." if tr.street and tr.street.n else
                         f"Street mean {f_ps(tr.street.mean, cur)}." if tr.street else "No Street consensus available."))
    sc = A.scenario_table(tr, data, scenarios)
    has_dcf = any(r["dcf"] for r in sc["rows"])
    out["scen"] = NS(rows=[NS(**r) for r in sc["rows"]], expected=sc["expected"], expected_ret=sc["expected_ret"], has_dcf=has_dcf)
    out["scen_svg"] = charts.scenario_strip(price, sc["rows"], cur)
    out["scen_take"] = (f"Weighting bear / base / bull 25 / 50 / 25 gives <b>{f_ps(sc['expected'], cur)}</b> "
                        f"({f_spct(sc['expected_ret'])} incl. dividends). Bear and bull come from the lens ranges (DCF bear/bull cases in the last column).")

    # ---- Row C charts ----------------------------------------------------------------------
    labels = ft.cols
    n_hist = ft.n_hist
    R = lambda name: rows_by_label[name].values
    out["combo_svg"] = charts.combo_chart(labels, R("Revenue"), R("EBIT margin"), n_hist, "Revenue", "EBIT margin", ft.unit, width=340, height=220)
    rev = [v for v in R("Revenue") if v is not None]
    if len(rev) > n_hist and n_hist >= 1 and rev[n_hist - 1] > 0:
        yrs = len(rev) - n_hist
        cagr = (rev[-1] / rev[n_hist - 1]) ** (1 / yrs) - 1
        mg = [v for v in R("EBIT margin") if v is not None]
        out["combo_take"] = (f"Revenue compounds <b>{cagr:+.0%}</b> a year to {labels[-1]} on the base case; EBIT margin "
                             f"{f_pct(mg[n_hist - 1], 0) if len(mg) >= n_hist else '—'} → {f_pct(mg[-1], 0)}.")
    else:
        out["combo_take"] = ""
    out["eps_svg"] = charts.bars_chart(labels, R("Diluted EPS"), n_hist, "Diluted EPS", cur, width=340, height=220)
    out["eps_take"] = (f"Consensus EPS {f_ps(fwd.eps_fy1, cur)}" + (f" → {f_ps(fwd.eps_fy2, cur)}" if fwd.eps_fy2 else "")
                       + f" for FY{fwd.fy1_year}" + (f"–{fwd.fy1_year + 1}" if fwd.eps_fy2 else "") + f"; NTM P/E <b>{f_x(price / fwd.eps_ntm, 1) if fwd.eps_ntm and fwd.eps_ntm > 0 else 'n/a'}</b>.")
    out["cf_svg"] = charts.grouped_bars(labels, [("OCF", R("Operating cash flow"), "s-ocf"), ("Capex", R("Capex"), "s-capex"),
                                                  ("FCF", R("Free cash flow"), "s-fcf")], ft.unit, width=340, height=220)
    fcfs = [v for v in R("Free cash flow")[:n_hist] if v is not None]
    conv = [v for v in R("FCF / net income")[:n_hist] if v is not None]
    out["cf_take"] = (f"FCF {('%+.1f' % fcfs[-1]) if fcfs else '—'}{ft.unit} last year" + (f", {conv[-1]:.1f}x net income" if conv else "")
                      + f"; capex intensity {f_x(rows_by_label['Capex / D&A'].values[n_hist - 1], 1) if rows_by_label['Capex / D&A'].values[n_hist - 1] else '—'} D&A.")
    rs = A.returns_series(data, tax)
    yrs_l = [f"’{str(y)[-2:]}" for y in rs["years"]]
    out["roic_svg"] = charts.line_chart(yrs_l, [("ROIC", rs["roic"], "lc-roic"), ("ROE", rs["roe"], "lc-roe"),
                                                ("WACC", [wacc.wacc] * len(yrs_l), "lc-wacc")], pct=True, width=340, height=220)
    roic = next((v for v in reversed(rs["roic"]) if v is not None), None)
    out["roic_take"] = ((f"ROIC <b>{f_pct(roic, 0)}</b> vs WACC {f_pct(wacc.wacc, 1)}: "
                         + ("value-creating growth." if roic > wacc.wacc else "returns below the cost of capital.")) if roic is not None else "")

    # ---- multiples -----------------------------------------------------------------------------
    mr = A.multiples_table(data, fwd, ref, tr, peers)
    out["bullets_svg"] = charts.multiples_bullets(mr)
    out["has_peers"] = bool(peers) and any(m.get("peer") for m in mr)
    rows = []
    for m in mr:
        pct_fmt = m["fmt"] == "pct"
        ff = (lambda v: f_pct(v, 1)) if pct_fmt else (lambda v: f_x(v, 2 if m["fmt"] == "x2" else 1))
        tone = ""
        if m["prem"] is not None:
            cheap = (m["prem"] < -0.05) if m["lower_better"] else (m["prem"] > 0.05)
            rich = (m["prem"] > 0.05) if m["lower_better"] else (m["prem"] < -0.05)
            tone = "up" if cheap else ("down" if rich else "")
        rows.append({"metric": m["metric"], "now": ff(m["now"]), "ref": ff(m["ref"]) if m["ref"] else "—",
                     "prem": f_spct(m["prem"]) if m["prem"] is not None else "—", "tone": tone,
                     "target": ff(m["target"]) if m.get("target") else "—"})
    out["mult_rows"] = rows
    pe = next((m for m in mr if m["metric"].startswith("P/E")), None)
    ev = next((m for m in mr if m["metric"].startswith("EV/EBITDA")), None)
    bits = []
    if pe and pe["ref"]:
        bits.append(f"<b>{f_x(pe['now'])} NTM earnings</b> vs a {f_x(pe['ref'])} sector reference ({f_spct(pe['prem'])})")
    if ev and ev["ref"]:
        bits.append(f"{f_x(ev['now'])} EV/EBITDA vs {f_x(ev['ref'])}")
    out["mult_take"] = ("; ".join(bits) + ". At our target the P/E would be " + (f_x(pe["target"]) if pe and pe.get("target") else "n/a") + "." if bits else
                        "Earnings-based multiples are not meaningful here; see the EV/Sales and book-value lenses.")

    # ---- scorecard / view ---------------------------------------------------------------------------
    cyc = clockdata.cycle_view(data.sector, data.industry, data.ticker, cycle_raw) if cycle_raw else None
    sc_axes = A.scorecard(data, tr, fwd, cyc, wacc.wacc, tax)
    out["scorecard"] = sc_axes
    out["radar_svg"] = charts.radar(sc_axes)
    pio, alt, accr = A.piotroski(data), A.altman_z(data), A.accruals(data)
    out["view"] = _view(data, tr, fwd, cur, roic, wacc, cyc, reverse, pio, alt, scenarios, price)

    # ---- financial section ------------------------------------------------------------------------------
    def rf(v, fmt):
        return {"pct": f_pct(v, 1), "x": f_x(v, 2)}[fmt] if v is not None else "—"

    out["ret"] = NS(years=rs["years"], rows=[("ROE", [f_pct(v, 1) for v in rs["roe"]]), ("ROA", [f_pct(v, 1) for v in rs["roa"]]),
                                              ("ROIC", [f_pct(v, 1) for v in rs["roic"]]), ("Asset turnover", [f_x(v, 2) for v in rs["turnover"]]),
                                              ("Equity multiplier", [f_x(v, 2) for v in rs["multiplier"]])])
    dp = A.dupont(data)
    out["dupont"] = NS(nm=f_pct(dp["net_margin"], 1), at=f_x(dp["turnover"], 2), em=f_x(dp["multiplier"], 2), roe=f_pct(dp["roe"], 1), year=dp["year"]) if dp else None
    out["pio"] = NS(score=pio["score"], available=pio["available"], items=[(l, ok) for l, ok in pio["items"]])
    if alt:
        zones = {"safe": "safe zone", "grey": "grey zone", "distress": "distress zone"}
        out["alt"] = NS(z_txt=f"{alt['z']:.1f}", zone=zones[alt["zone"]],
                        meter=charts.meter(min(alt["z"], 5.0), 0, 5, [(1.81, "bad"), (2.99, "mid"), (5, "good")]))
    else:
        out["alt"] = None
    out["accr_txt"] = f_pct(accr, 1) if accr is not None else "n/a"
    y = data.latest
    out["conv_txt"] = f_x(y.operating_cash_flow / y.net_income, 2) if y.net_income and y.net_income > 0 else "n/a"
    wc = A.working_capital_days(data) or {}
    out["wc"] = {k: f"{v:.0f} d" for k, v in wc.items()}

    # ---- DCF section ---------------------------------------------------------------------------------------------
    if dcf:
        sc_ = ft.scale
        rows = []
        prev = data.latest.revenue
        for f in dcf.forecast:
            def fm(v):
                return _num(v / sc_)[0]
            rows.append({"year": f.year, "revenue": fm(f.revenue), "growth": f_pct(f.revenue / prev - 1, 1), "ebit": fm(f.ebit),
                         "margin": f_pct(f.ebit_margin, 1), "nopat": fm(f.nopat), "da": fm(f.da), "capex": fm(-f.capex), "dnwc": fm(-f.d_nwc),
                         "fcff": fm(f.fcff), "df": f"{f.discount_factor:.3f}", "pv": fm(f.pv_fcff)})
            prev = f.revenue
        out["fcff_rows"] = rows
        out["fcff_lines"] = [("Revenue", "revenue", "b"), ("growth", "growth", "sub"), ("EBIT", "ebit", ""), ("EBIT margin", "margin", "sub"),
                             ("NOPAT", "nopat", ""), ("+ D&A", "da", ""), ("− Capex", "capex", ""), ("− Δ working capital", "dnwc", ""),
                             ("Unlevered FCF", "fcff", "b"), ("Discount factor", "df", "sub"), ("Present value", "pv", "")]
        d = diagnostics or {}
        out["dcf_stats"] = [("WACC", f_pct(dcf.wacc, 2)), ("Terminal growth", f_pct(dcf.terminal_growth, 2)),
                            ("Terminal value / EV", f_pct(dcf.tv_pct_of_ev, 0)), ("Enterprise value", f_money(dcf.enterprise_value, cur)),
                            ("Equity value", f_money(dcf.equity_value, cur)),
                            ("Implied exit EV/EBITDA", f_x(d.get("implied_ev_ebitda"), 1)), ("Terminal ROIC", f_pct(d.get("roic_term"), 0)),
                            ("DCF value / share", f_ps(dcf.value_per_share, cur))]

    # ---- cycle -------------------------------------------------------------------------------------------------------------
    out["cycle"] = None
    if cyc:
        out.update(_cycle(cyc, tr, data, cur, price))

    # ---- price / technicals -----------------------------------------------------------------------------------------------------
    out["price_svg"], out["price_stats"] = "", []
    if len(data.price_history) >= 30:
        out["price_svg"] = charts.price_chart(data.price_history, price, tr.target, tr.bear, tr.bull, cur)
        out["price_stats"] = _price_stats(data, tr)

    # ---- peers ---------------------------------------------------------------------------------------------------------------------
    pr = []
    if peers:
        for p in peers:
            pr.append({"name": f"{p.name} ({p.ticker})" if p.name != p.ticker else p.ticker, "mc": f_money(p.market_cap, cur), "pe": f_x(p.fwd_pe or p.pe, 1),
                       "ev": f_x(p.ev_ebitda, 1), "evs": f_x(p.ev_sales, 1), "pb": f_x(p.pb, 1), "med": False})
        meds = {k: charts_median([getattr(p, a) or (p.pe if a == "fwd_pe" else None) for p in peers]) for k, a in
                (("pe", "fwd_pe"), ("ev", "ev_ebitda"), ("evs", "ev_sales"), ("pb", "pb"))}
        pr.append({"name": "Median", "mc": "", "pe": f_x(meds["pe"]), "ev": f_x(meds["ev"]), "evs": f_x(meds["evs"]), "pb": f_x(meds["pb"]), "med": True})
    out["peer_rows"] = pr
    return out


def charts_median(vals):
    v = [x for x in vals if x is not None and math.isfinite(x) and x > 0]
    return statistics.median(v) if v else None


def _price_stats(data, tr) -> list:
    h = data.price_history
    closes = [c for _, c in h]
    last = closes[-1]
    wk = closes[-52:]
    rets = [closes[i] / closes[i - 1] - 1 for i in range(1, len(closes))]
    vol = statistics.pstdev(rets[-104:]) * math.sqrt(52) if len(rets) >= 30 else None
    peak, mdd = closes[0], 0.0
    for c in closes:
        peak = max(peak, c)
        mdd = min(mdd, c / peak - 1)

    def ret(n):
        return last / closes[-n - 1] - 1 if len(closes) > n else None

    return [("52-week high", f"{max(wk):,.2f}"), ("52-week low", f"{min(wk):,.2f}"), ("From 52w high", f_spct(last / max(wk) - 1)),
            ("3-month", f_spct(ret(13))), ("6-month", f_spct(ret(26))), ("1-year", f_spct(ret(52))),
            ("Volatility (2y, ann.)", f_pct(vol, 0) if vol else "—"), ("Max drawdown (5y)", f_spct(mdd)),
            ("Target vs 52w high", f_spct(tr.target / max(wk) - 1))]


def _view(data, tr, fwd, cur, roic, wacc, cyc, reverse, pio, alt, scenarios, price) -> list:
    v = []
    tone = "pos" if tr.total_return > 0.05 else ("neg" if tr.total_return < -0.05 else "neu")
    if tr.rated:
        v.append({"tone": tone, "text": f"<b>Valuation.</b> Fair value {f_ps(tr.fair_value, cur)} vs price {f_ps(price, cur)}; 12-month target "
                                        f"<b>{f_ps(tr.target, cur)}</b> ({f_spct(tr.upside)}, {f_spct(tr.total_return)} with dividends)."})
    else:
        v.append({"tone": "neu", "text": f"<b>Valuation.</b> No defensible price target: {tr.rating_note}. Indicative value {f_ps(tr.fair_value, cur)}."})
    g = (fwd.rev_fy1 / data.latest.revenue - 1) if (fwd.rev_fy1 and data.latest.revenue) else None
    fund = []
    if g is not None:
        fund.append(f"FY+1 revenue {f_spct(g)}")
    if roic is not None:
        fund.append(f"ROIC {f_pct(roic, 0)} vs WACC {f_pct(wacc.wacc, 1)}")
    fund.append(f"EBIT margin {f_pct(data.latest.ebit_margin, 0)}")
    v.append({"tone": "pos" if (roic is not None and roic > wacc.wacc) else "neu", "text": "<b>Fundamentals.</b> " + "; ".join(fund) + "."})
    if fwd.cycle.durability < 0.999 or fwd.flags:
        v.append({"tone": "neg", "text": f"<b>Earnings quality.</b> {fwd.flags[0] if fwd.flags else 'Forward earnings are cyclically elevated.'}"})
    elif pio["available"] >= 5:
        v.append({"tone": "pos" if pio["score"] >= 6 else "neu", "text": f"<b>Quality.</b> Piotroski {pio['score']}/{pio['available']}"
                  + (f"; Altman Z {alt['z']:.1f} ({alt['zone']})" if alt else "") + "."})
    if cyc and cyc.get("tilt") is not None:
        t = cyc["tilt"]
        v.append({"tone": "pos" if t > 0.5 else ("neg" if t < -0.5 else "neu"),
                  "text": f"<b>Cycle.</b> Reloj reads <b>{PHASE_EN[cyc['phase']]}</b> ({STRENGTH_EN.get(cyc['strength'], cyc['strength'])} signal); "
                          f"{clockdata.en(cyc['asset'])} has a probability-weighted tilt of <b>{t:+.1f} pp/yr</b> vs the US market."})
    if reverse and reverse.get("solved"):
        d = reverse["base_y1_growth"] - reverse["implied_y1_growth"]
        v.append({"tone": "pos" if d > 0 else "neg", "text": f"<b>Priced in.</b> The market discounts year-1 growth of {f_pct(reverse['implied_y1_growth'], 0)} "
                                                              f"vs our {f_pct(reverse['base_y1_growth'], 0)}: " + ("less than we model." if d > 0 else "more than we model.")})
    v.append({"tone": "neu", "text": f"<b>What would change our mind.</b> A sustained miss on FY+1 {'revenue' if g is not None else 'earnings'} or margin; "
                                     f"{'a re-rating of the sector multiple; ' if tr.fair_value else ''}a move in the cost of equity ({f_pct(tr.ke, 1)} today)."})
    return v[:6]


def _cycle(cyc, tr, data, cur, price) -> dict:
    phase, alt = cyc["phase"], cyc["alt"]
    probs = cyc["probs"]
    cls = PHASE_CLS[phase]
    strength = STRENGTH_EN.get(cyc["strength"], cyc["strength"] or "n/a")
    asset = cyc["asset"] or "—"
    asset_en = clockdata.en(asset)
    stats = cyc["stats"]
    st = stats.get(phase, {}) if stats else {}
    tilt, edge_now = cyc["tilt"], cyc["edge_now"]
    conf_pts = (cyc["confidence"] or 0) * 100
    pnow, palt = probs.get(phase, 0), probs.get(alt, 0)

    sent = [f"<b>{phase}</b> ({PHASE_EN[phase]}), {strength} signal: {pnow:.0%} vs {palt:.0%} for {alt} ({PHASE_EN.get(alt, alt)})."]
    if edge_now is not None:
        sent.append(f" {asset_en} has historically {'beaten' if edge_now >= 0 else 'lagged'} the US market by <b>{abs(edge_now):.1f} pp/yr</b> in this phase"
                    + (f"; probability-weighted tilt <b>{tilt:+.1f} pp/yr</b>." if tilt is not None else "."))
    pn = cyc["playbook_now"]
    sent.append(f" The Reloj's playbook {'holds ' + str(pn['weight']) + '% in ' + asset_en if pn else 'does not hold ' + asset_en} in this phase.")
    summary = "".join(sent)

    read = (f"The Reloj's call is <b>{phase}</b> with <b>{strength}</b> conviction: only {conf_pts:.1f} points separate it from {alt} ({PHASE_EN.get(alt, alt)}). "
            f"Growth sits at {cyc['growth']:+.2f}σ and inflation at {cyc['inflation']:+.2f}σ of their ten-year norms"
            + (f"; the 12-month recession probability is {cyc['recession']:.0%}." if cyc.get("recession") is not None else "."))

    table = []
    for p in PHASES:
        s = stats.get(p, {}) if stats else {}
        rel = s.get("rel_shrunk")
        reliab_es = s.get("reliability") or "n/a"
        reliab = REL_EN.get(reliab_es, reliab_es)
        table.append({"phase": f"{PHASE_EN[p]}{' ●' if p == phase else ''}", "ann": f"{s['ann']:.1f}%" if s.get("ann") is not None else "—",
                      "rel": f"{rel:+.1f}" if rel is not None else "—", "tone": "up" if (rel or 0) > 0.5 else ("down" if (rel or 0) < -0.5 else ""),
                      "t": f"{s['t']:+.1f}" if s.get("t") is not None else "—", "hit": f"{s['hit']:.0%}" if s.get("hit") is not None else "—",
                      "n": s.get("n") or "—", "reliability": reliab,
                      "rel_cls": {"strong": "ok", "moderate": "med"}.get(reliab, "neutral")})
    ast = cyc.get("asset_stats") or {}
    edge_take = ""
    if st:
        edge_take = (f"In {PHASE_EN[phase]} {asset_en} has returned <b>{st.get('ann', 0):.1f}%</b> a year on average "
                     f"(<b>{st.get('rel_shrunk', 0):+.1f} pp/yr</b> vs the market, t = {st.get('t', 0):+.1f}, reliability <i>{REL_EN.get(st.get('reliability'), st.get('reliability'))}</i>). "
                     + (f"Weighted by today's probabilities the sector's expected edge is <b>{tilt:+.1f} pp/yr</b>. " if tilt is not None else "")
                     + (f"Across all sector×phase cells the Reloj tests, {ast.get('fdr_survivors')} of {ast.get('cells')} survive false-discovery control." if ast.get("fdr_survivors") is not None else ""))

    pbk = cyc["playbook_all"].get(phase, [])
    asset_names = {cyc["asset"], cyc["parent"]}
    playbook = [(clockdata.en(n), f"{w:.1f}%", n in asset_names) for n, w in pbk]
    if pn:
        play_take = (f"The current playbook allocates <b>{pn['weight']:.1f}%</b> to {asset_en}. "
                     + ("Valuation upside and the cycle point the same way." if tr.total_return > 0.05 else
                        "The cycle supports the sector while our valuation does not see upside." if tr.total_return < -0.05 else
                        "The cycle is supportive; valuation upside is modest."))
    else:
        pa = cyc["playbook_alt"]
        play_take = (f"{asset_en} is <b>not in</b> the Reloj's playbook for {PHASE_EN[phase]}"
                     + (f", but would hold {pa['weight']:.1f}% if the cycle tips to {PHASE_EN.get(alt, alt)}." if pa else f" nor for the runner-up phase ({PHASE_EN.get(alt, alt)})."))

    hold = cyc["holding"]
    etf_facts = [("ETFs", " · ".join(t for t, _ in cyc["etfs"]) or "—")]
    main_hit = next((h for h in hold["hits"] if h["sector"] in asset_names), None) or (hold["hits"][0] if hold["hits"] else None)
    if main_hit:
        etf_facts += [("Weight in sector ETF", f"{main_hit['weight']:.2f}%"), ("Rank in ETF", f"#{main_hit['rank']}")]
    if hold["group"]:
        etf_facts.append((f"{hold['group']['group']} (sub-sector)", f"{hold['group']['group_weight']:.1f}% of ETF"))
    etf_take = ("Owning the sector through its ETF carries this company at the weight above; owning the stock instead adds single-name risk the "
                "Reloj's sector evidence does not measure." if main_hit else
                "The company is not among the largest holdings the Reloj tracks, so the sector evidence is context rather than exposure.")

    probs_html = charts.prob_bars(probs, phase, "en")
    current = {"phase": phase, "growth": cyc["growth"], "inflation": cyc["inflation"], "sigma_g": cyc["sigma_g"], "sigma_i": cyc["sigma_i"]}
    return {
        "cycle": NS(asof=cyc["asof"], fetched=cyc["fetched"], phase=phase, phase_en=PHASE_EN[phase], cls=cls, strength_en=strength, summary=summary,
                    read=read, conf_pts=f"{conf_pts:.1f}", asset_en=asset_en, table=[NS(**r) for r in table], edge_take=edge_take,
                    playbook=playbook, playbook_label=clockdata.en(cyc.get("playbook_label") or ""), playbook_take=play_take,
                    etf_facts=etf_facts, etf_take=etf_take, holdings_asof=cyc.get("holdings_asof"), site=clockdata.SITE_URL,
                    source_txt=("live data" if cyc["fetched"] == "live" else "snapshot") + f" as of {cyc['asof']}",
                    facts=[("Growth z", f"{cyc['growth']:+.2f}σ"), ("Inflation z", f"{cyc['inflation']:+.2f}σ"),
                           ("Recession 12m", f"{cyc['recession']:.0%}" if cyc.get("recession") is not None else "—"),
                           ("Growth Δ3m", f"{(cyc['momentum'] or {}).get('growth_3m', 0):+.2f}σ"), ("Inflation Δ3m", f"{(cyc['momentum'] or {}).get('inflation_3m', 0):+.2f}σ"),
                           ("Data", cyc["fetched"])]),
        "plane_svg": charts.phase_plane(cyc["trail"], current, probs, "en", 560, 400),
        "plane_big_svg": charts.phase_plane(cyc["trail"], current, probs, "en", 560, 440),
        "edge_svg": charts.phase_edge_bars(stats, phase, probs, "en") if stats else "",
        "probs_html": probs_html,
    }
