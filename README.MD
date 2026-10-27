# Toolkit de extracción, análisis bursátil y gestión de carteras

**MIAX · Bloque 1 · Taller B1-T1 · Equipo 7**

Paquete de Python que descarga precios de acciones e índices, los convierte a un formato común sea cual sea la API de origen, y analiza una cartera: métricas de rentabilidad, riesgo y diversificación, advertencias, gráficos y simulación de Monte Carlo.

```python
from toolkit import Cartera

cartera = Cartera(["SAN.MC", "ITX.MC", "AAPL"], [0.4, 0.3, 0.3], rebalanceo="monthly",
                  benchmark="^IBEX", fecha_inicio="2021-01-01", fecha_fin="2025-12-31",
                  capital_inicial=50_000)

cartera.report()                                        # informe/report.md: métricas + gráficos
cartera.plots_report()                                  # informe/graficos.md: todos los gráficos
cartera.montecarlo(n_simulaciones=10_000, horizonte=252, mostrar=True)
```

## Índice

1. [Prerrequisitos e instalación](#1-prerrequisitos-e-instalación)
2. [Uso](#2-uso)
3. [Ejemplos reproducibles](#3-ejemplos-reproducibles)
4. [Fuentes de datos y estandarización](#4-fuentes-de-datos-y-estandarización)
5. [Modelado: series y cartera](#5-modelado-series-y-cartera)
6. [Monte Carlo: criterios](#6-monte-carlo-criterios)
7. [Limpieza y validación de inputs](#7-limpieza-y-validación-de-inputs)
8. [Arquitectura](#8-arquitectura)
9. [Tests](#9-tests)

## 1. Prerrequisitos e instalación

Necesitas Python 3.10 o superior, Git y conexión a internet para descargar los datos.

```bash
git clone <url-del-repositorio>
cd tallerb1-t1-equipo7

python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # macOS / Linux

pip install -e ".[dev]"           # instala el paquete `toolkit` y pytest
python -m pytest                  # comprobación: todos los tests en verde
```

## 2. Uso

### Definir la cartera

```python
from toolkit import Cartera

cartera = Cartera(["SAN.MC", "ITX.MC", "AAPL"], [0.4, 0.3, 0.3], rebalanceo="monthly",
                  benchmark="^IBEX", fecha_inicio="2021-01-01", fecha_fin="2025-12-31",
                  capital_inicial=50_000)
```

| Argumento | Por defecto | Qué es |
|---|---|---|
| `activos` | — | Tickers de Yahoo Finance (`.MC` = Bolsa de Madrid; sin sufijo = EE. UU.; `.DE` = Xetra...) |
| `pesos` | — | Lista en el mismo orden que los activos, o dict `{ticker: peso}`. Deben sumar 1 |
| `rebalanceo` | `None` | `"monthly"`: al cierre de cada mes se vuelve a los pesos. `None`: comprar y mantener |
| `benchmark` | `"^STOXX50E"` | Índice de referencia: `"^IBEX"`, `"^GSPC"`... `None` = sin benchmark |
| `fecha_inicio` | hace 5 años | Primera fecha de los datos, `"AAAA-MM-DD"` |
| `fecha_fin` | hoy | Última fecha de los datos, `"AAAA-MM-DD"` |
| `capital_inicial` | 10 000 | Euros invertidos al inicio. El report expresa con él los resultados ("valor final de 50.000 €", importe por activo) y Monte Carlo parte de él |
| `fuente` | `YahooFinance()` | API de los precios; también `AlphaVantage()` |
| `nombre` | `"Cartera"` | Título del report |

Al crearse, la cartera descarga los precios de todos los activos a la vez, más el benchmark, el Bund, la inflación y los tipos de cambio. Después valida los datos, los limpia, pasa todo a euros y calcula las métricas.

### Report

```python
cartera.report()                                    # todas las secciones, con gráficos → informe/report.md
cartera.report(["resumen", "riesgo", "montecarlo"]) # solo algunas
cartera.report(umbrales={"peso_alto": 0.5}, graficos=False)
```

| Argumento | Por defecto | Qué hace |
|---|---|---|
| `secciones` | todas | `resumen`, `advertencias`, `composicion`, `rentabilidad`, `riesgo`, `ajustada`, `diversificacion`, `mercado`, `montecarlo`, `calidad` |
| `umbrales` | los de `toolkit.UMBRALES` | Cambia cuándo salta cada advertencia de riesgo |
| `graficos` | `True` | Incluye los gráficos de cada sección (PNG en `informe/graficos/`) |
| `ruta` | `"informe"` | Carpeta donde se guarda `report.md` (y los gráficos). `None` = no guardar |

El report se guarda automáticamente en `informe/report.md` (relativo a la carpeta desde la que se ejecuta Python; cada llamada lo sobrescribe) y además se devuelve como texto; `cartera.report().archivo` dice dónde está. Ábrelo en VS Code con Ctrl+Shift+V.

Cada sección del `.md` es un desplegable (1. Resumen, 2. Advertencias...): se ve la lista de títulos y cada uno se abre con un clic (vista previa de VS Code, GitHub o Jupyter).

Cada métrica va acompañada de una lectura automática (p. ej. Sharpe entre 0,5 y 1 → "aceptable"). En un notebook, `cartera.report()` se ve ya renderizado; en un script, usa `print(cartera.report())`.

Si no se ha ejecutado antes `cartera.montecarlo(...)`, la sección de Monte Carlo muestra el aviso **"No se ha configurado la simulación"**.

### Gráficos

```python
cartera.plots_report()                                # todos → informe/graficos.md
cartera.plots_report(["evolucion", "correlaciones"])  # solo algunos
cartera.plots_report(mostrar=True)                    # además, abrirlos en ventanas
```

`plots_report()` genera un `.md` aparte del report, `informe/graficos.md`, con un desplegable por gráfico (título, qué muestra y la imagen; los PNG van a `informe/graficos/`). Igual que `report()`, se guarda automáticamente y devuelve el texto.

| Argumento | Por defecto | Qué hace |
|---|---|---|
| `graficos` | todos | Lista de nombres (tabla de abajo) |
| `ruta` | `"informe"` | Carpeta donde se guarda `graficos.md`. `None` = no guardar |
| `mostrar` | `False` | Además, abrirlos en ventanas |

Gráficos disponibles:

| Nombre | Qué muestra |
|---|---|
| `evolucion` | Base 100 frente al benchmark y los Bunds |
| `drawdown` | Caídas desde el máximo |
| `correlaciones` | Matriz de correlaciones |
| `riesgo_rentabilidad` | Riesgo frente a rentabilidad de cada activo |
| `pesos_contribucion` | Peso frente a contribución al riesgo |
| `rentabilidad_anual` | Rentabilidad de cada año |
| `distribucion` | Rentabilidades diarias frente a una normal |
| `volatilidad_vix` | Volatilidad de la cartera frente al VIX |
| `correlacion_bund` | Correlación móvil con el ETF de Bunds |
| `exposicion` | Exposición por sector y por divisa |
| `montecarlo` | Resultado de la simulación (si no se ha ejecutado, muestra el aviso) |

### Monte Carlo

```python
res = cartera.montecarlo()                                          # cartera, supuestos históricos
res = cartera.montecarlo(n_simulaciones=20_000, horizonte=504,
                         retorno=0.06, volatilidad=0.20, mostrar=True)
res = cartera.montecarlo(activo="AAPL")                              # un activo individual
res = cartera.montecarlo(por_activos=True)                           # cada activo con sus correlaciones
res.metricas      # mediana, percentiles, probabilidad de pérdida, VaR y CVaR al horizonte
res.plot()        # trayectorias + distribución del valor final
```

| Argumento | Por defecto | Qué controla |
|---|---|---|
| `n_simulaciones` | 10 000 | Número de trayectorias (iteraciones) |
| `horizonte` | 252 | Sesiones a simular (252 ≈ 1 año) |
| `retorno` | histórico | Rentabilidad anual supuesta |
| `volatilidad` | histórica | Volatilidad anual supuesta |
| `activo` | — | Ticker para simular un solo activo en lugar de la cartera |
| `por_activos` | `False` | Simula cada activo con sus correlaciones y el rebalanceo de la cartera; `retorno` y `volatilidad` pueden ser un dict por ticker |
| `confianza` | 0,95 | Nivel del VaR y de los percentiles extremos |
| `semilla` | 42 | Para reproducir el resultado (`None` = aleatorio) |
| `mostrar` | `False` | Dibuja las trayectorias y la distribución al terminar |

La simulación de la cartera se guarda en `cartera.simulacion` y aparece en el report.

## 3. Ejemplos reproducibles

```bash
python src/main.py                                                    # cartera de ejemplo
python src/main.py SAN.MC=0.5 AAPL=0.3 ITX.MC=0.2 --rebalanceo none --benchmark ^IBEX --fecha-inicio 2022-01-01 --capital 50000
```

Genera `informe/report.md` y `informe/graficos.md` (ábrelos en VS Code con Ctrl+Shift+V), con las imágenes en `informe/graficos/`. Al fijar `--fecha-inicio` y `--fecha-fin`, el resultado es siempre el mismo.

## 4. Fuentes de datos y estandarización

| Fuente | Datos | Clave |
|---|---|---|
| `YahooFinance` | Acciones, índices, ETF, materias primas y divisas, más sector, divisa y país | No |
| `AlphaVantage` | Acciones y metadatos (cierres sin ajustar por dividendos) | Sí, gratuita: `ALPHAVANTAGE_API_KEY` |
| `Fred` (dato adicional) | Bund a 10 años, inflación HICP, VIX, Brent, EUR/USD | No |

Las fuentes de precios heredan de `FuentePrecios`, que fija el formato de salida. Cada API solo implementa cómo pedir los cierres (`_cierres`) y los metadatos (`_metadatos`), y la clase base construye siempre la misma `PriceSeries`: fechas sin hora ni zona horaria, ordenadas y sin duplicados, divisa en mayúsculas y peniques pasados a libras. Un test comprueba que Yahoo y Alpha Vantage, que entregan formatos distintos, producen objetos idénticos.

`descargar_varios([...])` descarga N series en paralelo y, si alguna falla, dice cuál. Para añadir una API nueva basta con una subclase de `FuentePrecios` con esos dos métodos; se usa con `Cartera(..., fuente=MiFuente())` sin tocar nada más.

```python
from toolkit import YahooFinance, Fred
YahooFinance().descargar_varios(["SAN.MC", "AAPL", "^IBEX"], "2020-01-01")   # {ticker: PriceSeries}
Fred().descargar("IRLTLT01DEM156N", "2020-01-01")                            # MacroSeries
```

## 5. Modelado: series y cartera

Todas son DataClasses ([diagrama de clases](docs/arquitectura.md)):

- **`Serie`**: símbolo, fuente, datos y nombre. Al instanciarse valida los datos y calcula automáticamente `media` y `desviacion`.
- **`PriceSeries(Serie)`**: precios de un activo, con divisa, tipo, sector y país. La media y la desviación típica se calculan sobre las rentabilidades diarias, igual que `media_anual` y `volatilidad_anual`.
- **`MacroSeries(Serie)`**: indicador económico con su unidad y frecuencia.
- **`Cartera`**: agrega varias `PriceSeries` con sus pesos y su rebalanceo. Contiene los métodos `report()`, `plots_report()` y `montecarlo()`.

Convenciones: precio de cierre ajustado, año de 252 sesiones, todo en euros (los activos en otra divisa se convierten con el tipo de cambio diario) y tipo libre de riesgo = Bund a 10 años.

## 6. Monte Carlo: criterios

- **Modelo:** movimiento browniano geométrico. Cada día, `S(t+1) = S(t) · exp[(μ − σ²/2)/252 + σ/√252 · Z]`, con `Z ~ N(0,1)`. El precio nunca es negativo.
- **Supuestos:** μ (`retorno`) y σ (`volatilidad`) son parámetros; si no se indican, se usan la media y la volatilidad históricas anualizadas.
- **Por activos:** los choques de cada activo se correlacionan con la descomposición de Cholesky de la matriz de covarianzas histórica, y se aplica el rebalanceo de la cartera (mensual = cada 21 sesiones). Si se cambia la volatilidad, se mantienen las correlaciones.
- **Limitaciones:** supone rentabilidades normales (subestima las caídas extremas; el gráfico `distribucion` lo muestra), μ y σ constantes, y no tiene en cuenta aportaciones, retiradas ni costes.

## 7. Limpieza y validación de inputs

**¿Debe admitirse cualquier input con una serie de precios?** No. Se admite cualquier *origen* (cualquier API o una `pandas.Series` propia), pero todo pasa por la DataClass `PriceSeries`, que valida al crearse. Admitir "cualquier cosa con fechas y números" trasladaría los errores a las métricas, donde son silenciosos: un Sharpe calculado con divisas mezcladas da un número, pero falso.

El criterio: **lo que haría falsas las cifras detiene el programa; lo que solo las hace menos fiables se corrige, se registra y aparece en la sección "Calidad de los datos" del report.**

| Situación | Tratamiento |
|---|---|
| Datos que no son una serie con índice de fechas, menos de 2 valores, precios ≤ 0 | Error |
| Pesos que no suman 1, negativos o que no casan con los activos; activos repetidos | Error |
| Ticker sin datos | Error que indica cuál |
| Activo en otra divisa sin tipo de cambio | Error |
| Menos de 30 sesiones comunes | Error |
| Menos de 252 sesiones | Advertencia alta |
| Fechas con hora o zona horaria, desordenadas o duplicadas | Se normalizan |
| Calendarios distintos (festivos de cada bolsa) | Se rellena con el último cierre (máximo 5 sesiones seguidas) y se informa del % imputado |
| Huecos de más de 5 sesiones | Se descartan esas fechas |
| Fines de semana (cripto) | Se eliminan |
| Saltos diarios > 50 % | Se marcan, sin tocarlos (suelen ser splits mal ajustados) |
| Fallo de una fuente opcional (VIX, Brent...) | Se anota y la métrica sale "n/d" |

## 8. Arquitectura

Cuatro capas. Solo `ingesta` se conecta a internet, y la cartera la usa a través de la interfaz `FuentePrecios`, nunca de una API concreta. Diagramas de clases (UML), dependencias y flujo en **[docs/arquitectura.md](docs/arquitectura.md)**.

```
src/toolkit/
├── ingesta/    base.py (FuentePrecios), yahoo.py, alphavantage.py, fred.py, mercado.py
├── modelos/    series.py (Serie, PriceSeries, MacroSeries), mercado.py, cartera.py (Cartera)
├── analisis/   preprocesado.py, metricas.py, montecarlo.py, advertencias.py
└── salida/     report.py, graficos.py
```

## 9. Tests

```bash
python -m pytest           # sin internet: series, cartera, rebalanceo, limpieza, Monte Carlo, report, gráficos
python -m pytest -m red    # con descargas reales de Yahoo y FRED
```
