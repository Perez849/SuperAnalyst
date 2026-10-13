"""Browser test of the library page and its "Generar PDF" panel (network fully mocked).

Needs Playwright and a Chromium (PLAYWRIGHT_BROWSERS_PATH); skipped otherwise.
"""
import functools
import glob
import http.server
import json
import os
import threading

import pytest

pw = pytest.importorskip("playwright.sync_api")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")


def _chromium():
    base = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "")
    hits = sorted(glob.glob(os.path.join(base, "chromium-*", "chrome-linux*", "chrome")))
    return hits[-1] if hits else None


@pytest.fixture(scope="module")
def server():
    if not os.path.exists(os.path.join(DOCS, "index.html")):
        pytest.skip("docs/index.html not built")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=DOCS)
    handler.log_message = lambda *a, **k: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


@pytest.fixture(scope="module")
def browser():
    exe = _chromium()
    if not exe:
        pytest.skip("no Chromium available")
    with pw.sync_playwright() as p:
        b = p.chromium.launch(executable_path=exe, args=["--no-sandbox"])
        yield b
        b.close()


def test_library_renders_without_errors(server, browser):
    page = browser.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(server + "/index.html")
    assert page.locator(".rcard").count() >= 1
    assert page.locator("#genForm").count() == 1
    assert "Reloj" in page.content() or "SuperAnalyst" in page.title()
    assert not errors, errors
    # every card has a PDF link
    for card in page.locator(".rcard").all():
        assert card.locator(".rlinks a", has_text="PDF").count() == 1


def test_invalid_ticker_is_rejected_client_side(server, browser):
    page = browser.new_page()
    page.goto(server + "/index.html")
    page.fill("#genTicker", "AAPL; rm -rf /")
    page.evaluate("document.getElementById('genTicker').removeAttribute('maxlength')")
    page.click("#genGo")
    page.wait_for_selector("#genMsg:has-text('no válido')")
    assert page.locator("#genDone").is_hidden()


def test_generate_flow_with_token_mode(server, browser):
    ctx = browser.new_context()
    page = ctx.new_page()
    dispatched = {}

    def gh(route):
        req = route.request
        if req.method == "POST" and req.url.endswith("/dispatches"):
            dispatched["body"] = json.loads(req.post_data)
            dispatched["auth"] = req.headers.get("authorization")
            return route.fulfill(status=204, body="")
        return route.fulfill(status=200, content_type="application/json", body=json.dumps({"workflow_runs": [
            {"created_at": "2999-01-01T00:00:00Z", "status": "completed", "conclusion": "success",
             "html_url": "https://github.com/x/y/actions/runs/1"}]}))

    page.route("https://api.github.com/**", gh)
    page.route("**/reports/ZZZ.json*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps({
        "ticker": "ZZZ", "name": "Zeta Corp", "rating": "ADD", "rated": True, "currency": "$", "target": 123.45,
        "html": "ZZZ.html", "pdf": "ZZZ.pdf", "xlsx": "ZZZ.xlsx", "generated_at": "2999-01-01T00:00:00Z"})))
    page.add_init_script("""
        localStorage.setItem('superanalyst.ghtoken','github_pat_test');
        const _st = window.setTimeout; window.setTimeout = (f, ms, ...a) => _st(f, ms > 1000 ? 5 : ms, ...a);""")
    page.goto(server + "/index.html")
    page.fill("#genTicker", "zzz")
    page.select_option("#genProfile", "bank")
    page.click("#genGo")
    page.wait_for_selector("#genDone a:has-text('Descargar PDF')", timeout=15000)
    assert dispatched["body"]["inputs"] == {"ticker": "ZZZ", "profile": "bank", "provider": "auto"}
    assert dispatched["body"]["ref"] == "main"
    assert dispatched["auth"] == "Bearer github_pat_test"
    assert page.locator("#genDone a[href='reports/ZZZ.pdf']").count() == 1
