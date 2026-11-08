# MIAX · Análisis de carteras

**Rentabilidad · Riesgo · Simulación · Informes**

[Español](#espanol) · [English](#english) | [Guía completa / Full guide](docs/uso.md)

---

<a id="espanol"></a>

## Español

De una lista de activos a un informe con gráficos: analiza tu cartera, compara su evolución
y explora escenarios con Monte Carlo. **Los mensajes y los informes se generan en español.**

[Empezar](#es-inicio) · [Uso](#es-uso) · [Opciones](#es-opciones) · [Parámetros](#es-parametros) · [Resultados](#es-resultados)

<a id="es-inicio"></a>

### Empieza en tres pasos

Necesitas **Python 3.11 o posterior**, Git e Internet. Con Yahoo Finance no necesitas claves.

**1. Descarga el proyecto.**

```bash
git clone https://github.com/Diegopasfer1909/tallerb1-t1-equipo7.git
cd tallerb1-t1-equipo7
```

**2. Crea y activa un entorno virtual.**

| Sistema | Crear | Activar |
| --- | --- | --- |
| Windows · PowerShell | `py -m venv .venv` | `.\.venv\Scripts\Activate.ps1` |
| macOS / Linux | `python3 -m venv .venv` | `source .venv/bin/activate` |

**3. Instala y genera tu primer informe.**

```bash
python -m pip install -e .
python src/main.py --assets cartera_ejemplo.txt --report
```

La cartera de ejemplo destina un **60 % a IBM y un 40 % a Microsoft**. La consola indica
la ruta del informe, guardado con sus imágenes en `informes/FECHA_HORA/`. Abre el `.md`
en un visor de Markdown; en VS Code, usa `Ctrl+Shift+V`.

<a id="es-uso"></a>

### Elige cómo indicar tu cartera

| Entrada | Ejemplo | Qué representa |
| --- | --- | --- |
| Pesos | `--assets IBM:0.6 MSFT:0.4` | Reparto objetivo 60/40 |
| Acciones | `--shares AAPL:10 SPY:5` | 10 acciones de Apple y 5 participaciones de SPY |
| Archivo | `--assets cartera_ejemplo.txt` | Un par `SÍMBOLO:PESO` por línea |

Los pesos suman **1**: escribe `0.6`, no `60`. Usa punto decimal. Con `--shares`, las
cantidades son positivas, se admiten fracciones y no se puede usar `--capital`; solo admite
Yahoo. Por defecto, los pesos se revisan mensualmente y las cantidades se mantienen.

```bash
# Cartera por acciones, expresada en euros
python src/main.py --shares AAPL:10 SPY:5 --currency EUR --report

# Informe histórico breve, sin Monte Carlo
python src/main.py --assets cartera_ejemplo.txt --report --report-sections summary warnings risk data

# Simulación de 126 sesiones con 5.000 escenarios
python src/main.py --assets cartera_ejemplo.txt --simulate --steps 126 --simulations 5000
```

<a id="es-opciones"></a>

### Opciones más útiles

| Opción | Qué cambia |
| --- | --- |
| `--start 2025-01-01 --end 2026-01-01` | Período histórico: inicio incluido, fin excluido |
| `--estimation-start 2015-01-01` | Inicio de los datos con los que Monte Carlo estima volatilidad y correlaciones; 5 años por defecto |
| `--capital 10000` | Capital inicial hipotético; 10.000 por defecto con pesos |
| `--currency EUR` | Convierte la cartera a euros |
| `--rebalance none` | Mantiene las posiciones sin reajustarlas |
| `--report` / `--plots-report` | Guarda el informe y gráficos / muestra los gráficos |
| `--report-detail full` | Muestra todo el informe sin desplegables |
| `--benchmark "^IBEX"` | Cambia la referencia; requiere informe o gráficos |
| `--output-dir resultados` | Guarda los informes en otra carpeta |
| `--return 0.08 --volatility 0.20` | Fija los supuestos de la simulación |
| `--broker none --rebalance-band 0` | Reajuste mensual sin comisiones ni banda de tolerancia |

`--report` incluye Monte Carlo por defecto. La consola aplica una tarifa IBKR orientativa
y una banda de 5 puntos al rebalanceo mensual. Abajo tienes [todos los parámetros con sus
valores por defecto](#es-parametros); también los muestra `python src/main.py --help`, y la
[guía de uso](docs/uso.md#es-parametros) añade más detalle.

<a id="es-parametros"></a>

### Todos los parámetros y sus valores por defecto

<details>
<summary><strong>Cartera y datos</strong></summary>

| Parámetro | Para qué sirve | Por defecto |
| --- | --- | --- |
| `--assets SÍMBOLO:PESO ...` | Pesos objetivo, o un archivo `.txt` | Obligatorio si no usas `--shares` |
| `--shares SÍMBOLO:ACCIONES ...` | Número de acciones, o un archivo `.txt`; solo con Yahoo | Alternativa a `--assets` |
| `--provider yahoo\|alpha_vantage` | Proveedor de precios | `yahoo` |
| `--start AAAA-MM-DD` | Inicio del análisis (incluido) | Hace 1 año con Yahoo; 120 días con Alpha Vantage |
| `--end AAAA-MM-DD` | Fin del análisis y de la estimación (excluido) | Hoy |
| `--currency EUR` | Divisa a la que convertir la cartera | La de los activos |
| `--capital 10000` | Capital inicial hipotético; no se usa con `--shares` | `10000` |
| `--rebalance monthly\|none` | Rebalanceo mensual o sin reajustes | `monthly` con `--assets`; `none` con `--shares` |

</details>

<details>
<summary><strong>Informe y gráficos</strong></summary>

| Parámetro | Para qué sirve | Por defecto |
| --- | --- | --- |
| `--report` | Guarda el informe en Markdown con sus gráficos | Desactivado |
| `--plots-report` | Muestra los gráficos en pantalla sin guardar archivos | Desactivado |
| `--report-detail compact\|full` | Secciones plegadas o todo desplegado; requiere `--report` | `compact` |
| `--report-sections CLAVE ...` | Secciones a incluir; requiere `--report` | Todas |
| `--output-dir CARPETA` | Carpeta de los informes; requiere `--report` | `informes/`, en la carpeta actual |
| `--benchmark SÍMBOLO` | Índice o fondo de comparación; requiere `--report` o `--plots-report` | `^GSPC` en USD; `^STOXX50E` en EUR |

Claves de `--report-sections`: `summary` (resumen), `warnings` (advertencias), `composition`
(composición), `returns` (rentabilidad), `risk` (riesgo), `risk_adjusted` (rentabilidad
ajustada al riesgo), `diversification` (diversificación), `market` (contexto de mercado),
`simulation` (Monte Carlo) y `data` (calidad de los datos). Si incluyes `simulation`, no hace
falta `--simulate`.

</details>

<details>
<summary><strong>Monte Carlo</strong></summary>

Requieren `--simulate` o un informe que incluya la sección `simulation`.

| Parámetro | Para qué sirve | Por defecto |
| --- | --- | --- |
| `--simulate` | Ejecuta la simulación y muestra su resumen | Desactivado |
| `--steps 252` | Horizonte, en sesiones de bolsa | Un año: `252`, o `365` si la cartera es solo cripto |
| `--simulations 10000` | Número de escenarios | `10000` |
| `--seed 42` | Semilla: repite los mismos escenarios | `42` |
| `--confidence 0.95` | Nivel del VaR y del CVaR | `0.95` |
| `--return 0.08` o `--return IBM:0.08 MSFT:0.1` | Rentabilidad anual esperada, común o por activo | Tipo libre de riesgo + prima por la parte en renta variable |
| `--equity-premium 0.045` | Prima de la renta variable sobre el tipo libre de riesgo | `0.045` (4,5 %) |
| `--volatility 0.2` o `--volatility IBM:0.2` | Volatilidad anual, común o por activo | Histórica |
| `--estimation-start AAAA-MM-DD` | Inicio de los precios con los que se estiman la volatilidad y las correlaciones | 5 años antes de `--end`, o `--start` si es anterior; con Alpha Vantage, `--start` |

**Cambiar el horizonte.** `--steps` se indica en sesiones: `21` es un mes, `126` medio año,
`504` dos años y `1260` cinco años. Por ejemplo:

```bash
python src/main.py --assets SAN.MC:0.5 ITX.MC:0.5 --simulate --steps 504
```

Escenarios × (sesiones + 1 + 2 × activos) no puede superar 20 millones: con 10.000
escenarios, el máximo ronda las 1.990 sesiones (unos 8 años). Para más, baja
`--simulations`.

</details>

<details>
<summary><strong>Comisiones del rebalanceo</strong></summary>

Solo se aplican con rebalanceo mensual.

| Parámetro | Para qué sirve | Por defecto |
| --- | --- | --- |
| `--broker` | Tarifa de partida: `ibkr` (0,05 % por orden, mínimo 3), `degiro` (2 por orden), `trade_republic` (1 por orden), `xtb` o `none` (sin comisiones) | `ibkr` |
| `--commission-rate 0.0005` | Comisión proporcional por orden | La del bróker |
| `--commission-fixed 2` | Comisión fija por orden | La del bróker |
| `--commission-min 3` | Comisión mínima por orden | La del bróker |
| `--commission-max 50` | Comisión máxima por orden | La del bróker |
| `--rebalance-band 0.05` | Solo se reajusta si algún peso se desvía más que esto; `0` reajusta cada mes | `0.05` (5 puntos) |
| `--max-order-cost 0.01` | Descarta las órdenes cuya comisión supere esta fracción de su importe | `0.01` (1 %) |

Los importes fijos se expresan en la divisa de la cartera.

</details>

<a id="es-resultados"></a>

### Un ejemplo con resultados

Este caso **ficticio**, sin rebalanceo, comisiones ni dividendos, muestra cómo se calcula el valor:

| Activo | Inversión inicial | Cambio del precio | Valor final |
| --- | --- | --- | --- |
| AAA | 6.000 USD | +20 % | 7.200 USD |
| BBB | 4.000 USD | +10 % | 4.400 USD |
| **Cartera** | **10.000 USD** | **+16 %** | **11.600 USD** |

Puedes [reproducirlo sin conexión y generar su informe](docs/uso.md#es-resultados).
Con datos reales, los resultados dependen de las fechas y precios descargados.
El informe reúne resumen, advertencias, composición, rentabilidad, riesgo, diversificación,
contexto de mercado y simulación. «No disponible» indica datos ausentes o una medida que
no se puede calcular; no significa cero.

**Claves opcionales.** Copia [`.env.example`](.env.example) a `.env`: `FRED_API_KEY` añade
inflación y otras referencias; `ALPHA_VANTAGE_API_KEY` habilita ese proveedor. Sin FRED,
el informe continúa con las medidas disponibles. Las simulaciones son escenarios, no predicciones.

**Sigue leyendo:** [guía y ayuda](docs/uso.md#espanol) · [decisiones del modelo](Decisiones.MD) ·
[arquitectura](ARQUITECTURA.md) · [desarrollo](docs/uso.md#es-desarrollo)

[↑ Español](#espanol) · [English ↓](#english)

---

<a id="english"></a>

## English

Turn a list of assets into a report with charts: analyze your portfolio, compare its
performance, and explore Monte Carlo scenarios. **Program messages and reports are in Spanish.**

[Get started](#en-start) · [Usage](#en-usage) · [Options](#en-options) · [Parameters](#en-parameters) · [Results](#en-results)

<a id="en-start"></a>

### Get started in three steps

You need **Python 3.11 or later**, Git, and Internet access. Yahoo Finance needs no API key.

**1. Download the project.**

```bash
git clone https://github.com/Diegopasfer1909/tallerb1-t1-equipo7.git
cd tallerb1-t1-equipo7
```

**2. Create and activate a virtual environment.**

| System | Create | Activate |
| --- | --- | --- |
| Windows · PowerShell | `py -m venv .venv` | `.\.venv\Scripts\Activate.ps1` |
| macOS / Linux | `python3 -m venv .venv` | `source .venv/bin/activate` |

**3. Install and generate your first report.**

```bash
python -m pip install -e .
python src/main.py --assets cartera_ejemplo.txt --report
```

The sample portfolio allocates **60% to IBM and 40% to Microsoft**. The terminal prints
the report path under `informes/DATE_TIME/`, alongside its images. Open the `.md` in a
Markdown viewer; in VS Code, use `Ctrl+Shift+V`.

<a id="en-usage"></a>

### Choose your portfolio input

| Input | Example | Meaning |
| --- | --- | --- |
| Weights | `--assets IBM:0.6 MSFT:0.4` | Target allocation of 60/40 |
| Shares | `--shares AAPL:10 SPY:5` | 10 Apple shares and 5 SPY units |
| File | `--assets cartera_ejemplo.txt` | One `SYMBOL:WEIGHT` pair per line |

Weights must sum to **1**: use `0.6`, not `60`, with decimal points. With `--shares`,
quantities must be positive, fractions are accepted, and `--capital` is unavailable;
Yahoo only. By default, weights are reviewed monthly and share quantities stay fixed.

```bash
# Share-based portfolio expressed in euros
python src/main.py --shares AAPL:10 SPY:5 --currency EUR --report

# Short historical report without Monte Carlo
python src/main.py --assets cartera_ejemplo.txt --report --report-sections summary warnings risk data

# Simulate 126 sessions with 5,000 scenarios
python src/main.py --assets cartera_ejemplo.txt --simulate --steps 126 --simulations 5000
```

<a id="en-options"></a>

### Most useful options

| Option | What it changes |
| --- | --- |
| `--start 2025-01-01 --end 2026-01-01` | Historical interval: inclusive start, exclusive end |
| `--estimation-start 2015-01-01` | Start of the data Monte Carlo uses to estimate volatility and correlations; 5 years by default |
| `--capital 10000` | Initial hypothetical capital; 10,000 by default with weights |
| `--currency EUR` | Converts the portfolio to euros |
| `--rebalance none` | Keeps positions without rebalancing |
| `--report` / `--plots-report` | Saves the report and charts / displays charts |
| `--report-detail full` | Expands all report sections |
| `--benchmark "^IBEX"` | Changes the benchmark; requires a report or charts |
| `--output-dir resultados` | Saves reports to a different parent folder |
| `--return 0.08 --volatility 0.20` | Sets simulation assumptions |
| `--broker none --rebalance-band 0` | Monthly rebalancing without commissions or a tolerance band |

`--report` includes Monte Carlo by default. The CLI applies an illustrative IBKR commission
schedule and a 5-percentage-point band to monthly rebalancing. Below are [all parameters and
their defaults](#en-parameters); `python src/main.py --help` shows them too, and the
[user guide](docs/uso.md#en-parameters) adds more detail.

<a id="en-parameters"></a>

### All parameters and defaults

<details>
<summary><strong>Portfolio and data</strong></summary>

| Parameter | Purpose | Default |
| --- | --- | --- |
| `--assets SYMBOL:WEIGHT ...` | Target weights, or a `.txt` file | Required unless you use `--shares` |
| `--shares SYMBOL:SHARES ...` | Number of shares, or a `.txt` file; Yahoo only | Alternative to `--assets` |
| `--provider yahoo\|alpha_vantage` | Price provider | `yahoo` |
| `--start YYYY-MM-DD` | Start of the analysis (inclusive) | 1 year ago with Yahoo; 120 days with Alpha Vantage |
| `--end YYYY-MM-DD` | End of the analysis and the estimation (exclusive) | Today |
| `--currency EUR` | Currency to convert the portfolio into | The assets' currency |
| `--capital 10000` | Hypothetical initial capital; not used with `--shares` | `10000` |
| `--rebalance monthly\|none` | Monthly rebalancing or none | `monthly` with `--assets`; `none` with `--shares` |

</details>

<details>
<summary><strong>Report and charts</strong></summary>

| Parameter | Purpose | Default |
| --- | --- | --- |
| `--report` | Saves the Markdown report with its charts | Off |
| `--plots-report` | Displays the charts without saving files | Off |
| `--report-detail compact\|full` | Collapsible or fully expanded sections; requires `--report` | `compact` |
| `--report-sections KEY ...` | Sections to include; requires `--report` | All |
| `--output-dir FOLDER` | Reports folder; requires `--report` | `informes/` under the current folder |
| `--benchmark SYMBOL` | Comparison index or fund; requires `--report` or `--plots-report` | `^GSPC` for USD; `^STOXX50E` for EUR |

`--report-sections` keys: `summary`, `warnings`, `composition`, `returns`, `risk`,
`risk_adjusted`, `diversification`, `market`, `simulation` (Monte Carlo) and `data` (data
quality). Including `simulation` makes `--simulate` unnecessary.

</details>

<details>
<summary><strong>Monte Carlo</strong></summary>

These require `--simulate` or a report that includes the `simulation` section.

| Parameter | Purpose | Default |
| --- | --- | --- |
| `--simulate` | Runs the simulation and prints its summary | Off |
| `--steps 252` | Horizon, in trading sessions | One year: `252`, or `365` for crypto-only portfolios |
| `--simulations 10000` | Number of scenarios | `10000` |
| `--seed 42` | Seed: repeats the same scenarios | `42` |
| `--confidence 0.95` | VaR and CVaR level | `0.95` |
| `--return 0.08` or `--return IBM:0.08 MSFT:0.1` | Expected annual return, common or per asset | Risk-free rate plus a premium on the equity portion |
| `--equity-premium 0.045` | Equity premium over the risk-free rate | `0.045` (4.5%) |
| `--volatility 0.2` or `--volatility IBM:0.2` | Annual volatility, common or per asset | Historical |
| `--estimation-start YYYY-MM-DD` | Start of the prices used to estimate volatility and correlations | 5 years before `--end`, or `--start` if earlier; with Alpha Vantage, `--start` |

**Changing the horizon.** `--steps` is in sessions: `21` is one month, `126` half a year,
`504` two years and `1260` five years. For example:

```bash
python src/main.py --assets SAN.MC:0.5 ITX.MC:0.5 --simulate --steps 504
```

Scenarios × (sessions + 1 + 2 × assets) cannot exceed 20 million: with 10,000 scenarios the
maximum is about 1,990 sessions (around 8 years). For more, lower `--simulations`.

</details>

<details>
<summary><strong>Rebalancing commissions</strong></summary>

Only applied with monthly rebalancing.

| Parameter | Purpose | Default |
| --- | --- | --- |
| `--broker` | Starting schedule: `ibkr` (0.05% per order, minimum 3), `degiro` (2 per order), `trade_republic` (1 per order), `xtb` or `none` (no commissions) | `ibkr` |
| `--commission-rate 0.0005` | Proportional commission per order | The broker's |
| `--commission-fixed 2` | Fixed commission per order | The broker's |
| `--commission-min 3` | Minimum commission per order | The broker's |
| `--commission-max 50` | Maximum commission per order | The broker's |
| `--rebalance-band 0.05` | Rebalances only if a weight drifts more than this; `0` rebalances every month | `0.05` (5 points) |
| `--max-order-cost 0.01` | Skips orders whose commission exceeds this fraction of their amount | `0.01` (1%) |

Fixed amounts are expressed in the portfolio currency.

</details>

<a id="en-results"></a>

### A worked example

This **synthetic** case, without rebalancing, commissions, or dividends, shows the valuation:

| Asset | Initial allocation | Price change | Final value |
| --- | --- | --- | --- |
| AAA | 6,000 USD | +20% | 7,200 USD |
| BBB | 4,000 USD | +10% | 4,400 USD |
| **Portfolio** | **10,000 USD** | **+16%** | **11,600 USD** |

[Reproduce it offline and generate its report](docs/uso.md#en-results).
With market data, results depend on the dates and downloaded prices. The report includes
a summary, warnings, composition, returns, risk, diversification, market context, and simulation.
“No disponible” indicates missing data or an undefined metric; it does not mean zero.

**Optional keys.** Copy [`.env.example`](.env.example) to `.env`: `FRED_API_KEY` adds inflation
and other references; `ALPHA_VANTAGE_API_KEY` enables that provider. Without FRED, available
metrics still work. Simulations describe scenarios, not predictions.

**Read more:** [guide and help](docs/uso.md#english) · [model decisions, in Spanish](Decisiones.MD) ·
[architecture](ARQUITECTURA.md) · [development](docs/uso.md#en-development)

[↑ English](#english) · [Leer en español](#espanol)
