"""Textos de los avisos y de las medidas sin calcular, separados de los cálculos."""

NO_RISK_FREE_RATE = (
    "No se ha proporcionado un tipo de interés de referencia. No se calculan las ratios de "
    "Sharpe y Sortino ni se presupone un tipo del 0 %."
)
NO_RISK_FREE_RATE_NOTE = (
    "No se ha cargado un tipo de interés de referencia. Consulta las incidencias de descarga y "
    "la clave FRED_API_KEY, que también da acceso a ALFRED."
)
RATE_UNITS = (
    "El tipo de interés de referencia debe ser una tasa anual expresada en porcentaje. No se "
    "calculan las medidas de rentabilidad ajustada al riesgo."
)
RATE_UNITS_NOTE = "La serie de referencia debe expresar un tipo de interés anual en porcentaje."
RATE_STALE = (
    "No hay datos válidos y suficientemente recientes del tipo de interés para todo el período. "
    "Las medidas que dependen de él no se han podido calcular."
)
RATE_STALE_NOTE = (
    "Faltan datos válidos del tipo de interés para algunas fechas, o los disponibles son "
    "demasiado antiguos."
)
SHARPE_UNDEFINED = (
    "La diferencia de rentabilidad respecto a la referencia no varía durante el período. La "
    "ratio de Sharpe no puede calcularse porque su denominador es cero."
)
SORTINO_UNDEFINED = (
    "La rentabilidad no cae por debajo de la referencia en ningún período. La ratio de Sortino "
    "no puede calcularse porque su denominador es cero."
)

NO_INFLATION_NOTE = (
    "No se ha cargado un índice de precios de consumo. Consulta las incidencias de descarga y "
    "la clave FRED_API_KEY, que también da acceso a ALFRED."
)
INFLATION_UNITS = (
    "Para calcular la inflación se necesita un índice de precios de consumo, no una tasa de "
    "inflación expresada en porcentaje."
)
INFLATION_UNITS_NOTE = "La serie disponible no es un índice de precios de consumo."
INFLATION_STALE = (
    "No hay datos válidos y suficientemente recientes del índice de precios para todo el "
    "período. No se ha podido calcular la rentabilidad real."
)
INFLATION_STALE_NOTE = (
    "Faltan datos válidos del índice de precios para algunas fechas, o los disponibles son "
    "demasiado antiguos."
)

NO_BENCHMARK_NOTE = (
    "No se ha cargado un índice de referencia. Consulta las incidencias de descarga y las "
    "referencias configuradas para la divisa del informe."
)
BENCHMARK_CURRENCY = "No consta la divisa del índice de referencia. No se realiza la comparación."
BENCHMARK_CURRENCY_NOTE = "No consta la divisa del índice de referencia."
BENCHMARK_COVERAGE = (
    "No se realiza la comparación con el índice de referencia: comprueba la cobertura de "
    "fechas, los precios disponibles y los tipos de cambio."
)
BENCHMARK_COVERAGE_NOTE = (
    "Faltan precios comparables o tipos de cambio del índice para algunas fechas."
)
BENCHMARK_COMPARISON = (
    "Comparación con el índice basada en {dates} fechas comunes, con la misma divisa y columna "
    "de precios. Revisa si el índice incorpora dividendos."
)
BETA_UNDEFINED = (
    "La rentabilidad del índice de referencia no varía durante el período. No se puede "
    "calcular la beta porque la varianza del índice es cero."
)

ANNUALIZATION_GAP = (
    "Las fechas están separadas unos {gap:.0f} días, pero se anualiza con {periods} períodos "
    "por año. Indica periods_per_year según la frecuencia de los datos (por ejemplo, 12 si son "
    "mensuales)."
)
SHORT_HISTORY = (
    "El historial contiene menos de un año de datos. Las estimaciones anuales pueden variar "
    "mucho según el período elegido."
)
PARTIAL_HISTORY = "Al menos un proveedor ha devuelto solo una parte del historial solicitado."
UNADJUSTED_PRICES = (
    "{symbols}: los precios se utilizan sin ajustar. Un desdoblamiento puede producir un salto "
    "en los precios que distorsione las rentabilidades, la volatilidad y los parámetros de la "
    "simulación, por lo que los resultados pueden diferir de los obtenidos con cierres "
    "ajustados por desdoblamientos."
)
UNKNOWN_ADJUSTMENT = (
    "El proveedor no indica si algunos precios están ajustados. Conviene comprobar cómo se han "
    "tratado los dividendos y los desdoblamientos."
)
DROPPED_ROWS = "{symbol}: se han descartado {rows} fechas sin precio de cierre."
ECONOMIC_DATA_TIMING = (
    "Algunos datos económicos se sitúan en la fecha a la que corresponden, aunque se publicaran "
    "más tarde, y pueden incluir revisiones posteriores: el resultado puede usar información que "
    "entonces no se conocía (sesgo de anticipación)."
)
ECONOMIC_DATA_POINT_IN_TIME = (
    "Los datos económicos se usan tal como se publicaron: en cada fecha se toma el último dato "
    "conocido entonces, sin revisiones posteriores ni cifras aún no publicadas. Así se evita el "
    "sesgo de anticipación (look-ahead bias)."
)
