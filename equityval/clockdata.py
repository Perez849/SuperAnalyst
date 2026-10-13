"""Link to the Reloj de inversión (github.com/Perez849/reloj-inversion).

The Reloj classifies the US economic cycle every month into one of four phases from 28 FRED
series (growth x inflation, by robust z-scores + PCA) and records what every equity sector has
*historically* paid in each phase, tested statistically against the market (Newey-West t,
false-discovery control, walk-forward rotation). This module reads its published
``data.json`` and answers, for one company:

  * what phase is the cycle in right now, and how sure is the Reloj (probabilities)?
  * how has this company's sector paid in each phase (excess return vs the market, t-stat,
    hit rate, reliability) and what is the probability-weighted tilt today?
  * is the sector in the Reloj's current playbook, and what weight does the company carry
    inside the sector ETF?

Data is fetched live when the network allows (short timeout) and falls back to a vendored
snapshot (``equityval/data/reloj_snapshot.json``, refreshed by scripts/refresh_reloj.py), so
reports are reproducible offline. Nothing here is invented: if a sector has no Reloj asset
or a company is not a ETF holding, the field is simply None.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Optional

PAGES_URL = "https://perez849.github.io/reloj-inversion/data/data.json"
RAW_URL = "https://raw.githubusercontent.com/Perez849/reloj-inversion/main/docs/data/data.json"
SITE_URL = "https://perez849.github.io/reloj-inversion/"
SNAPSHOT = Path(__file__).resolve().parent / "data" / "reloj_snapshot.json"

PHASES = ["Recuperación", "Sobrecalentamiento", "Estanflación", "Reflación"]
PHASE_EN = {"Recuperación": "Recovery", "Sobrecalentamiento": "Overheat",
            "Estanflación": "Stagflation", "Reflación": "Reflation"}
PHASE_COLOR = {"Recuperación": "#3F6B52", "Sobrecalentamiento": "#B8863B",
               "Estanflación": "#9C4A3C", "Reflación": "#3E4E7A"}
PHASE_HINT = {
    "Recuperación": "growth above trend, inflation below",
    "Sobrecalentamiento": "growth and inflation above trend",
    "Estanflación": "growth below trend, inflation above",
    "Reflación": "growth and inflation below trend",
}

# yfinance/GICS-like sector -> Reloj asset (most specific first via industry keywords)
SECTOR_ASSET = {
    "technology": "Tecnología", "communication services": "Comunicaciones",
    "consumer cyclical": "Consumo discrecional", "consumer defensive": "Consumo básico",
    "healthcare": "Salud", "financial services": "Financiero", "industrials": "Industria",
    "energy": "Energía", "basic materials": "Materiales / Químicas", "utilities": "Utilities",
    "real estate": "Inmobiliario",
}
INDUSTRY_ASSET = [(("semiconductor",), "Semiconductores"), (("gold", "silver"), "Metales preciosos (mineras)")]

ETF_MAP = {
    "Tecnología": [["IYW", "iShares US Technology"], ["XLK", "Technology Select Sector SPDR"]],
    "Semiconductores": [["SOXX", "iShares Semiconductor ETF"], ["SMH", "VanEck Semiconductor ETF"]],
    "Salud": [["IYH", "iShares US Healthcare"], ["XLV", "Health Care Select Sector SPDR"]],
    "Energía": [["IYE", "iShares US Energy"], ["XLE", "Energy Select Sector SPDR"]],
    "Comunicaciones": [["IYZ", "iShares US Telecommunications"], ["XLC", "Communication Services SPDR"]],
    "Financiero": [["IYF", "iShares US Financials"], ["XLF", "Financial Select Sector SPDR"]],
    "Industria": [["IYJ", "iShares US Industrials"], ["XLI", "Industrial Select Sector SPDR"]],
    "Materiales / Químicas": [["IYM", "iShares US Basic Materials"], ["XLB", "Materials Select Sector SPDR"]],
    "Utilities": [["IDU", "iShares US Utilities"], ["XLU", "Utilities Select Sector SPDR"]],
    "Consumo discrecional": [["IYC", "iShares US Consumer Discretionary"], ["XLY", "Consumer Discretionary SPDR"]],
    "Consumo básico": [["IYK", "iShares US Consumer Goods"], ["XLP", "Consumer Staples Select Sector SPDR"]],
    "Inmobiliario": [["IYR", "iShares US Real Estate"], ["XLRE", "Real Estate Select Sector SPDR"]],
    "Metales preciosos (mineras)": [["RING", "iShares MSCI Global Gold Miners"], ["GDX", "VanEck Gold Miners"]],
}
ASSET_EN = {
    "Tecnología": "Technology", "Semiconductores": "Semiconductors", "Salud": "Health care", "Energía": "Energy",
    "Comunicaciones": "Communications", "Financiero": "Financials", "Industria": "Industrials",
    "Materiales / Químicas": "Materials", "Utilities": "Utilities", "Consumo discrecional": "Consumer discretionary",
    "Consumo básico": "Consumer staples", "Inmobiliario": "Real estate", "Metales preciosos (mineras)": "Gold miners",
    "Oro (lingote)": "Gold bullion", "Materias primas (índice)": "Commodities index",
    "Renta variable EE.UU. (mercado)": "US equities (market)",
}
LABEL_EN = {"Inverso de la volatilidad": "Inverse volatility", "Igual ponderación": "Equal weight",
            "Ponderación por señal": "Signal-weighted", "Paridad de riesgo": "Risk parity"}


def en(name):
    """English display name for a Reloj asset / label (falls back to the original)."""
    return ASSET_EN.get(name) or LABEL_EN.get(name) or name


KEEP_ASSETS = set(ETF_MAP) | {"Renta variable EE.UU. (mercado)", "Oro (lingote)", "Materias primas (índice)"}
STAT_KEYS = ("ann", "ann_tot", "rel", "rel_shrunk", "t", "hit", "n", "vol", "reliability", "grade", "q")

_cache: dict = {}


# --------------------------------------------------------------------------- #
def trim(full: dict) -> dict:
    """Reduce the 400 KB data.json to what the reports use (also used for the snapshot)."""
    cur = full["current"]
    assets = {}
    for a in full.get("assets", []):
        if a.get("name") in KEEP_ASSETS:
            assets[a["name"]] = {
                "class": a.get("class"), "uncond_ann": a.get("uncond_ann"),
                "phases": {p: {k: v.get(k) for k in STAT_KEYS} for p, v in (a.get("phases") or {}).items()},
            }
    rot = full.get("rotation", {})
    scheme = (rot.get("schemes") or {}).get(rot.get("default")) or next(iter((rot.get("schemes") or {}).values()), {})
    hold = full.get("holdings", {})
    return {
        "generated_utc": full.get("meta", {}).get("generated_utc"),
        "holdings_asof": (hold.get("meta") or {}).get("as_of"),
        "current": {k: cur.get(k) for k in (
            "date", "phase", "phase_long", "alt_phase", "growth", "inflation", "leading", "sigma_g",
            "sigma_i", "horizon_m", "probs", "confidence", "call_strength", "momentum")}
        | {"recession": {"prob_12m": (cur.get("recession") or {}).get("prob_12m"),
                         "auc": (cur.get("recession") or {}).get("auc")}},
        "history": [{k: h[k] for k in ("d", "g", "i", "p")} for h in full.get("history", [])[-96:]],
        "assets": assets,
        "playbook": dict(scheme.get("playbook") or {}),
        "sleeve_mix": scheme.get("sleeve_mix") or {},
        "playbook_label": scheme.get("label"),
        "holdings": {s: rows[:40] for s, rows in (hold.get("por_sector") or {}).items()},
        "groups": hold.get("grupos") or {},
        "asset_stats": {k: (full.get("asset_stats") or {}).get(k) for k in ("cells", "graded", "fdr_survivors")},
    }


def _fetch(url: str, timeout: float = 6.0) -> Optional[dict]:
    try:
        import requests
        r = requests.get(url, timeout=timeout, headers={"User-Agent": "superanalyst/1.0"})
        if r.ok:
            return r.json()
    except Exception:
        return None
    return None


def load(live: bool = True) -> Optional[dict]:
    """Trimmed Reloj data: live when reachable, else the vendored snapshot. None if neither."""
    if "v" in _cache and _cache.get("live") == live:
        return _cache["v"]
    out = None
    if live and not os.environ.get("EQUITYVAL_OFFLINE"):
        for url in (PAGES_URL, RAW_URL):
            full = _fetch(url)
            if full and full.get("current"):
                out = trim(full)
                out["fetched"], out["source"] = "live", url
                break
    if out is None and SNAPSHOT.exists():
        out = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        out["fetched"], out["source"] = "snapshot", f"snapshot of {SITE_URL}"
    _cache.update(v=out, live=live)
    return out


# --------------------------------------------------------------------------- #
def asset_for(sector: str | None, industry: str | None) -> tuple[Optional[str], Optional[str]]:
    """(specific asset, parent sector asset) in the Reloj's vocabulary."""
    s, i = (sector or "").lower(), (industry or "").lower()
    parent = SECTOR_ASSET.get(s)
    for kws, name in INDUSTRY_ASSET:
        if any(k in i for k in kws):
            return name, parent
    return parent, parent


def _finite(x) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(x)


def holding_for(clock: dict, ticker: str) -> dict:
    """Where the ticker appears in the Reloj's sector-ETF holdings, with subsector group."""
    t = ticker.upper()
    hits = []
    for sector, rows in (clock.get("holdings") or {}).items():
        for rank, r in enumerate(rows, 1):
            if (r.get("ticker") or "").upper() == t:
                hits.append({"sector": sector, "weight": r.get("weight"), "rank": rank})
    group = None
    for sector, groups in (clock.get("groups") or {}).items():
        for g in groups:
            for e in g.get("empresas", []):
                if (e.get("ticker") or "").upper() == t:
                    group = {"sector": sector, "group": g.get("grupo"), "group_weight": g.get("peso"),
                             "weight": e.get("weight")}
    return {"hits": hits, "group": group}


def cycle_view(sector: str | None, industry: str | None, ticker: str, clock: Optional[dict]) -> Optional[dict]:
    """Everything the report needs about the cycle and this company's sector. None if no data."""
    if not clock:
        return None
    cur = clock["current"]
    probs = cur.get("probs") or {}
    phase = cur.get("phase")
    asset, parent = asset_for(sector, industry)
    stats = (clock["assets"].get(asset) or {}).get("phases") if asset else None
    if stats is None and parent:
        asset, stats = parent, (clock["assets"].get(parent) or {}).get("phases")
    market = (clock["assets"].get("Renta variable EE.UU. (mercado)") or {})
    tilt = None
    if stats:
        parts = [(probs.get(p, 0) or 0) * (stats.get(p, {}).get("rel_shrunk") or 0) for p in PHASES]
        tilt = sum(parts)
    edge_now = (stats or {}).get(phase, {}).get("rel_shrunk") if stats else None
    pb = clock.get("playbook") or {}

    def playbook_weight(ph):
        for r in pb.get(ph, []):
            if r.get("name") in (asset, parent):
                return {"name": r["name"], "weight": r.get("weight"), "sleeve": r.get("sleeve")}
        return None

    hold = holding_for(clock, ticker)
    trail = [(h["g"], h["i"], h["p"], h["d"]) for h in clock.get("history", [])[-36:]]
    return {
        "fetched": clock.get("fetched"), "source": clock.get("source"), "asof": cur.get("date"),
        "generated": clock.get("generated_utc"), "phase": phase, "alt": cur.get("alt_phase"),
        "probs": probs, "confidence": cur.get("confidence"), "strength": cur.get("call_strength"),
        "growth": cur.get("growth"), "inflation": cur.get("inflation"),
        "sigma_g": cur.get("sigma_g"), "sigma_i": cur.get("sigma_i"),
        "recession": (cur.get("recession") or {}).get("prob_12m"),
        "momentum": cur.get("momentum") or {}, "trail": trail,
        "asset": asset, "parent": parent, "etfs": ETF_MAP.get(asset) or ETF_MAP.get(parent) or [],
        "stats": stats or {}, "uncond": (clock["assets"].get(asset) or {}).get("uncond_ann") if asset else None,
        "market": (market.get("phases") or {}), "market_uncond": market.get("uncond_ann"),
        "tilt": tilt, "edge_now": edge_now,
        "playbook_now": playbook_weight(phase), "playbook_alt": playbook_weight(cur.get("alt_phase")),
        "playbook_all": {p: [(r["name"], r.get("weight")) for r in pb.get(p, [])] for p in PHASES},
        "playbook_label": clock.get("playbook_label"),
        "holding": hold, "holdings_asof": clock.get("holdings_asof"),
        "asset_stats": clock.get("asset_stats") or {},
    }


def summary(sector: str | None, industry: str | None, ticker: str, live: bool = True) -> Optional[dict]:
    """Compact, JSON-friendly cycle facts for the library cards (None when the Reloj is unavailable)."""
    cv = cycle_view(sector, industry, ticker, load(live))
    if not cv:
        return None
    pn = cv.get("playbook_now")
    return {
        "phase": cv["phase"], "asof": cv["asof"], "confidence": cv["confidence"], "strength": cv["strength"],
        "asset": cv["asset"], "tilt": None if cv["tilt"] is None else round(cv["tilt"], 2),
        "edge_now": None if cv["edge_now"] is None else round(cv["edge_now"], 2),
        "playbook_weight": pn["weight"] if pn else None,
        "source": cv["fetched"],
    }
