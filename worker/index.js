/* Cloudflare Worker: lanza la generación de informes (y su PDF) desde la web de SuperAnalyst.
 *
 * La web (GitHub Pages) es estática y no puede guardar un token de GitHub. Este Worker lo
 * guarda como secreto y, cuando la web se lo pide, lanza el workflow "Equity valuation → Pages"
 * (workflow_dispatch). El workflow calcula, genera HTML + PDF + Excel y los publica en /docs.
 *
 * Seguridad:
 *   - solo acepta peticiones desde ALLOWED_ORIGIN;
 *   - valida ticker / perfil / proveedor con listas cerradas (nada llega al workflow sin validar);
 *   - limita peticiones por IP (MAX_PER_HOUR) y en total (MAX_TOTAL_PER_HOUR), best-effort en memoria;
 *   - el token solo necesita el permiso «Actions: lectura y escritura» sobre UN repositorio.
 * Despliegue: ver worker/README.md
 */
const TICKER_RE = /^[A-Za-z0-9.^=\-]{1,12}$/;
const PROFILES = ["auto", "standard", "bank", "insurance", "reit", "utility", "cyclical", "high_growth"];
const PROVIDERS = ["auto", "fmp", "yfinance"];
const hits = new Map();
let total = [];

function cors(origin, env) {
  const allowed = (env.ALLOWED_ORIGIN || "https://perez849.github.io").split(",").map(s => s.trim());
  return {
    "Access-Control-Allow-Origin": allowed.includes(origin) ? origin : allowed[0],
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Vary": "Origin",
  };
}
const json = (obj, status, headers) =>
  new Response(JSON.stringify(obj), { status, headers: { "Content-Type": "application/json", ...headers } });

function gh(env, path, init = {}) {
  return fetch(`https://api.github.com/repos/${env.REPO || "Perez849/SuperAnalyst"}${path}`, {
    ...init,
    headers: {
      "Authorization": `Bearer ${env.GITHUB_TOKEN}`,
      "Accept": "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "superanalyst-worker",
      ...(init.headers || {}),
    },
  });
}

export default {
  async fetch(req, env) {
    const origin = req.headers.get("Origin") || "";
    const h = cors(origin, env);
    const allowed = (env.ALLOWED_ORIGIN || "https://perez849.github.io").split(",").map(s => s.trim());
    if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: h });
    if (!allowed.includes(origin)) return json({ error: "Origen no permitido" }, 403, h);
    if (!env.GITHUB_TOKEN) return json({ error: "Falta el secreto GITHUB_TOKEN en el Worker" }, 500, h);
    const workflow = env.WORKFLOW || "pages.yml";

    // Estado del último lanzamiento (para la barra de progreso de la web)
    if (req.method === "GET") {
      const since = Date.parse(new URL(req.url).searchParams.get("since") || "") || 0;
      const r = await gh(env, `/actions/workflows/${workflow}/runs?event=workflow_dispatch&per_page=5`);
      if (!r.ok) return json({ error: `GitHub respondió ${r.status}` }, 502, h);
      const run = ((await r.json()).workflow_runs || []).find(x => Date.parse(x.created_at) >= since - 90000);
      return json(run ? { status: run.status, conclusion: run.conclusion, url: run.html_url } : {}, 200, h);
    }
    if (req.method !== "POST") return json({ error: "Método no permitido" }, 405, h);

    const ip = req.headers.get("CF-Connecting-IP") || "?";
    const now = Date.now();
    const recent = (hits.get(ip) || []).filter(t => now - t < 3600_000);
    total = total.filter(t => now - t < 3600_000);
    if (recent.length >= Number(env.MAX_PER_HOUR || 6) || total.length >= Number(env.MAX_TOTAL_PER_HOUR || 30))
      return json({ error: "Demasiadas peticiones, espera un rato" }, 429, h);

    let body;
    try { body = await req.json(); } catch { return json({ error: "JSON no válido" }, 400, h); }
    const ticker = String(body.ticker || "").trim().toUpperCase();
    const profile = String(body.profile || "auto");
    const provider = String(body.provider || "auto");
    if (!TICKER_RE.test(ticker)) return json({ error: "Ticker no válido" }, 400, h);
    if (!PROFILES.includes(profile)) return json({ error: "Perfil no válido" }, 400, h);
    if (!PROVIDERS.includes(provider)) return json({ error: "Proveedor no válido" }, 400, h);

    recent.push(now); hits.set(ip, recent); total.push(now);
    const r = await gh(env, `/actions/workflows/${workflow}/dispatches`, {
      method: "POST",
      body: JSON.stringify({ ref: env.REF || "main", inputs: { ticker, profile, provider } }),
    });
    if (r.status !== 204) {
      const t = await r.text();
      return json({ error: `GitHub respondió ${r.status}`, detail: t.slice(0, 200) }, 502, h);
    }
    return json({ ok: true, ticker, dispatched_at: new Date().toISOString() }, 200, h);
  },
};
