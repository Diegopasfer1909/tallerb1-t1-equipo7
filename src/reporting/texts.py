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
SHARES_NOTE = (
    "Cartera definida por número de acciones: el importe inicial es el valor de esas acciones en "
    "la primera fecha y los pesos iniciales resultan de él. Las cantidades no cambian (sin "
    "rebalanceo) y se valoran con el precio de cierre sin ajustar por dividendos, de modo que el "
    "valor de cada posición es su número de acciones por el precio; no se suman dividendos."
)
SHARES_ADJUSTED_NOTE = (
    "Cartera definida por número de acciones: el importe inicial es el valor de esas acciones en "
    "la primera fecha y los pesos iniciales resultan de él. Las cantidades no cambian (sin "
    "rebalanceo). Como en cualquier cartera, la rentabilidad incluye los dividendos. Valor de "
    "mercado de las acciones hoy (acciones × último cierre): {market}. El valor final del "
    "resumen, {value}, es mayor porque suma los dividendos."
)
SHARES_REBALANCED_NOTE = (
    "Cartera definida por número de acciones con rebalanceo mensual: el importe inicial es el "
    "valor de esas acciones en la primera fecha y los pesos objetivo resultan de él. Cada mes se "
    "vuelve a esos pesos, así que las cantidades cambian: la columna Acciones iniciales indica "
    "las de la primera fecha y el valor actual ya no es su número por el precio de cierre."
)
COSTS_NOTE = (
    "Los resultados no incluyen comisiones, impuestos ni aportaciones o retiradas de dinero, y "
    "se permite invertir en fracciones de cada activo: operar esta cartera rendiría menos."
)
COMMISSIONS_NOTE = (
    "Los resultados descuentan las comisiones de cada rebalanceo con la tarifa de {broker} "
    "({tariff}), pero no las de la compra inicial, los impuestos, el cambio de divisa ni "
    "aportaciones o retiradas de dinero, y se permite invertir en fracciones de cada activo. Los "
    "importes fijos de la tarifa se aplican en {currency}, la divisa de la cartera."
)
REBALANCE_COSTS_NOTE = (
    "Sin rebalanceo se mantienen las posiciones de la primera fecha y no se paga ninguna comisión "
    "después de la compra inicial, común a las dos estrategias. Rebalancear controla el riesgo: "
    "aunque rinda algo menos, puede compensar si mantiene la cartera cerca de sus pesos. Las "
    "tarifas son orientativas; comprueba la vigente en tu bróker y ajústala con "
    "`--broker` y `--commission-*`."
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
SHORT_RETURN_MEASURES_NOTE = (
    "**Por qué las medidas de rentabilidad pueden discrepar:** la rentabilidad del período es el "
    "crecimiento compuesto entre la primera y la última fecha. Las ratios de Sharpe y Sortino "
    "usan la media aritmética de las rentabilidades por período, que no es menor que el "
    "crecimiento compuesto equivalente: con +20 % y −19 %, la media es +0,5 %, pero el valor cae "
    "un 2,8 % (1,20 × 0,81 − 1). Por eso un Sharpe positivo puede convivir con una rentabilidad "
    "negativa en el período."
)
SHORT_HISTORY_RETURNS = (
    "**Menos de un año de historia:** las rentabilidades y sus diferencias se dan para el "
    "período completo, sin anualizar, porque anualizar unas semanas o meses las magnificaría. "
    "La volatilidad, las ratios de Sharpe y Sortino y el alfa siguen siendo anuales."
)

# Simulación
SIMULATION_NOT_CONFIGURED = (
    "> ⚠️ **No se ha configurado la simulación.** Para incluir esta sección, ejecuta el programa "
    "con `--simulate --report`."
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
    "python src/main.py {option} {assets} --simulate --simulations 50000 --steps 126 "
    "--estimation-start 2015-01-01 --equity-premium 0.04 --volatility 0.2 --confidence 0.99 "
    "--seed 7 --report"
)
SIMULATION_START_NOTE = (
    "La simulación parte del valor de la cartera en la última fecha del historial, no del "
    "capital inicial."
)
SIMULATION_LIMITATIONS = (
    "**Limitaciones:** los incrementos logarítmicos se suponen normales y μ y σ se mantienen "
    "constantes, por lo que el modelo puede subestimar las caídas extremas. No incluye "
    "aportaciones, retiradas ni impuestos, y solo descuenta las comisiones de los reajustes. "
    "Los escenarios no son una predicción."
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
SIMULATED_REBALANCE = (
    "Revisión cada {interval} sesiones simuladas; se vuelve a los pesos objetivo{condition}"
)
ESTIMATION_WINDOW_NOTE = (
    "**Volatilidad y correlaciones:** se estiman con los precios diarios del {start} al {end} "
    "(~{years} años), no con el período del análisis, para que no dependan de que ese período "
    "haya sido tranquilo o agitado. Por eso la volatilidad de la simulación puede no coincidir "
    "con la de las secciones anteriores. El inicio se cambia con `--estimation-start`."
)
SHORT_ESTIMATION_NOTE = (
    "> ⚠️ **Pocos datos para estimar.** La volatilidad y las correlaciones se han estimado con "
    "menos de {years} años de precios: pueden no ser representativas. Amplía el período con "
    "`--estimation-start` o indica la volatilidad con `--volatility`."
)
SIMULATED_BUY_AND_HOLD = "Sin rebalanceo"

# Calidad de los datos
# Explicación de la base de precios según la columna utilizada en el análisis.
PRICE_BASIS_NOTES = {
    "Close": (
        "La valoración usa el precio de cierre sin ajustar: la rentabilidad no incluye los "
        "dividendos ni otras distribuciones, porque no todos los activos publican precios "
        "ajustados."
    ),
    "Adj Close": (
        "El análisis usa precios ajustados por dividendos y otras distribuciones: los valores de "
        "la cartera estiman su crecimiento con reinversión y pueden diferir del valor de mercado "
        "de las posiciones."
    ),
}
NO_DATA_ISSUES = "**Incidencias de los datos:** ninguna."
SHORT_HISTORY_NOTE = " — menos de un año: métricas poco fiables."
UNADJUSTED_NOTE = (
    " Precios sin ajustar por dividendos: {symbols} (su rentabilidad está infravalorada)."
)
