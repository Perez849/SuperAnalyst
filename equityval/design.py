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

.family-w{font-family:var(--mono);font-size:11px;color:rgba(251,249,243,.5)}
.st{font-family:var(--mono);font-size:9.5px;letter-spacing:.06em;text-transform:uppercase;color:var(--gold);border:1px solid rgba(217,185,120,.35);border-radius:99px;padding:0 7px;margin-left:6px}
.st.bad{color:#E3A596;border-color:rgba(227,165,150,.4)}
.buy-item.off .nm{text-decoration:line-through;color:rgba(251,249,243,.45)}
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
.dial{width:100%;height:auto;display:block}
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
@page{size:A4;margin:8mm;background:#F6F2E8}
@media print{
  *{box-shadow:none !important;backdrop-filter:none !important}
  .top{position:static;background:none;backdrop-filter:none}.top-nav,.top-actions,.pdf-btn,.no-print{display:none !important}
  .wrap,.rule-wrap{max-width:100%;padding:0}.section{padding:26px 0}.section.tight{padding:20px 0}.hero{padding:26px 0 24px}
  .hero-grid{grid-template-columns:1fr 260px;gap:26px}.phase-name{font-size:30px}.phase-why{font-size:13px}.lede{font-size:13px}
  .buy-inner{padding:26px 24px}.buy .total .v{font-size:26px}.section-head h2{font-size:22px}
  .lens,.card,.guard,tr,svg,.sidebar,.outlook,.buy,.buy-col,.plane-card{break-inside:avoid;page-break-inside:avoid}
  thead{display:table-header-group}h2,h3,.section-head,.eyebrow,.exh{break-after:avoid;page-break-after:avoid}
  .cols{grid-template-columns:1fr 230px;gap:22px}.three{grid-template-columns:repeat(3,1fr)}
}
"""

DASH = """
/* ---------- tear sheet ---------- */
.mast{padding:30px 0 20px;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:24px;align-items:end;border-bottom:1px solid var(--line)}
.mast h1{font-size:clamp(30px,4.4vw,50px);line-height:1.04;letter-spacing:-.02em}
.mast h1 .tk{font-family:var(--mono);font-size:.32em;color:var(--ink-faint);font-weight:500;letter-spacing:.04em;margin-left:8px}
.chips{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px;align-items:center}
.chip{font-family:var(--mono);font-size:10.5px;letter-spacing:.06em;text-transform:uppercase;padding:3px 10px;border-radius:99px;border:1px solid var(--line-strong);color:var(--ink-soft)}
.chip.rating{font-weight:700;letter-spacing:.1em}
.chip.up{background:rgba(63,107,82,.12);color:var(--rec);border-color:rgba(63,107,82,.45)} .chip.down{background:rgba(156,74,60,.1);color:var(--stag);border-color:rgba(156,74,60,.45)}
.chip.flat{background:var(--paper-deep)}
.mast-r{text-align:right;font-family:var(--mono);font-size:11.5px;color:var(--ink-faint);line-height:1.7}
.mast-r b{color:var(--ink);font-size:22px;font-weight:500;font-family:var(--serif)}
.sheet{padding:22px 0 8px}
.dash{display:grid;gap:14px;margin-top:14px}
.dash>*{min-width:0}
.c{background:var(--paper-raised);border:1px solid var(--line);border-radius:var(--r-md);padding:16px 18px 14px;box-shadow:var(--shadow-card);margin:0}
.c .ct{font-family:var(--mono);font-size:10.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-faint);font-weight:500;margin:0 0 8px;display:flex;justify-content:space-between;align-items:baseline;gap:10px}
.c .ct em{font-style:normal;letter-spacing:.04em;text-transform:none;color:var(--accent-ink)}
.c .take{font-size:12.5px;color:var(--ink-soft);line-height:1.5;margin-top:8px}
.c .take b{color:var(--ink)}
.row-a{grid-template-columns:minmax(0,.95fr) minmax(0,1.3fr) minmax(0,1fr)}
.row-b{grid-template-columns:minmax(0,1.5fr) minmax(0,1fr)}
.row-c{grid-template-columns:repeat(4,minmax(0,1fr))}
.row-d{grid-template-columns:minmax(0,1.15fr) minmax(0,1fr)}
.row-e{grid-template-columns:minmax(0,1.1fr) minmax(0,1fr) minmax(0,.95fr)}
.tri{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;background:var(--line);border:1px solid var(--line);border-radius:var(--r-sm);overflow:hidden;margin-top:10px}
.tri div{background:var(--paper);padding:7px 4px;text-align:center}
.tri .k{font-family:var(--mono);font-size:9px;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-faint)}
.tri .v{font-family:var(--mono);font-size:12.5px;color:var(--ink);white-space:nowrap}
.tri .down{color:var(--stag)} .tri .up{color:var(--rec)}
.kpis{display:grid;grid-template-columns:repeat(2,1fr);gap:1px;background:var(--line);border-radius:var(--r-sm);overflow:hidden}
.kt{background:var(--paper-raised);padding:9px 12px 8px;position:relative}
.kt .k{font-family:var(--mono);font-size:9.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-faint)}
.kt .v{font-family:var(--mono);font-size:17px;color:var(--ink);line-height:1.25}
.kt .v.up{color:var(--rec)} .kt .v.down{color:var(--stag)}
.kt .s{font-size:10.5px;color:var(--ink-faint);line-height:1.3}
.kt .spark{position:absolute;right:10px;top:24px;width:52px;height:20px;opacity:.9}
.spark polyline{fill:none;stroke:var(--accent);stroke-width:1.5;stroke-linejoin:round} .spark circle{fill:var(--accent)}
.tbl-s{font-size:12px} .tbl-s td,.tbl-s th{padding:6px 8px}
.tbl-s .pt{font-weight:600}
.legend{display:flex;gap:14px;flex-wrap:wrap;font-family:var(--mono);font-size:10px;color:var(--ink-faint);margin-top:6px}
.legend i{display:inline-block;vertical-align:middle;margin-right:5px}
.legend .l-bar{width:14px;height:6px;background:var(--ink-soft);border-radius:2px}
.legend .l-ref{width:2px;height:12px;background:var(--ink)} .legend .l-peer{width:8px;height:8px;border-radius:50%;background:var(--accent)}
.legend .l-tgt{width:8px;height:8px;background:var(--refl);transform:rotate(45deg)}
ul.view{list-style:none;padding:0;margin:0}
ul.view li{padding:9px 0 9px 22px;border-bottom:1px solid var(--line-soft);position:relative;font-size:13px;line-height:1.5;margin:0}
ul.view li:last-child{border-bottom:0}
ul.view li::before{content:"";position:absolute;left:2px;top:15px;width:9px;height:9px;border-radius:50%;background:var(--accent)}
ul.view li.pos::before{background:var(--rec)} ul.view li.neg::before{background:var(--stag)} ul.view li.neu::before{background:var(--ink-faint)}
ul.view b{color:var(--ink)}
.rlist{list-style:none;padding:0;margin:0;counter-reset:rk}
.rlist li{counter-increment:rk;padding:8px 0 8px 28px;position:relative;border-bottom:1px solid var(--line-soft);font-size:12.5px;line-height:1.5;margin:0}
.rlist li:last-child{border-bottom:0}
.rlist li::before{content:counter(rk,decimal-leading-zero);position:absolute;left:0;top:9px;font-family:var(--mono);font-size:10.5px;color:var(--accent-ink)}
.scs{list-style:none;padding:0;margin:8px 0 0;display:grid;grid-template-columns:repeat(2,1fr);gap:4px 14px}
.scs li{font-size:11.5px;color:var(--ink-soft);margin:0;display:flex;justify-content:space-between;border-bottom:1px solid var(--line-soft);padding:3px 0}
.scs li b{font-family:var(--mono);font-weight:500;color:var(--ink)}
/* statements */
table.fin{font-size:12px} table.fin td,table.fin th{padding:6px 10px}
table.fin th.fc,table.fin td.fc{background:rgba(62,78,122,.055)}
table.fin thead th.fc{color:var(--refl)}
table.fin tr.sub td{color:var(--ink-faint);font-size:11px;padding-top:2px;padding-bottom:3px}
table.fin tr.sub td:first-child{padding-left:22px}
table.fin tr.b td{font-weight:600}
table.fin tr.sec td{background:var(--paper-deep);font-family:var(--mono);font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-faint);padding:6px 10px}
table.fin td.neg{color:var(--stag)}
table.fin td.spk{width:70px;padding:2px 6px;text-align:center}
.mini-t td,.mini-t th{padding:7px 10px;font-size:12.3px}
.score{display:inline-flex;align-items:baseline;gap:4px;font-family:var(--serif);font-size:34px;line-height:1;color:var(--ink)}
.score small{font-family:var(--mono);font-size:12px;color:var(--ink-faint)}
.chk{list-style:none;padding:0;margin:8px 0 0}
.chk li{display:flex;gap:9px;align-items:center;font-size:12.2px;padding:4px 0;border-bottom:1px solid var(--line-soft);margin:0}
.chk li i{width:14px;height:14px;border-radius:50%;flex:none;border:1px solid var(--line-strong);position:relative}
.chk li.y i{background:var(--rec);border-color:var(--rec)} .chk li.n i{background:var(--stag);border-color:var(--stag)} .chk li.u i{background:var(--paper-deep)}
.chk li.u{color:var(--ink-faint)}
.dp{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-top:6px;font-family:var(--mono);font-size:12px}
.dp .box{border:1px solid var(--line-strong);border-radius:var(--r-sm);padding:7px 11px;background:var(--paper);text-align:center}
.dp .box b{display:block;font-size:16px;font-weight:500;color:var(--ink)} .dp .box span{font-size:9.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-faint)}
.dp .op{color:var(--ink-faint);font-size:16px}
/* cycle */
.plane{width:100%;height:auto;display:block}
.plane .q{fill-opacity:.045} .plane .q.on{fill-opacity:.12}
.plane .q-rec{fill:var(--rec)} .plane .q-over{fill:var(--over)} .plane .q-stag{fill:var(--stag)} .plane .q-refl{fill:var(--refl)}
.plane .grid{stroke:var(--line-soft)} .plane .axis-l{stroke:var(--line-strong);stroke-width:1.2}
.plane .ql{font:600 10.5px var(--mono);letter-spacing:.02em;opacity:.6} .plane .ql.on{opacity:1} .plane .qp{font:500 11px var(--mono);opacity:.85}
.plane .ql-rec{fill:var(--rec)} .plane .ql-over{fill:var(--over)} .plane .ql-stag{fill:var(--stag)} .plane .ql-refl{fill:var(--refl)}
.plane .trail{fill:none;stroke:var(--ink-faint);stroke-width:1.3;opacity:.4}
.plane .pt-rec{fill:var(--rec)} .plane .pt-over{fill:var(--over)} .plane .pt-stag{fill:var(--stag)} .plane .pt-refl{fill:var(--refl)}
.plane .halo{fill-opacity:.1;stroke-dasharray:3 3;stroke-opacity:.55} .plane .halo-rec{fill:var(--rec);stroke:var(--rec)} .plane .halo-over{fill:var(--over);stroke:var(--over)}
.plane .halo-stag{fill:var(--stag);stroke:var(--stag)} .plane .halo-refl{fill:var(--refl);stroke:var(--refl)}
.plane .ring{fill:none;stroke-width:1.4;opacity:.6} .plane .ring-rec{stroke:var(--rec)} .plane .ring-over{stroke:var(--over)} .plane .ring-stag{stroke:var(--stag)} .plane .ring-refl{stroke:var(--refl)}
.plane .now-rec{fill:var(--rec)} .plane .now-over{fill:var(--over)} .plane .now-stag{fill:var(--stag)} .plane .now-refl{fill:var(--refl)}
.plane .axis{fill:var(--ink-faint);font:500 10px var(--mono)}
.edge .axis-l{stroke:var(--line-strong)} .edge .lbl{fill:var(--ink-soft);font:500 11.5px var(--sans)} .edge .lbl.on{fill:var(--accent-ink);font-weight:700}
.edge .sub{fill:var(--ink-faint);font:500 9.5px var(--mono)} .edge .val{fill:var(--ink);font:500 10.5px var(--mono)} .edge .axis{fill:var(--ink-faint);font:500 9.5px var(--mono)}
.edge .eb-raw{fill-opacity:.25} .edge .eb-shr{fill-opacity:.95}
.edge .b-rec{fill:var(--rec)} .edge .b-over{fill:var(--over)} .edge .b-stag{fill:var(--stag)} .edge .b-refl{fill:var(--refl)}
.edge .cur-band{fill:none;stroke:var(--accent);stroke-dasharray:3 3;stroke-width:1}
.pbars{display:flex;flex-direction:column;gap:7px;margin:8px 0}
.pb{display:grid;grid-template-columns:118px 1fr 40px;gap:9px;align-items:center;font-size:12px;color:var(--ink-soft)}
.pb.on{color:var(--ink);font-weight:600} .pb .bar{height:7px;border-radius:99px;background:var(--paper-deep);border:1px solid var(--line-soft);overflow:hidden}
.pb .bar i{display:block;height:100%;border-radius:99px} .pb .v{font-family:var(--mono);text-align:right;font-size:12px}
.c-rec{background:var(--rec)} .c-over{background:var(--over)} .c-stag{background:var(--stag)} .c-refl{background:var(--refl)}
.pill-phase{display:inline-block;font-family:var(--mono);font-size:11px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;padding:3px 11px;border-radius:99px;color:#FBF9F3}
.pill-phase.p-rec{background:var(--rec)} .pill-phase.p-over{background:var(--over)} .pill-phase.p-stag{background:var(--stag)} .pill-phase.p-refl{background:var(--refl)}
/* generic chart classes */
.wf-total{fill:var(--ink)} .wf-up{fill:var(--rec)} .wf-down{fill:var(--stag)} .wf-link{stroke:var(--ink-faint);stroke-dasharray:2 2}
.mini .cb-hist{fill:var(--refl)} .mini .cb-fc{fill:var(--refl);fill-opacity:.28;stroke:var(--refl);stroke-dasharray:3 2}
.mini .cb-hist.neg{fill:var(--stag)} .mini .cb-fc.neg{fill:var(--stag);stroke:var(--stag)}
.mini .cl-line{fill:none;stroke:var(--accent);stroke-width:2} .mini .cl-dot{fill:var(--accent)} .mini .ax2{fill:var(--accent-ink)}
.mini .k-bar{fill:var(--refl)} .mini .k-line{fill:var(--accent)}
.mini .s-ocf{fill:var(--refl)} .mini .s-capex{fill:var(--stag)} .mini .s-fcf{fill:var(--rec)}
.mini .k-s-ocf{fill:var(--refl)} .mini .k-s-capex{fill:var(--stag)} .mini .k-s-fcf{fill:var(--rec)}
.mini .lc-roic{fill:none;stroke:var(--rec);stroke-width:2.2} .mini .lc-roic-dot{fill:var(--rec)}
.mini .lc-wacc{fill:none;stroke:var(--stag);stroke-width:1.8;stroke-dasharray:5 3} .mini .lc-wacc-dot{fill:var(--stag)}
.mini .lc-roe{fill:none;stroke:var(--refl);stroke-width:2} .mini .lc-roe-dot{fill:var(--refl)}
.mini .k-lc-roic{fill:var(--rec)} .mini .k-lc-wacc{fill:var(--stag)} .mini .k-lc-roe{fill:var(--refl)}
.mini .lc-fill{fill:var(--rec);fill-opacity:.1}
.mini .sub{fill:var(--ink-faint);font:500 9px var(--mono)} .mini .lbl2{fill:var(--ink-soft);font:600 8.5px var(--mono);letter-spacing:.08em}
.mini .sc-range{fill:var(--paper-deep);stroke:var(--line-strong)} .mini .sc-bear{fill:var(--stag)} .mini .sc-base{fill:var(--ink)} .mini .sc-bull{fill:var(--rec)}
.mini .v-price{stroke:var(--stag);stroke-width:1.5;stroke-dasharray:4 3} .mini .v-price-t{fill:var(--stag);font:600 9.5px var(--mono)}
.bul .lbl{fill:var(--ink);font:600 11px var(--sans)} .bul .sub{fill:var(--ink-faint);font:500 9px var(--mono)} .bul .val{fill:var(--ink);font:500 11px var(--mono)}
.bul-bg{fill:var(--paper-deep)} .bul-bar{fill:var(--ink-soft)} .bul-bar.b-cheap{fill:var(--rec)} .bul-bar.b-rich{fill:var(--stag)}
.bul-ref{stroke:var(--ink);stroke-width:1.8} .bul-peer{fill:var(--accent)} .bul-tgt{fill:var(--refl)} .bul{width:100%;height:auto;display:block}
.radar{width:100%;height:auto;display:block;max-width:320px;margin:0 auto}
.radar .rg{fill:none;stroke:var(--line)} .radar .rpoly{fill:var(--accent);fill-opacity:.2;stroke:var(--accent);stroke-width:2} .radar .rdot{fill:var(--accent)}
.radar .rl{font:600 10px var(--sans);fill:var(--ink)} .radar .rv{font:500 10px var(--mono);fill:var(--accent-ink)}
.px .px-line{fill:none;stroke:var(--ink);stroke-width:1.5} .px .px-s10{fill:none;stroke:var(--refl);stroke-width:1.1} .px .px-s40{fill:none;stroke:var(--over);stroke-width:1.2}
.px .px-cone{fill:var(--rec);fill-opacity:.12} .px .px-tgt{stroke:var(--rec);stroke-width:2;stroke-dasharray:4 3}
.px .val.up{fill:var(--rec)} .px .val.down{fill:var(--stag)} .px .val.tg{fill:var(--ink);font-weight:700}
.px .k-px{fill:var(--ink)} .px .k-s10{fill:var(--refl)} .px .k-s40{fill:var(--over)}
.meter .m-bad{fill:#E5BDB3} .meter .m-mid{fill:#EAD9AE} .meter .m-good{fill:#BBD5C3} .meter .m-mark{fill:var(--ink);stroke:var(--ink);stroke-width:1.6}
.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:1px;background:var(--line);border:1px solid var(--line);border-radius:var(--r-sm);overflow:hidden}
.metrics>div{background:var(--paper-raised);padding:9px 12px}
.metrics .k{font-family:var(--mono);font-size:9.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-faint)}
.metrics .v{font-family:var(--mono);font-size:15px}
.cyc-t td,.cyc-t th{padding:6px 6px;font-size:11px}
.fin3{grid-template-columns:minmax(0,1.35fr) minmax(0,1fr) minmax(0,1fr)}
.fin3 .metrics{grid-template-columns:repeat(2,1fr)} .fin3 .metrics>div:last-child:nth-child(odd){grid-column:1/-1}
.fin3 .mini-t td,.fin3 .mini-t th{padding:6px 7px;font-size:11.5px}
@media (max-width:1100px){.fin3{grid-template-columns:minmax(0,1fr)}}
.sheet-title{display:flex;align-items:baseline;justify-content:space-between;gap:20px;margin:0 0 4px}
.sheet-title h2{font-size:30px}
@media (max-width:1100px){.row-a,.row-b,.row-d,.row-e{grid-template-columns:minmax(0,1fr)}.row-c{grid-template-columns:repeat(2,minmax(0,1fr))}.mast{grid-template-columns:1fr}.mast-r{text-align:left}}
@media (max-width:640px){.row-c{grid-template-columns:minmax(0,1fr)}.kpis{grid-template-columns:repeat(2,1fr)}}
@media print{
  html,body{-webkit-print-color-adjust:exact;print-color-adjust:exact}
  /* the two tear-sheet pages are laid out at screen width (~1100px) and scaled onto one A4 page each;
     prose sections use a gentler scale so body text stays readable */
  .sheet{zoom:.665;padding:0}.section{zoom:.75}
  .row-a{grid-template-columns:.95fr 1.3fr 1fr}.row-b{grid-template-columns:1.5fr 1fr}.row-c{grid-template-columns:repeat(4,1fr)}
  .row-d{grid-template-columns:1.15fr 1fr}.row-e{grid-template-columns:1.1fr 1fr .95fr}.mast{grid-template-columns:1fr auto}
  .fin3{grid-template-columns:1.35fr 1fr 1fr}.lenses{grid-template-columns:repeat(3,minmax(0,1fr))}
  #dcf{zoom:.55}#risks{zoom:.68}#financials{zoom:.69}#thesis{zoom:.68}#financials .fin3,#dcf .c,.lens{break-inside:avoid}
  .mast{padding:6px 0 14px}.dash{margin-top:12px}
  .c{break-inside:avoid;page-break-inside:avoid}
  .pagebreak{break-before:page;page-break-before:always}
  .kpis,.kt,.c,.fin,.mini-t{break-inside:avoid}
  table.fin td,table.fin th{padding:5px 8px}
  .section-head{margin-bottom:14px}
}
"""


PAGES = """
/* ---------- analyst document: fixed A4 pages, prose column + exhibit column ---------- */
[hidden]{display:none !important}
body.doc{background:#E7DFCB;font-family:var(--sans);-webkit-font-smoothing:antialiased}
.doc .top{position:sticky;top:0}
.pages{padding:26px 0 46px;transform-origin:0 0}
.pg{width:210mm;height:297mm;margin:0 auto 22px;background:var(--paper);box-shadow:0 1px 2px rgba(27,24,16,.14),0 12px 38px rgba(27,24,16,.14);
  padding:10mm 12mm 8mm;box-sizing:border-box;display:grid;grid-template-rows:auto auto minmax(0,1fr) auto auto;position:relative;overflow:hidden;
  break-after:page;page-break-after:always}
.pg:last-child{break-after:auto;page-break-after:auto}
.ph{display:flex;justify-content:space-between;align-items:center;gap:12px;font:500 8px/1 var(--mono);letter-spacing:.09em;text-transform:uppercase;
  color:var(--ink-soft);padding-bottom:6px;border-bottom:1.5px solid var(--ink)}
.ph .ph-l{display:flex;align-items:center;gap:7px}.ph .ph-l svg{width:15px;height:15px}.ph .ph-l b{font-family:var(--serif);font-size:11px;letter-spacing:0;text-transform:none;color:var(--ink);font-weight:600}
.ph .ph-r{display:flex;gap:9px;align-items:center}.ph .ph-r b{color:var(--ink);font-weight:600}
.ph .rt{font-style:normal;font-weight:700;padding:2px 7px;border-radius:99px;border:1px solid var(--line-strong);letter-spacing:.1em}
.ph .rt.up{background:rgba(63,107,82,.12);color:var(--rec);border-color:rgba(63,107,82,.45)}.ph .rt.down{background:rgba(156,74,60,.1);color:var(--stag);border-color:rgba(156,74,60,.45)}
.pt{margin:11px 0 0}
.pt .kick{font:600 8px/1 var(--mono);letter-spacing:.16em;text-transform:uppercase;color:var(--accent-ink)}
.pt h2{font:600 23px/1.12 var(--serif);letter-spacing:-.012em;margin:5px 0 0;color:var(--ink)}
.pt .sub{font:400 11px/1.45 var(--sans);color:var(--ink-soft);margin:6px 0 0;max-width:92%}
.pbody{display:grid;grid-template-columns:minmax(0,1.62fr) minmax(0,1fr);gap:18px;min-height:0;margin-top:11px}
.pbody.one{grid-template-columns:minmax(0,1fr)}
.pmain{min-height:0;overflow:hidden;font-size:var(--fs,10.3px);line-height:var(--lh,1.5);color:var(--ink-2)}
.pm-in>.sg:first-child>:first-child{margin-top:0}.sg{break-inside:avoid;display:flow-root}
.pm-in p{margin:0 0 var(--pgap,.65em);text-align:justify;hyphens:auto;-webkit-hyphens:auto;orphans:2;widows:2}
.pm-in p b{font-weight:600;color:var(--ink)}.pm-in p i{font-style:italic}
.pm-in p.lead{font-size:1.1em;line-height:1.46;color:var(--ink)}
.pm-in h3{font:600 1.24em/1.2 var(--serif);letter-spacing:-.005em;color:var(--ink);margin:.45em 0 .38em;padding-top:.55em;border-top:1px solid var(--line)}
.pm-in>.sg:first-child>h3:first-child{border-top:0;padding-top:0;margin-top:0}
.pm-in ul.bl{margin:.15em 0 var(--pgap,.65em);padding:0;list-style:none}
.pm-in ul.bl li{position:relative;padding-left:1.1em;margin:0 0 .38em;text-align:left}
.pm-in ul.bl li::before{content:"";position:absolute;left:.12em;top:.58em;width:.36em;height:.36em;background:var(--accent)}
.pm-in .callout{margin:.2em 0 var(--pgap,.75em);padding:.65em .85em .5em;background:var(--paper-raised);border:1px solid var(--line);border-left:3px solid var(--accent)}
.pm-in .cols-2{column-count:2;column-gap:18px}.pg.cols2 .pm-in{column-count:2;column-gap:20px}
.pm-in .callout .ct{font:600 .7em/1 var(--mono);letter-spacing:.13em;text-transform:uppercase;color:var(--accent-ink);margin-bottom:.45em}
.pm-in .callout ul.bl{margin:0}.pm-in .callout ul.bl li:last-child{margin-bottom:.1em}
.pm-in .tiles{display:grid;grid-template-columns:repeat(var(--n,4),1fr);gap:1px;background:var(--line);border:1px solid var(--line);margin:.1em 0 var(--pgap,.75em)}
.pm-in .tiles>div{background:var(--paper-raised);padding:.5em .6em .45em}
.pm-in .tiles .k{font:500 .62em/1 var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--ink-faint)}
.pm-in .tiles .v{font:600 1.45em/1.15 var(--serif);color:var(--ink);margin-top:.15em}.pm-in .tiles .v.up{color:var(--rec)}.pm-in .tiles .v.down{color:var(--stag)}
.pm-in .tiles .s{font:400 .68em/1.2 var(--sans);color:var(--ink-faint)}
.pm-in .pull{margin:.3em 0 var(--pgap,.8em);padding:.1em 0 .1em .9em;border-left:3px solid var(--accent);font:italic 500 1.28em/1.3 var(--serif);color:var(--ink)}
.pside{min-height:0;overflow:hidden}
.ps-in{display:flex;flex-direction:column;gap:9px}
.ex{background:var(--paper-raised);border:1px solid var(--line);border-top:2px solid var(--ink);padding:6px 8px 5px;break-inside:avoid}
.ex-h{display:flex;gap:6px;align-items:baseline;font:600 7.6px/1.3 var(--mono);letter-spacing:.07em;text-transform:uppercase;color:var(--ink);margin-bottom:5px}
.ex-h .ex-n{color:var(--accent-ink);white-space:nowrap}
.ex-b svg{display:block;width:100%;height:auto}
.ex-b svg.mini .axis{font:500 7.3px var(--mono)}.ex-b svg.mini .val{font:500 7.8px var(--mono)}.ex-b svg.mini .sub{font:500 7px var(--mono)}.ex-b svg.mini .lbl2{font:600 7.2px var(--mono)}
.ex-b svg.mini .v-price-t{font:600 7px var(--mono)}.ex-b svg.mini text.hub-v{font-size:25px}
.ex-b table.sens{font:500 8px var(--mono);width:100%}.ex-b table.sens th,.ex-b table.sens td{padding:3.4px 1px;font-size:8px;text-align:center}.ex-b table.sens thead th{font-size:7px;letter-spacing:.02em}.ex-b .sens-wrap{overflow:hidden}
.ex-b svg.radar .rl{font:600 8px var(--sans);fill:var(--ink)}.ex-b svg.radar .rv{font:500 8px var(--mono);fill:var(--accent-ink)}
.ex-b .legend{margin-top:3px;font-size:7.5px;gap:8px}
.ex-b .take{font:400 8.4px/1.4 var(--sans);color:var(--ink-soft);margin:5px 0 0}
.ex-s{font:italic 400 6.9px/1.35 var(--sans);color:var(--ink-faint);margin-top:4px}
.xt{width:100%;border-collapse:collapse;font:500 8.3px/1.3 var(--mono);color:var(--ink)}
.xt th{font:600 7px/1.2 var(--mono);letter-spacing:.06em;text-transform:uppercase;color:var(--ink-faint);text-align:right;padding:2px 3px 3px;border-bottom:1px solid var(--ink);white-space:nowrap}
.xt td{padding:2.5px 3px;border-bottom:1px solid var(--line-soft);text-align:right;white-space:nowrap}
.xt th:first-child,.xt td:first-child{text-align:left;font-family:var(--sans);white-space:normal}
.xt td:first-child{font-weight:500;font-size:8.3px}
.xt tr.b td{font-weight:700}.xt tr.sub td{color:var(--ink-faint);font-size:7.8px}.xt tr.sub td:first-child{padding-left:9px}
.xt tr.sec td{font:600 7px/1 var(--mono);letter-spacing:.1em;text-transform:uppercase;background:var(--paper-deep);color:var(--ink-soft);padding:3px}
.xt tr.tot td{border-top:1px solid var(--ink);font-weight:700}
.xt .fc{background:rgba(62,78,122,.07)}.xt .up{color:var(--rec)}.xt .down,.xt .neg{color:var(--stag)}.xt td.l{text-align:left;font-family:var(--sans);white-space:normal}.xt td.w{white-space:normal;word-break:break-word}
.xt.app{font-size:9.5px}.xt.app td{padding:3.7px 4px}.xt.app td:first-child{font-size:9.5px}.xt.wide{font-size:8.9px}.xt.wide th{font-size:7.4px}.xt.wide td:first-child{font-size:8.9px}
.xt .tag{font:600 6.8px var(--mono);padding:1px 5px;border-radius:99px;border:1px solid var(--line-strong);letter-spacing:.05em;text-transform:uppercase}
.xt .tag.ok{color:var(--rec);border-color:rgba(63,107,82,.45);background:rgba(63,107,82,.1)}.xt .tag.med{color:var(--accent-ink);border-color:rgba(169,117,44,.5);background:rgba(169,117,44,.1)}
.xt .tag.warn,.xt .tag.high{color:var(--stag);border-color:rgba(156,74,60,.45);background:rgba(156,74,60,.09)}.xt .tag.low{color:var(--rec);border-color:rgba(63,107,82,.45)}
.xk{display:grid;grid-template-columns:1fr 1fr;gap:1px;background:var(--line);border:1px solid var(--line);margin-top:2px}
.xk>div{background:var(--paper);padding:4px 6px}.xk .k{font:500 6.8px/1.1 var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--ink-faint)}.xk .v{font:500 11px/1.25 var(--mono);color:var(--ink)}
.ex .chk{list-style:none;margin:4px 0 0;padding:0}.ex .chk li{display:flex;gap:6px;align-items:center;padding:1.8px 0;border-bottom:1px solid var(--line-soft);font:400 8.3px/1.35 var(--sans);margin:0;color:var(--ink)}
.ex .chk li i{width:7px;height:7px;border-radius:50%;background:var(--ink-faint);flex:none}.ex .chk li.y i{background:var(--rec)}.ex .chk li.n i{background:var(--stag)}.ex .chk li.u{color:var(--ink-soft)}
.sb{display:flex;height:13px;border:1px solid var(--line-strong);margin:2px 0 5px}.sb span{display:block;height:100%}.sb .s1{background:var(--refl)}.sb .s2{background:var(--rec)}.sb .s3{background:var(--over)}.sb .s4{background:var(--ink-faint)}
.sbl{display:flex;gap:10px;flex-wrap:wrap;font:500 7.4px var(--mono);color:var(--ink-soft)}.sbl i{display:inline-block;width:7px;height:7px;margin-right:4px;vertical-align:baseline}
.bigscore{font:600 26px/1 var(--serif);color:var(--ink)}.bigscore small{font:500 8px var(--mono);color:var(--ink-faint);margin-left:6px;letter-spacing:.05em}
.pband{margin-top:9px}.pband .ex{padding:6px 9px 5px}
.pband.two{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.pf{display:flex;justify-content:space-between;align-items:flex-end;gap:14px;margin-top:8px;padding-top:5px;border-top:1px solid var(--line-strong);font:400 6.8px/1.4 var(--sans);color:var(--ink-faint)}
.pf .pn{font:600 8px var(--mono);color:var(--ink);white-space:nowrap}.pf .pf-src{max-width:78%}
/* cover */
.cv{margin-top:12px;display:grid;grid-template-columns:minmax(0,1fr) 62mm;gap:16px;align-items:end;padding-bottom:10px;border-bottom:1px solid var(--line-strong)}
.cv .kick{font:600 8px/1 var(--mono);letter-spacing:.16em;text-transform:uppercase;color:var(--accent-ink)}
.cv h1{font:600 31px/1.04 var(--serif);letter-spacing:-.018em;margin:6px 0 0;color:var(--ink)}.cv h1 .tk{font:500 11px var(--mono);color:var(--ink-faint);letter-spacing:.06em;margin-left:8px}
.cv .hl{font:italic 500 16.5px/1.28 var(--serif);color:var(--ink-soft);margin:8px 0 0}
.cv .rbox{border:1px solid var(--line-strong);background:var(--paper-raised);padding:8px 10px 7px}
.cv .rbox .rt{display:inline-block;font:700 11px/1 var(--mono);letter-spacing:.14em;padding:4px 10px;border-radius:99px;border:1px solid var(--line-strong)}
.cv .rbox .rt.up{background:rgba(63,107,82,.12);color:var(--rec);border-color:rgba(63,107,82,.5)}.cv .rbox .rt.down{background:rgba(156,74,60,.1);color:var(--stag);border-color:rgba(156,74,60,.5)}
.cv .rbox .row{display:flex;justify-content:space-between;font:500 9px/1.7 var(--mono);color:var(--ink-soft);border-bottom:1px solid var(--line-soft)}.cv .rbox .row:last-child{border:0}
.cv .rbox .row b{color:var(--ink);font-weight:600}.cv .rbox .row b.up{color:var(--rec)}.cv .rbox .row b.down{color:var(--stag)}
.cv .rbox .pt-big{font:600 25px/1.05 var(--serif);color:var(--ink);margin:6px 0 3px}.cv .rbox .pt-big small{font:500 9px var(--mono);color:var(--ink-faint);letter-spacing:.08em;margin-left:5px}
/* the dark answer block, scaled for a page */
.ans{background:#1D1A12;color:#F4EFE3;padding:9px 11px 8px;margin:.2em 0 var(--pgap,.75em)}
.ans .k{font:500 6.8px/1 var(--mono);letter-spacing:.14em;text-transform:uppercase;color:#D9B978}
.ans .big{font:600 1.9em/1.1 var(--serif);color:#FBF9F3;margin-top:3px}
.ans .row{display:flex;justify-content:space-between;gap:12px}.ans .row>div:last-child{text-align:right}
.ans .ar{font:400 .8em/1.45 var(--sans);color:rgba(244,239,227,.78);margin-top:6px;padding-top:6px;border-top:1px solid rgba(244,239,227,.18)}
/* compact charts */
svg.cs{display:block;width:100%;height:auto}svg.cs text{font-family:var(--sans)}
svg.cs .t{font:600 8.3px var(--sans);fill:var(--ink)}svg.cs .t-street,svg.cs .t-target{fill:var(--accent-ink)}
svg.cs .s{font:500 7px var(--mono);fill:var(--ink-faint)}svg.cs .v{font:600 8px var(--mono);fill:var(--ink)}
svg.cs .ax{font:500 6.8px var(--mono);fill:var(--ink-faint)}svg.cs .track{fill:var(--paper-deep)}
svg.cs .grid{stroke:var(--line);stroke-width:1}svg.cs .lk{stroke:var(--ink-faint);stroke-dasharray:2 2}
svg.cs .bar-lens{fill:rgba(62,78,122,.26);stroke:var(--refl);stroke-width:.8}svg.cs .bar-street{fill:rgba(169,117,44,.28);stroke:var(--accent);stroke-width:.8}
svg.cs .bar-target{fill:rgba(63,107,82,.28);stroke:var(--rec);stroke-width:.8}
svg.cs .pt-lens{fill:var(--refl)}svg.cs .pt-street{fill:var(--accent)}svg.cs .pt-target{fill:var(--rec)}
svg.cs .v-price{stroke:var(--stag);stroke-width:1.2;stroke-dasharray:3 3}svg.cs .v-price-t{fill:var(--stag);font:600 7px var(--mono)}
svg.cs .v-target{stroke:var(--rec);stroke-width:1.3}
svg.cs .cur{fill:rgba(169,117,44,.07);stroke:var(--accent);stroke-dasharray:3 2;stroke-width:.9}
svg.cs .ph-raw{fill-opacity:.25}svg.cs .ph-shr{fill-opacity:.95}
svg.cs .ph-rec{fill:var(--rec)}svg.cs .ph-over{fill:var(--over)}svg.cs .ph-stag{fill:var(--stag)}svg.cs .ph-refl{fill:var(--refl)}
@media print{
  html,body{background:var(--paper) !important;-webkit-print-color-adjust:exact;print-color-adjust:exact}
  body.doc{background:var(--paper)}.top{display:none !important}
  .pages{padding:0;transform:none !important;width:auto !important;margin:0 !important}.pg{margin:0;box-shadow:none}
}
@page{size:A4;margin:0;background:#F6F2E8}
"""


def css(font_base: str = "../assets/fonts/", doc: bool = False) -> str:
    parts = [font_faces(font_base), tokens_css(), BASE, DASH]
    if doc:
        parts.append(PAGES)
    return "\n".join(parts)
