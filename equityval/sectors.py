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
        Profile.STANDARD, "Standard (2-Stage FCFE)",
        {"fcff_dcf": 0.55, "comps": 0.30, "ddm": 0.15}, "ke", 5,
        "Fair value from a 2-stage Free Cash Flow to Equity model: analyst levered-FCF "
        "estimates over 10 years plus a Gordon terminal, discounted at the cost of equity."),
    Profile.BANK: ProfileSpec(
        Profile.BANK, "Bank / Diversified Financials (Excess Returns)",
        {"residual_income": 0.50, "ddm": 0.30, "pb_roe": 0.20}, "ke", 6,
        "Leverage is the business, not a financing choice, so cash-flow models don't apply. "
        "Value = book value + present value of excess returns (ROE above the cost of equity)."),
    Profile.INSURANCE: ProfileSpec(
        Profile.INSURANCE, "Insurance (Excess Returns)",
        {"residual_income": 0.45, "pb_roe": 0.30, "ddm": 0.25}, "ke", 6,
        "Valued off book value and sustainable ROE versus the cost of equity via the "
        "Excess Returns model, the balance-sheet-appropriate approach for financials."),
    Profile.REIT: ProfileSpec(
        Profile.REIT, "REIT (AFFO 2-Stage)",
        {"ffo_multiple": 0.45, "affo_yield": 0.35, "ddm": 0.20}, "ke", 5,
        "Property cash flow is measured by AFFO, not free cash flow. A 2-stage AFFO model "
        "discounts adjusted funds from operations at the cost of equity (NAV fallback)."),
    Profile.UTILITY: ProfileSpec(
        Profile.UTILITY, "Utility (2-Stage FCFE)",
        {"ddm": 0.45, "fcff_dcf": 0.30, "comps": 0.25}, "ke", 7,
        "Regulated, low-growth, high-payout: valued on a 2-stage cash-flow-to-equity model "
        "off analyst estimates, or a dividend model where FCF estimates are unavailable."),
    Profile.CYCLICAL: ProfileSpec(
        Profile.CYCLICAL, "Cyclical / Commodities (2-Stage FCFE)",
        {"normalized": 0.45, "fcff_dcf": 0.30, "comps": 0.25}, "ke", 5,
        "Valued on a 2-stage Free Cash Flow to Equity model off analyst estimates, which "
        "already reflect through-cycle expectations for cash generation."),
    Profile.HIGH_GROWTH: ProfileSpec(
        Profile.HIGH_GROWTH, "High-growth (2-Stage FCFE)",
        {"fcff_dcf": 0.55, "comps": 0.45}, "ke", 8,
        "A 2-stage Free Cash Flow to Equity model captures the analyst growth ramp over a "
        "10-year explicit horizon before fading to the terminal rate."),
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
