# Guía de uso / User guide

**[Español](#espanol) · [English](#english) · [README](../README.MD)**

Referencia completa de parámetros, ejemplos reproducibles y ayuda de uso.
Complete parameter reference, reproducible examples, and usage help.

Los criterios del modelo y su justificación están en [Decisiones.MD](../Decisiones.MD).
Model choices and their rationale are recorded in [Decisiones.MD](../Decisiones.MD) (Spanish).

<a id="espanol"></a>

## Español

[Cartera](#es-cartera) · [Comandos](#es-ejemplos) · [Parámetros](#es-parametros) · [Informe](#es-informe) · [Ejemplo con resultados](#es-resultados) · [Claves](#es-claves) · [Problemas frecuentes](#es-problemas) · [Python y desarrollo](#es-desarrollo)


<a id="es-cartera"></a>

### 1. Define tu cartera

Elige **una** de estas formas:

| Forma | Ejemplo | Significado |
| --- | --- | --- |
| Pesos objetivo | `--assets IBM:0.6 MSFT:0.4` | Invertir el 60 % del capital en IBM y el 40 % en Microsoft |
| Número de acciones | `--shares AAPL:10 SPY:5` | Analizar 10 acciones de Apple y 5 participaciones del ETF SPY |
| Archivo de texto | `--assets cartera_ejemplo.txt` | Leer un par `SÍMBOLO:PESO` por línea; con `--shares` se leen cantidades |

Un símbolo es el identificador del activo en el proveedor: `IBM`, `MSFT`, `SAN.MC` o `BTC-USD`,
por ejemplo. Los símbolos de algunos mercados pueden variar entre proveedores.

- **Pesos:** deben estar entre 0 y 1 y sumar 1. Escribe `0.6`, no `60`, para indicar un 60 %.
  Se admite el redondeo de tres pesos `0.333333` (tolerancia `1e-5`). El capital inicial
  hipotético es de 10.000 unidades de la divisa de la cartera, salvo que uses `--capital`.
- **Acciones:** las cantidades deben ser positivas; se admiten fracciones como `MSFT:2.5`.
  Solo funciona con Yahoo. No se puede combinar con `--capital` ni con `--assets`.
- **Rebalanceo:** con pesos, por defecto se revisa al cierre de cada mes si hay que volver
  al reparto objetivo. Con acciones, por defecto se mantienen las cantidades durante el
  histórico. `--shares ... --rebalance monthly` usa como objetivo los pesos de la primera fecha.
- **Divisas:** usa `--currency EUR` para convertir a euros. Sin esa opción, todos los activos
  deben compartir divisa y unidad de cotización. La divisa de origen debe ser conocida.

Los archivos `.txt` deben guardarse en UTF-8. Admiten comentarios con `#` y líneas vacías;
no admiten símbolos repetidos. No mezcles un archivo con pares escritos en el mismo comando.
Usa punto decimal en todos los parámetros y comillas si una ruta contiene espacios.

Por ejemplo, el contenido de `cartera_ejemplo.txt` es:

```text
# Pesos objetivo: deben sumar 1.
IBM:0.6
MSFT:0.4
```

<a id="es-ejemplos"></a>

### 2. Comandos habituales

Ejecuta los comandos desde la carpeta del proyecto, con el entorno activado:

```bash
# Consultar las posiciones sin generar un informe
python src/main.py --assets IBM:0.6 MSFT:0.4

# Informe completo, sin desplegables, para un intervalo concreto
python src/main.py --assets IBM:0.6 MSFT:0.4 --start 2025-01-01 --end 2026-01-01 --report --report-detail full

# Cartera definida por acciones, expresada en euros
python src/main.py --shares AAPL:10 SPY:5 --currency EUR --report

# Informe breve del histórico, sin simulación
python src/main.py --assets cartera_ejemplo.txt --report --report-sections summary warnings risk data

# Solo simulación: 126 sesiones, 5.000 escenarios y supuestos propios
python src/main.py --assets cartera_ejemplo.txt --simulate --steps 126 --simulations 5000 --return 0.08 --volatility 0.20 --seed 7

# Mostrar gráficos y compararlos con el Nasdaq, sin guardar un informe
python src/main.py --assets cartera_ejemplo.txt --plots-report --benchmark "^IXIC"

# Usar Alpha Vantage, después de configurar su clave
python src/main.py --provider alpha_vantage --assets IBM:1 --report
```

`--start` incluye la fecha indicada; `--end` la excluye. Por ejemplo, `--end 2026-01-01`
no incluye el 1 de enero de 2026. Solo se usan fechas con precios para todos los activos.

<a id="es-parametros"></a>

### 3. Referencia de parámetros

Consulta también `python src/main.py --help`. Los nombres de las opciones se mantienen
en inglés porque son los que reconoce el programa.

#### Cartera y período

| Parámetro | Para qué sirve | Valor por defecto |
| --- | --- | --- |
| `-h`, `--help` | Mostrar la ayuda y salir | — |
| `--assets SÍMBOLO:PESO ...` | Pesos objetivo o un archivo `.txt` | Obligatorio si no usas `--shares` |
| `--shares SÍMBOLO:CANTIDAD ...` | Acciones o participaciones, o un archivo `.txt` | Alternativa a `--assets`; solo Yahoo |
| `--provider yahoo\|alpha_vantage` | Proveedor de precios de los activos | `yahoo` |
| `--start AAAA-MM-DD` | Inicio incluido | Hoy menos 365 días con Yahoo; menos 120 con Alpha Vantage |
| `--end AAAA-MM-DD` | Fin excluido | Hoy |
| `--currency EUR` | Divisa de destino; descarga los cambios necesarios | Divisa común de los activos |
| `--capital 10000` | Capital hipotético al comienzo del histórico; solo con pesos | `10000` |
| `--rebalance monthly\|none` | Revisar el reparto cada mes o mantener las posiciones | `monthly` con pesos; `none` con acciones |

#### Salidas e informe

| Parámetro | Para qué sirve | Valor por defecto |
| --- | --- | --- |
| `--report` | Guardar informe y gráficos; incluye Monte Carlo si se selecciona su sección | Desactivado |
| `--simulate` | Ejecutar Monte Carlo y mostrar su resumen en consola | Desactivado |
| `--plots-report` | Mostrar los gráficos en pantalla; por sí solo no guarda archivos | Desactivado |
| `--output-dir CARPETA` | Carpeta donde crear los informes; requiere `--report` | `informes/`, en la carpeta actual |
| `--benchmark SÍMBOLO` | Índice o fondo de Yahoo para comparar; requiere `--report` o `--plots-report` | `^GSPC` en USD; `^STOXX50E` en EUR |
| `--report-detail compact\|full` | Desplegables o contenido completamente visible; requiere `--report` | `compact` |
| `--report-sections CLAVE ...` | Elegir las secciones; requiere `--report` | Todas; claves en la [tabla del informe](#es-informe) |

Puedes combinar `--report`, `--simulate` y `--plots-report`. No necesitas añadir `--simulate`
a un informe que ya incluye `simulation`. Si excluyes esa sección, solo se simula si añades
`--simulate`. Los gráficos solos no descargan todas las referencias económicas; con
`--benchmark` sí se consulta el índice elegido.

#### Simulación de Monte Carlo

Estas opciones requieren `--simulate` o un informe que incluya `simulation`.

| Parámetro | Para qué sirve | Valor por defecto |
| --- | --- | --- |
| `--steps 252` | Número de períodos futuros; entero positivo | Un año: 252 sesiones o 365 días con calendario diario que incluya fines de semana |
| `--simulations 10000` | Número de escenarios; entero positivo | `10000` |
| `--seed 42` | Semilla aleatoria; entero no negativo | `42` |
| `--confidence 0.95` | Nivel para el VaR y CVaR; mayor que `0.5` y menor que `1` | `0.95` |
| `--equity-premium 0.045` | Prima anual sobre el tipo libre de riesgo, aplicada a la parte en renta variable | `0.045` (4,5 %) |
| `--return 0.08` | Deriva anual del modelo para todos los activos | Tipo libre de riesgo + prima; sin tipo disponible, retorno histórico con aviso |
| `--return IBM:0.08 MSFT:0.10` | Cambiar la deriva solo para los activos indicados | Los demás conservan el supuesto por defecto |
| `--volatility 0.20` | Volatilidad anual para todos los activos; no negativa | Estimada con el histórico |
| `--volatility IBM:0.20 MSFT:0.30` | Cambiar la volatilidad por activo; conserva las correlaciones históricas | Los demás conservan la estimación histórica |

`0.08` representa un 8 % como parámetro del modelo. Al ser una deriva continua,
`--return 0.08` implica un crecimiento esperado de aproximadamente `exp(0.08) - 1 = 8,33 %`
a un año para un activo sin costes; no fija una ganancia exacta del 8 %. La misma semilla
reproduce los escenarios cuando los datos y los demás parámetros también son iguales.

#### Rebalanceo y comisiones

Estas opciones solo se aceptan con rebalanceo mensual. Las comisiones se descuentan del
valor de la cartera tanto en el histórico como en Monte Carlo.

| Parámetro | Para qué sirve | Valor por defecto |
| --- | --- | --- |
| `--broker ibkr\|degiro\|trade_republic\|xtb\|none` | Elegir una tarifa de partida | `ibkr` |
| `--commission-rate 0.0005` | Comisión proporcional al importe de cada orden | La de la tarifa elegida |
| `--commission-fixed 2` | Importe fijo por orden | El de la tarifa elegida |
| `--commission-min 3` | Comisión mínima por orden | La de la tarifa elegida |
| `--commission-max 30` | Comisión máxima por orden | Sin máximo en las tarifas incluidas |
| `--rebalance-band 0.05` | Reajustar si algún peso se desvía más de esta fracción del objetivo | `0.05`: 5 puntos porcentuales; `0` revisa sin banda |
| `--max-order-cost 0.01` | Descartar una orden si su comisión supera esta fracción de su importe | `0.01`: 1 % |

Las tarifas **incluidas en el código**, orientativas, son: IBKR, 0,05 % con mínimo 3;
DEGIRO, 2 fijos; Trade Republic, 1 fijo; XTB y `none`, 0. Son supuestos del modelo,
no una garantía de las tarifas que te aplicará un intermediario. Los importes fijos se
expresan en la divisa de la cartera. Puedes sobrescribir cualquier campo de la tarifa.

Por ejemplo, con objetivo 60/40, un reparto 63/37 no supera la banda de 5 puntos; 66/34 sí.
Una orden de 200 con comisión mínima de 3 cuesta un 1,5 % y se descarta con el límite del 1 %.
Para reajustar cada mes sin comisiones: `--broker none --rebalance-band 0`.
La compra inicial no paga comisión; se comparan los costes de los reajustes.

<a id="es-informe"></a>

### 4. Qué contiene el informe y dónde se guarda

Cada ejecución con `--report` crea una carpeta nueva:

```text
informes/
└── AAAA-MM-DD_HH-MM-SS/
    ├── AAAA-MM-DD_HH-MM-SS.md
    ├── evolucion.png
    ├── exposicion.png
    └── ... imágenes de las secciones seleccionadas
```

El informe y sus imágenes deben permanecer juntos. `--output-dir resultados` cambia la
carpeta raíz. El modo `full` es útil si tu visor no admite desplegables. Solo aparecen los
gráficos para los que hay datos; un fallo al guardar no deja un informe a medio hacer.

| Clave de sección | Qué encontrarás |
| --- | --- |
| `summary` | Resumen de la evolución y las medidas principales |
| `warnings` | Advertencias sobre concentración, caídas y otros riesgos |
| `composition` | Activos, pesos, sectores y divisas |
| `returns` | Rentabilidad, meses y años; coste del rebalanceo frente a mantener las posiciones |
| `risk` | Volatilidad, caída máxima y pérdidas de cola |
| `risk_adjusted` | Rentabilidad en relación con el riesgo y las referencias disponibles |
| `diversification` | Correlaciones, concentración y contribuciones al riesgo |
| `market` | Contexto de mercado: VIX, petróleo, oro, deuda alemana y efecto divisa |
| `simulation` | Escenarios de Monte Carlo, supuestos y sensibilidad al retorno |
| `data` | Fuentes, cobertura, incidencias y motivos de las medidas no disponibles |

Lee primero `summary`, `warnings` y `data`. «No disponible» significa que faltan datos o
que la medida no se puede calcular; no equivale a cero. Las advertencias son orientativas.

Estas son algunas de las medidas que verás:

| Medida | Cómo entenderla |
| --- | --- |
| Rentabilidad total | Cambio entre el valor inicial y final: de 10.000 a 11.600 es un +16 % |
| Rentabilidad anualizada | Expresa el crecimiento como tasa anual equivalente; no es la ganancia de cada año |
| Volatilidad | Cuánto varían las rentabilidades; no indica una pérdida máxima |
| Caída máxima | Mayor descenso desde un máximo anterior hasta un mínimo posterior |
| Sharpe | Relaciona la rentabilidad por encima de la referencia sin riesgo con su variabilidad |
| VaR / CVaR | Umbral de la cola de pérdidas / media de esa cola; comprueba si son porcentajes por período o dinero al horizonte simulado |

<a id="es-resultados"></a>

### 5. Ejemplo reproducible con resultados

Este ejemplo usa **datos ficticios**, sin Internet ni claves. Sirve para entender la
valoración; tres sesiones no bastan para evaluar el riesgo de una inversión real.
Guarda este código como `demo.py` en la carpeta del proyecto y ejecuta `python demo.py`:

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

Resultado numérico:

```text
Capital inicial: 10000.00 USD
Valor final: 11600.00 USD
Rentabilidad total: 16.00%
```

Además, la última línea muestra la ruta del informe generado dentro de `informes/demo/`.
El resultado se entiende así:

| Activo | Inversión inicial | Evolución del precio | Valor final |
| --- | --- | --- | --- |
| AAA | 6.000 USD | De 100 a 120: +20 % | 7.200 USD |
| BBB | 4.000 USD | De 100 a 110: +10 % | 4.400 USD |
| **Total** | **10.000 USD** | **+16 %** | **11.600 USD** |

No hay rebalanceo, comisiones ni dividendos en este ejemplo. El informe histórico se guarda
sin ejecutar Monte Carlo porque se utiliza `analysis.report()` y no se le pasa una simulación.
Con precios reales, los resultados dependen del período, las fuentes y los datos descargados.

<a id="es-claves"></a>

### 6. Claves de API, proveedores y caché

Para añadir claves, copia [`.env.example`](../.env.example) a `.env` en la carpeta del proyecto
y completa solo las que necesites. No subas `.env` al repositorio. También puedes definir
las variables en tu entorno; tienen prioridad sobre `.env`.

| Servicio | Clave | Qué aporta |
| --- | --- | --- |
| Yahoo Finance | No necesita | Precios, fichas, índices y cambios de divisa; proveedor por defecto |
| BCE | No necesita | Tipo libre de riesgo en EUR |
| Alpha Vantage | `ALPHA_VANTAGE_API_KEY` | Proveedor alternativo con `--provider alpha_vantage` |
| FRED | `FRED_API_KEY` | Inflación, VIX, Brent y tipo libre de riesgo en USD; permite calcular sus medidas dependientes |

Sin FRED, el informe continúa; faltarán inflación, rentabilidad real, VIX y Brent, y en USD
también Sharpe, Sortino y alfa. Sin la clave de Alpha Vantage no puedes elegir ese proveedor.
El proveedor seleccionado se usa para todos los activos; no hay cambio automático si falla.
Las referencias auxiliares mantienen sus propias fuentes, aunque elijas Alpha Vantage.

**Alpha Vantage:** la configuración incluida limita los envíos a 25 intentos por clave en
24 horas. Precios y ficha consumen una petición cada uno: 12 activos sin caché pueden gastar
24. Su modo `compact` ofrece unas 100 sesiones y se rechaza un intervalo que no pueda cubrir.
La consola utiliza precios sin ajustar por dividendos ni desdoblamientos, por lo que este
proveedor no admite `--shares`.

El control persistente de cuota y sus bloqueos se explican en la
[decisión 25](../Decisiones.MD#cuota-alpha-vantage).

**Caché:** las respuestas se reutilizan durante un día en `.cache/market-data`, respecto a
la carpeta desde la que ejecutas el programa. Cambiar solo la simulación no obliga a volver
a descargar los precios. Puedes borrar esa carpeta para forzar nuevas descargas; la caché
no reinicia la cuota y las respuestas vigentes siguen disponibles aunque no quede cuota.

<a id="es-problemas"></a>

### 7. Problemas frecuentes

| Problema | Qué hacer |
| --- | --- |
| No se encuentra `python` | Crea el entorno con `py` en Windows o `python3` en macOS/Linux y actívalo |
| PowerShell bloquea la activación | Puedes usar directamente `.\.venv\Scripts\python.exe -m pip install -e .` y `.\.venv\Scripts\python.exe src/main.py --assets cartera_ejemplo.txt --report` |
| Yahoo no descarga precios | Comprueba el símbolo y las fechas; si hay un límite temporal, espera y repite |
| Falta `FRED_API_KEY` | El informe sigue con las medidas disponibles; configura la clave si necesitas las demás |
| Falta una divisa o un cambio | Revisa la ficha del activo y las divisas; `--currency` indica destino, no rellena una divisa de origen desconocida |
| Los pesos no suman 1 | Usa fracciones con punto decimal, por ejemplo `0.6` y `0.4` |
| «Los parámetros de Monte Carlo requieren…» | Añade `--simulate` o incluye `simulation` en `--report-sections` |
| No aparecen gráficos en pantalla | Usa `--report` para guardarlos si ejecutas en un entorno sin interfaz gráfica |

<a id="es-desarrollo"></a>

### 8. Uso desde Python y desarrollo

Para cargar datos reales desde Python, después de instalar el proyecto:

```python
from src.portfolio_loader import load_portfolio
from src.providers import YahooFinanceAPI

portfolio = load_portfolio(
    {"IBM": 0.6, "MSFT": 0.4},
    YahooFinanceAPI(cache_dir=".cache/market-data"),
    "2025-01-01",
    "2026-01-01",
    rebalance=None,
)
analysis = portfolio.analyze(price_column=portfolio.preferred_price_column)
print(analysis.metrics["total_return"])
path = analysis.report(sections=["summary", "returns", "risk", "data"])
```

Este ejemplo consulta precios, pero no carga referencias económicas. Para incluirlas,
usa `load_references()` de `src.market_loader` y pásalas a `portfolio.analyze(references, ...)`.
`portfolio.monte_carlo()` ejecuta la simulación; `portfolio.report()` la genera si se incluye
su sección. Desde Python no hay comisiones por defecto: se configuran con `RebalanceRule`.
Los modelos protegen sus datos; para cambiar la composición se crea otra cartera.

Para contribuir, instala las herramientas y ejecuta las comprobaciones sin red:

```bash
python -m pip install -e ".[dev]"
python -B -m ruff check --no-cache .
python -B -m ruff format --no-cache --check .
python -B -m coverage run -m unittest discover -s tests -v
python -B -m coverage report
```

CI comprueba Python 3.11 y 3.14, cobertura de líneas y ramas de al menos el 94 %, formato,
complejidad, paquete instalado y secretos con gitleaks. CodeQL complementa esos controles.
Las pruebas de API reales están separadas: `python -B -m unittest tests.integration_apis -v`;
necesitan red y claves y consumen cuota. El pipeline y sus condiciones están en
[`.github/workflows/ci.yml`](../.github/workflows/ci.yml).

Más detalles: [decisiones](../Decisiones.MD), [arquitectura UML](../ARQUITECTURA.md),
[arquitectura resumida](../docs/arquitectura.md) y [regeneración de diagramas](../diagramas/README.md).

---

<a id="english"></a>

## English

[Portfolio](#en-portfolio) · [Commands](#en-examples) · [Parameters](#en-parameters) · [Report](#en-report) · [Worked example](#en-results) · [API keys](#en-keys) · [Troubleshooting](#en-troubleshooting) · [Python and development](#en-development)


<a id="en-portfolio"></a>

### 1. Define your portfolio

Choose **one** input method:

| Method | Example | Meaning |
| --- | --- | --- |
| Target weights | `--assets IBM:0.6 MSFT:0.4` | Allocate 60% of the capital to IBM and 40% to Microsoft |
| Share counts | `--shares AAPL:10 SPY:5` | Analyze 10 Apple shares and 5 units of the SPY ETF |
| Text file | `--assets cartera_ejemplo.txt` | Read one `SYMBOL:WEIGHT` pair per line; `--shares` reads quantities instead |

A symbol identifies an asset at the selected provider: for example, `IBM`, `MSFT`, `SAN.MC`,
or `BTC-USD`. Symbols for some markets can differ between providers.

- **Weights:** each must be between 0 and 1, and the total must be 1. Use `0.6`, not `60`,
  for 60%. Three rounded weights of `0.333333` are accepted (tolerance `1e-5`). Initial
  hypothetical capital is 10,000 units of the portfolio currency unless you set `--capital`.
- **Shares:** quantities must be positive; fractional shares such as `MSFT:2.5` are accepted.
  This method supports Yahoo only and cannot be combined with `--capital` or `--assets`.
- **Rebalancing:** weighted portfolios check at each month-end whether to restore target
  weights. Share-based portfolios keep their quantities throughout the history by default.
  `--shares ... --rebalance monthly` targets the weights at the first historical date.
- **Currencies:** use `--currency EUR` to convert to euros. Without it, all assets must share
  a currency and quote unit. Each asset's original currency must be known.

Save `.txt` files as UTF-8. Blank lines and `#` comments are supported; duplicate symbols
are rejected. Do not mix a file and inline pairs in the same command. Use decimal points
in parameters and quote paths containing spaces.

For example, `cartera_ejemplo.txt` contains:

```text
# Target weights must sum to 1.
IBM:0.6
MSFT:0.4
```

<a id="en-examples"></a>

### 2. Common commands

Run these from the project folder with the virtual environment active:

```bash
# Display holdings without generating a report
python src/main.py --assets IBM:0.6 MSFT:0.4

# Fully expanded report for a specific historical interval
python src/main.py --assets IBM:0.6 MSFT:0.4 --start 2025-01-01 --end 2026-01-01 --report --report-detail full

# Share-based portfolio expressed in euros
python src/main.py --shares AAPL:10 SPY:5 --currency EUR --report

# Short historical report without simulation
python src/main.py --assets cartera_ejemplo.txt --report --report-sections summary warnings risk data

# Simulation only: 126 sessions, 5,000 scenarios, and custom assumptions
python src/main.py --assets cartera_ejemplo.txt --simulate --steps 126 --simulations 5000 --return 0.08 --volatility 0.20 --seed 7

# Display charts against the Nasdaq without saving a report
python src/main.py --assets cartera_ejemplo.txt --plots-report --benchmark "^IXIC"

# Use Alpha Vantage after configuring its key
python src/main.py --provider alpha_vantage --assets IBM:1 --report
```

`--start` is inclusive; `--end` is exclusive. For example, `--end 2026-01-01` excludes
January 1, 2026. Only dates with prices for all portfolio assets are retained.

<a id="en-parameters"></a>

### 3. Parameter reference

You can also run `python src/main.py --help`. Option names stay unchanged because they
are the names the program accepts.

#### Portfolio and date range

| Parameter | Purpose | Default |
| --- | --- | --- |
| `-h`, `--help` | Display help and exit | — |
| `--assets SYMBOL:WEIGHT ...` | Target weights or a `.txt` file | Required unless you use `--shares` |
| `--shares SYMBOL:QUANTITY ...` | Share or fund-unit quantities, or a `.txt` file | Alternative to `--assets`; Yahoo only |
| `--provider yahoo\|alpha_vantage` | Price provider for portfolio assets | `yahoo` |
| `--start YYYY-MM-DD` | Inclusive start date | Today minus 365 days for Yahoo; minus 120 for Alpha Vantage |
| `--end YYYY-MM-DD` | Exclusive end date | Today |
| `--currency EUR` | Target currency; downloads the necessary exchange rates | Assets' common currency |
| `--capital 10000` | Hypothetical capital at the start of the history; weights only | `10000` |
| `--rebalance monthly\|none` | Check allocations monthly or keep positions unchanged | `monthly` for weights; `none` for shares |

#### Output and reports

| Parameter | Purpose | Default |
| --- | --- | --- |
| `--report` | Save a report and charts; includes Monte Carlo if its section is selected | Off |
| `--simulate` | Run Monte Carlo and display its summary in the terminal | Off |
| `--plots-report` | Display charts; does not save files on its own | Off |
| `--output-dir FOLDER` | Parent folder for reports; requires `--report` | `informes/` under the current folder |
| `--benchmark SYMBOL` | Yahoo index or fund for comparison; requires `--report` or `--plots-report` | `^GSPC` for USD; `^STOXX50E` for EUR |
| `--report-detail compact\|full` | Collapsible sections or fully visible content; requires `--report` | `compact` |
| `--report-sections KEY ...` | Choose sections; requires `--report` | All; see [report section keys](#en-report) |

You can combine `--report`, `--simulate`, and `--plots-report`. A report containing
`simulation` already runs Monte Carlo; adding `--simulate` is unnecessary. If you exclude
that section, simulation runs only when you add `--simulate`. Charts alone do not download
all economic references; `--benchmark` does load the selected comparison index.

#### Monte Carlo simulation

These options require `--simulate` or a report containing `simulation`.

| Parameter | Purpose | Default |
| --- | --- | --- |
| `--steps 252` | Number of future periods; positive integer | One year: 252 sessions, or 365 days for a daily calendar including weekends |
| `--simulations 10000` | Number of scenarios; positive integer | `10000` |
| `--seed 42` | Random seed; nonnegative integer | `42` |
| `--confidence 0.95` | VaR/CVaR level; greater than `0.5` and less than `1` | `0.95` |
| `--equity-premium 0.045` | Annual premium over the risk-free rate, applied to the equity portion | `0.045` (4.5%) |
| `--return 0.08` | Annual model drift for every asset | Risk-free rate plus premium; historical return with a warning if no rate is available |
| `--return IBM:0.08 MSFT:0.10` | Override drift for specified assets | Others keep their default assumption |
| `--volatility 0.20` | Annual volatility for every asset; nonnegative | Estimated from history |
| `--volatility IBM:0.20 MSFT:0.30` | Override volatility by asset; retains historical correlations | Others keep their historical estimate |

`0.08` represents 8% as a model parameter. Because this is continuous drift,
`--return 0.08` implies approximately `exp(0.08) - 1 = 8.33%` expected growth over a year
for an asset without costs, rather than an exact 8% gain. A fixed seed reproduces scenarios
when the data and all other parameters are also unchanged.

#### Rebalancing and commissions

These options require monthly rebalancing. Commissions reduce portfolio value in both
the historical calculation and Monte Carlo.

| Parameter | Purpose | Default |
| --- | --- | --- |
| `--broker ibkr\|degiro\|trade_republic\|xtb\|none` | Choose a starting commission schedule | `ibkr` |
| `--commission-rate 0.0005` | Commission as a fraction of each order's value | Selected schedule |
| `--commission-fixed 2` | Fixed amount per order | Selected schedule |
| `--commission-min 3` | Minimum commission per order | Selected schedule |
| `--commission-max 30` | Maximum commission per order | No maximum in the included schedules |
| `--rebalance-band 0.05` | Rebalance if any weight drifts by more than this fraction from its target | `0.05`: 5 percentage points; `0` removes the band |
| `--max-order-cost 0.01` | Skip an order if its commission exceeds this fraction of its value | `0.01`: 1% |

The **schedules included in the code** are illustrative: IBKR, 0.05% with a minimum of 3;
DEGIRO, a fixed 2; Trade Republic, a fixed 1; XTB and `none`, zero. These are model
assumptions, not a guarantee of a broker's actual charges. Fixed amounts use the portfolio
currency. You can override any schedule field.

For a 60/40 target, 63/37 stays inside the 5-point band; 66/34 exceeds it. A minimum
commission of 3 on a 200 order is 1.5%, so that order is skipped with a 1% cost limit.
Use `--broker none --rebalance-band 0` to restore weights monthly without commissions.
The initial purchase is not charged; the comparison measures rebalancing costs.

<a id="en-report"></a>

### 4. Report contents and saved files

Each run with `--report` creates a new folder:

```text
informes/
└── YYYY-MM-DD_HH-MM-SS/
    ├── YYYY-MM-DD_HH-MM-SS.md
    ├── evolucion.png
    ├── exposicion.png
    └── ... images for the selected sections
```

Keep the report and its images together. `--output-dir resultados` changes the parent
folder. Use `full` if your viewer does not support collapsible sections. Charts appear
only when their data are available; a saving failure does not leave a partial report.

| Section key | Contents |
| --- | --- |
| `summary` | Portfolio performance and main metrics |
| `warnings` | Concentration, drawdown, and other risk warnings |
| `composition` | Assets, weights, sectors, and currencies |
| `returns` | Returns, monthly/yearly results, and rebalancing costs versus buy-and-hold |
| `risk` | Volatility, maximum drawdown, and tail losses |
| `risk_adjusted` | Return relative to risk and available references |
| `diversification` | Correlations, concentration, and risk contributions |
| `market` | Market context: VIX, oil, gold, German bonds, and currency effects |
| `simulation` | Monte Carlo scenarios, assumptions, and return sensitivity |
| `data` | Sources, coverage, issues, and reasons for unavailable metrics |

Start with `summary`, `warnings`, and `data`. “No disponible” means data are missing or
a metric is undefined; it does not mean zero. Warnings are indicative.

Some of the metrics you will see:

| Metric | How to read it |
| --- | --- |
| Total return | Change from initial to final value: 10,000 to 11,600 is +16% |
| Annualized return | Growth expressed as an equivalent annual rate, rather than the gain in each year |
| Volatility | How much returns vary; it is not a maximum loss |
| Maximum drawdown | Largest drop from an earlier peak to a later trough |
| Sharpe | Relates return above the risk-free reference to its variability |
| VaR / CVaR | Loss-tail threshold / average of that tail; check whether values are per-period returns or money at the simulated horizon |

<a id="en-results"></a>

### 5. Reproducible worked example

This example uses **synthetic data** and needs no Internet or API keys. It demonstrates
valuation; three sessions are insufficient to assess a real investment's risk.
Save this as `demo.py` in the project folder and run `python demo.py`:

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
print(f"Initial capital: {portfolio.initial_capital:.2f} USD")
print(f"Final value: {portfolio.total_value:.2f} USD")
print(f"Total return: {(portfolio.total_value / portfolio.initial_capital - 1):.2%}")

analysis = portfolio.analyze()
path = analysis.report(
    sections=["summary", "composition", "returns", "data"],
    directory="informes/demo",
)
print(f"Report generated: {path}")
```

Numerical output:

```text
Initial capital: 10000.00 USD
Final value: 11600.00 USD
Total return: 16.00%
```

The final line also prints the generated report path under `informes/demo/`.
Here is the calculation:

| Asset | Initial allocation | Price change | Final value |
| --- | --- | --- | --- |
| AAA | 6,000 USD | 100 to 120: +20% | 7,200 USD |
| BBB | 4,000 USD | 100 to 110: +10% | 4,400 USD |
| **Total** | **10,000 USD** | **+16%** | **11,600 USD** |

There is no rebalancing, commission, or dividend in this example. It saves a historical
report without running Monte Carlo because it calls `analysis.report()` without supplying
a simulation. With market prices, results depend on the period, sources, and downloaded data.

<a id="en-keys"></a>

### 6. API keys, providers, and cache

To add keys, copy [`.env.example`](../.env.example) to `.env` in the project folder and fill in
only those you need. Do not commit `.env`. You can also set environment variables;
existing environment variables take precedence over `.env`.

| Service | Key | Provides |
| --- | --- | --- |
| Yahoo Finance | None required | Prices, profiles, indices, and exchange rates; default provider |
| ECB | None required | EUR risk-free reference rate |
| Alpha Vantage | `ALPHA_VANTAGE_API_KEY` | Alternative provider via `--provider alpha_vantage` |
| FRED | `FRED_API_KEY` | Inflation, VIX, Brent, and the USD risk-free rate, enabling dependent metrics |

Without FRED, the report continues without inflation, real returns, VIX, and Brent; in USD,
Sharpe, Sortino, and alpha are also unavailable. Selecting Alpha Vantage requires its key.
One selected provider supplies all portfolio assets, with no automatic fallback on failure.
Auxiliary references keep their own sources even when you select Alpha Vantage.

**Alpha Vantage:** the included configuration limits requests to 25 attempts per key in
24 hours. Prices and profiles each consume one request: 12 uncached assets can use 24.
Its `compact` mode provides around 100 sessions; date ranges it cannot cover are rejected.
The CLI uses closes unadjusted for dividends or splits, so this provider does not support
`--shares`.

See [decision 25](../Decisiones.MD#cuota-alpha-vantage) for persistent quota tracking
and cooldown behavior (in Spanish).

**Cache:** responses are reused for one day in `.cache/market-data`, relative to the folder
where you run the program. Changing only simulation settings does not require downloading
prices again. Delete that folder to force fresh downloads; clearing the cache does not
reset the quota, and valid cached responses remain usable when quota is exhausted.

<a id="en-troubleshooting"></a>

### 7. Troubleshooting

| Problem | Action |
| --- | --- |
| `python` is not found | Create the environment with `py` on Windows or `python3` on macOS/Linux, then activate it |
| PowerShell blocks activation | Use `.\.venv\Scripts\python.exe -m pip install -e .` and `.\.venv\Scripts\python.exe src/main.py --assets cartera_ejemplo.txt --report` directly |
| Yahoo cannot download prices | Check the symbol and dates; wait and retry if temporarily rate-limited |
| `FRED_API_KEY` is missing | Available metrics still work; configure a key if you need the others |
| An asset currency or exchange rate is missing | Check the asset profile and currencies; `--currency` sets the destination and cannot fill an unknown original currency |
| Weights do not sum to 1 | Use fractions with decimal points, such as `0.6` and `0.4` |
| Monte Carlo parameters are rejected | Add `--simulate` or include `simulation` in `--report-sections` |
| Charts do not appear on screen | Use `--report` to save them when running without a graphical interface |

<a id="en-development"></a>

### 8. Python usage and development

After installing the project, load real prices from Python:

```python
from src.portfolio_loader import load_portfolio
from src.providers import YahooFinanceAPI

portfolio = load_portfolio(
    {"IBM": 0.6, "MSFT": 0.4},
    YahooFinanceAPI(cache_dir=".cache/market-data"),
    "2025-01-01",
    "2026-01-01",
    rebalance=None,
)
analysis = portfolio.analyze(price_column=portfolio.preferred_price_column)
print(analysis.metrics["total_return"])
path = analysis.report(sections=["summary", "returns", "risk", "data"])
```

This example downloads prices but does not load economic references. To include them, use
`load_references()` from `src.market_loader` and pass them to `portfolio.analyze(references, ...)`.
`portfolio.monte_carlo()` runs a simulation; `portfolio.report()` runs it when its section is
included. Python usage has no commissions by default; configure them with `RebalanceRule`.
Models protect their data; create another portfolio to change the allocation.

To contribute, install the development tools and run offline checks:

```bash
python -m pip install -e ".[dev]"
python -B -m ruff check --no-cache .
python -B -m ruff format --no-cache --check .
python -B -m coverage run -m unittest discover -s tests -v
python -B -m coverage report
```

CI checks Python 3.11 and 3.14, combined line/branch coverage of at least 94%, formatting,
complexity, installed packaging, and secrets with gitleaks. CodeQL adds static analysis.
Live API tests are separate: `python -B -m unittest tests.integration_apis -v`; they need
network access and keys and consume quota. See [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)
for the pipeline and its conditions.

Further reading: [decisions](../Decisiones.MD), [UML architecture](../ARQUITECTURA.md),
[architecture overview](../docs/arquitectura.md), and [diagram generation](../diagramas/README.md).
