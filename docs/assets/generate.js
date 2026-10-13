/* Generar informes (y su PDF) desde la propia web.
 *
 * GitHub Pages es estático: no puede ejecutar Python. Lo que hace esta página es pedirle a
 * GitHub Actions que ejecute el workflow "Equity valuation → Pages" (que calcula, genera HTML,
 * PDF y Excel y los publica en /docs) y esperar a que el resultado aparezca. Tres modos:
 *   1. api        un Worker de Cloudflare guarda el token y lanza el workflow (recomendado).
 *   2. token      un token fino de GitHub guardado solo en este navegador (localStorage).
 *   3. manual     enlace directo a GitHub Actions; la página espera igualmente al resultado.
 * Sin dependencias.
 */
(function () {
  "use strict";
  var cfg = Object.assign({ api: "", repo: "Perez849/SuperAnalyst", workflow: "pages.yml", ref: "main" },
                          window.SUPERANALYST || {});
  var $ = function (id) { return document.getElementById(id); };
  var form = $("genForm");
  if (!form) return;

  var TICKER_RE = /^[A-Za-z0-9.^=\-]{1,12}$/;
  var KEY = "superanalyst.ghtoken";
  var token = ""; try { token = localStorage.getItem(KEY) || ""; } catch (e) {}
  var busy = false;

  var elStatus = $("genStatus"), elSteps = $("genSteps"), elMsg = $("genMsg"), elDone = $("genDone");
  var elMode = $("genMode"), elTok = $("genToken"), elTokRow = $("genTokenRow"), elConn = $("genConn");

  function mode() { return cfg.api ? "api" : (token ? "token" : "manual"); }
  function sleep(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }

  function renderMode() {
    var m = mode();
    elMode.textContent = m === "api" ? "Conectado mediante Worker" :
                         m === "token" ? "Conectado con tu token de GitHub (solo en este navegador)" :
                         "Sin conexión: te llevo a GitHub Actions";
    elMode.className = "gen-mode " + m;
    elTokRow.hidden = m === "api";
    if (elTok) elTok.value = token ? "••••••••••••••••" : "";
    $("genForget").hidden = !token;
  }

  function steps(active, failed) {
    var names = ["Petición enviada", "En cola en GitHub Actions", "Calculando valoración y PDF", "Publicando en la web"];
    elSteps.innerHTML = names.map(function (n, i) {
      var cls = i < active ? "done" : (i === active ? (failed ? "bad" : "now") : "");
      return '<li class="' + cls + '"><i></i>' + n + "</li>";
    }).join("");
  }
  function say(html) { elMsg.innerHTML = html; }

  function ghHeaders() {
    return { "Accept": "application/vnd.github+json", "Authorization": "Bearer " + token,
             "X-GitHub-Api-Version": "2022-11-28", "Content-Type": "application/json" };
  }

  async function dispatch(inputs) {
    var m = mode();
    if (m === "api") {
      var r = await fetch(cfg.api, { method: "POST", headers: { "Content-Type": "application/json" },
                                      body: JSON.stringify(inputs) });
      var j = {}; try { j = await r.json(); } catch (e) {}
      if (!r.ok) throw new Error(j.error || ("El Worker respondió " + r.status));
      return;
    }
    if (m === "token") {
      var r2 = await fetch("https://api.github.com/repos/" + cfg.repo + "/actions/workflows/" + cfg.workflow + "/dispatches", {
        method: "POST", headers: ghHeaders(), body: JSON.stringify({ ref: cfg.ref, inputs: inputs }) });
      if (r2.status !== 204) {
        var t = ""; try { t = (await r2.json()).message || ""; } catch (e) {}
        if (r2.status === 401 || r2.status === 403 || r2.status === 404)
          throw new Error("GitHub rechazó el token (" + r2.status + "). Comprueba que es un token fino con permiso «Actions: lectura y escritura» sobre " + cfg.repo + ". " + t);
        throw new Error("GitHub respondió " + r2.status + ". " + t);
      }
      return;
    }
    throw new Error("manual");
  }

  async function runState(since) {
    // estado del workflow (solo con token, o vía Worker si lo implementa); devuelve {status, conclusion, url}
    try {
      var url;
      var opts = {};
      if (mode() === "token") {
        url = "https://api.github.com/repos/" + cfg.repo + "/actions/workflows/" + cfg.workflow + "/runs?event=workflow_dispatch&per_page=5";
        opts = { headers: ghHeaders() };
      } else if (mode() === "api") {
        url = cfg.api + (cfg.api.indexOf("?") > -1 ? "&" : "?") + "since=" + encodeURIComponent(new Date(since).toISOString());
      } else return null;
      var r = await fetch(url, opts);
      if (!r.ok) return null;
      var j = await r.json();
      if (j.workflow_runs) {
        var run = j.workflow_runs.filter(function (x) { return Date.parse(x.created_at) >= since - 90000; })[0];
        return run ? { status: run.status, conclusion: run.conclusion, url: run.html_url } : null;
      }
      return j && j.status ? j : null;
    } catch (e) { return null; }
  }

  async function fetchMeta(ticker) {
    try {
      var r = await fetch("reports/" + encodeURIComponent(ticker) + ".json?_=" + Date.now(), { cache: "no-store" });
      if (!r.ok) return null;
      return await r.json();
    } catch (e) { return null; }
  }

  function showDone(meta, ticker) {
    var rated = meta.rated !== false;
    var links = ['<a class="pdf-btn gold" href="reports/' + esc(meta.pdf || (ticker + ".pdf")) + '" download>⬇ Descargar PDF</a>',
                 '<a class="ghost" href="reports/' + esc(meta.html) + '">Abrir informe</a>'];
    if (meta.xlsx) links.push('<a class="ghost" href="reports/' + esc(meta.xlsx) + '">Excel</a>');
    links.push('<a class="ghost" href="./" onclick="location.reload();return false">Recargar biblioteca</a>');
    elDone.innerHTML =
      '<div class="gen-result"><div><span class="k">' + esc(meta.ticker) + " · " + esc(meta.name || "") + "</span>" +
      '<div class="v">' + esc(meta.rating || "") + (rated ? " · " + esc(meta.currency || "$") + Number(meta.target).toLocaleString("es-ES", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : " · sin precio objetivo") + "</div></div>" +
      '<div class="gen-links">' + links.join("") + "</div></div>";
    elDone.hidden = false;
  }

  async function wait(ticker, since, withState) {
    var deadline = Date.now() + 12 * 60 * 1000, lastShown = -1;
    while (Date.now() < deadline) {
      await sleep(8000);
      var secs = Math.round((Date.now() - since) / 1000);
      var st = withState ? await runState(since) : null;
      var active = 1;
      if (st) {
        if (st.status === "in_progress") active = 2;
        if (st.status === "completed") active = st.conclusion === "success" ? 3 : 2;
        if (st.status === "completed" && st.conclusion !== "success") {
          steps(2, true);
          say('El workflow terminó con error (' + esc(st.conclusion) + '). Mira el registro en <a href="' + esc(st.url) + '" target="_blank" rel="noopener">GitHub Actions</a>: lo más habitual es que Yahoo limitara las peticiones; vuelve a intentarlo o usa un proveedor FMP.');
          return false;
        }
      } else if (secs > 25) { active = 2; }
      if (active !== lastShown) { steps(active); lastShown = active; }
      say("Esto suele tardar 2–4 minutos. Llevas " + secs + " s. Puedes dejar esta pestaña abierta.");
      var meta = await fetchMeta(ticker);
      if (meta && meta.generated_at && Date.parse(meta.generated_at) >= since - 5000) {
        steps(4); say("¡Listo! El informe ya está publicado.");
        showDone(meta, ticker); return true;
      }
    }
    steps(3, true);
    say("Todavía no veo el resultado tras 12 minutos. Puede que el workflow siga en cola o haya fallado: revisa la pestaña Actions del repositorio y recarga esta página.");
    return false;
  }

  form.addEventListener("submit", async function (ev) {
    ev.preventDefault();
    if (busy) return;
    var ticker = $("genTicker").value.trim().toUpperCase();
    if (!TICKER_RE.test(ticker)) { elStatus.hidden = false; elDone.hidden = true; steps(0, true);
      say("Ticker no válido. Usa letras, números, punto o guion (p. ej. AAPL, BRK-B, SAN.MC)."); return; }
    var inputs = { ticker: ticker, profile: $("genProfile").value, provider: $("genProvider").value };
    busy = true; $("genGo").disabled = true; elStatus.hidden = false; elDone.hidden = true;
    var since = Date.now();
    try {
      steps(0); say("Enviando la petición a GitHub…");
      try { await dispatch(inputs); }
      catch (e) {
        if (e.message !== "manual") throw e;
        // modo manual: abrir Actions con el ticker a mano
        say('Sin token ni Worker no puedo lanzarlo yo. <b>1)</b> Abre <a target="_blank" rel="noopener" href="https://github.com/' + cfg.repo + "/actions/workflows/" + cfg.workflow + '">GitHub Actions</a> → <i>Run workflow</i> con el ticker <b>' + esc(ticker) + "</b>. <b>2)</b> Esta página esperará aquí a que aparezca el resultado.");
        steps(1);
        await wait(ticker, since, false);
        return;
      }
      steps(1); say("Petición aceptada. Esperando a que GitHub empiece…");
      await wait(ticker, since, true);
    } catch (e) {
      steps(0, true); say("No se pudo lanzar: " + esc(e.message));
    } finally { busy = false; $("genGo").disabled = false; }
  });

  $("genSave").addEventListener("click", function () {
    var v = (($("genTokenInput") || {}).value || "").trim();
    if (!v) return;
    token = v; try { localStorage.setItem(KEY, v); } catch (e) {}
    $("genTokenInput").value = ""; renderMode(); elConn.open = false;
  });
  $("genForget").addEventListener("click", function () {
    token = ""; try { localStorage.removeItem(KEY); } catch (e) {}
    renderMode();
  });

  renderMode();
})();
