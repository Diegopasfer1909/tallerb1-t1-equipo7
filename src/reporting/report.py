"""Informes en español a partir de los resultados del análisis, sin descargas."""

from datetime import datetime

import pandas as pd

from .formatting import format_number
from .sections import SECTION_CHARTS, SECTION_TITLES, select_sections

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


def _summary(analysis) -> str:
    metrics = analysis.metrics
    difference = metrics["difference_from_benchmark"]
    rows = [
        [
            f"Valor de la cartera hipotética ({analysis.currency})",
            format_number(analysis.values.iloc[-1]),
        ],
        ["Rentabilidad anualizada", format_number(metrics["annualized_return"], True)],
        [
            "Diferencia anual frente al índice",
            format_number(difference * 100) + " p. p." if pd.notna(difference) else "No disponible",
        ],
        ["Caída máxima", format_number(metrics["max_drawdown"], True)],
        ["Ratio de Sharpe", format_number(metrics["sharpe"])],
    ]
    comparison = analysis.benchmark_comparison
    coverage = (
        f"Comparación con el índice: {comparison.index[0]:%d/%m/%Y} – "
        f"{comparison.index[-1]:%d/%m/%Y}, {len(comparison)} fechas comunes."
        if not comparison.empty
        else "Comparación con el índice no disponible; consulta las advertencias."
    )
    return "\n\n".join(
        [
            _table(["Medida", "Resultado"], rows),
            f"Cartera hipotética con un capital inicial de {format_number(analysis.initial_capital)} "
            f"{analysis.currency}. Rentabilidad acumulada: {format_number(metrics['total_return'], True)}. "
            "El valor mostrado corresponde a la última fecha común y no representa el saldo real de una cuenta.",
            coverage,
        ]
    )


def _warnings(analysis) -> str:
    rows = []
    for warning in analysis.risk_warnings:
        percentage = warning.code not in ("high_correlation", "unrecovered_drawdown")
        observed = format_number(warning.observed, percentage)
        if warning.code == "unrecovered_drawdown":
            observed = f"{warning.observed:.0f} días naturales"
        threshold = (
            format_number(warning.threshold, percentage) if warning.threshold is not None else "—"
        )
        rows.append(
            [
                "Alta" if warning.severity == "high" else "Media",
                warning.message,
                observed,
                threshold,
            ]
        )
    parts = [
        _table(["Nivel", "Riesgo observado", "Valor", "Umbral"], rows)
        if rows
        else "No se superan los umbrales de riesgo configurados.",
        "Los umbrales son orientativos. La ausencia de avisos no implica ausencia de riesgo.",
    ]
    # Data issues and methodological notes remain separate from portfolio risk rules.
    notes = list(dict.fromkeys([*analysis.warnings, *analysis.metric_notes.values()]))
    if notes:
        parts.extend(
            ["### Datos y criterios que revisar", "\n".join(f"- {note}" for note in notes)]
        )
    return "\n\n".join(parts)


def _drawdown_details(analysis) -> str:
    episode = analysis.drawdown_episode
    if episode.peak is None:
        return "No se observaron caídas desde máximos en el período analizado."
    recovery = f"{episode.recovery:%d/%m/%Y}" if episode.recovery is not None else "Sin recuperar"
    return (
        _table(
            ["Pico anterior", "Valle", "Recuperación", "Días naturales desde el pico"],
            [
                [
                    f"{episode.peak:%d/%m/%Y}",
                    f"{episode.trough:%d/%m/%Y}",
                    recovery,
                    episode.underwater_days,
                ]
            ],
        )
        + "\n\nLa duración corresponde a la mayor caída; si no se recuperó, se cuenta hasta el final del historial."
    )


def _calendar_details(analysis) -> str:
    monthly = analysis.monthly_returns
    complete = monthly.loc[~monthly["partial"], "return"].dropna()
    parts = ["### Rentabilidades por calendario"]
    if complete.empty:
        parts.append("No hay meses completos con los que identificar el mejor y el peor mes.")
    else:
        parts.append(
            _table(
                ["Mes completo", "Período", "Rentabilidad"],
                [
                    ["Mejor", str(complete.idxmax()), format_number(complete.max(), True)],
                    ["Peor", str(complete.idxmin()), format_number(complete.min(), True)],
                ],
            )
        )
    annual = analysis.annual_returns
    parts.extend(
        [
            _table(
                ["Año", "Rentabilidad", "Cobertura"],
                [
                    [
                        str(period),
                        format_number(row["return"], True),
                        "Parcial" if row["partial"] else "Completa",
                    ]
                    for period, row in annual.iterrows()
                ],
            ),
            "### Rentabilidades mensuales\n\n"
            + _table(
                ["Mes", "Rentabilidad", "Observaciones", "Cobertura"],
                [
                    [
                        str(period),
                        format_number(row["return"], True),
                        row["observations"],
                        "Parcial" if row["partial"] else "Completa",
                    ]
                    for period, row in monthly.iterrows()
                ],
            ),
            "Las rentabilidades parciales no se anualizan ni participan en la selección del mejor/peor mes. "
            "La cobertura comprueba el cierre previo y el final del período con un calendario lunes-viernes; "
            "no certifica los festivos de cada bolsa ni la ausencia de huecos internos. Los intervalos que saltan "
            "un mes/año entero quedan sin atribuir a un único mes/año.",
        ]
    )
    return "\n\n".join(parts)


def _composition(analysis) -> str:
    return "\n\n".join(
        [
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
        ]
    )


def _performance(analysis) -> str:
    return "\n\n".join(
        [
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
            "### Recuperación de la mayor caída",
            _drawdown_details(analysis),
            _calendar_details(analysis),
            "### Datos publicados y beta",
            _asset_fundamentals(analysis),
            "La beta publicada es la que facilita el proveedor. La beta calculada utiliza el índice "
            "de referencia y el período de este informe, por lo que ambas pueden diferir. El PER "
            "relaciona el precio de la acción con el beneficio por acción. Los datos de la ficha "
            "corresponden a la consulta realizada, no a cada fecha del historial. La capitalización "
            "bursátil se muestra en la divisa de cotización original.",
        ]
    )


def _diversification(analysis) -> str:
    pairs = analysis.correlation_pairs
    pair_note = "No hay pares de activos con correlación definida."
    if not pairs.empty:
        a, b = pairs.index[0]
        pair_note = f"Mayor correlación: {a} / {b} ({format_number(pairs.iloc[0])}). "
        pair_note += f"Media de los pares definidos: {format_number(pairs.mean())}."
    return "\n\n".join(
        [
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
            pair_note,
            "HHI y número efectivo de activos miden concentración de pesos; no cuentan apuestas independientes.",
            "La comparación con una distribución normal utiliza incrementos logarítmicos históricos. "
            "Con pocos datos, las diferencias en las colas son poco concluyentes.",
        ]
    )


def _data(analysis) -> str:
    parts = [_quality(analysis)]
    if analysis.reference_names:
        parts.extend(
            [
                "### Referencias utilizadas",
                _table(["Referencia", "Serie"], analysis.reference_names.items()),
                "En consola, el índice y los cambios de divisa se consultan en Yahoo Finance; "
                "la inflación y el tipo de interés, en FRED. Las fuentes de los activos figuran en sus fichas.",
            ]
        )
    parts.extend(
        [
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
    return "\n\n".join(parts)


_BUILDERS = {
    "summary": _summary,
    "warnings": _warnings,
    "composition": _composition,
    "performance": _performance,
    "diversification": _diversification,
    "data": _data,
}


def build_report(
    analysis,
    generated_on: datetime | None = None,
    charts: dict[str, str] | None = None,
    simulation=None,
    *,
    sections=None,
    detail: str = "compact",
) -> str:
    selected = select_sections(sections, detail, has_simulation=simulation is not None)
    generated_on = generated_on or datetime.now().astimezone()
    charts = charts or {}
    strategy = "Rebalanceo mensual" if analysis.rebalance == "monthly" else "Sin rebalanceo"
    blocks = [
        "# Informe de cartera",
        f"**Período:** {analysis.values.index[0]:%d/%m/%Y} — {analysis.values.index[-1]:%d/%m/%Y} · "
        f"**Divisa:** {analysis.currency} · **Precios:** {analysis.price_column} · {strategy}  \n"
        f"*Elaborado el {generated_on:%d/%m/%Y a las %H:%M:%S %z}*",
    ]
    for number, key in enumerate(selected, 1):
        if key == "simulation":
            body = (
                _simulation_summary(simulation)
                if simulation is not None
                else "No se ha proporcionado una simulación."
            )
        else:
            body = _BUILDERS[key](analysis)
        for chart in SECTION_CHARTS.get(key, ()):
            if chart in charts:
                body += f"\n\n![{SECTION_TITLES[key]}: {chart}]({charts[chart]})"
        title = f"{number}. {SECTION_TITLES[key]}"
        if detail == "compact" and key not in ("summary", "warnings"):
            blocks.append(f"<details>\n<summary>{title}</summary>\n\n{body}\n\n</details>")
        else:
            blocks.append(f"## {title}\n\n{body}")
    return "\n\n".join(blocks) + "\n"
