"""Textos fijos del informe. Los que contienen llaves se completan con str.format()."""

# Resumen
SUMMARY_CAPITAL = (
    "Cartera hipotética con un capital inicial de {capital} {currency}. Rentabilidad acumulada: "
    "{total_return}. El valor mostrado corresponde a la última fecha común y no representa el "
    "saldo real de una cuenta."
)
BENCHMARK_COVERAGE = "Comparación con el índice {symbol}: {start} – {end}, {dates} fechas comunes."
NO_BENCHMARK_COVERAGE = "Comparación con el índice no disponible; consulta las advertencias."

# Advertencias
SECTOR_CONCENTRATION = "Concentración sectorial: {sector}."
NO_RISK_WARNINGS = "No se superan los umbrales de riesgo configurados."
THRESHOLDS_NOTE = (
    "Los umbrales son orientativos. La ausencia de avisos no implica ausencia de riesgo."
)

# Composición
COMPOSITION_NOTE = (
    "Precios e importes expresados en {currency}. Los pesos objetivo son los indicados al "
    "definir la cartera; los pesos actuales reflejan su evolución hasta la última fecha."
)
MONTHLY_REBALANCE = (
    "La cartera vuelve a los pesos objetivo al cierre de cada mes, usando la última fecha "
    "disponible. Durante el mes los pesos pueden variar. Se permite invertir en fracciones de "
    "cada activo y no se incluyen costes de compraventa."
)
BUY_AND_HOLD = "La cartera mantiene las posiciones iniciales sin rebalanceo."

# Resultados históricos
PERFORMANCE_NOTE = (
    "Las diferencias de rentabilidad se expresan en puntos porcentuales (p. p.). Para comparar "
    "la cartera con el índice se utilizan las fechas en las que hay datos de ambos. La "
    "rentabilidad del tipo de interés de referencia se aproxima mediante capitalización; no "
    "representa la rentabilidad real de invertir en un bono."
)
RETURN_MEASURES_NOTE = (
    "**Por qué las medidas de rentabilidad pueden discrepar:** la rentabilidad anualizada es el "
    "crecimiento compuesto entre la primera y la última fecha, repartido por los días naturales "
    "transcurridos. Las ratios de Sharpe y Sortino y la μ histórica usan la media aritmética de "
    "las rentabilidades por período, que no es menor que el crecimiento compuesto equivalente: "
    "con +20 % y −19 %, la media es +0,5 %, pero el valor cae un 2,8 % (1,20 × 0,81 − 1). Por "
    "eso un Sharpe positivo puede convivir con una rentabilidad anualizada negativa. En Monte "
    "Carlo, μ es además la deriva del GBM, no el crecimiento esperado exacto."
)
ESTIMATES_NOTE = (
    "Las estimaciones históricas utilizan la media de las rentabilidades simples por período "
    "multiplicada por los períodos anuales para μ, y su desviación típica multiplicada por la "
    "raíz de los períodos anuales para σ. Los supuestos personalizados se muestran en la sección "
    "de Monte Carlo y no modifican los resultados históricos. No son previsiones publicadas por "
    "las empresas."
)
NO_DRAWDOWN = "No se observaron caídas desde máximos en el período analizado."
DRAWDOWN_DURATION = (
    "La duración corresponde a la mayor caída; si no se recuperó, se cuenta hasta el final del "
    "historial."
)
NO_COMPLETE_MONTHS = "No hay meses completos con los que identificar el mejor y el peor mes."
CALENDAR_NOTE = (
    "Las rentabilidades parciales no se anualizan ni participan en la selección del mejor/peor "
    "mes. La cobertura comprueba el cierre previo y el final del período con un calendario "
    "lunes-viernes; no certifica los festivos de cada bolsa ni la ausencia de huecos internos. "
    "Los intervalos que saltan un mes/año entero quedan sin atribuir a un único mes/año."
)
FUNDAMENTALS_NOTE = (
    "La beta publicada es la que facilita el proveedor. La beta calculada utiliza el índice de "
    "referencia y el período de este informe, por lo que ambas pueden diferir. El PER relaciona "
    "el precio de la acción con el beneficio por acción. Los datos de la ficha corresponden a la "
    "consulta realizada, no a cada fecha del historial. La capitalización bursátil se muestra en "
    "la divisa de cotización original."
)

# Diversificación
RISK_CONTRIBUTION_NOTE = (
    "La contribución al riesgo se calcula con los pesos actuales y la covarianza histórica de "
    "las rentabilidades. Puede ser negativa si un activo compensa parte de las fluctuaciones de "
    "los demás."
)
CONCENTRATION_NOTE = (
    "HHI y número efectivo de activos miden concentración de pesos; no cuentan apuestas "
    "independientes."
)
DISTRIBUTION_NOTE = (
    "La comparación con una distribución normal utiliza incrementos logarítmicos históricos. "
    "Con pocos datos, las diferencias en las colas son poco concluyentes."
)

# Simulación
SIMULATION_HEADER = (
    "**{simulations} escenarios** · Horizonte: **{steps} períodos** · Divisa: **{currency}**."
)
SIMULATION_SETTINGS = (
    "Fecha de valoración inicial: {date}. Cálculos anuales basados en {periods_per_year} "
    "períodos por año. Semilla aleatoria: {seed} (permite reproducir la simulación cuando se "
    "fija un valor)."
)
SIMULATED_REBALANCE = (
    "Rebalanceo mensual a los pesos objetivo cada {interval} sesiones simuladas. Es una "
    "aproximación por sesiones, no por meses de calendario."
)
SIMULATED_BUY_AND_HOLD = "Las posiciones evolucionan sin rebalanceo durante la simulación."
CONFIDENCE_NOTE = (
    "Los percentiles {lower:g} y {upper:g} delimitan el {central:g} % central de los valores "
    "finales. La confianza se utiliza para medir la cola de pérdidas del VaR y del CVaR, no "
    "como probabilidad de que el valor real quede en ese intervalo."
)
MODEL_NOTE = (
    "**Modelo:** movimiento browniano geométrico por activos. Método de correlación: {method}. "
    "Se mantienen las correlaciones históricas al cambiar la volatilidad. μ es la deriva anual "
    "del GBM: con μ = 0,08, el crecimiento esperado a un año es exp(0,08) − 1, aproximadamente "
    "un 8,33 %, no un 8 % exacto."
)
SIMULATION_LIMITATIONS = (
    "**Limitaciones:** los incrementos logarítmicos se suponen normales y μ y σ se mantienen "
    "constantes. El modelo puede subestimar las caídas extremas. No incluye aportaciones, "
    "retiradas, comisiones ni impuestos. El VaR y el CVaR son pérdidas respecto al valor inicial "
    "de la simulación; pueden ser negativos si la cola considerada todavía presenta ganancias. "
    "Los escenarios no son una predicción."
)

# Datos y referencias
# Explicación de la base de precios según la columna utilizada en el análisis.
PRICE_BASIS_NOTES = {
    "Close": (
        "La valoración usa Close. Adj Close incorpora además dividendos y otras distribuciones; "
        "la columna «Ajuste de los precios» indica cómo ajusta cada proveedor sus cierres. Tener "
        "Adj Close disponible no significa que se haya usado en este análisis."
    ),
    "Adj Close": (
        "El análisis usa Adj Close, que incorpora dividendos y otras distribuciones: los valores "
        "de la cartera estiman su crecimiento con reinversión y pueden diferir del valor de "
        "mercado de las posiciones. La columna «Ajuste de los precios» indica cómo ajusta cada "
        "proveedor sus cierres."
    ),
}
CONFIGURATION = (
    "**Configuración utilizada:** las rentabilidades se calculan con los precios de la columna "
    "{price_column}, tomando {periods_per_year} períodos por año. La información de los activos "
    "y las referencias económicas se consultan automáticamente. Si se ha realizado una "
    "simulación, sus parámetros se detallan en la sección correspondiente."
)
CALCULATION_CRITERIA = (
    "**Criterios de cálculo:** solo se utilizan fechas con precios para todos los activos. Para "
    "convertir divisas puede utilizarse el último tipo de cambio disponible, siempre que no "
    "supere el límite de antigüedad indicado. Las rentabilidades calculadas con Close no "
    "incluyen dividendos. Con Adj Close se estima el crecimiento con reinversión de las "
    "distribuciones, que puede diferir del valor de las posiciones. Los cálculos no incluyen "
    "comisiones, impuestos, aportaciones ni retiradas de dinero."
)
GLOSSARY = "\n".join(
    [
        "- **Rentabilidad anualizada:** rentabilidad anual equivalente al crecimiento del "
        "período analizado, según los días naturales transcurridos (365,25 por año); no depende "
        "del número de observaciones.",
        "- **Rentabilidad real:** rentabilidad después de descontar la inflación.",
        "- **Volatilidad:** mide cuánto fluctúan las rentabilidades; no indica cuánto se puede "
        "llegar a perder.",
        "- **Caída máxima:** mayor descenso respecto a un máximo anterior durante el período "
        "analizado.",
        "- **Sharpe y Sortino:** relacionan la rentabilidad por encima de la referencia con el "
        "riesgo asumido.",
        "- **Percentil 5 y media de los peores resultados:** muestran el umbral de las "
        "rentabilidades más bajas y la media de las que quedan en ese umbral o por debajo de él. "
        "Se calculan por período de observación.",
        "- **HHI y número efectivo de activos:** indican cómo se reparte el valor de la cartera "
        "entre sus posiciones; no tienen en cuenta las correlaciones.",
    ]
)
