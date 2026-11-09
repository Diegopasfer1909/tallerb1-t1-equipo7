# Arquitectura · B1–T1 / Equipo 7

Siete vistas complementarias explican la estructura del toolkit, sus contratos y su ejecución. Los nombres de clases y métodos coinciden con el código; las imágenes se pueden ampliar sin perder calidad y editar en Excalidraw.

**Referencia:** código del commit **`fb2d2ea`** (8 de noviembre de 2026): comisiones del rebalanceo, ventana de estimación de Monte Carlo y `returns_mean` / `returns_std` en `PriceHistory`; las láminas 01, 03 y 05 incluyen además los puertos de `src/ports.py` ([decisión 74](Decisiones.MD)). [El manifiesto](diagramas/verificacion.json) identifica las fuentes y los artefactos mediante hashes; al cambiar el código, hay que revisar qué láminas quedan afectadas. [La vista general](diagramas/vista-general.png) reúne las siete láminas en una sola imagen.

| Lámina | Vista formal | Pregunta que responde |
| --- | --- | --- |
| [01 · Arquitectura](#01--arquitectura-del-sistema) | Componentes y responsabilidades | ¿Qué hace cada parte y dónde ocurre la E/S? |
| [02 · Modelos de dominio](#02--modelos-de-dominio) | Clases UML | ¿Qué objetos forman una cartera y qué referencias comparten? |
| [03 · Proveedores](#03--contratos-y-proveedores) | Clases e interfaces UML | ¿Cómo se intercambia la fuente y se controla el acceso externo? |
| [04 · Simulación](#04--contrato-de-simulación) | Contratos y dependencias UML | ¿Cómo comparten motor un activo y una cartera? |
| [05 · Dependencias](#05--dependencias-entre-paquetes) | Dependencias de paquetes | ¿Qué módulos dependen de cuáles y cuándo se importan? |
| [06 · Flujo CLI](#06--flujo-de-la-aplicación) | Actividad UML | ¿Qué pasos y decisiones sigue una ejecución? |
| [07 · Consulta Alpha](#07--secuencia-de-una-consulta-alpha-vantage) | Secuencia UML | ¿Cómo interactúan caché, cuota, HTTP y errores? |

## Cómo leer las láminas

| Notación | Significado |
| --- | --- |
| Línea continua y triángulo hueco | Generalización: herencia nominal de clase. |
| Línea discontinua y triángulo hueco | Realización del contrato; en `PriceProvider`, conformidad estructural con un `Protocol`. |
| Rombo hueco | Agregación compartida: la parte puede existir y reutilizarse fuera del conjunto. |
| Rombo relleno | Composición de colaboradores creados por el adaptador; expresa el diseño de propiedad, no una restricción del recolector de Python. |
| Asociación con multiplicidad | Referencia conservada por un objeto; `1`, `0..1`, `1..*` y `0..*` indican cardinalidades. |
| Dependencia discontinua | Uso de un tipo, función o paquete; no implica guardar una referencia. |
| `«module»` / `«function»` | Funciones reales del código; no son clases añadidas para el diagrama. |
| `frozen=True` | Impide reasignar atributos; no garantiza inmutabilidad profunda ni validación automática del contenido. |

Las flechas se interpretan según la vista: **responsabilidad/interacción** en 01, **importación** en 05 y **orden de ejecución** en 06–07. Las multiplicidades describen referencias, no cantidades de peticiones ni escenarios.

## 01 · Arquitectura del sistema

![Arquitectura: entrada, carga, proveedores, dominio, cálculo y presentación](diagramas/01-arquitectura.svg)

[PNG](diagramas/01-arquitectura.png) · [Editar en Excalidraw](diagramas/01-arquitectura.excalidraw) · [Fuente Mermaid](diagramas/01-arquitectura.mmd)

Esta vista organiza **responsabilidades y llamadas del sistema**, no todas las importaciones. `main` compone la ejecución; los cargadores obtienen y transforman datos, incluidos los precios de 5 años con los que Monte Carlo estima la volatilidad y las correlaciones; los adaptadores encapsulan los servicios externos (Yahoo, Alpha Vantage, FRED y BCE). Los módulos transversales `commissions` y `frequency` aplican la misma regla de rebalanceo y el mismo calendario (252 o 365) en el histórico y en la simulación. Los modelos y los cálculos trabajan con contratos normalizados. `reporting` presenta resultados y escribe Markdown e imágenes, por lo que sí realiza E/S local.

La entrada de datos sigue **puertos y adaptadores**: `src/ports.py` define en el núcleo los contratos `PriceProvider`, `IndicatorProvider` (FRED y BCE) y `ReferenceSources`, y `errors` el `ProviderError` común. Los cargadores solo reciben esos puertos; `main` es el único módulo que elige y crea adaptadores (registro `PROVIDERS` y `reference_sources()`). El resto no es una hexagonal estricta: `Portfolio.report()`, `.plots_report()` y `SimulationResult.plot()` son fachadas que el enunciado pide en el dominio y que llegan a `reporting` ([decisión 74](Decisiones.MD)).

**Fuentes:** [main.py](src/main.py), [ports.py](src/ports.py), [portfolio_loader.py](src/portfolio_loader.py), [market_loader.py](src/market_loader.py), [providers](src/providers), [reporting/export.py](src/reporting/export.py).

## 02 · Modelos de dominio

![Clases UML del dominio y referencias compartidas](diagramas/02-modelos-dominio.svg)

[PNG](diagramas/02-modelos-dominio.png) · [Editar en Excalidraw](diagramas/02-modelos-dominio.excalidraw) · [Fuente Mermaid](diagramas/02-modelos-dominio.mmd)

`PriceHistory` conserva precios y procedencia; `AssetProfile`, los metadatos; `Asset`, la identidad y divisa del activo. `Portfolio` reúne activos y asigna pesos, capital y política de rebalanceo; `Portfolio.from_units()` la crea a partir del número de acciones, que conserva en `units`; sin rebalanceo las cantidades no cambian y con `rebalance="monthly"` cada mes se vuelve a los pesos iniciales. `rebalance_rule` (`RebalanceRule`, del módulo `commissions`) fija la tarifa del bróker (`CommissionSchedule`), la banda de desviación y el coste máximo por orden; `Portfolio.backtest()` devuelve un `BacktestResult` con la valoración, las órdenes y las comisiones pagadas. Un activo puede participar en varias carteras: su peso pertenece a cada cartera, no al propio activo. Por eso las relaciones del dominio usan asociación o agregación compartida.

`FxRates` agrupa pares directos o inversos y `ExchangeRate` añade significado de divisa a un `EconomicIndicator`. `MarketReferences` contiene referencias opcionales de benchmark, inflación, tipo libre de riesgo, VIX, Brent, oro y ETF de Bunds, además de cambios de divisa para el benchmark. `FxRates.combine()` permite reunirlos con los de la cartera para la comparación.

`PriceHistory` guarda copias defensivas y calcula al construirse la media y la desviación típica de los niveles de precio (`mean`, `std`) y de las rentabilidades de `Close` y `Adj Close` (`returns_mean`, `returns_std`); los pesos y los indicadores protegen su almacenamiento numérico. Esto no convierte todos los contenedores y resultados del sistema en profundamente inmutables. La alineación de activos conserva fechas comunes sin rellenar huecos; no implementa un calendario bursátil explícito.

**Fuentes:** [models/portfolio.py](src/models/portfolio.py), [asset.py](src/models/asset.py), [price_history.py](src/models/price_history.py), [currency.py](src/models/currency.py), [references.py](src/models/references.py), [snapshot.py](src/models/snapshot.py), [backtest.py](src/models/backtest.py), [commissions.py](src/commissions.py).

## 03 · Contratos y proveedores

![Contrato PriceProvider, adaptadores y colaboradores HTTP y cuota](diagramas/03-proveedores.svg)

[PNG](diagramas/03-proveedores.png) · [Editar en Excalidraw](diagramas/03-proveedores.excalidraw) · [Fuente Mermaid](diagramas/03-proveedores.mmd)

Yahoo y Alpha satisfacen estructuralmente `PriceProvider.get_prices()`: no heredan nominalmente del protocolo y `get_info()` no forma parte de ese contrato. FRED y el BCE (`EcbAPI`, que no necesita clave) cumplen otro puerto, `IndicatorProvider.get_series()`, que devuelve `EconomicIndicator`. Ambos protocolos viven en `src/ports.py`, en el núcleo: los adaptadores dependen de ellos y no al revés. Los adaptadores traducen formatos externos al dominio común: ese es el patrón **Adapter** que justifica intercambiarlos.

Alpha y FRED crean su propio `ApiClient`; Yahoo utiliza `yfinance` y `EcbAPI` utiliza `curl_cffi`: ambos comparten utilidades de caché, pero no ese cliente HTTP. Alpha crea además `AlphaVantageQuota` e inyecta sus métodos como callbacks genéricos del cliente. `requests.Session` puede suministrarse desde fuera, así que su relación es asociación, no composición exclusiva. La cuota persistente y la caché tienen cometidos distintos.

Cada adaptador puede declarar con el atributo opcional `max_download_workers` cuántas descargas simultáneas admite; no forma parte de `PriceProvider`. Yahoo declara 4: cada entrada de caché tiene un bloqueo propio dentro del proceso que cubre leer, ampliar el intervalo, descargar y escribir, los temporales son únicos por escritura y los filtros de avisos se configuran una sola vez desde la CLI. Alpha declara 1 y conserva su cuota, sus pausas y su `ApiClient` sin cambios; un proveedor que no declara nada también descarga de uno en uno.

**Fuentes:** [ports.py](src/ports.py), [providers/base.py](src/providers/base.py), [yahoo.py](src/providers/yahoo.py), [alpha_vantage.py](src/providers/alpha_vantage.py), [fred.py](src/providers/fred.py), [ecb.py](src/providers/ecb.py), [alpha_quota.py](src/providers/alpha_quota.py).

## 04 · Contrato de simulación

![Contratos comunes y motor funcional de simulación](diagramas/04-simulacion.svg)

[PNG](diagramas/04-simulacion.png) · [Editar en Excalidraw](diagramas/04-simulacion.excalidraw) · [Fuente Mermaid](diagramas/04-simulacion.mmd)

`Asset` y `Portfolio` construyen `SimulationInputs` y delegan en la misma función `simulate()`. No existe una superclase común de simulación ni un `MonteCarloMixin`. La reutilización se obtiene mediante **composición y un contrato de datos**: precios históricos, valor inicial de posiciones y pesos opcionales de rebalanceo, junto con la `RebalanceRule` que fija comisiones, banda de desviación y coste máximo por orden.

El módulo transversal `commissions` contiene `CommissionSchedule`, la tarifa de ejemplo de Interactive Brokers (`IBKR_COMMISSIONS`), `RebalanceRule` y la función vectorizada `rebalance_step()`. La usan igual el backtest histórico (`backtest_with_costs()`, una fila) y Monte Carlo (una fila por escenario), de modo que ambos recorridos aplican la misma regla y descuentan las mismas comisiones.

`Portfolio.monte_carlo(estimation_prices=...)` permite estimar la volatilidad y las correlaciones con otro período; la consola le pasa 5 años, mientras el valor inicial, los pesos objetivo y la `RebalanceRule` siguen siendo los de la cartera analizada.

`SimulationSettings` separa configuración y supuestos del estado del dominio. Sin `steps` se simula un año: `simulate()` deduce 252 sesiones o 365 días (carteras solo cripto) con `frequency.periods_per_year()`. `SimulationResult` guarda la regla aplicada y las comisiones pagadas en cada escenario, ya descontadas de las trayectorias. El motor valida las entradas, estima parámetros y genera trayectorias correlacionadas; `SimulationResult` conserva resultados y metadatos, ofrece un resumen y delega la presentación. No debe representarse como una dataclass congelada. El módulo `monte_carlo` contiene funciones, no una clase ficticia de motor.

**Fuentes:** [asset.py](src/models/asset.py), [portfolio.py](src/models/portfolio.py), [commissions.py](src/commissions.py), [backtest.py](src/models/backtest.py), [simulation/monte_carlo.py](src/simulation/monte_carlo.py), [settings.py](src/simulation/settings.py), [result.py](src/simulation/result.py).

## 05 · Dependencias entre paquetes

![Importaciones principales y cuatro dependencias diferidas entre paquetes](diagramas/05-dependencias.svg)

[PNG](diagramas/05-dependencias.png) · [Editar en Excalidraw](diagramas/05-dependencias.excalidraw) · [Fuente Mermaid](diagramas/05-dependencias.mmd)

Una flecha va del **importador al importado**. La lámina selecciona las importaciones principales entre paquetes y cuatro aristas internas diferidas; omite las relaciones dentro de cada paquete, las bibliotecas externas y las dependencias transversales recogidas abajo. `reporting` importa al cargarse funciones de `analysis` (`annualized_growth`, `evaluate_simulation`) y de `simulation` (`MODEL_RETURN`, `SimulationSettings`); ninguna de ellas crea un ciclo, porque las importaciones inversas son diferidas. No es el grafo completo de carga de Python ni una afirmación de ausencia total de ciclos.

| Arista diferida | Lugar y propósito |
| --- | --- |
| `models → analysis` | `Portfolio.analyze()` importa `analyze_portfolio`. |
| `models → reporting` | `Portfolio.report()` importa `select_sections`. |
| `analysis → reporting` | Métodos de `PortfolioAnalysis` importan construcción, exportación y gráficos. |
| `simulation → reporting` | `SimulationResult.plot()` importa funciones de gráficos. |

Se difiere la **sentencia concreta**, no necesariamente la primera carga efectiva del paquete: otras rutas de ejecución pueden haberlo importado ya. La CLI también tiene una importación local externa de `matplotlib.pyplot`.

| Dependencia transversal | Consumidores directos de nivel superior dentro de `src/` |
| --- | --- |
| `constants` | `main`, `portfolio_loader`, `market_loader`, `models`, `providers`, `simulation`, `analysis`, `reporting`, `validation`, `frequency`. |
| `errors` | `main`, `portfolio_loader`, `market_loader`, `models`, `providers`, `simulation`, `analysis`, `reporting`, `validation`, `commissions`. |
| `validation` | `main`, `portfolio_loader`, `models`, `providers`, `simulation`, `analysis`, `reporting`, `commissions`. |
| `commissions` | `main`, `portfolio_loader`, `models`, `simulation`, `analysis`, `reporting`. |
| `frequency` | `simulation`, `analysis`. |
| `ports` | `main`, `portfolio_loader`, `market_loader`, `providers`. |

| Importaciones bajo `TYPE_CHECKING` entre paquetes | Tipos utilizados |
| --- | --- |
| `models → analysis` | `PortfolioAnalysis`, `WarningThresholds`. |
| `analysis → models` | `Portfolio`; el paquete ya tiene otras importaciones de modelos en ejecución. |
| `reporting → analysis` | `PortfolioAnalysis` en `export`, `plots` y `report`. |
| `reporting → simulation` | `SimulationResult` en `export`, `plots` y `report`. |

Estas últimas sirven a anotaciones y comprobadores de tipos; sus bloques no se ejecutan normalmente. Además, `reporting` importa al cargar `analysis` (métricas y avisos) y `simulation` (supuestos de Monte Carlo); la lámina 05 los dibuja como líneas continuas ámbar. Solo `main` importa `providers`: los cargadores importan `ports`. El grafo de imports de módulo sigue siendo acíclico. La tabla agrupa módulos por paquete y no incluye importaciones internas del mismo paquete ni reexportaciones de `__init__.py`.

**Fuentes:** [portfolio.py](src/models/portfolio.py), [analysis/result.py](src/analysis/result.py), [analysis/portfolio_analysis.py](src/analysis/portfolio_analysis.py), [simulation/result.py](src/simulation/result.py), [reporting](src/reporting), [main.py](src/main.py).

## 06 · Flujo de la aplicación

![Actividad UML de una ejecución CLI](diagramas/06-flujo-cli.svg)

[PNG](diagramas/06-flujo-cli.png) · [Editar en Excalidraw](diagramas/06-flujo-cli.excalidraw) · [Fuente Mermaid](diagramas/06-flujo-cli.mmd)

La CLI carga entorno y argumentos, comprueba la configuración necesaria y crea los colaboradores. El cargador obtiene los históricos y, cuando procede, los tipos de cambio antes de construir la cartera. Parte de la validación necesita los datos y ocurre al construir modelos o ejecutar cálculos: el análisis de argumentos no sustituye esas comprobaciones.

Las opciones de comisiones (`--commission-*`, `--rebalance-band`, `--max-order-cost`) solo se admiten con `--rebalance monthly`; en otro caso `argparse` termina con código `2`. Después se muestran las posiciones, con las comisiones del backtest si hay tarifa, y se ejecuta la simulación si la configuración la solicita; antes de simular se consulta el tipo libre de riesgo de la divisa. Con Yahoo, la simulación descarga además los precios de los 5 años anteriores (o desde `--start`, si es anterior; o desde `--estimation-start`) para estimar la volatilidad y las correlaciones, y avisa si cubren menos de 3 años. El análisis se necesita para informe o gráficos; las referencias económicas se descargan solamente con `--report`, por lo que pueden consultarse después de crear la cartera. La selección de secciones del informe también puede activar su simulación al preparar la configuración.

`price_loader.load_price_histories()` descarga los historiales de cada lote (cartera por pesos, por acciones y precios de estimación) con hasta `--download-workers` descargas simultáneas, limitadas por el proveedor y por el número de activos; con una sola, no crea hilos. Devuelve los historiales en el orden de entrada y los activos y la cartera se crean después, en el hilo principal. Ante el primer fallo deja de enviar descargas, cancela las pendientes y propaga el error con el símbolo. Los tipos de cambio, el índice de referencia, FRED y el BCE siguen en secuencia. Los diagramas de `diagramas/` no representan todavía esta fase.

Las referencias opcionales fallidas se explican mediante avisos y medidas ausentes cuando la carga admite degradación; otros errores terminan la ejecución. `main()` devuelve `0` al completar y `1` para `PortfolioError`, `ProviderError` u `OSError`; los errores de argumentos siguen el comportamiento de `argparse`.

**Fuentes:** [main.py](src/main.py), [portfolio_loader.py](src/portfolio_loader.py), [market_loader.py](src/market_loader.py), [reporting/export.py](src/reporting/export.py).

## 07 · Secuencia de una consulta Alpha Vantage

![Secuencia UML: caché, reserva de cuota, descarga y normalización](diagramas/07-secuencia-alpha.svg)

[PNG](diagramas/07-secuencia-alpha.png) · [Editar en Excalidraw](diagramas/07-secuencia-alpha.excalidraw) · [Fuente Mermaid](diagramas/07-secuencia-alpha.mmd)

La secuencia sigue una consulta de precios. `ApiClient.get_json()` consulta primero la caché: un acierto evita red y reserva de cuota. Si falta una respuesta válida, respeta el intervalo mínimo, invoca `before_request` y realiza HTTP. La reserva persistente se confirma antes del envío; un rechazo local evita la petición y un intento fallido puede haber consumido una reserva.

Los rechazos remotos pasan por `on_rejection`; el control de cuota puede persistir un bloqueo. Una respuesta HTTP 200 también puede contener un error del proveedor. Solo una respuesta aceptada alcanza la caché y la normalización en `PriceHistory`. No se representa un bucle de reintentos automático. La consulta opcional de ficha (`include_info`) es una operación adicional y puede consumir otra reserva.

**Fuentes:** [alpha_vantage.py](src/providers/alpha_vantage.py), [base.py](src/providers/base.py), [alpha_quota.py](src/providers/alpha_quota.py).

## Edición, reproducción y alcance

[La guía de diagramas](diagramas/README.md) explica cómo editar y regenerar las láminas. Excalidraw conserva elementos editables; SVG es la vista vectorial y PNG sirve para insertar en diapositivas. Los `.mmd` recogen el modelo semántico en Mermaid; su disposición automática no pretende reproducir exactamente la composición gráfica.

El generador mantiene **Excalidraw, SVG y PNG**. Mermaid se mantiene manualmente y debe revisarse junto al código.

Los diagramas documentan contratos y decisiones observados. Su generación y comprobación visual no equivalen a ejecutar consultas reales de proveedores ni a certificar todos los comportamientos de la práctica.
