"""Textos fijos del informe. Los que contienen llaves se completan con str.format()."""

# Resumen
BENCHMARK_COVERAGE = "Comparación con el índice {symbol}: {start} – {end}, {dates} fechas comunes."

# Advertencias
SECTOR_CONCENTRATION = "Concentración sectorial: {sector}."
NO_RISK_WARNINGS = "Ninguna advertencia salta con los umbrales actuales."

# Rentabilidad
NOMINAL_RETURNS_NOTE = (
    "Cifras nominales en {currency}: incluyen dividendos y no descuentan la inflación, salvo la "
    "rentabilidad real."
)

# Composición
DAILY_VALUES_NOTE = "Valores diarios: se entienden mejor anualizados en las secciones 4 y 5."
CONVERTED_PRICES_NOTE = "Precios convertidos a {currency}."
COSTS_NOTE = (
    "Los resultados no incluyen comisiones, impuestos ni aportaciones o retiradas de dinero, y "
    "se permite invertir en fracciones de cada activo: operar esta cartera rendiría menos."
)

# Rentabilidad ajustada al riesgo
RETURN_MEASURES_NOTE = (
    "**Por qué las medidas de rentabilidad pueden discrepar:** la rentabilidad anualizada es el "
    "crecimiento compuesto entre la primera y la última fecha, repartido por los días naturales "
    "transcurridos. Las ratios de Sharpe y Sortino usan la media aritmética de las rentabilidades "
    "por período, que no es menor que el crecimiento compuesto equivalente: con +20 % y −19 %, la "
    "media es +0,5 %, pero el valor cae un 2,8 % (1,20 × 0,81 − 1). Por eso un Sharpe positivo "
    "puede convivir con una rentabilidad anualizada negativa."
)

# Simulación
SIMULATION_NOT_CONFIGURED = (
    "> ⚠️ **No se ha configurado la simulación.** Para incluir esta sección, ejecuta el programa "
    "con `--simulate --report` o pasa el resultado de `portfolio.monte_carlo(...)` al informe."
)
SIMULATION_DEFAULT_CRITERIA = (
    "**Criterios:** esta simulación se ha ejecutado con los criterios por defecto: {criteria}. "
    "Si se desean otros, ejecuta `{command}`."
)
SIMULATION_CUSTOM_CRITERIA = (
    "**Criterios:** esta simulación se ha ejecutado con estos criterios: {criteria}. Para "
    "cambiarlos, ejecuta `{command}`."
)
SIMULATION_COMMAND = (
    "python src/main.py --assets {assets} --simulate --simulations 50000 --steps 126 "
    "--equity-premium 0.04 --volatility 0.2 --confidence 0.99 --seed 7 --report"
)
SIMULATION_START_NOTE = (
    "La simulación parte del valor de la cartera en la última fecha del historial, no del "
    "capital inicial."
)
SIMULATION_LIMITATIONS = (
    "**Limitaciones:** los incrementos logarítmicos se suponen normales y μ y σ se mantienen "
    "constantes, por lo que el modelo puede subestimar las caídas extremas. No incluye "
    "aportaciones, retiradas, comisiones ni impuestos. Los escenarios no son una predicción."
)
SENSITIVITY_NOTE = (
    "Todas las filas usan los mismos escenarios aleatorios, la misma volatilidad y las mismas "
    "correlaciones. La pérdida real es acabar con menos poder de compra: {inflation}."
)
REAL_LOSS_INFLATION = "se supone una inflación anual del {inflation}"
NO_REAL_LOSS_INFLATION = "no se calcula porque falta la inflación interanual"
MODEL_RETURN_NOTE = (
    "**Retorno:** tipo libre de riesgo actual más la prima por la parte en renta variable. La renta "
    "fija, el oro y lo que no se puede clasificar reciben solo el tipo libre de riesgo. No se usa "
    "el histórico porque refleja lo que ya ocurrió: con pocos años de datos es muy impreciso y "
    "depende de la fecha de inicio. La prima es un supuesto, no una previsión; se cambia con "
    "`--equity-premium`, y el retorno, con `--return`, también por activo."
)
UNCLASSIFIED_NOTE = (
    "No se ha podido clasificar {symbols}: reciben solo el tipo libre de riesgo. Si no es "
    "adecuado, indica su retorno con `--return`."
)
HISTORICAL_RETURN_NOTE = (
    "**Retorno:** histórico, porque no hay tipo libre de riesgo para esta divisa o no se ha podido "
    "descargar. Suele ser optimista: refleja lo que ya ocurrió, es muy impreciso con pocos años de "
    "datos y depende de la fecha de inicio. Se puede indicar con `--return`."
)
NOMINAL_SIMULATION_NOTE = (
    "Importes nominales en {currency}: incluyen dividendos y no descuentan la inflación."
)
SIMULATED_REBALANCE = "Mensual, a los pesos objetivo cada {interval} sesiones simuladas"
SIMULATED_BUY_AND_HOLD = "Sin rebalanceo"

# Calidad de los datos
# Explicación de la base de precios según la columna utilizada en el análisis.
PRICE_BASIS_NOTES = {
    "Close": (
        "La valoración usa Close. Adj Close incorpora además dividendos y otras distribuciones. "
        "Tener Adj Close disponible no significa que se haya usado en este análisis."
    ),
    "Adj Close": (
        "El análisis usa Adj Close, que incorpora dividendos y otras distribuciones: los valores "
        "de la cartera estiman su crecimiento con reinversión y pueden diferir del valor de "
        "mercado de las posiciones."
    ),
}
NO_DATA_ISSUES = "**Incidencias de los datos:** ninguna."
SHORT_HISTORY_NOTE = " — menos de un año: métricas poco fiables."
UNADJUSTED_NOTE = (
    " Precios sin ajustar por dividendos: {symbols} (su rentabilidad está infravalorada)."
)
