#!/usr/bin/env python3
"""Command-line interface for the sector-aware equity valuation engine.

    python valorar.py AAPL --fmp-key XXXX -o aapl.html
    python valorar.py JPM --pdf                       # bank -> residual income
    python valorar.py O --pdf                          # REIT -> FFO/AFFO
    python valorar.py XOM --profile cyclical           # force a profile
    python valorar.py --demo --pdf
    python valorar.py --snapshot tests/fixtures/MU.json     # offline, reproducible

FMP_API_KEY is read from the environment if not passed.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path


def _chrome_binary() -> str | None:
    env = os.environ.get("CHROME_BIN")
    if env and shutil.which(env):
        return shutil.which(env)
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"):
        path = shutil.which(name)
        if path:
            return path
    import glob
    pw = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if pw:                                    # Playwright-managed Chromium
        hits = sorted(glob.glob(os.path.join(pw, "chromium-*", "chrome-linux*", "chrome")))
        if hits:
            return hits[-1]
    return None


def export_pdf(html_path: Path, pdf_path: Path) -> bool:
    """HTML -> PDF. Headless Chrome/Chromium first (the report uses modern CSS and inline SVG),
    then wkhtmltopdf, then weasyprint. Returns success."""
    chrome = _chrome_binary()
    if chrome:
        try:
            subprocess.run(
                [chrome, "--headless=new", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer",
                 f"--print-to-pdf={pdf_path.resolve()}", html_path.resolve().as_uri()],
                check=True, capture_output=True, timeout=180)
            if pdf_path.exists() and pdf_path.stat().st_size > 0:
                return True
        except Exception as e:
            print(f"[warn] chrome PDF failed: {e}")
    wk = shutil.which("wkhtmltopdf")
    if wk:
        try:
            subprocess.run(
                [wk, "--enable-local-file-access", "--quiet", "--print-media-type",
                 "--page-size", "A4",
                 "--margin-top", "12mm", "--margin-bottom", "12mm",
                 "--margin-left", "10mm", "--margin-right", "10mm",
                 str(html_path), str(pdf_path)],
                check=True, capture_output=True)
            return True
        except Exception as e:
            print(f"[warn] wkhtmltopdf failed: {e}")
    try:
        from weasyprint import HTML
        HTML(str(html_path)).write_pdf(str(pdf_path))
        return True
    except Exception as e:
        print(f"[warn] weasyprint unavailable: {e}")
    print("[info] No PDF engine found. Open the HTML and use the 'Save as PDF' button.")
    return False


def main(argv=None):
    ap = argparse.ArgumentParser(description="Sector-aware equity valuation & research note.")
    ap.add_argument("ticker", nargs="?", help="Stock ticker, e.g. AAPL")
    ap.add_argument("--demo", action="store_true", help="Run on bundled synthetic company (offline)")
    ap.add_argument("-o", "--output", default=None, help="Output HTML path")
    ap.add_argument("--pdf", action="store_true", help="Also export a PDF")
    ap.add_argument("--xlsx", action="store_true", help="Also export a live-formula Excel model")
    ap.add_argument("--provider", default="auto", choices=["auto", "fmp", "yfinance", "alphavantage", "av"])
    ap.add_argument("--fmp-key", default=None, help="FMP API key (or set FMP_API_KEY)")
    ap.add_argument("--profile", default=None,
                    choices=["standard", "bank", "insurance", "reit", "utility",
                             "cyclical", "high_growth"],
                    help="Force a valuation profile (else auto-classified)")
    ap.add_argument("--snapshot", default=None,
                    help="Value from a saved Yahoo snapshot JSON instead of the network (offline/reproducible)")
    ap.add_argument("--street-weight", type=float, default=0.30,
                    help="Max weight of Street consensus in the 12m target (0 = pure model; default 0.30)")
    ap.add_argument("--rf", type=float, default=0.043, help="Risk-free rate")
    ap.add_argument("--erp", type=float, default=0.046, help="Equity risk premium")
    ap.add_argument("--country-premium", type=float, default=0.0)
    ap.add_argument("--terminal-growth", type=float, default=0.025)
    ap.add_argument("--horizon", type=int, default=None, help="Override explicit horizon")
    ap.add_argument("--exit-multiple", type=float, default=None, help="Exit EV/EBITDA cross-check")
    ap.add_argument("--beta", type=float, default=None, help="Override beta")
    ap.add_argument("--json", dest="json_path", default=None,
                    help="Also write a metadata JSON sidecar (for the Pages index)")
    ap.add_argument("--open", action="store_true", help="Open the report in a browser")
    args = ap.parse_args(argv)

    from equityval.engine import ValuationConfig, value_company, value_data

    cfg = ValuationConfig(
        horizon=args.horizon, terminal_growth=args.terminal_growth,
        risk_free=args.rf, erp=args.erp, country_premium=args.country_premium,
        exit_multiple=args.exit_multiple, beta_override=args.beta,
        profile_override=args.profile, street_weight=args.street_weight,
    )

    if args.demo:
        from equityval.demo_data import demo_company, demo_peers
        res = value_data(demo_company(), None, cfg, peer_snaps=demo_peers())
        ticker = "DEMO"
    elif args.snapshot:
        from equityval.offline import load_snapshot
        data, prov = load_snapshot(args.snapshot)
        res = value_data(data, prov, cfg)
        ticker = data.ticker.upper()
    else:
        if not args.ticker:
            ap.error("provide a ticker, --snapshot or --demo")
        res = value_company(args.ticker, args.provider, args.fmp_key, cfg)
        ticker = args.ticker.upper()

    d = res["data"]
    tr = res["tr"]
    from equityval.report import derive_rating
    rating, _ = derive_rating(tr.total_return, tr.rated)
    street = f" | Street {d.currency_symbol}{tr.street.mean:,.2f} ({tr.street.upside:+.0%})" if tr.street else ""
    print(f"{ticker}: {res['profile'].value} profile | {rating} | 12m target "
          f"{d.currency_symbol}{tr.target:,.2f} ({tr.upside:+.1%} vs {d.currency_symbol}{d.price:,.2f}) | "
          f"fair value today {d.currency_symbol}{tr.fair_value:,.2f} | confidence {tr.confidence}{street}")
    for l in tr.lenses:
        print(f"   {l.label:34s} {d.currency_symbol}{l.value:>12,.2f}  weight {l.eff_weight:>4.0%}  {l.status}")
    for g in tr.guardrails:
        print(f"   ! {g}")

    out = Path(args.output or f"{ticker}_valuation.html")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(res["html"], encoding="utf-8")
    print(f"HTML -> {out.resolve()}")

    if args.pdf:
        pdf = out.with_suffix(".pdf")
        if export_pdf(out, pdf):
            print(f"PDF  -> {pdf.resolve()}")

    if args.xlsx:
        from equityval.excel_export import export_model
        xpath = out.with_suffix(".xlsx")
        export_model(res["data"], res, str(xpath))
        print(f"XLSX -> {xpath.resolve()}")

    if args.json_path:
        import json
        from equityval.theme import phases_for
        meta = {
            "ticker": ticker, "name": d.name, "sector": d.sector,
            "profile": res["profile"].value, "currency": d.currency_symbol,
            "price": round(d.price, 2), "target": round(tr.target, 2),
            "upside": round(tr.upside, 4), "total_return": round(tr.total_return, 4),
            "rating": rating, "rated": tr.rated,
            "fair_value": round(tr.fair_value, 2), "bear": round(tr.bear, 2), "bull": round(tr.bull, 2),
            "confidence": tr.confidence,
            "street": round(tr.street.mean, 2) if tr.street else None,
            "street_upside": round(tr.street.upside, 4) if tr.street else None,
            "phases": list(phases_for(d.sector, res["profile"].value)),
            "date": getattr(d, "asof", None) or __import__("datetime").date.today().isoformat(),
            "html": out.name, "pdf": out.with_suffix(".pdf").name if args.pdf else None,
            "xlsx": out.with_suffix(".xlsx").name if args.xlsx else None,
        }
        Path(args.json_path).write_text(json.dumps(meta, indent=2), encoding="utf-8")
        print(f"JSON -> {Path(args.json_path).resolve()}")

    if args.open:
        webbrowser.open(out.resolve().as_uri())


if __name__ == "__main__":
    main()
