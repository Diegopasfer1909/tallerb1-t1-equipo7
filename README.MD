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

### Claves de API (opcionales)

El programa funciona sin ninguna clave: Yahoo Finance no la necesita. Las claves solo
amplían lo que se puede hacer. Para añadirlas, copia `.env.example` a `.env` y
completa las que quieras; el programa busca `.env` en la carpeta desde la que lo
ejecutas y en las superiores.

| Sin clave | Con `ALPHA_VANTAGE_API_KEY` | Con `FRED_API_KEY` |
| --- | --- | --- |
| Precios y fichas de Yahoo Finance, conversión de divisas, Monte Carlo, gráficos e informe con el índice de referencia | `--provider alpha_vantage` | El informe añade inflación, rentabilidad real, tipo de interés y las ratios de Sharpe y Sortino |

Antes de descargar nada, la consola comprueba las claves que necesita lo que has
pedido:

- Si eliges `--provider alpha_vantage` sin su clave, se detiene con un mensaje que
  indica qué falta y propone `--provider yahoo`.
- Si pides `--report` sin `FRED_API_KEY`, avisa de lo que no incluirá y genera el
  informe con el resto; el informe explica qué medidas faltan y por qué.
- Si un proveedor rechaza una clave (no válida o sin cuota), el mensaje muestra el
  motivo que da el proveedor, sin mostrar la clave.

Desde Python, `has_api_key("FRED_API_KEY")` (en `src.providers`) indica si una clave
está configurada.

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
| `--output-dir CARPETA` | Carpeta de los informes; por defecto, `informes` dentro de la carpeta actual |
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
Por ejemplo, `IBM:0.6 MSFT:0.4` representa un 60 % y un 40 %. Se admite el redondeo
a seis decimales, como `0.333333` tres veces; en ese caso los pesos se reparten para
sumar exactamente 1. No se convierten porcentajes ni cantidades de acciones
automáticamente: `IBM:60` no es válido.

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

Desde Python, `Portfolio(assets, {"IBM": 0.6, "MSFT": 0.4}, ...)` recibe los pesos
objetivo como un diccionario por símbolo. `portfolio.target_weights` los conserva en
el orden de los activos y `portfolio.current_weights` muestra los pesos al final del
histórico. El capital se puede cambiar con `initial_capital`, que se valida al crear
la cartera, y se puede analizar una estrategia sin reajustes con `rebalance=None`.
`Portfolio.from_units(assets, {"IBM": 10, "MSFT": 5})` crea una cartera sin
rebalanceo a partir de las cantidades de cada activo.

La cartera no cambia después de crearse, por lo que su valoración se calcula una sola
vez y se reutiliza en cada consulta.

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
print(history.mean["Close"], history.std["Close"])  # calculadas a partir de los precios

portfolio = load_portfolio({"IBM": 0.6, "MSFT": 0.4}, yahoo, "2025-10-01", "2026-10-01")
```

Las fechas se indican siempre como `AAAA-MM-DD`. Cada adaptador traduce la ficha
del proveedor a un `AssetProfile` común, disponible en `history.profile`: `currency`,
`name`, `asset_type` (`stock`, `index`, `etf`, `fund` o `unknown`), `sector`,
`country`, `beta`, `market_cap` y `pe_ratio`. La respuesta original se conserva en
`profile.raw`. Si la ficha no está disponible, los precios descargados se conservan,
`profile.issue` explica el problema y la divisa debe indicarse con
`load_portfolio(..., currency="USD")`; no se supone ninguna.

### Cuota gratuita de Alpha Vantage

Alpha Vantage [permite 25 peticiones al día](https://www.alphavantage.co/support/).
El adaptador limita los envíos a **25 por clave en cualquier ventana de 24 horas**,
sin suponer una hora de reinicio del proveedor. Cada consulta de precios consume
una petición y cada ficha `OVERVIEW` otra. La consola activa ambas: una cartera de
12 activos sin caché puede consumir 24 peticiones. Desde Python se puede usar
`include_info=False` si no se necesita la ficha.

Las respuestas vigentes en caché no consumen cuota y siguen disponibles al llegar
al límite. Los intentos fallidos sí cuentan: el proveedor puede haber recibido la
petición aunque no llegue la respuesta. No se reintentan automáticamente ni se
siguen redirecciones. La petición 26 se bloquea antes del envío con
`AlphaVantageQuotaError` (subclase de `ProviderError`), que indica cuándo vuelve a
haber cuota en UTC. Si solo falta cuota para la ficha opcional, se conservan los
precios y se explica el problema en `profile.issue`.

El registro SQLite se guarda en `~/.local/state/miax/alpha-vantage.sqlite3`, fuera
de la caché, y persiste entre ejecuciones y carpetas de trabajo. Solo contiene el
hash de la clave, las horas de los intentos y los bloqueos de cuota. Las reservas son atómicas entre
procesos; si no se puede leer o guardar el registro, no se envía la consulta.
Desactivar o limpiar la caché no reinicia la cuota.

Para elegir otra ubicación persistente, configura `ALPHA_VANTAGE_USAGE_DB` en
el entorno o `.env`, o pasa `usage_db="/ruta/alpha-vantage.sqlite3"` al adaptador.
Todos los procesos que usen una misma clave deben usar el mismo archivo; no debe
borrarse para reiniciar el contador. El registro empieza vacío al instalar este
control: no conoce peticiones anteriores, realizadas por otras aplicaciones o
desde otros equipos. La misma clave puede usarse en CI y en local: si Alpha Vantage
responde que se ha alcanzado el límite, esa respuesta prevalece aunque el contador
local sea inferior a 25. Se reconocen los avisos de cuota de `Information` y `Note`
en respuestas HTTP 200, además del estado HTTP 429, incluso sin cuerpo JSON.

El rechazo genera `AlphaVantageQuotaError` y guarda un bloqueo para esa clave. Si el
aviso es del límite diario, dura 24 horas desde la respuesta, como margen conservador
al desconocer el reinicio real del proveedor. Si es un aviso de ritmo (más de una
petición por segundo o demasiadas por minuto) o un HTTP 429 sin más detalle, dura 60
segundos; nunca acorta un bloqueo diario ya guardado. Los siguientes intentos se
detienen antes del envío, también después de reiniciar el proceso; no prolongan el
bloqueo y la caché sigue disponible. Los errores de clave o de acceso a endpoints
premium no activan este bloqueo. Si falla la persistencia del rechazo, se informa
del problema y el cliente actual conserva el bloqueo en memoria.

Esto permite reaccionar al consumo compartido, pero no sincroniza los contadores de
máquinas distintas: cada instalación o runner nuevo debe recibir primero el aviso
del proveedor para conocer un agotamiento externo. No puede anticiparlo ni conocer
la cuota restante global sin un registro central compartido.
En las pruebas locales de integración, `ALPHA_VANTAGE_INTEGRATION=0` permite omitir
Alpha Vantage para reservar cuota.

El historial indica además cómo ajusta el proveedor los cierres (`price_basis`), si
empieza después de la fecha pedida (`partial_history`) y cuántas fechas sin precio
de cierre ha descartado el adaptador (`dropped_rows`). Una fecha sin cierre no
invalida toda la descarga: se descarta y el informe lo indica.

`mean` y `std` se calculan con los precios cada vez que se consultan, por lo que
siempre corresponden a los datos. Los modelos no se modifican después de crearse.

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

# Los mismos parámetros se pueden agrupar en un objeto y reutilizar.
from src.simulation import SimulationSettings

settings = SimulationSettings(**options)
result = portfolio.monte_carlo(settings)

# El mismo método simula un único activo, partiendo de su último precio.
ibm = portfolio.assets[0].monte_carlo(settings)
ibm.plot()
```

`SimulationSettings` reúne los parámetros con sus valores por defecto y los valida
una sola vez; la consola lo crea antes de descargar datos. Sin indicar `seed`, se
utiliza 42 en todos los casos, de modo que la simulación es reproducible; con
`seed=None` cada ejecución produce escenarios distintos.

`Asset` y `Portfolio` comparten el mismo cálculo, `simulate()`. Cada clase indica con
`simulation_inputs()` qué precios simular y con qué valores iniciales; la cartera
añade además sus pesos de rebalanceo. `expected_returns` y `volatilities` admiten un
valor para todos los activos o un diccionario por símbolo, también cuando se simula
un único activo.

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
cambia estas referencias. El informe identifica la fuente de cada activo y de
cada referencia utilizada.

### Datos económicos: FRED y no ALFRED

La inflación y el tipo de interés se consultan en FRED, que ofrece la última versión de
cada serie con cada dato en la fecha a la que corresponde. Solo intervienen en medidas que
se calculan al final del periodo (rentabilidad real, Sharpe, Sortino) para describir lo
que ocurrió, y para eso la cifra revisada es la mejor estimación. Ninguna decisión de la
cartera depende de ellas (los pesos son fijos), así que no hay sesgo de anticipación que
corregir.

ALFRED, el archivo de versiones de FRED, solo aportaría algo si una regla de inversión
usara el dato macro disponible en cada fecha. Para estas medidas no mejora el resultado y
tiene inconvenientes: las series predeterminadas apenas se revisan (los tipos de mercado,
nunca), el IPC entraría con la primera publicación y desfasado un mes, el €STR solo tiene
versiones archivadas desde 2022 y la API rechaza más de 2000 versiones por consulta, lo que
impide pedir el tipo diario de más de unos ocho años.

Desde Python, `FredAPI().get_series(serie, inicio, fin)` devuelve la serie; los tipos de
cambio de FRED se descargan con `load_fred_fx_rates()`.

Desde Python, las referencias se cargan con `load_references(divisa, inicio, fin)`
(o con `load_market_references()` para elegir cada serie) y se pasan al análisis:
`portfolio.analyze(references)`. Los tipos de cambio forman parte de la cartera
(`fx_rates`), porque sin ellos no se puede valorar; `load_portfolio()` los descarga
con `load_fx_rates()` cuando se indica `reporting_currency`. Todas estas funciones
admiten el proveedor como argumento, de modo que se pueden sustituir sin cambiar
el resto del programa.

Los datos disponibles no son idénticos. El adaptador diario de Alpha Vantage usa
precios sin ajustar y solicita las últimas 100 observaciones. Si no cubren las
fechas indicadas, la descarga se rechaza; no se recorta el período sin avisar.
El historial completo y el cierre ajustado requieren otras condiciones de acceso
del proveedor. La información de empresas procede de OVERVIEW y puede no estar
disponible para todos los instrumentos. Para construir y valorar un activo es
necesario conocer su divisa; no se supone USD si falta ese dato.

Un desdoblamiento puede distorsionar las rentabilidades calculadas con precios
sin ajustar. El informe advierte de ello para cada activo con precios sin ajustar,
sea cual sea el proveedor; los cierres de Yahoo ya se ajustan por desdoblamientos.
Los símbolos también pueden variar entre proveedores, especialmente en mercados
internacionales.

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
distribución, más los de simulación si se añade `--simulate` o `--report`. No guarda
archivos por sí solo ni descarga las referencias económicas, por lo que el gráfico de
la cartera no incluye el índice. Puede combinarse con `--report` para ver los gráficos
y guardar el informe completo.

Desde Python, `portfolio.plots_report()` devuelve ese mismo conjunto como un
diccionario de figuras (`portfolio`, `assets`, `distribution` y `risk_return`). Con
`portfolio.plots_report("graficos")` también se guardan como PNG en esa carpeta.

Cada informe crea una carpeta dentro de `informes`, en la carpeta desde la que
ejecutas el programa, o dentro de la indicada con `--output-dir` (`directory=` desde
Python):

```text
informes/
└── AAAA-MM-DD_HH-MM-SS/
    ├── AAAA-MM-DD_HH-MM-SS.md
    ├── analisis_cartera.png
    ├── evolucion_activos.png
    ├── distribucion_rentabilidades.png
    ├── riesgo_rentabilidad.png
    └── simulacion_monte_carlo.png
```

El informe completo incluye la imagen de Monte Carlo. Si se generan
dos informes en el mismo segundo, se añaden microsegundos al nombre para conservar ambos.
El informe se prepara en una carpeta temporal y solo aparece cuando se ha guardado
completo: si algo falla, no quedan carpetas a medias ni gráficos abiertos.

## Documentación de arquitectura

La carpeta `arquitectura/` contiene diagramas editables de Excalidraw: paquetes y
dependencias, la revisión de arquitectura, diagramas UML de clases y los flujos de uso
desde la consola y desde Python. Consulta `arquitectura/README.md` para abrirlos.

## Comprobaciones

```powershell
python -B -m ruff check --no-cache .
python -B -m ruff format --no-cache --check .
python -B -m unittest discover -s tests -v
```

Las pruebas no necesitan claves ni acceso a las API. GitHub Actions comprueba
código y formato con Python 3.14 (la de `.python-version`) y las pruebas con la
versión mínima (3.11) y con la del equipo (3.14). El trabajo «Paquete instalable»
construye la distribución, revisa sus metadatos con `twine check` y repite las
pruebas importando `src` desde la rueda instalada, no desde el repositorio. El
trabajo «Búsqueda de claves filtradas» revisa todo el historial con gitleaks y las
reglas de `.gitleaks.toml`: el escaneo de secretos de GitHub no reconoce las claves
de Alpha Vantage ni de FRED.

Las pruebas de integración (`tests/integration_apis.py`) consultan las API reales:
comprueban que las series predeterminadas de FRED siguen actualizándose, que
Alpha Vantage y Yahoo Finance responden y que el informe incluye inflación y Sharpe.
No forman parte de la suite anterior. En GitHub Actions las ejecuta el trabajo
«Integración con las API reales» en cada pull request, tras integrar en `main`, cada
lunes y a mano desde la pestaña Actions (Run workflow), con los secretos
`FRED_API_KEY` y `ALPHA_VANTAGE_API_KEY` del repositorio (Settings → Secrets and
variables → Actions). Si falta un secreto, el trabajo falla en lugar de omitir las
pruebas reales; por eso las pull requests desde forks, que no reciben secretos, no lo
superan.

Para reservar la cuota diaria de Alpha Vantage, una pull request solo lo consulta si
cambia `src/providers/`, `src/validation.py`, `tests/integration_apis.py`,
`pyproject.toml` o el pipeline; tras integrar en `main`, cada lunes y a mano se
consulta siempre. Si la cuota está agotada, la prueba se omite con un aviso en el
resumen de la ejecución en lugar de fallar.

El trabajo «Comprobaciones completas» resume el resultado: solo se supera si la
calidad, las pruebas con Python 3.11 y 3.14, el paquete, la búsqueda de claves y la
integración se superan. Es la comprobación obligatoria para integrar en `main`. Las
ramas se prueban al abrir su pull request; el push solo lanza el pipeline en `main`. En
local, las pruebas de integración usan las claves de `.env` o del entorno:

```powershell
python -B -m unittest tests.integration_apis -v
```

`__pycache__` está excluido
en `.gitignore`. La caché de respuestas de Yahoo Finance, Alpha Vantage y FRED se
conserva en `.cache/market-data`, dentro de la carpeta desde la que ejecutas el
programa, para evitar consultas repetidas; no contiene las claves en texto y las
respuestas de más de un día se eliminan automáticamente. Yahoo guarda por símbolo la
ficha y un único historial: cambiar los parámetros de la simulación no descarga nada,
cambiar un activo solo descarga ese activo y un intervalo de fechas contenido en otro
ya consultado se reutiliza. Para forzar una descarga nueva, borra esa carpeta.

## Lectura y selección del informe

El informe comienza con cinco cifras y las advertencias. Por defecto, las demás
secciones quedan plegadas en visores Markdown compatibles con `<details>`.
`detail="full"` produce Markdown completamente desplegado, también útil para
visores que no admitan esos elementos HTML.

```powershell
python src/main.py --assets cartera_ejemplo.txt --report --report-detail full
python src/main.py --assets cartera_ejemplo.txt --report --report-sections summary warnings performance
```

Desde Python se pueden reutilizar los mismos resultados sin descargar de nuevo:

```python
from src.analysis import WarningThresholds

analysis = portfolio.analyze(
    warning_thresholds=WarningThresholds(
        asset_weight=0.45, sector_weight=0.55, correlation=0.85, drawdown=0.30, volatility=0.25
    ),
)
text = analysis.markdown(detail="full")
path = analysis.report(sections=["summary", "warnings", "performance"])
# También se admiten sections, detail y directory directamente en portfolio.report().
```

Las secciones disponibles, en orden de lectura, son `summary`, `warnings`,
`composition`, `performance`, `diversification`, `simulation` y `data`.
Seleccionar secciones solo cambia la presentación. Se guardan únicamente las
imágenes utilizadas por esas secciones. Si `portfolio.report()` o la consola
excluyen `simulation`, no generan Monte Carlo; `--simulate` lo solicita de forma
independiente. Sin selección explícita se conserva la simulación automática de
`portfolio.report()` y `--report`. `analysis.report()` sigue permitiendo un
informe histórico o un resultado de simulación proporcionado explícitamente.

El resumen muestra valor final, rentabilidad anualizada, diferencia anual frente
al índice, caída máxima y Sharpe. Indica las fechas comunes de la comparación:
el gráfico de cartera e índice utiliza exactamente esas fechas y la divisa del
informe, con ambos recorridos normalizados a 100 al inicio común.

Las advertencias de riesgo se encuentran en `analysis.risk_warnings`, con código,
nivel, valor observado, umbral y unidad (`percent`, `ratio` o `days`). Los demás
avisos están en `analysis.notices`: cada `Notice` indica si señala un problema de los
datos (`data`) o un criterio de metodología (`method`), y el informe los presenta por
separado. `analysis.metric_notes` explica por qué falta cada medida sin calcular.
Las reglas usan pesos actuales y omiten correlaciones sin
posición o no definidas; un sector desconocido no se interpreta como una apuesta
sectorial. Son umbrales orientativos, no recomendaciones de inversión. La ausencia
de referencias sigue dejando sus métricas sin calcular, sin suponer un tipo cero.

`analysis.drawdown_episode` describe la mayor caída: último pico anterior al valle,
primera recuperación y días naturales desde el pico. Si no se recuperó, la duración
termina en la última fecha del análisis; si no hubo caídas, las fechas quedan vacías.

`analysis.monthly_returns` y `analysis.annual_returns` contienen rentabilidad,
número de observaciones y cobertura parcial. El mejor y peor mes se eligen solo
entre meses completos. Se exige un cierre previo y el final del período usando
lunes-viernes como aproximación conservadora, sin asumir festivos de una bolsa.
Los períodos sin observaciones no se convierten en rentabilidad cero y un retorno
que atraviese un mes/año entero sin precios no se asigna íntegramente al período
de llegada. Estas tablas son rentabilidades por calendario, sin anualización.

El panel histórico compara cartera e índice, anota la recuperación de la mayor
caída y enfrenta pesos actuales con contribuciones al riesgo. Se añade
`riesgo_rentabilidad.png`, un gráfico de volatilidad y rentabilidad anualizadas
para la cartera y sus activos. Los resultados numéricos proceden del análisis;
los generadores de texto y gráficos no consultan proveedores.
