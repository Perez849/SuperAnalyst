"""Data providers.

Two live sources:
  - FMP  (Financial Modeling Prep) -> best fundamentals, needs a free API key
  - yfinance -> keyless fallback, fundamentals a bit patchier

Both normalize into schema.CompanyData. If a field is missing the provider
leaves it at a neutral default and the assumption engine copes.

Usage:
    from equityval.providers import get_company
    data = get_company("AAPL", provider="auto", fmp_key="....")
"""
from __future__ import annotations

import os
from typing import Optional

from .schema import CompanyData, Estimates, PeerData, YearFinancials


# --------------------------------------------------------------------------- #
#  Helpers
# --------------------------------------------------------------------------- #
def _f(x, default=0.0) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except (TypeError, ValueError):
        return default




def _fyear(r):
    """Year key across legacy (calendarYear) and stable (fiscalYear/date) schemas."""
    v = r.get("calendarYear") or r.get("fiscalYear")
    if v:
        return int(v)
    d = r.get("date") or ""
    return int(d[:4]) if d[:4].isdigit() else None


def _rows_from_fmp(records: list, skip=("date","symbol","reportedCurrency","cik","fillingDate",
                                        "filingDate","acceptedDate","calendarYear","fiscalYear",
                                        "period","link","finalLink")) -> list:
    """FMP statement dicts -> [(label, {year: value})] preserving line order."""
    if not records:
        return []
    years = [_fyear(r) for r in records if _fyear(r)]
    keys = [k for k in records[0].keys() if k not in skip]
    out = []
    for k in keys:
        series = {}
        for rec, yr in zip(records, years):
            v = rec.get(k)
            if isinstance(v, (int, float)):
                series[yr] = float(v)
        if series:
            label = "".join((" " + ch if ch.isupper() else ch) for ch in k).strip().capitalize()
            out.append((label, series))
    return out


# --------------------------------------------------------------------------- #
#  FMP provider
# --------------------------------------------------------------------------- #
class FMPProvider:
    STABLE = "https://financialmodelingprep.com/stable"
    BASE = "https://financialmodelingprep.com/api/v3"   # legacy fallback
    BASE4 = "https://financialmodelingprep.com/api/v4"

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("FMP provider requires an API key.")
        self.key = api_key
        import requests
        self._s = requests.Session()

    def _raw(self, url, **params):
        params["apikey"] = self.key
        r = self._s.get(url, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict) and data.get("Error Message"):
            raise RuntimeError(data["Error Message"])
        return data

    def _stmt(self, name, ticker, years):
        """Fetch a statement/profile from the stable API (symbol in query)."""
        return self._raw(f"{self.STABLE}/{name}", symbol=ticker, limit=years)

    def _get(self, url, **params):   # kept for any legacy calls
        return self._raw(url, **params)

    def company(self, ticker: str, years: int = 6) -> CompanyData:
        inc = self._stmt("income-statement", ticker, years)
        bs = self._stmt("balance-sheet-statement", ticker, years)
        cf = self._stmt("cash-flow-statement", ticker, years)
        prof = self._raw(f"{self.STABLE}/profile", symbol=ticker)
        try:
            km = self._stmt("key-metrics", ticker, years)
        except Exception:
            km = []

        if not inc or not prof:
            raise ValueError(f"FMP returned no data for {ticker}")
        prof = prof[0]

        # FMP returns newest-first; reverse to oldest-first and align by year
        inc = list(reversed(inc))
        bs = list(reversed(bs))
        cf = list(reversed(cf))
        km = list(reversed(km))

        def _by_year(rows):
            return {_fyear(r): r for r in rows if _fyear(r)}

        bsy, cfy, kmy = _by_year(bs), _by_year(cf), _by_year(km)

        yfin: list[YearFinancials] = []
        for r in inc:
            yr = _fyear(r)
            b = bsy.get(yr, {})
            c = cfy.get(yr, {})
            k = kmy.get(yr, {})
            da = _f(r.get("depreciationAndAmortization")) or _f(c.get("depreciationAndAmortization"))
            ebitda = _f(r.get("ebitda")) or (_f(r.get("operatingIncome")) + da)
            # change in NWC: FMP gives changeInWorkingCapital as a cash-flow item
            # (positive = cash inflow). We want the OUTFLOW convention (increase = +).
            cwc = -_f(c.get("changeInWorkingCapital"))
            yfin.append(YearFinancials(
                year=yr,
                revenue=_f(r.get("revenue")),
                ebit=_f(r.get("operatingIncome")),
                ebitda=ebitda,
                depreciation_amort=da,
                interest_expense=abs(_f(r.get("interestExpense"))),
                pretax_income=_f(r.get("incomeBeforeTax")),
                tax_expense=_f(r.get("incomeTaxExpense")),
                net_income=_f(r.get("netIncome")),
                eps_diluted=_f(r.get("epsdiluted")) or _f(r.get("eps")),
                capex=abs(_f(c.get("capitalExpenditure"))),
                change_in_nwc=cwc,
                operating_cash_flow=_f(c.get("operatingCashFlow")),
                total_debt=_f(b.get("totalDebt")),
                cash_and_sti=_f(b.get("cashAndShortTermInvestments")),
                total_equity=_f(b.get("totalStockholdersEquity")),
                minority_interest=_f(b.get("minorityInterest")),
                invested_capital=_f(k.get("investedCapital")) or None,
            ))

        est = Estimates()
        try:
            an = self._raw(f"{self.STABLE}/analyst-estimates", symbol=ticker, limit=4, period="annual")
            if an:
                an = list(reversed(an))
                latest_rev = yfin[-1].revenue
                future = [a for a in an if a.get("date") and int(a["date"][:4]) > yfin[-1].year]
                if future and latest_rev:
                    est.revenue_growth_next = _f(future[0].get("estimatedRevenueAvg")) / latest_rev - 1
                    if len(future) > 1 and _f(future[0].get("estimatedRevenueAvg")):
                        est.revenue_growth_2y = (_f(future[1].get("estimatedRevenueAvg"))
                                                 / _f(future[0].get("estimatedRevenueAvg")) - 1)
                    est.eps_next = _f(future[0].get("estimatedEpsAvg")) or None
        except Exception:
            pass
        try:
            tgt = self._raw(f"{self.STABLE}/price-target-consensus", symbol=ticker)
            if tgt:
                est.target_price_mean = _f(tgt[0].get("targetConsensus")) or None
        except Exception:
            pass

        raw = {"income": _rows_from_fmp(inc), "balance": _rows_from_fmp(bs),
               "cashflow": _rows_from_fmp(cf)}
        shares = _f(inc[-1].get("weightedAverageShsOutDil")) or _f(prof.get("mktCap")) / _f(prof.get("price"), 1)
        return CompanyData(
            ticker=ticker.upper(),
            name=prof.get("companyName", ticker),
            currency=prof.get("currency", "USD"),
            sector=prof.get("sector", ""),
            industry=prof.get("industry", ""),
            price=_f(prof.get("price")),
            shares_diluted=shares,
            market_cap=_f(prof.get("mktCap")),
            beta=_f(prof.get("beta")) or None,
            dividend_per_share=abs(_f(cf[-1].get("dividendsPaid"))) / shares if shares else 0.0,
            years=yfin,
            estimates=est,
            provider="FMP",
            raw_statements=raw,
        )

    def peer(self, ticker: str) -> Optional[PeerData]:
        try:
            prof = self._raw(f"{self.STABLE}/profile", symbol=ticker)[0]
            inc = self._stmt("income-statement", ticker, 1)[0]
            bs = self._stmt("balance-sheet-statement", ticker, 1)[0]
            cf = self._stmt("cash-flow-statement", ticker, 1)[0]
            mc = _f(prof.get("mktCap"))
            debt = _f(bs.get("totalDebt"))
            cash = _f(bs.get("cashAndShortTermInvestments"))
            da = _f(inc.get("depreciationAndAmortization")) or _f(cf.get("depreciationAndAmortization"))
            fcf = _f(cf.get("operatingCashFlow")) - abs(_f(cf.get("capitalExpenditure")))
            return PeerData(
                ticker=ticker.upper(), name=prof.get("companyName", ticker),
                market_cap=mc, ev=mc + debt - cash,
                ebitda=_f(inc.get("ebitda")) or _f(inc.get("operatingIncome")) + da,
                ebit=_f(inc.get("operatingIncome")), revenue=_f(inc.get("revenue")),
                net_income=_f(inc.get("netIncome")), eps=_f(inc.get("epsdiluted")),
                price=_f(prof.get("price")), fcf=fcf,
            )
        except Exception:
            return None

    def peer_list(self, ticker: str, limit: int = 8) -> list[str]:
        try:
            data = self._raw(f"{self.STABLE}/stock-peers", symbol=ticker)
            if data:
                if isinstance(data, list) and data and isinstance(data[0], dict):
                    if data[0].get("peersList"):
                        return data[0]["peersList"][:limit]
                    syms = [d.get("symbol") for d in data if d.get("symbol")]
                    if syms:
                        return syms[:limit]
        except Exception:
            pass
        return []


# --------------------------------------------------------------------------- #
#  yfinance provider (keyless fallback)
# --------------------------------------------------------------------------- #
class YFinanceProvider:
    def company(self, ticker: str, years: int = 6) -> CompanyData:
        import yfinance as yf
        t = yf.Ticker(ticker)
        info = t.info
        fin = t.financials                # income stmt, cols = dates (newest first)
        bs = t.balance_sheet
        cf = t.cashflow

        def row(df, *names):
            for n in names:
                if n in df.index:
                    return df.loc[n]
            return None

        cols = list(fin.columns)[::-1][-years:]   # oldest -> newest
        yfin: list[YearFinancials] = []
        for col in cols:
            yr = col.year

            def g(df, *names):
                r = row(df, *names)
                if r is None or col not in r.index:
                    return 0.0
                return _f(r.get(col))

            rev = g(fin, "Total Revenue")
            ebit = g(fin, "Operating Income", "EBIT")
            da = g(cf, "Depreciation And Amortization", "Depreciation") or g(fin, "Reconciled Depreciation")
            ebitda = g(fin, "EBITDA") or (ebit + da)
            pretax = g(fin, "Pretax Income", "Income Before Tax")
            tax = g(fin, "Tax Provision", "Income Tax Expense")
            ni = g(fin, "Net Income")
            capex = abs(g(cf, "Capital Expenditure", "Capital Expenditures"))
            cwc = -g(cf, "Change In Working Capital")
            ocf = g(cf, "Operating Cash Flow", "Total Cash From Operating Activities")
            debt = g(bs, "Total Debt") or (g(bs, "Long Term Debt") + g(bs, "Current Debt"))
            cash = g(bs, "Cash Cash Equivalents And Short Term Investments", "Cash And Cash Equivalents")
            eq = g(bs, "Stockholders Equity", "Total Stockholder Equity")
            mi = g(bs, "Minority Interest")
            shares_y = g(fin, "Diluted Average Shares", "Basic Average Shares") \
                or _f(info.get("sharesOutstanding")) or 1
            yfin.append(YearFinancials(
                year=yr, revenue=rev, ebit=ebit, ebitda=ebitda, depreciation_amort=da,
                interest_expense=abs(g(fin, "Interest Expense")), pretax_income=pretax,
                tax_expense=tax, net_income=ni, eps_diluted=(ni / shares_y if shares_y else 0.0),
                capex=capex, change_in_nwc=cwc, operating_cash_flow=ocf,
                total_debt=debt, cash_and_sti=cash, total_equity=eq, minority_interest=mi,
            ))

        def _rows_from_df(df):
            out = []
            cols = list(df.columns)[::-1]
            for idx in df.index:
                series = {}
                for c in cols:
                    v = df.loc[idx, c]
                    try:
                        if v == v and v is not None:
                            series[c.year] = float(v)
                    except (TypeError, ValueError):
                        pass
                if series:
                    out.append((str(idx), series))
            return out
        raw = {"income": _rows_from_df(fin), "balance": _rows_from_df(bs),
               "cashflow": _rows_from_df(cf)}

        # --- analyst estimates: revenue path, growth, targets, and a levered-FCF
        #     forecast for the 2-stage FCFE model (Simply-Wall-St style) --------
        est = Estimates(
            revenue_growth_next=_f(info.get("revenueGrowth")) or None,
            target_price_mean=_f(info.get("targetMeanPrice")) or None,
            target_price_high=_f(info.get("targetHighPrice")) or None,
            target_price_low=_f(info.get("targetLowPrice")) or None,
            num_analysts=info.get("numberOfAnalystOpinions"),
            eps_growth_lt=_f(info.get("earningsGrowth")) or None,
        )
        # base levered FCF (FCFE proxy) = operating cash flow - capex, latest year
        base_fcfe = yfin[-1].operating_cash_flow - yfin[-1].capex if yfin else 0.0
        last_year = yfin[-1].year if yfin else None

        # Try to pull a forward revenue growth path from yfinance's estimate tables.
        growth_path = []          # per-year revenue growth from analysts
        try:
            ge = t.growth_estimates          # index like '0y','+1y', etc.
            if ge is not None and not ge.empty:
                col = ge.columns[0]
                for key in ("+1y", "+2y", "+3y", "+4y", "+5y"):
                    if key in ge.index:
                        v = _f(ge.loc[key, col])
                        if v == v and -0.5 < v < 1.0:
                            growth_path.append(v)
        except Exception:
            pass
        try:
            re_tbl = t.revenue_estimate      # rows: '0y','+1y',...
            if re_tbl is not None and not re_tbl.empty and "growth" in re_tbl.columns:
                gp2 = []
                for key in ("+1y", "+2y", "+3y", "+4y", "+5y"):
                    if key in re_tbl.index:
                        v = _f(re_tbl.loc[key, "growth"])
                        if v == v and -0.5 < v < 1.5:
                            gp2.append(v)
                if len(gp2) > len(growth_path):
                    growth_path = gp2
        except Exception:
            pass

        # Build a 10-year levered-FCF path: analyst growth for the covered years,
        # then fade to the long-term/terminal growth. Stored for the FCFE model.
        if base_fcfe > 0 and last_year:
            lt = est.eps_growth_lt if (est.eps_growth_lt and 0 < est.eps_growth_lt < 0.4) else None
            term = 0.035
            path = list(growth_path)
            if not path and lt:
                path = [lt]
            fcfe_path = []
            f = base_fcfe
            for i in range(10):
                if i < len(path):
                    gr = path[i]
                elif path:
                    # fade from last analyst year to terminal over remaining years
                    remain = 10 - len(path)
                    step = (i - len(path) + 1) / max(remain, 1)
                    gr = path[-1] + (term - path[-1]) * step
                else:
                    gr = term
                f = f * (1 + gr)
                fcfe_path.append((last_year + i + 1, f))
            est.fcfe_path = fcfe_path
            est.fcfe_base = base_fcfe

        shares = _f(info.get("sharesOutstanding")) or 1
        return CompanyData(
            ticker=ticker.upper(),
            name=info.get("longName", ticker),
            currency=info.get("currency", "USD"),
            sector=info.get("sector", ""),
            industry=info.get("industry", ""),
            price=_f(info.get("currentPrice")) or _f(info.get("regularMarketPrice")),
            shares_diluted=shares,
            market_cap=_f(info.get("marketCap")),
            beta=_f(info.get("beta")) or None,
            dividend_per_share=_f(info.get("dividendRate")),
            years=yfin, estimates=est, provider="yfinance", raw_statements=raw,
        )

    def peer(self, ticker: str) -> Optional[PeerData]:
        import yfinance as yf
        try:
            info = yf.Ticker(ticker).info
            mc = _f(info.get("marketCap"))
            return PeerData(
                ticker=ticker.upper(), name=info.get("shortName", ticker), market_cap=mc,
                ev=_f(info.get("enterpriseValue")) or mc,
                ebitda=_f(info.get("ebitda")), ebit=_f(info.get("ebitda")) * 0.8,
                revenue=_f(info.get("totalRevenue")), net_income=_f(info.get("netIncomeToCommon")),
                eps=_f(info.get("trailingEps")), price=_f(info.get("currentPrice")),
                fcf=_f(info.get("freeCashflow")),
            )
        except Exception:
            return None

    def peer_list(self, ticker: str, limit: int = 8) -> list[str]:
        return []


# --------------------------------------------------------------------------- #
#  Facade
# --------------------------------------------------------------------------- #
def get_company(ticker: str, provider: str = "auto",
                fmp_key: Optional[str] = None, years: int = 6) -> CompanyData:
    fmp_key = fmp_key or os.environ.get("FMP_API_KEY")
    if provider in ("auto", "fmp") and fmp_key:
        try:
            return FMPProvider(fmp_key).company(ticker, years)
        except Exception as e:
            if provider == "fmp":
                raise
            print(f"[warn] FMP failed ({e}); falling back to yfinance")
    return YFinanceProvider().company(ticker, years)


def get_provider(provider: str = "auto", fmp_key: Optional[str] = None):
    fmp_key = fmp_key or os.environ.get("FMP_API_KEY")
    if provider in ("auto", "fmp") and fmp_key:
        return FMPProvider(fmp_key)
    return YFinanceProvider()
