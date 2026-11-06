"""Informes en español a partir de los resultados del análisis, sin descargas."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from ..analysis.warnings import evaluate_simulation
from ..commissions import CommissionSchedule, RebalanceRule
from ..constants import ADJ_CLOSE, EUR, MONTHLY
from ..simulation.monte_carlo import MODEL_RETURN
from ..simulation.settings import SimulationSettings
from . import texts
from .formatting import UNAVAILABLE, format_date, format_number, format_points
from .labels import (
    CHART_TITLES,
    COUNTRIES,
    DIVIDEND_VALUE_LABEL,
    HOLDINGS_COLUMNS,
    PRICE_COLUMN_LABELS,
    RISK_FREE_NAMES,
    SECTORS,
    SENSITIVITY_CASES,
    SEVERITIES,
    SHARES_HOLDINGS_COLUMNS,
    SOURCES,
    WEIGHT_COLUMNS,
)
from .sections import SECTION_QUESTIONS, SECTION_TITLES, select_sections

if TYPE_CHECKING:
    from ..analysis.result import PortfolioAnalysis
    from ..simulation.result import SimulationResult


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


def holdings_table(holdings: pd.DataFrame, by_shares: bool = False) -> pd.DataFrame:
    """Posiciones con etiquetas en español y números con coma decimal.

    by_shares indica una cartera definida por número de acciones sin rebalanceo: sus pesos de
    partida no son un objetivo y su valor no es hipotético. Con Adj Close, Portfolio.holdings()
    añade el valor de mercado y el valor incluye los dividendos reinvertidos.
    """
    table = pd.DataFrame(index=holdings.index.rename("Activo"))
    columns = dict(SHARES_HOLDINGS_COLUMNS if by_shares else HOLDINGS_COLUMNS)
    if "market_value" in holdings:
        columns["value"] = DIVIDEND_VALUE_LABEL
    for column, label in columns.items():
        if column in ("shares", "market_value") and column not in holdings:
            continue
        percentage = column in WEIGHT_COLUMNS
        table[label] = [format_number(value, percentage) for value in holdings[column]]
    return table


# Lecturas: traducen cada cifra a una frase con los tramos de la guía del report.
def _band(value: float, limits: list[tuple[float, str]], last: str) -> str:
    if pd.isna(value):
        return ""
    for limit, text in limits:
        if value < limit:
            return text
    return last


def _read_sharpe(value):
    return _band(value, [(0, "malo"), (0.5, "pobre"), (1, "aceptable")], "bueno")


def _read_volatility(value):
    return _band(
        value,
        [(0.15, "baja"), (0.20, "como un índice amplio"), (0.25, "elevada")],
        "como una acción suelta",
    )


def _read_drawdown(value):
    return _band(
        value, [(-0.30, "caída de crisis fuerte"), (-0.15, "caída notable")], "caída moderada"
    )


def _read_beta(value):
    return _band(
        value, [(0.8, "defensiva"), (1.2, "se mueve como el índice")], "amplifica al mercado"
    )


def _read_mean_correlation(value):
    return _band(
        value, [(0.3, "buena diversificación"), (0.6, "moderada")], "los activos caen a la vez"
    )


def _read_vix(value):
    return _band(value, [(15, "calma"), (25, "normal"), (30, "nerviosismo")], "estrés")


def _read_sign(value, positive: str, negative: str):
    return "" if pd.isna(value) else (positive if value > 0 else negative)


def _strategy(analysis: PortfolioAnalysis) -> str:
    if analysis.units is not None and analysis.rebalance == MONTHLY:
        return "rebalanceo mensual a los pesos iniciales de las acciones"
    if analysis.units is not None:
        return "número de acciones fijo, sin rebalanceo"
    if analysis.rebalance == MONTHLY:
        return "rebalanceo mensual"
    return "sin rebalanceo (comprar y mantener)"


def _risk_free_label(analysis: PortfolioAnalysis) -> str:
    series = analysis.risk_free_series
    name = RISK_FREE_NAMES.get(series, series)
    return f"tipo libre de riesgo ({name})" if name else "tipo libre de riesgo"


def _annual_points(value: float) -> str:
    """Diferencia de rentabilidades anuales, con signo; un dato ausente no lleva unidad."""
    return UNAVAILABLE if pd.isna(value) else f"{format_points(value, signed=True)}/año"


def _read_gap(value: float, reference: str) -> str:
    """Cuántos puntos por encima o por debajo de una referencia quedó la cartera."""
    if pd.isna(value):
        return ""
    direction = "más" if value > 0 else "menos"
    return f"rindió {format_points(abs(value))} {direction} que {reference}"


def _money(value: float, currency: str) -> str:
    return f"{format_number(value)} {currency}"


def _summary(report: ReportContext) -> str:
    analysis = report.analysis
    metrics = analysis.metrics
    currency = analysis.currency
    dates = analysis.values.index
    header = (
        f"{format_date(dates[0])} – {format_date(dates[-1])} · {len(dates) - 1} sesiones · "
        f"referencia: {analysis.benchmark_name or 'sin índice'} · {_strategy(analysis)}"
    )
    difference = metrics["difference_from_benchmark"]
    drawdown = metrics["max_drawdown"]
    symbol = analysis.benchmark_symbol
    benchmark_label = "Diferencia anual frente al índice"
    if symbol:
        benchmark_label += f" ({symbol})"
    premium = metrics["excess_annualized_return"]
    rows = [
        [
            f"Valor final de {_money(analysis.initial_capital, currency)}",
            f"**{_money(analysis.values.iloc[-1], currency)}**",
            f"{format_number(metrics['total_return'], True, signed=True)} en total, "
            f"{format_number(metrics['annualized_return'], True)} al año",
        ],
        [
            benchmark_label,
            f"**{_annual_points(difference)}**",
            _read_sign(difference, "batió al índice", "habría sido mejor comprar el índice"),
        ],
        [
            f"Diferencia frente al {_risk_free_label(analysis)}",
            f"**{_annual_points(premium)}**",
            _read_gap(premium, "el tipo libre de riesgo"),
        ],
        [
            "Drawdown máximo",
            f"**{format_number(drawdown, True)}**",
            _read_drawdown(drawdown),
        ],
        [
            "Ratio de Sharpe",
            f"**{format_number(metrics['sharpe'])}**",
            _read_sharpe(metrics["sharpe"]),
        ],
    ]
    parts = [header, _table(["Cifra", "Valor", "Lectura"], rows)]
    comparison = analysis.benchmark_comparison
    if not comparison.empty:
        parts.append(
            texts.BENCHMARK_COVERAGE.format(
                symbol=symbol,
                start=format_date(comparison.index[0]),
                end=format_date(comparison.index[-1]),
                dates=len(comparison),
            )
        )
    return "\n\n".join(parts)


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
    warnings = list(analysis.risk_warnings)
    if report.simulation is not None:
        probability = report.simulation.summary()["probability_of_loss"]
        warnings.extend(evaluate_simulation(probability, analysis.warning_thresholds))
    warnings.sort(key=lambda warning: warning.severity != "high")
    if not warnings:
        return texts.NO_RISK_WARNINGS
    rows = []
    for warning in warnings:
        detail = f"{_warning_message(warning)} Valor: {_observed(warning.observed, warning.unit)}"
        if warning.threshold is not None:
            detail += f"; umbral: {_observed(warning.threshold, warning.unit)}"
        rows.append([SEVERITIES[warning.severity], warning.title, f"{detail}."])
    return _table(["Nivel", "Advertencia", "Detalle"], rows)


def _composition(report: ReportContext) -> str:
    analysis = report.analysis
    returns = analysis.asset_returns
    units = analysis.units
    shares = units is not None
    rebalanced = analysis.rebalance == MONTHLY
    rows = []
    for symbol, asset in analysis.asset_details.iterrows():
        target = analysis.target_weights[symbol]
        amount = [format_number(units[symbol])] if shares else []
        rows.append(
            [
                symbol,
                *amount,
                asset["name"],
                SECTORS.get(asset["sector"], asset["sector"]),
                asset["quote_currency"],
                COUNTRIES.get(asset["country"], asset["country"]),
                format_number(target, True),
                _money(analysis.initial_capital * target, analysis.currency),
                format_number(analysis.holdings.loc[symbol, "weight"], True),
                format_number(returns[symbol].mean(), True),
                format_number(returns[symbol].std(), True),
            ]
        )
    notes = texts.DAILY_VALUES_NOTE
    if (analysis.asset_details["quote_currency"] != analysis.currency).any():
        notes += " " + texts.CONVERTED_PRICES_NOTE.format(currency=analysis.currency)
    if shares:
        notes += "\n\n" + _shares_note(analysis)
    table = _table(
        [
            "Ticker",
            *([("Acciones iniciales" if rebalanced else "Acciones")] if shares else []),
            "Nombre",
            "Sector",
            "Divisa",
            "País",
            "Peso inicial" if shares and not rebalanced else "Peso objetivo",
            "Importe inicial",
            "Peso actual",
            "Media diaria",
            "Desv. típica diaria",
        ],
        rows,
    )
    return "\n\n".join([table, notes, _costs_note(analysis)])


def commission_description(schedule: CommissionSchedule, currency: str) -> str:
    """Tarifa por orden en palabras, como «0,05 % por orden, mínimo 3,00 EUR»."""
    if schedule.is_free:
        return "sin comisiones"
    return _tariff_terms(schedule, currency)


def tariff_label(schedule: CommissionSchedule, currency: str) -> str:
    """Nombre y tarifa, como «DEGIRO: 2,00 EUR por orden»; solo el nombre si es gratis."""
    if schedule.is_free:
        return schedule.name
    return f"{schedule.name}: {commission_description(schedule, currency)}"


def _tariff_terms(schedule: CommissionSchedule, currency: str) -> str:
    parts = []
    if schedule.rate:
        parts.append(format_number(schedule.rate, True))
    if schedule.fixed:
        parts.append(_money(schedule.fixed, currency))
    text = (" + ".join(parts) or "0") + " por orden"
    if schedule.minimum:
        text += f", mínimo {_money(schedule.minimum, currency)}"
    if schedule.maximum is not None:
        text += f", máximo {_money(schedule.maximum, currency)}"
    return text


def rule_description(rule: RebalanceRule) -> str:
    """Cuándo se reajusta: banda de desviación y órdenes descartadas por caras."""
    when = (
        f"si algún peso se desvía más de {format_points(rule.band)} de su objetivo"
        if rule.band
        else "siempre que los pesos se hayan desviado"
    )
    if rule.max_order_cost is not None:
        when += (
            "; se descartan las órdenes cuya comisión supere el "
            f"{format_number(rule.max_order_cost, True)} de su importe"
        )
    return when


def _costs_note(analysis: PortfolioAnalysis) -> str:
    costs = analysis.rebalance_costs
    if costs is None or costs.rule.commissions.is_free:
        return texts.COSTS_NOTE
    return texts.COMMISSIONS_NOTE.format(
        broker=costs.rule.commissions.name,
        tariff=commission_description(costs.rule.commissions, analysis.currency),
        currency=analysis.currency,
    )


def _rebalance_costs(analysis: PortfolioAnalysis) -> str:
    """Comisiones pagadas y valor final frente a comprar y mantener."""
    costs = analysis.rebalance_costs
    currency = analysis.currency
    rule = costs.rule
    advantage = costs.advantage
    share = costs.commissions / costs.gain if costs.gain > 0 else float("nan")
    rows = [
        ["Tarifa", tariff_label(rule.commissions, currency), ""],
        ["Cuándo se reajusta", f"A fin de mes, {rule_description(rule)}", ""],
        ["Reajustes realizados", str(costs.rebalances), ""],
        [
            "Órdenes ejecutadas / descartadas",
            f"{costs.orders} / {costs.skipped_orders}",
            "descartadas por comisión demasiado alta" if costs.skipped_orders else "",
        ],
        [
            "Comisiones pagadas",
            _money(costs.commissions, currency),
            f"{format_number(share, True)} de la ganancia antes de comisiones"
            if pd.notna(share)
            else "",
        ],
        ["Valor final con rebalanceo", _money(costs.final_value, currency), "neto de comisiones"],
        ["Valor final sin rebalanceo", _money(costs.buy_and_hold_value, currency), ""],
        [
            "Diferencia",
            f"{format_number(advantage, signed=True)} {currency}",
            _read_advantage(costs),
        ],
    ]
    return "\n\n".join(
        [
            "**Coste del rebalanceo**",
            _table(["Concepto", "Valor", "Lectura"], rows),
            texts.REBALANCE_COSTS_NOTE,
        ]
    )


def _read_advantage(costs) -> str:
    if costs.advantage > 0:
        return "rebalancear ha compensado, ya pagadas las comisiones"
    if costs.advantage == 0:
        return ""
    if costs.gross_advantage >= 0 and costs.commissions > 0:
        return "las comisiones anulan lo que aportaba rebalancear"
    return "rendiría menos incluso sin comisiones: vender lo que más sube frena la rentabilidad"


def _shares_note(analysis: PortfolioAnalysis) -> str:
    if analysis.rebalance == MONTHLY:
        return texts.SHARES_REBALANCED_NOTE
    holdings = analysis.holdings
    if analysis.price_column == ADJ_CLOSE and "market_value" in holdings:
        return texts.SHARES_ADJUSTED_NOTE.format(
            market=_money(holdings["market_value"].sum(), analysis.currency),
            value=_money(holdings["value"].sum(), analysis.currency),
        )
    return texts.SHARES_NOTE


def _annual_results(analysis: PortfolioAnalysis) -> str:
    """El primer y el último año pueden ser parciales: no son comparables con uno completo."""
    coverage = {True: "Parcial", False: "Completa"}
    return _table(
        ["Año", "Rentabilidad", "Cobertura"],
        [
            [str(year), format_number(row["return"], True, signed=True), coverage[row["partial"]]]
            for year, row in analysis.annual_returns.iterrows()
        ],
    )


def _asset_results(analysis: PortfolioAnalysis) -> str:
    """Resultado de cada activo en la divisa de la cartera, en las mismas fechas que esta."""
    return _table(
        ["Ticker", "Rentabilidad total", "CAGR", "Volatilidad", "Caída máxima", "Beta"],
        [
            [
                symbol,
                format_number(row["total_return"], True, signed=True),
                format_number(row["annualized_return"], True),
                format_number(row["annualized_volatility"], True),
                format_number(row["max_drawdown"], True),
                format_number(row["calculated_beta"]),
            ]
            for symbol, row in analysis.asset_details.iterrows()
        ],
    )


def _returns(report: ReportContext) -> str:
    analysis = report.analysis
    metrics = analysis.metrics
    difference = metrics["difference_from_benchmark"]
    real = metrics["real_annualized_return"]
    rows = [
        [
            "Rentabilidad acumulada",
            format_number(metrics["total_return"], True, signed=True),
            "de principio a fin",
        ],
        [
            "Rentabilidad anualizada (CAGR)",
            format_number(metrics["annualized_return"], True),
            "en renta variable, 6–9 % anual es lo habitual",
        ],
        [
            f"CAGR de {analysis.benchmark_name or 'el índice'}",
            format_number(metrics["benchmark_annualized_return"], True),
            "",
        ],
        [
            "Diferencia frente al índice",
            _annual_points(difference),
            _read_sign(difference, "la cartera batió al índice", "el índice rindió más"),
        ],
        ["Inflación media anual", format_number(metrics["annualized_inflation"], True), ""],
        [
            "Rentabilidad real",
            format_number(real, True),
            _read_sign(real, "ganó poder de compra", "perdió frente a la inflación"),
        ],
    ]
    monthly = analysis.monthly_returns
    complete = monthly.loc[~monthly["partial"], "return"].dropna()
    for label, month in (
        ("Mejor mes", complete.idxmax() if not complete.empty else None),
        ("Peor mes", complete.idxmin() if not complete.empty else None),
    ):
        value = complete[month] if month is not None else float("nan")
        rows.append(
            [
                label,
                format_number(value, True, signed=True),
                month.strftime("%m/%Y") if month is not None else "",
            ]
        )
    blocks = [
        _table(["Métrica", "Valor", "Lectura"], rows),
        texts.NOMINAL_RETURNS_NOTE.format(currency=analysis.currency),
        "**Por año**",
        _annual_results(analysis),
        "**Por activo**",
        _asset_results(analysis),
    ]
    if analysis.rebalance_costs is not None:
        blocks.append(_rebalance_costs(analysis))
    return "\n\n".join(blocks)


def _risk(report: ReportContext) -> str:
    analysis = report.analysis
    metrics = analysis.metrics
    episode = analysis.drawdown_episode
    drawdown_read = _read_drawdown(metrics["max_drawdown"])
    if episode.peak is not None:
        recovery = (
            format_date(episode.recovery) if episode.recovery is not None else "sin recuperar"
        )
        drawdown_read += (
            f": pico {format_date(episode.peak)}, valle {format_date(episode.trough)}, "
            f"recuperación {recovery}"
        )
    rows = [
        [
            "Volatilidad anualizada",
            format_number(metrics["annualized_volatility"], True),
            _read_volatility(metrics["annualized_volatility"]),
        ],
        ["Drawdown máximo", format_number(metrics["max_drawdown"], True), drawdown_read],
        [
            "VaR 95 % diario",
            format_number(metrics["period_var_95_return"], True),
            "uno de cada 20 días se pierde al menos esto",
        ],
        [
            "CVaR 95 % diario",
            format_number(metrics["period_cvar_95_return"], True),
            "pérdida media en ese 5 % de peores días",
        ],
        ["Beta", format_number(metrics["beta"]), _read_beta(metrics["beta"])],
    ]
    return _table(["Métrica", "Valor", "Lectura"], rows)


def _risk_adjusted(report: ReportContext) -> str:
    analysis = report.analysis
    metrics = analysis.metrics
    sharpe, sortino = metrics["sharpe"], metrics["sortino"]
    sortino_read = ""
    if pd.notna(sharpe) and pd.notna(sortino):
        sortino_read = (
            "volatilidad sobre todo al alza"
            if sortino > 1.5 * sharpe and sharpe > 0
            else "similar al Sharpe"
        )
    premium = metrics["excess_annualized_return"]
    premium_read = ""
    if pd.notna(premium):
        premium_read = (
            "poca compensación para el riesgo de la bolsa"
            if premium < analysis.warning_thresholds.premium
            else "compensó"
        )
    label = _risk_free_label(analysis)
    rows = [
        ["Ratio de Sharpe", format_number(sharpe), _read_sharpe(sharpe)],
        ["Ratio de Sortino", format_number(sortino), sortino_read],
        [
            "Alfa de Jensen (anual)",
            format_number(metrics["alpha"], True, signed=True),
            _read_sign(
                metrics["alpha"],
                "la selección de valores aportó",
                "habría sido mejor comprar el índice",
            ),
        ],
        [f"Prima frente al {label}", _annual_points(premium), premium_read],
        [
            f"{label[0].upper()}{label[1:]}, medio del periodo",
            format_number(metrics["reference_annualized_return"], True),
            "referencia de Sharpe, Sortino y alfa",
        ],
    ]
    if analysis.currency == EUR:
        difference = metrics["difference_from_bund_etf"]
        bund_etf = format_number(metrics["bund_etf_annualized_return"], True)
        read = _read_gap(difference, "la deuda alemana")
        rows.append(
            [
                "Diferencia frente a deuda alemana",
                _annual_points(difference),
                f"{read} (CAGR del ETF de Bunds: {bund_etf})" if read else "",
            ]
        )
    return "\n\n".join([_table(["Métrica", "Valor", "Lectura"], rows), texts.RETURN_MEASURES_NOTE])


def _diversification(report: ReportContext) -> str:
    analysis = report.analysis
    metrics = analysis.metrics
    pairs = analysis.correlation_pairs
    weights = analysis.holdings["weight"]
    pair_value, pair_read = "No disponible", ""
    if not pairs.empty:
        a, b = pairs.index[0]
        pair_value = f"{a} – {b}: {format_number(pairs.iloc[0])}"
        pair_read = "casi redundantes" if pairs.iloc[0] > 0.8 else ""
    effective = metrics["effective_asset_count"]
    rows = [
        [
            "Correlación media",
            format_number(metrics["correlation_mean"]),
            _read_mean_correlation(metrics["correlation_mean"]),
        ],
        ["Par más correlacionado", pair_value, pair_read],
        [
            "Nº efectivo de activos",
            f"{format_number(effective)} de {len(weights)}",
            f"en la práctica, unas {effective:.0f} apuestas distintas",
        ],
    ]
    contributions = _table(
        ["Ticker", "Peso", "Contribución al riesgo"],
        [
            [symbol, format_number(weights[symbol], True), format_number(share, True)]
            for symbol, share in analysis.risk_contributions.items()
        ],
    )
    sectors = ", ".join(
        f"{SECTORS.get(sector, sector)} {format_number(weight, True)}"
        for sector, weight in analysis.sector_weights.items()
    )
    currencies = ", ".join(
        f"{currency} {format_number(weight, True)}"
        for currency, weight in analysis.currency_weights.items()
    )
    return "\n\n".join(
        [
            _table(["Métrica", "Valor", "Lectura"], rows),
            contributions,
            f"**Por sector:** {sectors}  \n**Por divisa:** {currencies}",
        ]
    )


def _market(report: ReportContext) -> str:
    analysis = report.analysis
    market = analysis.market
    gold = market.gold_correlation
    gold_read = ""
    if pd.notna(gold):
        gold_read = "el oro aportaría diversificación" if gold < 0.2 else "el oro diversifica poco"
    rows = [
        [
            "VIX actual",
            f"{format_number(market.vix_current)} "
            f"(media del periodo {format_number(market.vix_mean)})",
            _read_vix(market.vix_current),
        ],
        [
            "Correlación con el Brent",
            format_number(market.brent_correlation),
            _read_sign(
                market.brent_correlation,
                "sensible al petróleo",
                "le perjudica que suba el petróleo",
            ),
        ],
        ["Correlación con el oro", format_number(gold), gold_read],
        [
            "Correlación con el ETF de Bunds",
            format_number(market.bund_etf_correlation),
            _read_sign(market.bund_etf_correlation, "caen juntos", "el Bund hace de refugio"),
        ],
        [
            "Bund en el 5 % de peores días",
            format_number(market.bund_on_worst_days, True, signed=True),
            _read_sign(market.bund_on_worst_days, "protegió", "no protegió"),
        ],
    ]
    parts = [_table(["Métrica", "Valor", "Lectura"], rows)]
    if not market.fx_effect.empty:
        details = analysis.asset_details
        parts.append(
            f"**Efecto divisa** (CAGR en {analysis.currency} − CAGR en la divisa original):\n\n"
            + _table(
                ["Ticker", "Divisa", "Efecto"],
                [
                    [
                        symbol,
                        details.loc[symbol, "quote_currency"],
                        f"{_annual_points(effect)} · "
                        + _read_sign(effect, "el tipo de cambio sumó", "el tipo de cambio restó"),
                    ]
                    for symbol, effect in market.fx_effect.items()
                ],
            )
        )
    return "\n\n".join(parts)


def _return_source(assumptions: pd.DataFrame) -> str:
    """Origen común del retorno de los activos: histórico, modelo o indicado por el usuario."""
    sources = assumptions["return_source"]
    if (sources == "usuario").any():
        return "supuesto"
    return MODEL_RETURN if (sources == MODEL_RETURN).any() else "histórico"


def _simulation_criteria(simulation: SimulationResult, analysis: PortfolioAnalysis) -> str:
    """Indica si la simulación usa los criterios por defecto y cómo cambiarlos."""
    defaults = SimulationSettings()
    assumptions = simulation.assumptions
    source = _return_source(assumptions)
    historical_volatility = (assumptions["volatility_source"] == "histórica").all()
    steps = len(simulation.paths) - 1
    scenarios = len(simulation.paths.columns)
    is_default = (
        source != "supuesto"
        and historical_volatility
        and simulation.equity_premium == defaults.equity_premium
        and steps == simulation.periods_per_year
        and scenarios == defaults.simulations
        and simulation.confidence == defaults.confidence
        and simulation.seed == defaults.seed
    )
    seed = simulation.seed if simulation.seed is not None else "sin fijar"
    if source == "supuesto" or not historical_volatility:
        assumption = "retorno y volatilidad indicados por el usuario"
    elif source == MODEL_RETURN:
        assumption = "retorno por tipo libre de riesgo más prima y volatilidad histórica"
    else:
        assumption = "retorno y volatilidad históricos"
    criteria = (
        f"{scenarios:,} escenarios".replace(",", ".")
        + f", {steps} sesiones, confianza del {simulation.confidence * 100:g} %".replace(".", ",")
        + f", semilla {seed} y {assumption}"
    )
    if analysis.units is not None:
        option = "--shares"
        assets = " ".join(f"{s}:{n:g}" for s, n in analysis.units.items())
        if analysis.rebalance == MONTHLY:
            assets += " --rebalance monthly"
    else:
        option = "--assets"
        assets = " ".join(f"{s}:{w:g}" for s, w in analysis.target_weights.items())
    template = texts.SIMULATION_DEFAULT_CRITERIA if is_default else texts.SIMULATION_CUSTOM_CRITERIA
    command = texts.SIMULATION_COMMAND.format(option=option, assets=assets)
    return template.format(criteria=criteria, command=command)


def _sensitivity_row(
    label: str, final: np.ndarray, start: float, confidence: float, real_floor: float
) -> list[str]:
    return [
        label,
        format_number((final < start).mean(), True),
        format_number((final < real_floor).mean() if pd.notna(real_floor) else np.nan, True),
        format_number(np.median(final) / start - 1, True, signed=True),
        format_number(1 - np.quantile(final, 1 - confidence) / start, True),
    ]


def _return_sensitivity(simulation: SimulationResult, inflation: float) -> str:
    """Compara el retorno usado en la simulación con otros supuestos, también en términos reales."""
    start = float(simulation.paths.iloc[0, 0])
    confidence = simulation.confidence
    years = (len(simulation.paths) - 1) / simulation.periods_per_year
    real_floor = start * (1 + inflation) ** years
    source = _return_source(simulation.assumptions)
    used = {MODEL_RETURN: "Tipo libre de riesgo + prima", "histórico": "Histórico"}.get(
        source, "Indicado"
    )
    rows = [
        _sensitivity_row(
            f"{used} (el usado arriba)",
            simulation.paths.iloc[-1].to_numpy(),
            start,
            confidence,
            real_floor,
        )
    ]
    for case, final in simulation.return_sensitivity.items():
        rows.append(_sensitivity_row(SENSITIVITY_CASES[case], final, start, confidence, real_floor))
    table = _table(
        [
            "Retorno anual μ",
            "Prob. de pérdida",
            "Prob. de pérdida real",
            "Variación mediana",
            f"VaR ({100 * confidence:g} %)",
        ],
        rows,
    )
    assumed = (
        texts.REAL_LOSS_INFLATION.format(inflation=format_number(inflation, True))
        if pd.notna(inflation)
        else texts.NO_REAL_LOSS_INFLATION
    )
    return f"{table}\n\n{texts.SENSITIVITY_NOTE.format(inflation=assumed)}"


def _return_note(simulation: SimulationResult) -> str:
    assumptions = simulation.assumptions
    if simulation.risk_free_rate is None:
        return texts.HISTORICAL_RETURN_NOTE
    note = texts.MODEL_RETURN_NOTE
    unclassified = assumptions.index[assumptions["equity_share"].isna()]
    if len(unclassified):
        note += " " + texts.UNCLASSIFIED_NOTE.format(symbols=", ".join(unclassified))
    return note


def _simulation(report: ReportContext) -> str:
    simulation = report.simulation
    if simulation is None:
        return texts.SIMULATION_NOT_CONFIGURED
    analysis = report.analysis
    currency = simulation.currency
    results = simulation.summary()
    confidence = simulation.confidence
    assumptions = simulation.assumptions
    steps = len(simulation.paths) - 1
    lower, upper = f"{100 * (1 - confidence):g}", f"{100 * confidence:g}"
    level = f"{100 * confidence:g} %"
    returns = ", ".join(
        f"{symbol} {format_number(value, True)}"
        for symbol, value in assumptions["annual_return"].items()
    )
    volatilities = ", ".join(
        f"{symbol} {format_number(value, True)}"
        for symbol, value in assumptions["annual_volatility"].items()
    )
    historical_volatility = (assumptions["volatility_source"] == "histórica").all()
    dates = analysis.values.index
    rebalance = (
        texts.SIMULATED_REBALANCE.format(interval=simulation.rebalance_interval)
        if simulation.rebalance_interval
        else texts.SIMULATED_BUY_AND_HOLD
    )
    parameters = [
        ["Método", "Por activos, con sus correlaciones"],
        ["Rebalanceo", rebalance],
        ["Valor inicial", _money(results["initial_value"], currency)],
        [
            "Horizonte",
            f"{steps} sesiones (~{format_number(steps / simulation.periods_per_year)} años)",
        ],
        ["Simulaciones", f"{len(simulation.paths.columns):,}".replace(",", ".")],
        [f"Retorno anual ({_return_source(assumptions)})", returns],
        [
            f"Volatilidad anual ({'histórica' if historical_volatility else 'supuesta'})",
            volatilities,
        ],
        ["Historia usada para estimar", f"{format_date(dates[0])} – {format_date(dates[-1])}"],
        ["Nivel de confianza", level],
        ["Semilla", simulation.seed if simulation.seed is not None else "aleatoria"],
    ]
    if simulation.risk_free_rate is not None:
        shares = ", ".join(
            f"{symbol} {format_number(share, True)}"
            for symbol, share in assumptions["equity_share"].items()
        )
        parameters[5:5] = [
            ["Tipo libre de riesgo actual", format_number(simulation.risk_free_rate, True)],
            ["Prima de riesgo", format_number(simulation.equity_premium, True)],
            ["Parte en renta variable", shares],
        ]
    rule = simulation.rebalance_rule
    if rule is not None and not rule.is_free:
        position = next(i for i, row in enumerate(parameters) if row[0] == "Rebalanceo") + 1
        parameters.insert(
            position,
            [
                "Comisiones de rebalanceo",
                f"{tariff_label(rule.commissions, currency)}, "
                f"{rule_description(rule)}; media pagada por escenario "
                f"{_money(simulation.mean_commissions, currency)}",
            ],
        )
    var = results["value_at_risk"]
    probability = results["probability_of_loss"]
    outcome = _table(
        ["Métrica", "Valor", "Lectura"],
        [
            [
                "Mediana del valor final",
                _money(results["median_final_value"], currency),
                "escenario central, no una predicción",
            ],
            [
                f"Percentiles {lower} y {upper}",
                f"{_money(results['lower_percentile'], currency)} – "
                f"{_money(results['upper_percentile'], currency)}",
                f"el {(2 * confidence - 1) * 100:g} % de los escenarios cae aquí",
            ],
            [
                "Probabilidad de pérdida",
                format_number(probability, True),
                "se pierde en casi 1 de cada 3 escenarios o más" if probability > 0.3 else "",
            ],
            [
                f"VaR al horizonte ({level})",
                _money(var, currency),
                f"con un {level} de confianza no se perdería más de esto"
                if var > 0
                else f"negativo: incluso el percentil {lower} acaba con ganancia",
            ],
            [
                "CVaR al horizonte",
                _money(results["conditional_value_at_risk"], currency),
                "pérdida media en los escenarios peores que el VaR",
            ],
        ],
    )
    return "\n\n".join(
        [
            _simulation_criteria(simulation, analysis),
            "**Parámetros**",
            _table(["Parámetro", "Valor"], parameters),
            texts.SIMULATION_START_NOTE,
            "**Resultados**",
            outcome,
            texts.NOMINAL_SIMULATION_NOTE.format(currency=currency),
            "**Sensibilidad al retorno supuesto**",
            _return_sensitivity(simulation, analysis.metrics["latest_inflation"]),
            _return_note(simulation),
            texts.SIMULATION_LIMITATIONS,
        ]
    )


def _data(report: ReportContext) -> str:
    analysis = report.analysis
    quality = analysis.data_quality
    dates = analysis.values.index
    sessions = len(dates) - 1
    history = (
        f"**Historia común:** {sessions} sesiones "
        f"({format_date(dates[0])} – {format_date(dates[-1])})"
    )
    days = analysis.metrics["history_days"]
    history += texts.SHORT_HISTORY_NOTE if days < analysis.warning_thresholds.short_history else "."
    limit = analysis.warning_thresholds.excluded_dates
    excluded_rows = []
    for symbol, row in quality.iterrows():
        share = row["excluded_observations"] / row["observations"]
        excluded_rows.append(
            [symbol, format_number(share, True), "menos fiable" if share > limit else ""]
        )
    excluded = _table(["Ticker", "% de fechas excluidas", "Lectura"], excluded_rows)
    dropped = int(quality["dropped_rows"].sum())
    cleaning = (
        f"**Limpieza:** solo se usan fechas con precio de todos los activos; {dropped} fechas "
        "descartadas por no tener precio de cierre."
    )
    jumps = analysis.price_jumps
    if not jumps.empty:
        cleaning += (
            " Saltos diarios sospechosos (> 50 %): "
            + ", ".join(
                f"{symbol} {format_date(day)} ({format_number(value, True, signed=True)})"
                for (day, symbol), value in list(jumps.items())[:10]
            )
            + "."
        )
    if analysis.price_column != ADJ_CLOSE:
        cleaning += texts.UNADJUSTED_NOTE.format(symbols=", ".join(quality.index))
    sources = [
        [symbol, f"{SOURCES.get(row['source'], row['source'])} ({symbol})"]
        for symbol, row in quality.iterrows()
    ]
    sources += [
        [label, f"{SOURCES.get(row['source'], row['source'])} ({row['series']})"]
        for label, row in analysis.reference_table.iterrows()
    ]
    data = [notice.message for notice in analysis.notices if notice.kind == "data"]
    method = [notice.message for notice in analysis.notices if notice.kind == "method"]
    issues = [*data, *analysis.metric_notes.values()]
    parts = [
        history,
        excluded,
        cleaning,
        texts.PRICE_BASIS_NOTES[analysis.price_column],
        _table(["Serie", "Fuente"], sources),
    ]
    if issues:
        parts.append("**Incidencias de los datos:**\n\n" + _bullets(dict.fromkeys(issues)))
    else:
        parts.append(texts.NO_DATA_ISSUES)
    if method:
        parts.append("**Notas de metodología:**\n\n" + _bullets(dict.fromkeys(method)))
    return "\n\n".join(parts)


_BUILDERS = {
    "summary": _summary,
    "warnings": _warnings,
    "composition": _composition,
    "returns": _returns,
    "risk": _risk,
    "risk_adjusted": _risk_adjusted,
    "diversification": _diversification,
    "market": _market,
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
    selected = select_sections(sections, detail)
    generated_on = generated_on or datetime.now().astimezone()
    charts = charts or {}
    report = ReportContext(analysis, simulation)
    dates = analysis.values.index
    # La misma estrategia que en el resumen, para que la cabecera no la describa de otra forma.
    strategy = _strategy(analysis).capitalize()
    blocks = [
        "# Informe de cartera",
        f"**Período:** {format_date(dates[0])} — {format_date(dates[-1])} · "
        f"**Divisa:** {analysis.currency} · "
        f"**Precios:** {PRICE_COLUMN_LABELS[analysis.price_column]} · {strategy}  \n"
        f"*Elaborado el {generated_on:%d/%m/%Y a las %H:%M:%S %z}*",
    ]
    # La numeración es la de la estructura completa, también al elegir solo algunas secciones.
    numbers = {key: number for number, key in enumerate(SECTION_TITLES, 1)}
    for key in selected:
        body = _BUILDERS[key](report)
        for chart, file in charts.get(key, {}).items():
            body += f"\n\n![{CHART_TITLES.get(chart, chart)}]({file})"
        title = f"{numbers[key]}. {SECTION_TITLES[key]}"
        if detail == "compact":
            summary = f"<b>{title}</b> — {SECTION_QUESTIONS[key]}"
            blocks.append(f"<details>\n<summary>{summary}</summary>\n\n{body}\n\n</details>")
        else:
            blocks.append(f"## {title}\n\n{body}")
    return "\n\n".join(blocks) + "\n"
