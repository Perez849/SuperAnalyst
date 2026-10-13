"""Triangulation: lenses -> one defensible 12-month price target.

This is where the engine stops being a single-model calculator and starts behaving like
a research desk:

  1. Weight the lenses a profile calls for (renormalised over those that produced a value).
  2. Guardrails. A lens that lands wildly outside what the price and the other lenses
     allow is excluded (or winsorised if it is the only one) -- and the note says so.
  3. Roll fair value forward to a 12-month price target:  PT = FV x (1 + Ke) - dividends.
  4. Cross-check with the Street. When consensus exists, the target is lightly anchored
     to it (weight scales with analyst count, capped at `street_weight`). The model-only
     number and the divergence are always reported, never hidden.
  5. Final plausibility band on the published target, and a confidence grade.

Nothing is silent: every intervention is returned in `guardrails` and printed in the note.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from typing import Optional

from .lenses import Lens
from .schema import CompanyData

PLAUSIBLE_LENS = (0.20, 5.0)       # a single lens must be within 0.2x - 5x of the price
PLAUSIBLE_TARGET = (0.40, 2.5)     # the published 12m target must be within 0.4x - 2.5x


@dataclass
class StreetView:
    mean: float
    median: Optional[float]
    low: Optional[float]
    high: Optional[float]
    n: Optional[int]
    rec_mean: Optional[float]
    upside: float


@dataclass
class TargetResult:
    lenses: list[Lens]
    fair_value: float                  # blended intrinsic/relative fair value, today
    fair_low: float
    fair_high: float
    model_target: float                # 12m target from the model alone (no Street anchor)
    target: float                      # published 12m price target
    bear: float
    bull: float
    price: float
    ke: float
    dps: float
    upside: float                      # price appreciation to target
    total_return: float                # upside + dividend yield
    street: Optional[StreetView]
    street_weight: float
    divergence: Optional[float]        # model_target / street mean - 1
    confidence: str
    confidence_reasons: list[str] = field(default_factory=list)
    guardrails: list[str] = field(default_factory=list)
    rated: bool = True                 # False when the model cannot defend a number
    rating_note: str = ""


def _fin(x) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(x)


def build_street(data: CompanyData) -> Optional[StreetView]:
    e = data.estimates
    p = data.price
    if not (_fin(e.target_price_mean) and e.target_price_mean and e.target_price_mean > 0 and p):
        return None
    if not (0.3 * p <= e.target_price_mean <= 4.0 * p):          # corrupt feed
        return None
    return StreetView(
        mean=e.target_price_mean, median=e.target_price_median,
        low=e.target_price_low if _fin(e.target_price_low) and e.target_price_low else None,
        high=e.target_price_high if _fin(e.target_price_high) and e.target_price_high else None,
        n=e.num_analysts, rec_mean=e.recommendation_mean,
        upside=e.target_price_mean / p - 1)


def triangulate(lenses: list[Lens], weights: dict, data: CompanyData, ke: float,
                flags: Optional[list[str]] = None, street_weight_max: float = 0.30,
                tv_share: Optional[float] = None) -> TargetResult:
    price = data.price
    dps = max(data.dividend_per_share or 0.0, 0.0)
    guard: list[str] = []
    flags = flags or []

    for l in lenses:
        l.weight = float(weights.get(l.key, 0.0))
        l.status, l.status_note, l.eff_weight = "ok", "", 0.0
    live = [l for l in lenses if _fin(l.value) and l.value > 0 and l.weight > 0]
    for l in lenses:
        if l not in live:
            l.status, l.status_note = "excluded", "no usable value"

    # --- 2a. absolute plausibility vs the price ---------------------------------------
    lo_b, hi_b = PLAUSIBLE_LENS[0] * price, PLAUSIBLE_LENS[1] * price
    inside = [l for l in live if lo_b <= l.value <= hi_b]
    for l in list(live):
        if lo_b <= l.value <= hi_b:
            continue
        ratio = l.value / price if price else float("inf")
        if inside:
            l.status = "excluded"
            l.status_note = f"implausible: {ratio:.1f}x the current price"
            guard.append(f"{l.label} excluded ({ratio:.1f}x the current price is outside the "
                         f"{PLAUSIBLE_LENS[0]:.1f}x–{PLAUSIBLE_LENS[1]:.0f}x plausibility band).")
            live.remove(l)
        else:
            old = l.value
            l.value = min(max(l.value, lo_b), hi_b)
            l.low, l.high = min(l.low, l.value), min(max(l.high, l.value), hi_b)
            l.status = "winsorized"
            l.status_note = f"winsorised from {old:,.2f}"
            guard.append(f"{l.label} was the only lens and fell outside the plausibility band; "
                         "winsorised to the band edge.")

    # --- 2b. cross-lens outliers (need >= 3 to judge) -----------------------------------
    eff = {l.key: l.weight for l in live}
    if len(live) >= 3:
        med = statistics.median(l.value for l in live)
        for l in live:
            if l.value > 2.2 * med or l.value < med / 2.2:
                eff[l.key] = l.weight * 0.4
                l.status_note = f"down-weighted: {l.value/med:.1f}x the median of the other lenses"
                guard.append(f"{l.label} sits {l.value/med:.1f}x the lens median and was "
                             "down-weighted by 60%.")

    tot = sum(eff.values())
    if live and tot > 0:
        for l in live:
            l.eff_weight = eff[l.key] / tot
        fair = sum(l.value * l.eff_weight for l in live)
        fair_lo = sum(min(l.low, l.value) * l.eff_weight for l in live)
        fair_hi = sum(max(l.high, l.value) * l.eff_weight for l in live)
    else:                       # nothing valued the company: say so, anchor on price
        fair = fair_lo = fair_hi = price
        guard.append("No lens produced a usable value; the target is set to the current price.")

    # --- 3. roll forward to a 12m target ----------------------------------------------
    roll = 1.0 + max(ke, 0.0)
    model_t = fair * roll - dps
    model_lo = fair_lo * roll - dps
    model_hi = fair_hi * roll - dps

    # --- 4. Street anchor ---------------------------------------------------------------
    street = build_street(data)
    w_s = 0.0
    divergence = None
    target, bear, bull = model_t, model_lo, model_hi
    if street:
        n = street.n
        if n is None:
            w_s = street_weight_max * 0.5
        elif n >= 3:
            w_s = street_weight_max * min(1.0, n / 12.0)
        divergence = model_t / street.mean - 1 if street.mean else None
        if w_s > 0:
            target = (1 - w_s) * model_t + w_s * street.mean
            s_lo = street.low if street.low else street.mean * 0.8
            s_hi = street.high if street.high else street.mean * 1.2
            bear = (1 - w_s) * model_lo + w_s * s_lo
            bull = (1 - w_s) * model_hi + w_s * s_hi
            guard.append(f"Target anchored {w_s:.0%} to the Street consensus "
                         f"({data.currency_symbol}{street.mean:,.2f}"
                         + (f", {n} analysts" if n else "") + "); model-only target "
                         f"{data.currency_symbol}{model_t:,.2f}.")

    # --- 5. final plausibility band -------------------------------------------------------
    t_lo, t_hi = PLAUSIBLE_TARGET[0] * price, PLAUSIBLE_TARGET[1] * price
    clamped = False
    if target > t_hi or target < t_lo:
        clamped = True
        guard.append(f"Target {target:,.2f} fell outside {PLAUSIBLE_TARGET[0]:.1f}x–"
                     f"{PLAUSIBLE_TARGET[1]:.1f}x the price and was limited to the band edge.")
        target = min(max(target, t_lo), t_hi)
    bear = min(max(bear, t_lo * 0.8), target)
    bull = max(min(bull, t_hi * 1.2), target)

    upside = target / price - 1 if price else 0.0
    total_return = upside + (dps / price if price else 0.0)

    # --- 6. confidence ---------------------------------------------------------------------
    pts, why = 0.0, []
    n_used = len(live)
    if n_used >= 3:
        pts += 1; why.append(f"{n_used} independent lenses agree on a valuation")
    elif n_used == 2:
        why.append("only two lenses produced a value")
    else:
        pts -= 1; why.append("fewer than two usable lenses")
    vals = [l.value for l in live]
    if len(vals) >= 2:
        cv = statistics.pstdev(vals) / statistics.mean(vals) if statistics.mean(vals) else 0.0
        if cv < 0.25:
            pts += 1; why.append(f"lens dispersion is tight (CV {cv:.0%})")
        elif cv > 0.60:
            pts -= 1; why.append(f"lens dispersion is wide (CV {cv:.0%})")
        else:
            why.append(f"lens dispersion is moderate (CV {cv:.0%})")
    if street and divergence is not None:
        if abs(divergence) < 0.25:
            pts += 1; why.append("model target is within 25% of the Street")
        elif abs(divergence) > 0.60:
            pts -= 1; why.append(f"model target is {divergence:+.0%} away from the Street")
    if tv_share is not None and tv_share > 0.85:
        pts -= 0.5; why.append(f"terminal value is {tv_share:.0%} of DCF enterprise value")
    if flags:
        pts -= min(1.0, 0.5 * len(flags))
        why.append(f"{len(flags)} data-quality / earnings-quality flag(s)")
    if any(g for g in guard if "excluded" in g or "limited" in g or "winsorised" in g):
        pts -= 0.5; why.append("a guardrail had to intervene")
    conf = "High" if pts >= 1.5 else ("Medium" if pts >= 0 else "Low")

    # A research desk does not put a rating on a number it cannot defend: fewer than two
    # independent lenses, or a result that only exists because a guardrail forced it into
    # the plausible band, is published as indicative (NOT RATED), never as a call.
    rated, rating_note = True, ""
    if n_used < 2:
        rated, rating_note = False, "fewer than two independent lenses could value the company"
    elif clamped or any(l.status == "winsorized" for l in lenses):
        rated, rating_note = False, "the result only exists inside the guardrail band"
    if not rated:
        conf = "Low"

    return TargetResult(
        lenses=lenses, fair_value=fair, fair_low=fair_lo, fair_high=fair_hi,
        model_target=model_t, target=target, bear=bear, bull=bull, price=price, ke=ke, dps=dps,
        upside=upside, total_return=total_return, street=street, street_weight=w_s,
        divergence=divergence, confidence=conf, confidence_reasons=why, guardrails=guard,
        rated=rated, rating_note=rating_note)
