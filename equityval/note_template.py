"""The research-note HTML template (Jinja). All numbers arrive pre-formatted from report.py."""
from jinja2 import Template

TEMPLATE = Template(r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ d.ticker }} — Equity Research · SuperAnalyst</title>
<style>{{ design_css|safe }}</style></head><body>
{%- macro head(eyebrow, title, lede=None) -%}
<div class="section-head"><div class="eyebrow">{{ eyebrow }}</div><h2>{{ title }}</h2>{% if lede %}<p class="cap">{{ lede }}</p>{% endif %}</div>
{%- endmacro -%}
{%- macro table(t, cls='') -%}
<div class="tblwrap"><table class="fin {{ cls }}"><thead><tr><th>{{ t.unit_label }}</th>{% for c in t.cols %}<th class="{{ 'fc' if loop.index0 >= t.n_hist else '' }}">{{ c }}</th>{% endfor %}<th></th></tr></thead><tbody>
{% for sec in t.sections %}<tr class="sec"><td colspan="{{ t.cols|length + 2 }}">{{ sec.title }}</td></tr>
{% for r in sec.rows %}<tr class="{{ 'sub' if r.sub }}{{ ' b' if r.bold }}"><td>{{ r.label }}</td>{% for c in r.cells %}<td class="{{ c.cls }}{{ ' fc' if loop.index0 >= t.n_hist }} mono">{{ c.t }}</td>{% endfor %}<td class="spk">{{ r.spark|safe }}</td></tr>{% endfor %}
{% endfor %}</tbody></table></div>
{%- endmacro -%}

<header class="top"><div class="wrap top-inner">
  <a class="brand" href="{{ library_href or '#top' }}">{{ brand|safe }}<span><span class="brand-word">SuperAnalyst</span><br><span class="brand-tag">VALUATION · LENSES · EVIDENCE</span></span></a>
  <nav class="top-nav"><a href="#top">Summary</a><a href="#verdict">Verdict</a><a href="#financials">Financials</a>{% if dcf %}<a href="#dcf">DCF</a>{% endif %}{% if cycle %}<a href="#cycle">Cycle</a>{% endif %}<a href="#risks">Risks</a></nav>
  <div class="top-actions">{% if library_href %}<a class="ghost" href="{{ library_href }}">← Library</a>{% endif %}<button class="pdf-btn" type="button" onclick="window.print()">⬇ Save as PDF</button></div>
</div></header>

<!-- ============================ SHEET 1 · SUMMARY ============================ -->
<section class="sheet" id="top"><div class="wrap">
  <div class="mast">
    <div>
      <div class="eyebrow">Independent valuation · {{ d.sector }}{% if d.industry %} · {{ d.industry }}{% endif %}</div>
      <h1>{{ d.name|e }} <span class="tk">{{ d.ticker }}</span></h1>
      <div class="chips"><span class="chip rating {{ rating_dir }}">{{ rating }}</span><span class="chip">{{ spec.label }}</span>
        <span class="chip">Confidence · {{ tr.confidence }}</span><span class="chip">12-month horizon</span><span class="chip">{{ report_date }}</span></div>
    </div>
    <div class="mast-r"><div>Price</div><b>{{ fmt_ps(d.price) }}</b><div>{{ d.provider }}</div></div>
  </div>

  <div class="dash row-a">
    <figure class="c"><div class="ct"><span>12-month price target</span><em>{{ rating }}</em></div>
      {{ clock_svg|safe }}
      <div class="tri"><div><div class="k">Bear</div><div class="v down">{{ fmt_ps(tr.bear) }}</div></div>
        <div><div class="k">{{ 'Target' if tr.rated else 'Indicative' }}</div><div class="v">{{ fmt_ps(tr.target if tr.rated else tr.fair_value) }}</div></div>
        <div><div class="k">Bull</div><div class="v up">{{ fmt_ps(tr.bull) }}</div></div></div>
    </figure>
    <div class="c"><div class="ct"><span>From price to target</span><em>{{ spct(tr.upside,0) if tr.rated else 'not rated' }}</em></div>
      {{ bridge_svg|safe }}
      <p class="take">{{ bridge_take|safe }}</p></div>
    <div class="c"><div class="ct"><span>Key figures</span><em>{{ d.currency }}</em></div>
      <div class="kpis">{% for k in kpis %}<div class="kt"><div class="k">{{ k.label }}</div><div class="v {{ k.tone or '' }}">{{ k.text }}</div><div class="s">{{ k.sub }}</div>{{ k.spark|safe }}</div>{% endfor %}</div></div>
  </div>

  <div class="dash row-b">
    <div class="c"><div class="ct"><span>Value per share by lens</span><em>fair value today · range</em></div>
      {{ ff_svg|safe }}
      <p class="take">{{ ff_take|safe }}</p></div>
    <div class="c"><div class="ct"><span>Scenarios · 12 months</span><em>E[target] {{ fmt_ps(scen.expected) }} ({{ spct(scen.expected_ret,0) }})</em></div>
      {{ scen_svg|safe }}
      <table class="tbl-s"><thead><tr><th>Case</th><th>Prob.</th><th>Target</th><th>Return</th>{% if scen.has_dcf %}<th>DCF</th>{% endif %}</tr></thead><tbody>
        {% for r in scen.rows %}<tr><td>{{ r.name }}</td><td class="mono">{{ '%d%%'|format(r.p*100) }}</td><td class="mono pt">{{ fmt_ps(r.pt) }}</td><td class="mono {{ 'up' if r.ret>=0 else 'down' }}">{{ spct(r.ret,0) }}</td>{% if scen.has_dcf %}<td class="mono">{{ fmt_ps(r.dcf) if r.dcf else '—' }}</td>{% endif %}</tr>{% endfor %}
      </tbody></table>
      <p class="take">{{ scen_take|safe }}</p></div>
  </div>

  <div class="dash row-c">
    <div class="c"><div class="ct"><span>Revenue &amp; EBIT margin</span><em>{{ ft.unit_label }}</em></div>{{ combo_svg|safe }}<p class="take">{{ combo_take|safe }}</p></div>
    <div class="c"><div class="ct"><span>EPS · actual &amp; est.</span><em>{{ d.currency }}/share</em></div>{{ eps_svg|safe }}<p class="take">{{ eps_take|safe }}</p></div>
    <div class="c"><div class="ct"><span>Cash generation</span><em>{{ ft.unit_label }}</em></div>{{ cf_svg|safe }}<p class="take">{{ cf_take|safe }}</p></div>
    <div class="c"><div class="ct"><span>ROIC vs WACC</span><em>+ ROE</em></div>{{ roic_svg|safe }}<p class="take">{{ roic_take|safe }}</p></div>
  </div>
</div></section>

<!-- ============================ SHEET 2 · SUMMARY II ============================ -->
<section class="sheet pagebreak" id="summary2"><div class="wrap">
  <div class="dash row-d" style="margin-top:0">
    <div class="c"><div class="ct"><span>Valuation vs the sector</span><em>{{ ref.label }} reference</em></div>
      {{ bullets_svg|safe }}
      <div class="legend"><span><i class="l-bar"></i>company today</span><span><i class="l-ref"></i>sector reference</span>{% if has_peers %}<span><i class="l-peer"></i>peer median</span>{% endif %}<span><i class="l-tgt"></i>at our target</span></div>
      <div class="tblwrap" style="margin-top:10px"><table class="tbl-s"><thead><tr><th>Multiple</th><th>Today</th><th>Sector</th><th>Premium</th><th>At target</th></tr></thead><tbody>
        {% for m in mult_rows %}<tr><td>{{ m.metric }}</td><td class="mono">{{ m.now }}</td><td class="mono">{{ m.ref }}</td><td class="mono {{ m.tone }}">{{ m.prem }}</td><td class="mono">{{ m.target }}</td></tr>{% endfor %}
      </tbody></table></div>
      <p class="take">{{ mult_take|safe }}</p></div>
    <div class="c"><div class="ct"><span>Reloj de inversión</span><em>{% if cycle %}{{ cycle.asof }} · {{ cycle.fetched }}{% else %}not available{% endif %}</em></div>
      {% if cycle %}
      <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:6px"><span class="pill-phase p-{{ cycle.cls }}">{{ cycle.phase }}</span><span class="small-cap">{{ cycle.phase_en }} · {{ cycle.strength_en }} signal</span></div>
      {{ plane_svg|safe }}
      <p class="take">{{ cycle.summary|safe }}</p>
      {% else %}<p class="take">The Reloj de inversión data could not be loaded; the cycle read is omitted rather than guessed.</p>{% endif %}</div>
  </div>
  <div class="dash row-e">
    <div class="c"><div class="ct"><span>Investment view</span><em>what the numbers say</em></div>
      <ul class="view">{% for v in view %}<li class="{{ v.tone }}">{{ v.text|safe }}</li>{% endfor %}</ul></div>
    <div class="c"><div class="ct"><span>Key risks</span><em>ranked</em></div>
      <ol class="rlist">{% for r in risks[:5] %}<li>{{ r }}</li>{% endfor %}</ol></div>
    <div class="c"><div class="ct"><span>Factor scorecard</span><em>0–100</em></div>
      {{ radar_svg|safe }}
      <ul class="scs">{% for a in scorecard %}<li><span>{{ a.axis }}</span><b>{{ a.score }}</b></li>{% endfor %}</ul>
      <p class="take" style="font-size:11px">Heuristic scales (thresholds in the appendix); the underlying metric is shown in the financial section.</p></div>
  </div>
</div></section>

<!-- ============================ THESIS + VERDICT ============================ -->
<section class="section tight pagebreak" id="thesis"><div class="wrap cols">
  <div>
    {{ head('Investment thesis', 'Why this number') }}
    <div class="lede" style="max-width:none">{% for p in thesis %}<p style="margin-bottom:13px;font-size:{{ '17px' if loop.first else '15px' }}">{{ p|safe }}</p>{% endfor %}</div>
    <p class="note">{{ spec.rationale }}</p>
  </div>
  <aside class="sidebar" style="margin-top:62px">
    <div class="sidetitle">Key data</div>
    {% for k,v in key_data %}<div class="kv"><span class="k">{{ k }}</span><span class="mono">{{ v }}</span></div>{% endfor %}
  </aside>
</div></section>

<section class="section tight" id="verdict"><div class="wrap"><div class="buy"><div class="buy-inner">
  <div class="eyebrow">The verdict</div>
  <h2>How the 12-month target is built</h2>
  <p class="lede">Each lens answers <i>what is a share worth?</i> independently. They are weighted by what fits the business, filtered by plausibility guardrails, rolled forward at the cost of equity and — where it exists — lightly anchored to the Street.</p>
  <div class="buy-cols">
  {% for fam in families %}
    <div class="buy-col"><h4><span>{{ fam.title }}</span><span class="family-w">{{ pct(fam.weight,0) }} of target</span></h4>
    {% for l in fam.lenses %}
      <div class="buy-item{% if l.status=='excluded' %} off{% endif %}"><div><span class="nm">{{ l.label }}</span>
        {% if l.status=='excluded' %}<span class="st bad">excluded</span>{% elif l.status=='winsorized' %}<span class="st bad">winsorised</span>{% elif l.status_note %}<span class="st">down-weighted</span>{% endif %}
        <span class="tickers"><span class="tick">{{ fmt_ps(l.low) }} – {{ fmt_ps(l.high) }}</span></span></div>
        <div class="wt">{{ fmt_ps(l.value) }}<br><span class="family-w">{{ pct(l.eff_weight,0) }}</span></div></div>
    {% endfor %}</div>
  {% endfor %}
  </div>
  <div class="total">
    <div><span class="k">Fair value today</span><div class="v">{{ fmt_ps(tr.fair_value) }}</div></div>
    <div style="text-align:right"><span class="k">{{ 'Published 12-month target' if tr.rated else 'Not rated — indicative only' }}</span>
      <div class="v">{{ fmt_ps(tr.target if tr.rated else tr.fair_value) }}{% if tr.rated %}<small class="{{ rating_dir }}">{{ spct(tr.upside,0) }}</small>{% endif %}</div></div>
  </div>
  <p class="buy-foot"><b>The arithmetic.</b> {{ fmt_ps(tr.fair_value) }} × (1 + {{ pct(tr.ke,2) }}){% if tr.dps %} − {{ fmt_ps(tr.dps) }} dividends{% endif %}
    = model target <b>{{ fmt_ps(tr.model_target) }}</b>{% if tr.street %}; Street mean {{ fmt_ps(tr.street.mean) }}
    {% if tr.street_weight>0 %}at {{ pct(tr.street_weight,0) }} weight{% else %}shown for reference (weight 0){% endif %}{% endif %}
    → published <b>{{ fmt_ps(tr.target) }}</b>.</p>
</div></div></div></section>

<section class="section tight"><div class="wrap">
  <div class="two">
    <div><h3 style="font-size:19px;margin-bottom:8px">Confidence: {{ tr.confidence }}</h3>
      <ul>{% for r in tr.confidence_reasons %}<li>{{ r }}</li>{% endfor %}</ul></div>
    <div><h3 style="font-size:19px;margin-bottom:8px">Guardrails &amp; disclosures</h3>
      {% for g in tr.guardrails %}<div class="guard">{{ g }}</div>{% else %}<p class="note">No guardrail intervened: every lens landed in the plausible band and no Street anchor was applied.</p>{% endfor %}
      {% for f in fwd.flags %}<div class="guard">{{ f }}</div>{% endfor %}</div>
  </div>
</div></section>

<section class="section tight" id="lenses"><div class="wrap">
  {{ head('Inside the lenses', 'Every input, so any number can be challenged', 'Relative lenses apply a target multiple to forward numbers; the DCF values the cash flows; sector lenses use the model that fits the business.') }}
  <div class="lenses">
  {% for l in tr.lenses %}
    <article class="lens"><header><h4>{{ l.label }}<span class="fam">{{ l.family }}</span></h4>
      <span class="tag {{ 'warn' if l.status=='excluded' else ('med' if (l.status!='ok' or l.status_note) else 'ok') }}">{{ 'excluded' if l.status=='excluded' else ('adjusted' if (l.status!='ok' or l.status_note) else pct(l.eff_weight,0) + ' weight') }}</span></header>
      <div class="body"><div class="big" style="font-family:var(--serif)">{{ fmt_ps(l.value) }}</div>
        <div class="rng">{{ fmt_ps(l.low) }} – {{ fmt_ps(l.high) }}{% if l.status_note %} · {{ l.status_note }}{% endif %}</div>
        <table><tbody>{% for k,v in l.rows %}<tr><td>{{ k }}</td><td class="mono">{{ v }}</td></tr>{% endfor %}</tbody></table>
        <p class="nt">{{ l.note }}</p></div></article>
  {% endfor %}
  </div>
</div></section>

<!-- ============================ FINANCIAL ANALYSIS ============================ -->
<section class="section tight pagebreak" id="financials"><div class="wrap">
  {{ head('Financial analysis', 'Statements, returns and balance-sheet quality', 'Reported fiscal years, with the DCF base case and consensus as shaded forecast columns. Forecast free cash flow is unlevered (FCFF).') }}
  {{ table(ft) }}
  <p class="note">{{ ft_note }}</p>

  <div class="dash fin3" style="margin-top:22px">
    <div class="c"><div class="ct"><span>Returns on capital</span><em>by fiscal year</em></div>
      <div class="tblwrap"><table class="mini-t"><thead><tr><th></th>{% for y in ret.years %}<th>FY{{ y }}</th>{% endfor %}</tr></thead><tbody>
        {% for lab, vals in ret.rows %}<tr><td>{{ lab }}</td>{% for v in vals %}<td class="mono">{{ v }}</td>{% endfor %}</tr>{% endfor %}</tbody></table></div>
      {% if dupont %}<div class="exh">DuPont · FY{{ dupont.year }}</div>
      <div class="dp"><div class="box"><b>{{ dupont.nm }}</b><span>net margin</span></div><span class="op">×</span><div class="box"><b>{{ dupont.at }}</b><span>asset turnover</span></div><span class="op">×</span><div class="box"><b>{{ dupont.em }}</b><span>equity multiplier</span></div><span class="op">=</span><div class="box"><b>{{ dupont.roe }}</b><span>ROE</span></div></div>{% endif %}</div>
    <div class="c"><div class="ct"><span>Piotroski F-score</span><em>financial strength · 0–9</em></div>
      {% if pio.available %}<div class="score">{{ pio.score }}<small>/ {{ pio.available }} tests available</small></div>
      <ul class="chk">{% for lab, ok in pio.items %}<li class="{{ 'y' if ok is true else ('n' if ok is false else 'u') }}"><i></i>{{ lab }}{% if ok is none %} <span class="muted">(n/a)</span>{% endif %}</li>{% endfor %}</ul>
      {% else %}<p class="take">Not enough statement lines to compute the score.</p>{% endif %}</div>
    <div class="c"><div class="ct"><span>Distress &amp; earnings quality</span><em>Altman · accruals · cash cycle</em></div>
      {% if alt %}<div class="score">{{ alt.z_txt }}<small>Altman Z · {{ alt.zone }}</small></div>
      <div style="margin:6px 0 10px">{{ alt.meter|safe }}</div>{% else %}<p class="take">Altman Z not computed (financial company or missing balance-sheet lines).</p>{% endif %}
      <div class="metrics">
        <div><div class="k">Sloan accruals</div><div class="v">{{ accr_txt }}</div></div>
        <div><div class="k">OCF / net income</div><div class="v">{{ conv_txt }}</div></div>
        {% for k, v in wc.items() %}<div><div class="k">{{ k }}</div><div class="v">{{ v }}</div></div>{% endfor %}
      </div>
      <p class="take">Sloan accruals below ~0 mean earnings are backed by cash; strongly positive readings flag aggressive accounting.</p></div>
  </div>
  {% if finsum %}
  <div class="exh" style="margin-top:24px">Multiples at the current price, by fiscal year</div>
  <div class="tblwrap"><table class="mini-t"><thead><tr><th>{{ d.currency_symbol }}, per share where noted</th>{% for c in finsum.cols %}<th>{{ c }}</th>{% endfor %}</tr></thead><tbody>
  {% for label, vals in finsum.rows.items() %}<tr><td{% if label in ['growth'] %} class="muted" style="padding-left:22px"{% endif %}>{{ label }}</td>{% for v in vals %}<td class="mono">{{ v }}</td>{% endfor %}</tr>{% endfor %}</tbody></table></div>
  <p class="note">{{ finsum.note }}</p>{% endif %}
</div></section>

<section class="section tight" id="quality"><div class="wrap">
  {{ head('Earnings quality', 'Are the earnings the market is paying for durable?') }}
  <div class="two">
    <div class="tblwrap"><table><tbody>
        <tr><td>Trailing EPS</td><td class="mono">{{ fmt_ps(fwd.eps_ltm) }}</td></tr>
        <tr><td>Consensus EPS FY{{ fwd.fy1_year }}</td><td class="mono">{{ fmt_ps(fwd.eps_fy1) }}</td></tr>
        <tr><td>Consensus EPS FY{{ fwd.fy1_year+1 }}</td><td class="mono">{{ fmt_ps(fwd.eps_fy2) }}</td></tr>
        <tr><td>NTM EPS used</td><td class="mono"><b>{{ fmt_ps(fwd.eps_ntm) }}</b></td></tr>
        <tr><td>Through-cycle (historical average) EPS</td><td class="mono">{{ fmt_ps(fwd.cycle.norm_eps) }}</td></tr>
        <tr><td>Forward ÷ through-cycle</td><td class="mono">{{ ('%.1fx'|format(fwd.cycle.peak_ratio)) if fwd.cycle.peak_ratio else '—' }}</td></tr>
        <tr><td>Durable EPS growth used</td><td class="mono">{{ pct(fwd.growth,1) }}</td></tr>
        <tr><td>Earnings-durability factor on multiples</td><td class="mono">×{{ '%.2f'|format(fwd.cycle.durability) }}</td></tr>
        <tr><td>Basis</td><td>{{ fwd.basis }}</td></tr>
    </tbody></table></div>
    <div>
      <p class="lede" style="font-size:16px"><b>{{ 'Cyclical or in an earnings inflection.' if fwd.cycle.is_cyclical else 'No cyclicality flags.' }}</b>
         {% if fwd.cycle.reasons %}{{ fwd.cycle.reasons|join('; ') }}.{% else %}Revenue and margins show no peak-to-trough pattern in the reported history, so forward earnings are capitalised at the full target multiple.{% endif %}</p>
      <p class="note">Growth source: {{ fwd.growth_src }}. Multiples price <i>durable</i> growth, so a one-year recovery step is never extrapolated, and when forward EPS is far above what the business has historically earned the target multiple is scaled down — the market pays less for peak earnings.</p>
    </div>
  </div>
</div></section>

<!-- ============================ DCF ============================ -->
{% if dcf %}
<section class="section tight pagebreak" id="dcf"><div class="wrap">
  {{ head('DCF cross-check', 'Drivers, cash-flow build and sensitivity') }}
  <div class="tblwrap"><table class="assum"><thead><tr><th>Driver</th><th>Path</th><th style="text-align:left">Why</th></tr></thead><tbody>
  {% for drv, path, why in assumptions %}
    <tr><td><b>{{ drv }}</b></td><td class="mono" style="white-space:nowrap">{{ path }}</td><td style="text-align:left;font-size:12.5px;line-height:1.5">{{ why }}</td></tr>
  {% endfor %}</tbody></table></div>
  <div class="exh" style="margin-top:22px">Free-cash-flow build · {{ ft.unit_label }}</div>
  <div class="tblwrap"><table class="fin"><thead><tr><th></th>{% for r in fcff_rows %}<th>{{ r.year }}E</th>{% endfor %}</tr></thead><tbody>
    {% for lab, key, cls in fcff_lines %}<tr class="{{ cls }}"><td>{{ lab }}</td>{% for r in fcff_rows %}<td class="mono">{{ r[key] }}</td>{% endfor %}</tr>{% endfor %}
  </tbody></table></div>
  <div class="three" style="margin-top:18px">
    <div class="c"><div class="ct"><span>Revenue &amp; FCFF</span></div>{{ proj_svg|safe }}</div>
    <div class="c"><div class="ct"><span>EBIT margin path</span></div>{{ margin_svg|safe }}</div>
    <div class="c"><div class="ct"><span>EV → equity bridge</span></div>{{ evbridge_svg|safe }}</div>
  </div>
  {% if sens_html %}
  <div class="two" style="margin-top:22px">
    <div class="sens-wrap"><div class="exh" style="margin-top:0">DCF value per share · WACC × terminal growth (vs. price)</div>{{ sens_html|safe }}
      <p class="note">Shaded against the current price: green = above, terracotta = below. Outlined cell = base case.</p></div>
    <div>
      <div class="metrics" style="margin-bottom:12px;grid-template-columns:repeat(4,1fr)">{% for k, v in dcf_stats %}<div><div class="k">{{ k }}</div><div class="v">{{ v }}</div></div>{% endfor %}</div>
      {% if returns_comment %}<p class="lede" style="font-size:15px">{{ returns_comment|safe }}</p>{% endif %}
      {% if diagnostics and diagnostics.flags %}<div class="tblwrap"><table><tbody>{% for k, v, st in diagnostics.flags %}<tr><td>{{ k }}</td><td class="mono">{{ v }}</td>
        <td><span class="tag {{ 'ok' if st=='ok' else 'warn' }}">{{ st }}</span></td></tr>{% endfor %}</tbody></table></div>{% endif %}
    </div>
  </div>
  {% endif %}
</div></section>
{% endif %}

<!-- ============================ CYCLE ============================ -->
{% if cycle %}
<section class="section tight pagebreak" id="cycle"><div class="wrap">
  {{ head('Reloj de inversión', 'Where the cycle is, and what it has paid ' + cycle.asset_en, 'Live reading of the Reloj de inversión project: 28 FRED series → growth and inflation axes (robust z-scores, PCA) → phase probabilities. Sector evidence is historical excess return vs the US market per phase, with Newey-West t-statistics and false-discovery control.') }}
  <div class="dash" style="grid-template-columns:minmax(0,1.1fr) minmax(0,1fr)">
    <div class="c"><div class="ct"><span>Growth × inflation plane</span><em>last 36 months</em></div>{{ plane_big_svg|safe }}</div>
    <div class="c"><div class="ct"><span>Phase probabilities</span><em>{{ cycle.strength_en }} signal · margin {{ cycle.conf_pts }} pts</em></div>
      {{ probs_html|safe }}
      <p class="take">{{ cycle.read|safe }}</p>
      <div class="metrics" style="margin-top:12px">{% for k, v in cycle.facts %}<div><div class="k">{{ k }}</div><div class="v">{{ v }}</div></div>{% endfor %}</div>
    </div>
  </div>
  <div class="dash" style="grid-template-columns:minmax(0,1.1fr) minmax(0,1fr)">
    <div class="c"><div class="ct"><span>{{ cycle.asset_en }}: excess return by phase</span><em>pp/yr vs US market · shrunk (solid) vs raw (pale)</em></div>{{ edge_svg|safe }}
      <p class="take">{{ cycle.edge_take|safe }}</p></div>
    <div class="c"><div class="ct"><span>Historical evidence for {{ cycle.asset_en }}</span><em>since 1970</em></div>
      <div class="tblwrap"><table class="mini-t cyc-t"><thead><tr><th>Phase</th><th>Ann.</th><th>vs mkt</th><th>t</th><th>Hit</th><th>Mo.</th><th>Signal</th></tr></thead><tbody>
        {% for r in cycle.table %}<tr><td>{{ r.phase }}</td><td class="mono">{{ r.ann }}</td><td class="mono {{ r.tone }}">{{ r.rel }}</td><td class="mono">{{ r.t }}</td><td class="mono">{{ r.hit }}</td><td class="mono">{{ r.n }}</td><td><span class="tag {{ r.rel_cls }}">{{ r.reliability }}</span></td></tr>{% endfor %}
      </tbody></table></div>
      <p class="note">“Ann.” is the sector's average annual return while the cycle was in that phase; “vs mkt” the excess over the US market (shrunk estimate); t-statistics are Newey-West. A weak or “no signal” reliability means the data cannot distinguish the sector's phase return from chance.</p></div>
  </div>
  <div class="dash" style="grid-template-columns:minmax(0,1fr) minmax(0,1fr)">
    <div class="c"><div class="ct"><span>The Reloj's playbook now</span><em>{{ cycle.phase }} · {{ cycle.playbook_label }}</em></div>
      <div class="tblwrap"><table class="mini-t"><thead><tr><th>Allocation</th><th>Weight</th></tr></thead><tbody>
        {% for name, w, mine in cycle.playbook %}<tr{% if mine %} class="total"{% endif %}><td>{{ name }}{% if mine %} <span class="tag ok">this company's sector</span>{% endif %}</td><td class="mono">{{ w }}</td></tr>{% endfor %}
      </tbody></table></div>
      <p class="take">{{ cycle.playbook_take|safe }}</p></div>
    <div class="c"><div class="ct"><span>How to use the ETF</span><em>{{ cycle.holdings_asof or '' }}</em></div>
      <div class="metrics">{% for k, v in cycle.etf_facts %}<div><div class="k">{{ k }}</div><div class="v">{{ v }}</div></div>{% endfor %}</div>
      <p class="take">{{ cycle.etf_take|safe }}</p>
      <p class="note">Source: <a href="{{ cycle.site }}" target="_blank" rel="noopener">Reloj de inversión</a> · {{ cycle.source_txt }}. This is an analytical tool, not investment advice; the sector tilt is context for the valuation, not an input to the price target.</p></div>
  </div>
</div></section>
{% endif %}

{% if price_svg %}
<section class="section tight" id="price"><div class="wrap">
  {{ head('Price & technicals', 'Five years of price against our 12-month target') }}
  <div class="c">{{ price_svg|safe }}</div>
  <div class="metrics" style="margin-top:14px">{% for k, v in price_stats %}<div><div class="k">{{ k }}</div><div class="v">{{ v }}</div></div>{% endfor %}</div>
</div></section>
{% endif %}

<!-- ============================ FACTORS · RISKS ============================ -->
<section class="section tight" id="risks"><div class="wrap">
  {% if peer_rows %}
  {{ head('Peers', 'Trading comparables') }}
  <div class="tblwrap"><table class="mini-t"><thead><tr><th>Peer</th><th>Mkt cap</th><th>P/E fwd</th><th>EV/EBITDA</th><th>EV/Sales</th><th>P/B</th></tr></thead><tbody>
    {% for p in peer_rows %}<tr class="{{ 'total' if p.med }}"><td>{{ p.name }}</td><td class="mono">{{ p.mc }}</td><td class="mono">{{ p.pe }}</td><td class="mono">{{ p.ev }}</td><td class="mono">{{ p.evs }}</td><td class="mono">{{ p.pb }}</td></tr>{% endfor %}
  </tbody></table></div><div style="height:30px"></div>{% endif %}
  {{ head('Factors', 'What moves this stock') }}
  {% if factors %}<div class="tblwrap"><table><thead><tr><th style="width:8%">Type</th><th style="width:20%">Factor</th>
    <th style="width:9%">Exposure</th><th style="width:24%;text-align:left">Evidence</th><th style="text-align:left">Why / mechanism</th></tr></thead><tbody>
  {% for f in factors %}
    <tr><td>{{ f.cat }}</td><td><b>{{ f.factor }}</b></td>
    <td><span class="tag {{ 'high' if f.level=='High' else ('med' if f.level=='Medium' else 'low') }}">{{ f.level }}</span></td>
    <td class="mono" style="text-align:left;font-size:11.5px">{{ f.evidence }}</td>
    <td style="text-align:left;font-size:12.5px;line-height:1.5">{{ f.why }}</td></tr>
  {% endfor %}</tbody></table></div>{% endif %}
  {% if catalysts %}<div style="height:26px"></div>{{ head('Catalysts', 'What each lever is worth') }}
  <ul>{% for c in catalysts %}<li>{{ c|safe }}</li>{% endfor %}</ul>{% endif %}
  <div style="height:26px"></div>{{ head('Risks', 'Key risks') }}
  <ul>{% for r in risks %}<li>{{ r }}</li>{% endfor %}</ul>
</div></section>

<section class="section tight" id="appendix"><div class="wrap">
  {{ head('Appendix', 'Method and definitions') }}
  <ol class="rules">
    <li><b>Lenses and weights</b>The target triangulates relative lenses (target multiples on consensus forward numbers, anchored on peers/sector references and adjusted for durable growth, leverage and earnings durability), a 10-year DCF (consensus for the near years, geometric growth decay, mean-reverting margins) and sector models, weighted by company profile.</li>
    <li><b>Guardrails</b>A lens outside 0.2×–5× the price is excluded; lenses &gt; 2.2× away from the median of the others are down-weighted by 60%; the published target is limited to 0.4×–2.5× the price; fewer than two usable lenses, or a result forced by a guardrail, is published NOT RATED.</li>
    <li><b>12-month target</b>Fair value × (1 + cost of equity) − dividends; bear/bull from the lens ranges; Street consensus anchored at up to 30% (scaled by analyst count) and always shown separately.</li>
    <li><b>Scorecard scales</b>Valuation: expected return −30%…+50% → 0…100. Growth: durable EPS growth 0…25% and FY+1 revenue −5…+30%. Profitability: ROIC−WACC −5…+25 pts and EBIT margin 0…35%. Quality: Piotroski share of tests passed, OCF/NI 0.5…1.2, accruals. Balance sheet: net debt/EBITDA, interest cover, Altman zone. Cycle fit: Reloj tilt −4…+4 pp/yr.</li>
    <li><b>Piotroski · Altman · Sloan</b>Piotroski F: nine binary tests of profitability, leverage/liquidity and efficiency (tests that cannot be computed from the available statement lines are excluded, not failed). Altman Z (original industrial form): &gt;2.99 safe, 1.81–2.99 grey, &lt;1.81 distress. Sloan accruals: (net income − OCF) / average assets.</li>
    <li><b>Reloj de inversión</b>Phase probabilities and sector evidence come from the linked project's published data (see source above). Tilt = Σ phase probability × shrunk excess return of the sector in that phase. It describes historical behaviour and is not an input to the price target.</li>
  </ol>
  <p class="disclaimer" style="margin-top:22px"><b>Disclaimer.</b> Generated by an automated, sector-aware valuation engine from public data ({{ d.provider }}). {{ d.ticker }} was classified as <b>{{ spec.label }}</b>. Forward numbers come from analyst consensus where available and from reported figures otherwise; they are not a substitute for fundamental judgement. Nothing here is investment advice, a recommendation, or an offer to transact. Do your own due diligence.</p>
</div></section>
<div class="foot-bar"><div class="wrap"><p class="disclaimer">SuperAnalyst · {{ report_date }} · {{ d.ticker }} · design system: Reloj de inversión</p></div></div>
<script>if(location.search.indexOf('print=1')>-1){window.addEventListener('load',function(){setTimeout(function(){window.print()},400)})}</script>
</body></html>""")
