# MIAX B1-T1

Indica qué activos componen tu cartera y qué proporción quieres invertir en cada
uno. El programa consulta sus precios y la información de las empresas y analiza
una cartera hipotética con rebalanceo mensual. Genera gráficos, simulaciones de
Monte Carlo e informes en español.

## Inicio rápido

**Requisitos previos:** [Python](https://www.python.org/downloads/) 3.11 o posterior y
[Git](https://git-scm.com/downloads). No hace falta ninguna clave de API. En Windows, al
instalar Python, marca «Add Python to PATH».

```bash
git clone https://github.com/Diegopasfer1909/tallerb1-t1-equipo7.git
cd tallerb1-t1-equipo7
```

Crea el entorno virtual una vez y actívalo cada vez que abras una terminal nueva:

| Sistema | Crear (una vez) | Activar |
| --- | --- | --- |
| Windows (PowerShell) | `python -m venv .venv` | `.\.venv\Scripts\Activate.ps1` |
| macOS / Linux | `python3 -m venv .venv` | `source .venv/bin/activate` |

Con el entorno activado, `python` funciona igual en todos los sistemas. Instala el proyecto
y genera un primer informe con la cartera de ejemplo:

```bash
python -m pip install -e .
python src/main.py --assets cartera_ejemplo.txt --simulate --report
```

En consola aparecen las posiciones y el resumen de la simulación; el informe Markdown y sus
gráficos se guardan en una carpeta nueva dentro de `informes/`, cuya ruta se indica al final.
Ábrelo con cualquier visor de Markdown (en VS Code, `Ctrl+Shift+V`). Si prefieres indicar
cuántas acciones tienes de cada activo en lugar de pesos, usa `--shares` (por ejemplo,
`--shares AAPL:10 SPY:5`; ver [Cartera por número de acciones](#cartera-por-número-de-acciones)).

## Instalación

El proyecto admite Python 3.11 o posterior. El equipo desarrolla y comprueba con
Python 3.14, indicado en `.python-version`; es la versión recomendada para
obtener los mismos resultados. Desde la carpeta del proyecto:

```powershell
# Windows (PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

```bash
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

`[dev]` añade Ruff, la herramienta de comprobación de código; para usar el programa basta
con `python -m pip install -e .`. La instalación editable permite ejecutar el archivo
principal utilizando los paquetes de `src`. Al trasladar el proyecto, recrea el entorno e
instala de nuevo.

### Problemas frecuentes

| Mensaje | Solución |
| --- | --- |
| `python` no se reconoce (macOS / Linux) | Usa `python3` para crear el entorno; una vez activado, `python` ya funciona |
| `python` no se reconoce o abre la Microsoft Store (Windows) | Crea el entorno con `py -m venv .venv`, o reinstala Python marcando «Add Python to PATH» |
| «la ejecución de scripts está deshabilitada» al activar el entorno (Windows) | Ejecuta una vez `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` y vuelve a activarlo |
| `Yahoo no ha podido descargar los precios` | Yahoo limita las consultas seguidas: espera unos minutos y repite; las respuestas ya descargadas se reutilizan desde la caché |
| Aviso de que falta `FRED_API_KEY` | No es un error: el informe se genera sin las medidas que dependen de FRED (ver [Claves de API](#claves-de-api-opcionales)) |

### Claves de API (opcionales)

El programa funciona sin ninguna clave: Yahoo Finance y el BCE no la necesitan. Las claves solo
amplían lo que se puede hacer. Para añadirlas, copia `.env.example` a `.env` y completa las que
quieras; el programa busca `.env` en la carpeta desde la que lo ejecutas y en las superiores.

| Sin clave | Con `ALPHA_VANTAGE_API_KEY` | Con `FRED_API_KEY` |
| --- | --- | --- |
| Precios y fichas de Yahoo Finance, conversión de divisas, Monte Carlo, gráficos e informe con índice de referencia, oro, ETF de Bunds y tipo libre de riesgo en EUR | `--provider alpha_vantage` | El informe añade inflación, rentabilidad real, VIX, Brent y, en USD, tipo libre de riesgo, Sharpe, Sortino y alfa |

Antes de descargar nada, la consola comprueba las claves que necesita lo que has pedido:

- Si eliges `--provider alpha_vantage` sin su clave, se detiene con un mensaje que
  indica qué falta y propone `--provider yahoo`.
- Si pides `--report` sin `FRED_API_KEY`, avisa de lo que no incluirá y genera el
  informe con el resto; el informe explica qué medidas faltan y por qué.
- Si un proveedor rechaza una clave (no válida o sin cuota), el mensaje muestra el
  motivo que da el proveedor, sin mostrar la clave.

## Uso

```powershell
python src/main.py --assets IBM:0.6 MSFT:0.4
python src/main.py --assets cartera_ejemplo.txt --simulate --report
python src/main.py --provider alpha_vantage --assets IBM:1 --simulate --report
python src/main.py --provider alpha_vantage --assets cartera_ejemplo.txt --simulate --report
python src/main.py --assets IBM:0.6 MSFT:0.4 --start 2025-10-01 --end 2026-10-01 --report
python src/main.py --assets cartera_ejemplo.txt --currency EUR --simulate --plots-report --report
python src/main.py --assets SAN.MC:0.5 ITX.MC:0.5 --benchmark ^IBEX --rebalance none --capital 50000 --report
python src/main.py --assets IBM:0.6 MSFT:0.4 --report --benchmark ^IXIC
python src/main.py --shares AAPL:10 SPY:5 --simulate --report
```

| Opción | Uso |
| --- | --- |
| `--provider yahoo` o `--provider alpha_vantage` | Proveedor de precios; por defecto, Yahoo Finance |
| `--assets SÍMBOLO:PESO ...` o `--assets archivo.txt` | Pesos objetivo de la cartera; obligatorio salvo con `--shares` |
| `--shares SÍMBOLO:ACCIONES ...` o `--shares archivo.txt` | Número de acciones de cada activo, en lugar de pesos (ver [Cartera por número de acciones](#cartera-por-número-de-acciones)) |
| `--start AAAA-MM-DD` | Fecha de inicio incluida; por defecto, hace un año con Yahoo y 120 días con Alpha Vantage (el modo `compact` ofrece unas 100 sesiones) |
| `--end AAAA-MM-DD` | Fecha de fin excluida; por defecto, hoy |
| `--simulate` | Simular la evolución de la cartera a partir de los datos históricos |
| `--plots-report` | Mostrar el conjunto de gráficos sin crear un documento |
| `--report` | Generar Monte Carlo y guardar el informe Markdown con sus imágenes |
| `--benchmark ^IBEX` | Índice de referencia; por defecto, `^GSPC` en USD y `^STOXX50E` en EUR |
| `--report-sections summary risk ...` | Secciones del informe; por defecto, todas |
| `--report-detail compact` o `full` | Secciones en desplegables o todo a la vista; por defecto, `compact` |
| `--output-dir CARPETA` | Carpeta de los informes; por defecto, `informes` dentro de la carpeta actual |
| `--currency EUR` | Convertir los precios y las posiciones a la divisa indicada |
| `--benchmark ^IXIC` | Índice o fondo de Yahoo Finance contra el que comparar la cartera, en lugar del predeterminado por divisa; requiere `--report` o `--plots-report` |
| `--steps 252` | Sesiones futuras de la simulación |
| `--simulations 10000` | Número de escenarios |
| `--equity-premium 0.045` | Retorno anual de la renta variable sobre el tipo libre de riesgo |
| `--return 0.08` | Retorno anual μ para todos los activos |
| `--return IBM:0.08 MSFT:0.10` | Cambiar μ por activo; los demás usan el cálculo por defecto |
| `--volatility 0.20` | Volatilidad anual σ para todos los activos |
| `--volatility IBM:0.20 MSFT:0.30` | Cambiar σ por activo manteniendo las correlaciones históricas |
| `--confidence 0.95` | Confianza de las medidas de cola VaR y CVaR; debe estar entre 0,5 y 1 |
| `--seed 42` | Semilla para reproducir la simulación |
| `--capital 10000` | Capital hipotético al inicio del histórico; no se usa con `--shares` |
| `--rebalance monthly` o `--rebalance none` | Rebalancear o mantener las posiciones; no se usa con `--shares` |
| `--report-detail compact` o `--report-detail full` | Informe con secciones plegadas (por defecto) o todo desplegado |
| `--report-sections summary warnings ...` | Secciones del informe que se incluyen; por defecto, todas (ver [Lectura y selección del informe](#lectura-y-selección-del-informe)) |

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

### Cartera por número de acciones

En lugar de pesos, puedes indicar cuántas acciones o participaciones tienes de cada activo
(acciones, ETF o fondos de Yahoo Finance). Se admiten fracciones:

```powershell
python src/main.py --shares AAPL:10 SPY:5 MSFT:2.5 --simulate --report
python src/main.py --shares SAN.MC:100 ITX.MC:20 SPY:5 --currency EUR --report
```

También puedes usar un archivo `.txt` con el mismo formato que los pesos, una línea por
activo (`AAPL:10`). `--assets` y `--shares` no se pueden combinar. Cada cantidad debe ser
positiva: incluye solo los activos que tienes.

- El valor de la cartera es el número de acciones por el último precio de cierre.
- El historial supone que se han mantenido esas mismas acciones durante todo el período,
  sin compras, ventas ni rebalanceo. Los pesos iniciales resultan de las cantidades en la
  primera fecha común y los actuales, de su evolución.
- Se valora con `Close`, no con `Adj Close`: así cada posición vale exactamente sus
  acciones por su precio. Los dividendos cobrados no se suman.
- Monte Carlo parte del valor actual y tampoco rebalancea: las cantidades no cambian.
- `--capital` y `--rebalance` no se admiten con `--shares`, porque el valor inicial sale de
  las cantidades y estas no se reajustan.
- Solo con Yahoo Finance: Alpha Vantage publica cierres sin ajustar por splits, y un split
  dentro del período multiplicaría el valor de las fechas anteriores.
- El programa no conoce el precio ni la fecha de compra: la rentabilidad se mide desde el
  inicio del período analizado, no desde la compra.

Desde Python, `load_portfolio_from_shares({"AAPL": 10, "SPY": 5}, YahooFinanceAPI(), inicio,
fin)` (en `src.portfolio_loader`) descarga los precios y crea la cartera con
`Portfolio.from_units()`; `portfolio.units` conserva las cantidades y
`portfolio.holdings()` las muestra en la columna `shares`. Si analizas esa cartera con
`price_column="Adj Close"`, los dividendos se reinvierten: el valor deja de ser acciones ×
precio, así que `holdings()` no incluye esa columna y el informe lo explica.

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
vez y se reutiliza en cada consulta. No basta con declararla `frozen`: consulta
[Instantáneas inmutables y estadísticos](#instantáneas-inmutables-y-estadísticos).

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
print(history.mean["Close"], history.std["Close"])  # calculadas al crear el historial

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

`mu` es la deriva anual del modelo y `sigma`, su volatilidad anual. `sigma` y las
correlaciones se estiman con las rentabilidades simples históricas, anualizadas con 252
sesiones. El retorno, si no se indica, es:

```text
mu = tipo libre de riesgo actual + prima de riesgo × parte del activo en renta variable
```

La prima es del 4,5 % por defecto y se cambia con `--equity-premium`. Las acciones y los
índices cuentan como 100 % renta variable; en ETF y fondos se usa la composición que publica
Yahoo Finance. Así, un ETF 60/40 recibe el 60 % de la prima, y la renta fija, el oro y lo que
no se puede clasificar reciben solo el tipo libre de riesgo; el informe lo indica. No se usa
el retorno de cada bono porque Yahoo no publica su rentabilidad a vencimiento, de modo que en
bonos a largo plazo este valor puede quedarse algo corto. Sin tipo libre de riesgo para la
divisa se usa el histórico y se avisa.

Por ejemplo, `--return 0.08`
fija mu en 0,08: el crecimiento esperado a un año es `exp(0.08) - 1`, aproximadamente
un 8,33 %. No se interpreta como un crecimiento anual exacto del 8 %.

Los choques por activo se correlacionan mediante Cholesky de la covarianza diaria.
Si la matriz es singular, por ejemplo con activos idénticos o volatilidad cero,
se utiliza una factorización por autovalores. El informe indica el método aplicado.
Cambiar sigma conserva las correlaciones históricas. Los supuestos por activo
pueden ser parciales; el resto utiliza sus parámetros históricos.

No se usa el retorno histórico por defecto porque es el supuesto más débil: la volatilidad y
las correlaciones se estiman bien con datos diarios, pero el retorno depende de los años de
historia, no del número de observaciones, y refleja sobre todo lo que ya ocurrió. El informe
repite la simulación con el retorno histórico y con solo el tipo libre de riesgo, con los
mismos escenarios aleatorios, y compara la probabilidad de pérdida, nominal y real, la
variación mediana y el VaR. Todos los importes son nominales.

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

Las fuentes auxiliares se mantienen separadas: el índice de referencia, el oro (`GC=F`),
el ETF de Bunds (`EXHD.DE`) y los cambios de divisa automáticos se consultan en Yahoo
Finance; la inflación, el VIX, el Brent y el tipo libre de riesgo en USD se consultan en la API
de FRED, que necesita `FRED_API_KEY`; el tipo libre de riesgo en EUR, en la API de datos del BCE,
sin clave. Elegir Alpha Vantage para los activos no
cambia estas referencias. El informe identifica la fuente de cada activo y de cada
referencia utilizada.

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
nunca), el IPC entraría con la primera publicación y desfasado un mes y la API rechaza más de 2000 versiones por consulta, lo que
impide pedir el tipo diario de más de unos ocho años.

Desde Python, `FredAPI().get_series(serie, inicio, fin)` devuelve la serie; los tipos de
cambio de FRED se descargan con `load_fred_fx_rates()`.

Desde Python, las referencias se cargan con `load_references(divisa, inicio, fin)`
(o con `load_market_references()` para elegir cada serie) y se pasan al análisis:
`portfolio.analyze(references)`. `load_references("USD", inicio, fin,
benchmark_symbol="^IXIC")` cambia solo el índice y conserva la inflación y el tipo de
interés predeterminados. Los tipos de cambio forman parte de la cartera
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

Las rentabilidades, la simulación y el informe utilizan Adj Close, que incluye los
dividendos, cuando lo publican todos los activos; si no, usan Close y el informe lo indica
en la sección de calidad de los datos. Se toman 252 períodos por año. La simulación de
Monte Carlo genera por defecto 10.000 escenarios de 252 períodos, con la semilla 42,
volatilidad histórica y el retorno explicado en "Parámetros de Monte Carlo". El informe indica
si se han usado estos criterios y qué comando los cambia. Salvo la rentabilidad real, todas las
cifras son nominales: incluyen dividendos y no descuentan la inflación.

Las referencias se eligen según la divisa del informe:

| Divisa | Índice | Inflación | Tipo libre de riesgo |
| --- | --- | --- | --- |
| USD | S&P 500 (`^GSPC`) | IPC de EE. UU. (`CPIAUCSL`) | Letra a 3 meses (`DGS3MO`) |
| EUR | EURO STOXX 50 (`^STOXX50E`) | IPCA de la zona euro (`CP0000EZ19M086NEST`) | Deuda AAA de la zona euro a 3 meses, BCE (`YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_3M`) |

El índice se puede cambiar con `--benchmark`; si cotiza en otra divisa, se descarga su
cambio para compararlo en la divisa del informe. Para otras divisas, las medidas sin
referencia configurada quedan sin calcular: no se supone un tipo del 0 %.

**Tipo libre de riesgo.** Es deuda pública de máxima calidad a 3 meses en la divisa de la
cartera, de modo que ambas divisas miden lo mismo. En euros no hay una serie gratuita de letras
cotizadas, así que se usa la curva de deuda AAA de la zona euro que estima el BCE, disponible
desde septiembre de 2004; la €STR mediría riesgo bancario, no de Estado. Cada sesión toma el
último tipo anual publicado y lo pasa a diario con `(1 + tipo) ** (1 / 252) - 1`, que es lo
que se habría ganado ese día sin arriesgar. Sharpe, Sortino y el alfa de Jensen restan ese dato
a la rentabilidad del mismo día. Si no hay un dato reciente para todas las fechas, esas medidas
quedan sin calcular.

**Deuda alemana.** El Bund a 10 años no se usa como tipo libre de riesgo: tiene riesgo de
precio y mezclaría divisas en una cartera en dólares. Su tipo tampoco indica lo que ganó
quien tenía bonos, porque no recoge la variación de su precio. Por eso, en carteras en euros,
"Diferencia frente a deuda alemana" compara la rentabilidad anualizada de la cartera con la
del ETF `EXHD.DE` (deuda alemana a 5,5-10,5 años), con cupones y variación de precio, en las
mismas fechas.

## Validación de entradas: por qué un contrato estricto

El enunciado pide decidir si se valida la entrada o se admite cualquier serie. Validamos
en las fronteras (consola, adaptadores y constructores de los modelos) porque un dato
inválido rara vez falla donde entra: avanza varios pasos y produce un resultado plausible
pero erróneo.

| Regla | Qué evita |
| --- | --- |
| Pesos entre 0 y 1 que suman 1 (tolerancia 1e-5), sin convertir porcentajes | Que `IBM:60` se lea como un 6.000 %, o simular cortos y apalancamiento que el modelo no contempla |
| `DatetimeIndex` sin fechas repetidas, vacías ni zona horaria | Alinear mal calendarios y calcular rentabilidades entre filas desordenadas |
| `Close` obligatorio, positivo y finito; columnas únicas | Rentabilidades infinitas con un precio cero, logaritmos de negativos y NaN que se propagan |
| Divisa conocida, nunca supuesta | Sumar dólares, euros o peniques como si fueran la misma unidad |
| Fechas comunes sin rellenar huecos | Rentabilidades nulas inventadas que rebajan la volatilidad y las correlaciones |
| Saltos diarios de más del 50 %: se marcan sin tocarlos | Ocultar desdoblamientos mal ajustados o errores de la fuente |
| Antigüedad máxima de tipos de cambio y datos macro | Usar un dato de hace meses como si fuera de la fecha valorada |
| Validar antes de descargar | Gastar cuota de Alpha Vantage en una petición cuyo resultado se rechazaría |

Las consecuencias son deliberadas:

- Los errores aparecen pronto, en español y con el motivo, antes de descargar nada.
- Se rechazan datos que serían válidos en otros contextos, como precios negativos de
  futuros o una ficha sin divisa; en ese caso hay que indicarla expresamente.
- Los datos complementarios (ficha, índice, inflación, tipo de interés) no detienen el
  análisis: la medida que dependa de ellos aparece como «No disponible», con su causa.

Admitir cualquier serie simplificaría la carga, pero repartiría las comprobaciones por
cada cálculo y no permitiría distinguir un resultado correcto de uno contaminado.

**Descarga en lote.** `load_portfolio()` descarga los N activos uno tras otro con el mismo
proveedor, una de las dos opciones del enunciado («simultánea o en lote»). Así se respeta
la cuota diaria de Alpha Vantage sin coordinar hilos, cada error se atribuye a su símbolo y
la caché evita repetir consultas; con pocas decenas de activos el tiempo no es relevante.
Paralelizar sería un cambio local del cargador: el contrato `PriceProvider` no cambia.

## Contrato temporal de las medidas

La intersección de calendarios puede eliminar fechas intermedias. Para que eso no altere
los resultados, cada medida declara cómo trata el tiempo:

- **Crecimiento anualizado** (cartera, activos, comparación con el índice e inflación):
  `(valor final / valor inicial) ^ (365,25 / días naturales) − 1`. Solo depende de las
  fechas extremas, de modo que perder fechas intermedias no lo cambia. La cartera y el
  índice se comparan entre las mismas fechas extremas.
- **Dispersión** (volatilidad, Sharpe, Sortino, VaR por período y los μ y σ de Monte Carlo):
  se calcula por observación y se escala con `periods_per_year` (252 por defecto). Supone
  observaciones regulares. El informe avisa si la separación típica supera cinco días o si
  hay menos del 90 % de las observaciones esperadas para la duración del historial.
- **Historial corto**: se mide en días naturales (menos de 350), no en número de
  observaciones, porque un año bursátil puede tener menos de 252 sesiones.

La media aritmética (Sharpe, μ) y el crecimiento compuesto pueden tener signos opuestos:
con +20 % y −19 %, la media es +0,5 %, pero el valor cae un 2,8 % (1,20 × 0,81 − 1). El
informe lo explica junto a las medidas.

## Instantáneas inmutables y estadísticos

`frozen=True` impide reasignar atributos, pero no modificar el contenido de un
`DataFrame` o una `Series`. Como la cartera memoriza su valoración, los datos de los que
depende son instantáneas protegidas:

- `PriceHistory` valida y guarda una copia ordenada; `history.prices` devuelve otra copia,
  así que modificarla no altera el historial ni las carteras que lo usan.
- `history.mean` y `history.std` se calculan al crear el historial, como pide el
  enunciado, y solo sobre las columnas de precio (`Open`, `High`, `Low`, `Close`,
  `Adj Close`). `Volume` no es un precio y no se resume.
- `EconomicIndicator.values` (inflación, tipos y cambios) y `Portfolio.target_weights` son
  de solo lectura: intentar modificarlos produce un `ValueError`.
- Para otra composición se crea otra cartera, por ejemplo con
  `dataclasses.replace(portfolio, target_weights={"IBM": 0.5, "MSFT": 0.5})`, que vuelve a
  validar los pesos.

## Gráficos e informes

`--plots-report` muestra los gráficos del informe, más el de la simulación si se añade
`--simulate` o `--report`. No guarda archivos por sí solo ni descarga las referencias económicas,
por lo que la evolución de la cartera no incluye el índice, salvo que se elija uno con
`--benchmark`, y tampoco hay gráficos de mercado. Puede combinarse con `--report` para ver los
gráficos y guardar el informe completo.

Desde Python, `portfolio.plots_report()` devuelve ese conjunto como un diccionario de
figuras. Con `portfolio.plots_report("graficos")` también se guardan como PNG en esa carpeta.

Cada informe crea una carpeta dentro de `informes`, en la carpeta desde la que
ejecutas el programa, o dentro de la indicada con `--output-dir` (`directory=` desde
Python):

```text
informes/
└── AAAA-MM-DD_HH-MM-SS/
    ├── AAAA-MM-DD_HH-MM-SS.md
    ├── exposicion.png            # 3. Composición
    ├── evolucion.png             # 4. Rentabilidad
    ├── evolucion_activos.png
    ├── rentabilidad_anual.png
    ├── drawdown.png              # 5. Riesgo
    ├── distribucion.png
    ├── riesgo_rentabilidad.png   # 6. Rentabilidad ajustada al riesgo
    ├── correlaciones.png         # 7. Diversificación
    ├── pesos_contribucion.png
    ├── volatilidad_vix.png       # 8. Contexto de mercado
    ├── correlacion_bund.png
    └── montecarlo.png            # 9. Monte Carlo
```

Los gráficos de mercado solo se crean si se han podido descargar sus datos. Si se generan
dos informes en el mismo segundo, se añaden microsegundos al nombre para conservar ambos.
El informe se prepara en una carpeta temporal y solo aparece cuando se ha guardado
completo: si algo falla, no quedan carpetas a medias ni gráficos abiertos.

## Documentación de arquitectura

[ARQUITECTURA.md](ARQUITECTURA.md) reúne siete láminas UML: vista de componentes,
modelo de dominio, contratos y proveedores, contrato de simulación, dependencias entre
paquetes, actividad de la consola y secuencia de una consulta a Alpha Vantage con caché y
cuota. Cada lámina está en `diagramas/` como SVG, PNG (para diapositivas), Excalidraw
editable y Mermaid; [diagramas/README.md](diagramas/README.md) explica cómo regenerarlas.

[docs/arquitectura.md](docs/arquitectura.md) resume en Mermaid las capas, las clases y el flujo de una
ejecución con el proveedor del BCE y el contexto de mercado, posteriores a esas láminas.

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
comprueban que las series predeterminadas de FRED y del BCE siguen actualizándose, que
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
en `.gitignore`. La caché de respuestas de Yahoo Finance, Alpha Vantage, FRED y el BCE se
conserva en `.cache/market-data`, dentro de la carpeta desde la que ejecutas el
programa, para evitar consultas repetidas; no contiene las claves en texto y las
respuestas de más de un día se eliminan automáticamente. Yahoo guarda por símbolo la
ficha y un único historial: cambiar los parámetros de la simulación no descarga nada,
cambiar un activo solo descarga ese activo y un intervalo de fechas contenido en otro
ya consultado se reutiliza. Para forzar una descarga nueva, borra esa carpeta.

## Lectura y selección del informe

El informe tiene diez secciones, cada una en un desplegable que responde a una pregunta:

| Nº | Clave | Sección | Pregunta |
| --- | --- | --- | --- |
| 1 | `summary` | Resumen | ¿Cómo ha ido, en cinco cifras? |
| 2 | `warnings` | Advertencias | ¿Qué hay que vigilar? |
| 3 | `composition` | Composición | ¿Qué contiene la cartera? |
| 4 | `returns` | Rentabilidad | ¿Cuánto ha ganado? |
| 5 | `risk` | Riesgo | ¿Cuánto ha arriesgado? |
| 6 | `risk_adjusted` | Rentabilidad ajustada al riesgo | ¿Ha compensado el riesgo? |
| 7 | `diversification` | Diversificación | ¿Está bien repartida? |
| 8 | `market` | Contexto de mercado | ¿Qué pasa fuera de la cartera que le afecte? |
| 9 | `simulation` | Monte Carlo | ¿Qué puede pasar a futuro? |
| 10 | `data` | Calidad de los datos | ¿Cuánto fiarse de todo lo anterior? |

`detail="full"` produce Markdown completamente desplegado, también útil para visores que no
admitan esos elementos HTML.

```powershell
python src/main.py --assets cartera_ejemplo.txt --report --report-detail full
python src/main.py --assets cartera_ejemplo.txt --report --report-sections summary warnings risk
```

Desde Python se pueden reutilizar los mismos resultados sin descargar de nuevo:

```python
from src.analysis import WarningThresholds

analysis = portfolio.analyze(
    warning_thresholds=WarningThresholds(asset_weight=0.45, drawdown=0.30, vix=35),
)
text = analysis.markdown(detail="full")
path = analysis.report(sections=["summary", "warnings", "risk"])
# También se admiten sections, detail y directory directamente en portfolio.report().
```

Seleccionar secciones solo cambia la presentación: cada una conserva su número y se guardan
únicamente sus imágenes. Si `portfolio.report()` o la consola excluyen `simulation`, no
generan Monte Carlo; `--simulate` lo solicita de forma independiente. `analysis.report()`
sin un resultado de simulación muestra en la sección 9 el aviso "No se ha configurado la
simulación".

Las advertencias se encuentran en `analysis.risk_warnings`, con código, nivel, valor
observado, umbral y unidad, y sus umbrales son los de `WarningThresholds`. Cubren
concentración, correlación, riesgo no compensado, caídas, volatilidad, inflación, divisa,
VIX, historia corta, fechas excluidas y escenarios desfavorables de la simulación. Son
orientativas, no recomendaciones de inversión, y un dato ausente nunca activa una regla.
Los demás avisos están en `analysis.notices`: cada `Notice` indica si señala un problema de
los datos (`data`) o un criterio de metodología (`method`), y aparecen en la sección 10.
`analysis.metric_notes` explica por qué falta cada medida sin calcular.

`analysis.drawdown_episode` describe la mayor caída: último pico anterior al valle,
primera recuperación y días naturales desde el pico. `analysis.monthly_returns` y
`analysis.annual_returns` contienen rentabilidad, número de observaciones y cobertura
parcial; el mejor y el peor mes se eligen solo entre meses completos. Un periodo necesita el
cierre del anterior: para que 2021 sea completo, `--start` debe ser anterior al último cierre
de 2020. Un período es completo
si tiene un cierre hasta 5 días antes de su final, porque los festivos de cada bolsa pueden
dejar sin fecha común el último día laborable; en el último período se exige la fecha exacta,
ya que sin datos posteriores puede no haber terminado.
`analysis.market` reúne el contexto de mercado: VIX, correlaciones con Brent, oro y ETF de
Bunds, comportamiento del Bund en los peores días y efecto divisa por activo. Los resultados
numéricos proceden del análisis; los generadores de texto y gráficos no consultan
proveedores.
