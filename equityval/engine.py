"""Orchestrator -- sector-aware triangulation.

1. Classify the company into a valuation profile.
2. Build every lens that profile calls for (forward multiples, DCF, sector models).
3. Triangulate them into a 12-month price target with guardrails, a Street cross-check
   and a confidence grade (triangulate.py).
4. Render the research note.
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
from .estimates import forward_numbers
from .forward_model import build_forward_model
from .lenses import (Lens, dcf_lens, ev_ebitda_forward, ev_sales_forward, from_method,
                      anchor_multiple, pb_book, pe_forward)
from .models import MethodResult
from .providers import get_company, get_provider
from .reference import lookup
from .schema import CompanyData
from .sectors import Profile, classify, get_spec
from .triangulate import triangulate


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
    street_weight: float = 0.30          # max weight of the Street consensus in the target (0 = off)


def _build_risks(data, profile, dcf, tr, fwd) -> list[str]:
    r = []
    cur = data.currency_symbol
    if fwd.cycle.is_cyclical and fwd.cycle.peak_ratio and fwd.cycle.peak_ratio > 2:
        r.append(f"Earnings are cyclically elevated: forward EPS is {fwd.cycle.peak_ratio:.1f}x the "
                 "through-cycle average. A normalisation of pricing, volumes or margins would reset "
                 "the earnings base the multiples are applied to.")
    if dcf and dcf.tv_pct_of_ev > 0.75:
        r.append(f"Terminal value carries {dcf.tv_pct_of_ev:.0%} of DCF enterprise value — "
                 "highly sensitive to perpetuity growth and the discount rate.")
    if profile in (Profile.BANK, Profile.INSURANCE):
        r.append("Valuation hinges on a normalised ROE assumption; credit losses, net-interest-"
                 "margin compression, or a capital raise would lower sustainable returns.")
        r.append("Regulatory capital requirements and rate-cycle sensitivity can move book-value "
                 "growth and payout capacity materially.")
    if profile == Profile.REIT:
        r.append("FFO/AFFO depend on occupancy, rent growth and cap-rate direction; rising rates "
                 "lift required yields and compress property values.")
    if profile == Profile.CYCLICAL:
        r.append("Through-cycle margin and multiple are estimates; a structurally lower commodity "
                 "price or cost inflation would reset the normalised earnings base.")
    if profile == Profile.UTILITY:
        r.append("Allowed returns and rate-case outcomes drive long-run value; a regulatory reset or "
                 "higher funding costs would compress the multiple.")
    de = data.latest.total_debt / data.market_cap if data.market_cap else 0
    if de > 0.6 and profile not in (Profile.BANK, Profile.INSURANCE):
        r.append(f"Elevated leverage (debt/equity {de:.1f}x at market) amplifies equity-value "
                 "sensitivity to the cost of capital.")
    if tr.street and tr.divergence is not None and abs(tr.divergence) > 0.35:
        r.append(f"Our model-only target is {tr.divergence:+.0%} versus the Street consensus "
                 f"({cur}{tr.street.mean:,.2f}); where the model is right the stock has an "
                 "information edge, where it is wrong the Street's inputs deserve more weight.")
    if tr.confidence == "Low":
        r.append("Low-confidence valuation: the lenses disagree or the inputs carry data-quality "
                 "flags. Treat the target as indicative.")
    r.append("Estimate risk: consensus forecasts can be revised sharply, and the forward-multiple lenses "
             "move one-for-one with the earnings they are applied to.")
    r.append("Multiple risk: target multiples are anchored on sector medians; a de-rating of the peer group "
             "lowers the target regardless of company performance.")
    r.append("Single third-party data source: restatements, non-recurring items or classification "
             "differences can shift the output.")
    return r


def value_company(ticker: str, provider: str = "auto", fmp_key: Optional[str] = None,
                  cfg: Optional[ValuationConfig] = None) -> dict:
    cfg = cfg or ValuationConfig()
    prov = get_provider(provider, fmp_key)
    data = get_company(ticker, provider, fmp_key, years=8)
    return value_data(data, prov, cfg)


def value_data(data: CompanyData, prov, cfg: ValuationConfig, peer_snaps: Optional[list] = None,
               render: bool = True) -> dict:
    if cfg.profile_override:
        profile = Profile(cfg.profile_override)
    else:
        profile = classify(data.sector, data.industry,
                           data.cagr("revenue"), data.latest.ebit_margin)
    spec = get_spec(profile)
    horizon = cfg.horizon or spec.horizon
    ref = lookup(data.sector, data.industry)
    weights = dict(spec.weights)

    # ---- peers (optional; reference multiples carry the load when absent) ------------
    if peer_snaps is None:
        peer_snaps = []
        if prov is not None:
            tickers = data.peers or prov.peer_list(data.ticker, cfg.max_peers)
            for t in tickers[: cfg.max_peers]:
                snap = prov.peer(t)
                if snap:
                    peer_snaps.append(snap)

    wacc = compute_wacc(data, cfg.risk_free, cfg.erp, cfg.country_premium,
                        beta_override=cfg.beta_override)
    ke = wacc.cost_of_equity
    discount = wacc.wacc if spec.discount == "wacc" else ke
    fwd = forward_numbers(data, ref)

    lenses: list[Lens] = []
    methods: dict[str, MethodResult] = {}
    scenarios = sens = diagnostics = reverse = base_drivers = dcf_base = None

    # ---- intrinsic: FCFF DCF with decaying growth and mean-reverting margins ----------
    if "dcf" in weights:
        try:
            scenarios = {}
            for sc in ("bear", "base", "bull"):
                dr = build_drivers(data, horizon, cfg.terminal_growth, sc, fwd=fwd, ref=ref)
                scenarios[sc] = run_dcf(data, dr, wacc.wacc, cfg.exit_multiple, cfg.mid_year)
            dcf_base = scenarios["base"]
            base_drivers = build_drivers(data, horizon, cfg.terminal_growth, "base", fwd=fwd, ref=ref)
            sens = sensitivity_grid(data, base_drivers, wacc.wacc)
            diagnostics = model_diagnostics(data, base_drivers, dcf_base, wacc.wacc)
            reverse = reverse_dcf(data, base_drivers, wacc.wacc)
            l = dcf_lens(scenarios, data)
            if l:
                lenses.append(l)
                methods["fcff_dcf"] = MethodResult("fcff_dcf", l.label, l.value, l.value / data.price - 1)
        except ValueError:
            scenarios = dcf_base = None            # WACC <= g: DCF not meaningful

    # ---- relative lenses -----------------------------------------------------------------
    if "pe_fwd" in weights:
        l = pe_forward(data, ref, fwd, peer_snaps)
        if l: lenses.append(l)
    if "ev_ebitda_fwd" in weights:
        l = ev_ebitda_forward(data, ref, fwd, peer_snaps)
        if l: lenses.append(l)
    if "ev_sales_fwd" in weights:
        l = ev_sales_forward(data, ref, fwd, peer_snaps)
        if l: lenses.append(l)
    if "pb_book" in weights:
        l = pb_book(data, ref, fwd, ke, peer_snaps)
        if l: lenses.append(l)

    # ---- sector models -------------------------------------------------------------------
    g_fin = max(cfg.terminal_growth, 0.03)
    sector_calls = {
        "residual_income": lambda: M.residual_income(data, ke, horizon, g_fin),
        "pb_roe": lambda: M.pb_roe(data, ke, g_fin, peer_snaps),
        "ddm": lambda: M.multistage_ddm(data, ke, min(horizon, 10), cfg.terminal_growth),
        "ffo_multiple": lambda: M.ffo_multiple(data, None, default_mult=anchor_multiple("pe", ref, [])[0]),
        "affo_yield": lambda: M.affo_yield(data, ke, cfg.terminal_growth),
        "normalized": lambda: M.normalized_cyclical(
            data, None, default_mult=anchor_multiple("ev_ebitda", ref, peer_snaps)[0] * 0.90),
    }
    for key, call in sector_calls.items():
        if key in weights:
            m = call()
            if m:
                methods[key] = m
                l = from_method(m)
                if l: lenses.append(l)

    # ---- coverage fallback: never leave a company with a single lens ----------------------
    if sum(1 for l in lenses if l.value and l.value > 0) < 2:
        for key, fn in (("ev_sales_fwd", lambda: ev_sales_forward(data, ref, fwd, peer_snaps)),
                        ("pb_book", lambda: pb_book(data, ref, fwd, ke, peer_snaps))):
            if key not in weights:
                l = fn()
                if l:
                    weights[key] = 0.5
                    lenses.append(l)

    comps = run_comps(data, peer_snaps) if peer_snaps else None
    if comps and not comps.blended_vps:
        comps = None

    # ---- triangulate -----------------------------------------------------------------------
    tr = triangulate(lenses, weights, data, ke, flags=fwd.flags,
                     street_weight_max=cfg.street_weight,
                     tv_share=dcf_base.tv_pct_of_ev if dcf_base else None)
    blend = {l.key: l.eff_weight for l in tr.lenses if l.eff_weight > 0}
    target, upside = tr.target, tr.upside

    fwd_model = None
    if dcf_base and base_drivers:
        try:
            fwd_model = build_forward_model(data, dcf_base, base_drivers, fwd)
        except Exception:
            fwd_model = None

    risks = _build_risks(data, profile, dcf_base, tr, fwd)

    html = "" if not render else report_mod.build_report(
        data=data, profile=profile, spec=spec, wacc=wacc, discount_rate=discount,
        methods=methods, dcf=dcf_base, scenarios=scenarios, sens=sens, comps=comps,
        base_drivers=base_drivers, diagnostics=diagnostics, reverse=reverse,
        target=target, upside=upside, blend=blend, risks=risks,
        tr=tr, fwd=fwd, ref=ref, fwd_model=fwd_model, peers=peer_snaps,
    )
    return {
        "data": data, "profile": profile, "spec": spec, "wacc": wacc,
        "methods": methods, "dcf": dcf_base, "scenarios": scenarios, "sens": sens,
        "comps": comps, "base_drivers": base_drivers, "diagnostics": diagnostics,
        "reverse": reverse, "target": target, "upside": upside, "blend": blend,
        "risks": risks, "html": html, "sws": None, "fwd_model": fwd_model,
        "tr": tr, "fwd": fwd, "ref": ref, "lenses": tr.lenses, "fair_value": tr.fair_value,
        "total_return": tr.total_return, "confidence": tr.confidence,
    }
