"""Informes en español a partir de los resultados del análisis, sin descargas."""

from datetime import datetime

import pandas as pd

from .formatting import format_number

ASSET_TYPES = {
    "stock": "Acción",
    "fund": "Fondo de inversión",
    "etf": "Fondo cotizado (ETF)",
    "index": "Índice",
    "unknown": "No disponible",
}
SECTORS = {
    "Technology": "Tecnología",
    "Financial Services": "Servicios financieros",
    "Financials": "Finanzas",
    "Healthcare": "Salud",
    "Health Care": "Salud",
    "Consumer Cyclical": "Consumo cíclico",
    "Consumer Defensive": "Consumo defensivo",
    "Consumer Discretionary": "Consumo discrecional",
    "Consumer Staples": "Productos de primera necesidad",
    "Communication Services": "Servicios de comunicación",
    "Industrials": "Industria",
    "Energy": "Energía",
    "Utilities": "Servicios públicos",
    "Real Estate": "Sector inmobiliario",
    "Basic Materials": "Materias primas",
    "Materials": "Materiales",
    "Unknown": "No disponible",
}
COUNTRIES = {
    "United States": "Estados Unidos",
    "USA": "Estados Unidos",
    "Spain": "España",
    "United Kingdom": "Reino Unido",
    "Germany": "Alemania",
    "France": "Francia",
    "Italy": "Italia",
    "Portugal": "Portugal",
    "Netherlands": "Países Bajos",
    "Switzerland": "Suiza",
    "Japan": "Japón",
    "China": "China",
    "Canada": "Canadá",
    "Australia": "Australia",
    "Ireland": "Irlanda",
    "Unknown": "No disponible",
}
SOURCES = {"yahoo": "Yahoo Finance", "alpha_vantage": "Alpha Vantage", "fred": "FRED"}


def _table(headers, rows) -> str:
    def cell(value):
        return str(value).replace("|", "\\|").replace("\n", " ")

    lines = ["| " + " | ".join(map(cell, headers)) + " |"]
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    lines.extend("| " + " | ".join(map(cell, row)) + " |" for row in rows)
    return "\n".join(lines)


def _asset_information(analysis) -> str:
    profiles = []
    for symbol, asset in analysis.asset_details.iterrows():
        kind = ASSET_TYPES.get(asset["asset_type"], asset["asset_type"])
        sector = SECTORS.get(asset["sector"], asset["sector"])
        country = COUNTRIES.get(asset["country"], asset["country"])
        source = SOURCES.get(asset["source"], asset["source"])
        profiles.append(
            f"**{symbol} · {asset['name']}**  \n"
            f"{kind} · {sector} · {country} · Cotización en {asset['quote_currency']} · Fuente: {source}."
        )
    return "\n\n".join(profiles)


def _holdings(analysis) -> str:
    return _table(
        ["Activo", "Peso objetivo", "Precio de cierre", "Valor hipotético", "Peso actual"],
        [
            [
                symbol,
                format_number(row["target_weight"], True),
                format_number(row["price"]),
                format_number(row["value"]),
                format_number(row["weight"], True),
            ]
            for symbol, row in analysis.holdings.iterrows()
        ],
    )


def _asset_performance(analysis) -> str:
    keys = ["total_return", "annualized_return", "annualized_volatility", "max_drawdown"]
    return _table(
        [
            "Activo",
            "Rentabilidad total",
            "Rentabilidad anualizada",
            "Volatilidad anual",
            "Caída máxima",
        ],
        [
            [symbol, *[format_number(row[key], True) for key in keys]]
            for symbol, row in analysis.asset_details.iterrows()
        ],
    )


def _asset_fundamentals(analysis) -> str:
    rows = []
    for symbol, asset in analysis.asset_details.iterrows():
        capital = (
            "No aplicable" if asset["asset_type"] == "index" else format_number(asset["market_cap"])
        )
        if pd.notna(asset["market_cap"]) and asset["asset_type"] != "index":
            capital += f" {asset['quote_currency']}"
        pe = "No aplicable" if asset["asset_type"] == "index" else format_number(asset["pe_ratio"])
        rows.append(
            [
                symbol,
                format_number(asset["reported_beta"]),
                format_number(asset["calculated_beta"]),
                capital,
                pe,
            ]
        )
    return _table(
        ["Activo", "Beta publicada", "Beta calculada", "Capitalización bursátil", "PER publicado"],
        rows,
    )


def _estimated_parameters(analysis) -> str:
    return _table(
        ["Activo", "Retorno anual μ (histórico)", "Volatilidad anual σ (histórica)"],
        [
            [
                symbol,
                format_number(row["expected_annual_return"], True),
                format_number(row["expected_annual_volatility"], True),
            ]
            for symbol, row in analysis.asset_details.iterrows()
        ],
    )


def _portfolio_metrics(analysis) -> str:
    definitions = [
        ("annualized_return", "Rentabilidad anualizada", "%"),
        ("real_annualized_return", "Rentabilidad real anualizada", "%"),
        ("annualized_volatility", "Volatilidad anual", "%"),
        (
            "comparison_portfolio_annualized_return",
            "Cartera: rentabilidad anualizada en las fechas comunes",
            "%",
        ),
        (
            "benchmark_annualized_return",
            "Índice: rentabilidad anualizada en las fechas comunes",
            "%",
        ),
        ("difference_from_benchmark", "Diferencia frente al índice", "pp"),
        ("beta", "Beta calculada de la cartera", ""),
        ("reference_annualized_return", "Rentabilidad equivalente del tipo de referencia", "%"),
        ("excess_annualized_return", "Diferencia frente al tipo de referencia", "pp"),
        ("sharpe", "Ratio de Sharpe", ""),
        ("sortino", "Ratio de Sortino", ""),
        ("annualized_inflation", "Inflación anualizada", "%"),
        ("period_var_95_return", "Rentabilidad en el percentil 5", "%"),
        ("period_cvar_95_return", "Rentabilidad media de los peores resultados", "%"),
        ("concentration_hhi", "Índice de concentración (HHI)", ""),
        ("effective_asset_count", "Número efectivo de activos", ""),
    ]
    rows, missing = [], []
    for key, label, unit in definitions:
        value = analysis.metrics[key]
        formatted = format_number(value, unit == "%")
        if unit == "pp" and pd.notna(value):
            formatted = format_number(value * 100) + " p. p."
        if pd.isna(value):
            reason = analysis.metric_notes.get(
                key, "No hay datos suficientes para calcular esta medida."
            )
            missing.append("- Motivo: " + reason)
        rows.append([label, formatted])
    sections = [_table(["Medida", "Resultado"], rows)]
    if missing:
        sections.append(
            "**Medidas que no se han podido calcular**\n\n" + "\n".join(dict.fromkeys(missing))
        )
    return "\n\n".join(sections)


def _quality(analysis) -> str:
    basis = {
        "unadjusted": "Sin ajustar, según el proveedor",
        "split_adjusted": "Yahoo: ajustado por desdoblamientos; sin ajuste por dividendos",
        "adjusted": "Ajustado por desdoblamientos y distribuciones",
        "unknown": "No consta",
        "adjusted growth proxy": "Crecimiento con cierre ajustado por desdoblamientos y distribuciones",
    }
    coverage = _table(
        ["Activo", "Datos disponibles", "Datos utilizados", "Datos excluidos", "Historial parcial"],
        [
            [
                symbol,
                row["observations"],
                row["common_observations"],
                row["excluded_observations"],
                "Sí" if row["partial_history"] else "No",
            ]
            for symbol, row in analysis.data_quality.iterrows()
        ],
    )
    prices = _table(
        ["Activo", "Columna utilizada", "Ajuste de los precios", "Adj Close disponible"],
        [
            [
                symbol,
                row["price_column"],
                basis.get(row["price_basis"], "No consta"),
                "Sí" if row["adjusted_close_available"] else "No",
            ]
            for symbol, row in analysis.data_quality.iterrows()
        ],
    )
    sections = [
        coverage,
        "### Precios utilizados",
        prices,
        "La valoración usa Close. En Yahoo, Close se ajusta por desdoblamientos; Adj Close incorpora "
        "además dividendos y otras distribuciones. Los precios diarios de Alpha Vantage se reciben sin ajustar. "
        "Tener Adj Close disponible no significa que se haya usado en este análisis.",
    ]
    for symbol, row in analysis.data_quality.iterrows():
        if row["missing_optional_cells"]:
            sections.append(
                f"- {symbol}: {row['missing_optional_cells']} datos ausentes en columnas opcionales."
            )
        if row["filled_asset_prices"]:
            sections.append(f"- {symbol}: {row['filled_asset_prices']} precios completados.")
    return "\n\n".join(sections)


def _simulation_summary(simulation) -> str:
    summary = simulation.summary()
    lower_percentile = 100 * (1 - simulation.confidence)
    upper_percentile = 100 * simulation.confidence
    rows = [
        ["Valor inicial", format_number(summary["initial_value"])],
        ["Valor final medio", format_number(summary["mean_final_value"])],
        ["Mediana del valor final", format_number(summary["median_final_value"])],
        [
            f"Percentil {lower_percentile:g} del valor final",
            format_number(summary["lower_percentile"]),
        ],
        [
            f"Percentil {upper_percentile:g} del valor final",
            format_number(summary["upper_percentile"]),
        ],
        ["Rentabilidad media simulada", format_number(summary["mean_return"], True)],
        ["Probabilidad estimada de pérdida", format_number(summary["probability_of_loss"], True)],
        [
            f"VaR al {simulation.confidence * 100:g} % al final del horizonte",
            format_number(summary["value_at_risk"]),
        ],
        [
            f"CVaR al {simulation.confidence * 100:g} % al final del horizonte",
            format_number(summary["conditional_value_at_risk"]),
        ],
    ]
    assumptions = _table(
        ["Activo", "Retorno anual μ", "Origen de μ", "Volatilidad anual σ", "Origen de σ"],
        [
            [
                symbol,
                format_number(row["annual_return"], True),
                row["return_source"],
                format_number(row["annual_volatility"], True),
                row["volatility_source"],
            ]
            for symbol, row in simulation.assumptions.iterrows()
        ],
    )
    seed = simulation.seed if simulation.seed is not None else "sin fijar"
    return "\n\n".join(
        [
            f"**{len(simulation.paths.columns)} escenarios** · Horizonte: **{len(simulation.paths) - 1} períodos** · Divisa: **{simulation.currency}**.",
            _table(["Resultado", "Importe o porcentaje"], rows),
            "### Supuestos de la simulación",
            assumptions,
            f"Fecha de valoración inicial: {simulation.valuation_date:%d/%m/%Y}. "
            f"Cálculos anuales basados en {simulation.periods_per_year} períodos por año. "
            f"Semilla aleatoria: {seed} (permite reproducir la simulación cuando se fija un valor).",
            f"Rebalanceo mensual a los pesos objetivo cada {simulation.periods_per_year // 12} sesiones "
            "simuladas. Es una aproximación por sesiones, no por meses de calendario."
            if simulation.rebalance == "monthly"
            else "Las posiciones evolucionan sin rebalanceo durante la simulación.",
            f"Los percentiles {lower_percentile:g} y {upper_percentile:g} delimitan el "
            f"{(2 * simulation.confidence - 1) * 100:g} % central de los valores finales. "
            "La confianza se utiliza para medir la cola de pérdidas del VaR y del CVaR, "
            "no como probabilidad de que el valor real quede en ese intervalo.",
            f"**Modelo:** movimiento browniano geométrico por activos. Método de correlación: {simulation.correlation_method}. "
            "Se mantienen las correlaciones históricas al cambiar la volatilidad. "
            "μ es la deriva anual del GBM: con μ = 0,08, el crecimiento esperado a un año es exp(0,08) − 1, "
            "aproximadamente un 8,33 %, no un 8 % exacto.",
            "**Limitaciones:** los incrementos logarítmicos se suponen normales y μ y σ se mantienen constantes. "
            "El modelo puede subestimar las caídas extremas. No incluye aportaciones, retiradas, comisiones ni impuestos. "
            "El VaR y el CVaR son pérdidas respecto al valor inicial de la simulación; pueden ser negativos si la cola "
            "considerada todavía presenta ganancias. Los escenarios no son una predicción.",
        ]
    )


def build_report(
    analysis,
    generated_on: datetime | None = None,
    charts: dict[str, str] | None = None,
    simulation=None,
) -> str:
    generated_on = generated_on or datetime.now().astimezone()
    charts = charts or {}
    metrics = analysis.metrics
    total = analysis.holdings["value"].sum()
    sections = [
        "# Informe de cartera",
        f"**Período:** {analysis.values.index[0]:%d/%m/%Y} — {analysis.values.index[-1]:%d/%m/%Y} · "
        f"**Divisa:** {analysis.currency}  \n"
        f"*Elaborado el {generated_on:%d/%m/%Y a las %H:%M:%S %z}*",
        "## 1. Resumen",
        _table(
            [
                f"Valor de la cartera hipotética ({analysis.currency})",
                "Rentabilidad acumulada",
                "Caída máxima",
            ],
            [
                [
                    format_number(total),
                    format_number(metrics["total_return"], True),
                    format_number(metrics["max_drawdown"], True),
                ]
            ],
        ),
        f"Cartera hipotética con un capital inicial de {format_number(analysis.initial_capital)} "
        f"{analysis.currency}, repartido según los pesos objetivo en la primera fecha común. "
        "El valor mostrado corresponde a la última fecha con precios para todos los activos. "
        "No representa el saldo real de una cuenta de inversión.",
        "## 2. Composición de la cartera",
        _holdings(analysis),
        f"Precios e importes expresados en {analysis.currency}. Los pesos objetivo son los indicados "
        "al definir la cartera; los pesos actuales reflejan su evolución hasta la última fecha.",
        "La cartera vuelve a los pesos objetivo al cierre de cada mes, usando la última fecha "
        "disponible. Durante el mes los pesos pueden variar. Se permite invertir en fracciones de "
        "cada activo y no se incluyen costes de compraventa."
        if analysis.rebalance == "monthly"
        else "La cartera mantiene las posiciones iniciales sin rebalanceo.",
        "### Información de los activos seleccionados",
        _asset_information(analysis),
        "## 3. Resultados históricos",
        _portfolio_metrics(analysis),
        "Las diferencias de rentabilidad se expresan en puntos porcentuales (p. p.). Para comparar la "
        "cartera con el índice se utilizan las fechas en las que hay datos de ambos. La rentabilidad "
        "del tipo de interés de referencia se aproxima mediante capitalización; no representa "
        "la rentabilidad real de invertir en un bono.",
        "### Análisis de cada activo",
        _asset_performance(analysis),
        "### Estimaciones a partir del historial",
        _estimated_parameters(analysis),
        "Las estimaciones históricas utilizan la media de las rentabilidades simples por período "
        "multiplicada por los períodos anuales para μ, y su desviación típica multiplicada por la raíz "
        "de los períodos anuales para σ. Los supuestos personalizados se muestran en la sección de Monte Carlo "
        "y no modifican los resultados históricos. No son previsiones publicadas por las empresas.",
    ]
    if "assets" in charts:
        sections.extend(
            [
                f"![Evolución de los activos]({charts['assets']})",
                "*Todos los activos parten de un valor de 100 para facilitar la comparación. Su evolución se expresa en la divisa del informe.*",
            ]
        )
    sections.extend(
        [
            "### Datos publicados y beta",
            _asset_fundamentals(analysis),
            "La beta publicada es la que facilita el proveedor. La beta calculada utiliza el índice "
            "de referencia y el período de este informe, por lo que ambas pueden diferir. El PER "
            "relaciona el precio de la acción con el beneficio por acción. Los datos de la ficha "
            "corresponden a la consulta realizada, no a cada fecha del historial. La capitalización "
            "bursátil se muestra en la divisa de cotización original.",
            "## 4. Diversificación",
            _table(
                ["Activo", "Peso en la cartera", "Contribución al riesgo"],
                [
                    [
                        symbol,
                        format_number(analysis.holdings.loc[symbol, "weight"], True),
                        format_number(value, True),
                    ]
                    for symbol, value in analysis.risk_contributions.items()
                ],
            ),
            _table(
                ["Sector", "Peso"],
                [
                    [SECTORS.get(sector, sector), format_number(weight, True)]
                    for sector, weight in analysis.sector_weights.items()
                ],
            ),
            "La contribución al riesgo se calcula con los pesos actuales y la covarianza histórica "
            "de las rentabilidades. Puede ser negativa si un activo compensa parte de las "
            "fluctuaciones de los demás.",
            "### Correlaciones",
            _table(
                ["Activo", *analysis.correlations.columns],
                [
                    [symbol, *[format_number(value) for value in row]]
                    for symbol, row in analysis.correlations.iterrows()
                ],
            ),
        ]
    )
    if "distribution" in charts:
        sections.extend(
            [
                "### Distribución de las rentabilidades",
                f"![Rentabilidades históricas y distribución normal]({charts['distribution']})",
                "La curva normal tiene la misma media y desviación típica que las rentabilidades logarítmicas históricas. "
                "Las diferencias en los extremos ayudan a apreciar las limitaciones del supuesto de normalidad. "
                "Con pocos datos esta comparación es poco concluyente.",
            ]
        )
    if "portfolio" in charts:
        sections.append(f"![Evolución y riesgo de la cartera]({charts['portfolio']})")
    if simulation is not None:
        sections.extend(["## 5. Simulación de Monte Carlo", _simulation_summary(simulation)])
        if "simulation" in charts:
            sections.append(
                f"![Escenarios simulados y distribución del valor final]({charts['simulation']})"
            )
    quality_number = 6 if simulation is not None else 5
    sections.extend([f"## {quality_number}. Datos y referencias", _quality(analysis)])
    if analysis.reference_names:
        sections.extend(
            [
                "### Referencias utilizadas",
                _table(["Referencia", "Serie"], analysis.reference_names.items()),
                "Las fuentes de los precios de cada activo figuran en sus fichas. En la ejecución "
                "desde consola, el índice de referencia y los cambios de divisa automáticos se "
                "consultan en Yahoo Finance. La inflación y el tipo de interés se consultan en FRED, "
                "independientemente del proveedor de precios elegido.",
            ]
        )
    sections.extend(
        [
            "### Observaciones",
            "\n".join(f"- {warning}" for warning in dict.fromkeys(analysis.warnings))
            or "Sin incidencias adicionales.",
            f"**Configuración utilizada:** las rentabilidades se calculan con los precios de la "
            f"columna {analysis.price_column}, tomando {analysis.periods_per_year} períodos por año. "
            "La información de los activos y las referencias económicas se consultan automáticamente. "
            "Si se ha realizado una simulación, sus parámetros se detallan en la sección correspondiente.",
            "**Criterios de cálculo:** solo se utilizan fechas con precios para todos los activos. "
            "Para convertir divisas puede utilizarse el último tipo de cambio disponible, siempre que "
            "no supere el límite de antigüedad indicado. Las rentabilidades calculadas con Close no "
            "incluyen dividendos. Con Adj Close se estima el crecimiento con reinversión de las "
            "distribuciones, que puede diferir del valor de las posiciones. Los cálculos no incluyen "
            "comisiones, impuestos, aportaciones ni retiradas de dinero.",
            "### Cómo leer las medidas",
            "- **Rentabilidad anualizada:** rentabilidad anual equivalente al crecimiento del período analizado.\n"
            "- **Rentabilidad real:** rentabilidad después de descontar la inflación.\n"
            "- **Volatilidad:** mide cuánto fluctúan las rentabilidades; no indica cuánto se puede llegar a perder.\n"
            "- **Caída máxima:** mayor descenso respecto a un máximo anterior durante el período analizado.\n"
            "- **Sharpe y Sortino:** relacionan la rentabilidad por encima de la referencia con el riesgo asumido.\n"
            "- **Percentil 5 y media de los peores resultados:** muestran el umbral de las rentabilidades más bajas y la media de las que quedan en ese umbral o por debajo de él. Se calculan por período de observación.\n"
            "- **HHI y número efectivo de activos:** indican cómo se reparte el valor de la cartera entre sus posiciones; no tienen en cuenta las correlaciones.",
        ]
    )
    return "\n\n".join(sections) + "\n"
