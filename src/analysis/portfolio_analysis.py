"""Analiza una asignación de capital con pesos objetivo y rebalanceo mensual."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from ..constants import (
    ADJ_CLOSE,
    CLOSE,
    DAILY_REFERENCE_MAX_AGE_DAYS,
    DAYS_PER_YEAR,
    MONTHLY_REFERENCE_MAX_AGE_DAYS,
    ONE_YEAR_MIN_DAYS,
    PERIODS_PER_YEAR,
    UNKNOWN,
    PriceColumn,
)
from ..errors import PortfolioError
from ..models import EconomicIndicator, FxRates, MarketReferences, Notice, PriceHistory
from ..simulation import estimate_parameters
from ..validation import validate_positive_int
from . import messages
from .metrics import (
    annualized_growth,
    annualized_return,
    beta,
    correlation_pairs,
    drawdown_episode,
    performance,
    risk_adjusted,
    risk_contributions,
)
from .result import PortfolioAnalysis
from .warnings import WarningThresholds, evaluate_risk

if TYPE_CHECKING:
    from ..models import Portfolio

RATE_METRICS = ("sharpe", "sortino", "reference_annualized_return", "excess_annualized_return")
BENCHMARK_METRICS = (
    "comparison_portfolio_annualized_return",
    "benchmark_annualized_return",
    "difference_from_benchmark",
    "beta",
)
INFLATION_METRICS = ("annualized_inflation", "real_annualized_return")
# Base de precios del análisis cuando se usa Adj Close en lugar de Close.
ADJUSTED_GROWTH = "adjusted_growth"
# Fracción mínima de las observaciones esperadas para escalar la dispersión con
# periods_per_year; por debajo, faltan demasiadas fechas comunes.
MIN_SAMPLE_COVERAGE = 0.9


@dataclass
class _Measures:
    """Medidas que dependen de una referencia, con el motivo de las que faltan."""

    values: dict[str, float] = field(default_factory=dict)
    notes: dict[str, str] = field(default_factory=dict)
    notices: list[Notice] = field(default_factory=list)

    @classmethod
    def missing(cls, keys: tuple[str, ...], note: str, notice: str | None = None) -> "_Measures":
        """Ninguna medida del grupo se calcula; cada una explica el motivo."""
        return cls(notes=dict.fromkeys(keys, note), notices=[Notice(notice)] if notice else [])


def _max_age(indicator: EconomicIndicator) -> int:
    """Admite el desfase habitual de publicación de los índices mensuales."""
    if indicator.frequency.lower().startswith("month"):
        return MONTHLY_REFERENCE_MAX_AGE_DAYS
    return DAILY_REFERENCE_MAX_AGE_DAYS


def _reference_rate(
    indicator: EconomicIndicator | None,
    returns: pd.Series,
    periods_per_year: int,
    annualized: float,
) -> _Measures:
    if indicator is None:
        return _Measures.missing(
            RATE_METRICS, messages.NO_RISK_FREE_RATE_NOTE, messages.NO_RISK_FREE_RATE
        )
    if indicator.units.strip().lower() not in ("percent", "%"):
        return _Measures.missing(RATE_METRICS, messages.RATE_UNITS_NOTE, messages.RATE_UNITS)
    rates = indicator.as_of(returns.index, _max_age(indicator)) / 100
    if rates.isna().any() or (rates <= -1).any():
        return _Measures.missing(RATE_METRICS, messages.RATE_STALE_NOTE, messages.RATE_STALE)
    reference = (1 + rates) ** (1 / periods_per_year) - 1
    values = risk_adjusted(returns, reference, periods_per_year)
    values["reference_annualized_return"] = annualized_return(reference, periods_per_year)
    values["excess_annualized_return"] = annualized - values["reference_annualized_return"]
    notes = {}
    if np.isnan(values["sharpe"]):
        notes["sharpe"] = messages.SHARPE_UNDEFINED
    if np.isnan(values["sortino"]):
        notes["sortino"] = messages.SORTINO_UNDEFINED
    return _Measures(values, notes)


def _inflation(
    indicator: EconomicIndicator | None,
    dates: pd.DatetimeIndex,
    annualized: float,
) -> _Measures:
    if indicator is None:
        return _Measures.missing(INFLATION_METRICS, messages.NO_INFLATION_NOTE)
    if "index" not in indicator.units.lower():
        return _Measures.missing(
            INFLATION_METRICS, messages.INFLATION_UNITS_NOTE, messages.INFLATION_UNITS
        )
    levels = indicator.as_of(dates, _max_age(indicator))
    if levels.isna().any() or (levels <= 0).any():
        return _Measures.missing(
            INFLATION_METRICS, messages.INFLATION_STALE_NOTE, messages.INFLATION_STALE
        )
    inflation = annualized_growth(levels)
    return _Measures(
        {
            "annualized_inflation": inflation,
            "real_annualized_return": (1 + annualized) / (1 + inflation) - 1,
        }
    )


def _comparable_benchmark(
    benchmark: PriceHistory,
    dates: pd.DatetimeIndex,
    target: str,
    fx_rates: FxRates,
    price_column: PriceColumn,
) -> pd.Series | None:
    """Precios del índice en las fechas de la cartera y en su divisa, o None si no bastan."""
    try:
        prices = benchmark.closing_prices(price_column).reindex(dates).dropna()
        if len(prices) < 3:
            return None
        return fx_rates.convert(prices, benchmark.profile.currency, target)
    except PortfolioError:
        return None


def _benchmark(
    benchmark: PriceHistory | None,
    values: pd.Series,
    currency: str,
    fx_rates: FxRates,
    price_column: PriceColumn,
) -> tuple[_Measures, pd.Series | None]:
    """Compara la cartera con el índice en sus fechas comunes y en la misma divisa.

    Ambas rentabilidades se anualizan por el tiempo transcurrido entre las mismas fechas
    extremas, aunque el índice no cotice en todas las fechas de la cartera.
    """
    if benchmark is None:
        return _Measures.missing(BENCHMARK_METRICS, messages.NO_BENCHMARK_NOTE), None
    if not benchmark.profile.currency:
        measures = _Measures.missing(
            BENCHMARK_METRICS, messages.BENCHMARK_CURRENCY_NOTE, messages.BENCHMARK_CURRENCY
        )
        return measures, None
    prices = _comparable_benchmark(benchmark, values.index, currency, fx_rates, price_column)
    if prices is None:
        measures = _Measures.missing(
            BENCHMARK_METRICS, messages.BENCHMARK_COVERAGE_NOTE, messages.BENCHMARK_COVERAGE
        )
        return measures, None
    on_benchmark_dates = values.reindex(prices.index)
    market = prices.pct_change(fill_method=None).dropna()
    returns = on_benchmark_dates.pct_change(fill_method=None).dropna()
    portfolio_return = annualized_growth(on_benchmark_dates)
    benchmark_return = annualized_growth(prices)
    measured = {
        "comparison_portfolio_annualized_return": portfolio_return,
        "benchmark_annualized_return": benchmark_return,
        "difference_from_benchmark": portfolio_return - benchmark_return,
        "beta": beta(returns, market),
    }
    notes = {"beta": messages.BETA_UNDEFINED} if np.isnan(measured["beta"]) else {}
    notice = Notice(
        messages.BENCHMARK_COMPARISON.format(symbol=benchmark.symbol, dates=len(prices)),
        kind="method",
    )
    return _Measures(measured, notes, [notice]), prices


def _quality(
    portfolio: "Portfolio", common_dates: pd.DatetimeIndex, price_column: PriceColumn
) -> pd.DataFrame:
    """Cobertura y base de precios de cada activo."""
    records = []
    for asset in portfolio.assets:
        history = asset.history
        basis = ADJUSTED_GROWTH if price_column == ADJ_CLOSE else history.price_basis
        records.append(
            {
                "asset": asset.symbol,
                "source": history.source,
                "quote_currency": asset.currency,
                "observations": len(history.prices),
                "common_observations": len(common_dates),
                "excluded_observations": len(history.prices.index.difference(common_dates)),
                "dropped_rows": history.dropped_rows,
                "partial_history": history.partial_history,
                "price_basis": basis,
                "price_column": price_column,
                "adjusted_close_available": ADJ_CLOSE in history.prices.columns,
                "missing_optional_cells": int(history.prices.isna().sum().sum()),
            }
        )
    return pd.DataFrame(records).set_index("asset")


def _asset_details(
    portfolio: "Portfolio",
    prices: pd.DataFrame,
    periods_per_year: int,
    benchmark_prices: pd.Series | None,
) -> pd.DataFrame:
    """Reúne la ficha y los resultados de cada activo para su presentación."""
    estimates = estimate_parameters(prices.pct_change(fill_method=None).iloc[1:], periods_per_year)
    market = None
    if benchmark_prices is not None:
        market = benchmark_prices.pct_change(fill_method=None).dropna()
    records = []
    for asset in portfolio.assets:
        profile = asset.history.profile
        result = performance(prices[asset.symbol], periods_per_year)
        calculated_beta = np.nan
        if market is not None:
            on_benchmark_dates = prices[asset.symbol].reindex(benchmark_prices.index)
            calculated_beta = beta(on_benchmark_dates.pct_change(fill_method=None).dropna(), market)
        records.append(
            {
                "asset": asset.symbol,
                "name": asset.name,
                "asset_type": asset.asset_type,
                "sector": profile.sector or UNKNOWN,
                "country": profile.country or UNKNOWN,
                "quote_currency": asset.currency,
                "source": asset.history.source,
                "reported_beta": profile.beta,
                "calculated_beta": calculated_beta,
                "market_cap": profile.market_cap,
                "pe_ratio": profile.pe_ratio,
                "total_return": result["total_return"],
                "annualized_return": result["annualized_return"],
                "annualized_volatility": result["annualized_volatility"],
                "max_drawdown": result["max_drawdown"],
                "expected_annual_return": estimates.loc[asset.symbol, "annual_return"],
                "expected_annual_volatility": estimates.loc[asset.symbol, "annual_volatility"],
            }
        )
    return pd.DataFrame(records).set_index("asset")


def _quality_notices(
    quality: pd.DataFrame,
    references: MarketReferences,
    dates: pd.DatetimeIndex,
    periods_per_year: int,
) -> list[Notice]:
    """Avisos de cobertura, frecuencia y ajuste de precios, sin alterar las métricas."""
    notices = []
    # pct_change no sabe cuánto tiempo separa dos filas: la anualización depende de este dato.
    typical_gap = pd.Series(dates).diff().dt.days.median()
    if periods_per_year >= PERIODS_PER_YEAR and typical_gap > 5:
        notices.append(
            Notice(messages.ANNUALIZATION_GAP.format(gap=typical_gap, periods=periods_per_year))
        )
    days = (dates[-1] - dates[0]).days
    if days < ONE_YEAR_MIN_DAYS:
        notices.append(Notice(messages.SHORT_HISTORY.format(days=days)))
    # Duración y tamaño de muestra son cosas distintas: un año puede tener pocas fechas comunes.
    expected = days / DAYS_PER_YEAR * periods_per_year
    if typical_gap <= 5 and len(dates) - 1 < MIN_SAMPLE_COVERAGE * expected:
        notices.append(
            Notice(
                messages.SPARSE_SAMPLE.format(
                    returns=len(dates) - 1, days=days, expected=expected, periods=periods_per_year
                )
            )
        )
    if quality["partial_history"].any():
        notices.append(Notice(messages.PARTIAL_HISTORY))
    unadjusted = quality.index[quality["price_basis"] == "unadjusted"]
    if len(unadjusted):
        notices.append(Notice(messages.UNADJUSTED_PRICES.format(symbols=", ".join(unadjusted))))
    if (quality["price_basis"] == "unknown").any():
        notices.append(Notice(messages.UNKNOWN_ADJUSTMENT))
    for symbol, rows in quality.loc[quality["dropped_rows"] > 0, "dropped_rows"].items():
        notices.append(Notice(messages.DROPPED_ROWS.format(symbol=symbol, rows=rows)))
    if references.inflation is not None or references.risk_free_rate is not None:
        notices.append(Notice(messages.ECONOMIC_DATA_TIMING, kind="method"))
    return notices


def _reference_table(references: MarketReferences, fx_rates: FxRates) -> pd.DataFrame:
    """Series utilizadas como referencia y su fuente, para citarlas en el informe."""
    rows = []
    if references.benchmark is not None:
        benchmark = references.benchmark
        rows.append(("Índice de referencia", benchmark.symbol, benchmark.source))
    if references.inflation is not None:
        inflation = references.inflation
        rows.append(("Inflación", inflation.series_id, inflation.source))
    if references.risk_free_rate is not None:
        rate = references.risk_free_rate
        rows.append(("Tipo de interés de referencia", rate.series_id, rate.source))
    for rate in fx_rates.rates:
        rows.append(
            (
                f"Tipo de cambio {rate.base_currency}/{rate.quote_currency}",
                f"{rate.indicator.series_id}; antigüedad máxima: {rate.max_age_days} días",
                rate.indicator.source,
            )
        )
    return pd.DataFrame(rows, columns=["reference", "series", "source"]).set_index("reference")


def analyze_portfolio(
    portfolio: "Portfolio",
    references: MarketReferences | None = None,
    *,
    periods_per_year: int = PERIODS_PER_YEAR,
    price_column: PriceColumn = CLOSE,
    warning_thresholds: WarningThresholds | None = None,
) -> PortfolioAnalysis:
    """Calcula los resultados históricos sin descargas; las referencias son opcionales."""
    validate_positive_int("periods_per_year", periods_per_year)
    if warning_thresholds is not None and not isinstance(warning_thresholds, WarningThresholds):
        raise TypeError("warning_thresholds debe ser WarningThresholds.")
    if references is not None and not isinstance(references, MarketReferences):
        raise TypeError("references debe ser MarketReferences.")
    thresholds = warning_thresholds or WarningThresholds()
    references = references or MarketReferences()
    prices = portfolio.close_prices(price_column)
    if len(prices) < 3:
        raise PortfolioError(
            "Para realizar el análisis hacen falta precios de todos los activos en al menos "
            "tres fechas."
        )
    values = portfolio.position_values(price_column).sum(axis=1).rename("portfolio_value")
    if not np.isfinite(values).all() or (values <= 0).any():
        raise PortfolioError("Los valores históricos de la cartera deben ser positivos y finitos.")
    returns = values.pct_change(fill_method=None).dropna()
    asset_returns = prices.pct_change(fill_method=None).dropna()
    holdings = portfolio.holdings(price_column)
    weights = holdings["weight"]

    metrics = performance(values, periods_per_year)
    annualized = metrics["annualized_return"]
    # Un índice en otra divisa puede traer en las referencias el tipo de cambio que necesita.
    fx_rates = portfolio.fx_rates.combine(references.fx_rates)
    benchmark, benchmark_prices = _benchmark(
        references.benchmark, values, portfolio.currency, fx_rates, price_column
    )
    measures = [
        _reference_rate(references.risk_free_rate, returns, periods_per_year, annualized),
        _inflation(references.inflation, prices.index, annualized),
        benchmark,
    ]
    for name in (*RATE_METRICS, *BENCHMARK_METRICS, *INFLATION_METRICS):
        metrics[name] = np.nan
    for measure in measures:
        for name, value in measure.values.items():
            metrics[name] = value
    metrics["concentration_hhi"] = (weights**2).sum()
    metrics["effective_asset_count"] = 1 / metrics["concentration_hhi"]

    details = _asset_details(portfolio, prices, periods_per_year, benchmark_prices)
    sector_weights = weights.groupby(details["sector"]).sum().sort_values(ascending=False)
    quality = _quality(portfolio, prices.index, price_column)
    correlations = asset_returns.corr()
    profile_notices = [
        Notice(f"{asset.symbol}: {asset.history.profile.issue}")
        for asset in portfolio.assets
        if asset.history.profile.issue
    ]
    notices = [
        *references.notices,
        *(notice for measure in measures for notice in measure.notices),
        *profile_notices,
        *_quality_notices(quality, references, prices.index, periods_per_year),
    ]
    return PortfolioAnalysis(
        currency=portfolio.currency,
        price_column=price_column,
        periods_per_year=periods_per_year,
        values=values,
        metrics=metrics,
        holdings=holdings,
        correlations=correlations,
        risk_contributions=risk_contributions(asset_returns, weights),
        sector_weights=sector_weights,
        data_quality=quality,
        notices=notices,
        metric_notes={name: note for measure in measures for name, note in measure.notes.items()},
        reference_table=_reference_table(references, fx_rates),
        asset_details=details,
        asset_prices=prices,
        initial_capital=portfolio.initial_capital,
        target_weights=portfolio.target_weights.copy(),
        rebalance=portfolio.rebalance,
        benchmark_prices=benchmark_prices,
        risk_warnings=evaluate_risk(
            metrics,
            weights,
            sector_weights,
            correlation_pairs(correlations),
            drawdown_episode(values),
            thresholds,
        ),
    )
