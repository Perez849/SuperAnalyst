#!/usr/bin/env python3
"""Build docs/index.html -- the valuation library, in the Investment Clock design.

Scans docs/reports/*.json (one sidecar per generated report) and renders a landing page:
a phase wheel summarising where the covered names live on the cycle, then one card per
report with a mini valuation dial, the 12-month target, expected return and the Street
cross-check. All colours come from equityval/theme.py.

    python scripts/build_index.py            # defaults to ./docs
    python scripts/build_index.py --docs docs
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from equityval import charts, theme  # noqa: E402


def css(t: dict) -> str:
    return f"""
body{{background:{t['bg']};color:{t['ink']}}} a{{color:{t['brass']}}}
.eyebrow,.muted,.nm,.foot,.k,.disc,.legend{{color:{t['muted']}}}
.masthead{{border-top:3px solid {t['brass']}}}
.card,.panel{{background:{t['surface']};border:1px solid {t['hair']};box-shadow:{t['shadow']}}}
.card:hover{{border-color:{t['brass']}}}
.pill.up{{background:{t['up']};color:#06130D}} .pill.down{{background:{t['down']};color:#1B0705}}
.pill.flat{{background:{t['flat']};color:#0A0F1C}}
.up{{color:{t['up']}}} .down{{color:{t['down']}}} .flat{{color:{t['flat']}}}
.row{{border-top:1px solid {t['hair']}}}
.chip{{border:1px solid {t['hair']};color:{t['muted']}}} .chip.on{{border-color:{t['brass']};color:{t['brass']}}}
.conf-High{{color:{t['up']}}} .conf-Medium{{color:{t['brass']}}} .conf-Low{{color:{t['down']}}}
.mgband{{fill:none;stroke-width:15}} .mgband.b-down2{{stroke:{t['down']}}} .mgband.b-down{{stroke:{t['down']};opacity:.55}}
.mgband.b-flat{{stroke:{t['flat']};opacity:.7}} .mgband.b-up{{stroke:{t['up']};opacity:.6}} .mgband.b-up2{{stroke:{t['up']}}}
.mghand{{stroke-width:7;stroke-linecap:round}} .mghand-up{{stroke:{t['up']}}} .mghand-down{{stroke:{t['down']}}} .mghand-flat{{stroke:{t['ink']}}}
.mghub{{fill:{t['surface']};stroke:{t['brass']};stroke-width:2}}
.dot-recovery{{background:{t['recovery']}}} .dot-overheat{{background:{t['overheat']}}}
.dot-stagflation{{background:{t['stagflation']}}} .dot-reflation{{background:{t['reflation']}}}
.wheel .seg{{stroke:{t['bg']};stroke-width:2}} .wheel .seg-recovery{{fill:{t['recovery']}}} .wheel .seg-overheat{{fill:{t['overheat']}}}
.wheel .seg-stagflation{{fill:{t['stagflation']}}} .wheel .seg-reflation{{fill:{t['reflation']}}}
.wheel .seg.lit{{opacity:1}} .wheel .seg.lit2{{opacity:.55}} .wheel .seg.dim{{opacity:.16}}
.wheel .ph-n{{font:800 11px {theme.FONT_SANS};letter-spacing:.1em;fill:#08101C}}
.wheel .ph-s,.wheel .ph-a{{font:500 8.5px {theme.FONT_SANS};fill:#08101C}} .wheel .dim{{fill:{t['muted']}}}
.wheel .wheel-hub{{fill:{t['surface']};stroke:{t['hair']}}} .wheel .wheel-arrow{{fill:none;stroke:{t['brass']};stroke-width:2.2}}
.wheel .wheel-head{{fill:{t['brass']}}} .wheel .wheel-c{{fill:{t['muted']};font:700 9px {theme.FONT_SANS};letter-spacing:.2em}}
.count{{fill:{t['ink']};font:700 22px {theme.FONT_SERIF}}}
"""


PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Equity Research — Investment Clock</title>
<style>
  *{{box-sizing:border-box}}
  body{{margin:0;font-family:{sans};font-size:15px;line-height:1.5}}
  .wrap{{max-width:1080px;margin:0 auto;padding:44px 36px 80px}}
  .serif{{font-family:{serif}}} .mono{{font-family:{mono};font-variant-numeric:tabular-nums}}
  .eyebrow{{font-size:10.5px;letter-spacing:.18em;text-transform:uppercase;font-weight:700}}
  h1{{font-size:42px;line-height:1.05;margin:.12em 0 .15em;font-weight:600;letter-spacing:-.01em}}
  .masthead{{padding-top:14px;margin-bottom:26px}}
  .hero{{display:grid;grid-template-columns:1fr 330px;gap:40px;align-items:center;margin:18px 0 38px}}
  .lead{{font-size:16px;max-width:520px}}
  .wheel{{width:100%;height:auto;display:block}}
  .chips{{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 18px}}
  .chip{{font-size:11px;letter-spacing:.08em;text-transform:uppercase;font-weight:700;padding:5px 12px;border-radius:99px;cursor:pointer;background:none}}
  .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:16px}}
  .card{{position:relative;border-radius:12px;padding:16px 18px 14px;color:inherit;display:block;transition:border-color .15s,transform .15s}}
  .stretch{{color:inherit;text-decoration:none}} .stretch::after{{content:"";position:absolute;inset:0;border-radius:12px}}
  .links{{position:relative;z-index:2}}
  .card:hover{{transform:translateY(-2px)}}
  .head{{display:flex;justify-content:space-between;align-items:flex-start;gap:10px}}
  .tk{{font-size:22px;font-weight:600;letter-spacing:.01em}}
  .nm{{font-size:12.5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:190px}}
  .pill{{display:inline-block;padding:3px 10px;border-radius:3px;font-weight:800;font-size:10.5px;letter-spacing:.1em;margin-top:6px}}
  .row{{display:flex;justify-content:space-between;align-items:baseline;padding:6px 0;font-size:13px}}
  .row:first-of-type{{margin-top:10px}}
  .foot{{margin-top:8px;font-size:11.5px;display:flex;justify-content:space-between;align-items:center}}
  .dots i{{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:4px}}
  .pdf{{font-weight:700;text-decoration:none}}
  .empty{{border:1px dashed {hair};padding:40px;text-align:center}}
  .disc{{font-size:11px;margin-top:44px;padding-top:14px;border-top:1px solid {hair}}}
  .legend{{font-size:11.5px;margin-top:10px}}
  @media(max-width:820px){{.hero{{grid-template-columns:1fr}}.wrap{{padding:24px 16px 60px}}h1{{font-size:32px}}}}
  {screen}
  @media print{{ {light} .chips{{display:none}} }}
</style></head><body><div class="wrap">
  <div class="masthead">
    <div class="eyebrow">Equity Research · Investment Clock</div>
    <h1 class="serif">Valuation library</h1>
    <div class="mono muted" style="font-size:12px">{count} report(s) · updated {updated}</div>
  </div>
  <div class="hero">
    <div>
      <p class="lead">Every report triangulates a 12-month price target from several lenses — forward multiples,
        a DCF with decaying growth, and sector models — then cross-checks it against the Street.
        The dial on each card is the expected total return: green right of centre, red left.</p>
      <div class="legend">Wheel: where the covered names live on the Investment Clock
        (sector affinity, clockwise: Recovery → Overheat → Stagflation → Reflation). Numbers are reports whose
        home phase it is.</div>
    </div>
    <div>{wheel}</div>
  </div>
  {chips}
  {body}
  <div class="disc">Generado automáticamente por <b>equityval</b>. Cada informe es una valoración independiente y
    sector-aware; el precio objetivo se ancla ligeramente al consenso de la calle cuando existe y se muestra siempre
    el valor del modelo por separado. No es asesoramiento de inversión.</div>
</div>
<script>
  document.querySelectorAll('.chip').forEach(function(c){{c.addEventListener('click',function(){{
    var on=c.classList.toggle('on'); var f=c.dataset.f;
    document.querySelectorAll('.chip').forEach(function(o){{if(o!==c)o.classList.remove('on')}});
    document.querySelectorAll('.card').forEach(function(card){{
      card.style.display=(!on||f==='all'||card.dataset.phase.indexOf(f)>-1||card.dataset.dir===f)?'':'none';}});
  }})}});
</script></body></html>"""

CARD = """<div class="card" data-phase="{phases}" data-dir="{dir}">
    <div class="head">
      <div><div class="tk"><a class="stretch" href="reports/{html}">{ticker}</a></div><div class="nm" title="{name}">{name}</div>
        <span class="pill {dir}">{rating}</span></div>
      {gauge}
    </div>
    <div class="row"><span class="k">{tlabel}</span><span class="mono">{cur}{target}</span></div>
    <div class="row"><span class="k">Price</span><span class="mono">{cur}{price}</span></div>
    <div class="row"><span class="k">Expected return</span><span class="mono {dir}">{ret}</span></div>
    <div class="row"><span class="k">Street · confidence</span><span class="mono">{street} · <span class="conf-{conf}">{conf}</span></span></div>
    <div class="foot"><span class="dots">{dots}</span><span class="mono">{date}</span><span class="links">{links}</span></div>
  </div>"""


def rating_dir(rating: str) -> str:
    return {"OVERWEIGHT": "up", "ADD": "up", "REDUCE": "down", "UNDERWEIGHT": "down"}.get(rating, "flat")


def wheel_with_counts(counts: dict) -> str:
    svg = charts.phase_wheel("", None)
    # light every phase equally; overlay report counts at each quadrant's outer edge
    svg = svg.replace(" dim", " lit2")
    pos = {"recovery": (62, 70), "overheat": (298, 70), "stagflation": (298, 306), "reflation": (62, 306)}
    extra = "".join(f'<text class="count" x="{x}" y="{y}" text-anchor="middle">{counts.get(ph, 0)}</text>'
                    for ph, (x, y) in pos.items())
    return svg.replace("</svg>", extra + "</svg>")


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

    counts: dict = {}
    cards = []
    for m in metas:
        up = m.get("upside", 0) or 0
        ret = m.get("total_return", up)
        rated = m.get("rated", True)
        rating = m.get("rating", "NOT RATED" if not rated else "")
        rdir = rating_dir(rating)
        phases = m.get("phases") or []
        if phases:
            counts[phases[0]] = counts.get(phases[0], 0) + 1
        links = []
        if m.get("pdf"):
            links.append(f'<a class="pdf" href="reports/{m["pdf"]}">PDF</a>')
        if m.get("xlsx"):
            links.append(f'<a class="pdf" href="reports/{m["xlsx"]}">XLS</a>')
        street = m.get("street")
        cur = m.get("currency", "$")
        value = m.get("target", 0) if rated else m.get("fair_value", m.get("target", 0))
        cards.append(CARD.format(
            html=m["html"], ticker=escape(m["ticker"]), name=escape(m.get("name", "")),
            rating=escape(rating), dir=rdir, cur=cur, tlabel=("12M price target" if rated else "Indicative value"), target=f'{value:,.2f}' + ("" if rated else "*"),
            price=f'{m.get("price", 0):,.2f}',
            ret=(f"{ret*100:+.0f}%" if rated else "n/a"),
            street=(f"{cur}{street:,.2f}" if street else "n/a"), conf=m.get("confidence", "Medium"),
            phases=" ".join(phases),
            dots="".join(f'<i class="dot-{p}" title="{p}"></i>' for p in phases),
            gauge=charts.mini_gauge(ret, rdir, rated), date=m.get("date", ""),
            links="&nbsp;·&nbsp;".join(links)))

    if not metas:
        body = '<div class="empty muted">Todavía no hay informes. Lanza el workflow "Equity valuation → Pages" con un ticker.</div>'
        chips = ""
    else:
        body = f'<div class="grid">{"".join(cards)}</div>'
        if any(not m.get("rated", True) for m in metas):
            body += '<p class="legend">* Not rated: indicative fair value shown, not a price target.</p>'
        chips = ('<div class="chips"><button class="chip" data-f="all">All</button>'
                 '<button class="chip" data-f="up">Positive</button><button class="chip" data-f="down">Negative</button>'
                 + "".join(f'<button class="chip" data-f="{p}">{theme.PHASE_NAMES[p][0]}</button>' for p in theme.PHASE_ORDER)
                 + "</div>")

    html = PAGE.format(
        sans=theme.FONT_SANS, serif=theme.FONT_SERIF, mono=theme.FONT_MONO, hair=theme.SCREEN["hair"],
        screen=css(theme.SCREEN), light=css(theme.PRINT), count=len(metas), updated=date.today().isoformat(),
        wheel=wheel_with_counts(counts), chips=chips, body=body)
    out = docs / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"Wrote {out} with {len(metas)} report(s)")


if __name__ == "__main__":
    main()
