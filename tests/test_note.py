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


# ------------------------------------------------------------------ the paged note
def _visible_text(html: str) -> str:
    import re
    return re.sub(r"<(script|style)\b.*?</\1>", "", html, flags=re.S)


def test_note_is_a_fifteen_page_document_with_exhibits_and_no_leaks(mu):
    import re
    html = mu[1]["html"]
    assert len(re.findall(r'<section class="pg', html)) == 15
    for i in range(1, 16):
        assert f'id="p{i}"' in html, i
    for marker in ("Exhibit 1", "Key takeaways", "Factor scorecard", "Piotroski", "Altman", "Summary financials", "Income statement",
                   "Stress tests", "Methodology, definitions and disclosures"):
        assert marker in html, marker
    assert html.count("<svg") >= 25
    text = _visible_text(html)
    assert not re.search(r"\[\[|\bnan\b|\bNone of\b(?!.*single)|\binf\b|\$-\d", text.replace("None of the single", "")), re.search(r"\[\[|\bnan\b|\$-\d", text)
    assert "@page" in html and "print=1" in html


def test_note_has_real_prose(mu):
    import re
    html = _visible_text(mu[1]["html"])
    paras = re.findall(r"<p[^>]*>(.*?)</p>", html, flags=re.S)
    words = sum(len(re.sub(r"<[^>]+>", "", p).split()) for p in paras)
    assert words > 5500, words          # the written analysis, not just charts and tables


def test_exhibit_references_resolve_to_real_numbers(mu):
    import re
    html = mu[1]["html"]
    nums = set(re.findall(r'class="ex-n">Exhibit (\d+)<', html))
    for ref in re.findall(r'class="xr" data-ex="[a-z0-9_]+">Exhibit (\d+)<', html):
        assert ref in nums


def test_not_rated_company_still_renders_full_note():
    data, prov = load_snapshot(os.path.join(FIX, "UEC.json"))
    r = value_data(data, prov, ValuationConfig(reloj_live=False))
    assert not r["tr"].rated and "NOT RATED" in r["html"] and 'id="p6"' in r["html"] and "[[" not in r["html"]


def test_all_reports_survive_without_reloj_data(monkeypatch):
    monkeypatch.setattr(clockdata, "SNAPSHOT", clockdata.SNAPSHOT.with_name("missing.json"))
    monkeypatch.setattr(clockdata, "_cache", {})
    data, prov = load_snapshot(os.path.join(FIX, "NVDA.json"))
    html = value_data(data, prov, ValuationConfig(reloj_live=False))["html"]
    assert 'id="p11"' not in html and 'id="p9"' in html and "[[" not in html


@pytest.mark.parametrize("profile", ["bank", "reit", "utility", "insurance", "high_growth", "cyclical"])
def test_every_valuation_profile_renders(profile):
    data, prov = load_snapshot(os.path.join(FIX, "CEG.json"))
    r = value_data(data, prov, ValuationConfig(reloj_live=False, profile_override=profile))
    html = r["html"]
    assert 'id="p1"' in html and 'id="p15"' in html and "[[" not in html
    if r["dcf"] is None:
        assert 'id="p9"' not in html            # no DCF pages when the profile does not call for one


# ------------------------------------------------------------------ the page-fit script
pw = pytest.importorskip("playwright.sync_api")


def _chromium():
    import glob
    base = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "")
    hits = sorted(glob.glob(os.path.join(base, "chromium-*", "chrome-linux*", "chrome")))
    return hits[-1] if hits else None


@pytest.fixture(scope="module")
def browser():
    exe = _chromium()
    if not exe:
        pytest.skip("no Chromium available")
    with pw.sync_playwright() as p:
        b = p.chromium.launch(executable_path=exe, args=["--no-sandbox"])
        yield b
        b.close()


def _fit_report(browser, html, tmp_path):
    f = tmp_path / "note.html"
    f.write_text(html, encoding="utf-8")
    page = browser.new_page(viewport={"width": 1000, "height": 1200})
    page.goto(f.as_uri())
    page.wait_for_function("document.body.dataset.fit==='done'")
    info = page.evaluate("""()=>[...document.querySelectorAll('.pg')].map(p=>({id:p.id,main:+p.dataset.fillMain,side:+(p.dataset.fillSide||0),
        clipped:[...p.querySelectorAll('.pm-in p, .pm-in li')].filter(e=>!e.closest('[hidden]')&&e.getBoundingClientRect().bottom>p.querySelector('.pmain').getBoundingClientRect().bottom+1).length}))""")
    page.close()
    return info


@pytest.mark.parametrize("ticker", ["MU", "UEC", "GFI"])
def test_no_page_overflows_or_clips_text(browser, tmp_path, ticker):
    data, prov = load_snapshot(os.path.join(FIX, f"{ticker}.json"))
    html = value_data(data, prov, ValuationConfig(reloj_live=False))["html"]
    for pg in _fit_report(browser, html, tmp_path):
        assert pg["main"] <= 1.005 and pg["side"] <= 1.005, pg
        assert pg["clipped"] == 0, pg


def test_standard_pages_are_filled(browser, tmp_path):
    """The point of the fit script: no page of a normal report ends half-empty."""
    data, prov = load_snapshot(os.path.join(FIX, "MU.json"))
    html = value_data(data, prov, ValuationConfig(reloj_live=False))["html"]
    info = _fit_report(browser, html, tmp_path)
    assert all(pg["main"] >= 0.97 for pg in info if pg["id"] not in ("p14", "p15")), info


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


def test_compact_side_charts_are_well_formed():
    from equityval import charts_side as cs
    steps = [{"label": "Price", "value": 100.0, "kind": "total"}, {"label": "Re-rating", "value": 20.0, "kind": "delta"},
             {"label": "Dividends", "value": -1.0, "kind": "delta"}, {"label": "Target", "value": 119.0, "kind": "total"}]
    svg = cs.waterfall_h(steps, "$", 246)
    assert svg.count("<rect") >= 8 and "nan" not in svg
    rows = [{"label": "DCF", "sub": "20%", "low": 80, "high": 120, "point": 100, "kind": "lens"},
            {"label": "Street", "sub": "Street", "low": 110, "high": 160, "point": 140, "kind": "street"}]
    assert "<path" in cs.football_stack(rows, 90.0, 115.0, "$", 246)
    mult = [{"metric": "P/E", "now": 10.0, "ref": 20.0, "target": 12.0, "prem": -0.5, "lower_better": True, "fmt": "x"}]
    assert "bul-ref" in cs.multiples_stack(mult, 246)


def test_negative_currency_keeps_the_sign_in_front():
    from equityval import charts
    assert charts._cs("$", "-5.34") == "-$5.34" and charts._cs("$", "5.34") == "$5.34"
