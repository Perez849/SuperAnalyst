"""Orchestrator — sector-aware.

Classifies the company into a valuation profile, runs only the models that are
appropriate for that profile, and blends them into the target using the
profile's weights (renormalised over whatever actually produced a value).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from . import models as M
from . import report as report_mod
from .assumptions import build_drivers
from .comps import run_comps
from .costofcapital import compute_wacc
from .dcf import run_dcf, sensitivity_grid, model_diagnostics, reverse_dcf
from .models import MethodResult
from .providers import get_company, get_provider
from .schema import CompanyData
from .sectors import Profile, classify, get_spec


@dataclass
class ValuationConfig:
    horizon: Optional[int] = None
    terminal_growth: float = 0.025
    risk_free: float = 0.043
    erp: float = 0.046
    country_premium: float = 0.0
    exit_multiple: Optional[float] = None
    beta_override: Optional[float] = None
    mid_year: bool = True
    max_peers: int = 8
    profile_override: Optional[str] = None


def _wrap_dcf(scenarios) -> MethodResult:
    base = scenarios["base"]
    return MethodResult("fcff_dcf", "Discounted cash flow (FCFF)",
                        base.value_per_share, base.upside)


def _wrap_comps(comps) -> Optional[MethodResult]:
    if comps and comps.blended_vps:
        return MethodResult("comps", "Trading comparables", comps.blended_vps,
                            comps.upside or 0.0)
    return None


def _build_risks(data, profile, dcf, wacc, methods) -> list[str]:
    r = []
    if dcf and dcf.tv_pct_of_ev > 0.75:
        r.append(f"Terminal value carries {dcf.tv_pct_of_ev:.0%} of enterprise value \u2014 highly "
                 "sensitive to perpetuity growth and WACC.")
    if profile in (Profile.BANK, Profile.INSURANCE):
        r.append("Valuation hinges on a normalised ROE assumption; credit losses, net-interest-"
                 "margin compression, or a capital raise would lower sustainable returns.")
        r.append("Regulatory capital requirements and rate-cycle sensitivity can move book-value "
                 "growth and payout capacity materially.")
    if profile == Profile.REIT:
        r.append("FFO/AFFO depend on occupancy, rent growth and cap-rate direction; rising rates "
                 "lift required yields and compress property values.")
    if profile == Profile.CYCLICAL:
        r.append("Through-cycle margin is an estimate; a structurally lower commodity price or "
                 "cost inflation would reset the normalised earnings base.")
    de = data.latest.total_debt / data.market_cap if data.market_cap else 0
    if de > 0.6 and profile not in (Profile.BANK, Profile.INSURANCE):
        r.append(f"Elevated leverage (debt/equity {de:.1f}x at market) amplifies equity-value "
                 "sensitivity to the cost of capital.")
    r.append("Single third-party data source: restatements, non-recurring items or classification "
             "differences can shift the output.")
    return r


def value_company(ticker: str, provider: str = "auto", fmp_key: Optional[str] = None,
                  cfg: Optional[ValuationConfig] = None) -> dict:
    cfg = cfg or ValuationConfig()
    prov = get_provider(provider, fmp_key)
    data = get_company(ticker, provider, fmp_key, years=8)
    return value_data(data, prov, cfg)


def value_data(data: CompanyData, prov, cfg: ValuationConfig) -> dict:
    if cfg.profile_override:
        profile = Profile(cfg.profile_override)
    else:
        profile = classify(data.sector, data.industry,
                           data.cagr("revenue"), data.latest.ebit_margin)
    spec = get_spec(profile)
    horizon = cfg.horizon or spec.horizon

    peer_tickers = data.peers or (prov.peer_list(data.ticker, cfg.max_peers) if prov else [])
    peer_snaps = []
    for t in peer_tickers[: cfg.max_peers]:
        snap = prov.peer(t) if prov else None
        if snap:
            peer_snaps.append(snap)

    wacc = compute_wacc(data, cfg.risk_free, cfg.erp, cfg.country_premium,
                        beta_override=cfg.beta_override)
    ke = wacc.cost_of_equity
    discount = wacc.wacc if spec.discount == "wacc" else ke

    methods: dict[str, MethodResult] = {}
    dcf_base = scenarios = sens = comps = None
    base_drivers = diagnostics = reverse = None
    wants = spec.methods()

    if "fcff_dcf" in wants:
        scenarios = {}
        for sc in ("bear", "base", "bull"):
            dr = build_drivers(data, horizon, cfg.terminal_growth, sc)
            scenarios[sc] = run_dcf(data, dr, wacc.wacc, cfg.exit_multiple, cfg.mid_year)
        dcf_base = scenarios["base"]
        base_drivers = build_drivers(data, horizon, cfg.terminal_growth, "base")
        sens = sensitivity_grid(data, base_drivers, wacc.wacc)
        diagnostics = model_diagnostics(data, base_drivers, dcf_base, wacc.wacc)
        reverse = reverse_dcf(data, base_drivers, wacc.wacc)
        methods["fcff_dcf"] = _wrap_dcf(scenarios)

    if "comps" in wants and peer_snaps:
        comps = run_comps(data, peer_snaps)
        w = _wrap_comps(comps)
        if w:
            methods["comps"] = w

    if "residual_income" in wants:
        m = M.residual_income(data, ke, horizon, max(cfg.terminal_growth, 0.03))
        if m: methods["residual_income"] = m
    if "pb_roe" in wants:
        m = M.pb_roe(data, ke, max(cfg.terminal_growth, 0.03), peer_snaps)
        if m: methods["pb_roe"] = m
    if "ddm" in wants:
        m = M.multistage_ddm(data, ke, horizon, cfg.terminal_growth)
        if m: methods["ddm"] = m
    if "ffo_multiple" in wants:
        m = M.ffo_multiple(data, peer_snaps)
        if m: methods["ffo_multiple"] = m
    if "affo_yield" in wants:
        m = M.affo_yield(data, ke, cfg.terminal_growth)
        if m: methods["affo_yield"] = m
    if "normalized" in wants:
        m = M.normalized_cyclical(data, peer_snaps)
        if m: methods["normalized"] = m

    avail = {k: spec.weights[k] for k in methods if k in spec.weights
             and methods[k].value_per_share and methods[k].value_per_share > 0}
    if avail:
        tot = sum(avail.values())
        target = sum(methods[k].value_per_share * (w / tot) for k, w in avail.items())
        blend = {k: w / tot for k, w in avail.items()}
    else:
        target = data.price
        blend = {}
    upside = target / data.price - 1 if data.price else 0.0

    risks = _build_risks(data, profile, dcf_base, wacc, methods)

    html = report_mod.build_report(
        data=data, profile=profile, spec=spec, wacc=wacc, discount_rate=discount,
        methods=methods, dcf=dcf_base, scenarios=scenarios, sens=sens, comps=comps,
        base_drivers=base_drivers, diagnostics=diagnostics, reverse=reverse,
        target=target, upside=upside, blend=blend, risks=risks,
    )
    return {
        "data": data, "profile": profile, "spec": spec, "wacc": wacc,
        "methods": methods, "dcf": dcf_base, "scenarios": scenarios, "sens": sens,
        "comps": comps, "base_drivers": base_drivers, "diagnostics": diagnostics,
        "reverse": reverse, "target": target, "upside": upside, "blend": blend,
        "risks": risks, "html": html,
    }
