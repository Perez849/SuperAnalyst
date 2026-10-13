# Worker: generar informes y PDF desde la web

La web de SuperAnalyst (GitHub Pages) es estática y no puede guardar un token. Este Worker lo
guarda como secreto y lanza el workflow **Equity valuation → Pages** cuando alguien pulsa
«Generar PDF». El workflow calcula la valoración, genera HTML + PDF + Excel y los publica en
`docs/`; la web espera al resultado y ofrece la descarga.

## Despliegue (una vez, ~5 minutos)

1. Crea un **token fino** en <https://github.com/settings/personal-access-tokens/new>:
   *Repository access → Only select repositories → `Perez849/SuperAnalyst`*;
   *Permissions → Repository permissions → **Actions: Read and write*** (nada más).
2. Despliega:
   ```
   cd worker
   npx wrangler login
   npx wrangler secret put GITHUB_TOKEN      # pega el token del paso 1
   npx wrangler deploy                       # te da https://superanalyst-generar.<cuenta>.workers.dev
   ```
3. Pon esa URL en `docs/assets/config.js` (`api: "https://…"`) y haz push (a `main`).

## Qué comprueba el Worker
- Solo atiende peticiones desde `ALLOWED_ORIGIN`.
- Ticker (`^[A-Za-z0-9.^=-]{1,12}$`), perfil y proveedor se validan con listas cerradas.
- Límite por IP (`MAX_PER_HOUR`) y global (`MAX_TOTAL_PER_HOUR`), en memoria (best-effort).
- El workflow vuelve a validar el ticker por su cuenta.

## Sin Worker
Si `api` está vacío, la web usa un token de GitHub que pegues en tu navegador (se guarda solo
en `localStorage`) o te lleva a la pestaña *Actions* para lanzarlo a mano.
