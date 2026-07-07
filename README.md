# equityval — motor de valoración sector-aware

Genera una **nota de equity research completa** (HTML + PDF, estilo sell-side) a partir
del ticker. **No aplica el mismo método a todo**: clasifica la compañía por sector y corre
los modelos correctos para ese modelo de negocio, luego mezcla en un precio objetivo.

No es asesoramiento de inversión. Los inputs se derivan de forma mecánica; el juicio
fundamental lo pones tú (por eso todo es override-able).

## Selección de modelo por sector

| Perfil | Se detecta como | Modelos (peso) | Descuento |
|---|---|---|---|
| **Standard** | industrial, consumo, salud, software rentable | FCFF-DCF (55) · comps (30) · DDM (15) | WACC |
| **Bank** | banca, servicios financieros | **Residual income** (50) · DDM (30) · P/B–ROE (20) | Ke |
| **Insurance** | seguros, reaseguro | Residual income (45) · P/B–ROE (30) · DDM (25) | Ke |
| **REIT** | REIT, real estate | **P/FFO** (45) · AFFO-yield (35) · DDM (20) | Ke |
| **Utility** | utilities, eléctricas reguladas | **DDM multi-etapa** (45) · FCFF (30) · comps (25) | WACC |
| **Cyclical** | energía, materiales, minería, O&G | **EBITDA normalizado mid-cycle** (45) · FCFF (30) · comps (25) | WACC |
| **High-growth** | crecimiento >22% y margen <10% | FCFF horizonte largo (55) · EV/Sales (45) | WACC |

Los bancos y REITs **no usan FCFF** (para un banco la deuda es el negocio, no financiación;
en un REIT la depreciación no-cash distorsiona el GAAP). Los pesos se renormalizan sobre los
métodos que realmente producen valor (si no hay pares, comps se cae y se redistribuye).

Puedes forzar el perfil con `--profile bank` si la auto-clasificación falla.

## Instalación

```bash
pip install -r requirements.txt
# para PDF por CLI en local: instala wkhtmltopdf (o usa el botón "Save as PDF" del HTML)
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

Exporta a PDF con `--pdf` (wkhtmltopdf → weasyprint como fallback), o abre el HTML y pulsa
el botón flotante **Save as PDF** (usa el print CSS optimizado; se oculta al imprimir).

## Uso — GitHub Actions (a demanda, eliges tú el valor)

`.github/workflows/valuation.yml` se lanza a mano con **workflow_dispatch**:

1. Sube el repo a GitHub. (Opcional pero recomendado) añade el secret `FMP_API_KEY` en
   *Settings → Secrets and variables → Actions*.
2. Ve a la pestaña **Actions → Equity valuation (on-demand) → Run workflow**.
3. Escribe el **ticker** y, si quieres, ajusta perfil / Rf / ERP / prima país / terminal /
   horizonte / múltiplo de salida. Run.
4. Al terminar, descarga el artifact `valuation-<TICKER>` con el **HTML y el PDF**.

Sin secret usa yfinance automáticamente. wkhtmltopdf se instala en el runner, así que el PDF
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

**Coste de capital.** Ke = Rf + β·ERP (+ prima país + tamaño). β bottom-up: deslevera betas de
pares (Hamada `βu = βl/(1+(1-t)·D/E)`), promedia y relever­a al D/E propio. Kd = (Rf + spread
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

**Cíclicas.** Margen EBIT through-cycle × múltiplo EV/EBITDA de ciclo → normaliza extremos.

## Estructura

```
equityval/
  schema.py         esquema de datos unificado
  providers.py      FMP + yfinance
  sectors.py        clasificación + perfiles de valoración
  costofcapital.py  WACC / CAPM / Hamada / spread sintético
  assumptions.py    drivers de proyección + escenarios
  dcf.py            FCFF DCF + sensibilidad
  models.py         residual income, DDM, P/B–ROE, FFO, AFFO, normalizado
  comps.py          comps por múltiplos
  charts.py         football field, proyección, heatmap, bridge
  report.py         ensamblado HTML (condicional por perfil) + Save-as-PDF
  engine.py         orquestador sector-aware
  demo_data.py      compañía sintética para pruebas offline
valorar.py                       CLI (--pdf, --profile)
streamlit_app.py                 app interactiva
.github/workflows/valuation.yml  Action on-demand (workflow_dispatch)
```

## Límites

- yfinance trae fundamentales a veces incompletos; FMP es más fiable.
- Un único data source: ojo con restatements, one-offs y clasificaciones raras.
- La clasificación es por keywords de sector/industria; verifica el tag del informe y usa
  `--profile` si hace falta.
