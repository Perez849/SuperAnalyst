"""Shared stylesheet for the research notes and the library page (one design, one source).

Adapted from the Reloj de inversión site: cream paper, ink, one ochre accent, the four phase
colours, a sticky header, an eyebrow + serif headline rhythm and a single dark "answer" block.
`css(font_base)` returns the whole sheet as text; reports inline it (so a note is one
standalone file) and the library builder writes it to docs/assets/superanalyst.css.
"""
from __future__ import annotations

import base64
from pathlib import Path

from . import theme

_FONTS = [
    ("Fraunces", 400, "normal", "fraunces-latin-400-normal"),
    ("Fraunces", 500, "normal", "fraunces-latin-500-normal"),
    ("Fraunces", 600, "normal", "fraunces-latin-600-normal"),
    ("Fraunces", 700, "normal", "fraunces-latin-700-normal"),
    ("Fraunces", 500, "italic", "fraunces-latin-500-italic"),
    ("Inter", 400, "normal", "inter-latin-400-normal"),
    ("Inter", 500, "normal", "inter-latin-500-normal"),
    ("Inter", 600, "normal", "inter-latin-600-normal"),
    ("Inter", 700, "normal", "inter-latin-700-normal"),
    ("IBM Plex Mono", 400, "normal", "ibm-plex-mono-latin-400-normal"),
    ("IBM Plex Mono", 500, "normal", "ibm-plex-mono-latin-500-normal"),
    ("IBM Plex Mono", 600, "normal", "ibm-plex-mono-latin-600-normal"),
]


def _fonts_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "docs" / "assets" / "fonts"


def font_faces(font_base: str) -> str:
    """@font-face rules. font_base is a URL prefix, or "embed" to inline the woff2 files as
    data URIs (a self-contained file: CI artifacts, Streamlit, anything outside docs/)."""
    out = []
    for fam, wt, style, file in _FONTS:
        if font_base == "embed":
            f = _fonts_dir() / f"{file}.woff2"
            if not f.exists():
                continue
            src = f'url("data:font/woff2;base64,{base64.b64encode(f.read_bytes()).decode()}") format("woff2")'
        else:
            src = f'local("{fam}"),url("{font_base}{file}.woff2") format("woff2")'
        out.append(f'@font-face{{font-family:"{fam}";font-style:{style};font-weight:{wt};font-display:swap;src:{src}}}')
    return "\n".join(out)


def tokens_css() -> str:
    t = theme.TOKENS
    vars_ = ";".join(f"--{k.replace('_', '-')}:{v}" for k, v in t.items())
    return (f":root{{{vars_};--serif:{theme.FONT_SERIF};--sans:{theme.FONT_SANS};--mono:{theme.FONT_MONO};"
            "--r-sm:3px;--r-md:6px;--maxw:1180px;"
            "--shadow-card:0 1px 2px rgba(27,24,16,.04),0 12px 28px -18px rgba(27,24,16,.22)}")


BASE = """
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;scroll-behavior:smooth}
body{margin:0;overflow-x:clip;background:var(--paper);color:var(--ink);font-family:var(--sans);font-size:16px;
  line-height:1.6;-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility;
  -webkit-print-color-adjust:exact;print-color-adjust:exact}
::selection{background:var(--accent);color:var(--paper-raised)}
.wrap{max-width:var(--maxw);margin:0 auto;padding:0 32px}
p{margin:0} b,strong{font-weight:600} a{color:var(--accent-ink)}
h1,h2,h3,h4{font-family:var(--serif);font-weight:600;letter-spacing:-.01em;margin:0;color:var(--ink)}
code,.mono{font-family:var(--mono)} .mono{font-variant-numeric:tabular-nums}
svg text{font-family:var(--sans)}

.eyebrow{font-family:var(--mono);font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:var(--accent-ink);
  display:flex;align-items:center;gap:9px}
.eyebrow::before{content:"";width:20px;height:1px;background:var(--accent);flex:none}
.lede{color:var(--ink-soft);font-size:17px;line-height:1.65;max-width:68ch}
.cap{color:var(--ink-soft);font-size:14.5px;line-height:1.6;max-width:62ch}
.small-cap{color:var(--ink-faint);font-size:12.5px}
.muted{color:var(--ink-faint)} .up{color:var(--pos)} .down{color:var(--neg)} .flat{color:var(--ink-soft)}

/* ---------- header ---------- */
.top{position:sticky;top:0;z-index:40;background:rgba(246,242,232,.88);backdrop-filter:blur(10px) saturate(1.1);
  border-bottom:1px solid var(--line-soft)}
.top-inner{display:flex;align-items:center;justify-content:space-between;gap:24px;padding-block:15px}
.brand{display:flex;align-items:center;gap:12px;text-decoration:none;color:inherit}
.brand-mark{width:30px;height:30px;flex:none}
.brand-word{font-family:var(--serif);font-size:18px;font-weight:600;letter-spacing:-.01em;line-height:1.1}
.brand-tag{font-family:var(--mono);font-size:10.5px;letter-spacing:.06em;color:var(--ink-faint)}
.top-nav{display:flex;gap:26px;align-items:center}
.top-nav a{font-family:var(--mono);font-size:11.5px;letter-spacing:.05em;color:var(--ink-soft);text-decoration:none;text-transform:uppercase}
.top-nav a:hover{color:var(--ink)}
.pdf-btn{font:600 12px/1 var(--sans);color:var(--paper-raised);background:var(--ink);border-radius:999px;padding:9px 14px;
  text-decoration:none;white-space:nowrap;border:1px solid var(--accent);cursor:pointer}
.pdf-btn:hover{background:var(--accent)}
.top-actions{display:flex;gap:10px;align-items:center}
.ghost{font-family:var(--mono);font-size:11px;letter-spacing:.03em;background:transparent;color:var(--ink-soft);
  border:1px solid var(--line-strong);border-radius:99px;padding:6px 14px;cursor:pointer;transition:.15s;text-decoration:none;display:inline-block}
.ghost:hover{color:var(--ink);border-color:var(--ink-faint);background:var(--paper-deep)}
@media (max-width:860px){.top-nav{display:none}}

/* ---------- structure ---------- */
.section{padding:64px 0} .section.tight{padding:40px 0}
.section-head{max-width:700px;margin-bottom:30px}
.section-head h2{font-size:32px;margin:10px 0 10px;line-height:1.15}
.rule{border:0;border-top:1px solid var(--line);margin:0}
.rule-wrap{max-width:var(--maxw);margin:0 auto;padding:0 32px}

/* ---------- hero ---------- */
.hero{background:linear-gradient(180deg,var(--paper-raised),var(--paper) 70%);border-bottom:1px solid var(--line);padding:52px 0 46px}
.hero-grid{display:grid;grid-template-columns:minmax(0,1.24fr) minmax(0,1fr);gap:52px;align-items:start}
.hero-grid>*{min-width:0}
.hero-eyebrow{margin-bottom:18px}
.phase-name{font-size:clamp(32px,5vw,58px);line-height:1.04;margin:0 0 8px;letter-spacing:-.02em;overflow-wrap:break-word}
.phase-name .tk{font-family:var(--mono);font-size:.34em;letter-spacing:.04em;color:var(--ink-faint);font-weight:500;margin-left:6px}
.phase-tie{font-size:15px;font-weight:600;letter-spacing:.01em;margin:0 0 14px;padding:7px 13px;border-radius:99px;display:inline-block;
  background:rgba(184,134,59,.12);color:#8a5f23;border:1px solid rgba(184,134,59,.35)}
.phase-tie.up{background:rgba(63,107,82,.12);color:var(--rec);border-color:rgba(63,107,82,.4)}
.phase-tie.down{background:rgba(156,74,60,.1);color:var(--stag);border-color:rgba(156,74,60,.4)}
.phase-tie.flat{background:var(--paper-deep);color:var(--ink-soft);border-color:var(--line-strong)}
.phase-window{font-family:var(--mono);font-size:12.5px;color:var(--ink-faint);letter-spacing:.03em;margin-bottom:22px}
.phase-why{font-size:18px;line-height:1.62;color:var(--ink-2);max-width:56ch;margin-bottom:26px}
.phase-why b{color:var(--ink)}
.conf-block{display:flex;flex-direction:column;gap:10px;max-width:470px;margin-bottom:8px}
.conf-row{display:grid;grid-template-columns:minmax(0,170px) minmax(0,1fr) 46px;align-items:center;gap:10px;font-size:12.5px}
.conf-row .nm{color:var(--ink-soft);overflow-wrap:anywhere;min-width:0}
.conf-row.lead .nm{color:var(--ink);font-weight:600}
.conf-bar{height:7px;border-radius:99px;background:var(--paper-deep);overflow:hidden;border:1px solid var(--line-soft)}
.conf-bar i{display:block;height:100%;border-radius:99px;background:var(--accent)}
.conf-bar i.rel{background:var(--refl)} .conf-bar i.int{background:var(--rec)} .conf-bar i.sec{background:var(--over)}
.conf-val{font-family:var(--mono);text-align:right;color:var(--ink-soft);font-size:12.5px}
.conf-note{font-size:13px;color:var(--ink-soft);border-left:2px solid var(--line-strong);padding-left:13px;margin-top:14px;max-width:52ch}
.plane-card{background:var(--paper-raised);border:1px solid var(--line);border-radius:var(--r-md);padding:20px 20px 16px;box-shadow:var(--shadow-card);margin:0}
.plane-top{display:flex;justify-content:space-between;align-items:baseline;gap:12px;margin-bottom:8px}
.plane-top h3{font-size:15px}

.outlook{margin:-14px 0 0;padding:22px 26px;display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:24px;
  border:1px solid var(--line);border-radius:var(--r-md);background:var(--paper-raised);box-shadow:var(--shadow-card)}
.outlook .item dt{font-family:var(--mono);font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-faint)}
.outlook .item dd{margin:5px 0 4px;font-family:var(--mono);font-size:19px;color:var(--ink)}
.outlook .item small{display:block;color:var(--ink-soft);font-family:var(--sans);font-size:12px;line-height:1.45}

/* ---------- the dark answer block ---------- */
.buy{background:var(--ink);color:var(--paper);border-radius:var(--r-md)}
.buy-inner{padding:46px 40px}
.buy .eyebrow{color:var(--gold)} .buy .eyebrow::before{background:var(--gold)}
.buy h2{color:var(--paper-raised);font-size:30px;margin:10px 0 12px}
.buy .lede{color:rgba(251,249,243,.72)}
.buy-cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:1px;margin-top:28px;border-radius:var(--r-md);overflow:hidden}
.buy-col{background:rgba(251,249,243,.03);padding:22px 24px;border:1px solid rgba(251,249,243,.14)}
.buy-col h4{font-family:var(--mono);font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:rgba(251,249,243,.5);margin-bottom:14px;display:flex;justify-content:space-between;font-weight:500}
.buy-item{display:flex;align-items:baseline;justify-content:space-between;gap:10px;padding:10px 0;border-bottom:1px solid rgba(251,249,243,.10)}
.buy-item:last-child{border-bottom:0}
.buy-item>div{min-width:0;overflow-wrap:break-word}
.buy-item .nm{color:var(--paper-raised);font-size:14.5px}
.buy-item .wt{font-family:var(--mono);color:rgba(251,249,243,.85);font-size:13.5px;white-space:nowrap;flex:none}
.buy-item .tickers{display:block;margin-top:3px}
.tick{display:inline-block;font-family:var(--mono);font-size:10.5px;letter-spacing:.02em;color:var(--gold);background:rgba(217,185,120,.12);
  border:1px solid rgba(217,185,120,.28);border-radius:4px;padding:1.5px 6px;margin:2px 4px 0 0}
.buy-empty{color:rgba(251,249,243,.55);font-size:13.5px;padding:6px 0}
.buy-foot{margin-top:22px;font-size:12.5px;color:rgba(251,249,243,.55);border-top:1px solid rgba(251,249,243,.12);padding-top:16px;max-width:80ch}
.buy-foot b{color:rgba(251,249,243,.85)}
.buy .total{display:flex;justify-content:space-between;align-items:baseline;gap:16px;margin-top:22px;padding-top:18px;border-top:1px solid rgba(251,249,243,.2)}
.buy .total .k{font-family:var(--mono);font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:rgba(251,249,243,.55)}
.buy .total .v{font-family:var(--serif);font-size:34px;color:var(--paper-raised);font-weight:600}
.buy .total .v small{font-family:var(--mono);font-size:13px;margin-left:10px}
.buy .total .up{color:#8FC7A6} .buy .total .down{color:#E3A596}

/* ---------- cards, tables ---------- */
.card{background:var(--paper-raised);border:1px solid var(--line);border-radius:var(--r-md);box-shadow:var(--shadow-card)}
.lenses{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:14px}
.lens{background:var(--paper-raised);border:1px solid var(--line);border-radius:var(--r-md);overflow:hidden}
.lens header{padding:14px 18px;border-bottom:1px solid var(--line-soft);display:flex;justify-content:space-between;align-items:baseline;gap:10px}
.lens h4{font-family:var(--sans);font-size:14.5px;font-weight:600;letter-spacing:0}
.lens .body{padding:12px 18px 14px}
.lens .big{font-family:var(--serif);font-size:30px;font-weight:600;line-height:1.1}
.lens .rng{font-family:var(--mono);font-size:11px;color:var(--ink-faint);margin:3px 0 8px}
.lens table{font-size:12.4px}
.lens .nt{font-size:12px;color:var(--ink-soft);margin-top:8px;line-height:1.5}
table{width:100%;border-collapse:collapse;font-size:12.8px;margin:6px 0 4px}
th,td{padding:9px 12px;text-align:right;border-bottom:1px solid var(--line-soft)}
th:first-child,td:first-child{text-align:left}
thead th{background:var(--paper-deep);font-family:var(--mono);font-size:10.5px;letter-spacing:.05em;text-transform:uppercase;color:var(--ink-soft);
  border-bottom:1px solid var(--line);font-weight:500}
tbody tr:hover{background:rgba(169,117,44,.05)}
tr.total td{border-top:1px solid var(--ink);font-weight:700}
tr.grp td{background:var(--paper-deep);font-family:var(--mono);font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-faint)}
tr.hist td{background:var(--paper-deep);color:var(--ink-faint)}
tr.divider td{border-bottom:1px solid var(--accent);padding:0;height:0}
tr.off td{color:var(--ink-faint);text-decoration:line-through;text-decoration-color:var(--line-strong)}
.tblwrap{border:1px solid var(--line);border-radius:var(--r-md);background:var(--paper-raised);box-shadow:var(--shadow-card);overflow-x:auto}
.tblwrap table{margin:0}
.kv{display:flex;justify-content:space-between;padding:6px 0;font-size:12.8px;border-bottom:1px solid var(--line-soft)}
.kv .k{color:var(--ink-soft)} .kv .mono{font-weight:600}
.sidebar{background:var(--paper-raised);border:1px solid var(--line);border-radius:var(--r-md);padding:14px 18px;align-self:start;box-shadow:var(--shadow-card)}
.sidetitle{font-family:var(--mono);font-size:10px;letter-spacing:.14em;text-transform:uppercase;color:var(--accent-ink);margin-bottom:6px}
.cols{display:grid;grid-template-columns:1fr 280px;gap:34px}
.two{display:grid;grid-template-columns:1fr 1fr;gap:24px} .three{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.tag{display:inline-block;font-family:var(--mono);font-size:10px;padding:2px 8px;border-radius:99px;font-weight:600;letter-spacing:.05em;text-transform:uppercase;border:1px solid transparent}
.tag.ok,.tag.low{background:rgba(63,107,82,.12);color:var(--rec);border-color:rgba(63,107,82,.3)}
.tag.warn,.tag.high{background:rgba(156,74,60,.1);color:var(--stag);border-color:rgba(156,74,60,.3)}
.tag.med{background:rgba(184,134,59,.14);color:#8a5f23;border-color:rgba(184,134,59,.35)}
.tag.neutral{background:var(--paper-deep);color:var(--ink-soft);border-color:var(--line)}
.fam{display:inline-block;font-family:var(--mono);font-size:9.5px;letter-spacing:.08em;text-transform:uppercase;padding:1px 7px;border-radius:99px;
  border:1px solid var(--line-strong);color:var(--ink-faint);margin-left:6px}
.bar-w{display:inline-block;width:64px;height:6px;border-radius:99px;background:var(--paper-deep);border:1px solid var(--line-soft);vertical-align:middle;margin-right:8px;overflow:hidden}
.bar-w i{display:block;height:100%;background:var(--accent)}
.guard{border-left:3px solid var(--accent);background:var(--paper-deep);border-radius:3px;padding:10px 14px;margin:8px 0;font-size:13px;line-height:1.5}
.note{font-size:12.3px;color:var(--ink-faint);margin-top:8px;line-height:1.5}
.src{display:inline-block;font-family:var(--mono);font-size:8px;font-weight:600;border:1px solid currentColor;border-radius:2px;padding:0 3px;vertical-align:middle;color:var(--accent-ink)}
.exh{font-family:var(--mono);font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-faint);margin:16px 0 6px}
ul{margin:6px 0 13px;padding-left:20px} li{margin:5px 0}
.details{margin-top:22px;border:1px solid var(--line);border-radius:var(--r-md);background:var(--paper-raised)}
.details summary{padding:15px 19px;cursor:pointer;font-family:var(--mono);font-size:12px;letter-spacing:.03em;color:var(--ink-soft);list-style:none;display:flex;align-items:center;gap:8px}
.details summary::-webkit-details-marker{display:none}
.details summary::before{content:"+";font-size:15px;color:var(--accent-ink);width:14px}
.details[open] summary::before{content:"\\2013"}
.details .body{padding:0 19px 19px;font-size:13px;color:var(--ink-soft)}
.rules{margin:0;padding:0;counter-reset:r;list-style:none;display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px}
.rules li{counter-increment:r;background:var(--paper-raised);padding:18px 20px;font-size:13.3px;color:var(--ink-soft);border:1px solid var(--line);border-radius:var(--r-md);margin:0}
.rules li::before{content:counter(r,decimal-leading-zero);font-family:var(--mono);font-size:11px;color:var(--accent-ink);display:block;margin-bottom:8px;letter-spacing:.08em}
.rules b{color:var(--ink);display:block;font-family:var(--sans);font-size:14px;margin-bottom:4px}
.foot-bar{margin-top:20px;border-top:1px solid var(--line);padding:26px 0 46px;color:var(--ink-faint);font-size:12.3px}
.disclaimer{color:var(--ink-faint);max-width:760px;line-height:1.6}
.sens-wrap table.sens{table-layout:fixed;text-align:center}
table.sens td,table.sens th{text-align:center;padding:8px 4px;font-family:var(--mono);font-size:11.5px}
table.sens th{background:var(--paper-deep)}
table.sens td{border:1px solid var(--paper-raised)}
table.sens td.up2{background:var(--rec);color:#FBF9F3} table.sens td.up{background:rgba(63,107,82,.16);color:var(--rec)}
table.sens td.flat{background:var(--paper-deep);color:var(--ink-soft)} table.sens td.down{background:rgba(156,74,60,.14);color:var(--stag)}
table.sens td.down2{background:var(--stag);color:#FBF9F3}
table.sens td.base{outline:2px solid var(--ink);outline-offset:-2px;font-weight:700}

/* ---------- charts (inline SVG) ---------- */
.dial,.wheel{width:100%;height:auto;display:block}
.dial .tick{stroke:var(--line-strong);stroke-width:1} .dial .tick-major{stroke:var(--ink-faint);stroke-width:1.5}
.dial .band{fill:none;stroke-width:15;stroke-linecap:butt}
.dial .b-down2{stroke:var(--stag)} .dial .b-down{stroke:var(--stag);opacity:.42} .dial .b-flat{stroke:var(--ink-faint);opacity:.4}
.dial .b-up{stroke:var(--rec);opacity:.42} .dial .b-up2{stroke:var(--rec)}
.dial .range{fill:none;stroke:var(--accent);stroke-width:5;stroke-linecap:round}
.dial .scale{fill:var(--ink-faint);font:500 9.5px var(--mono)}
.dial .street{fill:var(--accent-ink)} .dial .street-t{fill:var(--accent-ink);font-weight:700}
.dial .hand{stroke:var(--ink);stroke-width:3.4;stroke-linecap:round}
.dial .tip{fill:var(--accent);stroke:var(--paper-raised);stroke-width:1.5}
.dial .hub-ring{fill:none;stroke:var(--ink);stroke-width:1.2} .dial .hub{fill:var(--paper-raised)}
.dial .hub-k{fill:var(--ink-faint);font:500 7.5px var(--mono);letter-spacing:.14em}
.dial .hub-v{fill:var(--ink);font:600 25px var(--serif)}
.dial .hub-r{font:600 10px var(--mono);letter-spacing:.14em}
.dial .hub-up{fill:var(--rec)} .dial .hub-down{fill:var(--stag)} .dial .hub-flat{fill:var(--ink-soft)}
.dial .hub-s{fill:var(--ink-faint);font:500 9px var(--mono)}
.wheel .seg{stroke:var(--paper-raised);stroke-width:2.5}
.wheel .seg-recovery{fill:var(--rec)} .wheel .seg-overheat{fill:var(--over)} .wheel .seg-stagflation{fill:var(--stag)} .wheel .seg-reflation{fill:var(--refl)}
.wheel .seg.lit{fill-opacity:1} .wheel .seg.lit2{fill-opacity:.55} .wheel .seg.dim{fill-opacity:.13}
.wheel .ph-n{font:600 10.5px var(--mono);letter-spacing:.08em} .wheel .ph-n.long{font-size:8.2px;letter-spacing:.02em} .wheel .ph-s,.wheel .ph-a{font:500 8.5px var(--sans)}
.wheel text.lit{fill:#FBF9F3} .wheel text.lit2{fill:var(--ink)} .wheel text.dim{fill:var(--ink-soft)}
.wheel .wheel-hub{fill:var(--paper-raised);stroke:var(--line-strong)} .wheel .wheel-arrow{fill:none;stroke:var(--accent);stroke-width:2}
.wheel .wheel-head{fill:var(--accent)} .wheel .wheel-c{fill:var(--ink-faint);font:500 8.5px var(--mono);letter-spacing:.2em}
.wheel .count{fill:var(--ink);font:600 24px var(--serif)}
.ff .grid,.mini .grid{stroke:var(--line);stroke-width:1} .mini .sep{stroke-dasharray:3 3}
.ff .axis,.mini .axis{fill:var(--ink-faint);font:500 9.5px var(--mono)}
.ff .lbl{fill:var(--ink);font:600 11.5px var(--sans)} .ff .lbl-street,.ff .lbl-target{fill:var(--accent-ink)}
.ff .sub{fill:var(--ink-faint);font:500 9.5px var(--mono)}
.ff .bar-lens{fill:var(--refl);fill-opacity:.2;stroke:var(--refl)} .ff .bar-street{fill:var(--accent);fill-opacity:.2;stroke:var(--accent)}
.ff .bar-target{fill:var(--rec);fill-opacity:.2;stroke:var(--rec)}
.ff .pt-lens{fill:var(--refl)} .ff .pt-street{fill:var(--accent)} .ff .pt-target{fill:var(--rec)}
.ff .val,.mini .val{fill:var(--ink);font:500 10.5px var(--mono)}
.ff .v-price{stroke:var(--stag);stroke-width:1.6;stroke-dasharray:5 4} .ff .v-price-t{fill:var(--stag);font:600 10px var(--mono)}
.ff .v-target{stroke:var(--rec);stroke-width:1.8} .ff .v-target-t{fill:var(--rec);font:600 10px var(--mono)}
.mini .b-pos{fill:var(--refl)} .mini .b-neg{fill:var(--stag)} .mini .b-tot{fill:var(--accent)}
.mini .b-rev{fill:var(--refl)} .mini .b-fcf{fill:var(--accent)} .mini .k-rev{fill:var(--refl)} .mini .k-fcf{fill:var(--accent)}
.mini .l-act{fill:none;stroke:var(--ink);stroke-width:2.2} .mini .l-est{fill:none;stroke:var(--accent);stroke-width:2.2;stroke-dasharray:5 3}
.mini .k-act{fill:var(--ink)} .mini .k-est{fill:var(--accent)}
.mini{width:100%;height:auto;display:block} .ff{width:100%;height:auto;display:block}
.mg{display:block}
.mgband{fill:none;stroke-width:15} .mgband.b-down2{stroke:var(--stag)} .mgband.b-down{stroke:var(--stag);opacity:.42}
.mgband.b-flat{stroke:var(--ink-faint);opacity:.4} .mgband.b-up{stroke:var(--rec);opacity:.42} .mgband.b-up2{stroke:var(--rec)}
.mghand{stroke:var(--ink);stroke-width:7;stroke-linecap:round} .mghub{fill:var(--paper-raised);stroke:var(--ink);stroke-width:2}

/* ---------- responsive / print ---------- */
@media (max-width:980px){.hero-grid,.cols,.two,.three{grid-template-columns:minmax(0,1fr)}.dial{max-width:360px;margin:auto}}
@media (max-width:640px){.wrap{padding:0 18px}.rule-wrap{padding:0 18px}.buy-inner{padding:32px 22px}.section{padding:46px 0}
  .section-head h2{font-size:25px}.conf-row{grid-template-columns:100px 1fr 42px}.pdf-btn{padding:8px 10px;font-size:11px}}
@media (prefers-reduced-motion:reduce){*{animation-duration:.001ms !important;transition-duration:.001ms !important}}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:3px}
@page{size:A4;margin:11mm 9mm}
@media print{
  *{box-shadow:none !important;backdrop-filter:none !important}
  body{font-size:11px}.top{position:static;background:none;backdrop-filter:none}.top-nav,.top-actions,.pdf-btn,.no-print{display:none !important}
  .wrap,.rule-wrap{max-width:100%;padding:0}.section{padding:26px 0}.section.tight{padding:20px 0}.hero{padding:26px 0 24px}
  .hero-grid{grid-template-columns:1fr 260px;gap:26px}.phase-name{font-size:30px}.phase-why{font-size:13px}.lede{font-size:13px}
  .buy-inner{padding:26px 24px}.buy .total .v{font-size:26px}.section-head h2{font-size:22px}
  .lens,.card,.guard,tr,svg,.sidebar,.outlook,.buy,.buy-col,.plane-card{break-inside:avoid;page-break-inside:avoid}
  thead{display:table-header-group}h2,h3,.section-head,.eyebrow,.exh{break-after:avoid;page-break-after:avoid}
  .cols{grid-template-columns:1fr 230px;gap:22px}.three{grid-template-columns:repeat(3,1fr)}
}
"""


def css(font_base: str = "../assets/fonts/") -> str:
    return "\n".join([font_faces(font_base), tokens_css(), BASE])
