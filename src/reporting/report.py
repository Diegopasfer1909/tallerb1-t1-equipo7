"""Informes en español a partir de los resultados del análisis, sin descargas."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

import pandas as pd

from ..constants import MONTHLY
from . import texts
from .formatting import format_date, format_number, format_points
from .labels import (
    ASSET_TYPES,
    CHART_TITLES,
    COUNTRIES,
    HOLDINGS_COLUMNS,
    PERCENT_RESULTS,
    PRICE_BASES,
    SECTORS,
    SEVERITIES,
    SOURCES,
    WEIGHT_COLUMNS,
    simulation_labels,
)
from .sections import ALWAYS_OPEN, SECTION_TITLES, select_sections

if TYPE_CHECKING:
    from ..analysis.result import PortfolioAnalysis
    from ..simulation.result import SimulationResult

# Medida, etiqueta y unidad: % para rentabilidades, pp para diferencias y vacío para ratios.
PORTFOLIO_METRICS = [
    ("annualized_return", "Rentabilidad anualizada", "%"),
    ("real_annualized_return", "Rentabilidad real anualizada", "%"),
    ("annualized_volatility", "Volatilidad anual", "%"),
    (
        "comparison_portfolio_annualized_return",
        "Cartera: rentabilidad anualizada en las fechas comunes",
        "%",
    ),
    ("benchmark_annualized_return", "Índice: rentabilidad anualizada en las fechas comunes", "%"),
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


@dataclass(frozen=True)
class ReportContext:
    """Resultados que puede necesitar cada sección del informe."""

    analysis: PortfolioAnalysis
    simulation: SimulationResult | None = None


def _table(headers, rows) -> str:
    def cell(value):
        return str(value).replace("|", "\\|").replace("\n", " ")

    lines = ["| " + " | ".join(map(cell, headers)) + " |"]
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    lines.extend("| " + " | ".join(map(cell, row)) + " |" for row in rows)
    return "\n".join(lines)


def _bullets(items) -> str:
    return "\n".join(f"- {item}" for item in items)


def holdings_table(holdings: pd.DataFrame) -> pd.DataFrame:
    """Posiciones con etiquetas en español y números con coma decimal."""
    table = pd.DataFrame(index=holdings.index.rename("Activo"))
    for column, label in HOLDINGS_COLUMNS.items():
        percentage = column in WEIGHT_COLUMNS
        table[label] = [format_number(value, percentage) for value in holdings[column]]
    return table


def _asset_information(analysis: PortfolioAnalysis) -> str:
    profiles = []
    for symbol, asset in analysis.asset_details.iterrows():
        kind = ASSET_TYPES.get(asset["asset_type"], asset["asset_type"])
        sector = SECTORS.get(asset["sector"], asset["sector"])
        country = COUNTRIES.get(asset["country"], asset["country"])
        source = SOURCES.get(asset["source"], asset["source"])
        profiles.append(
            f"**{symbol} · {asset['name']}**  \n"
            f"{kind} · {sector} · {country} · Cotización en {asset['quote_currency']} · "
            f"Fuente: {source}."
        )
    return "\n\n".join(profiles)


def _asset_percentages(analysis: PortfolioAnalysis, columns: dict[str, str]) -> str:
    """Una fila por activo con las medidas de asset_details indicadas, en porcentaje."""
    return _table(
        ["Activo", *columns],
        [
            [symbol, *(format_number(row[key], True) for key in columns.values())]
            for symbol, row in analysis.asset_details.iterrows()
        ],
    )


def _asset_performance(analysis: PortfolioAnalysis) -> str:
    return _asset_percentages(
        analysis,
        {
            "Rentabilidad total": "total_return",
            "Rentabilidad anualizada": "annualized_return",
            "Volatilidad anual": "annualized_volatility",
            "Caída máxima": "max_drawdown",
        },
    )


def _asset_fundamentals(analysis: PortfolioAnalysis) -> str:
    rows = []
    for symbol, asset in analysis.asset_details.iterrows():
        if asset["asset_type"] == "index":
            capital = pe = "No aplicable"
        else:
            capital = format_number(asset["market_cap"])
            if pd.notna(asset["market_cap"]):
                capital += f" {asset['quote_currency']}"
            pe = format_number(asset["pe_ratio"])
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


def _estimated_parameters(analysis: PortfolioAnalysis) -> str:
    return _asset_percentages(
        analysis,
        {
            "Retorno anual μ (histórico)": "expected_annual_return",
            "Volatilidad anual σ (histórica)": "expected_annual_volatility",
        },
    )


def _portfolio_metrics(analysis: PortfolioAnalysis) -> str:
    rows, missing = [], []
    for key, label, unit in PORTFOLIO_METRICS:
        value = analysis.metrics[key]
        formatted = format_points(value) if unit == "pp" else format_number(value, unit == "%")
        rows.append([label, formatted])
        if pd.isna(value):
            reason = analysis.metric_notes.get(
                key, "No hay datos suficientes para calcular esta medida."
            )
            missing.append("Motivo: " + reason)
    parts = [_table(["Medida", "Resultado"], rows)]
    if missing:
        parts.append(
            "**Medidas que no se han podido calcular**\n\n" + _bullets(dict.fromkeys(missing))
        )
    return "\n\n".join(parts)


def _quality(analysis: PortfolioAnalysis) -> str:
    quality = analysis.data_quality
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
            for symbol, row in quality.iterrows()
        ],
    )
    prices = _table(
        ["Activo", "Columna utilizada", "Ajuste de los precios", "Adj Close disponible"],
        [
            [
                symbol,
                row["price_column"],
                PRICE_BASES.get(row["price_basis"], "No consta"),
                "Sí" if row["adjusted_close_available"] else "No",
            ]
            for symbol, row in quality.iterrows()
        ],
    )
    note = texts.PRICE_BASIS_NOTES[analysis.price_column]
    parts = [coverage, "### Precios utilizados", prices, note]
    missing = quality.loc[quality["missing_optional_cells"] > 0, "missing_optional_cells"]
    parts.extend(
        f"- {symbol}: {cells} datos ausentes en columnas opcionales."
        for symbol, cells in missing.items()
    )
    return "\n\n".join(parts)


def _simulation_summary(simulation: SimulationResult) -> str:
    labels = simulation_labels(simulation.confidence)
    rows = [
        [labels[key], format_number(value, key in PERCENT_RESULTS)]
        for key, value in simulation.summary().items()
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
    if simulation.rebalance_interval:
        rebalance = texts.SIMULATED_REBALANCE.format(interval=simulation.rebalance_interval)
    else:
        rebalance = texts.SIMULATED_BUY_AND_HOLD
    confidence = simulation.confidence
    return "\n\n".join(
        [
            texts.SIMULATION_HEADER.format(
                simulations=len(simulation.paths.columns),
                steps=len(simulation.paths) - 1,
                currency=simulation.currency,
            ),
            _table(["Resultado", "Importe o porcentaje"], rows),
            "### Supuestos de la simulación",
            assumptions,
            texts.SIMULATION_SETTINGS.format(
                date=format_date(simulation.valuation_date),
                periods_per_year=simulation.periods_per_year,
                seed=simulation.seed if simulation.seed is not None else "sin fijar",
            ),
            rebalance,
            texts.CONFIDENCE_NOTE.format(
                lower=100 * (1 - confidence),
                upper=100 * confidence,
                central=(2 * confidence - 1) * 100,
            ),
            texts.MODEL_NOTE.format(method=simulation.correlation_method),
            texts.SIMULATION_LIMITATIONS,
        ]
    )


def _summary(report: ReportContext) -> str:
    analysis = report.analysis
    metrics = analysis.metrics
    symbol = analysis.benchmark_symbol
    benchmark_label = "Diferencia anual frente al índice"
    if symbol:
        benchmark_label += f" ({symbol})"
    rows = [
        [
            f"Valor de la cartera hipotética ({analysis.currency})",
            format_number(analysis.values.iloc[-1]),
        ],
        ["Rentabilidad anualizada", format_number(metrics["annualized_return"], True)],
        [benchmark_label, format_points(metrics["difference_from_benchmark"])],
        ["Caída máxima", format_number(metrics["max_drawdown"], True)],
        ["Ratio de Sharpe", format_number(metrics["sharpe"])],
    ]
    comparison = analysis.benchmark_comparison
    if comparison.empty:
        coverage = texts.NO_BENCHMARK_COVERAGE
    else:
        coverage = texts.BENCHMARK_COVERAGE.format(
            symbol=symbol,
            start=format_date(comparison.index[0]),
            end=format_date(comparison.index[-1]),
            dates=len(comparison),
        )
    capital = texts.SUMMARY_CAPITAL.format(
        capital=format_number(analysis.initial_capital),
        currency=analysis.currency,
        total_return=format_number(metrics["total_return"], True),
    )
    return "\n\n".join([_table(["Medida", "Resultado"], rows), capital, coverage])


def _observed(value: float, unit: str) -> str:
    if unit == "days":
        return f"{value:.0f} días naturales"
    return format_number(value, percentage=unit == "percent")


def _warning_message(warning) -> str:
    """El análisis conserva el sector del proveedor; el informe lo muestra en español."""
    if warning.code == "sector_concentration" and warning.subject:
        return texts.SECTOR_CONCENTRATION.format(
            sector=SECTORS.get(warning.subject, warning.subject)
        )
    return warning.message


def _warnings(report: ReportContext) -> str:
    analysis = report.analysis
    rows = [
        [
            SEVERITIES[warning.severity],
            _warning_message(warning),
            _observed(warning.observed, warning.unit),
            _observed(warning.threshold, warning.unit) if warning.threshold is not None else "—",
        ]
        for warning in analysis.risk_warnings
    ]
    parts = [
        _table(["Nivel", "Riesgo observado", "Valor", "Umbral"], rows)
        if rows
        else texts.NO_RISK_WARNINGS,
        texts.THRESHOLDS_NOTE,
    ]
    # Los problemas de los datos se separan de los criterios que solo conviene conocer.
    data = [notice.message for notice in analysis.notices if notice.kind == "data"]
    method = [notice.message for notice in analysis.notices if notice.kind == "method"]
    for title, notes in (
        ("### Datos que revisar", [*data, *analysis.metric_notes.values()]),
        ("### Notas de metodología", method),
    ):
        if notes:
            parts.extend([title, _bullets(dict.fromkeys(notes))])
    return "\n\n".join(parts)


def _drawdown_details(analysis: PortfolioAnalysis) -> str:
    episode = analysis.drawdown_episode
    if episode.peak is None:
        return texts.NO_DRAWDOWN
    recovery = format_date(episode.recovery) if episode.recovery is not None else "Sin recuperar"
    table = _table(
        ["Pico anterior", "Valle", "Recuperación", "Días naturales desde el pico"],
        [
            [
                format_date(episode.peak),
                format_date(episode.trough),
                recovery,
                episode.underwater_days,
            ]
        ],
    )
    return f"{table}\n\n{texts.DRAWDOWN_DURATION}"


def _calendar_details(analysis: PortfolioAnalysis) -> str:
    monthly = analysis.monthly_returns
    complete = monthly.loc[~monthly["partial"], "return"].dropna()
    parts = ["### Rentabilidades por calendario"]
    if complete.empty:
        parts.append(texts.NO_COMPLETE_MONTHS)
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
    coverage = {True: "Parcial", False: "Completa"}
    parts.extend(
        [
            _table(
                ["Año", "Rentabilidad", "Cobertura"],
                [
                    [str(period), format_number(row["return"], True), coverage[row["partial"]]]
                    for period, row in analysis.annual_returns.iterrows()
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
                        coverage[row["partial"]],
                    ]
                    for period, row in monthly.iterrows()
                ],
            ),
            texts.CALENDAR_NOTE,
        ]
    )
    return "\n\n".join(parts)


def _composition(report: ReportContext) -> str:
    analysis = report.analysis
    holdings = holdings_table(analysis.holdings)
    return "\n\n".join(
        [
            _table([holdings.index.name, *holdings.columns], holdings.itertuples(name=None)),
            texts.COMPOSITION_NOTE.format(currency=analysis.currency),
            texts.MONTHLY_REBALANCE if analysis.rebalance == MONTHLY else texts.BUY_AND_HOLD,
            "### Información de los activos seleccionados",
            _asset_information(analysis),
        ]
    )


def _performance(report: ReportContext) -> str:
    analysis = report.analysis
    return "\n\n".join(
        [
            _portfolio_metrics(analysis),
            texts.PERFORMANCE_NOTE,
            texts.RETURN_MEASURES_NOTE,
            "### Análisis de cada activo",
            _asset_performance(analysis),
            "### Estimaciones a partir del historial",
            _estimated_parameters(analysis),
            texts.ESTIMATES_NOTE,
            "### Recuperación de la mayor caída",
            _drawdown_details(analysis),
            _calendar_details(analysis),
            "### Datos publicados y beta",
            _asset_fundamentals(analysis),
            texts.FUNDAMENTALS_NOTE,
        ]
    )


def _diversification(report: ReportContext) -> str:
    analysis = report.analysis
    pairs = analysis.correlation_pairs
    pair_note = "No hay pares de activos con correlación definida."
    if not pairs.empty:
        a, b = pairs.index[0]
        pair_note = (
            f"Mayor correlación: {a} / {b} ({format_number(pairs.iloc[0])}). "
            f"Media de los pares definidos: {format_number(pairs.mean())}."
        )
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
            texts.RISK_CONTRIBUTION_NOTE,
            "### Correlaciones",
            _table(
                ["Activo", *analysis.correlations.columns],
                [
                    [symbol, *[format_number(value) for value in row]]
                    for symbol, row in analysis.correlations.iterrows()
                ],
            ),
            pair_note,
            texts.CONCENTRATION_NOTE,
            texts.DISTRIBUTION_NOTE,
        ]
    )


def _simulation(report: ReportContext) -> str:
    if report.simulation is None:
        return "No se ha proporcionado una simulación."
    return _simulation_summary(report.simulation)


def _data(report: ReportContext) -> str:
    analysis = report.analysis
    parts = [_quality(analysis)]
    if not analysis.reference_table.empty:
        parts.extend(
            [
                "### Referencias utilizadas",
                _table(
                    ["Referencia", "Serie", "Fuente"],
                    [
                        [label, row["series"], SOURCES.get(row["source"], row["source"])]
                        for label, row in analysis.reference_table.iterrows()
                    ],
                ),
            ]
        )
    parts.extend(
        [
            texts.CONFIGURATION.format(
                price_column=analysis.price_column, periods_per_year=analysis.periods_per_year
            ),
            texts.CALCULATION_CRITERIA,
            "### Cómo leer las medidas",
            texts.GLOSSARY,
        ]
    )
    return "\n\n".join(parts)


_BUILDERS = {
    "summary": _summary,
    "warnings": _warnings,
    "composition": _composition,
    "performance": _performance,
    "diversification": _diversification,
    "simulation": _simulation,
    "data": _data,
}


def build_report(
    analysis: PortfolioAnalysis,
    generated_on: datetime | None = None,
    charts: dict[str, dict[str, str]] | None = None,
    simulation: SimulationResult | None = None,
    *,
    sections=None,
    detail: str = "compact",
) -> str:
    """Compone el Markdown; charts agrupa por sección los archivos de imagen ya guardados."""
    selected = select_sections(sections, detail, has_simulation=simulation is not None)
    generated_on = generated_on or datetime.now().astimezone()
    charts = charts or {}
    report = ReportContext(analysis, simulation)
    dates = analysis.values.index
    strategy = "Rebalanceo mensual" if analysis.rebalance == MONTHLY else "Sin rebalanceo"
    blocks = [
        "# Informe de cartera",
        f"**Período:** {format_date(dates[0])} — {format_date(dates[-1])} · "
        f"**Divisa:** {analysis.currency} · **Precios:** {analysis.price_column} · {strategy}  \n"
        f"*Elaborado el {generated_on:%d/%m/%Y a las %H:%M:%S %z}*",
    ]
    for number, key in enumerate(selected, 1):
        body = _BUILDERS[key](report)
        for chart, file in charts.get(key, {}).items():
            body += f"\n\n![{CHART_TITLES.get(chart, chart)}]({file})"
        title = f"{number}. {SECTION_TITLES[key]}"
        if detail == "compact" and key not in ALWAYS_OPEN:
            blocks.append(f"<details>\n<summary>{title}</summary>\n\n{body}\n\n</details>")
        else:
            blocks.append(f"## {title}\n\n{body}")
    return "\n\n".join(blocks) + "\n"
