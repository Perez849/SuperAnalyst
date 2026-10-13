#!/usr/bin/env python3
"""Build docs/index.html -- the valuation library, in the Reloj de inversión design.

Scans docs/reports/*.json (one sidecar per generated report) and renders the landing page:
a hero with the four-phase wheel, a "generate a PDF from here" panel (assets/generate.js),
one card per report with a mini valuation dial, and a short methodology. Also writes
docs/assets/superanalyst.css (the shared design sheet, from equityval/design.py).

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
from equityval import charts, design, theme  # noqa: E402

LIBRARY_CSS = """
/* ---------- library page ---------- */
.hero-stats{display:grid;grid-template-columns:repeat(2,1fr);gap:1px;background:var(--line);border:1px solid var(--line);border-radius:var(--r-md);overflow:hidden;margin-top:26px;max-width:470px}
.hero-stat{background:var(--paper-raised);padding:14px 16px}
.hero-stat dt{font-family:var(--mono);font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-faint);margin-bottom:4px}
.hero-stat dd{margin:0;font-family:var(--mono);font-size:17px;color:var(--ink)}
.seg{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 18px}
.seg button{font-family:var(--mono);font-size:11px;padding:6px 13px;border-radius:99px;cursor:pointer;background:var(--paper-raised);color:var(--ink-soft);border:1px solid var(--line);transition:.15s}
.seg button[aria-pressed=true]{background:var(--ink);color:var(--paper);border-color:var(--ink)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:16px}
.rcard{position:relative;background:var(--paper-raised);border:1px solid var(--line);border-radius:var(--r-md);padding:18px 20px 14px;box-shadow:var(--shadow-card);transition:border-color .15s,transform .15s}
.rcard:hover{border-color:var(--accent);transform:translateY(-2px)}
.rcard .head{display:flex;justify-content:space-between;align-items:flex-start;gap:10px}
.rcard .tk{font-family:var(--serif);font-size:26px;font-weight:600;letter-spacing:-.01em;line-height:1.1}
.rcard .tk a{color:inherit;text-decoration:none}
.rcard .tk a::after{content:"";position:absolute;inset:0;border-radius:var(--r-md)}
.rcard .nm{font-size:12.5px;color:var(--ink-faint);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:190px;margin-bottom:8px}
.rpill{display:inline-block;font-family:var(--mono);font-size:10.5px;font-weight:600;letter-spacing:.08em;padding:3px 10px;border-radius:99px;border:1px solid var(--line-strong);color:var(--ink-soft);background:var(--paper-deep)}
.rpill.up{background:rgba(63,107,82,.12);color:var(--rec);border-color:rgba(63,107,82,.4)}
.rpill.down{background:rgba(156,74,60,.1);color:var(--stag);border-color:rgba(156,74,60,.4)}
.rrow{display:flex;justify-content:space-between;align-items:baseline;padding:7px 0;border-top:1px solid var(--line-soft);font-size:13px}
.rrow:first-of-type{margin-top:10px}
.rrow .k{color:var(--ink-soft)} .rrow .mono{color:var(--ink)}
.conf-High{color:var(--rec)} .conf-Medium{color:var(--accent-ink)} .conf-Low{color:var(--stag)}
.rfoot{margin-top:10px;font-size:11.5px;color:var(--ink-faint);display:flex;justify-content:space-between;align-items:center;gap:8px}
.dots i{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:4px}
.dot-recovery{background:var(--rec)} .dot-overheat{background:var(--over)} .dot-stagflation{background:var(--stag)} .dot-reflation{background:var(--refl)}
.rlinks{position:relative;z-index:2;display:flex;gap:10px}
.rlinks a{font-family:var(--mono);font-size:11px;font-weight:600;text-decoration:none;color:var(--accent-ink);border:1px solid var(--line-strong);border-radius:99px;padding:2px 10px;background:var(--paper)}
.rlinks a:hover{background:var(--accent);color:var(--paper-raised);border-color:var(--accent)}
.empty{border:1px dashed var(--line-strong);border-radius:var(--r-md);padding:40px;text-align:center;color:var(--ink-faint)}

/* ---------- generator (inside the dark block) ---------- */
.gen{display:grid;grid-template-columns:minmax(0,1.3fr) minmax(0,1fr) minmax(0,1fr) auto;gap:12px;align-items:end;margin-top:26px}
.gen label{display:block;font-family:var(--mono);font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;color:rgba(251,249,243,.55)}
.gen input,.gen select{width:100%;margin-top:7px;font:500 15px var(--sans);color:var(--paper-raised);background:rgba(251,249,243,.06);border:1px solid rgba(251,249,243,.22);border-radius:var(--r-sm);padding:11px 12px}
.gen input::placeholder{color:rgba(251,249,243,.35)}
.gen input:focus,.gen select:focus{outline:2px solid var(--gold);outline-offset:1px}
.gen select option{color:#1B1810}
.pdf-btn.gold{background:var(--gold);color:var(--ink);border-color:var(--gold);padding:12px 20px;font-size:13px}
.pdf-btn.gold:hover{background:var(--paper-raised)}
.pdf-btn:disabled{opacity:.5;cursor:wait}
.gen-mode{margin-top:14px;font-family:var(--mono);font-size:11px;color:rgba(251,249,243,.55)}
.gen-mode::before{content:"";display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:8px;background:rgba(251,249,243,.35)}
.gen-mode.api::before,.gen-mode.token::before{background:#8FC7A6}
.gen-status{margin-top:22px;border:1px solid rgba(251,249,243,.16);border-radius:var(--r-md);padding:18px 20px;background:rgba(251,249,243,.03)}
.gen-steps{list-style:none;margin:0 0 12px;padding:0;display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px}
.gen-steps li{font-size:12.5px;color:rgba(251,249,243,.45);display:flex;align-items:center;gap:8px;margin:0}
.gen-steps li i{width:9px;height:9px;border-radius:50%;border:1px solid rgba(251,249,243,.4);flex:none}
.gen-steps li.done{color:rgba(251,249,243,.85)} .gen-steps li.done i{background:#8FC7A6;border-color:#8FC7A6}
.gen-steps li.now{color:var(--gold)} .gen-steps li.now i{background:var(--gold);border-color:var(--gold);animation:pulse 1.1s ease-in-out infinite}
.gen-steps li.bad{color:#E3A596} .gen-steps li.bad i{background:#E3A596;border-color:#E3A596}
@keyframes pulse{0%,100%{opacity:.35}50%{opacity:1}}
#genMsg{font-size:13.5px;color:rgba(251,249,243,.75);max-width:78ch} #genMsg a{color:var(--gold)}
.gen-result{display:flex;justify-content:space-between;align-items:center;gap:18px;flex-wrap:wrap;margin-top:16px;padding-top:16px;border-top:1px solid rgba(251,249,243,.16)}
.gen-result .k{font-family:var(--mono);font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:rgba(251,249,243,.55)}
.gen-result .v{font-family:var(--serif);font-size:26px;color:var(--paper-raised)}
.gen-links{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.gen-links .ghost{color:rgba(251,249,243,.85);border-color:rgba(251,249,243,.3)} .gen-links .ghost:hover{background:rgba(251,249,243,.1);color:var(--paper-raised)}
.dark-details{margin-top:18px;border-top:1px solid rgba(251,249,243,.12);padding-top:6px}
.dark-details summary{cursor:pointer;font-family:var(--mono);font-size:11.5px;letter-spacing:.04em;color:rgba(251,249,243,.6);padding:10px 0;list-style:none}
.dark-details summary::-webkit-details-marker{display:none}
.dark-details summary::before{content:"+ ";color:var(--gold)} .dark-details[open] summary::before{content:"– "}
.dark-details p,.dark-details li{font-size:13px;color:rgba(251,249,243,.7);max-width:80ch}
.dark-details a{color:var(--gold)} .dark-details code{color:var(--gold);font-size:12px}
.tokrow{display:flex;gap:10px;margin:10px 0;flex-wrap:wrap}
.tokrow input{flex:1;min-width:220px;font:500 14px var(--mono);color:var(--paper-raised);background:rgba(251,249,243,.06);border:1px solid rgba(251,249,243,.22);border-radius:var(--r-sm);padding:10px 12px}
.tokrow button{font:600 12px var(--sans);border-radius:99px;padding:9px 16px;cursor:pointer;border:1px solid rgba(251,249,243,.3);background:transparent;color:var(--paper-raised)}
.tokrow button:hover{background:rgba(251,249,243,.1)}
@media (max-width:860px){.gen{grid-template-columns:1fr 1fr}.gen .pdf-btn{grid-column:1/-1}}
@media print{.buy,.gen-status{display:none}}
"""

PAGE = """<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>SuperAnalyst · Valoración con criterio de industria</title>
<meta name="description" content="Precios objetivo a 12 meses triangulados con varias lentes (múltiplos forward, DCF acotado y modelos por sector), contrastados con la calle. Genera el informe en PDF desde la propia web.">
<link rel="stylesheet" href="assets/superanalyst.css?v={ver}">
</head><body>

<header class="top"><div class="wrap top-inner">
  <a class="brand" href="#top">{brand}<span><span class="brand-word">SuperAnalyst</span><br><span class="brand-tag">VALORACIÓN · LENTES · EVIDENCIA</span></span></a>
  <nav class="top-nav"><a href="#generar">Generar PDF</a><a href="#biblioteca">Biblioteca</a><a href="#metodo">Método</a>
    <a href="https://perez849.github.io/reloj-inversion/" target="_blank" rel="noopener">Reloj de inversión ↗</a></nav>
  <div class="top-actions"><a class="pdf-btn" href="#generar">⬇ Generar PDF</a></div>
</div></header>

<section class="hero" id="top"><div class="wrap hero-grid">
  <div>
    <div class="eyebrow hero-eyebrow">Biblioteca de valoraciones</div>
    <h1 class="phase-name">Precios objetivo que se parecen a los de la industria.</h1>
    <p class="phase-tie flat">{count} informes · actualizado {updated}</p>
    <p class="phase-why">Cada informe triangula un precio objetivo a 12 meses con varias lentes —
      <b>múltiplos forward</b>, un <b>DCF con crecimiento decreciente</b> y <b>modelos por sector</b>—,
      lo contrasta con la calle y avisa cuando no puede defender un número.</p>
    <dl class="hero-stats">
      <div class="hero-stat"><dt>Informes</dt><dd>{count}</dd></div>
      <div class="hero-stat"><dt>Rating positivo</dt><dd>{positive}</dd></div>
      <div class="hero-stat"><dt>Confianza alta</dt><dd>{high}</dd></div>
      <div class="hero-stat"><dt>Sin rating</dt><dd>{nr}</dd></div>
    </dl>
  </div>
  <figure class="plane-card">
    <div class="plane-top"><h3>Dónde viven en el ciclo</h3><span class="small-cap mono">informes por fase</span></div>
    <p class="cap" style="margin-bottom:12px">Fase en la que cada sector suele liderar (mapa clásico del <i>investment clock</i>).
      Los números cuentan los informes cuya fase principal es esa.</p>
    <div style="max-width:340px;margin:auto">{wheel}</div>
  </figure>
</div></section>

<section class="section" id="generar"><div class="wrap"><div class="buy"><div class="buy-inner">
  <div class="eyebrow">Pídelo aquí</div>
  <h2>Genera un informe en PDF desde la web</h2>
  <p class="lede">Escribe un ticker. GitHub Actions calcula la valoración, publica el informe en esta biblioteca y
    te devuelve el <b>PDF</b> y el <b>Excel</b> (2–4 minutos). Sin instalar nada.</p>
  <form class="gen" id="genForm" autocomplete="off">
    <label>Ticker<input id="genTicker" name="ticker" placeholder="AAPL · JPM · O · SAN.MC" maxlength="12" required spellcheck="false" autocapitalize="characters"></label>
    <label>Perfil<select id="genProfile">
      <option value="auto">Automático</option><option value="standard">Estándar</option><option value="bank">Banco</option>
      <option value="insurance">Seguro</option><option value="reit">REIT</option><option value="utility">Utility</option>
      <option value="cyclical">Cíclica</option><option value="high_growth">Alto crecimiento</option></select></label>
    <label>Datos<select id="genProvider"><option value="auto">Automático</option><option value="yfinance">Yahoo Finance</option><option value="fmp">FMP</option></select></label>
    <button class="pdf-btn gold" id="genGo" type="submit">⬇ Generar PDF</button>
  </form>
  <div class="gen-mode" id="genMode"></div>
  <div class="gen-status" id="genStatus" hidden>
    <ul class="gen-steps" id="genSteps"></ul>
    <p id="genMsg"></p>
    <div id="genDone" hidden></div>
  </div>
  <details class="dark-details" id="genConn">
    <summary>Conexión con GitHub (una sola vez)</summary>
    <div id="genTokenRow">
      <p>Esta web es estática: para lanzar el cálculo necesita permiso en GitHub. Hay dos formas:</p>
      <ul>
        <li><b>Worker (recomendado, 5 min):</b> despliega <code>worker/</code> en Cloudflare y pon su URL en
          <code>docs/assets/config.js</code>. El token nunca sale del Worker y cualquiera puede generar sin cuenta de GitHub.</li>
        <li><b>Token en este navegador:</b> crea un
          <a href="https://github.com/settings/personal-access-tokens/new" target="_blank" rel="noopener">token fino</a>
          limitado a este repositorio con permiso <i>Actions → Read and write</i> y pégalo aquí. Se guarda solo en tu
          navegador (<code>localStorage</code>) y solo se envía a <code>api.github.com</code>.</li>
      </ul>
      <div class="tokrow"><input id="genTokenInput" type="password" placeholder="github_pat_…" autocomplete="off" spellcheck="false">
        <button type="button" id="genSave">Guardar token</button><button type="button" id="genForget" hidden>Olvidar token</button></div>
    </div>
    <p>Sin ninguna de las dos, el botón te lleva a GitHub Actions (<i>Run workflow</i>) y esta página espera aquí al resultado.</p>
  </details>
  <p class="buy-foot"><b>Ya publicados:</b> cada tarjeta de la biblioteca tiene su PDF; dentro de cada informe,
    «Save as PDF» lo guarda desde el navegador sin esperar a nadie.</p>
</div></div></div></section>

<section class="section tight" id="biblioteca"><div class="wrap">
  <div class="section-head"><div class="eyebrow">Biblioteca</div><h2>Informes publicados</h2>
    <p class="cap">Cada tarjeta resume el precio objetivo a 12 meses, la rentabilidad esperada, el consenso de la calle y la confianza del modelo. El dial muestra la rentabilidad esperada: verde a la derecha, terracota a la izquierda.</p></div>
  {chips}
  {body}
</div></section>

<section class="section tight" id="metodo"><div class="wrap">
  <div class="section-head"><div class="eyebrow">Método</div><h2>Cómo se llega al número</h2>
    <p class="cap">Un solo modelo no valora bien a todos: un banco no es una minera ni una eléctrica. Por eso el motor clasifica
      la compañía y combina lentes distintas.</p></div>
  <ol class="rules">
    <li><b>Varias lentes, no una</b>Múltiplos forward, DCF y el modelo propio de cada sector (residual income en bancos, FFO en REIT, mid-cycle en cíclicas), con pesos por perfil.</li>
    <li><b>Múltiplos con criterio</b>El múltiplo objetivo parte de pares y de una tabla sectorial, y se ajusta por crecimiento duradero, apalancamiento y <i>durabilidad de los beneficios</i>: el mercado paga menos por picos de ciclo.</li>
    <li><b>DCF acotado</b>El crecimiento decae de forma geométrica hacia el terminal y los márgenes revierten a la media. Ningún salto de un año se extrapola una década.</li>
    <li><b>Guardrails visibles</b>Una lente fuera de 0,2×–5× el precio se excluye; las que se alejan mucho del resto pesan menos. Todo queda escrito en el informe.</li>
    <li><b>Objetivo a 12 meses</b>Valor justo × (1 + coste del capital) − dividendos, con rango bear–bull, y anclaje ligero (≤ 30 %) al consenso de la calle cuando existe.</li>
    <li><b>Honestidad</b>Si el modelo no puede defender un número, el informe sale <i>NOT RATED</i> en vez de inventarse un rating.</li>
  </ol>
</div></section>

<div class="foot-bar"><div class="wrap"><p class="disclaimer">Generado automáticamente por <b>equityval</b>. Cada informe es una valoración
  independiente y sector-aware; el objetivo del modelo se muestra siempre por separado del de la calle. Herramienta de análisis,
  no es recomendación de inversión ni asesoramiento financiero. Diseño: Reloj de inversión.</p></div></div>

<script src="assets/config.js?v={ver}"></script>
<script src="assets/generate.js?v={ver}"></script>
<script>
  document.querySelectorAll('.seg button').forEach(function(c){{c.addEventListener('click',function(){{
    var on=c.getAttribute('aria-pressed')!=='true'; var f=c.dataset.f;
    document.querySelectorAll('.seg button').forEach(function(o){{o.setAttribute('aria-pressed','false')}});
    c.setAttribute('aria-pressed',on?'true':'false');
    document.querySelectorAll('.rcard').forEach(function(card){{
      card.style.display=(!on||f==='all'||card.dataset.phase.indexOf(f)>-1||card.dataset.dir===f)?'':'none';}});
  }})}});
</script>
</body></html>"""

CARD = """<article class="rcard" data-phase="{phases}" data-dir="{dir}">
    <div class="head">
      <div><div class="tk"><a href="reports/{html}">{ticker}</a></div><div class="nm" title="{name}">{name}</div>
        <span class="rpill {dir}">{rating}</span></div>
      {gauge}
    </div>
    <div class="rrow"><span class="k">{tlabel}</span><span class="mono">{cur}{target}</span></div>
    <div class="rrow"><span class="k">Precio</span><span class="mono">{cur}{price}</span></div>
    <div class="rrow"><span class="k">Rentabilidad esperada</span><span class="mono {dir}">{ret}</span></div>
    <div class="rrow"><span class="k">Calle · confianza</span><span class="mono">{street} · <span class="conf-{conf}">{conf}</span></span></div>
    <div class="rfoot"><span class="dots" title="fases del ciclo">{dots}</span><span class="mono">{date}</span><span class="rlinks">{links}</span></div>
  </article>"""


def rating_dir(rating: str) -> str:
    return {"OVERWEIGHT": "up", "ADD": "up", "REDUCE": "down", "UNDERWEIGHT": "down"}.get(rating, "flat")


def wheel_with_counts(counts: dict) -> str:
    svg = charts.phase_wheel("", None, lang="es").replace(" dim", " lit2")
    pos = {"recovery": (46, 66), "overheat": (314, 66), "stagflation": (314, 316), "reflation": (46, 316)}
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
    (docs / "assets").mkdir(exist_ok=True)

    metas = []
    for jf in sorted(reports.glob("*.json")):
        try:
            m = json.loads(jf.read_text(encoding="utf-8"))
            if isinstance(m, dict) and m.get("ticker") and m.get("html"):
                metas.append(m)
        except Exception:
            pass
    metas.sort(key=lambda m: (m.get("generated_at") or m.get("date", "")), reverse=True)

    counts: dict = {}
    cards, positive, high, nr = [], 0, 0, 0
    for m in metas:
        up = m.get("upside", 0) or 0
        ret = m.get("total_return", up)
        rated = m.get("rated", True)
        rating = m.get("rating", "NOT RATED" if not rated else "")
        rdir = rating_dir(rating)
        positive += rdir == "up"
        high += m.get("confidence") == "High"
        nr += not rated
        phases = m.get("phases") or []
        if phases:
            counts[phases[0]] = counts.get(phases[0], 0) + 1
        links = [f'<a href="reports/{m["pdf"]}" download>PDF</a>' if m.get("pdf")
                 else f'<a href="reports/{m["html"]}?print=1">PDF</a>']
        if m.get("xlsx"):
            links.append(f'<a href="reports/{m["xlsx"]}">XLS</a>')
        street = m.get("street")
        cur = m.get("currency", "$")
        value = m.get("target", 0) if rated else m.get("fair_value", m.get("target", 0))
        cards.append(CARD.format(
            html=m["html"], ticker=escape(m["ticker"]), name=escape(m.get("name", "")),
            rating=escape(rating), dir=rdir, cur=cur, tlabel=("Precio objetivo 12m" if rated else "Valor indicativo"),
            target=f'{value:,.2f}' + ("" if rated else "*"), price=f'{m.get("price", 0):,.2f}',
            ret=(f"{ret*100:+.0f}%" if rated else "n/d"),
            street=(f"{cur}{street:,.2f}" if street else "n/d"), conf=m.get("confidence", "Medium"),
            phases=" ".join(phases),
            dots="".join(f'<i class="dot-{p}" title="{theme.PHASE_NAMES_ES[p][0]}"></i>' for p in phases),
            gauge=charts.mini_gauge(ret, rdir, rated, size=84), date=m.get("date", ""),
            links="".join(links)))

    if not metas:
        body = '<div class="empty">Todavía no hay informes. Usa «Generar PDF» arriba con un ticker.</div>'
        chips = ""
    else:
        body = f'<div class="grid">{"".join(cards)}</div>'
        if nr:
            body += '<p class="note">* Sin rating: se muestra un valor indicativo, no un precio objetivo.</p>'
        chips = ('<div class="seg"><button type="button" data-f="all" aria-pressed="false">Todos</button>'
                 '<button type="button" data-f="up" aria-pressed="false">Positivos</button>'
                 '<button type="button" data-f="down" aria-pressed="false">Negativos</button>'
                 + "".join(f'<button type="button" data-f="{p}" aria-pressed="false">{theme.PHASE_NAMES_ES[p][0]}</button>'
                           for p in theme.PHASE_ORDER) + "</div>")

    css = design.css("fonts/") + LIBRARY_CSS
    (docs / "assets" / "superanalyst.css").write_text(css, encoding="utf-8")
    ver = date.today().strftime("%Y%m%d") + str(len(css) % 997)
    html = PAGE.format(
        ver=ver, brand=theme.brand_mark(30), count=len(metas), updated=date.today().isoformat(),
        positive=positive, high=high, nr=nr, wheel=wheel_with_counts(counts), chips=chips, body=body)
    out = docs / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"Wrote {out} with {len(metas)} report(s)")


if __name__ == "__main__":
    main()
