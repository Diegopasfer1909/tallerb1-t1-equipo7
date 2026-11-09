# MIAX · Análisis de carteras

**Rentabilidad · Riesgo · Simulación · Informes**

[Español](#espanol) · [English](#english)

---

<a id="espanol"></a>

## Español

De una lista de activos a un informe con gráficos: analiza tu cartera, compara su evolución
y explora escenarios con Monte Carlo. **Los mensajes y los informes se generan en español.**

[Empezar](#es-inicio) · [Cartera](#es-cartera) · [Salidas](#es-salidas) ·
[`--simulate`](#es-simulate) · [`--plots-report`](#es-plots) · [`--report`](#es-report) ·
[Advertencias](#es-advertencias) · [Rebalanceo](#es-rebalanceo) · [Ejemplo](#es-ejemplo) · [Claves](#es-claves) ·
[Problemas](#es-problemas) · [Python y desarrollo](#es-desarrollo)

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
en un visor de Markdown; en VS Code, usa `Ctrl+Shift+V`. Todas las opciones también
aparecen con `python src/main.py --help`.

<a id="es-cartera"></a>

### 1. Define tu cartera

Elige **una** de estas formas:

| Entrada | Ejemplo | Qué representa |
| --- | --- | --- |
| Pesos | `--assets IBM:0.6 MSFT:0.4` | Reparto objetivo 60/40 de un capital hipotético |
| Acciones | `--shares AAPL:10 SPY:5` | 10 acciones de Apple y 5 participaciones de SPY |
| Archivo | `--assets cartera_ejemplo.txt` | Un par `SÍMBOLO:PESO` por línea; con `--shares`, cantidades |

- **Pesos:** entre 0 y 1 y deben sumar **1**: escribe `0.6`, no `60`. Usa punto decimal.
- **Acciones:** cantidades positivas; se admiten fracciones como `MSFT:2.5`. Solo con Yahoo y
  sin `--capital`.
- **Archivos `.txt`:** en UTF-8, con comentarios `#` y líneas vacías; sin símbolos repetidos.
- **Símbolos:** los de Yahoo, por ejemplo `IBM`, `SAN.MC`, `^IBEX` o `BTC-USD`.

Estas opciones valen para cualquier salida:

| Parámetro | Para qué sirve | Por defecto |
| --- | --- | --- |
| `--provider yahoo\|alpha_vantage` | Proveedor de precios | `yahoo` |
| `--start AAAA-MM-DD` | Inicio del análisis (incluido) | Hace 1 año con Yahoo; 120 días con Alpha Vantage |
| `--end AAAA-MM-DD` | Fin del análisis (excluido) | Hoy |
| `--currency EUR` | Divisa a la que convertir la cartera | La de los activos |
| `--capital 10000` | Capital inicial hipotético; no se usa con `--shares` | `10000` |
| `--rebalance monthly\|none` | Rebalanceo mensual o sin reajustes ([comisiones](#es-rebalanceo)) | `monthly` con `--assets`; `none` con `--shares` |
| `--download-workers N` | Activos que se descargan a la vez, de 1 a 4 ([descargas](#es-descargas)) | `1` |

Solo se usan las fechas con precio de todos los activos; los huecos no se rellenan.

<a id="es-salidas"></a>

### 2. Elige qué quieres obtener

Sin opciones de salida, el programa muestra las posiciones en la consola. Añade una o varias:

| Opción | Qué obtienes |
| --- | --- |
| *(ninguna)* | Posiciones, pesos y valor de la cartera en la consola |
| [`--simulate`](#es-simulate) | Simulación de Monte Carlo y su resumen en la consola |
| [`--plots-report`](#es-plots) | Gráficos en pantalla, sin guardar archivos |
| [`--report`](#es-report) | Informe en Markdown con sus gráficos; **incluye Monte Carlo** |

Se pueden combinar, por ejemplo `--report --plots-report`.

<a id="es-simulate"></a>

#### `--simulate` · Simulación de Monte Carlo

Simula miles de escenarios para la cartera a partir de su valor actual y muestra el valor
final medio, los percentiles, la probabilidad de pérdida, el VaR y el CVaR. Estas opciones
también se aplican a la sección de Monte Carlo de `--report`.

| Parámetro | Para qué sirve | Por defecto |
| --- | --- | --- |
| `--steps 252` | Horizonte, en sesiones de bolsa | Un año: `252`, o `365` si la cartera es solo cripto |
| `--simulations 10000` | Número de escenarios | `10000` |
| `--seed 42` | Semilla: repite los mismos escenarios | `42` |
| `--confidence 0.95` | Nivel del VaR y del CVaR | `0.95` |
| `--return 0.08` o `--return IBM:0.08 MSFT:0.1` | Rentabilidad anual esperada, común o por activo | Tipo libre de riesgo + prima por la parte en renta variable |
| `--equity-premium 0.045` | Prima de la renta variable sobre el tipo libre de riesgo | `0.045` (4,5 %) |
| `--volatility 0.2` o `--volatility IBM:0.2` | Volatilidad anual, común o por activo | Histórica |
| `--estimation-start AAAA-MM-DD` | Inicio de los precios con los que se estiman la volatilidad y las correlaciones | 5 años antes de `--end`, o `--start` si es anterior; con Alpha Vantage, `--start` |

**Cambiar el horizonte.** `--steps` se indica en sesiones: `21` es un mes, `126` medio año,
`504` dos años y `1260` cinco años. Escenarios × (sesiones + 1 + 2 × activos) no puede
superar 20 millones: con 10.000 escenarios, el máximo ronda las 1.990 sesiones (unos 8 años);
para más, baja `--simulations`.

```bash
# Dos años, 5.000 escenarios
python src/main.py --assets SAN.MC:0.5 ITX.MC:0.5 --simulate --steps 504 --simulations 5000
```

El informe analiza un año por defecto, pero la volatilidad y las correlaciones de la
simulación se estiman con 5 años para que no dependan de un solo año tranquilo o agitado;
si hay menos de 3 años de datos, se avisa. Las simulaciones son escenarios, no predicciones.

<a id="es-plots"></a>

#### `--plots-report` · Gráficos en pantalla

Abre los gráficos del análisis (evolución, caídas, correlaciones, riesgo y rentabilidad,
distribución…) y, si se simula, los de Monte Carlo. No guarda archivos ni descarga las
referencias económicas, salvo el índice de `--benchmark`.

| Parámetro | Para qué sirve | Por defecto |
| --- | --- | --- |
| `--benchmark SÍMBOLO` | Índice o fondo con el que comparar, por ejemplo `^IXIC` o `^IBEX` | Ninguno sin `--report` |

```bash
python src/main.py --assets cartera_ejemplo.txt --plots-report --benchmark "^IXIC"
```

<a id="es-report"></a>

#### `--report` · Informe en Markdown

Guarda un informe con resumen, advertencias, métricas y gráficos. Por defecto incluye
todas las secciones, también Monte Carlo, que usa las opciones de [`--simulate`](#es-simulate)
sin necesidad de añadir esa opción.

| Parámetro | Para qué sirve | Por defecto |
| --- | --- | --- |
| `--report-sections CLAVE ...` | Secciones a incluir | Todas |
| `--report-detail compact\|full` | Secciones plegadas o todo desplegado | `compact` |
| `--output-dir CARPETA` | Carpeta de los informes | `informes/`, en la carpeta actual |
| `--benchmark SÍMBOLO` | Índice o fondo con el que comparar | ETF con dividendos: `SPY` en USD; `EXW1.DE` en EUR |

| Clave de sección | Qué encontrarás |
| --- | --- |
| `summary` | Resumen de la evolución y las medidas principales |
| `warnings` | Advertencias sobre concentración, caídas y otros riesgos |
| `composition` | Activos, pesos, sectores y divisas |
| `returns` | Rentabilidad, meses y años; coste del rebalanceo frente a mantener las posiciones |
| `risk` | Volatilidad, caída máxima y pérdidas de cola |
| `risk_adjusted` | Rentabilidad en relación con el riesgo y las referencias |
| `diversification` | Correlaciones, concentración y contribuciones al riesgo |
| `market` | Contexto de mercado: VIX, petróleo, oro, deuda alemana y efecto divisa |
| `simulation` | Monte Carlo: supuestos, resultados y sensibilidad al retorno |
| `data` | Fuentes, cobertura, incidencias y medidas no disponibles |

Cada ejecución crea una carpeta nueva; el informe y sus imágenes deben permanecer juntos:

```text
informes/
└── AAAA-MM-DD_HH-MM-SS/
    ├── AAAA-MM-DD_HH-MM-SS.md
    └── evolucion.png, exposicion.png… (gráficos de las secciones elegidas)
```

```bash
# Informe completo, desplegado, para un intervalo concreto
python src/main.py --assets IBM:0.6 MSFT:0.4 --start 2025-01-01 --end 2026-01-01 --report --report-detail full

# Informe breve, sin Monte Carlo
python src/main.py --assets cartera_ejemplo.txt --report --report-sections summary warnings risk data

# Cartera por acciones, expresada en euros
python src/main.py --shares AAPL:10 SPY:5 --currency EUR --report
```

Lee primero `summary`, `warnings` y `data`. «No disponible» indica datos ausentes o una
medida que no se puede calcular; no significa cero.

<a id="es-advertencias"></a>

**Advertencias (sección `warnings`).** El informe compara los resultados con estos umbrales y
muestra solo las que saltan, primero las de nivel alto:

| Advertencia | Nivel | Cuándo salta |
| --- | --- | --- |
| Concentración en un activo | 🔴 Alta | Una posición pesa más del 40 % |
| Concentración en un activo | 🟠 Media | La mayor posición pesa más del 25 %, sin llegar al 40 % |
| Riesgo no compensado | 🔴 Alta | El ratio de Sharpe es negativo |
| Riesgo no compensado | 🟠 Media | Sharpe no negativo, pero la prima frente al tipo libre de riesgo es inferior a 2 puntos al año |
| Caída máxima elevada | 🔴 Alta | La caída máxima supera el 30 % |
| Historia corta | 🔴 Alta | El historial cubre menos de 350 días naturales |
| Concentración sectorial | 🟠 Media | Un sector pesa más del 50 % |
| Activos redundantes | 🟠 Media | El par más correlacionado supera 0,8 |
| Poca diversificación | 🟠 Media | La correlación media entre activos supera 0,6 |
| Caída sin recuperar | 🟠 Media | La mayor caída sigue sin recuperarse al final del historial |
| Volatilidad elevada | 🟠 Media | La volatilidad anual de la cartera supera el 25 % |
| Pérdida frente a la inflación | 🟠 Media | La rentabilidad anual real es negativa; requiere `FRED_API_KEY` |
| Riesgo de divisa | 🟠 Media | Los activos cotizan en más de una divisa |
| Mercado en estrés | 🟠 Media | El VIX supera 30; requiere `FRED_API_KEY` |
| Datos poco fiables | 🟠 Media | Más del 5 % de las fechas de un activo se descartan por no coincidir con los demás |
| Las comisiones anulan el rebalanceo | 🟠 Media | Sin comisiones, rebalancear habría superado a comprar y mantener; con ellas, no |
| Comisiones elevadas | 🟠 Media | Las comisiones superan el 10 % de la ganancia antes de comisiones |
| Escenarios desfavorables | 🟠 Media | Se pierde dinero en más del 45 % de los escenarios de Monte Carlo |

Son orientativas: señalan qué revisar, no qué hacer. Los pesos que se evalúan son los
actuales, y un dato ausente no activa ninguna regla. Los umbrales se cambian desde Python con
`portfolio.analyze(warning_thresholds=WarningThresholds(drawdown=0.2))`, importando
`WarningThresholds` de `src.analysis`; no hay opción de consola. Los avisos sobre claves o
datos que faltan son otra cosa: salen en la consola y en la sección `data`.

<a id="es-rebalanceo"></a>

### 3. Rebalanceo y comisiones

Con rebalanceo mensual, a fin de mes se comprueba si algún peso se ha desviado de su
objetivo y, si compensa, se vuelve a él pagando las comisiones del bróker. Como ejemplo se
usa siempre la tarifa de Interactive Brokers (IBKR): 0,05 % por orden con un mínimo de 3. No se
elige bróker; solo se pueden cambiar los valores de esa tarifa. Monte Carlo aplica la misma
regla. Estas opciones solo se aceptan con rebalanceo mensual.

| Parámetro | Para qué sirve | Por defecto |
| --- | --- | --- |
| `--commission-rate 0.001` | Comisión proporcional por orden | `0.0005` (0,05 %, IBKR) |
| `--commission-fixed 1` | Comisión fija por orden | `0` (IBKR) |
| `--commission-min 5` | Comisión mínima por orden | `3` (IBKR) |
| `--commission-max 50` | Comisión máxima por orden | Sin máximo (IBKR) |
| `--rebalance-band 0.05` | Solo se reajusta si algún peso se desvía más que esto; `0` reajusta cada mes | `0.05` (5 puntos) |
| `--max-order-cost 0.01` | Descarta las órdenes cuya comisión supere esta fracción de su importe | `0.01` (1 %) |

Por ejemplo, con objetivo 60/40, un reparto 63/37 no supera la banda de 5 puntos; 66/34 sí.
Los importes fijos se expresan en la divisa de la cartera. Para reajustar cada mes sin
comisiones: `--commission-rate 0 --commission-min 0 --rebalance-band 0`.

<a id="es-ejemplo"></a>

### 4. Ejemplo reproducible sin conexión

Este ejemplo usa **datos ficticios**, sin Internet ni claves, y muestra cómo se valora una
cartera. Guarda el código como `demo.py` en la carpeta del proyecto y ejecuta `python demo.py`:

```python
import pandas as pd
from src.models import Asset, AssetProfile, Portfolio, PriceHistory

dates = pd.to_datetime(["2026-01-05", "2026-01-06", "2026-01-07"])


def asset(symbol, closes):
    history = PriceHistory(
        symbol=symbol,
        source="demo",
        prices=pd.DataFrame({"Close": closes}, index=dates),
        profile=AssetProfile(currency="USD"),
        price_basis="split_adjusted",
    )
    return Asset(history)


portfolio = Portfolio(
    [asset("AAA", [100, 110, 120]), asset("BBB", [100, 100, 110])],
    {"AAA": 0.6, "BBB": 0.4},
    initial_capital=10000,
    rebalance=None,
)
print(f"Capital inicial: {portfolio.initial_capital:.2f} USD")
print(f"Valor final: {portfolio.total_value:.2f} USD")
print(f"Rentabilidad total: {(portfolio.total_value / portfolio.initial_capital - 1):.2%}")

analysis = portfolio.analyze()
path = analysis.report(
    sections=["summary", "composition", "returns", "data"],
    directory="informes/demo",
)
print(f"Informe generado: {path}")
```

```text
Capital inicial: 10000.00 USD
Valor final: 11600.00 USD
Rentabilidad total: 16.00%
```

| Activo | Inversión inicial | Evolución del precio | Valor final |
| --- | --- | --- | --- |
| AAA | 6.000 USD | De 100 a 120: +20 % | 7.200 USD |
| BBB | 4.000 USD | De 100 a 110: +10 % | 4.400 USD |
| **Total** | **10.000 USD** | **+16 %** | **11.600 USD** |

No hay rebalanceo, comisiones ni dividendos. Con datos reales, los resultados dependen de
las fechas y los precios descargados.

<a id="es-claves"></a>

### 5. Claves de API y caché

Copia [`.env.example`](.env.example) a `.env` y completa solo las claves que necesites; no
subas `.env` al repositorio.

| Servicio | Clave | Qué aporta |
| --- | --- | --- |
| Yahoo Finance | No necesita | Precios, fichas, índices y cambios de divisa |
| BCE | No necesita | Tipo libre de riesgo en EUR |
| Alpha Vantage | `ALPHA_VANTAGE_API_KEY` | Proveedor alternativo con `--provider alpha_vantage` |
| FRED | `FRED_API_KEY` | Inflación, VIX, Brent y tipo libre de riesgo en USD |

Sin FRED, el informe continúa sin inflación, rentabilidad real, VIX ni Brent, y en USD sin
Sharpe, Sortino ni alfa. Alpha Vantage gratuito ofrece unas 100 sesiones y 25 peticiones al
día, y no admite `--shares`. Las respuestas se guardan un día en `.cache/market-data`;
borra esa carpeta para forzar nuevas descargas.

<a id="es-descargas"></a>
**Descargas simultáneas:** `--download-workers N` (de 1 a 4; 1 por defecto) descarga hasta
N activos a la vez para solapar las esperas de red, tanto en la cartera (por pesos o por
acciones) como en los precios de estimación de Monte Carlo; el límite es por lote, no
global entre ejecuciones. Solo Yahoo descarga en paralelo: Alpha Vantage usa siempre una
descarga por su cuota y la consola avisa una vez si pides más. Tipos de cambio, índice de
referencia, FRED y BCE siguen en secuencia. Los resultados son los mismos con cualquier
valor; si falla un activo, se detiene la carga y el error indica cuál. En nuestras
mediciones con Yahoo (8 activos, caché vacía, `python -m tests.benchmark_downloads --real`),
2 descargas fueron unas tres veces más rápidas que 1, pero con 4 Yahoo limitó las consultas
y tardó más que con 1; por eso el ejemplo usa 2.

```bash
python src/main.py --assets IBM:0.6 MSFT:0.4 --simulate --download-workers 2
```

<a id="es-problemas"></a>

### 6. Problemas frecuentes

| Problema | Qué hacer |
| --- | --- |
| No se encuentra `python` | Crea el entorno con `py` en Windows o `python3` en macOS/Linux y actívalo |
| PowerShell bloquea la activación | Usa `.\.venv\Scripts\python.exe` en lugar de `python` |
| Yahoo no descarga precios | Comprueba el símbolo y las fechas; si hay un límite temporal, espera y repite |
| Los pesos no suman 1 | Usa fracciones con punto decimal, por ejemplo `0.6` y `0.4` |
| «Los parámetros de Monte Carlo requieren…» | Añade `--simulate` o incluye `simulation` en `--report-sections` |
| Falta una divisa o un cambio | Revisa los activos; `--currency` indica la divisa de destino |
| No aparecen gráficos en pantalla | Usa `--report` para guardarlos si no hay interfaz gráfica |

<a id="es-desarrollo"></a>

### 7. Uso desde Python y desarrollo

```python
from src.portfolio_loader import load_portfolio
from src.providers import YahooFinanceAPI

portfolio = load_portfolio(
    {"IBM": 0.6, "MSFT": 0.4},
    YahooFinanceAPI(cache_dir=".cache/market-data"),
    "2025-01-01",
    "2026-01-01",
)
analysis = portfolio.analyze(price_column=portfolio.preferred_price_column)
simulation = portfolio.monte_carlo(steps=126, price_column=portfolio.preferred_price_column)
simulation.plot()
path = analysis.report(simulation, sections=["summary", "risk", "simulation"])
```

Desde Python no se descargan referencias ni 5 años de estimación automáticamente: usa
`load_references()` de `src.market_loader` y `monte_carlo(estimation_prices=...)` si los
necesitas. Tampoco hay comisiones por defecto: se configuran con `RebalanceRule`.
`load_portfolio()` y `load_portfolio_from_shares()` aceptan `max_workers=1..4` con la misma
política que `--download-workers`; el proveedor declara su límite con `max_download_workers`
(Yahoo 4, Alpha Vantage 1; sin atributo, 1). La consola oculta una vez los avisos de
obsolescencia de yfinance con `quiet_yfinance_warnings()` de `src.providers.yahoo`; desde
Python puedes llamarla tú o dejar que se vean.

Para contribuir, instala las herramientas y ejecuta las comprobaciones sin red:

```bash
python -m pip install -e ".[dev]"
python -B -m ruff check --no-cache .
python -B -m ruff format --no-cache --check .
python -B -m coverage run -m unittest discover -s tests -v
python -B -m coverage report
```

La integración continua comprueba Python 3.11 y 3.14, una cobertura mínima del 94 %, el
formato, la complejidad, el paquete instalado y la ausencia de claves filtradas.

**Sigue leyendo:** [decisiones del modelo](Decisiones.MD) · [arquitectura](ARQUITECTURA.md) ·
[diagramas](diagramas/README.md)

[↑ Español](#espanol) · [English ↓](#english)

---

<a id="english"></a>

## English

Turn a list of assets into a report with charts: analyze your portfolio, compare its
performance, and explore Monte Carlo scenarios. **Program messages and reports are in Spanish.**

[Get started](#en-start) · [Portfolio](#en-portfolio) · [Outputs](#en-outputs) ·
[`--simulate`](#en-simulate) · [`--plots-report`](#en-plots) · [`--report`](#en-report) ·
[Warnings](#en-warnings) · [Rebalancing](#en-rebalancing) · [Example](#en-example) · [Keys](#en-keys) ·
[Troubleshooting](#en-troubleshooting) · [Python and development](#en-development)

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

The sample portfolio allocates **60% to IBM and 40% to Microsoft**. The terminal prints the
report path; it is saved with its images in `informes/DATE_TIME/`. Open the `.md` file in a
Markdown viewer; in VS Code, press `Ctrl+Shift+V`. Every option is also listed by
`python src/main.py --help`.

<a id="en-portfolio"></a>

### 1. Define your portfolio

Choose **one** of these inputs:

| Input | Example | Meaning |
| --- | --- | --- |
| Weights | `--assets IBM:0.6 MSFT:0.4` | 60/40 target allocation of a hypothetical capital |
| Shares | `--shares AAPL:10 SPY:5` | 10 Apple shares and 5 SPY fund units |
| File | `--assets cartera_ejemplo.txt` | One `SYMBOL:WEIGHT` pair per line; quantities with `--shares` |

- **Weights:** between 0 and 1 and must sum to **1**: write `0.6`, not `60`. Use a decimal point.
- **Shares:** positive quantities; fractions such as `MSFT:2.5` are allowed. Yahoo only and
  without `--capital`.
- **`.txt` files:** UTF-8, with `#` comments and blank lines; no repeated symbols.
- **Symbols:** Yahoo symbols, for example `IBM`, `SAN.MC`, `^IBEX`, or `BTC-USD`.

These options apply to every output:

| Parameter | Purpose | Default |
| --- | --- | --- |
| `--provider yahoo\|alpha_vantage` | Price provider | `yahoo` |
| `--start YYYY-MM-DD` | Start of the analysis (inclusive) | 1 year ago with Yahoo; 120 days with Alpha Vantage |
| `--end YYYY-MM-DD` | End of the analysis (exclusive) | Today |
| `--currency EUR` | Currency to convert the portfolio into | The assets' currency |
| `--capital 10000` | Hypothetical initial capital; not used with `--shares` | `10000` |
| `--rebalance monthly\|none` | Monthly rebalancing or none ([commissions](#en-rebalancing)) | `monthly` with `--assets`; `none` with `--shares` |
| `--download-workers N` | Assets downloaded at once, from 1 to 4 ([downloads](#en-downloads)) | `1` |

Only dates with prices for every asset are used; gaps are not filled.

<a id="en-outputs"></a>

### 2. Choose what you want

Without output options, the program prints the holdings. Add one or more:

| Option | What you get |
| --- | --- |
| *(none)* | Holdings, weights, and portfolio value in the terminal |
| [`--simulate`](#en-simulate) | Monte Carlo simulation and its summary in the terminal |
| [`--plots-report`](#en-plots) | Charts on screen, without saving files |
| [`--report`](#en-report) | Markdown report with its charts; **includes Monte Carlo** |

They can be combined, for example `--report --plots-report`.

<a id="en-simulate"></a>

#### `--simulate` · Monte Carlo simulation

Simulates thousands of scenarios from the portfolio's current value and prints the mean final
value, percentiles, probability of loss, VaR, and CVaR. These options also apply to the Monte
Carlo section of `--report`.

| Parameter | Purpose | Default |
| --- | --- | --- |
| `--steps 252` | Horizon, in trading sessions | One year: `252`, or `365` for crypto-only portfolios |
| `--simulations 10000` | Number of scenarios | `10000` |
| `--seed 42` | Seed: repeats the same scenarios | `42` |
| `--confidence 0.95` | VaR and CVaR level | `0.95` |
| `--return 0.08` or `--return IBM:0.08 MSFT:0.1` | Expected annual return, common or per asset | Risk-free rate plus a premium on the equity portion |
| `--equity-premium 0.045` | Equity premium over the risk-free rate | `0.045` (4.5%) |
| `--volatility 0.2` or `--volatility IBM:0.2` | Annual volatility, common or per asset | Historical |
| `--estimation-start YYYY-MM-DD` | Start of the prices used to estimate volatility and correlations | 5 years before `--end`, or `--start` if earlier; with Alpha Vantage, `--start` |

**Changing the horizon.** `--steps` is in sessions: `21` is one month, `126` half a year,
`504` two years, and `1260` five years. Scenarios × (sessions + 1 + 2 × assets) cannot exceed
20 million: with 10,000 scenarios the maximum is about 1,990 sessions (around 8 years); for
more, lower `--simulations`.

```bash
# Two years, 5,000 scenarios
python src/main.py --assets SAN.MC:0.5 ITX.MC:0.5 --simulate --steps 504 --simulations 5000
```

The report analyzes one year by default, but simulation volatility and correlations are
estimated from 5 years so they do not depend on a single calm or turbulent year; with less
than 3 years of data, a warning is shown. Simulations are scenarios, not forecasts.

<a id="en-plots"></a>

#### `--plots-report` · Charts on screen

Opens the analysis charts (evolution, drawdowns, correlations, risk and return,
distribution…) and, when simulating, the Monte Carlo charts. It saves no files and downloads
no economic references, except the `--benchmark` index.

| Parameter | Purpose | Default |
| --- | --- | --- |
| `--benchmark SYMBOL` | Index or fund to compare against, for example `^IXIC` or `^IBEX` | None without `--report` |

```bash
python src/main.py --assets cartera_ejemplo.txt --plots-report --benchmark "^IXIC"
```

<a id="en-report"></a>

#### `--report` · Markdown report

Saves a report with a summary, warnings, metrics, and charts. By default it includes every
section, including Monte Carlo, which uses the [`--simulate`](#en-simulate) options without
needing that flag.

| Parameter | Purpose | Default |
| --- | --- | --- |
| `--report-sections KEY ...` | Sections to include | All |
| `--report-detail compact\|full` | Collapsible or fully expanded sections | `compact` |
| `--output-dir FOLDER` | Reports folder | `informes/` under the current folder |
| `--benchmark SYMBOL` | Index or fund to compare against | ETF with dividends: `SPY` for USD; `EXW1.DE` for EUR |

| Section key | Contents |
| --- | --- |
| `summary` | Performance overview and key measures |
| `warnings` | Concentration, drawdown, and other risk warnings |
| `composition` | Assets, weights, sectors, and currencies |
| `returns` | Returns, months, and years; rebalancing cost versus holding |
| `risk` | Volatility, maximum drawdown, and tail losses |
| `risk_adjusted` | Return relative to risk and the references |
| `diversification` | Correlations, concentration, and risk contributions |
| `market` | Market context: VIX, oil, gold, German bonds, and currency effect |
| `simulation` | Monte Carlo: assumptions, results, and return sensitivity |
| `data` | Sources, coverage, issues, and unavailable measures |

Each run creates a new folder; keep the report and its images together:

```text
informes/
└── YYYY-MM-DD_HH-MM-SS/
    ├── YYYY-MM-DD_HH-MM-SS.md
    └── evolucion.png, exposicion.png… (charts for the selected sections)
```

```bash
# Full, expanded report for a specific interval
python src/main.py --assets IBM:0.6 MSFT:0.4 --start 2025-01-01 --end 2026-01-01 --report --report-detail full

# Short report without Monte Carlo
python src/main.py --assets cartera_ejemplo.txt --report --report-sections summary warnings risk data

# Share-based portfolio expressed in euros
python src/main.py --shares AAPL:10 SPY:5 --currency EUR --report
```

Read `summary`, `warnings`, and `data` first. «No disponible» means missing data or a measure
that cannot be calculated; it does not mean zero.

<a id="en-warnings"></a>

**Warnings (`warnings` section).** The report compares the results with these thresholds and
shows only those triggered, high-severity first. Warning titles appear in Spanish in the report:

| Warning | Report title | Level | Triggered when |
| --- | --- | --- | --- |
| Single-asset concentration | Concentración en un activo | 🔴 High | A position exceeds 40% |
| Single-asset concentration | Concentración en un activo | 🟠 Medium | The largest position exceeds 25% but not 40% |
| Uncompensated risk | Riesgo no compensado | 🔴 High | The Sharpe ratio is negative |
| Uncompensated risk | Riesgo no compensado | 🟠 Medium | Sharpe is not negative, but the premium over the risk-free rate is below 2 points a year |
| Large drawdown | Caída máxima elevada | 🔴 High | Maximum drawdown exceeds 30% |
| Short history | Historia corta | 🔴 High | The history covers fewer than 350 calendar days |
| Sector concentration | Concentración sectorial | 🟠 Medium | A sector exceeds 50% |
| Redundant assets | Activos redundantes | 🟠 Medium | The most correlated pair exceeds 0.8 |
| Low diversification | Poca diversificación | 🟠 Medium | Mean correlation between assets exceeds 0.6 |
| Unrecovered drawdown | Caída sin recuperar | 🟠 Medium | The largest drawdown is still unrecovered at the end of the history |
| High volatility | Volatilidad elevada | 🟠 Medium | Annual portfolio volatility exceeds 25% |
| Inflation loss | Pérdida frente a la inflación | 🟠 Medium | The real annual return is negative; requires `FRED_API_KEY` |
| Currency risk | Riesgo de divisa | 🟠 Medium | Assets are quoted in more than one currency |
| Market stress | Mercado en estrés | 🟠 Medium | VIX exceeds 30; requires `FRED_API_KEY` |
| Unreliable data | Datos poco fiables | 🟠 Medium | More than 5% of an asset's dates are dropped for not matching the others |
| Commissions cancel rebalancing | Las comisiones anulan el rebalanceo | 🟠 Medium | Without commissions rebalancing would have beaten buy-and-hold; with them it does not |
| High commissions | Comisiones elevadas | 🟠 Medium | Commissions exceed 10% of the gain before commissions |
| Unfavorable scenarios | Escenarios desfavorables | 🟠 Medium | Money is lost in more than 45% of Monte Carlo scenarios |

They are indicative: they point to what to review, not what to do. Current weights are
evaluated, and missing data never triggers a rule. Change thresholds from Python with
`portfolio.analyze(warning_thresholds=WarningThresholds(drawdown=0.2))`, importing
`WarningThresholds` from `src.analysis`; there is no CLI option. Notices about missing keys or
data are separate: they appear in the terminal and in the `data` section.

<a id="en-rebalancing"></a>

### 3. Rebalancing and commissions

With monthly rebalancing, at each month end the program checks whether any weight has
drifted from its target and, if worthwhile, restores it paying the broker's commissions. The
Interactive Brokers (IBKR) schedule is always used as the example: 0.05% per order with a
minimum of 3. There is no broker choice; only the values of that schedule can be changed.
Monte Carlo applies the same rule. These options require monthly rebalancing.

| Parameter | Purpose | Default |
| --- | --- | --- |
| `--commission-rate 0.001` | Proportional commission per order | `0.0005` (0.05%, IBKR) |
| `--commission-fixed 1` | Fixed commission per order | `0` (IBKR) |
| `--commission-min 5` | Minimum commission per order | `3` (IBKR) |
| `--commission-max 50` | Maximum commission per order | No maximum (IBKR) |
| `--rebalance-band 0.05` | Rebalances only if a weight drifts more than this; `0` rebalances every month | `0.05` (5 points) |
| `--max-order-cost 0.01` | Skips orders whose commission exceeds this fraction of their amount | `0.01` (1%) |

For a 60/40 target, 63/37 stays inside the 5-point band; 66/34 exceeds it. Fixed amounts are
expressed in the portfolio currency. To rebalance every month without commissions:
`--commission-rate 0 --commission-min 0 --rebalance-band 0`.

<a id="en-example"></a>

### 4. Reproducible offline example

This example uses **fictitious data**, with no Internet or keys, and shows how a portfolio is
valued. Save the code in the [Spanish section](#es-ejemplo) as `demo.py` in the project folder
and run `python demo.py`. It prints:

```text
Capital inicial: 10000.00 USD
Valor final: 11600.00 USD
Rentabilidad total: 16.00%
```

| Asset | Initial investment | Price change | Final value |
| --- | --- | --- | --- |
| AAA | 6,000 USD | 100 to 120: +20% | 7,200 USD |
| BBB | 4,000 USD | 100 to 110: +10% | 4,400 USD |
| **Total** | **10,000 USD** | **+16%** | **11,600 USD** |

There is no rebalancing, commission, or dividend. With real data, results depend on the
dates and downloaded prices.

<a id="en-keys"></a>

### 5. API keys and cache

Copy [`.env.example`](.env.example) to `.env` and fill in only the keys you need; never
commit `.env`.

| Service | Key | What it adds |
| --- | --- | --- |
| Yahoo Finance | None | Prices, profiles, indices, and exchange rates |
| ECB | None | EUR risk-free rate |
| Alpha Vantage | `ALPHA_VANTAGE_API_KEY` | Alternative provider with `--provider alpha_vantage` |
| FRED | `FRED_API_KEY` | Inflation, VIX, Brent, and the USD risk-free rate |

Without FRED, the report continues without inflation, real return, VIX, or Brent, and for
USD without Sharpe, Sortino, or alpha. Free Alpha Vantage offers about 100 sessions and 25
requests per day, and does not support `--shares`. Responses are cached for one day in
`.cache/market-data`; delete that folder to force new downloads.

<a id="en-downloads"></a>
**Concurrent downloads:** `--download-workers N` (1 to 4; 1 by default) downloads up to N
assets at once to overlap network waits, both for the portfolio (weights or shares) and for
the Monte Carlo estimation prices; the limit is per batch, not global across runs. Only
Yahoo downloads in parallel: Alpha Vantage always uses one download because of its quota,
and the CLI warns once if you ask for more. Exchange rates, the benchmark, FRED, and the ECB
remain sequential. Results are identical for any value; if one asset fails, loading stops
and the error names it. In our measurements with Yahoo (8 assets, empty cache,
`python -m tests.benchmark_downloads --real`), 2 downloads were about three times faster
than 1, but with 4 Yahoo throttled the requests and it took longer than 1; hence the example
uses 2.

```bash
python src/main.py --assets IBM:0.6 MSFT:0.4 --simulate --download-workers 2
```

<a id="en-troubleshooting"></a>

### 6. Troubleshooting

| Problem | What to do |
| --- | --- |
| `python` is not found | Create the environment with `py` on Windows or `python3` on macOS/Linux and activate it |
| PowerShell blocks activation | Use `.\.venv\Scripts\python.exe` instead of `python` |
| Yahoo downloads no prices | Check the symbol and dates; if rate-limited, wait and retry |
| Weights do not sum to 1 | Use fractions with a decimal point, for example `0.6` and `0.4` |
| «Los parámetros de Monte Carlo requieren…» | Add `--simulate` or include `simulation` in `--report-sections` |
| A currency or exchange rate is missing | Check the assets; `--currency` sets the target currency |
| No charts appear on screen | Use `--report` to save them if there is no graphical interface |

<a id="en-development"></a>

### 7. Python usage and development

See the [Spanish section](#es-desarrollo) for a Python example that loads a portfolio,
analyzes it, simulates it, and saves the report. Python usage downloads no references or
5-year estimation prices automatically: use `load_references()` from `src.market_loader` and
`monte_carlo(estimation_prices=...)` if you need them. It has no commissions by default;
configure them with `RebalanceRule`. `load_portfolio()` and `load_portfolio_from_shares()`
accept `max_workers=1..4` with the same policy as `--download-workers`; providers declare
their limit with `max_download_workers` (Yahoo 4, Alpha Vantage 1; none declared, 1). The
CLI hides yfinance deprecation noise once with `quiet_yfinance_warnings()` from
`src.providers.yahoo`; from Python you may call it yourself or leave those warnings visible.

To contribute, install the development tools and run the offline checks:

```bash
python -m pip install -e ".[dev]"
python -B -m ruff check --no-cache .
python -B -m ruff format --no-cache --check .
python -B -m coverage run -m unittest discover -s tests -v
python -B -m coverage report
```

Continuous integration checks Python 3.11 and 3.14, at least 94% coverage, formatting,
complexity, the installed package, and leaked secrets.

**Read more:** [model decisions, in Spanish](Decisiones.MD) · [architecture](ARQUITECTURA.md) ·
[diagrams](diagramas/README.md)

[↑ Español](#espanol) · [English ↑](#english)
