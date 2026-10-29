"""Analiza una asignación de capital con pesos objetivo y rebalanceo mensual."""

from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from ..models.market_context import MarketContext
from ..simulation.monte_carlo import estimate_parameters
from .metrics import annualized_return, performance, risk_adjusted, risk_contributions
from .result import PortfolioAnalysis

if TYPE_CHECKING:
    from ..models.portfolio import Portfolio


RATE_METRICS = ("sharpe", "sortino", "reference_annualized_return", "excess_annualized_return")
BENCHMARK_METRICS = (
    "comparison_portfolio_annualized_return",
    "benchmark_annualized_return",
    "difference_from_benchmark",
    "beta",
)
INFLATION_METRICS = ("annualized_inflation", "real_annualized_return")


def _reference_on_dates(indicator, dates: pd.DatetimeIndex) -> pd.Series:
    """Admite el desfase habitual de los índices mensuales con un límite de antigüedad."""
    age = 75 if indicator.frequency.lower().startswith("month") else 45
    return indicator.values.dropna().reindex(
        dates, method="ffill", tolerance=pd.Timedelta(days=age)
    )


def _add_reference_rate(metrics, context, returns, periods_per_year, warnings, notes):
    indicator = context.risk_free_rate
    if indicator is None:
        warnings.append(
            "No se ha proporcionado un tipo de interés de referencia. No se calculan las ratios de Sharpe y Sortino ni se presupone un tipo del 0 %."
        )
        return
    if indicator.units.strip().lower() not in ("percent", "%"):
        for key in RATE_METRICS:
            notes[key] = (
                "La serie de referencia debe expresar un tipo de interés anual en porcentaje."
            )
        warnings.append(
            "El tipo de interés de referencia debe ser una tasa anual expresada en porcentaje. No se calculan las medidas de rentabilidad ajustada al riesgo."
        )
        return
    rates = _reference_on_dates(indicator, returns.index) / 100
    if rates.isna().any() or (rates <= -1).any():
        for key in RATE_METRICS:
            notes[key] = (
                "Faltan datos válidos del tipo de interés para algunas fechas, o los disponibles son demasiado antiguos."
            )
        warnings.append(
            "No hay datos válidos y suficientemente recientes del tipo de interés para todo el período. Las medidas que dependen de él no se han podido calcular."
        )
        return
    reference = (1 + rates) ** (1 / periods_per_year) - 1
    metrics.update(risk_adjusted(returns, reference, periods_per_year))
    metrics["reference_annualized_return"] = annualized_return(reference, periods_per_year)
    metrics["excess_annualized_return"] = (
        metrics["annualized_return"] - metrics["reference_annualized_return"]
    )
    notes["sharpe"] = (
        "La diferencia de rentabilidad respecto a la referencia no varía durante el período. La ratio de Sharpe no puede calcularse porque su denominador es cero."
    )
    notes["sortino"] = (
        "La rentabilidad no cae por debajo de la referencia en ningún período. La ratio de Sortino no puede calcularse porque su denominador es cero."
    )


def _add_inflation(metrics, context, dates, periods_per_year, warnings, notes):
    indicator = context.inflation
    if indicator is None:
        return
    if "index" not in indicator.units.lower():
        notes["annualized_inflation"] = notes["real_annualized_return"] = (
            "La serie disponible no es un índice de precios de consumo."
        )
        warnings.append(
            "Para calcular la inflación se necesita un índice de precios de consumo, no una tasa de inflación expresada en porcentaje."
        )
        return
    levels = _reference_on_dates(indicator, dates)
    if levels.isna().any() or (levels <= 0).any():
        notes["annualized_inflation"] = notes["real_annualized_return"] = (
            "Faltan datos válidos del índice de precios para algunas fechas, o los disponibles son demasiado antiguos."
        )
        warnings.append(
            "No hay datos válidos y suficientemente recientes del índice de precios para todo el período. No se ha podido calcular la rentabilidad real."
        )
        return
    inflation = (levels.iloc[-1] / levels.iloc[0]) ** (periods_per_year / (len(dates) - 1)) - 1
    metrics["annualized_inflation"] = inflation
    metrics["real_annualized_return"] = (1 + metrics["annualized_return"]) / (1 + inflation) - 1


def _add_benchmark(
    metrics, portfolio, context, values, periods_per_year, price_column, warnings, notes
):
    benchmark = context.benchmark
    if benchmark is None:
        return
    currency = benchmark.info.get("currency") or benchmark.info.get("Currency")
    if not currency:
        for key in BENCHMARK_METRICS:
            notes[key] = "No consta la divisa del índice de referencia."
        warnings.append(
            "No consta la divisa del índice de referencia. No se realiza la comparación."
        )
        return
    try:
        prices = benchmark.closing_prices(price_column).reindex(values.index).dropna()
        if len(prices) < 3:
            raise ValueError(
                "Para realizar la comparación hacen falta precios de ambos en al menos tres fechas."
            )
        prices = context.convert(prices, currency, portfolio.currency)
    except ValueError:
        for key in BENCHMARK_METRICS:
            notes[key] = (
                "Faltan precios comparables o tipos de cambio del índice para algunas fechas."
            )
        warnings.append(
            "No se realiza la comparación con el índice de referencia: comprueba la cobertura de fechas, los precios disponibles y los tipos de cambio."
        )
        return
    market = prices.pct_change(fill_method=None).dropna()
    returns = values.reindex(prices.index).pct_change(fill_method=None).dropna()
    metrics["comparison_portfolio_annualized_return"] = annualized_return(returns, periods_per_year)
    metrics["benchmark_annualized_return"] = annualized_return(market, periods_per_year)
    metrics["difference_from_benchmark"] = (
        metrics["comparison_portfolio_annualized_return"] - metrics["benchmark_annualized_return"]
    )
    variance = market.var()
    metrics["beta"] = returns.cov(market) / variance if variance > 0 else np.nan
    notes["beta"] = (
        "La rentabilidad del índice de referencia no varía durante el período. No se puede calcular la beta porque la varianza del índice es cero."
    )
    warnings.append(
        f"Comparación con el índice basada en {len(prices)} fechas comunes, con la misma divisa y columna de precios. Revisa si el índice incorpora dividendos."
    )
    return prices


def _quality(portfolio, common_dates, price_column):
    records = []
    for asset in portfolio.assets:
        history = asset.history
        records.append(
            {
                "asset": asset.symbol,
                "source": history.source,
                "quote_currency": asset.currency,
                "observations": len(history.prices),
                "common_observations": len(common_dates),
                "excluded_observations": len(history.prices.index.difference(common_dates)),
                "filled_asset_prices": 0,
                "partial_history": bool(history.info.get("partial_history", False)),
                "price_basis": "adjusted growth proxy"
                if price_column == "Adj Close"
                else history.info.get("price_adjustment", "unknown"),
                "price_column": price_column,
                "adjusted_close_available": "Adj Close" in history.prices.columns,
                "missing_optional_cells": int(history.prices.isna().sum().sum()),
            }
        )
    return pd.DataFrame(records).set_index("asset")


def _numeric_info(info: dict, *keys: str) -> float:
    """Acepta cifras del proveedor en texto; una beta nula o negativa es válida."""
    for key in keys:
        value = info.get(key)
        if value is None or isinstance(value, bool):
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if np.isfinite(number):
            return number
    return float("nan")


def _asset_details(portfolio, prices, periods_per_year, benchmark_prices):
    """Reúne la ficha y los resultados de cada activo para su presentación."""
    records = []
    returns = prices.pct_change(fill_method=None).iloc[1:]
    estimates = estimate_parameters(returns, periods_per_year)
    benchmark_returns = None
    if benchmark_prices is not None:
        benchmark_returns = benchmark_prices.pct_change(fill_method=None).dropna()
    for asset in portfolio.assets:
        info = asset.history.info
        result = performance(prices[asset.symbol], periods_per_year)
        beta = np.nan
        if (
            benchmark_prices is not None
            and benchmark_returns is not None
            and benchmark_returns.var() > 0
        ):
            returns = (
                prices[asset.symbol]
                .reindex(benchmark_prices.index)
                .pct_change(fill_method=None)
                .dropna()
            )
            beta = returns.cov(benchmark_returns) / benchmark_returns.var()
        records.append(
            {
                "asset": asset.symbol,
                "name": asset.name,
                "asset_type": asset.asset_type,
                "sector": info.get("sector") or info.get("Sector") or "Unknown",
                "country": info.get("country") or info.get("Country") or "Unknown",
                "quote_currency": asset.currency,
                "source": asset.history.source,
                "reported_beta": _numeric_info(info, "beta", "Beta", "beta3Year"),
                "calculated_beta": beta,
                "market_cap": _numeric_info(info, "marketCap", "MarketCapitalization"),
                "pe_ratio": _numeric_info(info, "trailingPE", "PERatio"),
                "total_return": result["total_return"],
                "annualized_return": result["annualized_return"],
                "annualized_volatility": result["annualized_volatility"],
                "max_drawdown": result["max_drawdown"],
                "expected_annual_return": estimates.loc[asset.symbol, "annual_return"],
                "expected_annual_volatility": estimates.loc[asset.symbol, "annual_volatility"],
            }
        )
    return pd.DataFrame(records).set_index("asset")


def _missing_reference_notes() -> dict[str, str]:
    """Explica qué referencia falta para cada medida opcional."""
    reasons = [
        (
            RATE_METRICS,
            "No se ha cargado un tipo de interés de referencia. Consulta las incidencias de descarga y la configuración de FRED.",
        ),
        (
            BENCHMARK_METRICS,
            "No se ha cargado un índice de referencia. Consulta las incidencias de descarga y las referencias configuradas para la divisa del informe.",
        ),
        (
            INFLATION_METRICS,
            "No se ha cargado un índice de precios de consumo. Consulta las incidencias de descarga y la configuración de FRED.",
        ),
    ]
    return {key: reason for keys, reason in reasons for key in keys}


def _quality_warnings(
    quality, context, weights, observation_count, periods_per_year, concentration_limit
):
    """Reúne avisos de cobertura y concentración sin alterar las métricas."""
    warnings = []
    if observation_count < periods_per_year:
        warnings.append(
            "El historial contiene menos de un año de datos. Las estimaciones anuales pueden variar mucho según el período elegido."
        )
    if weights.max() > concentration_limit:
        warnings.append(
            f"Una posición supera el umbral orientativo de concentración del {concentration_limit * 100:.0f} %."
        )
    if quality["partial_history"].to_numpy().any():
        warnings.append(
            "Al menos un proveedor ha devuelto solo una parte del historial solicitado."
        )
    if ((quality["source"] == "alpha_vantage") & (quality["price_basis"] == "unadjusted")).any():
        warnings.append(
            "Los precios diarios de Alpha Vantage se utilizan sin ajustar. Un desdoblamiento puede "
            "producir un salto en los precios que distorsione las rentabilidades, la volatilidad "
            "y los parámetros de la simulación. Los resultados pueden diferir de los obtenidos "
            "con los cierres de Yahoo, que sí están ajustados por desdoblamientos."
        )
    if (quality["price_basis"] == "unknown").to_numpy().any():
        warnings.append(
            "El proveedor no indica si algunos precios están ajustados. Conviene comprobar cómo se han tratado los dividendos y los desdoblamientos."
        )
    if context.inflation is not None or context.risk_free_rate is not None:
        warnings.append(
            "Los datos económicos se sitúan en la fecha a la que corresponden, aunque se publicaran más tarde, y pueden incluir revisiones posteriores. El análisis describe el pasado; no reconstruye la información disponible en cada momento."
        )
    return warnings


def _reference_names(context: MarketContext) -> dict[str, str]:
    references = {}
    if context.benchmark is not None:
        references["Índice de referencia"] = context.benchmark.symbol
    if context.inflation is not None:
        references["Inflación"] = context.inflation.series_id
    if context.risk_free_rate is not None:
        references["Tipo de interés de referencia"] = context.risk_free_rate.series_id
    for rate in context.exchange_rates:
        references[f"Tipo de cambio {rate.base_currency}/{rate.quote_currency}"] = (
            f"{rate.indicator.series_id}; antigüedad máxima: {rate.max_age_days} días"
        )
    return references


def analyze_portfolio(
    portfolio: "Portfolio",
    periods_per_year: int = 252,
    price_column: str = "Close",
    concentration_limit: float = 0.4,
) -> PortfolioAnalysis:
    if (
        isinstance(periods_per_year, bool)
        or not isinstance(periods_per_year, int)
        or periods_per_year < 1
    ):
        raise ValueError("periods_per_year debe ser un entero positivo.")
    if (
        isinstance(concentration_limit, bool)
        or not np.isfinite(concentration_limit)
        or not 0 < concentration_limit <= 1
    ):
        raise ValueError("concentration_limit debe ser mayor que cero y menor o igual que uno.")
    prices = portfolio.close_prices(price_column)
    if len(prices) < 3:
        raise ValueError(
            "Para realizar el análisis hacen falta precios de todos los activos en al menos tres fechas."
        )
    positions = portfolio.position_values(price_column)
    values = positions.sum(axis=1).rename("portfolio_value")
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError("Los valores históricos de la cartera deben ser positivos y finitos.")
    returns = values.pct_change(fill_method=None).dropna()
    asset_returns = prices.pct_change(fill_method=None).dropna()
    metrics = performance(values, periods_per_year)
    for name in (*RATE_METRICS, *BENCHMARK_METRICS, *INFLATION_METRICS):
        metrics[name] = np.nan
    context = portfolio.market_context or MarketContext()
    warnings = list(context.issues)
    notes = _missing_reference_notes()
    _add_reference_rate(metrics, context, returns, periods_per_year, warnings, notes)
    _add_inflation(metrics, context, prices.index, periods_per_year, warnings, notes)
    benchmark_prices = _add_benchmark(
        metrics, portfolio, context, values, periods_per_year, price_column, warnings, notes
    )
    for asset in portfolio.assets:
        if asset.history.info.get("metadata_issue"):
            warnings.append(f"{asset.symbol}: {asset.history.info['metadata_issue']}")
    holdings = portfolio.holdings(price_column)
    weights = holdings["weight"]
    if not isinstance(weights, pd.Series):
        raise TypeError("Se esperaba un peso actual por activo.")
    metrics["concentration_hhi"] = (weights**2).sum()
    metrics["effective_asset_count"] = 1 / metrics["concentration_hhi"]
    sectors = pd.Series(
        {
            asset.symbol: asset.history.info.get("sector")
            or asset.history.info.get("Sector")
            or "Unknown"
            for asset in portfolio.assets
        }
    )
    sector_weights = pd.Series(weights.groupby(sectors).sum()).sort_values(ascending=False)
    quality = _quality(portfolio, prices.index, price_column)
    warnings.extend(
        _quality_warnings(
            quality, context, weights, len(returns), periods_per_year, concentration_limit
        )
    )
    missing_metrics = metrics.index[metrics.isna().to_numpy()]
    notes = {key: reason for key, reason in notes.items() if key in missing_metrics}
    return PortfolioAnalysis(
        currency=portfolio.currency,
        price_column=price_column,
        periods_per_year=periods_per_year,
        values=values,
        metrics=metrics,
        holdings=holdings,
        correlations=asset_returns.corr(),
        risk_contributions=risk_contributions(asset_returns, weights),
        sector_weights=sector_weights,
        data_quality=quality,
        warnings=warnings,
        reference_names=_reference_names(context),
        asset_details=_asset_details(portfolio, prices, periods_per_year, benchmark_prices),
        asset_prices=prices.copy(),
        metric_notes=notes,
        initial_capital=portfolio.initial_capital,
        target_weights=portfolio.target_weights,
        rebalance=portfolio.rebalance,
    )
