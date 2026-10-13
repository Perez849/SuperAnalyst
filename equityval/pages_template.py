"""The research note as a paged document (Jinja). Every page is a fixed A4 sheet: running header,
page title, a prose column with exhibits in a side column, an optional full-width band of tables
at the foot, and a footer with sources. The script at the end fits each page (type size, spacing,
optional / extra blocks) so no page ends half-empty or overflows; it runs on screen and before print."""
from jinja2 import Template

TEMPLATE = Template(r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ d.ticker }} — Equity Research · SuperAnalyst</title>
<style>{{ design_css|safe }}</style></head><body class="doc">
{%- macro blk(b) -%}
{%- if b.t == 'p' -%}<p{% if b.lead %} class="lead"{% endif %}{% if b.opt %} data-opt{% endif %}{% if b.more %} data-more hidden{% endif %}>{{ b.html|safe }}</p>
{%- elif b.t == 'h' -%}<h3{% if b.opt %} data-opt{% endif %}{% if b.more %} data-more hidden{% endif %}>{{ b.html|safe }}</h3>
{%- elif b.t == 'ul' -%}<ul class="bl"{% if b.opt %} data-opt{% endif %}{% if b.more %} data-more hidden{% endif %}>{% for i in b['items'] %}<li>{{ i|safe }}</li>{% endfor %}</ul>
{%- elif b.t == 'callout' -%}<div class="callout"{% if b.opt %} data-opt{% endif %}{% if b.more %} data-more hidden{% endif %}><div class="ct">{{ b.title }}</div><ul class="bl">{% for i in b['items'] %}<li>{{ i|safe }}</li>{% endfor %}</ul></div>
{%- elif b.t == 'tiles' -%}<div class="tiles" style="--n:{{ b['items']|length }}">{% for k, v, s, cls in b['items'] %}<div><div class="k">{{ k }}</div><div class="v {{ cls }}">{{ v }}</div>{% if s %}<div class="s">{{ s }}</div>{% endif %}</div>{% endfor %}</div>
{%- elif b.t == 'pull' -%}<div class="pull"{% if b.opt %} data-opt{% endif %}{% if b.more %} data-more hidden{% endif %}>{{ b.html|safe }}</div>
{%- elif b.t == 'ex' -%}{{ exh(b) }}
{%- elif b.t == 'ans' -%}<div class="ans"><div class="row"><div><div class="k">{{ b.left_k }}</div><div class="big">{{ b.left_v }}</div></div><div><div class="k">{{ b.right_k }}</div><div class="big">{{ b.right_v|safe }}</div></div></div><div class="ar">{{ b.html|safe }}</div></div>
{%- endif -%}
{%- endmacro -%}
{%- macro exh(e) -%}
<figure class="ex" data-key="{{ e.key }}" style="margin:0"{% if e.opt %} data-opt{% endif %}{% if e.more %} data-more hidden{% endif %}><figcaption class="ex-h"><span class="ex-n">Exhibit {{ e.num }}</span><span>{{ e.title }}</span></figcaption>
<div class="ex-b">{{ e.html|safe }}</div>{% if e.source %}<div class="ex-s">{{ e.source }}</div>{% endif %}</figure>
{%- endmacro -%}

<header class="top"><div class="wrap top-inner">
  <a class="brand" href="{{ library_href or '#p1' }}">{{ brand|safe }}<span><span class="brand-word">SuperAnalyst</span><br><span class="brand-tag">EQUITY RESEARCH</span></span></a>
  <nav class="top-nav">{% for pg in pages if pg.nav %}<a href="#{{ pg.key }}">{{ pg.nav }}</a>{% endfor %}</nav>
  <div class="top-actions">{% if library_href %}<a class="ghost" href="{{ library_href }}">← Library</a>{% endif %}<button class="pdf-btn" type="button" onclick="window.print()">⬇ Save as PDF</button></div>
</div></header>

<main class="pages" id="pages">
{% for pg in pages %}
<section class="pg{% if pg.cols2 %} cols2{% endif %}" id="{{ pg.key }}" data-n="{{ loop.index }}">
  <header class="ph"><span class="ph-l">{{ brand_small|safe }}<b>SuperAnalyst</b><span>Equity Research</span></span>
    <span class="ph-r"><b>{{ d.ticker }}</b><span>{{ d.sector }}</span><em class="rt {{ rating_dir }}">{{ rating }}</em><span>PT {{ pt_txt }}</span></span></header>
  {% if pg.cover %}
  <div class="cv">
    <div><div class="kick">Independent valuation · {{ d.sector }}{% if d.industry %} · {{ d.industry }}{% endif %}</div>
      <h1>{{ d.name|e }}<span class="tk">{{ d.ticker }}</span></h1>
      <div class="hl">{{ pg.cover.headline }}</div></div>
    <div class="rbox"><span class="rt {{ rating_dir }}">{{ rating }}</span>
      <div class="pt-big">{{ pt_txt }}<small>{{ 'target · 12m' if tr.rated else 'indicative value' }}</small></div>
      <div class="row"><span>Price ({{ price_date }})</span><b>{{ fmt_ps(d.price) }}</b></div>
      <div class="row"><span>{{ '12m total return' if tr.rated else 'vs price' }}</span><b class="{{ rating_dir }}">{{ spct(tr.total_return if tr.rated else tr.fair_value / d.price - 1, 0) }}</b></div>
      <div class="row"><span>Fair value today</span><b>{{ fmt_ps(tr.fair_value) }}</b></div>
      <div class="row"><span>Confidence</span><b>{{ tr.confidence }}</b></div></div>
  </div>
  {% else %}
  <div class="pt"><div class="kick">{{ pg.kicker }}</div><h2>{{ pg.title }}</h2>{% if pg.sub %}<p class="sub">{{ pg.sub }}</p>{% endif %}</div>
  {% endif %}
  <div class="pbody{% if not pg.side %} one{% endif %}">
    <div class="pmain"><div class="pm-in">{% for g in pg.groups %}<div class="sg">{% for b in g %}{{ blk(b) }}{% endfor %}</div>{% endfor %}</div></div>
    {% if pg.side %}<aside class="pside"><div class="ps-in">{% for e in pg.side %}{{ exh(e) }}{% endfor %}</div></aside>{% endif %}
  </div>
  {% if pg.band %}<div class="pband{% if pg.band|length > 1 %} two{% endif %}">{% for e in pg.band %}{{ exh(e) }}{% endfor %}</div>{% else %}<div></div>{% endif %}
  <footer class="pf"><span class="pf-src">{{ pg.source or default_source }}</span><span class="pn">{{ d.ticker }} · {{ loop.index }} / {{ pages|length }}</span></footer>
</section>
{% endfor %}
</main>
<script>
(function(){
  var FS_MIN=8.8, FS_MAX=11.8, LO=9.6, HI=10.45, root=document.getElementById('pages');
  function setT(m,fs,lh,pg){m.style.setProperty('--fs',fs+'px');m.style.setProperty('--lh',lh);m.style.setProperty('--pgap',pg+'em')}
  function fits(m,inner){return inner.offsetHeight<=m.clientHeight+0.5}
  function sync(inner){[].forEach.call(inner.children,function(sg){var v=[].filter.call(sg.children,function(e){return !e.hidden});sg.hidden=!v.length||v.every(function(e){return e.tagName==='H3'});sg.style.paddingTop=''})}
  function bestFs(m,inner){
    sync(inner); setT(m,FS_MAX,1.5,.65); if(fits(m,inner)) return FS_MAX;
    setT(m,FS_MIN,1.5,.65); if(!fits(m,inner)) return 0;
    var lo=FS_MIN,hi=FS_MAX;
    for(var i=0;i<12;i++){var mid=(lo+hi)/2;setT(m,mid,1.5,.65);if(fits(m,inner))lo=mid;else hi=mid}
    return lo;
  }
  function fitMain(pg){
    var m=pg.querySelector('.pmain'), inner=m.firstElementChild;
    var opts=[].slice.call(inner.querySelectorAll('[data-opt]')), extras=[].slice.call(inner.querySelectorAll('[data-more]'));
    opts.forEach(function(e){e.hidden=false}); extras.forEach(function(e){e.hidden=true});
    var fs=bestFs(m,inner), nOpt=opts.length, nExt=0;
    while((fs===0||fs<LO) && nOpt>0){opts[--nOpt].hidden=true; fs=bestFs(m,inner)}
    if(fs===0) fs=FS_MIN;
    while(fs>HI && nExt<extras.length){
      extras[nExt].hidden=false; var f2=bestFs(m,inner);
      if(f2===0){extras[nExt].hidden=true;break}
      nExt++; fs=f2;
    }
    sync(inner); setT(m,fs,1.5,.65);
    var lo=0,hi=1;                       // spend leftover room on leading and paragraph spacing
    setT(m,fs,1.62,1.1); if(fits(m,inner)){lo=1}
    else{for(var i=0;i<10;i++){var t=(lo+hi)/2;setT(m,fs,1.5+.12*t,.65+.45*t);if(fits(m,inner))lo=t;else hi=t}}
    setT(m,fs,1.5+.12*lo,.65+.45*lo);
    var secs=[].filter.call(inner.children,function(e){return !e.hidden});
    var slack=m.clientHeight-inner.offsetHeight;
    if(slack>1 && secs.length>1){var add=Math.min(34,Math.floor(slack/(secs.length-1))); for(var k=1;k<secs.length;k++) secs[k].style.paddingTop=add+'px'}
    pg.dataset.fillMain=(inner.offsetHeight/m.clientHeight).toFixed(3);
    pg.dataset.slackMain=Math.max(0,slack).toFixed(0);
  }
  function fitSide(pg){
    var s=pg.querySelector('.pside'); if(!s) return;
    var inner=s.firstElementChild; inner.style.cssText='';
    var opts=[].slice.call(inner.querySelectorAll('[data-opt]')), extras=[].slice.call(inner.querySelectorAll('[data-more]'));
    opts.forEach(function(e){e.hidden=false}); extras.forEach(function(e){e.hidden=true});
    function h(){return inner.getBoundingClientRect().height}
    function room(){return s.getBoundingClientRect().height}
    function zfit(){ inner.style.zoom=1; if(h()<=room()+.5) return 1;
      var lo=.8,hi=1; inner.style.zoom=lo; if(h()>room()+.5) return 0;
      for(var i=0;i<10;i++){var mid=(lo+hi)/2;inner.style.zoom=mid;if(h()<=room()+.5)lo=mid;else hi=mid}
      return lo }
    var z=zfit(), nOpt=opts.length;
    while(z===0 && nOpt>0){opts[--nOpt].hidden=true; z=zfit()}
    if(z===0) z=.8;
    var nExt=0;
    while(h()<room()*.9 && nExt<extras.length){
      extras[nExt].hidden=false; var z2=zfit();
      if(z2===0){extras[nExt].hidden=true;break}
      nExt++; z=z2;
    }
    inner.style.zoom=z;
    var slack=room()-h();
    if(slack>2){ if(slack/room()<=.25){inner.style.cssText='display:flex;flex-direction:column;justify-content:space-between;height:'+(room()/z)+'px;zoom:'+z}else{inner.style.cssText='display:flex;flex-direction:column;gap:16px;zoom:'+z} }
    pg.dataset.fillSide=(h()/room()).toFixed(3);
  }
  function renumber(){
    var n=0, map={};
    [].forEach.call(document.querySelectorAll('figure.ex'),function(e){
      if(e.hidden||e.closest('[hidden]')) return;
      n++; map[e.dataset.key]=n; var t=e.querySelector('.ex-n'); if(t) t.textContent='Exhibit '+n;
    });
    [].forEach.call(document.querySelectorAll('.xr'),function(x){var k=x.dataset.ex; x.textContent=map[k]?('Exhibit '+map[k]):'the exhibit'});
  }
  function fitAll(){
    var tf=root.style.transform; root.style.transform='none';
    [].forEach.call(document.querySelectorAll('.pg'),function(pg){fitMain(pg);fitSide(pg)});
    renumber();
    root.style.transform=tf;
    document.body.dataset.fit='done';
  }
  function scale(){
    var w=window.innerWidth;
    if(w<830){
      var pz=(w-14)/794;
      root.style.width='794px'; root.style.marginLeft='7px'; root.style.marginRight='0';
      root.style.transform='scale('+pz.toFixed(4)+')';
      root.style.marginBottom=(-(root.offsetHeight*(1-pz)))+'px';
    }else{
      root.style.transform=''; root.style.width=''; root.style.marginLeft=''; root.style.marginRight=''; root.style.marginBottom='';
    }
  }
  fitAll(); scale();
  if(document.fonts&&document.fonts.ready) document.fonts.ready.then(function(){fitAll();scale()});
  window.addEventListener('load',function(){setTimeout(function(){fitAll();scale()},30)});
  window.addEventListener('resize',scale);
  if(location.search.indexOf('print=1')>-1){window.addEventListener('load',function(){setTimeout(function(){window.print()},500)})}
})();
</script>
</body></html>""")
