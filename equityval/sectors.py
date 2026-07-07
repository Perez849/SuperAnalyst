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
        Profile.STANDARD, "Standard (FCFF-DCF led)",
        {"fcff_dcf": 0.55, "comps": 0.30, "ddm": 0.15}, "wacc", 5,
        "Cash-generative operating business: unlevered DCF is the anchor, "
        "trading comps and a dividend cross-check corroborate."),
    Profile.BANK: ProfileSpec(
        Profile.BANK, "Bank / Diversified Financials (residual income led)",
        {"residual_income": 0.50, "ddm": 0.30, "pb_roe": 0.20}, "ke", 6,
        "Leverage is the business, not a financing choice, so FCFF is meaningless. "
        "Value = book value + PV of excess returns (ROE above cost of equity)."),
    Profile.INSURANCE: ProfileSpec(
        Profile.INSURANCE, "Insurance (excess-return / P-B–ROE led)",
        {"residual_income": 0.45, "pb_roe": 0.30, "ddm": 0.25}, "ke", 6,
        "Valued off book value and sustainable ROE versus cost of equity; "
        "FCFF does not apply to a balance-sheet-driven model."),
    Profile.REIT: ProfileSpec(
        Profile.REIT, "REIT (P/FFO & AFFO-yield led)",
        {"ffo_multiple": 0.45, "affo_yield": 0.35, "ddm": 0.20}, "ke", 5,
        "Property cash flow is measured by FFO/AFFO, not FCFF; heavy non-cash "
        "depreciation makes GAAP earnings and DCF misleading."),
    Profile.UTILITY: ProfileSpec(
        Profile.UTILITY, "Utility (dividend-discount led)",
        {"ddm": 0.45, "fcff_dcf": 0.30, "comps": 0.25}, "wacc", 7,
        "Regulated, low-growth, high-payout: a multi-stage dividend model leads, "
        "with a slow-growth DCF and comps as support."),
    Profile.CYCLICAL: ProfileSpec(
        Profile.CYCLICAL, "Cyclical / Commodities (mid-cycle normalized)",
        {"normalized": 0.45, "fcff_dcf": 0.30, "comps": 0.25}, "wacc", 5,
        "Spot margins mislead at cycle extremes: value off mid-cycle normalized "
        "margins and through-cycle multiples."),
    Profile.HIGH_GROWTH: ProfileSpec(
        Profile.HIGH_GROWTH, "High-growth (long-horizon DCF & EV/Sales)",
        {"fcff_dcf": 0.55, "comps": 0.45}, "wacc", 8,
        "Earnings immature: a longer explicit horizon lets margins mature, with "
        "EV/Sales comps anchoring the near-term multiple."),
}


_BANK_KW = ("bank", "capital markets", "consumer finance", "financial services",
            "diversified financ", "mortgage", "credit services", "asset management",
            "brokerage")
_INS_KW = ("insurance", "reinsurance", "assurance")
_REIT_KW = ("reit", "real estate investment trust")
_UTIL_KW = ("utilit", "electric", "gas distribution", "water", "power",
            "regulated", "multi-utilities")
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
    if any(k in blob for k in _UTIL_KW) or s == "utilities":
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
