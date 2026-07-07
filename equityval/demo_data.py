"""A synthetic but internally-consistent large-cap, for offline demos/tests.

Clearly labelled as illustrative — not a real company's financials.
"""
from __future__ import annotations

from .schema import CompanyData, Estimates, PeerData, YearFinancials


def demo_company() -> CompanyData:
    years = []
    rev = 58.0e9
    for i, yr in enumerate(range(2020, 2026)):
        rev *= (1 + [0.0, 0.11, 0.09, 0.07, 0.08, 0.06][i])
        ebit_m = 0.26 + i * 0.005
        ebit = rev * ebit_m
        da = rev * 0.052
        ebitda = ebit + da
        interest = 0.55e9
        pretax = ebit - interest + 0.2e9
        tax = pretax * 0.19
        ni = pretax - tax
        shares = 1.62e9 - i * 0.02e9
        years.append(YearFinancials(
            year=yr, revenue=rev, ebit=ebit, ebitda=ebitda, depreciation_amort=da,
            interest_expense=interest, pretax_income=pretax, tax_expense=tax,
            net_income=ni, eps_diluted=ni / shares,
            capex=rev * 0.048, change_in_nwc=rev * 0.012,
            operating_cash_flow=ni + da,
            total_debt=12.0e9, cash_and_sti=9.5e9 + i * 0.6e9,
            total_equity=28e9 + i * 2e9, minority_interest=0.3e9,
        ))
    def series(attr):
        return {y.year: getattr(y, attr) for y in years}
    raw = {
        "income": [("Revenue", series("revenue")), ("EBIT (operating income)", series("ebit")),
                   ("EBITDA", series("ebitda")), ("D&A", series("depreciation_amort")),
                   ("Interest expense", series("interest_expense")),
                   ("Pre-tax income", series("pretax_income")), ("Tax expense", series("tax_expense")),
                   ("Net income", series("net_income"))],
        "balance": [("Total debt", series("total_debt")), ("Cash & ST investments", series("cash_and_sti")),
                    ("Total equity", series("total_equity")), ("Minority interest", series("minority_interest"))],
        "cashflow": [("Operating cash flow", series("operating_cash_flow")), ("Capex", series("capex")),
                     ("Change in NWC", series("change_in_nwc"))],
    }
    return CompanyData(
        ticker="DEMO", name="Meridian Industrials (illustrative)", currency="USD",
        sector="Industrials", industry="Diversified Machinery",
        price=182.0, shares_diluted=1.52e9, market_cap=182.0 * 1.52e9,
        beta=1.12, dividend_per_share=2.40, years=years,
        estimates=Estimates(revenue_growth_next=0.07, target_price_mean=205.0,
                             num_analysts=24),
        provider="DEMO (synthetic)",
        raw_statements=raw,
    )


def demo_peers() -> list[PeerData]:
    base = [
        ("PEERA", 155e9, 9.0e9, 62e9, 6.2, 148),
        ("PEERB", 98e9, 6.1e9, 41e9, 5.1, 121),
        ("PEERC", 210e9, 12.5e9, 78e9, 8.9, 262),
        ("PEERD", 76e9, 4.8e9, 33e9, 4.2, 88),
        ("PEERE", 134e9, 8.2e9, 55e9, 7.4, 176),
    ]
    peers = []
    for tk, mc, ebitda, rev, eps, px in base:
        ebit = ebitda * 0.78
        peers.append(PeerData(
            ticker=tk, name=tk, market_cap=mc, ev=mc + 10e9 - 6e9,
            ebitda=ebitda, ebit=ebit, revenue=rev, net_income=ebitda * 0.45,
            eps=eps, price=px, fcf=ebitda * 0.55,
        ))
    return peers
