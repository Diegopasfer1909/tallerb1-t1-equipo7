"""Analiza una asignación de capital con pesos objetivo y rebalanceo mensual."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from ..constants import (
    ADJ_CLOSE,
    CLOSE,
    DAILY_REFERENCE_MAX_AGE_DAYS,
    EUR,
    MONTHLY_REFERENCE_MAX_AGE_DAYS,
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
    MarketContext,
    annualized_return,
    beta,
    correlation_pairs,
    currency_effect,
    drawdown_episode,
    jensen_alpha,
    market_context,
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
INFLATION_METRICS = ("annualized_inflation", "real_annualized_return", "latest_inflation")
BUND_ETF_METRICS = ("bund_etf_annualized_return", "difference_from_bund_etf")
# Base de precios del análisis cuando se usa Adj Close en lugar de Close.
ADJUSTED_GROWTH = "adjusted_growth"


@dataclass
class _Measures:
    """Medidas que dependen de una referencia, con el motivo de las que faltan."""

    values: dict[str, float] = field(default_factory=dict)
    notes: dict[str, str] = field(default_factory=dict)
    notices: list[Notice] = field(default_factory=list)
    series: pd.Series | None = None

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
    return _Measures(values, notes, series=reference)


def _inflation(
    indicator: EconomicIndicator | None,
    dates: pd.DatetimeIndex,
    periods_per_year: int,
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
    inflation = (levels.iloc[-1] / levels.iloc[0]) ** (periods_per_year / (len(dates) - 1)) - 1
    return _Measures(
        {
            "annualized_inflation": inflation,
            "real_annualized_return": (1 + annualized) / (1 + inflation) - 1,
            "latest_inflation": _latest_inflation(indicator),
        }
    )


def _latest_inflation(indicator: EconomicIndicator) -> float:
    """Variación interanual del último dato; NaN si no se ha cargado un año de historia."""
    observed = indicator.values.dropna()
    last = observed.index[-1]
    earlier = observed.loc[: last - pd.DateOffset(years=1)]
    if earlier.empty or (last - earlier.index[-1]).days > 366 + _max_age(indicator):
        return np.nan
    return float(observed.iloc[-1] / earlier.iloc[-1] - 1)


def _bund_etf(
    history: PriceHistory | None,
    values: pd.Series,
    currency: str,
    periods_per_year: int,
    price_column: PriceColumn,
) -> dict[str, float]:
    """Lo que rindió invertir en deuda alemana, con cupones y variación de precio.

    Se compara en las fechas comunes y solo con carteras en euros: en otra divisa las mezclaría.
    """
    if history is None or currency != EUR:
        return {}
    prices = _on_dates(history, values.index, price_column).dropna()
    if len(prices) < 3:
        return {}
    bund_etf = annualized_return(prices.pct_change(fill_method=None).dropna(), periods_per_year)
    portfolio = annualized_return(
        values.reindex(prices.index).pct_change(fill_method=None).dropna(), periods_per_year
    )
    return {
        "bund_etf_annualized_return": bund_etf,
        "difference_from_bund_etf": portfolio - bund_etf,
    }


def _alpha(
    returns: pd.Series,
    benchmark_prices: pd.Series | None,
    reference: pd.Series | None,
    periods_per_year: int,
) -> float:
    if benchmark_prices is None or reference is None:
        return np.nan
    market = benchmark_prices.pct_change(fill_method=None).dropna()
    return jensen_alpha(returns, market, reference, periods_per_year)


def _on_dates(history: PriceHistory | None, dates: pd.DatetimeIndex, column: PriceColumn):
    """Precios externos en las fechas de la cartera, con el último cierre conocido."""
    if history is None:
        return None
    selected = column if column in history.prices.columns else CLOSE
    return history.closing_prices(selected).reindex(dates, method="ffill")


def _market(
    references: MarketReferences,
    portfolio: "Portfolio",
    prices: pd.DataFrame,
    returns: pd.Series,
    periods_per_year: int,
    price_column: PriceColumn,
) -> MarketContext:
    dates = prices.index
    effects = {}
    for asset in portfolio.assets:
        if asset.currency != portfolio.currency:
            local = _on_dates(asset.history, dates, price_column)
            effects[asset.symbol] = currency_effect(local, prices[asset.symbol], periods_per_year)
    vix = references.vix
    brent = references.brent
    return market_context(
        returns,
        vix.as_of(dates, DAILY_REFERENCE_MAX_AGE_DAYS) if vix is not None else None,
        brent.as_of(dates, DAILY_REFERENCE_MAX_AGE_DAYS) if brent is not None else None,
        _on_dates(references.gold, dates, price_column),
        _on_dates(references.bund_etf, dates, price_column),
        pd.Series(effects, dtype=float),
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
    portfolio: "Portfolio",
    periods_per_year: int,
    price_column: PriceColumn,
    benchmark_fx: FxRates,
) -> tuple[_Measures, pd.Series | None]:
    """Compara la cartera con el índice en sus fechas comunes y en la misma divisa."""
    if benchmark is None:
        return _Measures.missing(BENCHMARK_METRICS, messages.NO_BENCHMARK_NOTE), None
    if not benchmark.profile.currency:
        measures = _Measures.missing(
            BENCHMARK_METRICS, messages.BENCHMARK_CURRENCY_NOTE, messages.BENCHMARK_CURRENCY
        )
        return measures, None
    fx_rates = benchmark_fx if benchmark_fx.rates else portfolio.fx_rates
    prices = _comparable_benchmark(
        benchmark, values.index, portfolio.currency, fx_rates, price_column
    )
    if prices is None:
        measures = _Measures.missing(
            BENCHMARK_METRICS, messages.BENCHMARK_COVERAGE_NOTE, messages.BENCHMARK_COVERAGE
        )
        return measures, None
    market = prices.pct_change(fill_method=None).dropna()
    returns = values.reindex(prices.index).pct_change(fill_method=None).dropna()
    portfolio_return = annualized_return(returns, periods_per_year)
    benchmark_return = annualized_return(market, periods_per_year)
    measured = {
        "comparison_portfolio_annualized_return": portfolio_return,
        "benchmark_annualized_return": benchmark_return,
        "difference_from_benchmark": portfolio_return - benchmark_return,
        "beta": beta(returns, market),
    }
    notes = {"beta": messages.BETA_UNDEFINED} if np.isnan(measured["beta"]) else {}
    notice = Notice(messages.BENCHMARK_COMPARISON.format(dates=len(prices)), kind="method")
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
    if len(dates) - 1 < periods_per_year:
        notices.append(Notice(messages.SHORT_HISTORY))
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
        rows.append(("Tipo libre de riesgo", rate.series_id, rate.source))
    for label, indicator in (
        ("VIX", references.vix),
        ("Brent", references.brent),
    ):
        if indicator is not None:
            rows.append((label, indicator.series_id, indicator.source))
    for label, history in (("Oro", references.gold), ("ETF de Bunds", references.bund_etf)):
        if history is not None:
            rows.append((label, history.symbol, history.source))
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
    benchmark, benchmark_prices = _benchmark(
        references.benchmark,
        values,
        portfolio,
        periods_per_year,
        price_column,
        references.benchmark_fx,
    )
    rate = _reference_rate(references.risk_free_rate, returns, periods_per_year, annualized)
    measures = [
        rate,
        _inflation(references.inflation, prices.index, periods_per_year, annualized),
        benchmark,
    ]
    for name in (*RATE_METRICS, *BENCHMARK_METRICS, *INFLATION_METRICS, *BUND_ETF_METRICS):
        metrics[name] = np.nan
    for measure in measures:
        for name, value in measure.values.items():
            metrics[name] = value
    metrics.update(
        _bund_etf(references.bund_etf, values, portfolio.currency, periods_per_year, price_column)
    )
    metrics["alpha"] = _alpha(returns, benchmark_prices, rate.series, periods_per_year)
    metrics["concentration_hhi"] = (weights**2).sum()
    metrics["effective_asset_count"] = 1 / metrics["concentration_hhi"]
    metrics["sessions"] = len(returns)
    pairs = correlation_pairs(asset_returns.corr())
    metrics["correlation_mean"] = pairs.mean() if not pairs.empty else np.nan

    details = _asset_details(portfolio, prices, periods_per_year, benchmark_prices)
    sector_weights = weights.groupby(details["sector"]).sum().sort_values(ascending=False)
    quality = _quality(portfolio, prices.index, price_column)
    correlations = asset_returns.corr()
    market = _market(references, portfolio, prices, returns, periods_per_year, price_column)
    excluded = quality["excluded_observations"] / quality["observations"]
    currency_weights = weights.groupby(details["quote_currency"]).sum().sort_values(ascending=False)
    metric_notes = {name: note for measure in measures for name, note in measure.notes.items()}
    if np.isnan(metrics["alpha"]):
        metric_notes["alpha"] = messages.NO_ALPHA_NOTE
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
        metric_notes=metric_notes,
        reference_table=_reference_table(references, portfolio.fx_rates),
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
            currencies=currency_weights,
            excluded_dates=excluded,
            vix=market.vix_current,
        ),
        market=market,
        currency_weights=currency_weights,
        benchmark_name=_benchmark_name(references.benchmark),
        risk_free_series=references.risk_free_rate.series_id if references.risk_free_rate else "",
        warning_thresholds=thresholds,
    )


def _benchmark_name(benchmark: PriceHistory | None) -> str:
    if benchmark is None:
        return ""
    return benchmark.profile.name or benchmark.symbol
