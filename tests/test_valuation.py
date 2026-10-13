"""Regression tests for the triangulated valuation engine.

The snapshots in tests/fixtures are rebuilt from real runs (statements, price, consensus EPS /
revenue, Street mean target). Three of them (MU, SNDK, UEC) used to publish absurd targets:
MU $34,784 on a $949 stock, SNDK $389,748 on $1,727, UEC "nan". These tests pin the fix.

Run:  python -m pytest tests -q
"""
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from equityval.assumptions import build_drivers
from equityval.demo_data import demo_company, demo_peers
from equityval.engine import ValuationConfig, value_data
from equityval.estimates import forward_numbers
from equityval.lenses import Lens
from equityval.offline import load_snapshot
from equityval.providers import _f
from equityval.reference import lookup
from equityval.triangulate import PLAUSIBLE_TARGET, triangulate

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
STREET = {"MU": 1486.0, "SNDK": 1975.95, "NVDA": 301.62, "CEG": 357.81, "GFI": 54.28}
TICKERS = ["MU", "SNDK", "NVDA", "CEG", "GFI", "UEC"]


@pytest.fixture(scope="module")
def results():
    out = {}
    for t in TICKERS:
        data, prov = load_snapshot(os.path.join(FIX, f"{t}.json"))
        out[t] = value_data(data, prov, ValuationConfig(), render=False)
    return out


@pytest.mark.parametrize("t", TICKERS)
def test_target_is_finite_and_plausible(results, t):
    r = results[t]
    tr, price = r["tr"], r["data"].price
    assert math.isfinite(tr.target) and math.isfinite(tr.fair_value)
    assert PLAUSIBLE_TARGET[0] * price <= tr.target <= PLAUSIBLE_TARGET[1] * price
    assert tr.bear <= tr.target <= tr.bull
    for l in tr.lenses:
        assert math.isfinite(l.value) and math.isfinite(l.low) and math.isfinite(l.high)
    used = [l for l in tr.lenses if l.eff_weight > 0]
    assert used and abs(sum(l.eff_weight for l in used) - 1.0) < 1e-9


@pytest.mark.parametrize("t", sorted(STREET))
def test_target_is_in_the_street_ballpark(results, t):
    """Not equal to the Street (that would be pointless) but the same order of magnitude."""
    tr = results[t]["tr"]
    assert 0.55 <= tr.target / STREET[t] <= 1.45, (t, tr.target, STREET[t])


def test_mu_and_sndk_regressions(results):
    assert results["MU"]["tr"].target < 3 * results["MU"]["data"].price          # was 36.7x
    assert results["SNDK"]["tr"].target < 3 * results["SNDK"]["data"].price      # was 225x


def test_uec_is_not_rated_instead_of_nan(results):
    tr = results["UEC"]["tr"]
    assert math.isfinite(tr.target)
    assert not tr.rated and tr.confidence == "Low"


def test_peak_earnings_cut_the_multiple(results):
    assert results["MU"]["fwd"].cycle.durability < 0.7          # memory cycle at record EPS
    assert results["NVDA"]["fwd"].cycle.durability == 1.0       # monotonic ramp is not a cycle


def test_street_anchor_is_bounded_and_disclosed(results):
    tr = results["NVDA"]["tr"]
    assert 0 < tr.street_weight <= 0.30
    assert any("Street" in g for g in tr.guardrails)
    cfg = ValuationConfig(street_weight=0.0)
    data, prov = load_snapshot(os.path.join(FIX, "NVDA.json"))
    pure = value_data(data, prov, cfg, render=False)["tr"]
    assert pure.street_weight == 0 and abs(pure.target - pure.model_target) < 1e-6


@pytest.mark.parametrize("profile", [None, "bank", "insurance", "reit", "utility", "cyclical", "high_growth"])
def test_every_profile_runs(profile):
    r = value_data(demo_company(), None, ValuationConfig(profile_override=profile),
                   peer_snaps=demo_peers(), render=False)
    assert math.isfinite(r["tr"].target) and r["tr"].target > 0
    assert r["tr"].lenses


def test_drivers_decay_and_stay_bounded(results):
    d = results["MU"]["data"]
    ref = lookup(d.sector, d.industry)
    dr = build_drivers(d, 10, 0.025, "base", fwd=forward_numbers(d, ref), ref=ref)
    tail = dr.revenue_growth[2:]                       # after the two consensus years
    assert all(tail[i] >= tail[i + 1] - 1e-12 for i in range(len(tail) - 1))   # monotone decay
    assert max(tail) <= 0.22 and abs(tail[-1] - dr.terminal_growth) < 1e-9
    assert max(dr.ebit_margin) <= dr.anchors["margin_cap"] + 1e-9


def test_growth_fades_gradually_instead_of_falling_off_a_cliff(results):
    """After the consensus window growth fades smoothly: in the first half of the fade no single year
    loses more than 30% of its excess over the terminal rate, and mid-horizon growth is still
    visibly above trend (the old geometric decay lost ~30% a year and was at trend by year 6)."""
    for t in ("MU", "NVDA", "SNDK", "CEG", "GFI", "UEC"):
        d = results[t]["data"]
        ref = lookup(d.sector, d.industry)
        dr = build_drivers(d, 10, 0.025, "base", fwd=forward_numbers(d, ref), ref=ref)
        g, tg = dr.revenue_growth, dr.terminal_growth
        tail = g[2:]
        first_half = tail[: len(tail) // 2]
        steps = [(first_half[i] - tg) / (first_half[i - 1] - tg) for i in range(1, len(first_half))]
        assert all(x >= 0.7 for x in steps), (t, [round(x, 3) for x in g])
        assert g[5] - tg >= 0.4 * (g[2] - tg), (t, [round(x, 3) for x in g])


def _lens(key, value, weight=0.3):
    return Lens(key, key, "relative", value, value * 0.8, value * 1.2, weight=weight)


def test_guardrail_excludes_an_absurd_lens():
    data = demo_company()
    lenses = [_lens("a", data.price * 1.1), _lens("b", data.price * 1.2), _lens("c", data.price * 150)]
    tr = triangulate(lenses, {"a": .3, "b": .3, "c": .4}, data, ke=0.09, street_weight_max=0)
    assert lenses[2].status == "excluded" and lenses[2].eff_weight == 0
    assert tr.target < 2 * data.price


def test_single_lens_is_not_rated():
    data = demo_company()
    tr = triangulate([_lens("a", data.price * 1.1)], {"a": 1.0}, data, ke=0.09, street_weight_max=0)
    assert not tr.rated


def test_nan_cells_do_not_poison_the_valuation():
    assert _f(float("nan")) == 0.0 and _f(None, 5) == 5 and _f(float("inf")) == 0.0 and _f("7") == 7.0


def test_report_renders_without_nan(results):
    for t in ("MU", "UEC"):
        data, prov = load_snapshot(os.path.join(FIX, f"{t}.json"))
        html = value_data(data, prov, ValuationConfig())["html"]
        assert "<svg class=\"dial\"" in html and "Reloj de inversión" in html
        assert "$nan" not in html and "+nan" not in html and "nan%" not in html
