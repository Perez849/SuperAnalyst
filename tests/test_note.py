"""The research note: Reloj de inversión linkage, financial analysis, charts and the library page."""
import json
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from equityval import analysis, charts, clockdata
from equityval.engine import ValuationConfig, value_data
from equityval.offline import load_snapshot

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = os.path.join(ROOT, "tests", "fixtures")


@pytest.fixture(scope="module")
def mu():
    data, prov = load_snapshot(os.path.join(FIX, "MU.json"))
    return data, value_data(data, prov, ValuationConfig(reloj_live=False))


# ------------------------------------------------------------------ Reloj de inversión
def test_snapshot_is_the_reloj_data():
    clock = clockdata.load(live=False)
    cur = clock["current"]
    assert clock["fetched"] == "snapshot" and cur["phase"] in clockdata.PHASES
    assert abs(sum(cur["probs"].values()) - 1.0) < 0.02
    assert clock["history"] and "Semiconductores" in clock["assets"]


@pytest.mark.parametrize("sector,industry,asset", [
    ("Technology", "Semiconductors", "Semiconductores"),
    ("Technology", "Software - Application", "Tecnología"),
    ("Basic Materials", "Gold", "Metales preciosos (mineras)"),
    ("Energy", "Uranium", "Energía"),
    ("Healthcare", "Biotechnology", "Salud"),
    ("Something else", "", None),
])
def test_company_maps_to_a_reloj_asset(sector, industry, asset):
    assert clockdata.asset_for(sector, industry)[0] == asset


def test_tilt_is_the_probability_weighted_excess_return():
    clock = clockdata.load(live=False)
    cv = clockdata.cycle_view("Technology", "Semiconductors", "MU", clock)
    stats = clock["assets"]["Semiconductores"]["phases"]
    expected = sum(clock["current"]["probs"][p] * stats[p]["rel_shrunk"] for p in clockdata.PHASES)
    assert cv["tilt"] == pytest.approx(expected)
    assert cv["edge_now"] == stats[cv["phase"]]["rel_shrunk"]
    assert cv["holding"]["hits"], "MU is a SOXX/SMH holding in the Reloj's data"


def test_unknown_sector_has_no_tilt_but_still_reads_the_cycle():
    cv = clockdata.cycle_view("Something else", "", "ZZZZ", clockdata.load(live=False))
    assert cv["tilt"] is None and cv["asset"] is None and cv["phase"] in clockdata.PHASES


def test_summary_is_json_serialisable():
    s = clockdata.summary("Technology", "Semiconductors", "MU", live=False)
    assert json.loads(json.dumps(s))["asset"] == "Semiconductores"
    assert set(s) >= {"phase", "tilt", "edge_now", "playbook_weight", "asset"}


def test_report_uses_the_reloj_and_not_the_merrill_sector_map(mu):
    html = mu[1]["html"]
    for needle in ("Reloj de inversión", "Growth × inflation plane",
                   "Phase probabilities", "playbook", "Semiconductors"):
        assert needle.lower() in html.lower(), needle
    assert "Merrill" not in html and "classic Investment Clock" not in html


# ------------------------------------------------------------------ tear sheet
def test_note_has_the_summary_blocks_and_no_nan(mu):
    html = mu[1]["html"]
    for marker in ('id="top"', 'id="verdict"', 'id="financials"', 'id="dcf"', 'id="cycle"', 'id="risks"',
                   "From price to target", "Scenarios", "Factor scorecard", "Piotroski", "Altman", "Valuation vs the sector"):
        assert marker in html, marker
    assert html.count("<svg") >= 20
    import re
    text = re.sub(r"<(script|style)\b.*?</\1>", "", html, flags=re.S)
    assert not re.search(r"\bnan\b|\bNone\b|\binf\b|\$-\d", text), re.search(r"\bnan\b|\bNone\b|\binf\b|\$-\d", text)
    assert "@page" in html and "print=1" in html


def test_not_rated_company_still_renders_full_note():
    data, prov = load_snapshot(os.path.join(FIX, "UEC.json"))
    r = value_data(data, prov, ValuationConfig(reloj_live=False))
    assert not r["tr"].rated and "NOT RATED" in r["html"] and "id=\"financials\"" in r["html"]


def test_all_reports_survive_without_reloj_data(monkeypatch):
    monkeypatch.setattr(clockdata, "SNAPSHOT", clockdata.SNAPSHOT.with_name("missing.json"))
    monkeypatch.setattr(clockdata, "_cache", {})
    data, prov = load_snapshot(os.path.join(FIX, "NVDA.json"))
    html = value_data(data, prov, ValuationConfig(reloj_live=False))["html"]
    assert "id=\"cycle\"" not in html and "id=\"dcf\"" in html


# ------------------------------------------------------------------ analysis
def test_financial_tables_mark_forecast_columns(mu):
    data, r = mu
    ft = analysis.financial_tables(data, r["dcf"], r["fwd_model"] if "fwd_model" in r else None, r["fwd"])
    assert ft.n_hist >= 3 and len(ft.cols) > ft.n_hist
    assert ft.cols[ft.n_hist].endswith("E") and ft.cols[0].endswith("A")


def test_quality_scores_are_bounded(mu):
    data = mu[0]
    pio = analysis.piotroski(data)
    assert 0 <= pio["score"] <= pio["available"] <= 9
    z = analysis.altman_z(data)
    assert z is None or (math.isfinite(z["z"]) and z["zone"] in ("safe", "grey", "distress"))
    d = analysis.dupont(data)
    assert d is None or d["roe"] == pytest.approx(d["net_margin"] * d["turnover"] * d["multiplier"])


def test_lin_scales_and_clamps():
    assert analysis.lin(5, 0, 10) == 50 and analysis.lin(-5, 0, 10) == 0 and analysis.lin(99, 0, 10) == 100
    assert analysis.lin(None, 0, 10) is None


# ------------------------------------------------------------------ charts
def test_price_chart_needs_history_and_draws_with_it():
    assert charts.price_chart([("2024-01-01", 10.0)] * 5, 10, 12, 9, 14) == ""
    hist = [(f"2021-{1 + i % 12:02d}-{1 + i % 28:02d}", 100 + i * 0.5 + 8 * math.sin(i / 6)) for i in range(120)]
    svg = charts.price_chart(hist, 160, 190, 150, 220)
    assert svg.startswith("<svg") and "polyline" in svg and "nan" not in svg


def test_phase_plane_places_the_current_point():
    clock = clockdata.load(live=False)
    cur = clock["current"]
    trail = [(h["g"], h["i"], h["p"], h["d"]) for h in clock["history"][-12:]]
    svg = charts.phase_plane(trail, {"phase": cur["phase"], "growth": cur["growth"], "inflation": cur["inflation"],
                                     "sigma_g": cur["sigma_g"], "sigma_i": cur["sigma_i"]}, cur["probs"], "en")
    assert svg.count("<circle") >= 12 and "STAGFLATION" in svg


def test_radar_needs_three_axes():
    assert charts.radar([{"axis": "a", "score": 50}, {"axis": "b", "score": 60}]) == ""
    axes = [{"axis": c, "score": s} for c, s in zip("abcde", (80, 40, 60, 90, 10))]
    assert "<polygon" in charts.radar(axes)


# ------------------------------------------------------------------ library
def test_library_cards_show_the_reloj_cycle_tilt(tmp_path):
    import subprocess
    docs = tmp_path / "docs"
    (docs / "reports").mkdir(parents=True)
    meta = {"ticker": "MU", "name": "Micron", "html": "MU.html", "rating": "OVERWEIGHT", "rated": True, "target": 1264.8,
            "price": 948.8, "upside": 0.33, "total_return": 0.33, "confidence": "Medium", "currency": "$", "date": "2026-07-09",
            "cycle": clockdata.summary("Technology", "Semiconductors", "MU", live=False)}
    (docs / "reports" / "MU.json").write_text(json.dumps(meta))
    env = dict(os.environ, EQUITYVAL_OFFLINE="1")
    subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "build_index.py"), "--docs", str(docs)], check=True, env=env)
    html = (docs / "index.html").read_text(encoding="utf-8")
    assert "Sesgo del ciclo" in html and "pp/año" in html and "El Reloj de inversión ahora" in html
    assert "Merrill" not in html and 'data-tilt="head"' in html
