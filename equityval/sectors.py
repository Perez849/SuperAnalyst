"""Sector classification -> valuation profile.

Maps a company's sector/industry into one of a handful of *valuation profiles*,
each of which prescribes which models to run and how to weight them into the
blended target. This is the core of "don't DCF a bank".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Profile(Enum):
    STANDARD = "standard"                 # industrials, consumer, healthcare, most tech
    BANK = "bank"                         # deposit-takers, diversified financials
    INSURANCE = "insurance"
    REIT = "reit"
    UTILITY = "utility"
    CYCLICAL = "cyclical"                 # materials, energy, mining, commodities
    HIGH_GROWTH = "high_growth"           # fast-growing, thin/negative margins


@dataclass
class ProfileSpec:
    profile: Profile
    label: str
    # method_key -> blend weight (only methods listed here run + feed the target)
    weights: dict
    discount: str = "wacc"                # 'wacc' or 'ke'
    horizon: int = 5
    rationale: str = ""

    def methods(self):
        return list(self.weights.keys())


PROFILE_SPECS = {
    Profile.STANDARD: ProfileSpec(
        Profile.STANDARD, "Standard (forward multiples + DCF)",
        {"dcf": 0.35, "pe_fwd": 0.30, "ev_ebitda_fwd": 0.25, "ddm": 0.10}, "wacc", 10,
        "Priced like the sell-side prices it: a target multiple on forward earnings and EBITDA "
        "(peer-anchored, adjusted for growth and earnings durability), cross-checked against a "
        "10-year FCFF DCF whose growth fades and whose margins mean-revert."),
    Profile.BANK: ProfileSpec(
        Profile.BANK, "Bank / Diversified Financials (P/B-ROE + residual income)",
        {"pb_roe": 0.35, "residual_income": 0.30, "pe_fwd": 0.25, "ddm": 0.10}, "ke", 6,
        "Leverage is the business, not a financing choice, so cash-flow models do not apply. "
        "Value = book value + the present value of returns above the cost of equity, "
        "cross-checked against justified P/B and forward P/E."),
    Profile.INSURANCE: ProfileSpec(
        Profile.INSURANCE, "Insurance (P/B-ROE + residual income)",
        {"pb_roe": 0.30, "residual_income": 0.30, "pe_fwd": 0.30, "ddm": 0.10}, "ke", 6,
        "Valued off book value and sustainable ROE versus the cost of equity, with forward "
        "P/E as the market cross-check."),
    Profile.REIT: ProfileSpec(
        Profile.REIT, "REIT (P/FFO + AFFO yield)",
        {"ffo_multiple": 0.40, "affo_yield": 0.30, "ddm": 0.15, "ev_ebitda_fwd": 0.15}, "ke", 10,
        "Property cash flow is measured by FFO/AFFO, not free cash flow or GAAP earnings: "
        "price-to-FFO, a capitalised AFFO yield, and EV/EBITDA as a leverage-aware cross-check."),
    Profile.UTILITY: ProfileSpec(
        Profile.UTILITY, "Utility (P/E + dividends + DCF)",
        {"pe_fwd": 0.30, "ddm": 0.25, "dcf": 0.25, "ev_ebitda_fwd": 0.20}, "wacc", 10,
        "Regulated, low-growth, high-payout: forward P/E against regulated peers, a multi-stage "
        "dividend model, and a DCF with rate-base-style reinvestment."),
    Profile.CYCLICAL: ProfileSpec(
        Profile.CYCLICAL, "Cyclical / Commodities (mid-cycle multiples + DCF)",
        {"normalized": 0.30, "ev_ebitda_fwd": 0.25, "pe_fwd": 0.15, "dcf": 0.30}, "wacc", 10,
        "Spot margins mislead at both ends of the cycle: value on mid-cycle EBITDA and "
        "through-cycle multiples, with forward multiples (scaled for earnings durability) and a "
        "mean-reverting DCF as cross-checks."),
    Profile.HIGH_GROWTH: ProfileSpec(
        Profile.HIGH_GROWTH, "High-growth (EV/Sales + DCF)",
        {"ev_sales_fwd": 0.35, "dcf": 0.30, "pe_fwd": 0.20, "pb_book": 0.15}, "wacc", 10,
        "Thin or negative earnings: forward EV/Sales sized to growth and margin potential, a "
        "long-horizon DCF with margin convergence, and book value as the downside anchor."),
}


_BANK_KW = ("bank", "capital markets", "consumer finance", "financial services",
            "diversified financ", "mortgage", "credit services", "asset management",
            "brokerage")
_INS_KW = ("insurance", "reinsurance", "assurance")
_REIT_KW = ("reit", "real estate investment trust")
# Only *regulated* utilities belong here (rate-base, high payout). Independent /
# merchant power producers (IPPs) are NOT regulated utilities and are excluded.
_UTIL_KW = ("regulated electric", "gas distribution", "water utilit",
            "multi-utilities", "regulated gas", "electric utilit")
_IPP_KW = ("independent power", "merchant power", "power producer", "renewable")
_CYC_KW = ("oil", "gas", "energy", "mining", "metals", "materials", "chemical",
           "steel", "copper", "gold", "uranium", "coal", "aluminum", "commodit",
           "e&p", "exploration", "refining", "paper", "forest")


def classify(sector: str, industry: str,
             revenue_growth: float | None = None,
             ebit_margin: float | None = None,
             is_reit_flag: bool = False) -> Profile:
    s = (sector or "").lower()
    i = (industry or "").lower()
    blob = f"{s} {i}"

    if is_reit_flag or any(k in blob for k in _REIT_KW):
        return Profile.REIT
    if any(k in blob for k in _INS_KW):
        return Profile.INSURANCE
    if any(k in blob for k in _BANK_KW) or s == "financial services" or s == "financials":
        return Profile.BANK
    # Independent/merchant power producers trade on power prices & growth, not a
    # regulated dividend — treat as standard cash-flow businesses, not utilities.
    if any(k in blob for k in _IPP_KW):
        return Profile.STANDARD
    if any(k in blob for k in _UTIL_KW) or (s == "utilities" and "independent" not in i):
        return Profile.UTILITY
    if any(k in blob for k in _CYC_KW) or s in ("energy", "basic materials", "materials"):
        return Profile.CYCLICAL
    # high growth: fast top line and thin/negative margins
    if revenue_growth is not None and ebit_margin is not None:
        if revenue_growth > 0.22 and ebit_margin < 0.10:
            return Profile.HIGH_GROWTH
    return Profile.STANDARD


def get_spec(profile: Profile) -> ProfileSpec:
    return PROFILE_SPECS[profile]
