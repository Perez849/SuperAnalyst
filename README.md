# equityval — motor de valoración sector-aware

Genera una **nota de equity research completa** (HTML + PDF, estilo sell-side) a partir
del ticker. **No aplica el mismo método a todo**: clasifica la compañía por sector y corre
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
# para PDF por CLI: Chrome/Chromium (o wkhtmltopdf), o el botón "Save as PDF" del HTML
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

Exporta a PDF con `--pdf` (Chrome headless → wkhtmltopdf → weasyprint), o abre el HTML y pulsa
el botón flotante **Save as PDF** (usa el print CSS optimizado; se oculta al imprimir).

## Uso — GitHub Actions (a demanda, eliges tú el valor)

`.github/workflows/valuation.yml` se lanza a mano con **workflow_dispatch**:

1. Sube el repo a GitHub. (Opcional pero recomendado) añade el secret `FMP_API_KEY` en
   *Settings → Secrets and variables → Actions*.
2. Ve a la pestaña **Actions → Equity valuation (on-demand) → Run workflow**.
3. Escribe el **ticker** y, si quieres, ajusta perfil / Rf / ERP / prima país / terminal /
   horizonte / múltiplo de salida. Run.
4. Al terminar, descarga el artifact `valuation-<TICKER>` con el **HTML y el PDF**.

Sin secret usa yfinance automáticamente. Chrome ya viene en el runner (y wkhtmltopdf se instala si faltara), así que el PDF
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

## Web en GitHub Pages (biblioteca de valoraciones)

Pages solo sirve estáticos, así que el patrón es: **el Action genera el informe y lo publica
en `/docs`, y Pages lo sirve**. La web se va llenando con un índice que se autoconstruye.

**Alta (una vez):**
1. Sube el repo a GitHub. (Opcional) añade el secret `FMP_API_KEY` en *Settings → Secrets and
   variables → Actions*.
2. *Settings → Pages → Build and deployment → Source: Deploy from a branch*, rama `main`,
   carpeta **`/docs`**. Guarda. Tu web queda en `https://<usuario>.github.io/<repo>/`.
3. *Settings → Actions → General → Workflow permissions*: marca **Read and write permissions**
   (para que el workflow pueda commitear en `/docs`).

**Cada valoración:**
1. Pestaña **Actions → "Equity valuation → Pages" → Run workflow**.
2. Escribe el **ticker** (y ajusta perfil / Rf / ERP / país / terminal si quieres). Run.
3. El workflow genera `docs/reports/<TICKER>.html` + `.pdf` + `.json`, reconstruye
   `docs/index.html` y hace commit. En ~1 min tu web muestra la nueva tarjeta con rating,
   precio objetivo y upside, enlazando al informe y al PDF.

El repo ya trae un `docs/` de ejemplo con el informe DEMO; bórralo cuando quieras.

> Si prefieres no acumular informes en el repo, usa el otro workflow (`valuation.yml`), que
> deja HTML+PDF como *artifact* descargable sin tocar `/docs`.

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
  theme.py          tokens de diseño "Investment Clock" (un único sitio para re-skin)
  charts.py         esfera de valoración, rueda de fases, football field (SVG)
  report.py         informe HTML + Save-as-PDF
  excel_export.py   modelo Excel con fórmulas vivas (+ hoja Target Price)
  engine.py         orquestador
tests/              regresión con instantáneas reales (MU, SNDK, NVDA, CEG, GFI, UEC)
valorar.py                       CLI (--pdf, --xlsx, --profile, --snapshot, --street-weight)
streamlit_app.py                 app interactiva
.github/workflows/               valuation.yml, pages.yml, tests.yml
```

## Diseño "Investment Clock"

Esfera de 270° con 12 horas como identidad: la aguja marca la rentabilidad esperada a 12 m,
el arco dorado es el rango bear–bull y el triángulo "S" el consenso de la calle. La rueda de
cuatro fases (Recovery → Overheat → Stagflation → Reflation) muestra en qué fases suele liderar
el sector de la compañía (mapa sectorial clásico de Merrill Lynch; es afinidad ilustrativa, no
una lectura macro actual). Pantalla oscura, impresión/PDF en claro. Todos los colores viven en
`equityval/theme.py`.

## Offline y tests

```bash
python valorar.py --snapshot tests/fixtures/MU.json --pdf --xlsx   # reproducible, sin red
python -m pytest tests -q
```

El PDF se genera con Chrome/Chromium headless si lo encuentra (`CHROME_BIN` para forzarlo),
con wkhtmltopdf y weasyprint como alternativas.

## Límites

- yfinance trae fundamentales a veces incompletos; FMP es más fiable.
- Un único data source: ojo con restatements, one-offs y clasificaciones raras.
- La clasificación es por keywords de sector/industria; verifica el tag del informe y usa
  `--profile` si hace falta.
