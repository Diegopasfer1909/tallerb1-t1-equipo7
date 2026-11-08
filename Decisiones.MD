# Registro de decisiones

Este documento recoge las decisiones técnicas del proyecto en cinco partes:

- **Parte I (decisiones 1 a 32):** las tomadas en las sesiones de revisión y desarrollo entre
  el 30 de octubre y el 6 de noviembre de 2026.
- **Parte II (decisiones 33 a 56):** las que están documentadas en el propio proyecto (README,
  `ARQUITECTURA.md`, código e historial de git), muchas tomadas por otros miembros del
  equipo. Cada una indica su origen: la sección del README o el commit.
- **Parte III (decisiones 57 a 63):** detalles recuperados de las conversaciones disponibles
  y contrastados con el código el 6 de noviembre de 2026. Las decisiones ya recogidas se
  amplían en su entrada original, como la 25, para evitar duplicarlas.
- **Parte IV (decisiones 64 a 72):** las razonadas en las sesiones de trabajo del 29 de
  octubre al 6 de noviembre de 2026 y contrastadas con el código el 7 de noviembre. Lo que
  ya estaba registrado se amplía en su entrada original (1, 10, 18, 36, 40, 42, 45, 46, 50,
  51, 54 y 55).
- **Parte V (decisión 73):** la sesión del 7 y 8 de noviembre de 2026 sobre Monte Carlo
  (PR #26). Las alternativas que se descartaron en ella se añaden a sus entradas originales
  (27, 40, 47, 50 y 67).

Cada entrada explica qué se decidió, por qué y qué alternativas se descartaron, con un
ejemplo sencillo para entenderla.

Si una decisión se cambió más adelante, o su aplicación está incompleta, se indica en
**Estado**. El código determina el comportamiento implementado; una propuesta de la
conversación no se considera aplicada solo por haberse recomendado.

## Dónde encontrar cada explicación

El [README](README.MD) reúne la instalación, todos los parámetros con sus valores por
defecto (agrupados en `--simulate`, `--plots-report` y `--report`), los ejemplos y la ayuda.
Desde el 8 de noviembre de 2026 sustituye a la antigua guía `docs/uso.md`, que se eliminó
para no mantener dos referencias de parámetros. Este registro reúne los criterios técnicos y
su justificación, incluidos los detalles trasladados del README al simplificarlo el 6 de
noviembre de 2026. Se amplían las entradas existentes sin duplicarlas.

| Tema | Decisiones |
| --- | --- |
| Historial y ramas | 1 |
| Cuota, persistencia y bloqueos de Alpha Vantage | [25](#cuota-alpha-vantage) |
| Comisiones y simplificaciones de costes | 26–30 |
| Proveedores y datos macroeconómicos | 18, 39, 65, 70 |
| Validación, fechas comunes y datos sin rellenar | 12–14, 36–38, 66–67 |
| Calendarios, anualización y datos inmutables | [40](#contrato-temporal), 41–42 |
| Precios ajustados y referencias por divisa | 43–46 |
| Modelo y supuestos de Monte Carlo | [47](#modelo-monte-carlo), 59, 62, 64, 73 |
| Caché, informe y controles de calidad | 15, 19–24, 51–55, 68, 71–72 |
| Diagramas y documentación de arquitectura | 56, 69 |

## Fuentes y alcance de la revisión

Se han podido leer completas estas dos sesiones de revisión relacionadas con el proyecto:

| Referencia | Conversación | Fecha | Qué permite comprobar |
| --- | --- | --- | --- |
| C1 | `Analyze Carlos branch report` (`01a18c11-7444-7942-8d6a-34fbb63d4ed3`) | 30 de octubre de 2026 | Revisión de la guía de Carlos, autorización para adaptar las mejoras respetando la arquitectura y resultado de la implementación |
| C2 | `Review AlphaVantage API usage limits` (`01a18e24-5e16-76a2-99e1-fd9f82195a66`) | 30 de octubre de 2026 | Control persistente de cuota y petición expresa de contemplar una clave compartida entre CI y local |

Los commits `e6b3373` y `d150397` permiten contrastar los cambios de C1 y C2,
respectivamente. Las referencias a archivos de las entradas describen el código revisado,
no una consulta a las condiciones actuales de los proveedores.

El historial accesible no muestra otras sesiones de revisión de este proyecto.
Se conservan las 56 entradas previas y sus atribuciones; esto no implica haber recuperado
las conversaciones originales de todas ellas. Cuando solo hay evidencia en el repositorio,
se identifica como tal. Tampoco se presenta una propuesta de la revisión como una decisión
expresa del equipo si la conversación no lo demuestra.

Además, se han leído completas las diez sesiones de trabajo que se conservan del proyecto:

| Referencia | Conversación | Fecha | Qué permite comprobar |
| --- | --- | --- | --- |
| S1 | `20182515` | 29 de octubre de 2026 | Revisión de simplicidad, errores corregidos, Monte Carlo común, ficha de Yahoo, Python 3.11 y paso a la rama `main` |
| S2 | `a4e22cdc` | 31 de octubre de 2026 | Reutilizar descargas entre ejecuciones: caché de Yahoo por símbolo |
| S3 | `e8a4605b` | 31 de octubre de 2026 | ALFRED contrastado con la API real, vuelta a FRED y conflictos de la PR #8 |
| S4 | `1d3e6591` | 31 de octubre y 1 de noviembre de 2026 | Análisis completo, contraste con otro análisis, mejoras integradas, `--benchmark` y simplificación |
| S5 | `210c136e` | 31 de octubre de 2026 | Diagramas Mermaid en `ARQUITECTURA.md` |
| S6 | `a9b36f56` | 31 de octubre a 5 de noviembre de 2026 | Diagramas versionados, colores de los `.mmd`, FRED sin clave y correcciones de la PR #18 |
| S7 | `4da29415` | 5 de noviembre de 2026 | Revisión y corrección de la PR #13 (`--shares`) |
| S8 | `9c461486` | 5 de noviembre de 2026 | Revisión y mejora de la PR #14 (instrucciones de instalación) |
| S9 | `16e8c5b9` | 5 de noviembre de 2026 | Láminas de arquitectura con el proveedor del BCE |
| S10 | `f71501aa` | 5 y 6 de noviembre de 2026 | Revisión de la PR #16 (Ruff, cobertura y CodeQL) y PR #21 |

Las sesiones en las que se decidieron las comisiones y la vectorización (26 a 32) no están
entre estas sesiones, así que esas entradas no se han vuelto a contrastar. Se aplica
el mismo criterio que en la parte III: una propuesta solo figura como decisión si se aplicó
o el usuario la eligió, y las propuestas descartadas se indican como tales.

## Índice

**Parte I · Decisiones de las sesiones de revisión y desarrollo**

| # | Tema | Decisión | Estado |
| --- | --- | --- | --- |
| 1 | Forma de trabajo | Ramas y pull requests, sin commits automáticos | Vigente |
| 2 | Arquitectura | Capas con dependencias en un solo sentido | Vigente |
| 3 | Arquitectura | Separar `MarketContext` en `FxRates` y `MarketReferences` | Vigente |
| 4 | Arquitectura | Composición y `SimulationSettings` en lugar de `MonteCarloMixin` | Vigente |
| 5 | Arquitectura | Calcular la valoración de la cartera una sola vez | Vigente |
| 6 | Modelado | Tipos explícitos en lugar de diccionarios y cadenas | Vigente |
| 7 | Modelado | Una única forma de indicar pesos | Vigente |
| 8 | Errores | Errores propios y mensajes por la salida de errores | Vigente |
| 9 | Código limpio | Constantes, textos y registros en un único sitio | Vigente |
| 10 | Diseño | Patrones solo donde aportan | Vigente |
| 11 | Empaquetado | Aplazar el cambio de nombre del paquete `src` | Pendiente |
| 12 | Datos | No rellenar fechas sin precio | Vigente |
| 13 | Datos | Tolerancia de 1e-5 en la suma de pesos | Vigente |
| 14 | Datos | Normalizar la divisa antes de compararla | Vigente |
| 15 | Archivos | Informes y caché seguros ante fallos | Vigente |
| 16 | Claves de API | Funcionar sin claves y avisar de lo que falta | Vigente |
| 17 | Datos macro | Cambiar FRED por ALFRED | Revertida (ver 18) |
| 18 | Datos macro | Volver a FRED, con el BCE para el euro | Vigente |
| 19 | Pruebas | Pruebas unitarias sin red y pruebas de integración aparte | Vigente |
| 20 | CI | Integración obligatoria y comprobación única para `main` | Vigente |
| 21 | CI | El push solo lanza el pipeline en `main` | Vigente |
| 22 | CI | Comprobar el paquete instalado | Vigente |
| 23 | CI | Buscar claves filtradas con gitleaks | Vigente |
| 24 | CI | Consultar Alpha Vantage solo cuando hace falta | Vigente |
| 25 | Alpha Vantage | Correcciones del contador de cuota | Vigente |
| 26 | Comisiones | Tarifas de bróker con IBKR por defecto | Vigente |
| 27 | Comisiones | Rebalancear solo si compensa: banda y coste máximo | Vigente |
| 28 | Comisiones | Comparar con comprar y mantener | Vigente |
| 29 | Comisiones | Valores por defecto solo en la consola | Vigente |
| 30 | Comisiones | Simplificaciones del modelo de costes | Vigente |
| 31 | Rendimiento | Vectorizar el backtest sin rebalanceo | Vigente |
| 32 | Rendimiento | Mantener los bucles de Monte Carlo, betas y comisiones | Vigente |

**Parte II · Decisiones documentadas en el proyecto**

| # | Tema | Decisión | Origen |
| --- | --- | --- | --- |
| 33 | Equipo | Unificar la versión de Carlos con la estructura de `main` | `7888fe2`, `ac0f47d` |
| 34 | Alcance | Retirar el sentimiento de noticias | `244af23` |
| 35 | Datos | Conservar los precios si falta la ficha del activo | `8ad866b` |
| 36 | Datos | Validación estricta en las fronteras | README, «Validación de entradas» |
| 37 | Datos | Marcar los saltos de más del 50 % sin corregirlos | README, `metrics.py` |
| 38 | Datos | Descargar los activos en lote, uno tras otro | README, «Validación de entradas» |
| 39 | Proveedores | Un proveedor por ejecución, sin cambio automático | README, «Elección del proveedor» |
| 40 | Medidas | Contrato temporal de las medidas | README, «Contrato temporal» |
| 41 | Medidas | 365 períodos al año en carteras solo cripto | `c04ac05` |
| 42 | Modelado | Instantáneas inmutables de verdad | README, `f5327ca` |
| 43 | Medidas | `Adj Close` cuando todos los activos lo publican | README, `7888fe2` |
| 44 | Referencias | Índice, inflación y tipo libre de riesgo según la divisa | README, `7888fe2` |
| 45 | Referencias | Índice de referencia elegible con `--benchmark` | `c10fe69` |
| 46 | Medidas | Alfa en los mismos intervalos que la beta y precios de mercado recientes | `f5327ca` |
| 47 | Simulación | Retorno de Monte Carlo: tipo libre de riesgo más prima | README, `7888fe2` |
| 48 | Medidas | Un mes o un año está completo con un cierre hasta 5 días antes de su final | `7888fe2` |
| 49 | Consola | `--plots-report` no descarga referencias | README, `ac0f47d` |
| 50 | Cartera | Cartera por número de acciones (`--shares`) | `edbee1b`, `b15534c`, `a7cae73`, `e8e7845` |
| 51 | Caché | Caché de Yahoo por símbolo | `95eb80e` |
| 52 | Informe | Diez secciones que responden a una pregunta | README, `7888fe2`, `e8e7845` |
| 53 | Informe | Advertencias orientativas con umbrales configurables | README, `warnings.py` |
| 54 | Calidad | Límites de complejidad, cobertura mínima y CodeQL | `973e5f7`, `dce38fa` |
| 55 | Entorno | Python 3.11 como versión mínima | `95eb80e` |
| 56 | Documentación | Diagramas generados por script en cuatro formatos | `diagramas/README.md` |

**Parte III · Detalles contrastados con las conversaciones disponibles**

| # | Tema | Decisión | Estado |
| --- | --- | --- | --- |
| 57 | Integración | Adaptar las mejoras del informe sin duplicar motores | Aplicada; ampliada después en 33 |
| 58 | Diversificación | Usar pesos actuales y distinguir concentración de independencia | Parcial: explicación pendiente |
| 59 | Riesgo | Explicar VaR, CVaR y bandas con sus unidades y horizonte | Parcial: redacción mejorable |
| 60 | Riesgo | Describir profundidad, duración y recuperación de las caídas | Vigente |
| 61 | Referencias | Comparar cartera e índice en la misma divisa y fechas | Vigente |
| 62 | Simulación | Proyectar las posiciones finales, conservando la estrategia | Vigente |
| 63 | Pruebas | Cubrir precios planos, referencias ausentes y cambios de divisa | Vigente |

**Parte IV · Decisiones de las sesiones de trabajo**

| # | Tema | Decisión | Estado |
| --- | --- | --- | --- |
| 64 | Simulación | Un único Monte Carlo para activo y cartera | Vigente; su forma la sustituyó la 4 |
| 65 | Proveedores | Contrato común con las opciones en el constructor | Vigente |
| 66 | Datos | Solo fechas ISO `AAAA-MM-DD` | Vigente |
| 67 | Consola | Un año de historial en Yahoo y 120 días en Alpha Vantage | Vigente |
| 68 | Informe | `.plots_report()` reúne todas las figuras | Vigente |
| 69 | Documentación | Diagramas versionados y legibles con cualquier tema | Parcial: falta el BCE |
| 70 | Datos macro | API oficial de FRED con clave, no la descarga CSV | Vigente |
| 71 | Instalación | Inicio rápido por sistema y publicación del informe con reintentos | Vigente |
| 72 | Código limpio | Simplificar sin cambiar el comportamiento | Modificada en parte (ver 54) |

**Parte V · Decisiones sobre Monte Carlo (7 y 8 de noviembre)**

| # | Tema | Decisión | Estado |
| --- | --- | --- | --- |
| 73 | Simulación | Estimar volatilidad y correlaciones con 5 años, aparte del período del informe | Vigente |

---

## Forma de trabajo

### 1. Ramas y pull requests, sin commits automáticos

**Decisión.** Cada cambio se hace en su propia rama (`refactor/code-review`,
`ci/integracion-apis`, `feature/comision`, `feature/mult-matrix`…) y llega a `main` por pull
request. Nada se confirma ni se sube sin que el equipo lo pida. Los conflictos se resuelven
con un *merge* de `main` en la rama, no con *rebase*.

**Por qué.** Es un trabajo de equipo y la autoría de cada cambio importa. El *rebase*
reescribiría una rama que ya está subida y que otros pueden tener descargada.

**Ejemplo.** La PR #22 (comisiones) entró en conflicto con la PR #18, que se había
integrado antes. El único conflicto estaba en los imports de `portfolio_analysis.py`: una
rama añadía `MONTHLY` y la otra `MARKET_PRICE_MAX_AGE_DAYS`. Se fusionó `main` en la rama
conservando los dos imports, sin reescribir su historial.

**Ampliación (S3, S7 y S8).** El *rebase* solo se usó en ramas que aún no se habían
subido. En la pull request de un compañero, las correcciones se añaden como commits nuevos en su
rama y la descripción se deja a su autor.

**Ejemplo.** La revisión de `--shares` se subió como dos commits nuevos en la rama de la
PR #13, sin rehacer los del autor. En la PR #14 no se cambió la descripción, aunque citaba
un commit antiguo de las láminas: se avisó para que la actualizara quien la había escrito.

---

## Arquitectura

### 2. Capas con dependencias en un solo sentido

**Contexto.** La revisión del 30 de octubre encontró que los modelos importaban la
simulación, el análisis y los informes, y que había un ciclo entre `analysis` y `models`
que solo se evitaba importando dentro de los métodos.

**Decisión.** Las dependencias van siempre hacia abajo:
consola → carga e informes → análisis y simulación → modelos → base.
Las fachadas cómodas (`portfolio.report()`, `result.plot()`) se mantienen, pero son
envoltorios de una línea.

**Por qué.** Si `Portfolio` conoce el informe, cualquier cambio en el informe puede romper
la cartera. Con un solo sentido, cada capa se entiende y se prueba sin las de arriba.

**Ejemplo.** Es como una cocina: el cocinero (análisis) usa los ingredientes (modelos),
pero los ingredientes no necesitan saber qué plato se va a servir. `Portfolio` calcula su
valor, y es `reporting` quien decide cómo mostrarlo.

### 3. Separar `MarketContext` en `FxRates` y `MarketReferences`

**Contexto.** `MarketContext` mezclaba dos cosas: los tipos de cambio y las referencias del
análisis (índice, inflación y tipo libre de riesgo). Eso obligaba a fusionar contextos y a
reasignar `portfolio.market_context` desde la consola.

**Decisión.**
- `FxRates` pertenece a la cartera, porque sin tipos de cambio no se puede valorar.
- `MarketReferences` se pasa a `portfolio.analyze(references)`, porque solo lo usa el
  análisis.

**Ejemplo.** Una cartera en euros con acciones de IBM necesita el cambio EUR/USD para saber
cuánto vale. Eso es `FxRates`. El S&P 500 o la inflación solo hacen falta para comparar y
calcular la ratio de Sharpe. Eso es `MarketReferences`. Una cartera se puede valorar sin
referencias, pero no sin tipos de cambio.

### 4. Composición y `SimulationSettings` en lugar de `MonteCarloMixin`

**Contexto.** El *mixin* añadía herencia sin reutilizar nada: solo desempaquetaba una tupla
y reenviaba 11 argumentos. Además, la semilla por defecto era `None` en `monte_carlo()` y 42
en el informe y la consola, y la consola detectaba las opciones de Monte Carlo usadas sin
`--simulate` comparándolas con valores fijos.

**Decisión.** Una función `simulate()` sirve tanto para `Asset` como para `Portfolio`. Los
parámetros se agrupan en un objeto, `SimulationSettings`, que fija los valores por defecto y
los valida una sola vez. La semilla por defecto es 42 en todas partes.

**Ejemplo.** Antes, `--steps 252` sin `--simulate` se aceptaba sin avisar, porque 252
coincidía con el valor por defecto. Ahora argparse usa `default=None` y se rechaza. Con
`SimulationSettings(steps=252, simulations=1000, seed=42)`, dos ejecuciones dan exactamente
el mismo resultado, se lancen desde Python o desde la consola.

### 5. Calcular la valoración de la cartera una sola vez

**Contexto.** Las propiedades de la cartera repetían en cada acceso la unión de precios, la
conversión de divisas y el backtest. Una ejecución con `--report --simulate` hacía unos cinco
backtests.

**Decisión.** La cartera es inmutable, así que calcula su valoración una vez y la reutiliza.
Los datos de los que depende son copias protegidas (consulta «Instantáneas inmutables» en
el README).

**Ejemplo.** Es como apuntar el resultado de una suma larga en vez de volver a hacerla cada
vez que alguien pregunta. Como los números de partida no pueden cambiar, el resultado
apuntado sigue siendo válido.

---

## Modelado de datos

### 6. Tipos explícitos en lugar de diccionarios y cadenas

**Contexto.** `PriceHistory.info` era un diccionario con unas 18 claves implícitas, escritas
por tres proveedores y leídas con `.get("...")`. Seis no se leían nunca. Los avisos llegaban
en cinco formas distintas (`warnings`, `risk_warnings`, `metric_notes`…).

**Decisión.**
- La ficha del activo es un `AssetProfile` con campos fijos.
- Los avisos son `Notice`, que distingue datos que revisar de notas de metodología.
- Cada aviso de riesgo lleva su unidad.
- Los valores cerrados (rebalanceo, tipo de activo…) usan `Literal`.

**Ejemplo.** Antes, un error tipográfico como `info.get("curency")` devolvía `None` en
silencio y el fallo aparecía mucho después. Con `history.profile.currency`, el editor y las
pruebas detectan el error en el momento.

### 7. Una única forma de indicar pesos

**Contexto.** `Portfolio` recibía dos listas paralelas y el cargador un diccionario. Además
había cuatro nombres parecidos, y `weights` significaba los pesos *actuales*, no los
objetivo.

**Decisión.** Los pesos son siempre un diccionario `símbolo → peso`. Los objetivo se llaman
`target_weights` y los del final del histórico, `current_weights`.

**Ejemplo.** `Portfolio(activos, {"IBM": 0.6, "MSFT": 0.4})`. Si al cabo de un mes IBM ha
subido más, `target_weights` sigue siendo 60/40, pero `current_weights` puede ser 62/38.
Con nombres distintos no se confunde «lo que quiero» con «lo que tengo».

### 8. Errores propios y mensajes por la salida de errores

**Decisión.** `PortfolioError` cubre los datos o parámetros que impiden el análisis, y su
subclase `ConfigurationError` la configuración que falta, como una clave de API. La consola
solo captura estos errores y los muestra por la salida de errores (stderr). Un `TypeError`
ya no se presenta como un error del usuario.

**Ejemplo.** Si el usuario escribe pesos que suman 1,2, ve un mensaje claro en español. Si
hay un fallo de programación, por ejemplo una función llamada con un argumento de más, se
muestra la traza completa. Así no se esconde un fallo del código detrás de un mensaje de
«revisa tus datos».

### 9. Constantes, textos y registros en un único sitio

**Decisión.**
- Los literales repetidos (`"Close"` aparecía 17 veces, `252` aparecía 14) pasan a
  `constants.py`.
- Los párrafos del informe pasan a `texts.py` y las etiquetas a `labels.py`.
- Las tres listas de gráficos se unen en un único registro, `CHARTS`.
- Un diccionario `PROVIDERS` sustituye la cadena de `if` que elegía el proveedor.

**Ejemplo.** Para añadir un bróker o un proveedor nuevo basta con una entrada más en su
diccionario, sin tocar el resto del programa. Si cambia el número de sesiones del año,
se cambia en una sola línea.

### 10. Patrones solo donde aportan

**Decisión.** Se mantienen o introducen:
- el adaptador con `Protocol` para los proveedores;
- los objetos de valor (dataclasses inmutables);
- los objetos de parámetros (`SimulationSettings`, `RunConfig`);
- los registros;
- las fachadas finas.

Se descartaron los contenedores de inyección de dependencias, los sistemas de *plugins*,
las clases abstractas con una sola implementación y los motores de plantillas.

**Por qué.** Prima la simplicidad: cada patrón debe resolver un problema que existe hoy.

**Ejemplo.** Yahoo y Alpha Vantage devuelven datos con formatos distintos, pero los dos
adaptadores entregan el mismo `PriceHistory`. El análisis no sabe de dónde vienen los datos.
Ese patrón sí aporta. Una clase abstracta para un único tipo de informe solo añadiría
código.

**Ampliación (S4).** Al preparar la presentación se acordó nombrar solo los patrones que el
código aplica de verdad:
- `PROVIDERS` es un registro de constructores, no una *Abstract Factory*.
- `build_report()` no aplica el patrón *Builder* por llamarse así.
- Los proveedores no son un *Repository* de entidades.
- La arquitectura no es hexagonal estricta: `Portfolio` conoce la simulación y sus fachadas
  llegan al informe.

**Ejemplo.** Si en la presentación se pregunta dónde está la *Abstract Factory*, el código no
tiene respuesta. Decir «un diccionario que asocia cada nombre de proveedor con su
constructor» describe exactamente lo que hay y se puede enseñar en una línea.

### 11. Aplazar el cambio de nombre del paquete `src`

**Decisión.** El paquete se sigue llamando `src`, aunque al instalarlo aparece con ese
nombre en `site-packages`.

**Por qué.** Renombrarlo cambia todos los imports y entraría en conflicto con todas las
ramas abiertas. Es una decisión de equipo y se propuso `miax_cartera` como nombre.

**Ejemplo.** Es como cambiar el nombre de una calle con obras en marcha: mejor hacerlo
cuando nadie esté trabajando en ella.

---

## Calidad y limpieza de datos

### 12. No rellenar fechas sin precio

**Decisión.** Si a una fecha le falta el cierre, se elimina esa fila y se informa de cuántas
se han quitado. Ya no se rechaza toda la descarga, y tampoco se inventa un valor.

**Ejemplo.** Si falta el cierre del 15 de marzo, rellenarlo con el del 14 crearía una
rentabilidad del 0 % ese día. Eso rebaja la volatilidad y las correlaciones de forma
artificial. Es mejor quitar el día y avisar.

### 13. Tolerancia de 1e-5 en la suma de pesos

**Decisión.** Los pesos deben sumar 1 con una tolerancia de 1e-5 y después se ajustan para
que sumen exactamente 1. Antes la tolerancia era 1e-10.

**Por qué.** Se probó 1e-6, pero el error de redondeo de los números decimales hacía que
`0,333333 × 3` siguiera fallando por muy poco.

**Ejemplo.** Tres activos a partes iguales escritos con seis decimales (0,333333 + 0,333333
+ 0,333333 = 0,999999) se aceptan. En cambio, `IBM:60` se rechaza, porque no se convierten
porcentajes: sería un 6.000 %.

### 14. Normalizar la divisa antes de compararla

**Decisión.** El código de divisa se limpia (espacios, mayúsculas) antes de compararlo.

**Ejemplo.** Con `"USD "` (con un espacio al final), el programa decía «cotiza en USD; la
divisa indicada es USD ». Ahora se acepta.

### 15. Informes y caché seguros ante fallos

**Decisión.**
- El informe se construye entero y se escribe al final. Si algo falla, se borra la carpeta
  a medio hacer y se cierran los gráficos abiertos.
- Los informes se guardan en `./informes` o en `--output-dir`, no junto al paquete
  instalado.
- La caché borra las respuestas caducadas y escribe cada archivo de forma atómica (primero
  en un archivo temporal y después lo renombra).

**Ejemplo.** Antes, si fallaba el quinto gráfico, quedaba una carpeta con cuatro imágenes y
sin informe. Además, ejecutar el programa siete días seguidos dejaba siete archivos de caché
de FRED que nunca se borraban.

---

## Claves de API

### 16. Funcionar sin claves y avisar de lo que falta

**Decisión.** El programa funciona completo con Yahoo Finance sin ninguna clave. Antes de
descargar nada, `check_api_keys()` comprueba:
- **la clave del proveedor elegido:** si falta, el programa se detiene con un error que
  propone la alternativa;
- **las claves opcionales:** si falta alguna, avisa de qué medidas faltarán y genera el
  informe con el resto.

**Ejemplo.**

| Situación | Resultado |
| --- | --- |
| Sin ninguna clave | Precios, divisas, Monte Carlo, gráficos e informe con Yahoo |
| `--provider alpha_vantage` sin su clave | Se detiene: «configura ALPHA_VANTAGE_API_KEY… o usa `--provider yahoo`» |
| `--report` sin `FRED_API_KEY` | Avisa de que faltarán la inflación, la rentabilidad real, Sharpe y Sortino, y genera el informe |
| Clave rechazada | Muestra el motivo que da el proveedor, nunca la clave |

---

## Datos macroeconómicos

### 17. Cambiar FRED por ALFRED (30 de octubre)

**Contexto.** FRED devuelve la última versión revisada de cada serie. Si se entrena o
evalúa un modelo en 2020 con datos descargados hoy, se usan cifras que el mercado aún no
conocía en 2020. Esto es el **sesgo de anticipación** (*look-ahead bias*).

**Decisión.** Usar ALFRED, el archivo de versiones de FRED, para tomar en cada fecha el
último dato publicado ese día. Los tipos de cambio se siguieron leyendo por fecha de
observación, porque son precios de mercado que no se revisan.

**Ejemplo con el IPC.**

| Fecha del análisis | Dato que se usaba |
| --- | --- |
| Antes del 12 de septiembre | IPC de julio (el de agosto aún no se había publicado) |
| Del 12 de septiembre al 14 de octubre | Primera publicación del IPC de agosto |
| Desde el 15 de octubre | IPC de septiembre |

**Estado.** Revertida al día siguiente (ver decisión 18).

### 18. Volver a FRED, con el BCE para el euro (31 de octubre)

**Decisión.** La inflación, el VIX, el Brent y el tipo libre de riesgo en USD vuelven a
consultarse en FRED. El tipo libre de riesgo en EUR se consulta en la API del BCE, que no
necesita clave. (Commit `10397b4`.)

**Por qué.**
- Estos datos solo intervienen en medidas que se calculan al final del periodo
  (rentabilidad real, Sharpe y Sortino) para describir lo que pasó. Para eso, la cifra
  revisada es la mejor estimación.
- Ninguna decisión de la cartera depende de ellos, porque los pesos son fijos. Por eso no
  hay sesgo de anticipación que corregir.
- ALFRED tenía inconvenientes: el IPC entraba con un mes de desfase y su API rechaza más de
  2000 versiones por consulta, lo que impide pedir el tipo diario de más de unos ocho años.

**Ejemplo.** El sesgo de anticipación es como apostar en una carrera sabiendo ya quién ganó:
solo es un problema si la información influye en la apuesta. Aquí la cartera no «apuesta»
con la inflación; solo la usa al final, para contar cuánto se ganó en términos reales.
Para eso conviene el dato más preciso, que es el revisado. ALFRED solo aportaría algo si una
regla de inversión usara el dato macro disponible en cada fecha.

**Comprobación previa (S3).** Antes de revertir se consultaron las API reales con el código
que usaba ALFRED:

| Serie | FRED | ALFRED |
| --- | --- | --- |
| €STR, de 2020 a 2024 | Datos desde el 2 de enero de 2020 | Datos solo desde el 5 de enero de 2022 |
| Letra a 3 meses (`DGS3MO`), de 2015 a 2025 | Funciona | Error HTTP 400: más de 2000 versiones |
| IPC (`CPIAUCSL`), diciembre de 2023 | 308,741: dato de diciembre, revisado | 307,917: publicado el 12 de diciembre, corresponde a noviembre |

Con ALFRED, una cartera en euros que empezara antes de 2022 se quedaba sin Sharpe ni Sortino,
y una en dólares con unos ocho años de historia, también. La vuelta a FRED eliminó 155 líneas
de código. Más tarde, el €STR se sustituyó por la deuda AAA del BCE (ver 44).

---

## Pruebas e integración continua

### 19. Pruebas unitarias sin red y pruebas de integración aparte

**Decisión.** La suite normal (`tests/test_*.py`) simula las respuestas de las API y no
necesita red ni claves. Las pruebas contra las API reales están en
`tests/integration_apis.py`. Ese nombre no empieza por `test_`, así que
`unittest discover` no las ejecuta. En GitHub reciben las claves como secretos del
repositorio.

**Ejemplo.** Si Yahoo está caído un día, las pruebas unitarias siguen pasando, porque lo
que comprueban es el código. Las de integración comprueban otra cosa: que las API siguen
respondiendo como esperamos.

### 20. Integración obligatoria y comprobación única para `main`

**Decisión.**
- Si falta un secreto, la integración **falla**. Antes solo avisaba y se omitía, así que
  pasaba sin haber probado nada.
- Un trabajo final, «Comprobaciones completas», solo se supera si todos los demás terminan
  bien. Un trabajo omitido cuenta como fallo.
- La regla de protección de `main` exige esa comprobación. La configuró el equipo en
  GitHub (*Settings → Rules → Rulesets*).

**Por qué.** Por defecto, GitHub da por superado un trabajo obligatorio que se ha omitido.

**Ejemplo.** Sin la comprobación final, si la integración se saltara por cualquier motivo,
el botón de merge se pondría en verde sin haber probado las API. Con ella, «omitido» se
trata como «suspendido».

### 21. El push solo lanza el pipeline en `main`

**Decisión.** Las ramas se prueban al abrir su pull request. Un push solo lanza el pipeline
en `main`. Además, la integración se ejecuta cada lunes y se puede lanzar a mano.

**Ejemplo.** Antes, un push a una rama con una PR abierta ejecutaba todo dos veces: una por
el push y otra por la PR. Eso también gastaba dos consultas de Alpha Vantage, que solo
permite unas 25 al día.

### 22. Comprobar el paquete instalado

**Contexto.** CI instalaba el paquete, pero ejecutaba las pruebas desde la raíz del
repositorio, así que Python importaba `src` de la carpeta y no del paquete instalado. Un
error de empaquetado pasaba desapercibido.

**Decisión.** Un trabajo nuevo, «Paquete instalable»:
1. construye el paquete y lo revisa con `twine check`;
2. comprueba que la rueda solo contiene `src/` y sus metadatos;
3. la instala y repite las pruebas con `python -P`, que no añade la raíz del repositorio a
   las rutas de importación.

**Ejemplo.** Este trabajo encontró un problema real: una prueba nueva importaba
`from tests.test_providers import ...`, que solo funciona desde la raíz del repositorio.
En el trabajo normal pasaba, y en este fallaba con `No module named 'tests'`. Se cambió al
estilo del resto de pruebas, `from test_providers import ...`.

### 23. Buscar claves filtradas con gitleaks

**Decisión.** Un trabajo de CI ejecuta gitleaks sobre todo el historial con reglas propias
en `.gitleaks.toml`. El equipo activó además el escaneo de secretos de GitHub en la
configuración del repositorio.

**Por qué.** El escáner de GitHub no reconoce el formato de las claves de Alpha Vantage ni
de FRED, así que por sí solo no las detectaría.

**Ejemplo.** Se probaron siete claves falsas en distintos sitios (una línea de `.env`, un
argumento `api_key=`, una URL y una celda de cuaderno). Las reglas detectaron las siete y no
dieron falsos positivos en el repositorio.

### 24. Consultar Alpha Vantage solo cuando hace falta

**Contexto.** Había dos propuestas: ejecutar Alpha Vantage solo a mano, o hacerlo según los
archivos que cambie la PR. El equipo eligió la segunda.

**Decisión.**
- En una pull request, solo se consulta Alpha Vantage si cambian `src/providers/`,
  `src/validation.py`, `tests/integration_apis.py`, `pyproject.toml` o el pipeline.
- Tras integrar en `main`, cada lunes y a mano, se consulta siempre.
- Si la cuota está agotada, la prueba se omite con un aviso en lugar de fallar.

**Ejemplo.** Una PR que solo cambia el texto del informe no gasta ninguna de las 25
consultas diarias. Una que cambia el adaptador de Alpha Vantage sí lo prueba, porque es
justo ahí donde puede romperse.

<a id="cuota-alpha-vantage"></a>

### 25. Correcciones del contador de cuota de Alpha Vantage

**Origen.** Conversación C2, commit `d150397` y
[`src/providers/alpha_quota.py`](src/providers/alpha_quota.py).

**Contexto.** Había separación entre peticiones, pero faltaba un límite diario persistente.
El usuario pidió controlar el plan gratuito y añadió que la misma clave podía utilizarse
en CI y en local. Un contador local por sí solo no conoce ese consumo externo.

**Decisión.**
- Se permiten como máximo 25 intentos por clave en una ventana móvil de 24 horas. Se reserva
  antes del envío: cuentan también los intentos fallidos, pero una respuesta de la caché no
  consume cuota. Se informa de cuándo se libera la reserva más antigua, sin reintentar
  automáticamente.
- Las reservas se guardan en SQLite, fuera de la caché, y se coordinan de forma atómica
  entre los procesos que usan el mismo archivo. Cambiar de carpeta o reiniciar Python no
  reinicia el contador. Si no se puede comprobar o guardar, no se envía la consulta.
- Se guarda el hash de la clave, no la clave en texto. La ruta se puede indicar con
  `ALPHA_VANTAGE_USAGE_DB`; borrar la caché de precios no borra el registro de cuota.
- Un rechazo remoto prevalece sobre el contador local. Se reconocen `Information` y `Note`
  en respuestas HTTP 200, y HTTP 429 incluso sin JSON. Los errores de clave inválida o de
  acceso a un endpoint premium no se convierten en agotamiento de cuota.
- El bloqueo remoto se conserva entre ejecuciones. Intentar consultar durante ese bloqueo
  no alarga su duración y la caché sigue disponible. Si solo falla la ficha opcional del
  activo, se conservan los precios ya descargados (ver 35).
- **La clave nunca aparece en una traza de error.** El error de cuota se lanza fuera del
  bloque `except`, para que no arrastre el error original de `requests`, cuyo mensaje
  incluye la URL con `apikey=`.
- **Dos tipos de bloqueo:** un mensaje de límite diario bloquea 24 horas, y uno de límite
  por segundo o por minuto bloquea solo 60 segundos. Un HTTP 429 sin más detalle también
  usa el bloqueo corto.
- El límite fijo de 25 al día queda como decisión pendiente del equipo, porque afectaría a
  quien tenga un plan de pago.

**Detalle trasladado del README.** El archivo por defecto es
`~/.local/state/miax/alpha-vantage.sqlite3`. Cada historial consume una petición y cada
ficha `OVERVIEW`, otra: la consola puede gastar 24 peticiones al cargar 12 activos sin caché.
Separar el registro de la caché evita que limpiar precios descargados reinicie el contador.
Los procesos con la misma clave deben compartir el mismo archivo persistente.

**Ejemplo.** Alpha Vantage responde «use sparingly» cuando se hacen dos peticiones en el
mismo segundo. Antes, eso bloqueaba la clave un día entero. Ahora se espera un minuto y se
sigue. Si hay duda sobre qué tipo de mensaje es, se elige el bloqueo corto: equivocarse así
cuesta una petición rechazada, y al revés costaría un día sin datos.

**Ejemplo de clave compartida.** CI ha consumido 24 consultas y el ordenador local no ha
hecho ninguna. Una descarga de precios puede consumir la última; la consulta posterior de
la ficha recibe el rechazo diario. Aunque el contador local solo registre dos intentos, se
guarda el bloqueo remoto y se conserva el historial de precios. Reiniciar el programa no
provoca otra petición; leer esos precios desde la caché sí sigue permitido.

**Límite del diseño.** SQLite coordina procesos que comparten su archivo, no máquinas
distintas. El cliente local descubre el consumo externo cuando el proveedor lo rechaza;
no puede anticipar la cuota global restante. Una sincronización preventiva requeriría un
registro central compartido, que no se implementó.

**Estado.** Vigente con las correcciones de bloqueo corto descritas arriba. En C2 el primer
diseño esperaba 24 horas ante cualquier rechazo de cuota; no es la regla actual para los
avisos de ritmo.

**Otras mejoras propuestas y no aplicadas.** De las mejoras gratuitas propuestas para el
pipeline, el equipo eligió el paquete instalable, la búsqueda de claves y la cuota de Alpha
Vantage (decisiones 22 a 24). Quedaron fuera Windows en CI, las versiones mínimas de
dependencias, Dependabot, `pip-audit`, tipado estático y pre-commit. Más tarde se añadieron
la cobertura mínima y CodeQL.

---

## Comisiones del rebalanceo (6 de noviembre)

### 26. Tarifas de bróker con IBKR por defecto

**Decisión.** Cada orden de rebalanceo paga una comisión. Hay tarifas predefinidas,
consultadas en noviembre de 2026 y orientativas:

| `--broker` | Tarifa por orden |
| --- | --- |
| `ibkr` (por defecto) | 0,05 %, mínimo 3 |
| `degiro` | 2 fijos |
| `trade_republic` | 1 fijo |
| `xtb` | 0 |
| `none` | Sin comisiones |

El usuario puede cambiar cualquier campo con `--commission-rate`, `--commission-fixed`,
`--commission-min` y `--commission-max`.

**Por qué IBKR.** Su modelo porcentual con mínimo es la referencia profesional más usada y
penaliza bien las órdenes pequeñas, que son las típicas de un rebalanceo.

**Ejemplo.**
- Una orden de 10.000 € paga 5 € (0,05 %).
- Una de 1.000 € pagaría 0,50 €, pero se aplica el mínimo: 3 €, que es un 0,3 % de la orden.
- Con `--broker degiro --commission-min 5`, se parte de DEGIRO y se fija un mínimo de 5.

### 27. Rebalancear solo si compensa: banda y coste máximo

**Decisión.** A fin de mes solo se reajusta si algún peso se desvía más de 5 puntos de su
objetivo (`--rebalance-band 0.05`). Además, se descarta cualquier orden cuya comisión supere
el 1 % de su importe (`--max-order-cost 0.01`). Monte Carlo aplica la misma regla.

**Por qué.** Con comisiones, reajustar cada mes suele costar más de lo que aporta.

**Ejemplo.** Objetivo 60/40:
- Si a fin de mes está en 63/37, la desviación es de 3 puntos y no se hace nada.
- Si está en 66/34, la desviación es de 6 puntos y se rebalancea.
- Si una de las órdenes es de 200 €, el mínimo de 3 € supone un 1,5 % y esa orden se
  descarta.

**Estado.** Vigente. Hasta la PR #26 el informe solo decía «rebalanceo mensual» en la
cabecera y en Monte Carlo, aunque se aplicaba la banda. Ahora ambas indican «si algún peso se
desvía más de 5,00 p. p. de su objetivo» (ver 73). Con `--rebalance-band 0` desaparece la
condición.

### 28. Comparar con comprar y mantener

**Decisión.** El informe añade la tabla «Coste del rebalanceo», con:
- los reajustes;
- las órdenes ejecutadas y descartadas;
- las comisiones pagadas;
- el valor final con y sin rebalanceo.

La advertencia solo aparece si sin comisiones rebalancear habría compensado y con ellas no,
o si las comisiones se llevan más del 10 % de la ganancia.

**Por qué no avisar siempre que rebalancear rinda menos.** Suele pasar cuando un activo sube
mucho más que el resto. Es el precio de mantener el riesgo previsto, no un problema.

**Ejemplo real** (SPY 60 % / TLT 40 %, 2023–2026, 10.000 USD):

| Configuración | Reajustes | Comisiones | Valor final |
| --- | --- | --- | --- |
| Por defecto (IBKR y banda) | 3 | 18 USD | 15.391 |
| IBKR reajustando cada mes | 44 | 264 USD | 14.925 |
| Cada mes sin comisiones | 46 | 0 | 15.246 |
| Sin rebalancear | — | — | 16.225 |

La banda ahorra unos 250 USD frente a reajustar cada mes. Sin rebalancear se gana más
porque en ese periodo las acciones subieron mucho más que los bonos.

### 29. Valores por defecto solo en la consola

**Decisión.** La consola usa IBKR, la banda de 5 puntos y el coste máximo del 1 %. Desde
Python, `Portfolio` no paga comisiones salvo que se le pase `rebalance_rule`.

**Por qué.** Así los resultados y las pruebas que ya existían no cambian.

**Ejemplo.**
```python
rule = RebalanceRule(BROKER_PRESETS["degiro"], band=0.05, max_order_cost=0.01)
Portfolio(activos, {"IBM": 0.6, "MSFT": 0.4}, rebalance_rule=rule)
```

### 30. Simplificaciones del modelo de costes

**Decisión.**
- La compra inicial no paga comisión, porque es la misma con y sin rebalanceo.
- Los importes fijos se aplican en la divisa de la cartera.
- Quedan fuera los impuestos, el coste del cambio de divisa y el ITF español. Este último se
  puede aproximar con `--commission-rate`.
- No se modelan aportaciones ni retiradas; se permiten fracciones de activos para aplicar
  los pesos sin tener que simular efectivo sobrante ni redondear cantidades enteras.

**Ejemplo.** Al comparar las dos estrategias, los 3 € de la compra inicial aparecerían en
ambas y se anularían. Quitarlos no cambia la comparación y la hace más clara.

---

## Vectorización (6 de noviembre)

### 31. Vectorizar el backtest sin rebalanceo

**Contexto.** Se revisó si había bucles `for` que pudieran sustituirse por operaciones
matriciales. La mayoría de los cálculos ya estaban vectorizados: la covarianza, los shocks
correlacionados de Monte Carlo (`shocks @ factor.T`) y las contribuciones al riesgo
(`w @ Σ @ w`).

**Decisión.** Sin rebalanceo, el backtest calcula las posiciones de una vez con
`capital × pesos × np.cumprod(crecimiento, axis=0)`, en lugar de recorrer las fechas. Con
rebalanceo mensual se mantiene el bucle, porque cada reajuste depende del anterior.

**Ejemplo.** 10.000 € al 60/40. El activo A sube un 10 % y luego baja un 5 %; el B se
mantiene y luego sube un 2 %.

| | Día 1 | Día 2 |
| --- | --- | --- |
| A: 6.000 × producto acumulado | 6.000 × 1,10 = 6.600 | 6.000 × 1,10 × 0,95 = 6.270 |
| B: 4.000 × producto acumulado | 4.000 × 1,00 = 4.000 | 4.000 × 1,00 × 1,02 = 4.080 |

El producto acumulado da todas las fechas en una sola operación. El resultado es el mismo
que con el bucle (diferencia máxima de 1e-11) y unas 8 veces más rápido.

### 32. Mantener los bucles de Monte Carlo, betas y comisiones

**Decisión.** No se vectorizan:
- **Monte Carlo sin rebalanceo.** El bucle da unas 252 vueltas, una por paso, y dentro de
  cada vuelta ya calcula los 10.000 escenarios a la vez. Quitarlo obliga a tener en memoria
  todos los pasos de golpe.
- **Betas por activo.** Solo hay unos pocos activos y el bucle también construye la ficha de
  cada uno.
- **El ajuste de comisiones (`for _ in range(3)`).** La comisión depende del tamaño de la
  orden, y la orden de la comisión. Es una iteración de punto fijo, no una multiplicación.

**Ejemplo medido** (252 pasos y 10.000 escenarios):

| Activos | Bucle actual | Vectorizado | Memoria del vectorizado |
| --- | --- | --- | --- |
| 2 | 0,09 s | 0,14 s | 121 MB |
| 8 | 0,26 s | 0,84 s | 484 MB |

Con más activos, la versión vectorizada sale peor. Lo que cuesta es mover casi 500 MB de
memoria, no las 252 vueltas del bucle. El backtest era distinto: miles de fechas, muy poco
trabajo en cada una y ninguna memoria extra.

---

# Parte II · Decisiones documentadas en el proyecto

Estas decisiones no salen de las sesiones de la parte I, sino del README, `ARQUITECTURA.md`,
el código y los mensajes de commit. Cuando el commit no explica el motivo, se dice.

## Organización del equipo y alcance

### 33. Unificar la versión de Carlos con la estructura de `main`

**Origen.** Commits `7888fe2` y `ac0f47d` (2 de noviembre, PR #10).

**Contexto.** Había dos versiones del programa: la de `main` y la de la rama de Carlos, que
tenía su propia estructura en `src/toolkit` (`ingesta`, `modelos`, `analisis`, `salida`).

**Decisión.** `src/toolkit` desaparece y su contenido pasa a la estructura de `main`. De cada
versión se conserva lo mejor:
- **De `main`:** el crecimiento anualizado por días naturales, `--benchmark`, los datos de
  solo lectura, las pruebas de contratos, los diagramas y la validación de entradas.
- **De Carlos:** el informe de 10 secciones con 12 gráficos, el tipo libre de riesgo del
  BCE, el retorno de Monte Carlo y el contexto de mercado.

**Ejemplo.** Es como juntar dos borradores de un mismo trabajo: se elige un índice común
(la estructura de `main`) y en cada capítulo se queda la versión más completa, en lugar de
mantener dos programas que hacen lo mismo.

### 34. Retirar el sentimiento de noticias

**Origen.** Commit `244af23` (31 de octubre).

**Decisión.** Se eliminó el módulo que descargaba titulares de Google News y puntuaba su
sentimiento con `pysentimiento` (español) y FinBERT (inglés), junto con sus dependencias,
su métrica y su sección del informe.

**Por qué.** El commit no lo explica. Lo que sí consta en el propio módulo es que los modelos
de sentimiento eran paquetes pesados y opcionales: sin ellos, solo se obtenían los titulares,
sin puntuación.

**Ejemplo.** Para analizar una cartera de IBM y MSFT, el programa necesita precios,
referencias y simulación. Instalar un modelo de lenguaje de cientos de megas para añadir una
cifra de «sentimiento» complicaba la instalación sin cambiar ningún cálculo de la cartera.

## Datos y proveedores

### 35. Conservar los precios si falta la ficha del activo

**Origen.** Commit `8ad866b` (29 de octubre, PR #2).

**Decisión.** Si Yahoo no devuelve la ficha de un activo (nombre, sector, divisa…), se
conservan los precios descargados y se anota el motivo, igual que ya hacía Alpha Vantage.
Hoy ese motivo está en `history.profile.issue`.

**Ejemplo.** Si Yahoo falla al dar el sector de un ETF poco conocido, el análisis sigue con
sus precios y el informe dice «Sector: desconocido» con la causa, en lugar de perder el
activo entero. Lo único que no se supone es la divisa: si falta, hay que indicarla.

### 36. Validación estricta en las fronteras

**Origen.** README, sección «Validación de entradas: por qué un contrato estricto».

**Decisión.** Los datos se validan donde entran: en la consola, en los adaptadores y en los
constructores de los modelos. Las reglas principales son:
- pesos entre 0 y 1 que suman 1, sin convertir porcentajes;
- fechas sin repetir, sin vacíos y sin zona horaria;
- `Close` positivo y finito;
- divisa conocida, nunca supuesta;
- fechas comunes sin rellenar huecos;
- antigüedad máxima de tipos de cambio y datos macro;
- validar antes de descargar.

**Por qué.** Un dato inválido rara vez falla donde entra. Avanza varios pasos y acaba en un
resultado que parece correcto pero no lo es. Los datos complementarios (ficha, índice,
inflación) no detienen el análisis: la medida que dependa de ellos aparece como «No
disponible», con su causa.

**Ejemplo.**
- Un precio de 0 produciría una rentabilidad infinita al día siguiente, así que se rechaza
  al cargarlo.
- Una cartera con una acción en dólares y otra en peniques (`GBp`) no se suma sin convertir.
- Con Alpha Vantage, un peso mal escrito se rechaza antes de gastar ninguna consulta de la
  cuota.

**Origen del criterio (S1 y S4).** La revisión del 29 de octubre encontró las comprobaciones
de pesos repetidas en cinco sitios (`parse_values`, `load_portfolio`, `Portfolio`, el
backtest y la simulación) y la misma guarda de tipos escrita once veces. Se reunieron en
`src/validation.py` con una regla: validar en las fronteras y confiar en las llamadas
internas. El 31 de octubre se añadió la justificación por escrito al README, porque el
apartado 4.5 del enunciado pide analizar y justificar la validación, no solo aplicarla.

### 37. Marcar los saltos de más del 50 % sin corregirlos

**Origen.** README («Validación de entradas») y `price_jumps()` en `src/analysis/metrics.py`.

**Decisión.** Una variación diaria de más del 50 %, al alza o a la baja, se señala en el
informe, pero no se modifica el dato.

**Por qué.** Suele ser un desdoblamiento (*split*) mal ajustado o un error de la fuente, pero
también puede ser real. Corregirlo automáticamente escondería el problema.

**Ejemplo.** Una acción con precios sin ajustar pasa de 300 a 100 por un *split* 3 por 1. Eso
parece una caída del 66,7 % en un día. El informe lo marca para que se revise, en lugar de
contarlo en silencio como una pérdida.

### 38. Descargar los activos en lote, uno tras otro

**Origen.** README, sección «Validación de entradas», apartado «Descarga en lote».

**Decisión.** `load_portfolio()` descarga los activos uno tras otro con el mismo proveedor,
sin hilos. Es una de las dos opciones que da el enunciado («simultánea o en lote»).

**Por qué.**
- Se respeta la cuota de Alpha Vantage sin coordinar hilos.
- Cada error se atribuye a su símbolo.
- La caché evita repetir consultas.
- Con pocas decenas de activos, el tiempo no es relevante.

Paralelizar sería un cambio local del cargador, sin tocar el contrato `PriceProvider`.

**Ejemplo.** Si en una cartera de 12 activos falla el séptimo, el mensaje dice exactamente
cuál ha fallado. Con 12 descargas a la vez sería más difícil saberlo y se podría pasar del
límite de Alpha Vantage en un instante.

### 39. Un proveedor por ejecución, sin cambio automático

**Origen.** README, sección «Elección del proveedor».

**Decisión.**
- El proveedor elegido (`--provider`) se usa para todos los activos de esa ejecución.
- Si una descarga falla, no se cambia de proveedor automáticamente.
- Las referencias tienen fuentes fijas: el índice, el oro, el ETF de Bunds y los cambios
  automáticos salen de Yahoo; la inflación, el VIX, el Brent y el tipo en USD, de FRED; y el
  tipo en EUR, del BCE.

**Ejemplo.** Si Alpha Vantage no encuentra un símbolo, cambiar a Yahoo sin avisar mezclaría
precios ajustados y sin ajustar en la misma cartera. Es mejor detenerse y que el usuario
decida.

## Medidas y referencias

<a id="contrato-temporal"></a>

### 40. Contrato temporal de las medidas

**Origen.** README, sección «Contrato temporal de las medidas».

**Decisión.** Cada medida declara cómo trata el tiempo, para que eliminar fechas intermedias
al cruzar calendarios no altere los resultados:
- **Crecimiento anualizado:** `(valor final / valor inicial) ^ (365,25 / días naturales) − 1`.
  Solo depende de las fechas extremas.
- **Dispersión (volatilidad, Sharpe, Sortino, VaR):** se calcula por observación y se escala
  con `periods_per_year` para las medidas anualizadas: 252 por defecto y 365 con calendario
  diario que incluye fines de semana (ver 41). El VaR por período conserva su horizonte.
- **Historial corto:** se mide en días naturales (menos de 350), no en número de sesiones.

**Cobertura.** El informe avisa si la separación típica entre observaciones supera cinco
días o si hay menos del 90 % de las esperadas para la duración del historial. Una serie
irregular no se convierte en diaria rellenando huecos: las medidas de dispersión dependen
de la frecuencia de las observaciones y deben leerse con esa limitación.

**Ejemplo.**
- Pasar de 10.000 a 11.000 en 182 días naturales equivale a un 21,1 % anual
  (`1,1 ^ (365,25 / 182) − 1`), falten o no sesiones intermedias por festivos.
- La media y el crecimiento compuesto pueden tener signos opuestos: con +20 % y −19 %, la
  media es +0,5 %, pero el valor cae un 2,8 % (1,20 × 0,81 − 1). El informe lo explica.
- Un año bursátil puede tener 249 sesiones comunes entre dos bolsas. Contar días naturales
  evita llamar «corto» a un historial de un año completo.

**Origen (S1 y S4).** Se llegó a este contrato por dos fallos reproducidos:
- **29 de octubre.** Tres precios mensuales (100, 110 y 121) se anualizaban como si fueran
  sesiones diarias, y la cifra salía del orden de 2,7 × 10¹⁰. Se añadió el aviso de
  separación típica superior a cinco días.
- **31 de octubre.** Con el mismo crecimiento del 20 % en el mismo período, 252 observaciones
  daban un 20,00 % anual y, quitando diez fechas intermedias, un 20,91 %. Por eso el
  crecimiento anualizado pasó a contar días naturales y no filas (commit `c10fe69`).

**Alternativa descartada (5 de noviembre): anualizar con las sesiones reales.** Al cruzar
bolsas con festivos distintos, las fechas comunes son menos de 252 al año, y se planteó
anualizar con el número real de sesiones. Se midió el efecto:
- España y EE. UU. pierden un 2,8 % de las fechas; EE. UU. y Japón, un 6,2 %. El movimiento
  del día eliminado no se pierde: entra en la rentabilidad del día siguiente.
- La volatilidad apenas cambia: 18,44 % frente a 18,45 % en un caso y 19,47 % frente a
  19,52 % en otro.

Se mantienen las fechas comunes y 252 períodos, la convención del mercado, para que las
cifras sean comparables con las de cualquier otra fuente. Solo las carteras de criptomonedas,
que cotizan todos los días, usan 365 (ver 41).

### 41. 365 períodos al año en carteras solo cripto

**Origen.** Commit `c04ac05` (5 de noviembre) y `src/frequency.py`.

**Decisión.** Si las fechas comunes son diarias e incluyen fines de semana (al menos un 20 %),
el análisis y Monte Carlo usan 365 períodos al año en lugar de 252. El horizonte por defecto
pasa a ser de 365 días y el rebalanceo mensual, cada 30 días. Las carteras con acciones
siguen con 252.

**Ejemplo.** Bitcoin cotiza los 7 días de la semana: 2 de cada 7 fechas caen en fin de semana.
Anualizar su volatilidad con 252 la subestimaría, porque un año tiene 365 observaciones. En
cuanto la cartera mezcla bitcoin con una acción, las fechas comunes son solo días de bolsa y
se vuelve a 252.

### 42. Instantáneas inmutables de verdad

**Origen.** README, sección «Instantáneas inmutables y estadísticos», y commit `f5327ca`
(PR #18).

**Decisión.** `frozen=True` impide reasignar atributos, pero no cambiar el contenido de un
`DataFrame` o una `Series`. Por eso:
- `PriceHistory` guarda una copia y `history.prices` devuelve otra;
- `target_weights`, `units` y `EconomicIndicator.values` son de solo lectura y rechazan
  también las etiquetas nuevas, las operaciones *inplace* y los cambios de índice o nombre;
- para otra composición se crea otra cartera con `dataclasses.replace(...)`, que vuelve a
  validar los pesos.

**Estadísticos del historial.** `PriceHistory.mean` y `PriceHistory.std` se calculan una
sola vez al crear el objeto, sobre `Open`, `High`, `Low`, `Close` y `Adj Close` cuando
existen. Se excluye `Volume`, porque no es un precio. Al proteger la instantánea, esos
estadísticos y la valoración memorizada siguen correspondiendo a los datos originales.

**Estadísticos de las rentabilidades (8 de noviembre).** Desde la rama
`feature/estadisticos-rentabilidades`, `PriceHistory` calcula también al crearse
`returns_mean` y `returns_std`: la media y la desviación típica de las rentabilidades simples
de `Close` y `Adj Close`. El enunciado pide media y desviación típica automáticas en la
DataClass de precios, y las de los niveles de precio casi no tienen sentido financiero:
dependen de lo que cueste la acción y mezclan la tendencia con la variación. Con datos reales
de 2021 a 2026, la desviación del precio de Inditex (12,40 €) es casi cuatro veces la de
Santander (3,19 €) solo porque su acción es más cara; la de las rentabilidades muestra lo
contrario: Santander es más volátil (1,95 % diario frente a 1,58 %). Se conservan `mean` y
`std` por compatibilidad. El informe no usa ninguno de los dos: calcula sus medias y
desviaciones sobre las fechas comunes de la cartera y en su divisa, que es otra serie.

**Ejemplo.** Sin esta protección, `portfolio.target_weights["IBM"] = 0.9` cambiaría los pesos
sin pasar por la validación y la valoración ya calculada (decisión 5) quedaría desfasada.
Ahora esa línea da un `ValueError`.

**Origen (S4 y S6).**
- **31 de octubre.** Se reprodujo que, tras `portfolio.target_weights["A"] = 0.9`, los pesos
  sumaban 1,4 y `total_value` seguía devolviendo el valor memorizado. También se aceptaba un
  precio de −5 en `history.prices`. Para el apartado 4.3 se decidió calcular la media y la
  desviación al crear el historial, en lugar de limitarse a explicar la diferencia con el
  enunciado: costaba pocas líneas.
- **5 de noviembre.** Todavía se podían añadir etiquetas nuevas o usar
  `drop(..., inplace=True)`. La PR #18 cerró esas vías. Solo queda sin bloquear el nombre del
  índice, que no cambia datos ni etiquetas.

### 43. `Adj Close` cuando todos los activos lo publican

**Origen.** README («Información y supuestos del informe») y commit `7888fe2`.

**Decisión.** Las rentabilidades, la simulación y el informe usan `Adj Close`, que incluye
los dividendos, si lo publican todos los activos. Si no, usan `Close` y el informe lo indica.
Todas las cifras son nominales salvo la rentabilidad real.

**Ejemplo.** Una acción que reparte un 3 % de dividendo y cuyo precio no cambia en un año ha
dado un 3 % al accionista. Con `Close` parecería un 0 %; con `Adj Close`, el 3 %. Mezclar
ambas columnas en una misma cartera favorecería a unos activos frente a otros.

### 44. Índice, inflación y tipo libre de riesgo según la divisa

**Origen.** README («Información y supuestos del informe») y commit `7888fe2`.

**Decisión.**

| Divisa | Índice | Inflación | Tipo libre de riesgo |
| --- | --- | --- | --- |
| USD | ETF del S&P 500 (`SPY`) | IPC de EE. UU. | Letra a 3 meses (FRED) |
| EUR | ETF del EURO STOXX 50 (`EXW1.DE`) | IPCA de la zona euro | Deuda AAA de la zona euro a 3 meses (BCE) |

- **La referencia es un ETF desde el 8 de noviembre.** Los índices `^GSPC` y `^STOXX50E` no
  incluyen dividendos y la cartera sí, lo que inflaba la ventaja y el alfa. Entre noviembre
  de 2024 y noviembre de 2026, `^STOXX50E` rindió un 12,80 % anual y `EXW1.DE` con dividendos,
  un 15,94 %; `^GSPC`, un 11,16 %, y `SPY`, un 12,41 %. Yahoo no devuelve datos del índice con
  dividendos `^SX5T`, y usar un ETF en las dos divisas las trata igual. `--benchmark` sigue
  admitiendo un índice; entonces el informe avisa de que puede no incluir dividendos.
- **En euros no se usa la €STR**, porque mide riesgo bancario, no de Estado.
- **El Bund a 10 años no se usa como tipo libre de riesgo**, porque tiene riesgo de precio.
  En su lugar, la cartera se compara con lo que rindió el ETF `EXHD.DE` (deuda alemana con
  cupones y variación de precio).
- **Para otras divisas,** las medidas sin referencia quedan sin calcular. No se supone un
  tipo del 0 %.

**Ejemplo.** Un tipo anual del 3 % se convierte en un tipo diario de
`1,03 ^ (1/252) − 1 ≈ 0,0117 %`. Eso es lo que se habría ganado cada sesión sin arriesgar, y
es lo que Sharpe y Sortino restan a la rentabilidad de ese día. Suponer un 0 % haría que
cualquier cartera pareciera mejor de lo que es.

### 45. Índice de referencia elegible con `--benchmark`

**Origen.** Commit `c10fe69` (31 de octubre, PR #11) y README («Uso»).

**Decisión.** El índice por defecto depende de la divisa, pero se puede cambiar con
`--benchmark`. Si el índice cotiza en otra divisa, se descarga su tipo de cambio para
compararlo en la divisa del informe. Cambiar el índice no cambia la inflación ni el tipo
libre de riesgo.

**Ejemplo.** Una cartera de SAN.MC e ITX.MC no se compara bien con el S&P 500. Con
`--benchmark ^IBEX` se compara con su mercado. Una cartera tecnológica en dólares se puede
comparar con el Nasdaq (`--benchmark ^IXIC`).

**Ampliación (S4).** El símbolo se valida antes de descargar nada, y la opción exige
`--report` o `--plots-report`: sin ellos no tendría efecto, así que se rechaza. La necesidad
apareció en la revisión del 31 de octubre: una cartera de acciones de EE. UU. convertida a
euros se comparaba con el EURO STOXX 50 y daba una beta de 0,16, que reflejaba la elección del
índice más que el riesgo de la cartera.

### 46. Alfa en los mismos intervalos que la beta y precios de mercado recientes

**Origen.** Commit `f5327ca` (5 de noviembre, PR #18).

**Decisión.**
- **El alfa de Jensen** se calcula sobre los mismos intervalos que la beta. Si el índice no
  cotiza en todas las fechas de la cartera, los retornos y el tipo libre de riesgo se
  calculan entre las fechas comunes.
- **El oro y el ETF de Bunds** solo se usan con cierres de hasta 7 días de antigüedad y al
  menos tres observaciones reales. Si no, sus medidas quedan sin calcular y un aviso lo
  explica.

**Ejemplo.**
- Una cartera de acciones de EE. UU. comparada con el IBEX: el IBEX no cotiza algunos
  festivos españoles en los que Wall Street sí. Si el alfa usara días que la beta no ve,
  ambas medidas no serían comparables.
- Si el ETF de Bunds deja de cotizar un mes, usar su último precio durante 30 días lo haría
  parecer «sin riesgo». Con el límite de 7 días solo se cubren festivos.

**Origen (S6).** Los dos fallos se reprodujeron con datos sintéticos, sin red, antes de
corregirlos:
- Con beta 1 y ninguna diferencia frente al índice, el alfa salía −79,19 % anual porque
  comparaba intervalos distintos. Tras la corrección sale 0, con un tipo libre de riesgo del
  0 % y del 2 %.
- Con un solo cierre del ETF de Bunds en todo un trimestre, el informe daba un 0 % de
  rentabilidad y 47 puntos de diferencia, sin ningún aviso.

Cada caso tiene una prueba que fallaba con el código anterior.

<a id="modelo-monte-carlo"></a>

### 47. Retorno de Monte Carlo: tipo libre de riesgo más prima

**Origen.** README («Parámetros de Monte Carlo») y commit `7888fe2`.

**Decisión.** Si no se indica `--return`, el retorno esperado es:

```text
mu = tipo libre de riesgo + 4,5 % × parte del activo en renta variable
```

- Las acciones y los índices cuentan como 100 % renta variable. En ETF y fondos se usa la
  composición que publica Yahoo.
- La renta fija, el oro y lo no clasificado reciben solo el tipo libre de riesgo.
- Hay 10.000 escenarios por defecto.
- El informe repite la simulación con el retorno histórico y con solo el tipo libre de
  riesgo, con los mismos escenarios aleatorios, para comparar.
- Si no se dispone del tipo libre de riesgo, el motor usa el retorno histórico como base;
  no inventa un tipo del 0 %. En ese caso la sensibilidad usa los casos alternativos
  configurados en `SENSITIVITY_RETURNS`. Los supuestos del usuario tienen prioridad.
- La advertencia de escenarios desfavorables sube del 30 % al 45 %.

**Por qué no el retorno histórico.** Es el supuesto más débil. La volatilidad y las
correlaciones se estiman bien con datos diarios, pero el retorno depende de los años de
historia, no del número de observaciones, y sobre todo refleja lo que ya pasó.

**Modelo trasladado del README.** Se usa movimiento browniano geométrico, con deriva
`mu`, volatilidad `sigma` y correlaciones constantes. Para `p` períodos por año:

```text
S(t+1) = S(t) × exp[(mu − sigma²/2)/p + sigma/√p × Z]
```

La volatilidad se estima con retornos simples históricos y se anualiza con `sqrt(p)`.
Los choques normales `Z` se correlacionan mediante Cholesky de la covarianza; si la matriz
es singular, se usan autovalores para conservarla. Cambiar la volatilidad de un activo
mantiene las correlaciones estimadas. Las colas reales pueden ser más extremas que las
del modelo; una simulación no garantiza pérdidas acotadas (ver 59).

**Ejemplo del parámetro.** `--return 0.08` fija una deriva continua, no una rentabilidad
anual exacta: para un activo sin costes, el crecimiento esperado a un año es
`exp(0.08) − 1 ≈ 8,33 %`. La semilla 42 permite reproducir escenarios si se mantienen
también los datos y el resto de los parámetros. No permite conservar resultados cuando
cambian las series descargadas.

**Ejemplo.**
- Con un tipo libre de riesgo del 3 %, un ETF 60/40 recibe `3 % + 4,5 % × 0,6 = 5,7 %`.
- Una acción que subió un 80 % el año pasado no recibe un 80 % esperado para el próximo año.
- Sobre el umbral: a un año, una cartera de bolsa pierde en cerca del 40 % de los
  escenarios. Avisar por encima del 30 % habría saltado casi siempre.

**Distribución normal, no t de Student (8 de noviembre).** Se planteó usar una t de Student
para recoger las colas gruesas de los rendimientos diarios. Se midió con una acción de
μ = 6,5 % y σ = 20 %, 100.000 escenarios y la t escalada para tener la misma volatilidad:

| Distribución | Percentil 5 a un año | CVaR 95 % a un año | Peor día simulado |
| --- | --- | --- | --- |
| Normal | −24,7 % | −30,5 % | −5,4 % |
| t de Student (5 grados) | −24,6 % | −30,4 % | −13,8 % |
| t de Student (3 grados) | −24,2 % | −30,7 % | −33,9 % |

A un día la t sí cambia las colas, pero a un año el VaR y el CVaR son casi iguales: al sumar
252 días independientes, el resultado vuelve a parecerse a una normal (teorema central del
límite). Lo que hace las pérdidas reales peores, las rachas de volatilidad y las caídas
conjuntas de los activos, no lo recoge ninguna de las dos si los días son independientes.
Se mantiene la normal. Las alternativas que sí cambiarían el resultado, el *bootstrap*
histórico por bloques o los escenarios de estrés, quedan como posibles mejoras.

**Horizonte de un año por defecto.** Se mantiene: es el plazo habitual del VaR y en el que
más se sostiene un modelo con μ, σ y correlaciones constantes. `--steps` lo cambia, en
sesiones: 21 para un mes y 1.260 para cinco años. A más años, el resultado depende cada vez
más del retorno supuesto.

### 48. Un mes o un año está completo con un cierre hasta 5 días antes de su final

**Origen.** Commit `7888fe2` (constante `PERIOD_CLOSE_TOLERANCE_DAYS = 5`).

**Decisión.** Para las tablas por mes y por año, un período cuenta como completo si su último
cierre es de hasta 5 días antes de que termine y se dispone del cierre de partida del
período anterior. En el último período del historial se exige llegar al cierre final
previsto: sin datos posteriores no se puede dar por terminado. Los saltos que omiten un
mes o año entero no se atribuyen al período de llegada.

**Ejemplo.** Si diciembre termina en fin de semana y el 31 es festivo, el último cierre puede
ser del 29. Sin tolerancia, diciembre aparecería como incompleto y se quedaría fuera de la
rentabilidad anual.

**Contraejemplo.** Si el historial acaba el 26 de noviembre, noviembre sigue siendo parcial,
aunque falten menos de cinco días para su cierre. No se usa para elegir el mejor o peor mes
completo.

### 49. `--plots-report` no descarga referencias

**Origen.** README («Gráficos e informes») y commit `ac0f47d`.

**Decisión.** `--plots-report` sin `--report` solo muestra los gráficos de la cartera. No
descarga inflación, tipos ni contexto de mercado, salvo el índice si se elige con
`--benchmark`. Hay una prueba que lo comprueba.

**Ejemplo.** Quien solo quiere ver rápidamente la evolución de su cartera no necesita la
clave de FRED ni esperar las descargas del VIX o el Brent.

## Funcionalidades

### 50. Cartera por número de acciones (`--shares`)

**Origen.** Commits `edbee1b` (modetpablo-dot, 3 de noviembre), `b15534c`, `a7cae73` y `e8e7845`.

**Decisión.**
- Se puede indicar cuántas acciones se tienen en lugar de pesos: `--shares AAPL:10 SPY:5`.
- Por defecto no hay rebalanceo: se mantienen las mismas acciones todo el período. Con
  `--rebalance monthly`, las acciones definen los pesos de la primera fecha y se vuelve a
  ellos cada mes.
- Se usa `Adj Close`, como en el resto de carteras, así que la rentabilidad incluye los
  dividendos. Aparte se muestra el valor de mercado (acciones × último cierre).
- Solo funciona con Yahoo, porque Alpha Vantage da cierres sin ajustar por *splits*. No se
  admite `--capital` ni cantidades de cero o negativas.

**Ejemplo.** Con 10 AAPL y 5 SPY, el valor de mercado es lo que mostraría un bróker hoy: 10 ×
precio de AAPL + 5 × precio de SPY. El valor de la cartera es algo mayor, porque suma los
dividendos cobrados y reinvertidos durante el período. Si hubiera un *split* 4 por 1 con
Alpha Vantage, las 10 acciones valdrían 4 veces más en las fechas anteriores y la
rentabilidad saldría mal; por eso se rechaza antes de descargar.

**Revisión de la PR #13 (S7).** La idea se aprobó y antes de integrarla se corrigieron siete
puntos. Los principales:
- **Acciones y valor coherentes.** Desde Python, pedir `Adj Close` en una cartera por
  acciones daba posiciones que no cuadraban: 10 acciones a 100 valían 1.111,11. No se
  prohibió `Adj Close`, porque cuatro pruebas de `from_units` lo usaban a propósito. La
  columna de acciones solo se muestra con `Close`, y con `Adj Close` el informe explica que los
  dividendos se reinvierten.
- **Modo explícito.** El informe ya no deduce si la cartera es por acciones porque exista una
  columna `shares`: lo indica `PortfolioAnalysis.units`.
- **Rechazos antes de descargar.** No se admiten cantidades de cero, y `--shares` con Alpha
  Vantage se detiene gracias a `ProviderOption.split_adjusted`.
- **Diagramas.** Las láminas 02 y 06 se actualizaron en un commit aparte, para que el
  manifiesto registre el commit exacto del código.

**Alternativa descartada (8 de noviembre): indicar la cartera por importes.** Se planteó una
tercera forma de definir la cartera, con el importe invertido en cada activo. Se descartó
porque equivale a pesos más capital: «6.000 € en SAN y 4.000 € en ITX» es
`--assets SAN.MC:0.6 ITX.MC:0.4 --capital 10000`. Añadiría opciones, validaciones y pruebas
sin dar ningún resultado nuevo, y podría confundir el importe invertido al principio con
el valor de hoy, que es lo que ya resuelve `--shares`. Tampoco se normalizan importes
escritos en `--assets`: los pesos deben sumar 1 a propósito, para que un error al
escribirlos no pase desapercibido (ver 13).

### 51. Caché de Yahoo por símbolo

**Origen.** Commit `95eb80e` (31 de octubre) y README («Comprobaciones»).

**Decisión.** La caché vive en `.cache/market-data`. Para cada símbolo guarda su ficha y un
único historial, y las respuestas de más de un día se borran solas. La clave nunca se guarda
en texto.

**Ejemplo.**
- Cambiar `--simulations` o `--seed` no descarga nada.
- Añadir MSFT a una cartera de IBM solo descarga MSFT.
- Pedir de junio a diciembre después de haber pedido el año completo reutiliza lo
  descargado.

**Origen y medida (S2).** La petición fue reutilizar los datos cuando solo cambian los
parámetros de la simulación o algunos activos. Yahoo, el proveedor por defecto, no guardaba
nada en disco: cada ejecución volvía a pedir precios y ficha de cada activo, del índice y de
cada tipo de cambio. Se contaron las peticiones con IBM y MSFT y el informe en euros:

| Ejecución | Antes | Después |
| --- | --- | --- |
| Primera | 8 | 7 |
| Mismos activos; cambian `--simulations` y `--steps` | 8 | 0 |
| MSFT se cambia por AAPL y se acorta `--start` | 6 | 2, solo de AAPL |

Dos reglas completan el diseño:
- **La sesión de hoy nunca se da por cerrada:** una petición que llega hasta hoy vuelve a
  descargar, porque el mercado puede seguir abierto.
- **Los tipos de cambio no piden la ficha** (`include_info=False`), que costaba una petición
  y no se usaba.

En FRED, la caché depende de las fechas pedidas, porque su límite de peticiones es amplio. Se
propuso una opción `--refresh` para forzar una descarga nueva y no se aplicó: hay que borrar
`.cache/market-data` o esperar un día.

### 52. Diez secciones que responden a una pregunta

**Origen.** README («Lectura y selección del informe») y commits `7888fe2` y `e8e7845`.

**Decisión.**
- El informe tiene 10 secciones, cada una en un desplegable que responde a una pregunta:
  «¿Cuánto ha ganado?», «¿Cuánto ha arriesgado?», «¿Cuánto fiarse de todo lo anterior?»…
- Se pueden elegir secciones (`--report-sections`) y el nivel de detalle (`--report-detail`).
- El texto no menciona columnas, variables ni funciones del código.
- El informe se prepara en una carpeta temporal y solo aparece cuando está completo.

**Ejemplo.** Un lector sin conocimientos de programación lee «se usan los precios ajustados
por dividendos» en lugar de «se usa `Adj Close`». Con `--report-sections summary warnings
risk` se obtiene un informe corto con el resumen, las advertencias y el riesgo, y cada
sección conserva su número.

### 53. Advertencias orientativas con umbrales configurables

**Origen.** README («Lectura y selección del informe») y `WarningThresholds` en
`src/analysis/warnings.py`.

**Decisión.** Las advertencias cubren la concentración, la correlación, las caídas, la
volatilidad, el VIX, el historial corto y otros riesgos. Sus umbrales están en
`WarningThresholds` y se pueden cambiar desde Python. Son orientativas, no recomendaciones de
inversión, y **un dato que falta nunca activa una regla**.

**Ejemplo.** Por defecto, un activo de más del 40 % de la cartera genera un aviso de
concentración. Con `WarningThresholds(asset_weight=0.45)` el umbral pasa al 45 %. Si no se ha
podido descargar el VIX, no aparece ningún aviso de VIX alto: falta el dato y el informe lo
dice en otra sección.

## Calidad, entorno y documentación

### 54. Límites de complejidad, cobertura mínima y CodeQL

**Origen.** Commits `973e5f7` (PR #16) y `dce38fa` (PR #21).

**Decisión.**
- **Ruff** limita en `src` la complejidad McCabe a 10, las ramas por función a 12 y las
  sentencias a 50. Los límites están en `pyproject.toml`, así que el editor aplica los mismos
  que CI. Las pruebas y el generador de diagramas quedan exentos.
- **La cobertura** combinada de líneas y ramas debe ser de al menos el 94 % sobre todo
  `src`. Si baja, CI falla.
- **CodeQL** analiza Python y los workflows. La regla `codeql-quality` de `main` bloquea las
  alertas nuevas de seguridad alta o crítica.

**Ejemplo.** Una función con 13 `if` encadenados no pasa Ruff y hay que dividirla. Así se
dividió, por ejemplo, `analyze_portfolio` (commit `b59f127`). Si alguien añade código sin
pruebas y la cobertura baja al 93 %, la PR no se puede integrar.

**Revisión de la PR #16 (S10).** Se comprobó que las cuatro funciones divididas se
comportaban igual, que la cobertura local (94,84 %) coincidía con CI y que las dos alertas
descartadas de CodeQL eran falsos positivos: una imprime el nombre de la variable, no la
clave, y la otra usa el SHA-256 de la clave como identificador, no para guardar contraseñas.
De la revisión salió la PR #21:
- Los límites de complejidad pasaron de una opción en la línea de órdenes de CI a la lista
  `select` de `pyproject.toml`. Así `ruff check .` y el editor avisan igual que CI.
- `_raise_http_error` se anota como `NoReturn`, porque siempre lanza un error.
- Se quitó el porcentaje fijo de cobertura del README y de `pyproject.toml`, que ya no
  coincidía con CI.

**Ejemplo.** Con `-> None`, quien lee `_download` puede pensar que, tras el error, el código
sigue hasta `response.json()` con una respuesta vacía. `NoReturn` deja claro que esa línea no
se alcanza.

### 55. Python 3.11 como versión mínima

**Origen.** Commit `95eb80e` (31 de octubre).

**Decisión.** `requires-python` pasa de `>=3.10` a `>=3.11`. CI prueba con la mínima (3.11) y
con la del equipo (3.14, la de `.python-version`). Ruff toma la versión objetivo de
`requires-python`.

**Ejemplo.** Si el proyecto declara 3.10 pero nadie lo prueba con esa versión, un alumno con
3.10 podría instalarlo y encontrarse un error. Declarar solo lo que CI comprueba evita esa
sorpresa.

**Origen (S1).** El 29 de octubre convivían tres versiones: CI probaba 3.10 y 3.14, y el
lint usaba 3.12 sin ningún motivo registrado. Se eligió 3.11 como mínima porque 3.10 llegaba
al final de su soporte ese mes y pandas 3 exige 3.11: el trabajo de 3.10 era el único que
probaba pandas 2, que nadie del equipo usaba. El lint lee `.python-version`, de modo que cada
versión sale de un único sitio.

### 56. Diagramas generados por script en cuatro formatos

**Origen.** `ARQUITECTURA.md` y `diagramas/README.md`.

**Decisión.** Las siete láminas de arquitectura las genera `diagramas/generar_diagramas.py`
en cuatro formatos:

| Formato | Uso |
| --- | --- |
| SVG | Lectura y ampliación |
| PNG | Diapositivas y documentos |
| Excalidraw | Edición visual |
| Mermaid | Edición como texto |

`verificacion.json` guarda los *hashes* e indica si el código de `src` coincidía con el
commit al generarlos.

**Ejemplo.** Si se cambia una clase del dominio, se regenera la lámina con el script en lugar
de editar a mano cuatro archivos. El manifiesto permite saber si un diagrama corresponde al
código actual o a uno anterior.

---

# Parte III · Detalles contrastados con las conversaciones disponibles

Estas entradas completan el registro con el razonamiento de C1 y su contraste con el
repositorio. La petición del usuario fue adaptar las mejoras respetando la arquitectura,
con código limpio y evitando errores y duplicidades. Se distingue lo aplicado de las
correcciones de explicación que siguen pendientes.

## Adaptación del informe

### 57. Adaptar las mejoras del informe sin duplicar motores

**Origen.** C1, petición de continuar tras la revisión; commit `e6b3373`.

**Contexto.** La guía de Carlos proponía medidas y gráficos, pero varios cálculos ya estaban
en `main`. Además, la guía describía interfaces que todavía no coincidían con su código.

**Decisión.** Reutilizar el análisis y la simulación existentes, y adaptar la presentación:
resumen seguido de advertencias, secciones seleccionables, detalle compacto o completo,
episodios de caída, tablas por mes y año y nuevos gráficos. No se creó un segundo motor
para calcular las mismas medidas. Los resultados se conservan en `PortfolioAnalysis` y
los textos y gráficos los consumen sin volver a descargar los datos.

**Por qué.** Dos implementaciones de Sharpe o de Monte Carlo podrían divergir aunque
intentaran responder a la misma pregunta. Separar los resultados de su presentación
permite corregir una fórmula una sola vez.

**Ejemplo.** Tras `analysis = portfolio.analyze()`, `analysis.markdown(detail="full")` y
`analysis.report(sections=["summary", "risk"])` presentan los mismos resultados. Elegir un
informe más corto no cambia la volatilidad ni lanza nuevas consultas a los proveedores.

**Estado.** Aplicada inicialmente el 30 de octubre. La posterior integración de Carlos
amplió el informe conservando la estructura común (decisión 33). Elegir secciones solo
cambia la presentación; si se excluye la simulación, `portfolio.report()` evita calcularla
salvo que se haya solicitado por separado.

## Interpretación del riesgo

### 58. Usar pesos actuales y distinguir concentración de independencia

**Origen.** Hallazgos de C1;
[`src/analysis/portfolio_analysis.py`](src/analysis/portfolio_analysis.py),
[`src/analysis/warnings.py`](src/analysis/warnings.py) y
[`tests/test_report_details.py`](tests/test_report_details.py).

**Contexto.** La revisión detectó que la rama de Carlos describía el riesgo actual con los
pesos iniciales. También interpretaba `1 / sum(pesos²)` como un número de apuestas
independientes, aunque esa fórmula no utiliza las correlaciones.

**Decisión.** Las exposiciones y los avisos de concentración se evalúan con los pesos
actuales. El HHI y su inverso describen el reparto de los pesos; para valorar la
diversificación se consultan además las correlaciones y las contribuciones al riesgo.
Los pesos objetivo se conservan para definir la estrategia de rebalanceo (ver 7).

**Por qué.** El riesgo actual depende de lo que pesa cada posición hoy. Contar nombres o
usar el reparto inicial puede ocultar una concentración que ha crecido con los precios.

**Ejemplo de pesos.** Una cartera empieza con 2.500 en A y 7.500 en B. Si A multiplica su
precio por cuatro y B no cambia, pasa a tener 10.000 en A y 7.500 en B: A pesa un 57,1 %,
no un 25 %. Un aviso con umbral del 55 % debe activarse.

**Ejemplo de interpretación.** Diez activos con un peso del 10 % tienen
`HHI = 10 × 0,1² = 0,1` y número efectivo 10. Si sus retornos son idénticos, esos diez
nombres no aportan diez riesgos independientes: se comportan igual.

**Estado.** Parcial. Los cálculos y avisos usan pesos actuales y hay pruebas que lo
comprueban. La corrección explicativa de C1 no está completamente aplicada:
`_diversification()` en `src/reporting/report.py` aún dice «apuestas distintas». Esa frase
no se debe interpretar como una propiedad demostrada por el HHI; queda pendiente ajustar
el texto del informe.

### 59. Explicar VaR, CVaR y bandas con sus unidades y horizonte

**Origen.** Correcciones metodológicas de C1;
[`src/analysis/metrics.py`](src/analysis/metrics.py) y
[`src/simulation/result.py`](src/simulation/result.py).

**Decisión.** Distinguir dos resultados que tienen nombres parecidos:
- El VaR histórico al 95 % es el percentil 5 de los retornos por período; el CVaR es la
  media de los retornos de esa cola. Se expresan como rentabilidad, habitualmente negativa.
- En Monte Carlo, el VaR al horizonte es `valor inicial − percentil 5 del valor final`;
  el CVaR resta al inicial la media del valor final de esa cola. Se expresan en dinero.
- La banda entre percentiles 5 y 95 contiene el 90 % central de los escenarios simulados.
  Un VaR al 95 % no significa que esa banda cubra el 95 %, ni que sea una pérdida máxima.

**Por qué.** Confundir porcentaje diario, dinero al horizonte y probabilidad del modelo
puede hacer que dos cifras correctas parezcan contradictorias. Ninguna elimina los
resultados peores que su umbral ni garantiza que el modelo describa el futuro.

**Ejemplo.** Con un valor inicial de 10.000 €, un percentil 5 final de 8.000 € y una media
de 7.000 € en esa cola, el VaR simulado es 2.000 € y el CVaR, 3.000 €. El modelo todavía
incluye resultados peores que perder 2.000 €. Si el percentil 95 es 14.000 €, el intervalo
8.000–14.000 € contiene el 90 % central de las simulaciones. Un VaR histórico diario del
−2 % responde a otra pregunta y no se compara directamente con esos 2.000 €.

**Estado.** Parcial. Las fórmulas y el porcentaje de la banda están implementados. El
informe todavía usa «con un 95 % de confianza no se perdería más de esto» para un VaR
positivo; la recomendación de C1 es explicitar que se trata de un percentil del modelo y
que la cola restante puede ser peor. La redacción queda pendiente.

### 60. Describir profundidad, duración y recuperación de las caídas

**Origen.** C1, implementación del commit `e6b3373` y `drawdown_episode()` en
[`src/analysis/metrics.py`](src/analysis/metrics.py).

**Decisión.** Además del porcentaje de caída máxima, conservar el pico anterior, el valle,
la primera recuperación y los días naturales desde el pico. Si el máximo se repite, se
elige el último anterior al valle. Si todavía no se ha recuperado, la duración llega al
final del historial. El capital inicial cuenta como posible máximo.

**Por qué.** Dos carteras pueden caer un 20 % y tener experiencias muy distintas si una
recupera en un mes y la otra sigue por debajo del máximo dos años después.

**Ejemplo.** Una cartera vale 10.000 el 1 de enero, 8.000 el 1 de febrero, 8.800 el 1 de
marzo y vuelve a 10.000 el 1 de abril de 2026. La caída es del 20 % y la duración desde el
pico hasta la recuperación es de 90 días. Omitir el capital inicial ocultaría la primera
caída al empezar la serie en 8.000. Si el historial terminara en marzo, la recuperación
figuraría como pendiente.

**Estado.** Vigente. Las historias planas o siempre crecientes no inventan un episodio:
devuelven profundidad y duración cero, sin fechas de pico, valle ni recuperación.

## Comparaciones y simulación

### 61. Comparar cartera e índice en la misma divisa y fechas

**Origen.** Hallazgo de C1 y pruebas de alineación;
[`src/analysis/portfolio_analysis.py`](src/analysis/portfolio_analysis.py) y
[`tests/test_analysis.py`](tests/test_analysis.py).

**Contexto.** En la versión revisada de Carlos, una cartera convertida a euros se comparaba
directamente con un índice en dólares. Una diferencia causada solo por el cambio parecía
una diferencia de rendimiento de la inversión.

**Decisión.** Convertir el índice a la divisa del informe y comparar entre las mismas
fechas. En el gráfico se normalizan ambos a base 100 para comparar evolución, no niveles
de precio. La selección del índice (45) y la alineación temporal del alfa (46) completan
este contrato.

**Por qué.** La divisa y el intervalo forman parte de la medida. Si difieren entre las
dos series, la comparación mezcla el rendimiento de los activos con efectos de cambio o
con movimientos de fechas que solo aparecen en una de ellas.

**Ejemplo.** Una acción y su índice no cambian de precio en USD. Si el cambio pasa de
1 USD por EUR a 1,2 USD por EUR, 100 USD pasan de valer 100 € a 83,33 €. La acción y el
índice pierden ambos un 16,67 % medidos en euros. Comparar la acción convertida con el
índice sin convertir produciría una falsa desventaja de 16,67 puntos.

**Estado.** Vigente. Si falta una referencia utilizable, se explica por qué la medida no
está disponible; no se sustituye la referencia por cero.

### 62. Proyectar las posiciones finales, conservando la estrategia

**Origen.** Diferencia entre ramas identificada en C1; README («Capital de referencia y
rebalanceo mensual»), `Portfolio.simulation_inputs()` y
[`src/simulation/monte_carlo.py`](src/simulation/monte_carlo.py).

**Decisión.** Monte Carlo parte del valor de cada posición en la última fecha histórica,
con la misma base de precios y divisa del análisis. Una cartera sin rebalanceo sigue sin
rebalancear; una mensual vuelve a sus pesos objetivo durante la simulación. El histórico
usa cierres de mes y la proyección los aproxima cada 21 sesiones, o cada 30 días cuando
se usan 365 períodos al año. No se generan calendarios futuros de festivos.

**Por qué.** La pregunta es qué podría pasar a partir de las posiciones valoradas al final
del análisis. Reiniciar el capital y los pesos iniciales respondería a la pregunta de
hacer una inversión nueva.

**Ejemplo.** Se empezó con 10.000 al 60/40, pero hoy las posiciones valen 10.500 y 4.500.
Todas las trayectorias arrancan de 15.000 con ese reparto. Sin rebalanceo, los pesos
pueden seguir separándose; con rebalanceo mensual, se aplica la regla de regreso al 60/40,
incluidas la banda y las comisiones si están configuradas.

**Estado.** Vigente. Al adjuntar una simulación a un informe se comprueba que coincidan
fecha, divisa, activos, valores de partida y criterios de cálculo. Dos carteras con el
mismo valor total pero distinta composición no son intercambiables.

## Verificación de casos límite

### 63. Cubrir precios planos, referencias ausentes y cambios de divisa

**Origen.** C1: las suites existentes pasaban, pero los casos sintéticos adicionales
descubrieron fallos. La adaptación añadió pruebas de regresión en el commit `e6b3373`.

**Decisión.** Probar ejemplos pequeños con resultado conocido, además de ejecutar las
suites existentes. Cubrir especialmente precios planos, ausencia de referencias, pesos
que cambian con el tiempo y alineación de divisas. Un cálculo indefinido aparece como
«No disponible», con su motivo cuando corresponde, sin producir infinitos ni impedir
generar el resto del informe.

**Por qué.** Que todas las pruebas pasen demuestra que se cumplen los casos cubiertos;
los fallos de la revisión mostraron que faltaban escenarios importantes.

**Ejemplo.** Dos activos con precios 100, 100, 100 tienen volatilidad y caída cero, pero
su correlación no se puede estimar porque no varían. El informe muestra «Par más
correlacionado: No disponible»; no busca el máximo de una lista vacía ni dice que su
correlación sea cero. Las ratios sin denominador válido tampoco se presentan como infinitas.

**Estado.** Vigente. Hay casos explícitos en
[`tests/test_report_details.py`](tests/test_report_details.py) y
[`tests/test_analysis.py`](tests/test_analysis.py). Los números de pruebas que constan en
C1 y C2 corresponden a aquellas sesiones, no certifican la suite actual.

---

# Parte IV · Decisiones de las sesiones de trabajo

Estas entradas recogen lo que se razonó y aplicó en las sesiones S1 a S10 y que no
tenía entrada propia. Cada una se ha contrastado con el código el 7 de noviembre de 2026.

## Simulación y proveedores

### 64. Un único Monte Carlo para activo y cartera

**Origen.** S1 (29 de octubre), commit `9bd3560`. Su forma cambió en `1c880e3` (ver 4).

**Contexto.** `Asset` y `Portfolio` tenían cada uno su propia simulación. La petición fue
reutilizar el código sin perder la posibilidad de simular un activo suelto o la cartera
entera.

**Decisión.** Un solo motor. Cada clase aporta únicamente lo que hay que simular:
- **el activo:** su historial, partiendo de su último precio;
- **la cartera:** los precios alineados, el valor actual de cada posición y, si rebalancea,
  los pesos objetivo.

Los nombres de los parámetros se igualaron: en `Asset`, `expected_return` y `volatility`
pasaron a ser `expected_returns` y `volatilities`, como en `Portfolio`.

**Por qué.** Dos copias del mismo modelo pueden separarse sin que nadie lo note. Ya había
una prueba que exigía que un activo y una cartera formada solo por ese activo dieran el mismo
resultado.

**Ejemplo.** Con la misma semilla, `ibm.monte_carlo(...)` y
`Portfolio([ibm], {"IBM": 1.0}).monte_carlo(...)` deben coincidir. Si alguien corrigiera la
fórmula de la deriva en uno solo de los dos sitios, la prueba lo detectaría.

**Estado.** El objetivo sigue vigente; la forma cambió al día siguiente. El primer diseño
usaba un *mixin* (`MonteCarloMixin`), que se sustituyó por `simulation_inputs()` y una
función `simulate()` (decisión 4).

### 65. Contrato común para los proveedores, con las opciones en el constructor

**Origen.** S1 (29 de octubre); `PriceProvider` en
[`src/providers/base.py`](src/providers/base.py).

**Contexto.** `portfolio_loader.py` comprobaba si el proveedor era `AlphaVantageAPI` para
llamarlo con otros argumentos. Además, el análisis leía
`info.get("currency") or info.get("Currency")`, porque cada API usaba sus propios nombres.

**Decisión.**
- Todos los proveedores se llaman igual: `get_prices(symbol, start, end)`. Lo documenta un
  `Protocol` de pocas líneas, `PriceProvider`.
- Las opciones propias de cada fuente (`outputsize`, `allow_partial`, `include_info`) se
  fijan al crear el adaptador.
- Cada adaptador traduce su ficha a unos campos comunes y conserva la respuesta original
  aparte. Esa ficha se convirtió después en `AssetProfile` (decisión 6).

**Por qué.** El enunciado valora poder añadir fuentes sin alterar el núcleo. Un `Protocol`
cuesta unas líneas y no obliga a heredar de ninguna clase.

**Ejemplo.** Antes, el cargador necesitaba una rama `if isinstance(...)` para pasar a Alpha
Vantage sus opciones. Ahora se crea `AlphaVantageAPI(outputsize="full")` una vez y el
cargador siempre hace `provider.get_prices(símbolo, inicio, fin)`. Un tercer proveedor no
añade ninguna rama al cargador.

**Estado.** Vigente. Se descartó una jerarquía de clases abstractas (ver 10).

## Datos y consola

### 66. Solo fechas ISO `AAAA-MM-DD`

**Origen.** S1 (29 de octubre); [`src/validation.py`](src/validation.py).

**Decisión.** Las fechas de entrada se validan una sola vez con el formato `AAAA-MM-DD`
(`datetime.strptime(..., "%Y-%m-%d")`). A partir de ahí se trabaja con fechas normalizadas.

**Por qué.** `date_range()` anunciaba ese formato, pero aceptaba otros, mientras que otras
funciones usaban `date.fromisoformat()`. La misma cadena podía valer en un sitio y fallar en
otro.

**Ejemplo.** `01/02/2025` puede ser el 1 de febrero o el 2 de enero según el país. Antes se
aceptaba sin avisar; ahora se rechaza y hay que escribir `2025-02-01`.

**Estado.** Vigente.

### 67. Un año de historial en Yahoo y 120 días en Alpha Vantage

**Origen.** S1 (29 de octubre); `ProviderOption.default_history_days` en
[`src/main.py`](src/main.py).

**Contexto.** Por defecto se pedían 30 días: unas 20 rentabilidades diarias, anualizadas
con 252 sesiones, alimentaban una simulación a un año.

**Decisión.** Si no se indica `--start`, se pide un año con Yahoo y 120 días naturales con
Alpha Vantage.

**Por qué 120 días.** El modo gratuito de Alpha Vantage (`compact`) devuelve unas 100
sesiones. 120 días naturales son unas 83 sesiones, así que caben sin pedir un período que el
proveedor no puede dar.

**Ejemplo.** Estimar la volatilidad anual con 20 días es como calcular la temperatura media
del año con tres semanas de enero. Con un año de datos entran períodos tranquilos y
agitados del mercado.

**Estado.** Vigente. El aviso de historial corto se mide en días naturales (ver 40), para que
un año con 249 sesiones comunes no cuente como «menos de un año». Desde la PR #26 (8 de
noviembre), este año solo es el período del informe: Monte Carlo estima la volatilidad y
las correlaciones con 5 años (ver 73).

## Informe y documentación

### 68. `.plots_report()` reúne todas las figuras

**Origen.** S1 (29 de octubre); `PortfolioAnalysis.plots_report()` en
[`src/analysis/result.py`](src/analysis/result.py) y `plot_report()` en
[`src/reporting/plots.py`](src/reporting/plots.py).

**Contexto.** El método que pide el enunciado solo devolvía la figura de análisis general.
La consola, en cambio, montaba por su cuenta otras figuras, como la comparación de activos.

**Decisión.** Una única función construye el conjunto de gráficos históricos.
`.plots_report()` lo devuelve como diccionario y puede guardarlo en una carpeta. La consola y
la exportación del informe usan esa misma función.

**Ejemplo.** Antes, `--plots-report` mostraba la comparación normalizada de activos y
`portfolio.plots_report()` no. Ahora las tres salidas comparten el código y no pueden
mostrar conjuntos distintos.

**Estado.** Vigente. El registro `CHARTS` (decisión 9) amplió después el conjunto de
gráficos.

### 69. Diagramas versionados y legibles con cualquier tema

**Origen.** S4, S5 y S6 (31 de octubre a 2 de noviembre); S8 y S9 (5 de noviembre).

**Contexto.** Los diagramas estaban en `docs/`, que `.gitignore` excluía, y citaban clases
ya eliminadas (`MarketContext`, `MonteCarloMixin`, `simulate_paths`). En GitHub no se veía
ninguno, y el apartado 4.6 del enunciado se evalúa.

**Decisión.**
- `ARQUITECTURA.md`, en la raíz, reúne las láminas con su explicación, y `diagramas/` deja de
  estar ignorada. Más tarde también se quitó `docs` del `.gitignore` (PR #14).
- Se corrigió el generador. Al comprobar si un texto cabía, contaba el espacio vacío bajo la
  última línea y fallaba por menos de un píxel, así que nunca había llegado a producir las
  imágenes.
- Los `.mmd` no fijan colores: usan el tema de quien los abre.
- Hay dos documentos con funciones distintas: `ARQUITECTURA.md`, con las siete láminas
  formales, y `docs/arquitectura.md`, un resumen en Mermaid para orientarse.

**Por qué no fijar colores.** Los `.mmd` imponían texto azul marino pensado para fondo claro.
Con el tema oscuro, las etiquetas de las flechas y los títulos de los grupos quedaban oscuros
sobre fondo oscuro.

**Ejemplo.** Una etiqueta azul marino se lee bien en el modo claro de GitHub, pero desaparece
en el oscuro. Sin colores fijos, el visor elige un contraste adecuado en ambos casos.
`diagramas/README.md` lo explica para que nadie vuelva a añadirlos.

**Estado.** Parcial. Las láminas reflejan `--shares`, pero ninguna muestra todavía el
proveedor del BCE (`EcbAPI`). La actualización de las láminas 01 a 06 está hecha en el commit
`b60421d`, en una rama local que no se ha subido ni integrado.

## Datos macroeconómicos

### 70. API oficial de FRED con clave, no la descarga CSV

**Origen.** S6 (2 de noviembre).

**Contexto.** Un compañero había obtenido datos de FRED sin clave, y surgió la duda de si
`FRED_API_KEY` era necesaria.

**Decisión.** Se mantiene la API oficial (`api.stlouisfed.org`), que exige una clave
gratuita. Si falta, el programa avisa y genera el informe sin las medidas que dependen de
FRED (decisión 16).

**Por qué.** Se probaron las dos vías. La API sin clave responde con un error HTTP 400 que
indica que falta `api_key`. La descarga CSV de la web (`fredgraph.csv`, el botón «Download»
de cada gráfica) no pide clave, pero:
- no está documentada como API y puede cambiar de formato sin aviso;
- no incluye metadatos de la serie ni errores estructurados;
- obligaría a escribir y probar otro lector para algo que ya funciona con una clave
  gratuita.

**Ejemplo.** `fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCSL` devuelve el IPC sin
clave, y probablemente es lo que usaba el compañero, directamente o a través de
`pandas_datareader`. Sirve para una consulta puntual. Pero si FRED cambiara una columna de
ese CSV, el programa fallaría sin un mensaje claro; la API devuelve un error con su causa.

**Estado.** Vigente.

## Instalación y código limpio

### 71. Inicio rápido por sistema y publicación del informe con reintentos

**Origen.** S8: revisión y mejora de la PR #14 (commits `51e18ee` y `9809e03`).

**Contexto.** Para instalar había que leer más de 650 líneas de README, y el único comando
para crear el entorno (`python -m venv .venv`) suele fallar en macOS y Linux. En Windows,
publicar el informe fallaba a veces con «Acceso denegado».

**Decisión.**
- El inicio rápido da el comando de cada sistema: `py -m venv .venv` en Windows y
  `python3 -m venv .venv` en macOS y Linux. Se siguió al pie de la letra desde un entorno
  limpio para comprobarlo.
- Al renombrar la carpeta temporal del informe, solo se reintenta ante un `PermissionError`:
  hasta 6 intentos, separados 0,5 segundos. Cualquier otro error falla en el acto, y se
  mantiene la limpieza de la carpeta a medias (decisión 15).
- Los avisos de obsolescencia de yfinance se silencian solo durante sus llamadas y solo los
  que proceden de sus módulos.

**Por qué.** El apartado 4.1 pide clonar y ejecutar sin fricciones. Además, el antivirus o el
indexador de Windows pueden tener abierto durante un instante un gráfico recién guardado, y
eso no es un error del programa.

**Ejemplo.** Si el antivirus bloquea la carpeta medio segundo, el segundo intento la publica
y el usuario no nota nada. Si el disco está lleno, el error aparece enseguida, porque no es un
`PermissionError` y no tiene sentido esperar.

**Límites.** `warnings.catch_warnings()` modifica un estado global y no es seguro entre
hilos. Hoy no importa, porque la descarga es secuencial (decisión 38). Con yfinance 1.8.0 y
pandas 3.1.1 no se reprodujeron esos avisos, así que el filtro es preventivo.

**Estado.** Vigente.

### 72. Simplificar sin cambiar el comportamiento

**Origen.** S4 (1 de noviembre), commit `2e9553c`.

**Contexto.** Tras integrar las mejoras de la revisión y `--benchmark`, algunas funciones
habían crecido y costaba recorrerlas en una presentación de cinco minutos.

**Decisión.** Recortar solo lo que no cambia el resultado, pasando las pruebas tras cada
bloque:
- `load_references` pasa las tres referencias de forma explícita y comparte la descarga de
  la inflación y el tipo de interés.
- `period_returns()` sustituye seis repeticiones de `pct_change(fill_method=None).dropna()`.
- `run()` solo coordina los pasos; qué referencias se descargan lo decide
  `load_run_references()`.
- La comprobación de que una simulación corresponde al informe se expresa con tres
  condiciones con nombre: `same_start`, `same_positions` y `same_criteria`.

Se dejaron largas a propósito `evaluate_risk`, porque cada regla de riesgo era un bloque
visible, y `build_parser`, que solo declara opciones de la consola.

**Por qué.** El objetivo era que cada función se leyera de arriba abajo, no reducir líneas:
en total salieron 21.

**Ejemplo.** Tras la simplificación, el flujo cabe en una frase que se puede seguir en el
código: la consola valida, los adaptadores descargan, los modelos validan y se congelan, el
análisis calcula y el informe presenta.

**Estado.** Modificada en parte. Los límites de complejidad de Ruff (decisión 54) obligaron
después a dividir `evaluate_risk` en funciones auxiliares, conservando el orden de sus
avisos.

---

# Parte V · Decisiones sobre Monte Carlo (7 y 8 de noviembre)

Estas entradas recogen la sesión de trabajo del 7 y 8 de noviembre de 2026 sobre la
simulación. Se han contrastado con el código fusionado en `main` (PR #26).

### 73. Estimar volatilidad y correlaciones con 5 años, aparte del período del informe

**Origen.** Commit `3afe24e`, fusionado en la PR #26 (8 de noviembre);
[`src/main.py`](src/main.py) (`_estimation_start` y `load_estimation_prices`) y
`Portfolio.monte_carlo(estimation_prices=...)`.

**Contexto.** El informe y Monte Carlo usaban el mismo período, un año por defecto con
Yahoo (ver 67). Un año sirve para contar cómo le ha ido a la cartera, pero no para estimar
su riesgo futuro: si ese año fue tranquilo, la volatilidad sale baja y el VaR parece seguro,
sin que el usuario lo note porque no ha elegido el período.

**Decisión.**
- El informe mantiene su período: `--start` a `--end`, un año por defecto.
- Monte Carlo estima la volatilidad y las correlaciones con los 5 años anteriores a `--end`
  o, si `--start` es anterior, desde `--start`: nunca con menos datos que el informe.
- `--estimation-start AAAA-MM-DD` elige el inicio a mano. Solo se admite si hay simulación.
- Con Alpha Vantage se sigue usando el período del informe, porque su modo gratuito no da
  5 años.
- Solo cambian σ y las correlaciones. La simulación sigue partiendo del valor actual de la
  cartera del informe, con sus pesos objetivo, comisiones y banda de rebalanceo. Con
  `--shares --rebalance monthly`, el objetivo son los pesos de las acciones al inicio del
  análisis, no al inicio de la estimación. El retorno no cambia: es el tipo libre de riesgo
  más la prima (ver 47).
- Si la estimación cubre menos de 3 años, por ejemplo por un activo reciente, la consola y
  el informe avisan.
- El informe muestra las fechas reales de la estimación y explica por qué la volatilidad
  de la simulación puede no coincidir con la del análisis. También describe la banda de
  rebalanceo en la cabecera y en Monte Carlo (ver 27).
- Desde Python, `monte_carlo()` no descarga nada: usa el período de la cartera salvo que
  se le pasen `estimation_prices`, con los mismos activos y la misma fecha final.

**Por qué 5 años.** Es la referencia habitual de fondos y analistas, incluye con más
probabilidad algún episodio de tensión y Yahoo los ofrece gratis. Un período más largo
tendría más riesgo de mezclar mercados que ya no se parecen al actual.

**Alternativas descartadas.**
- **Un solo período de 5 años para todo.** Era más sencillo, pero cambiaba el informe por
  defecto de «el último año» a «los últimos 5 años».
- **Mantener un año y solo avisar.** El aviso no corregía el problema para quien no toca
  las opciones.

**Ejemplo real** (SAN.MC e Inditex al 50 %, valoración del 6 de noviembre de 2026):

| Estimación | Volatilidad SAN | Volatilidad ITX | VaR 95 % a un año |
| --- | --- | --- | --- |
| Último año | 31,8 % | 25,5 % | 3.744 € |
| 5 años | 30,9 % | 25,0 % | 3.597 € |

Aquí la diferencia es pequeña porque el último año fue parecido a la media; lo importante
es que el resultado ya no depende de eso. Con un año más tranquilo, la volatilidad de un
año habría salido claramente por debajo.

**Estado.** Vigente.
