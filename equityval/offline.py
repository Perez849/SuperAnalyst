"""Offline snapshots: run the real Yahoo provider code against a saved payload.

A snapshot is the JSON shape of what yfinance returned (``info`` dict, the three
statements as ``{label: {year: value}}`` and the 0y/+1y consensus tables). Feeding it
through ``YFinanceProvider.company`` exercises exactly the production parsing path, so
results are reproducible without network access -- handy for regression tests, for
re-rendering a report from a past run, and for working behind a firewall.

    python valorar.py --snapshot tests/fixtures/MU.json
"""
from __future__ import annotations

import json
from pathlib import Path

from .providers import YFinanceProvider
from .schema import CompanyData


class _FakeTicker:
    def __init__(self, payload: dict):
        import pandas as pd

        def frame(rows: dict):
            years = sorted({int(y) for series in rows.values() for y in series}, reverse=True)
            cols = [pd.Timestamp(f"{y}-12-31") for y in years]
            data = {c: {label: (series.get(str(y), series.get(y)) if series else None)
                        for label, series in rows.items()} for c, y in zip(cols, years)}
            return pd.DataFrame(data, columns=cols).astype(float)

        def est(d):
            if not d or all(v is None for v in d.values()):
                return pd.DataFrame()
            idx = [k for k, v in d.items() if v is not None]
            return pd.DataFrame({"avg": [d[k] for k in idx], "growth": [None] * len(idx)}, index=idx)

        self.info = payload.get("info", {})
        self.income_stmt = self.financials = frame(payload["income"])
        self.balance_sheet = frame(payload["balance"])
        self.cashflow = frame(payload["cashflow"])
        self.revenue_estimate = est(payload.get("revenue_estimate"))
        self.earnings_estimate = est(payload.get("earnings_estimate"))
        self.growth_estimates = None
        self.fast_info = {}

    def history(self, period="5d"):
        import pandas as pd
        return pd.DataFrame()


class SnapshotProvider(YFinanceProvider):
    """YFinanceProvider whose network layer is replaced by a saved payload."""

    def __init__(self, payload: dict):
        self._payload = payload

    def _ticker(self):
        return _FakeTicker(self._payload)

    def company(self, ticker: str, years: int = 6) -> CompanyData:
        # the production parser calls the (static) factory; point it at our payload
        orig = YFinanceProvider._make_ticker
        YFinanceProvider._make_ticker = staticmethod(lambda _t: self._ticker())
        try:
            return super().company(ticker, years)
        finally:
            YFinanceProvider._make_ticker = orig

    def peer(self, ticker):            # no network: reference multiples carry the comps
        return None

    def peer_list(self, ticker, limit=8):
        return []


def load_snapshot(path: str | Path):
    """Return (CompanyData, provider) for a saved snapshot."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    prov = SnapshotProvider(payload)
    data = prov.company(payload["ticker"], years=8)
    asof = payload.get("asof")
    data.provider = f"Yahoo snapshot as of {asof}" if asof else f"snapshot ({Path(path).name})"
    data.asof = asof
    return data, prov
