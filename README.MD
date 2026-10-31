# MIAX B1-T1

Indica qué activos componen tu cartera y qué proporción quieres invertir en cada
uno. El programa consulta sus precios y la información de las empresas y analiza
una cartera hipotética con rebalanceo mensual. Genera gráficos, simulaciones de
Monte Carlo e informes en español.

## Instalación

El proyecto admite Python 3.11 o posterior. El equipo desarrolla y comprueba con
Python 3.14, indicado en `.python-version`; es la versión recomendada para
obtener los mismos resultados. Desde la carpeta del proyecto:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

La instalación editable permite ejecutar el archivo principal utilizando los
paquetes de `src`. Al trasladar el proyecto, recrea el entorno e instala de nuevo.

Puedes elegir Yahoo Finance o Alpha Vantage para los precios y la información
de los activos. Para usar Alpha Vantage, copia `.env.example` a `.env` y completa
`ALPHA_VANTAGE_API_KEY`. Las referencias económicas de FRED se consultan aparte
y requieren `FRED_API_KEY`. Si falta una referencia opcional, el informe explica
qué medidas no han podido calcularse.

## Uso

```powershell
python src/main.py --assets IBM:0.6 MSFT:0.4
python src/main.py --assets cartera_ejemplo.txt --simulate --report
python src/main.py --provider alpha_vantage --assets IBM:1 --simulate --report
python src/main.py --provider alpha_vantage --assets cartera_ejemplo.txt --simulate --report
python src/main.py --assets IBM:0.6 MSFT:0.4 --start 2025-10-01 --end 2026-10-01 --report
python src/main.py --assets cartera_ejemplo.txt --currency EUR --simulate --plots-report --report
```

| Opción | Uso |
| --- | --- |
| `--provider yahoo` o `--provider alpha_vantage` | Proveedor de precios; por defecto, Yahoo Finance |
| `--assets SÍMBOLO:PESO ...` o `--assets archivo.txt` | Pesos objetivo de la cartera; obligatorio |
| `--start AAAA-MM-DD` | Fecha de inicio incluida; por defecto, hace un año con Yahoo y 120 días con Alpha Vantage (el modo `compact` ofrece unas 100 sesiones) |
| `--end AAAA-MM-DD` | Fecha de fin excluida; por defecto, hoy |
| `--simulate` | Simular la evolución de la cartera a partir de los datos históricos |
| `--plots-report` | Mostrar el conjunto de gráficos sin crear un documento |
| `--report` | Generar Monte Carlo y guardar el informe Markdown con sus imágenes |
| `--currency EUR` | Convertir los precios y las posiciones a la divisa indicada |
| `--steps 252` | Sesiones futuras de la simulación |
| `--simulations 1000` | Número de escenarios |
| `--return 0.08` | Retorno anual μ para todos los activos |
| `--return IBM:0.08 MSFT:0.10` | Cambiar μ por activo; los demás conservan su estimación histórica |
| `--volatility 0.20` | Volatilidad anual σ para todos los activos |
| `--volatility IBM:0.20 MSFT:0.30` | Cambiar σ por activo manteniendo las correlaciones históricas |
| `--confidence 0.95` | Confianza de las medidas de cola VaR y CVaR; debe estar entre 0,5 y 1 |
| `--seed 42` | Semilla para reproducir la simulación |
| `--capital 10000` | Capital hipotético al inicio del histórico |
| `--rebalance monthly` o `--rebalance none` | Rebalancear o mantener las posiciones |

Cada peso debe estar entre 0 y 1, incluidos ambos extremos, y todos deben sumar 1.
Por ejemplo, `IBM:0.6 MSFT:0.4` representa un 60 % y un 40 %. No se convierten
porcentajes ni cantidades de acciones automáticamente: `IBM:60` no es válido.

También puedes indicar un archivo de texto UTF-8, con un activo por línea:

```text
# Cartera objetivo
IBM:0.6
MSFT:0.4
```

Se admiten líneas vacías y comentarios con `#`. Los símbolos no pueden repetirse,
ni siquiera cambiando mayúsculas por minúsculas. Las rutas relativas parten de la
carpeta desde la que ejecutas el programa; si contienen espacios, ponlas entre
comillas. No se puede mezclar una ruta con activos escritos en consola.

La divisa de origen se obtiene de cada ficha. `--currency` indica la divisa de
destino y descarga los cambios necesarios automáticamente. Si falta un tipo de
cambio necesario, el programa explica el problema y detiene la conversión.

Sin `--currency`, todos los activos deben compartir divisa y unidad de cotización.

## Capital de referencia y rebalanceo mensual

La cartera empieza con un capital hipotético de 10.000 unidades de su divisa por defecto,
repartido según los pesos objetivo en la primera fecha común de los historiales.
Este importe sirve para comparar la evolución de distintas asignaciones; no se
interpreta como el saldo real del usuario.

Al cierre de cada mes se vuelve a los pesos objetivo utilizando las fechas comunes
disponibles. Durante el mes, los pesos actuales pueden alejarse de los objetivos.
Se permiten fracciones de los activos y se supone que el rebalanceo no tiene
comisiones, impuestos ni aportaciones o retiradas de capital.

Monte Carlo parte del valor de las posiciones al final del análisis histórico y
aproxima el rebalanceo mensual con un reajuste cada 21 sesiones simuladas. No se
generan fechas futuras ni se reconstruyen festivos de las bolsas. El histórico
conserva el rebalanceo al cierre de cada mes. Con `--rebalance none` se desactivan
los reajustes en ambos recorridos. El informe explica esta diferencia.

Desde Python, `Portfolio(assets, allocations, ...)` recibe una lista de pesos en
el mismo orden que los activos. El capital se puede cambiar con `initial_capital`
y se puede analizar una estrategia sin reajustes con `rebalance=None`.

## Uso desde Python

Todos los proveedores de precios cumplen el mismo contrato, `PriceProvider`:
`get_prices(symbol, start, end)` devuelve un `PriceHistory`. Las opciones propias de
cada fuente se fijan al crear el adaptador, por lo que `load_portfolio()` y el
análisis no necesitan saber qué proveedor se utiliza:

```python
from src.portfolio_loader import load_portfolio
from src.providers import AlphaVantageAPI, YahooFinanceAPI

yahoo = YahooFinanceAPI()
alpha = AlphaVantageAPI(include_info=True, outputsize="compact", allow_partial=False)

history = yahoo.get_prices("^GSPC", "2025-10-01", "2026-10-01")
print(history.mean["Close"], history.std["Close"])  # calculadas al crear el objeto

portfolio = load_portfolio({"IBM": 0.6, "MSFT": 0.4}, yahoo, "2025-10-01", "2026-10-01")
```

Las fechas se indican siempre como `AAAA-MM-DD`. Cada adaptador traduce la ficha
del proveedor a unas claves comunes de `history.info`: `currency`, `name`,
`asset_type` (`stock`, `index`, `etf`, `fund` o `unknown`), `sector`, `country`,
`beta`, `market_cap` y `pe_ratio`. La respuesta original se conserva en
`info["raw"]`. Si la ficha no está disponible, los precios descargados se conservan,
`info["metadata_issue"]` explica el problema y la divisa debe indicarse con
`load_portfolio(..., currency="USD")`; no se supone ninguna.

`mean` y `std` se calculan al crear el historial. Si cambias los precios, crea un
`PriceHistory` nuevo para que las estadísticas sigan correspondiendo a los datos.

La consola trabaja con precios diarios. Si construyes historiales con otra
frecuencia, indica `periods_per_year` en `analyze()`, `report()` y `monte_carlo()`
(por ejemplo, 12 para datos mensuales); el análisis avisa si las fechas no
parecen diarias y se anualiza con 252 períodos.

## Parámetros de Monte Carlo

Los mismos parámetros se pueden utilizar con `--simulate` y con `--report`. El
informe genera e incluye la simulación aunque no se añada `--simulate`:

```powershell
python src/main.py --assets cartera_ejemplo.txt --simulate --steps 126 --simulations 5000 --return 0.08 --volatility 0.20 --seed 7
python src/main.py --assets cartera_ejemplo.txt --report --steps 126 --simulations 5000 --return IBM:0.08 MSFT:0.10 --volatility IBM:0.20 MSFT:0.30 --confidence 0.99
```

El modelo es un movimiento browniano geométrico. En cada sesión se aplica:

```text
S(t+1) = S(t) × exp[(mu − sigma²/2)/252 + sigma/√252 × Z]
```

`mu` es la deriva anual del modelo y `sigma`, su volatilidad anual. Si no se
indican, se estiman con la media y la desviación típica de las rentabilidades
simples históricas, anualizadas con 252 sesiones. Por ejemplo, `--return 0.08`
fija mu en 0,08: el crecimiento esperado a un año es `exp(0.08) - 1`, aproximadamente
un 8,33 %. No se interpreta como un crecimiento anual exacto del 8 %.

Los choques por activo se correlacionan mediante Cholesky de la covarianza diaria.
Si la matriz es singular, por ejemplo con activos idénticos o volatilidad cero,
se utiliza una factorización por autovalores. El informe indica el método aplicado.
Cambiar sigma conserva las correlaciones históricas. Los supuestos por activo
pueden ser parciales; el resto utiliza sus parámetros históricos.

El nivel de confianza controla la cola del VaR y CVaR al final del horizonte.
Con 0,95 se muestran los percentiles 5 y 95, que delimitan el 90 % central de los
escenarios; con 0,99, los percentiles 1 y 99 delimitan el 98 % central. No es una
probabilidad de cobertura del resultado real. Las pérdidas pueden ser negativas
si incluso la cola considerada termina con ganancias.

Desde Python, la misma configuración sirve para los dos métodos:

```python
options = dict(steps=126, simulations=5000, expected_returns=0.08,
               volatilities=0.20, confidence=0.99, seed=7)
result = portfolio.monte_carlo(**options)
path = portfolio.report(**options)

# El mismo método simula un único activo, partiendo de su último precio.
ibm = portfolio.assets[0].monte_carlo(**options)
ibm.plot()
```

`Asset` y `Portfolio` heredan `monte_carlo()` de `MonteCarloMixin`, de modo que
el algoritmo existe una sola vez. Cada clase indica qué precios simular y con qué
valores iniciales; la cartera añade además sus pesos de rebalanceo.
`expected_returns` y `volatilities` admiten un valor para todos los activos o un
diccionario por símbolo, también cuando se simula un único activo.

Si ya tienes un resultado, puedes reutilizarlo con `portfolio.report(simulation=result)`.
Los parámetros de generación solo se utilizan cuando no se proporciona un resultado.
`portfolio.analyze().report()` permite guardar únicamente el análisis histórico.

El GBM supone incrementos logarítmicos normales, mu y sigma constantes y puede
subestimar movimientos extremos. No incluye aportaciones, retiradas ni costes.
El gráfico de distribución compara los incrementos logarítmicos históricos con
una normal de igual media y desviación para mostrar posibles diferencias en las colas.

## Elección del proveedor

Un único activo se indica con peso 1 (100 %), por ejemplo `--assets IBM:1`.
El proveedor elegido se utiliza para todos los activos de esa ejecución. Ambos
producen el mismo tipo de historial interno, por lo que comparten el análisis,
Monte Carlo, los gráficos y el informe. No se cambia de proveedor automáticamente
si una descarga falla.

Las fuentes auxiliares se mantienen separadas: el índice de referencia y los
cambios de divisa automáticos se consultan en Yahoo Finance; la inflación y el
tipo de interés se consultan en FRED. Elegir Alpha Vantage para los activos no
cambia estas referencias. El informe identifica la fuente de cada activo y
explica el origen de las referencias utilizadas.

Los datos disponibles no son idénticos. El adaptador diario de Alpha Vantage usa
precios sin ajustar y solicita las últimas 100 observaciones. Si no cubren las
fechas indicadas, la descarga se rechaza; no se recorta el período sin avisar.
El historial completo y el cierre ajustado requieren otras condiciones de acceso
del proveedor. La información de empresas procede de OVERVIEW y puede no estar
disponible para todos los instrumentos. Para construir y valorar un activo es
necesario conocer su divisa; no se supone USD si falta ese dato.

Un desdoblamiento puede distorsionar las rentabilidades calculadas con precios
sin ajustar. El informe advierte de esta diferencia frente a los cierres de Yahoo,
que se ajustan por desdoblamientos. Los símbolos también pueden variar entre
proveedores, especialmente en mercados internacionales.

## Información y supuestos del informe

El nombre de cada empresa, su sector, país, beta publicada, capitalización bursátil
y PER se consultan automáticamente. El informe reúne esta información, los
resultados del análisis, las referencias utilizadas y las posibles limitaciones
de los datos.

El informe incluye μ y σ históricos por activo y, por separado, los parámetros
efectivamente utilizados en Monte Carlo con su origen (histórico o usuario). Los
supuestos personalizados no modifican los resultados históricos. Son estimaciones
del modelo, no previsiones publicadas por las empresas ni garantías de resultados.

Los cálculos utilizan el precio de cierre (Close) y 252 períodos por año. La
simulación de Monte Carlo genera 1.000 escenarios de 252 períodos y utiliza
la semilla aleatoria 42 por defecto. El informe muestra todos los parámetros utilizados.
La valoración usa Close: en Yahoo está ajustado por desdoblamientos y no incorpora
el ajuste adicional por dividendos de Adj Close.

Para las carteras en dólares estadounidenses (USD), las referencias son el S&P 500,
el IPC estadounidense y el rendimiento de las letras del Tesoro a tres meses.
Para las carteras en euros (EUR), se utilizan el EURO STOXX 50, el IPCA de la zona
euro y el tipo de interés €STR. Las referencias
se eligen por divisa y se identifican en el informe. Para otras divisas, las medidas
que carezcan de una referencia configurada quedan sin calcular.

## Gráficos e informes

`--plots-report` muestra gráficos históricos, de comparación de activos y de
distribución, más los de simulación si se añade `--simulate` o `--report`. No guarda archivos por sí solo. Puede
combinarse con `--report` para ver los gráficos y guardar el informe completo.

Desde Python, `portfolio.plots_report()` devuelve ese mismo conjunto como un
diccionario de figuras (`portfolio`, `assets` y `distribution`). Con
`portfolio.plots_report("graficos")` también se guardan como PNG en esa carpeta.

Cada informe crea una carpeta dentro del proyecto:

```text
informes/
└── AAAA-MM-DD_HH-MM-SS/
    ├── AAAA-MM-DD_HH-MM-SS.md
    ├── analisis_cartera.png
    ├── evolucion_activos.png
    ├── distribucion_rentabilidades.png
    └── simulacion_monte_carlo.png
```

El informe completo incluye la imagen de Monte Carlo. Si se generan
dos informes en el mismo segundo, se añaden microsegundos al nombre para conservar ambos.

## Comprobaciones

```powershell
python -B -m ruff check --no-cache .
python -B -m ruff format --no-cache --check .
python -B -m unittest discover -s tests -v
```

Las pruebas no necesitan claves ni acceso a las API. GitHub Actions comprueba
código y formato con Python 3.14, y ejecuta las pruebas con la versión mínima
(3.11) y con la del equipo (3.14). `__pycache__` está excluido
en `.gitignore`. La caché de respuestas de Yahoo Finance, Alpha Vantage y FRED
se conserva un día en `.cache/market-data` para evitar consultas repetidas; no
contiene las claves en texto. Se guarda por símbolo: cambiar los parámetros de la
simulación no descarga nada y cambiar un activo solo descarga ese activo. En Yahoo
también se reutiliza un intervalo de fechas contenido en otro ya consultado. Para
forzar una descarga nueva, borra esa carpeta.
