"""Technical analysis behind the research note.

Pure functions that turn CompanyData + the valuation result into the structured numbers the
report draws: financial statements with consensus-based forecast columns, returns / DuPont,
quality and distress scores (Piotroski F, Altman Z, Sloan accruals), valuation vs the sector
reference and peers, scenario table, the price -> target bridge and a six-axis factor
scorecard. Nothing is invented: a figure that cannot be computed from the statements is None
and the report prints "n/a".
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from typing import Optional

from .lenses import _ebitda_ntm, _peer_stat
from .schema import CompanyData


def _fin(x) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(x)


def _norm(s: str) -> str:
    return "".join(ch for ch in str(s).lower() if ch.isalnum())


def lin(x: Optional[float], x0: float, x1: float) -> Optional[float]:
    """Linear map x0 -> 0, x1 -> 100, clamped."""
    if x is None or not _fin(x):
        return None
    return max(0.0, min(100.0, (x - x0) / (x1 - x0) * 100.0))


# --------------------------------------------------------------------------- #
#  Statement lines (raw statements are provider-specific; match by normalised label)
# --------------------------------------------------------------------------- #
ALIASES = {
    "gross_profit": ["Gross Profit"],
    "total_assets": ["Total Assets"],
    "current_assets": ["Current Assets", "Total Current Assets"],
    "current_liab": ["Current Liabilities", "Total Current Liabilities"],
    "retained": ["Retained Earnings"],
    "total_liab": ["Total Liabilities Net Minority Interest", "Total Liabilities"],
    "shares": ["Diluted Average Shares", "Weighted average shs out dil", "Weighted Average Shares Diluted"],
    "receivables": ["Accounts Receivable", "Net Receivables"],
    "inventory": ["Inventory"],
    "payables": ["Accounts Payable"],
    "cogs": ["Cost Of Revenue", "Cost of revenue"],
    "lt_debt": ["Long Term Debt"],
    "dividends": ["Cash Dividends Paid", "Common Stock Dividend Paid", "Dividends paid"],
    "buybacks": ["Repurchase Of Capital Stock", "Common stock repurchased"],
}


def line(data: CompanyData, key: str) -> dict:
    """{year: value} for a statement line, searched across all three statements."""
    want = {_norm(a) for a in ALIASES[key]}
    for kind in ("income", "balance", "cashflow"):
        for label, series in (data.raw_statements.get(kind) or []):
            if _norm(label) in want:
                return {int(y): v for y, v in series.items() if _fin(v)}
    return {}


def _at(d: dict, year: int):
    return d.get(year)


# --------------------------------------------------------------------------- #
#  Financial tables (history + forecast)
# --------------------------------------------------------------------------- #
@dataclass
class Row:
    label: str
    values: list                    # one per column (None = n/a)
    fmt: str = "money"              # money | pct | x | ps | num
    bold: bool = False
    sub: bool = False               # indented sub-row (growth, margin)
    spark: list = field(default_factory=list)


@dataclass
class Section:
    title: str
    rows: list


@dataclass
class FinTables:
    cols: list                      # column labels ("FY2024A" ... "FY2027E")
    n_hist: int
    unit: str                       # "bn" | "mn"
    scale: float
    sections: list


def _unit(data: CompanyData):
    top = max((abs(y.revenue) for y in data.years if _fin(y.revenue)), default=1.0)
    return ("bn", 1e9) if top >= 5e9 else ("mn", 1e6)


def financial_tables(data: CompanyData, dcf=None, fwd_model=None, fwd=None, n_fc: int = 3,
                     max_hist: int = 5) -> FinTables:
    yrs = data.years[-max_hist:]
    unit, sc = _unit(data)
    gp, ta = line(data, "gross_profit"), line(data, "total_assets")
    shares = line(data, "shares")
    nh = len(yrs)
    fc = list(dcf.forecast[:n_fc]) if dcf else []
    fm = list(fwd_model.years[:n_fc]) if fwd_model else []
    cols = [f"FY{y.year}A" for y in yrs] + [f"FY{f.year}E" for f in fc]

    def ser(fn_hist, fn_fc=None):
        v = []
        for y in yrs:
            try:
                x = fn_hist(y)
            except (ZeroDivisionError, TypeError):
                x = None
            v.append(x if x is None or _fin(x) else None)
        for i, f in enumerate(fc):
            try:
                x = fn_fc(f, i) if fn_fc else None
            except (ZeroDivisionError, TypeError, IndexError):
                x = None
            v.append(x if x is None or _fin(x) else None)
        return v

    def prev_rev(y):
        i = data.years.index(y)
        return data.years[i - 1].revenue if i > 0 else None

    def growth_hist(y):
        p = prev_rev(y)
        return y.revenue / p - 1 if p else None

    ebitda = lambda y: y.ebitda or (y.ebit + y.depreciation_amort)
    fcf = lambda y: y.operating_cash_flow - y.capex
    s = lambda x: x / sc if x is not None else None
    last_rev = [y.revenue for y in data.years]

    # --- income statement ---
    inc = [
        Row("Revenue", ser(lambda y: s(y.revenue), lambda f, i: s(f.revenue)), bold=True),
        Row("growth", ser(growth_hist, lambda f, i: f.revenue / (fc[i - 1].revenue if i else yrs[-1].revenue) - 1),
            "pct", sub=True),
        Row("Gross profit", ser(lambda y: s(gp.get(y.year)) if gp.get(y.year) is not None else None), "money"),
        Row("gross margin", ser(lambda y: gp[y.year] / y.revenue if gp.get(y.year) is not None else None), "pct", sub=True),
        Row("EBITDA", ser(lambda y: s(ebitda(y)), lambda f, i: s(f.ebit + f.da))),
        Row("EBITDA margin", ser(lambda y: ebitda(y) / y.revenue, lambda f, i: (f.ebit + f.da) / f.revenue), "pct", sub=True),
        Row("EBIT", ser(lambda y: s(y.ebit), lambda f, i: s(f.ebit)), bold=True),
        Row("EBIT margin", ser(lambda y: y.ebit / y.revenue, lambda f, i: f.ebit_margin), "pct", sub=True),
        Row("Net income", ser(lambda y: s(y.net_income), lambda f, i: s(fm[i].net_income) if fm else None)),
        Row("net margin", ser(lambda y: y.net_income / y.revenue,
                              lambda f, i: fm[i].net_income / f.revenue if fm else None), "pct", sub=True),
        Row("Diluted EPS", ser(lambda y: y.eps_diluted, lambda f, i: fm[i].eps if fm else None), "ps", bold=True),
    ]
    # --- balance sheet ---
    bal = [
        Row("Cash & short-term investments", ser(lambda y: s(y.cash_and_sti))),
        Row("Total debt", ser(lambda y: s(y.total_debt))),
        Row("Net debt / (net cash)", ser(lambda y: s(y.total_debt - y.cash_and_sti)), bold=True),
        Row("Net debt / EBITDA", ser(lambda y: (y.total_debt - y.cash_and_sti) / ebitda(y) if ebitda(y) > 0 else None), "x", sub=True),
        Row("Total assets", ser(lambda y: s(ta.get(y.year)) if ta.get(y.year) is not None else None)),
        Row("Shareholders' equity", ser(lambda y: s(y.total_equity))),
        Row("Book value / share", ser(lambda y: y.total_equity / (shares.get(y.year) or data.shares_diluted)), "ps"),
    ]
    # --- cash flow ---
    cfs = [
        Row("Operating cash flow", ser(lambda y: s(y.operating_cash_flow))),
        Row("Capex", ser(lambda y: s(-y.capex), lambda f, i: s(-f.capex))),
        Row("Free cash flow", ser(lambda y: s(fcf(y)), lambda f, i: s(f.fcff)), bold=True),
        Row("FCF margin", ser(lambda y: fcf(y) / y.revenue, lambda f, i: f.fcff / f.revenue), "pct", sub=True),
        Row("FCF / net income", ser(lambda y: fcf(y) / y.net_income if y.net_income > 0 else None), "x", sub=True),
        Row("Capex / D&A", ser(lambda y: y.capex / y.depreciation_amort if y.depreciation_amort else None,
                               lambda f, i: f.capex / f.da if f.da else None), "x", sub=True),
    ]
    sections = [Section("Income statement", inc), Section("Balance sheet", bal), Section("Cash flow", cfs)]
    for sec in sections:
        for r in sec.rows:
            r.spark = [v for v in r.values[:nh] if v is not None]
    return FinTables(cols, nh, unit, sc, sections)


# --------------------------------------------------------------------------- #
#  Returns, DuPont
# --------------------------------------------------------------------------- #
def returns_series(data: CompanyData, tax: float, max_hist: int = 5) -> dict:
    """ROE, ROA, ROIC by year (end-of-year balances; NOPAT = EBIT x (1 - tax))."""
    ta = line(data, "total_assets")
    out = {"years": [], "roe": [], "roa": [], "roic": [], "turnover": [], "multiplier": []}
    for y in data.years[-max_hist:]:
        eff = y.effective_tax_rate
        t = eff if (eff is not None and 0 <= eff <= 0.5) else tax
        ic = y.total_debt + y.total_equity - y.cash_and_sti
        assets = ta.get(y.year)
        out["years"].append(y.year)
        out["roe"].append(y.net_income / y.total_equity if y.total_equity > 0 else None)
        out["roa"].append(y.net_income / assets if assets else None)
        out["roic"].append(y.ebit * (1 - t) / ic if ic > 0 else None)
        out["turnover"].append(y.revenue / assets if assets else None)
        out["multiplier"].append(assets / y.total_equity if assets and y.total_equity > 0 else None)
    return out


def dupont(data: CompanyData) -> Optional[dict]:
    r = returns_series(data, 0.2)
    y = data.latest
    if r["turnover"][-1] is None or r["multiplier"][-1] is None or not y.revenue:
        return None
    nm = y.net_income / y.revenue
    return {"net_margin": nm, "turnover": r["turnover"][-1], "multiplier": r["multiplier"][-1],
            "roe": nm * r["turnover"][-1] * r["multiplier"][-1], "year": y.year}


# --------------------------------------------------------------------------- #
#  Quality & distress scores
# --------------------------------------------------------------------------- #
def piotroski(data: CompanyData) -> dict:
    """Piotroski F-score. Each test is True / False / None (cannot be computed)."""
    ys = data.years
    if len(ys) < 2:
        return {"score": None, "available": 0, "items": []}
    a, b = ys[-2], ys[-1]
    ta, gp = line(data, "total_assets"), line(data, "gross_profit")
    ca, cl = line(data, "current_assets"), line(data, "current_liab")
    sh = line(data, "shares")

    def roa(y):
        return y.net_income / ta[y.year] if ta.get(y.year) else None

    def lev(y):
        return y.total_debt / ta[y.year] if ta.get(y.year) else None

    def cr(y):
        return ca[y.year] / cl[y.year] if ca.get(y.year) and cl.get(y.year) else None

    def gm(y):
        return gp[y.year] / y.revenue if gp.get(y.year) and y.revenue else None

    def at(y):
        return y.revenue / ta[y.year] if ta.get(y.year) else None

    def cmp(f, g, better="up"):
        x, y_ = f(b), f(a)
        if x is None or y_ is None:
            return None
        return (x > y_) if better == "up" else (x < y_)

    items = [
        ("Positive return on assets", None if roa(b) is None else roa(b) > 0),
        ("Positive operating cash flow", b.operating_cash_flow > 0),
        ("Return on assets improving", cmp(roa, None)),
        ("Cash flow exceeds net income (low accruals)", b.operating_cash_flow > b.net_income),
        ("Leverage falling", cmp(lev, None, "down")),
        ("Current ratio improving", cmp(cr, None)),
        ("No dilution (share count not up)",
         None if not (sh.get(b.year) and sh.get(a.year)) else sh[b.year] <= sh[a.year] * 1.005),
        ("Gross margin improving", cmp(gm, None)),
        ("Asset turnover improving", cmp(at, None)),
    ]
    avail = [i for i in items if i[1] is not None]
    return {"score": sum(1 for _, v in avail if v), "available": len(avail), "items": items}


def altman_z(data: CompanyData) -> Optional[dict]:
    """Altman Z (original, for industrial companies). None if the lines are not available."""
    y = data.latest
    ta, ca, cl = line(data, "total_assets"), line(data, "current_assets"), line(data, "current_liab")
    re, tl = line(data, "retained"), line(data, "total_liab")
    t = ta.get(y.year)
    if not (t and ca.get(y.year) is not None and cl.get(y.year) is not None and re.get(y.year) is not None
            and tl.get(y.year) and data.market_cap):
        return None
    wc = (ca[y.year] - cl[y.year]) / t
    z = 1.2 * wc + 1.4 * re[y.year] / t + 3.3 * y.ebit / t + 0.6 * data.market_cap / tl[y.year] + 1.0 * y.revenue / t
    zone = "safe" if z > 2.99 else ("grey" if z > 1.81 else "distress")
    return {"z": z, "zone": zone, "parts": [("Working capital / assets", 1.2 * wc),
            ("Retained earnings / assets", 1.4 * re[y.year] / t), ("EBIT / assets", 3.3 * y.ebit / t),
            ("Market cap / liabilities", 0.6 * data.market_cap / tl[y.year]), ("Sales / assets", y.revenue / t)]}


def accruals(data: CompanyData) -> Optional[float]:
    """Sloan accrual ratio: (net income - operating cash flow) / average total assets."""
    ta = line(data, "total_assets")
    ys = data.years
    if len(ys) < 2 or not ta.get(ys[-1].year) or not ta.get(ys[-2].year):
        return None
    avg = (ta[ys[-1].year] + ta[ys[-2].year]) / 2
    return (ys[-1].net_income - ys[-1].operating_cash_flow) / avg


def working_capital_days(data: CompanyData) -> Optional[dict]:
    y = data.latest
    rec, inv, pay, cogs = (line(data, k).get(y.year) for k in ("receivables", "inventory", "payables", "cogs"))
    if not y.revenue:
        return None
    out = {}
    if rec is not None:
        out["DSO"] = rec / y.revenue * 365
    if inv is not None and cogs:
        out["DIO"] = inv / cogs * 365
    if pay is not None and cogs:
        out["DPO"] = pay / cogs * 365
    if len(out) == 3:
        out["CCC"] = out["DSO"] + out["DIO"] - out["DPO"]
    return out or None


# --------------------------------------------------------------------------- #
#  Valuation vs reference
# --------------------------------------------------------------------------- #
def multiples_table(data: CompanyData, fwd, ref, tr, peers=None) -> list[dict]:
    """Company multiples at the current price and at our target, against sector reference/peers."""
    y = data.latest
    price, shares = data.price, data.shares_diluted
    ev = data.market_cap + data.net_debt + (y.minority_interest or 0)
    ebitda_ntm = _ebitda_ntm(data, fwd)
    rows = []

    def add(name, now, at_target, ref_v, peer_v, fmt="x", lower_better=True):
        prem = (now / ref_v - 1) if (now and ref_v) else None
        rows.append({"metric": name, "now": now, "target": at_target, "ref": ref_v, "peer": peer_v,
                     "prem": prem, "fmt": fmt, "lower_better": lower_better})

    pe_peer = _peer_stat(peers or [], "pe")[0]
    if fwd.eps_ntm and fwd.eps_ntm > 0:
        add("P/E (NTM)", price / fwd.eps_ntm, tr.target / fwd.eps_ntm, ref.pe, pe_peer)
    if ebitda_ntm and ebitda_ntm > 0:
        tgt_ev = tr.target * shares + data.net_debt + (y.minority_interest or 0)
        add("EV/EBITDA (NTM)", ev / ebitda_ntm, tgt_ev / ebitda_ntm, ref.ev_ebitda, _peer_stat(peers or [], "ev_ebitda")[0])
    if fwd.rev_ntm and fwd.rev_ntm > 0:
        tgt_ev = tr.target * shares + data.net_debt + (y.minority_interest or 0)
        add("EV/Sales (NTM)", ev / fwd.rev_ntm, tgt_ev / fwd.rev_ntm, ref.ev_sales, _peer_stat(peers or [], "ev_sales")[0])
    bv = (y.total_equity - (y.minority_interest or 0)) / shares if shares else 0
    if bv > 0:
        add("P/B", price / bv, tr.target / bv, ref.pb, _peer_stat(peers or [], "pb")[0])
    f = y.operating_cash_flow - y.capex
    if data.market_cap and f:
        add("FCF yield (LTM)", f / data.market_cap, f / (tr.target * shares) if tr.target else None, None, None,
            fmt="pct", lower_better=False)
    if data.dividend_per_share and price:
        add("Dividend yield", data.dividend_per_share / price, data.dividend_per_share / tr.target if tr.target else None,
            None, None, fmt="pct", lower_better=False)
    if fwd.eps_ntm and fwd.eps_ntm > 0 and fwd.growth and fwd.growth > 0.01:
        add("PEG", price / fwd.eps_ntm / (fwd.growth * 100), tr.target / fwd.eps_ntm / (fwd.growth * 100),
            None, None, fmt="x2")
    return rows


# --------------------------------------------------------------------------- #
#  Scenarios and the price -> target bridge
# --------------------------------------------------------------------------- #
def scenario_table(tr, data: CompanyData, scenarios: Optional[dict]) -> dict:
    price, yld = data.price, (tr.dps / data.price if data.price else 0.0)
    probs = {"Bear": 0.25, "Base": 0.50, "Bull": 0.25}
    pts = {"Bear": tr.bear, "Base": tr.target, "Bull": tr.bull}
    rows = []
    for k in ("Bear", "Base", "Bull"):
        row = {"name": k, "p": probs[k], "pt": pts[k], "ret": pts[k] / price - 1 + yld,
               "dcf": None, "g1": None, "m_end": None}
        if scenarios and k.lower() in scenarios:
            d = scenarios[k.lower()]
            row["dcf"] = d.value_per_share
        rows.append(row)
    expected = sum(r["p"] * r["pt"] for r in rows)
    return {"rows": rows, "expected": expected, "expected_ret": expected / price - 1 + yld}


def target_bridge(tr) -> list[dict]:
    """Waterfall from the current price to the published target."""
    fv, ke, dps = tr.fair_value, tr.ke, tr.dps
    steps = [
        {"label": "Price", "value": tr.price, "kind": "total"},
        {"label": "Re-rating to fair value", "value": fv - tr.price, "kind": "delta"},
        {"label": "Ke carry (12m)", "value": fv * ke, "kind": "delta"},
    ]
    if dps:
        steps.append({"label": "Dividends paid", "value": -dps, "kind": "delta"})
    steps.append({"label": "Model target", "value": tr.model_target, "kind": "total"})
    adj = tr.target - tr.model_target
    if abs(adj) > 1e-6 * max(tr.price, 1):
        steps.append({"label": "Street / guardrail", "value": adj, "kind": "delta"})
    steps.append({"label": "12M target", "value": tr.target, "kind": "total"})
    return steps


# --------------------------------------------------------------------------- #
#  KPI tiles and the factor scorecard
# --------------------------------------------------------------------------- #
def kpi_tiles(data: CompanyData, fwd, ref, tr, tax: float) -> list[dict]:
    y = data.latest
    ev = data.market_cap + data.net_debt + (y.minority_interest or 0)
    ebitda = y.ebitda or (y.ebit + y.depreciation_amort)
    rs = returns_series(data, tax)
    ys = data.years[-5:]
    ebitda_ntm = _ebitda_ntm(data, fwd)
    f = y.operating_cash_flow - y.capex
    tiles = []

    def tile(label, value, fmt, sub, spark=None, tone=None):
        tiles.append({"label": label, "value": value, "fmt": fmt, "sub": sub, "spark": spark or [], "tone": tone})

    cur = data.currency_symbol

    def mny(v):
        a = abs(v)
        return f"{cur}{a/1e12:,.2f}trn" if a >= 1e12 else f"{cur}{a/1e9:,.2f}bn" if a >= 1e9 else f"{cur}{a/1e6:,.0f}mn"

    tile("Market cap", data.market_cap, "money", f"EV {mny(ev)}")
    if fwd.eps_ntm and fwd.eps_ntm > 0:
        pe = data.price / fwd.eps_ntm
        tile("P/E · NTM", pe, "x", f"sector ref {ref.pe:.1f}x", None, "up" if pe < ref.pe else "down")
    if ebitda_ntm and ebitda_ntm > 0:
        m = ev / ebitda_ntm
        tile("EV/EBITDA · NTM", m, "x", f"sector ref {ref.ev_ebitda:.1f}x", None, "up" if m < ref.ev_ebitda else "down")
    if data.market_cap:
        tile("FCF yield · LTM", f / data.market_cap, "pct", "OCF − capex",
             [yy.operating_cash_flow - yy.capex for yy in ys], "up" if f > 0 else "down")
    roic = next((v for v in reversed(rs["roic"]) if v is not None), None)
    if roic is not None:
        tile("ROIC", roic, "pct", "NOPAT / invested capital", [v for v in rs["roic"] if v is not None])
    if ebitda and ebitda > 0:
        nd = (y.total_debt - y.cash_and_sti) / ebitda
        tile("Net debt / EBITDA", nd, "x", "net cash" if nd < 0 else "x EBITDA", None, "up" if nd < 1.5 else "down")
    if fwd.rev_fy1 and y.revenue:
        tile("Revenue growth · FY+1", fwd.rev_fy1 / y.revenue - 1, "pct", f"FY{fwd.fy1_year}E consensus",
             [yy.revenue for yy in ys])
    tile("EBIT margin", y.ebit_margin, "pct", "latest fiscal year", [yy.ebit_margin for yy in ys if yy.ebit_margin is not None])
    return tiles


def scorecard(data: CompanyData, tr, fwd, cycle: Optional[dict], wacc: float, tax: float) -> list[dict]:
    y = data.latest
    rs = returns_series(data, tax)
    roic = next((v for v in reversed(rs["roic"]) if v is not None), None)
    pio, alt, accr = piotroski(data), altman_z(data), accruals(data)
    ebitda = y.ebitda or (y.ebit + y.depreciation_amort)
    lev = (y.total_debt - y.cash_and_sti) / ebitda if ebitda and ebitda > 0 else None
    cov = y.ebit / y.interest_expense if y.interest_expense else None
    conv = y.operating_cash_flow / y.net_income if y.net_income and y.net_income > 0 else None
    g_rev = (fwd.rev_fy1 / y.revenue - 1) if (fwd.rev_fy1 and y.revenue) else None

    def avg(*xs):
        xs = [x for x in xs if x is not None]
        return sum(xs) / len(xs) if xs else None

    axes = []

    def add(axis, score, metric):
        if score is not None:
            axes.append({"axis": axis, "score": round(score), "metric": metric})

    add("Valuation", lin(tr.total_return, -0.30, 0.50), f"12m expected return {tr.total_return:+.0%}")
    gscore = avg(lin(fwd.growth, 0.0, 0.25), lin(min(g_rev, 0.6) if g_rev is not None else None, -0.05, 0.30))
    add("Growth", gscore, f"durable EPS growth {fwd.growth:.1%}" + (f" · FY+1 revenue {g_rev:+.0%}" if g_rev is not None else ""))
    pscore = avg(lin(roic - wacc, -0.05, 0.25) if roic is not None else None, lin(y.ebit_margin, 0.0, 0.35))
    add("Profitability", pscore, f"ROIC {roic:.1%} vs WACC {wacc:.1%}" if roic is not None else f"EBIT margin {y.ebit_margin:.0%}")
    qparts = [lin(conv, 0.5, 1.2)]
    if pio["available"] >= 5:
        qparts.append(pio["score"] / pio["available"] * 100)
    if accr is not None:
        qparts.append(lin(-accr, -0.10, 0.05))
    qs = avg(*qparts)
    qm = []
    if pio["available"] >= 5:
        qm.append(f"Piotroski {pio['score']}/{pio['available']}")
    if conv is not None:
        qm.append(f"OCF/NI {conv:.1f}x")
    add("Earnings quality", qs, " · ".join(qm))
    bparts = [None if lev is None else (100 if lev <= 0 else max(0.0, 100 - lev * 20)), lin(cov, 1.0, 12.0) if cov else None]
    if alt:
        bparts.append({"safe": 90, "grey": 50, "distress": 10}[alt["zone"]])
    bs = avg(*bparts)
    bm = [f"net debt/EBITDA {lev:.1f}x" if lev is not None and lev > 0 else "net cash"] if lev is not None else []
    if alt:
        bm.append(f"Altman Z {alt['z']:.1f}")
    add("Balance sheet", bs, " · ".join(bm))
    if cycle and cycle.get("tilt") is not None:
        add("Cycle fit", lin(cycle["tilt"], -4.0, 4.0), f"Reloj tilt {cycle['tilt']:+.1f} pp/yr in {cycle['asset']}")
    return axes
