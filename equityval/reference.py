"""Sector reference data: target multiples, long-run growth, unlevered betas, peer map.

Why this exists
---------------
Sell-side price targets are built as  *target multiple x forward earnings*, with the
multiple anchored on peers and then adjusted for growth/quality. yfinance (the keyless
provider) exposes no peer list, so before this module the comps lens silently never ran
and every target came from a single DCF. These tables give the engine a defensible
multiple anchor when live peers are unavailable, and a sanity bound when they are.

The numbers are long-run, developed-market, large-cap *medians* (Damodaran / index
sector medians, rounded). They are deliberately slow-moving reference points, not
market-timing calls: live peer medians override them whenever >= 3 peers are fetched,
and the growth/quality adjustments in lenses.py do the company-specific work.

Every value is overridable; keep them in this one file so they are easy to audit.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SectorRef:
    pe: float            # forward P/E
    ev_ebitda: float     # forward EV/EBITDA
    ev_sales: float      # forward EV/Sales
    pb: float            # price / book
    growth: float        # long-run EPS growth embedded in the multiples (decimal)
    unlev_beta: float    # Damodaran-style US industry unlevered beta
    margin: float        # typical EBIT margin (sanity anchor for mean reversion)
    label: str = ""


# --- broad sectors (yfinance / GICS-like names, lower-cased) -------------------------
SECTORS: dict[str, SectorRef] = {
    "technology":             SectorRef(24, 17, 6.0, 7.0, 0.12, 1.20, 0.22, "Technology"),
    "communication services": SectorRef(17,  9, 2.5, 3.0, 0.08, 0.92, 0.18, "Communication Services"),
    "consumer cyclical":      SectorRef(19, 12, 1.3, 4.0, 0.09, 1.08, 0.09, "Consumer Cyclical"),
    "consumer defensive":     SectorRef(19, 13, 1.5, 4.0, 0.06, 0.58, 0.10, "Consumer Defensive"),
    "healthcare":             SectorRef(18, 13, 3.5, 4.0, 0.08, 0.88, 0.16, "Healthcare"),
    "industrials":            SectorRef(20, 13, 2.0, 4.0, 0.09, 0.98, 0.12, "Industrials"),
    "energy":                 SectorRef(12,  5.5, 1.2, 1.7, 0.04, 0.95, 0.12, "Energy"),
    "utilities":              SectorRef(17, 11, 2.8, 1.9, 0.06, 0.39, 0.17, "Utilities"),
    "real estate":            SectorRef(16, 17, 8.0, 1.8, 0.04, 0.63, 0.30, "Real Estate"),
    "basic materials":        SectorRef(14,  7, 2.0, 2.0, 0.05, 1.02, 0.14, "Basic Materials"),
    "financial services":     SectorRef(12,  9, 3.0, 1.5, 0.07, 0.90, 0.25, "Financial Services"),
}
DEFAULT_SECTOR = SectorRef(17, 11, 2.0, 3.0, 0.07, 0.90, 0.12, "Market")

# --- industry overrides: first keyword hit wins (checked against sector+industry) -----
INDUSTRIES: list[tuple[tuple[str, ...], SectorRef]] = [
    (("semiconductor equipment",), SectorRef(24, 17, 7.0, 7.0, 0.12, 1.30, 0.28, "Semiconductor equipment")),
    (("semiconductor",),           SectorRef(21, 15, 7.0, 5.0, 0.12, 1.30, 0.25, "Semiconductors")),
    (("software",),                SectorRef(27, 20, 8.0, 9.0, 0.15, 1.20, 0.22, "Software")),
    (("internet", "interactive media"), SectorRef(21, 13, 4.5, 5.0, 0.13, 1.20, 0.22, "Internet")),
    (("computer hardware", "data storage", "consumer electronics", "electronic component"),
                                   SectorRef(17, 11, 2.5, 5.0, 0.09, 1.10, 0.13, "Hardware & storage")),
    (("information technology services", "it services"),
                                   SectorRef(18, 12, 2.5, 5.0, 0.09, 1.00, 0.15, "IT services")),
    (("biotech",),                 SectorRef(20, 14, 6.0, 4.5, 0.12, 1.10, 0.20, "Biotech")),
    (("drug manufacturers", "pharma"), SectorRef(15, 11, 4.0, 4.0, 0.06, 0.85, 0.28, "Pharma")),
    (("medical devices", "medical instruments", "diagnostics"),
                                   SectorRef(24, 16, 4.5, 4.5, 0.09, 0.95, 0.20, "Medtech")),
    (("bank",),                    SectorRef(11,  9, 3.0, 1.2, 0.06, 0.60, 0.30, "Banks")),
    (("insurance", "reinsurance"), SectorRef(12,  9, 1.2, 1.7, 0.07, 0.70, 0.12, "Insurance")),
    (("asset management", "capital markets", "financial data", "credit services"),
                                   SectorRef(16, 11, 4.0, 3.0, 0.09, 1.10, 0.35, "Capital markets")),
    (("reit", "real estate investment trust"),
                                   SectorRef(16, 17, 8.0, 1.8, 0.04, 0.63, 0.30, "REITs")),
    (("independent power", "renewable utilit", "power producer"),
                                   SectorRef(19, 11, 3.0, 3.0, 0.09, 0.75, 0.18, "Power producers")),
    (("utilities - regulated", "regulated electric", "regulated gas", "regulated water", "multi-utilit"),
                                   SectorRef(17, 11, 2.8, 1.9, 0.06, 0.39, 0.17, "Regulated utilities")),
    (("gold", "silver"),           SectorRef(12,  6.5, 3.2, 2.2, 0.06, 0.95, 0.30, "Precious metals")),
    (("uranium",),                 SectorRef(30, 18, 12.0, 3.5, 0.15, 1.20, 0.25, "Uranium")),
    (("copper", "other industrial metals", "aluminum"),
                                   SectorRef(13,  6.5, 2.0, 2.0, 0.05, 1.05, 0.18, "Base metals")),
    (("steel",),                   SectorRef(10,  5.5, 0.7, 1.1, 0.03, 1.05, 0.08, "Steel")),
    (("oil & gas e&p", "oil & gas exploration"),
                                   SectorRef(11,  4.5, 2.2, 1.6, 0.03, 1.00, 0.28, "Oil & gas E&P")),
    (("oil & gas integrated",),    SectorRef(12,  5.0, 1.0, 1.7, 0.03, 0.85, 0.11, "Integrated oil")),
    (("oil & gas midstream",),     SectorRef(14, 10.0, 2.8, 2.5, 0.04, 0.70, 0.22, "Midstream")),
    (("oil & gas refining", "oil & gas equipment", "oil & gas drilling"),
                                   SectorRef(11,  6.0, 0.7, 1.8, 0.04, 1.05, 0.06, "Energy services")),
    (("aerospace", "defense"),     SectorRef(24, 16, 2.5, 6.0, 0.10, 0.95, 0.12, "Aerospace & defense")),
    (("auto manufacturers",),      SectorRef(9,   6.0, 0.6, 1.4, 0.04, 1.10, 0.06, "Autos")),
    (("airlines",),                SectorRef(8,   5.0, 0.6, 2.0, 0.04, 1.20, 0.08, "Airlines")),
    (("specialty retail", "internet retail", "department stores"),
                                   SectorRef(20, 12, 1.2, 5.0, 0.09, 1.10, 0.08, "Retail")),
    (("beverages", "packaged foods", "household", "tobacco", "grocery", "discount stores"),
                                   SectorRef(19, 13, 1.8, 4.5, 0.05, 0.60, 0.15, "Staples")),
    (("restaurants",),             SectorRef(23, 15, 3.5, 8.0, 0.09, 0.95, 0.20, "Restaurants")),
    (("telecom",),                 SectorRef(12,  7, 2.0, 2.0, 0.03, 0.70, 0.20, "Telecom")),
    (("engineering", "construction", "building products", "specialty industrial", "machinery",
      "electrical equipment", "farm & heavy"),
                                   SectorRef(21, 14, 2.3, 5.0, 0.10, 1.05, 0.14, "Industrial equipment")),
]


def lookup(sector: str | None, industry: str | None) -> SectorRef:
    """Most specific reference for a sector/industry (industry keywords beat sector)."""
    s = (sector or "").strip().lower()
    i = (industry or "").strip().lower()
    blob = f"{s} {i}"
    for kws, ref in INDUSTRIES:
        if any(k in blob for k in kws):
            return ref
    return SECTORS.get(s, DEFAULT_SECTOR)


# --- peer candidates (liquid, well-covered names) used when the provider lists none ---
_PEERS: list[tuple[tuple[str, ...], list[str]]] = [
    (("data storage", "computer hardware"),
     ["WDC", "STX", "MU", "NTAP", "PSTG", "DELL", "HPQ", "SMCI"]),
    (("semiconductor equipment",), ["AMAT", "LRCX", "KLAC", "ASML", "TER", "ENTG"]),
    (("semiconductor",),
     ["NVDA", "AMD", "AVGO", "TSM", "QCOM", "TXN", "MU", "INTC", "MRVL", "ADI", "MCHP"]),
    (("software",),
     ["MSFT", "ORCL", "CRM", "ADBE", "NOW", "INTU", "SNPS", "CDNS", "WDAY"]),
    (("internet", "interactive media"), ["GOOGL", "META", "AMZN", "NFLX", "PINS", "SNAP"]),
    (("independent power", "power producer"), ["VST", "NRG", "CEG", "TLN", "AES"]),
    (("regulated", "utilit"),
     ["NEE", "DUK", "SO", "AEP", "D", "EXC", "XEL", "SRE", "PEG", "ED"]),
    (("uranium",), ["CCJ", "UEC", "UUUU", "DNN", "NXE", "EU"]),
    (("gold",), ["NEM", "AEM", "GFI", "AU", "KGC", "WPM", "FNV", "HMY"]),
    (("silver",), ["WPM", "PAAS", "AG", "HL", "CDE"]),
    (("copper", "industrial metals"), ["FCX", "SCCO", "TECK", "RIO", "BHP", "VALE"]),
    (("steel",), ["NUE", "STLD", "CLF", "X", "MT"]),
    (("oil & gas integrated",), ["XOM", "CVX", "SHEL", "BP", "TTE", "COP"]),
    (("oil & gas e&p", "oil & gas exploration"),
     ["COP", "EOG", "DVN", "FANG", "OXY", "APA", "HES"]),
    (("oil & gas midstream",), ["KMI", "WMB", "OKE", "ET", "EPD", "MPLX"]),
    (("bank",), ["JPM", "BAC", "WFC", "C", "USB", "PNC", "TFC", "GS", "MS"]),
    (("insurance",), ["BRK-B", "CB", "PGR", "TRV", "AIG", "ALL", "MET", "PRU"]),
    (("asset management", "capital markets"), ["BLK", "BX", "KKR", "APO", "SCHW", "MS", "GS"]),
    (("reit",), ["PLD", "AMT", "EQIX", "O", "SPG", "PSA", "WELL", "DLR"]),
    (("biotech",), ["AMGN", "GILD", "VRTX", "REGN", "BIIB", "MRNA"]),
    (("drug manufacturers", "pharma"), ["LLY", "JNJ", "MRK", "PFE", "ABBV", "NVS", "AZN", "BMY"]),
    (("medical",), ["MDT", "ABT", "SYK", "BSX", "ISRG", "EW", "ZBH"]),
    (("aerospace", "defense"), ["BA", "LMT", "RTX", "NOC", "GD", "GE", "HWM"]),
    (("auto manufacturers",), ["TSLA", "TM", "GM", "F", "STLA", "HMC"]),
    (("airlines",), ["DAL", "UAL", "LUV", "AAL"]),
    (("beverages", "packaged foods", "household"), ["KO", "PEP", "PG", "MDLZ", "CL", "KHC", "GIS"]),
    (("specialty retail", "internet retail"), ["AMZN", "HD", "LOW", "COST", "TGT", "WMT", "TJX"]),
    (("restaurants",), ["MCD", "SBUX", "CMG", "YUM", "DRI"]),
    (("telecom",), ["T", "VZ", "TMUS", "CMCSA", "CHTR"]),
    (("machinery", "electrical equipment", "specialty industrial", "engineering"),
     ["CAT", "DE", "ETN", "EMR", "ITW", "PH", "ROK", "HON", "GE"]),
    (("information technology services",), ["ACN", "IBM", "CTSH", "EPAM", "IT"]),
]

_SECTOR_FALLBACK_PEERS = {
    "technology": ["MSFT", "AAPL", "NVDA", "AVGO", "ORCL", "CRM"],
    "healthcare": ["JNJ", "LLY", "UNH", "ABT", "MRK", "TMO"],
    "financial services": ["JPM", "BAC", "GS", "MS", "BLK", "SCHW"],
    "consumer cyclical": ["AMZN", "HD", "MCD", "NKE", "LOW", "TJX"],
    "consumer defensive": ["PG", "KO", "PEP", "COST", "WMT", "MDLZ"],
    "industrials": ["CAT", "HON", "GE", "UNP", "DE", "ETN"],
    "energy": ["XOM", "CVX", "COP", "EOG", "SLB", "OXY"],
    "utilities": ["NEE", "DUK", "SO", "AEP", "D", "EXC"],
    "real estate": ["PLD", "AMT", "EQIX", "O", "SPG", "PSA"],
    "basic materials": ["LIN", "SHW", "FCX", "NEM", "NUE", "APD"],
    "communication services": ["GOOGL", "META", "NFLX", "DIS", "T", "VZ"],
}


def peer_candidates(ticker: str, sector: str | None, industry: str | None,
                    limit: int = 8) -> list[str]:
    """Curated, liquid peers for the company's industry (never the company itself)."""
    blob = f"{(sector or '').lower()} {(industry or '').lower()}"
    t = ticker.upper()
    for kws, names in _PEERS:
        if any(k in blob for k in kws):
            return [n for n in names if n != t][:limit]
    return [n for n in _SECTOR_FALLBACK_PEERS.get((sector or "").lower(), []) if n != t][:limit]
