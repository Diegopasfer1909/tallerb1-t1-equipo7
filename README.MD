# MIAX · Análisis de carteras

**Rentabilidad · Riesgo · Simulación · Informes**

[Español](#espanol) · [English](#english) | [Guía completa / Full guide](docs/uso.md)

---

<a id="espanol"></a>

## Español

De una lista de activos a un informe con gráficos: analiza tu cartera, compara su evolución
y explora escenarios con Monte Carlo. **Los mensajes y los informes se generan en español.**

[Empezar](#es-inicio) · [Uso](#es-uso) · [Opciones](#es-opciones) · [Resultados](#es-resultados)

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
y una banda de 5 puntos al rebalanceo mensual. Consulta todos los parámetros y sus valores
por defecto en la [guía de uso](docs/uso.md#es-parametros) o con `python src/main.py --help`.

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

[Get started](#en-start) · [Usage](#en-usage) · [Options](#en-options) · [Results](#en-results)

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
schedule and a 5-percentage-point band to monthly rebalancing. See every option and default
in the [user guide](docs/uso.md#en-parameters) or run `python src/main.py --help`.

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
