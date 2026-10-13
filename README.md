# equityval — motor de valoración sector-aware

Genera una **nota de equity research completa** (HTML + PDF de ~10 páginas, estilo sell-side) a
partir del ticker, con un resumen de una página (*tear sheet*) lleno de gráficos y tablas. **No aplica el mismo método a todo**: clasifica la compañía por sector y corre
los modelos correctos para ese modelo de negocio, luego mezcla en un precio objetivo.

No es asesoramiento de inversión. Los inputs se derivan de forma mecánica; el juicio
fundamental lo pones tú (por eso todo es override-able).

## Cómo se construye el precio objetivo

El motor ya **no** valora con un único modelo. Cada compañía se clasifica por sector y se
valora con varias **lentes** independientes que se triangulan, como hace una mesa de research:

| Perfil | Se detecta como | Lentes (peso base) |
|---|---|---|
| **Standard** | industrial, consumo, salud, tech | DCF FCFF (35) · P/E fwd (30) · EV/EBITDA fwd (25) · DDM (10) |
| **Bank** | banca, serv. financieros | P/B–ROE (35) · residual income (30) · P/E fwd (25) · DDM (10) |
| **Insurance** | seguros | P/B–ROE (30) · residual income (30) · P/E fwd (30) · DDM (10) |
| **REIT** | REIT, real estate | P/FFO (40) · AFFO yield (30) · DDM (15) · EV/EBITDA (15) |
| **Utility** | utilities reguladas | P/E fwd (30) · DDM (25) · DCF (25) · EV/EBITDA (20) |
| **Cyclical** | energía, minería, materiales | EBITDA mid-cycle (30) · DCF (30) · EV/EBITDA fwd (25) · P/E fwd (15) |
| **High-growth** | crecimiento >22 % y margen <10 % | EV/Sales (35) · DCF (30) · P/E fwd (20) · P/B (15) |

Los pesos se renormalizan sobre las lentes que producen valor. Después:

1. **Múltiplos forward (lentes relativas).** Múltiplo objetivo × EPS/EBITDA/ventas del consenso
   (EPS NTM = media de FY+1 y FY+2). El múltiplo parte de la mediana de pares (60 %) y de una
   tabla sectorial de referencia (40 %, `equityval/reference.py`; sirve sola si no hay pares) y
   se ajusta por crecimiento *duradero*, apalancamiento y **durabilidad de los beneficios**: si
   el EPS forward es muy superior a lo que la compañía ha ganado históricamente (memoria,
   mineras, picos de ciclo) el múltiplo se reduce, porque el mercado paga menos por picos.
2. **DCF acotado.** 10 años: consenso para los 1–2 primeros, después el crecimiento **decae
   geométricamente** hacia el terminal y los márgenes **revierten a la media** (60 % en
   cíclicas, 30 % en compounders); el margen implícito del consenso se limita a 1,5× el máximo
   histórico. Ya no se puede extrapolar un +100 % durante una década.
3. **Guardrails.** Una lente fuera de 0,2×–5× el precio se excluye; si se aleja >2,2× de la
   mediana del resto se pondera un 60 % menos; el objetivo publicado se limita a 0,4×–2,5×; y
   si el modelo no puede defender un número (menos de 2 lentes, o resultado forzado por un
   guardrail) el informe sale **NOT RATED** en lugar de inventar un rating. Todo queda escrito.
4. **Objetivo a 12 meses.** `PT = Valor justo × (1 + Ke) − dividendos`, con bear/bull de los
   rangos de las lentes.
5. **Contraste con la calle.** Si hay consenso, el objetivo se ancla ligeramente a él (peso
   ≤ 30 %, escalado por nº de analistas; `--street-weight 0` lo desactiva). Siempre se muestran
   por separado el objetivo del modelo, el de la calle y la divergencia.
6. **Confianza** (High/Medium/Low) por nº de lentes, dispersión, acuerdo con la calle, peso del
   valor terminal y banderas de calidad de datos.

Rating a partir de la rentabilidad total esperada a 12 m: ≥ +15 % OVERWEIGHT · +5 % ADD ·
±5 % NEUTRAL · −5 % REDUCE · ≤ −15 % UNDERWEIGHT.

Los bancos y REITs **no usan FCFF** (para un banco la deuda es el negocio; en un REIT la
depreciación no-cash distorsiona el GAAP). Puedes forzar el perfil con `--profile bank`.

## Instalación

```bash
pip install -r requirements.txt
# para PDF por CLI: Chrome/Chromium (o el botón "Save as PDF" del HTML)
```

## Uso — CLI

```bash
python valorar.py --demo --pdf                 # prueba offline, saca HTML + PDF
python valorar.py NVDA -o nvda.html            # yfinance, sin key
export FMP_API_KEY=tu_key                       # fundamentales mejores (free tier)
python valorar.py JPM --pdf                     # banco -> residual income
python valorar.py O   --pdf                     # REIT  -> FFO / AFFO
python valorar.py XOM --profile cyclical        # fuerza cíclica
python valorar.py CEG --erp 0.05 --terminal-growth 0.025 --exit-multiple 12 --pdf
python valorar.py SAN.MC --country-premium 0.012  # europea: prima país + divisa auto
```

Exporta a PDF con `--pdf` (Chrome headless → weasyprint), o abre el HTML y pulsa
el botón flotante **Save as PDF** (usa el print CSS optimizado; se oculta al imprimir).

## Uso — GitHub Actions (a demanda, eliges tú el valor)

`.github/workflows/valuation.yml` se lanza a mano con **workflow_dispatch**:

1. Sube el repo a GitHub. (Opcional pero recomendado) añade el secret `FMP_API_KEY` en
   *Settings → Secrets and variables → Actions*.
2. Ve a la pestaña **Actions → Equity valuation (on-demand) → Run workflow**.
3. Escribe el **ticker** y, si quieres, ajusta perfil / Rf / ERP / prima país / terminal /
   horizonte / múltiplo de salida. Run.
4. Al terminar, descarga el artifact `valuation-<TICKER>` con el **HTML y el PDF**.

Sin secret usa yfinance automáticamente. Chrome ya viene en el runner, así que el PDF
sale sin tocar nada.



## Modelo Excel con fórmulas vivas (`--xlsx`)

`python valorar.py NVDA --xlsx` genera un **workbook de trabajo con fórmulas dentro de las
celdas**, convenciones de banca (inputs en azul, fórmulas en negro, links entre hojas en verde,
negativos entre paréntesis):

- **Assumptions** — todos los inputs: precio, acciones, deuda, Rf, ERP, beta, tax, terminal g,
  y los drivers año a año (crecimiento, margen, D&A%, capex%, NWC%). Cambia cualquier celda
  azul y el modelo entero recalcula.
- **WACC** — build CAPM por fórmula.
- **Model** — históricos reportados (sombreados) + proyección por fórmulas encadenadas.
- **DCF** — descuento mid-year, valor terminal consistente (TV = NOPATn·(1+g)·(1−g/ROIC)/(WACC−g)),
  puente EV→equity→por acción.
- **Sensitivity** — rejilla 5×5 WACC×g donde **cada celda re-ejecuta el DCF completo** en vivo
  (SUMPRODUCT sobre los FCFF + terminal local).
- **IS / BS / CF (reported)** — los estados completos tal cual los reporta la fuente de datos.

Verificado: cero errores de fórmula y los valores del Excel cuadran al céntimo con el motor
Python (incl. la rejilla de sensibilidad). Los workflows de GitHub suben el .xlsx junto al
HTML/PDF, y la web de Pages enlaza "XLS" en cada tarjeta.

Nota: la hoja **Target Price** del Excel reproduce la triangulación con pesos editables
(valor justo, objetivo del modelo y objetivo publicado son fórmulas vivas).

Nota: en Excel el terminal g y los drivers anuales son inputs independientes (como en un
modelo de banca); en el motor Python cambiar el terminal también mueve el fade del crecimiento.

## Web en GitHub Pages (biblioteca + generador de PDFs)

Pages solo sirve estáticos, así que el patrón es: **el Action genera el informe y lo publica
en `/docs`, y Pages lo sirve**. La web (`docs/index.html`, se autoconstruye con
`scripts/build_index.py`) lista los informes y trae un panel **«Genera un informe en PDF desde la
web»**: escribes un ticker, la página lanza el workflow, espera 2–4 min y ofrece PDF, HTML y Excel.

**Alta (una vez):**
1. Sube el repo a GitHub. (Opcional) añade el secret `FMP_API_KEY` en *Settings → Secrets and
   variables → Actions*.
2. *Settings → Pages → Build and deployment → Source: Deploy from a branch*, rama `main`,
   carpeta **`/docs`**. Tu web queda en `https://<usuario>.github.io/<repo>/`.
3. *Settings → Actions → General → Workflow permissions*: **Read and write permissions**.

**Cómo se lanza la generación desde la web** (la web es estática y necesita permiso en GitHub):

| Modo | Qué hace | Configuración |
|---|---|---|
| **Worker** (recomendado) | Un Worker de Cloudflare guarda el token y lanza el workflow; cualquiera puede generar sin cuenta de GitHub, con límites por IP | `worker/README.md` → pon su URL en `docs/assets/config.js` (`api`) |
| **Token en tu navegador** | Pegas un token fino (solo *Actions: Read and write* sobre este repo); se guarda en `localStorage` y solo viaja a `api.github.com` | desde el propio panel, «Conexión con GitHub» |
| **Manual** | El botón te lleva a *Actions → Run workflow* y la página espera aquí al resultado | nada |

El workflow valida el ticker (`^[A-Za-z0-9.^=-]{1,12}$`) y nunca lo interpola en el shell; el
Worker valida ticker, perfil y proveedor con listas cerradas y limita peticiones.

**Cada valoración, a mano:** *Actions → "Equity valuation → Pages" → Run workflow* con el ticker.
Genera `docs/reports/<TICKER>.html` + `.pdf` + `.xlsx` + `.json`, reconstruye el índice y hace commit.
Además, dentro de cada informe el botón **Save as PDF** guarda el PDF desde el navegador al instante.

> Si prefieres no acumular informes en el repo, usa `valuation.yml`, que deja HTML+PDF+Excel como
> *artifact* descargable (HTML autocontenido, con las fuentes incrustadas) sin tocar `/docs`.

## Uso — app Streamlit

```bash
streamlit run streamlit_app.py
```

Ticker + sliders (Rf/ERP/país/terminal/horizonte); el informe se regenera en vivo y hay botón
de descarga del HTML.

## Uso — librería

```python
from equityval import value_company, ValuationConfig
res = value_company("JPM", cfg=ValuationConfig(erp=0.05))
print(res["profile"], res["target"], res["upside"], list(res["methods"]))
open("jpm.html","w").write(res["html"])
```

`res` trae todo lo intermedio: `profile`, `spec`, `wacc`, `methods` (dict de resultados por
modelo), `dcf`, `scenarios`, `sens`, `comps`, `blend`.

## Metodología

**Coste de capital.** Ke = Rf + β·ERP (+ prima país + tamaño). β: mezcla 50/50 de la beta de regresión ajustada (Blume, 0,67·β+0,33) y la beta de industria
relevereada (Hamada `βl = βu·(1+(1-t)·D/E)`) al D/E propio, acotada a 0,7–1,9. Kd = (Rf + spread
sintético)·(1−t), spread desde interest coverage (rejilla tipo Damodaran). WACC con pesos a
mercado (equity) y libros (deuda). Los perfiles de balance (banco/seguro/REIT) descuentan a **Ke**,
no a WACC.

**FCFF-DCF.** FCFF = EBIT·(1−t) + D&A − Capex − ΔNWC, mid-year, TV Gordon + cross-check por
múltiplo de salida, puente EV − deuda neta − minoritarios.

**Residual income.** Valor = book value + Σ PV[(ROE − Ke)·BV] + PV continuación. El ancla
correcta para un banco.

**DDM multi-etapa.** Dividendos crecen del ritmo retención×ROE y hacen fade al terminal, a Ke.

**P/B justificado.** P/B = (ROE − g)/(Ke − g). Un banco que gana su Ke vale exactamente libros.

**REIT.** P/FFO (FFO = NI + depreciación) y AFFO capitalizado como perpetuidad creciente.

**Cíclicas.** Margen EBIT through-cycle × múltiplo EV/EBITDA de ciclo → normaliza extremos; los
múltiplos forward se escalan por la durabilidad de los beneficios.

## Estructura

```
equityval/
  schema.py         esquema de datos unificado
  providers.py      FMP + yfinance (+ pares, consenso, objetivos de la calle)
  offline.py        instantáneas JSON de Yahoo -> mismo parser de producción, sin red
  sectors.py        clasificación + perfiles y pesos de lentes
  reference.py      múltiplos sectoriales de referencia, betas, pares curados
  estimates.py      EPS/ventas forward, ciclicidad y durabilidad de beneficios
  assumptions.py    drivers del DCF (decaimiento geométrico, reversión de márgenes)
  costofcapital.py  WACC / CAPM / beta Blume + industria / spread sintético
  dcf.py            FCFF DCF + sensibilidad + DCF inverso
  models.py         residual income, DDM, P/B–ROE, FFO, AFFO, normalizado
  lenses.py         cada lente con rango y traza de auditoría
  triangulate.py    mezcla, guardrails, objetivo a 12m, calle, confianza, NOT RATED
  theme.py          tokens del diseño Reloj de inversión
  design.py         hoja de estilos compartida (informes + biblioteca), fuentes y reglas de impresión
  clockdata.py      enlace con el Reloj de inversión: fase, probabilidades, tilt sectorial, playbook, ETF
  data/reloj_snapshot.json  copia versionada de los datos del Reloj (offline / sin red)
  analysis.py       estados financieros, ROE/ROIC/DuPont, Piotroski, Altman Z, Sloan, capital circulante, scorecard
  charts.py         esfera, waterfall, football field, plano crecimiento×inflación, radar, precio (SVG)
  notectx.py        prepara todos los números ya formateados para la plantilla
  note_template.py  plantilla Jinja del informe (tear sheet + secciones)
  report.py         ensambla el informe HTML + Save-as-PDF
  excel_export.py   modelo Excel con fórmulas vivas (+ hoja Target Price)
  engine.py         orquestador
tests/              regresión con instantáneas reales (MU, SNDK, NVDA, CEG, GFI, UEC) y test de la web
worker/             Worker de Cloudflare que lanza la generación desde la web
docs/               web publicada: index.html, assets/ (css, js, fuentes), reports/
valorar.py                       CLI (--pdf, --xlsx, --profile, --snapshot, --street-weight)
streamlit_app.py                 app interactiva
.github/workflows/               valuation.yml, pages.yml, tests.yml
```

## El informe

Una **hoja resumen** (se imprime en una página A4) y siete secciones técnicas:

| Bloque | Qué contiene |
|---|---|
| Tear sheet | esfera del precio objetivo, puente precio → objetivo, KPIs con sparklines, valor por lente (football field), escenarios bear/base/bull con probabilidades, ingresos/margen, BPA, caja y ROIC vs WACC |
| Resumen II | múltiplos vs sector (bullets + tabla), lectura del **Reloj de inversión**, visión de inversión, riesgos y scorecard de seis ejes |
| Veredicto | tesis, cómo se construye el objetivo lente a lente, guardrails y confianza |
| Lentes | cada input de cada lente, para poder discutirlo |
| Financieros | cuenta de resultados, balance y flujos (histórico + estimado), ROE/ROA/ROIC, DuPont, Piotroski, Altman, Sloan, DSO/DIO/DPO, múltiplos por año, calidad de beneficios |
| DCF | drivers, FCFF año a año, gráficos, sensibilidad WACC × g, comprobaciones de la salida |
| Ciclo | plano crecimiento × inflación, probabilidades de fase, retorno excedente del sector por fase, playbook y ETF |
| Factores y riesgos | qué mueve la acción, palancas valoradas en $ por acción, riesgos y método |

## Vínculo con el Reloj de inversión

Los informes leen el **[Reloj de inversión](https://perez849.github.io/reloj-inversion/)**
(`Perez849/reloj-inversion`), no un mapa sectorial genérico: la fase actual y su convicción, las
probabilidades de las cuatro fases, y lo que **el sector de la compañía ha pagado históricamente en
cada fase** (retorno anual, exceso vs el mercado EE.UU. encogido, t de Newey-West, tasa de acierto,
fiabilidad). De ahí salen el *tilt* (Σ probabilidad × exceso del sector), el peso del sector en el
playbook de la fase y el peso de la compañía dentro del ETF sectorial. Es contexto: **no mueve el
precio objetivo**.

- Con red se descarga `data.json` del Reloj; sin red (o con `EQUITYVAL_OFFLINE=1`) se usa
  `equityval/data/reloj_snapshot.json`. Refresca la copia con `python scripts/refresh_reloj.py`.
- Si una compañía no tiene activo equivalente en el Reloj, el campo queda vacío (no se inventa nada);
  si no hay datos del Reloj, la sección del ciclo simplemente no aparece.
- La biblioteca muestra el mismo plano del Reloj y, en cada tarjeta, el sesgo del ciclo del sector.

## Diseño: Reloj de inversión

Informes y web comparten el sistema visual del proyecto
[reloj-inversion](https://github.com/Perez849/reloj-inversion): papel crema, tinta, un único
acento ocre, Fraunces / Inter / IBM Plex Mono (alojadas en `docs/assets/fonts`, licencia OFL),
los cuatro colores de fase (verde bosque, ocre, terracota, índigo) y un único bloque oscuro para
"la respuesta". La firma de cada informe es una **esfera de valoración**: la aguja marca la
rentabilidad esperada a 12 m, el arco ocre el rango bear–bull y la "S" el consenso de la calle.

Todo sale de dos archivos: `equityval/theme.py` (tokens) y `equityval/design.py` (hoja de estilos
compartida, incluidas las reglas `@media print` que encajan el resumen en una página). Cambiar ahí
reestiliza informes y biblioteca.

## Offline y tests

```bash
python valorar.py --snapshot tests/fixtures/MU.json --pdf --xlsx   # reproducible, sin red
python -m pytest tests -q
```

El PDF se genera con Chrome/Chromium headless (`CHROME_BIN` para forzarlo; el runner de GitHub ya
lo trae), con weasyprint como alternativa. wkhtmltopdf ya no se usa: no entiende variables CSS.

## Límites

- yfinance trae fundamentales a veces incompletos; FMP es más fiable.
- Un único data source: ojo con restatements, one-offs y clasificaciones raras.
- La clasificación es por keywords de sector/industria; verifica el tag del informe y usa
  `--profile` si hace falta.
