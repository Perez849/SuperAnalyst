#!/usr/bin/env python3
"""Build docs/index.html from the metadata sidecars in docs/reports/.

Scans docs/reports/*.json (one per generated report) and renders a styled
landing page that lists every valuation with rating, target and upside, linking
to the HTML report and PDF. Matches the report's visual language.

    python scripts/build_index.py            # defaults to ./docs
    python scripts/build_index.py --docs docs
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Equity Research — Valuation Library</title>
<style>
  :root{{--ink:#0E1116;--paper:#FBFBF9;--teal:#0F6466;--up:#1B7A5A;--down:#B23A48;
    --hair:#C9C9C2;--muted:#6B6F76;}}
  *{{box-sizing:border-box}} body{{margin:0;background:var(--paper);color:var(--ink);
    font-family:"Helvetica Neue",Arial,system-ui,sans-serif;font-size:15px;line-height:1.5;}}
  .wrap{{max-width:1000px;margin:0 auto;padding:48px 40px 80px;}}
  .serif{{font-family:"Iowan Old Style",Palatino,Georgia,serif;}}
  .mono{{font-family:ui-monospace,"SF Mono",Menlo,monospace;font-variant-numeric:tabular-nums;}}
  .eyebrow{{font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:var(--muted);font-weight:600;}}
  h1{{font-size:32px;margin:.15em 0 .35em;font-weight:600;}}
  .masthead{{border-top:3px solid var(--ink);padding-top:14px;margin-bottom:28px;}}
  .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px;}}
  .card{{border:1px solid var(--hair);background:#fff;padding:16px 18px;text-decoration:none;color:inherit;
    display:block;transition:border-color .15s;}}
  .card:hover{{border-color:var(--teal);}}
  .card .tk{{font-size:20px;font-weight:600;}}
  .card .nm{{font-size:12.5px;color:var(--muted);margin-bottom:10px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}}
  .pill{{display:inline-block;padding:3px 10px;border-radius:2px;font-weight:700;font-size:11px;
    letter-spacing:.06em;color:#fff;}}
  .pill.up{{background:var(--up)}} .pill.down{{background:var(--down)}} .pill.flat{{background:var(--muted)}}
  .row{{display:flex;justify-content:space-between;align-items:baseline;margin-top:10px;font-size:13px;}}
  .up{{color:var(--up)}} .down{{color:var(--down)}}
  .prof{{font-size:10px;letter-spacing:.06em;text-transform:uppercase;color:var(--teal);
    border:1px solid var(--teal);border-radius:2px;padding:1px 7px;display:inline-block;margin-top:8px;}}
  .foot{{margin-top:10px;font-size:11.5px;color:var(--muted);display:flex;justify-content:space-between;}}
  .pdf{{color:var(--teal);text-decoration:none;font-weight:600;}}
  .empty{{border:1px dashed var(--hair);padding:40px;text-align:center;color:var(--muted);}}
  .disc{{font-size:11px;color:var(--muted);margin-top:40px;border-top:1px solid var(--hair);padding-top:14px;}}
</style></head><body><div class="wrap">
  <div class="masthead">
    <div class="eyebrow">Equity Research · Independent Valuations</div>
    <h1 class="serif">Valuation library</h1>
    <div class="mono" style="color:var(--muted);font-size:12px">{count} report(s) · updated {updated}</div>
  </div>
  {body}
  <div class="disc">Generado automáticamente por <b>equityval</b>. Cada informe es una valoración
    independiente y sector-aware. No es asesoramiento de inversión.</div>
</div></body></html>"""

CARD = """<a class="card" href="reports/{html}">
    <div class="tk">{ticker} <span class="pill {dir}">{rating}</span></div>
    <div class="nm">{name}</div>
    <div><span class="prof">{profile}</span></div>
    <div class="row"><span>Fair value</span><span class="mono">{cur}{target}</span></div>
    <div class="row"><span>Price</span><span class="mono">{cur}{price}</span></div>
    <div class="row"><span>Upside</span><span class="mono {dir}">{upside}</span></div>
    <div class="foot"><span>{date}</span>{pdf_link}</div>
  </a>"""


def rating_dir(upside):
    if upside >= 0.05: return "up"
    if upside > -0.05: return "flat"
    return "down"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", default="docs")
    args = ap.parse_args()
    docs = Path(args.docs)
    reports = docs / "reports"
    reports.mkdir(parents=True, exist_ok=True)

    metas = []
    for jf in sorted(reports.glob("*.json")):
        try:
            metas.append(json.loads(jf.read_text(encoding="utf-8")))
        except Exception:
            pass
    metas.sort(key=lambda m: m.get("date", ""), reverse=True)

    if not metas:
        body = '<div class="empty">Todavía no hay informes. Lanza el workflow "Equity valuation → Pages" con un ticker.</div>'
    else:
        cards = []
        for m in metas:
            up = m.get("upside", 0)
            links = []
            if m.get("pdf"):
                links.append(f'<a class="pdf" href="reports/{m["pdf"]}">PDF</a>')
            if m.get("xlsx"):
                links.append(f'<a class="pdf" href="reports/{m["xlsx"]}">XLS</a>')
            pdf_link = f'<span>{"&nbsp;·&nbsp;".join(links)}</span>' if links else "<span></span>"
            cards.append(CARD.format(
                html=m["html"], ticker=m["ticker"], name=m.get("name", ""),
                rating=m.get("rating", ""), dir=rating_dir(up),
                profile=m.get("profile", ""), cur=m.get("currency", "$"),
                target=f'{m.get("target", 0):,.2f}', price=f'{m.get("price", 0):,.2f}',
                upside=f'{up*100:+.0f}%', date=m.get("date", ""), pdf_link=pdf_link,
            ))
        body = f'<div class="grid">{"".join(cards)}</div>'

    out = docs / "index.html"
    out.write_text(PAGE.format(count=len(metas), updated=date.today().isoformat(), body=body),
                   encoding="utf-8")
    print(f"Wrote {out} with {len(metas)} report(s)")


if __name__ == "__main__":
    main()
