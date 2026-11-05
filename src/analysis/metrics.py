"""Cálculos con rentabilidades expresadas como fracción (0.05 equivale al 5 %).

Contrato temporal: el crecimiento se anualiza con los días naturales transcurridos, por lo que
perder fechas intermedias no lo altera. Las medidas de dispersión (volatilidad, Sharpe, Sortino)
se escalan con periods_per_year y suponen observaciones con esa frecuencia.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..constants import DAYS_PER_YEAR, PERIOD_CLOSE_TOLERANCE_DAYS


def annualized_growth(values: pd.Series) -> float:
    """Crecimiento compuesto entre la primera y la última fecha, expresado por año natural.

    Solo depende de los extremos y del tiempo que los separa, no del número de observaciones.
    """
    days = (values.index[-1] - values.index[0]).days
    if days <= 0:
        return np.nan
    return float((values.iloc[-1] / values.iloc[0]) ** (DAYS_PER_YEAR / days) - 1)


def annualized_return(returns: pd.Series, periods_per_year: int) -> float:
    """Compone rentabilidades por período, como las de un tipo de interés, a una tasa anual."""
    return float((1 + returns).prod() ** (periods_per_year / len(returns)) - 1)


def drawdowns(values: pd.Series) -> pd.Series:
    """Incluye el capital inicial como primer máximo posible."""
    return values / values.cummax() - 1


@dataclass(frozen=True)
class DrawdownEpisode:
    depth: float
    peak: pd.Timestamp | None
    trough: pd.Timestamp | None
    recovery: pd.Timestamp | None
    underwater_days: int


def drawdown_episode(values: pd.Series) -> DrawdownEpisode:
    """Mayor caída; ante máximos empatados, toma el último antes del valle.

    La duración son días naturales desde el pico hasta la recuperación o el fin
    del historial. Una historia sin caídas no tiene un episodio ni fechas.
    """
    series = drawdowns(values)
    depth = float(series.min())
    if depth >= 0:
        return DrawdownEpisode(0.0, None, None, None, 0)
    trough = series.idxmin()
    preceding = values.loc[:trough]
    peak_value = preceding.max()
    peak = preceding[preceding == peak_value].index[-1]
    recovered = values.loc[trough:][values.loc[trough:] >= peak_value]
    recovery = recovered.index[0] if not recovered.empty else None
    end = recovery if recovery is not None else values.index[-1]
    return DrawdownEpisode(depth, peak, trough, recovery, (end - peak).days)


def calendar_returns(values: pd.Series, frequency: str) -> pd.DataFrame:
    """Agrupa retornos por mes (M) o año (Y), sin inventar meses vacíos.

    Los extremos sin cobertura se marcan como parciales. Si un intervalo salta
    un mes/año entero, no se atribuye toda su ganancia al período de llegada.
    El cierre se aproxima con lunes-viernes; no se presume un calendario bursátil, de modo que
    un cierre hasta PERIOD_CLOSE_TOLERANCE_DAYS antes se admite como festivo. En el último
    período se exige la fecha exacta: sin datos posteriores, puede que aún no haya terminado.
    """
    if frequency not in ("M", "Y"):
        raise ValueError("frequency debe ser M o Y.")
    returns = values.pct_change(fill_method=None).iloc[1:]
    starts = pd.Series(values.index[:-1], index=returns.index)
    last_period = returns.index[-1].to_period(frequency)
    tolerance = pd.Timedelta(days=PERIOD_CLOSE_TOLERANCE_DAYS)
    records = []
    for period, group in returns.groupby(returns.index.to_period(frequency)):
        start = starts.loc[group.index[0]]
        end = group.index[-1]
        # Necesitamos el cierre del período anterior para una rentabilidad completa.
        previous_end = pd.offsets.BDay().rollback((period - 1).end_time.normalize())
        period_end = pd.offsets.BDay().rollback(period.end_time.normalize())
        skipped = any(
            begins.to_period(frequency).ordinal < ends.to_period(frequency).ordinal - 1
            for begins, ends in zip(starts.loc[group.index], group.index, strict=True)
        )
        missing_start = not previous_end - tolerance <= start <= previous_end
        allowed_end = period_end if period == last_period else period_end - tolerance
        records.append(
            {
                "period": period,
                "return": np.nan if skipped else (1 + group).prod() - 1,
                "observations": len(group),
                "partial": missing_start or end < allowed_end or skipped,
            }
        )
    return pd.DataFrame(records).set_index("period")


def correlation_pairs(correlations: pd.DataFrame) -> pd.Series:
    """Pares únicos con correlación definida; admite uno o varios activos planos."""
    mask = np.triu(np.ones(correlations.shape, dtype=bool), k=1)
    return correlations.where(mask).stack().dropna().sort_values(ascending=False)


def performance(values: pd.Series, periods_per_year: int) -> pd.Series:
    returns = values.pct_change(fill_method=None).dropna()
    drawdown = drawdowns(values)
    threshold = returns.quantile(0.05)
    return pd.Series(
        {
            "total_return": values.iloc[-1] / values.iloc[0] - 1,
            "annualized_return": annualized_growth(values),
            "annualized_volatility": returns.std() * np.sqrt(periods_per_year),
            "max_drawdown": drawdown.min(),
            "period_var_95_return": threshold,
            "period_cvar_95_return": returns[returns <= threshold].mean(),
        },
        dtype=float,
    )


def risk_adjusted(returns: pd.Series, reference: pd.Series, periods_per_year: int) -> dict:
    """La referencia contiene rentabilidades por período, no tipos anuales en porcentaje."""
    excess = returns - reference
    deviation = float(np.std(excess.to_numpy(dtype=float), ddof=1))
    downside = float(np.sqrt((excess.clip(upper=0) ** 2).mean()))
    return {
        "sharpe": excess.mean() / deviation * np.sqrt(periods_per_year)
        if deviation > 0
        else np.nan,
        "sortino": excess.mean() / downside * np.sqrt(periods_per_year) if downside > 0 else np.nan,
    }


def beta(returns: pd.Series, market: pd.Series) -> float:
    """Sensibilidad frente al índice; NaN si la rentabilidad del índice no varía."""
    variance = market.var()
    return float(returns.cov(market) / variance) if variance > 0 else np.nan


def jensen_alpha(
    returns: pd.Series, market: pd.Series, reference: pd.Series, periods_per_year: float
) -> float:
    """Alfa anual: rentabilidad no explicada por la beta, ambas por encima de la referencia."""
    data = pd.concat({"market": market - reference, "asset": returns - reference}, axis=1).dropna()
    if len(data) < 3 or not data["market"].var() > 0:
        return np.nan
    _, alpha = np.polyfit(data["market"], data["asset"], 1)
    return float(alpha * periods_per_year)


def currency_effect(local: pd.Series, converted: pd.Series) -> float:
    """Rentabilidad anualizada en la divisa de la cartera menos la de la divisa original."""
    return annualized_growth(converted) - annualized_growth(local)


def price_jumps(prices: pd.DataFrame, limit: float = 0.5) -> pd.Series:
    """Rentabilidades diarias extremas, que suelen ser desdoblamientos o errores de la fuente."""
    returns = prices.pct_change(fill_method=None).stack()
    return returns[returns.abs() > limit]


@dataclass(frozen=True)
class MarketContext:
    """Lo que ocurre fuera de la cartera; un dato no disponible queda como None o NaN."""

    vix: pd.Series | None = None
    vix_current: float = np.nan
    vix_mean: float = np.nan
    brent_correlation: float = np.nan
    gold_correlation: float = np.nan
    bund_etf_correlation: float = np.nan
    bund_on_worst_days: float = np.nan
    bund_rolling_correlation: pd.Series | None = None
    bund_etf_prices: pd.Series | None = None
    fx_effect: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))


def market_context(
    returns: pd.Series,
    vix: pd.Series | None,
    brent: pd.Series | None,
    gold: pd.Series | None,
    bund_etf: pd.Series | None,
    fx_effect: pd.Series,
) -> MarketContext:
    """Los precios y el VIX deben estar en las fechas de la cartera, con el último dato conocido."""

    def correlation(prices: pd.Series | None) -> float:
        if prices is None:
            return np.nan
        return float(returns.corr(prices.pct_change(fill_method=None).reindex(returns.index)))

    bund_on_worst_days, rolling = np.nan, None
    if bund_etf is not None:
        bund_returns = bund_etf.pct_change(fill_method=None).reindex(returns.index)
        rolling = returns.rolling(60).corr(bund_returns)
        bund_on_worst_days = float(bund_returns[returns <= returns.quantile(0.05)].mean())
    observed = vix.dropna() if vix is not None else None
    has_vix = observed is not None and not observed.empty
    return MarketContext(
        vix=observed if has_vix else None,
        vix_current=float(observed.iloc[-1]) if has_vix else np.nan,
        vix_mean=float(observed.mean()) if has_vix else np.nan,
        brent_correlation=correlation(brent),
        gold_correlation=correlation(gold),
        bund_etf_correlation=correlation(bund_etf),
        bund_on_worst_days=bund_on_worst_days,
        bund_rolling_correlation=rolling,
        bund_etf_prices=bund_etf,
        fx_effect=fx_effect,
    )


def risk_contributions(returns: pd.DataFrame, weights: pd.Series) -> pd.Series:
    """Contribuciones a la varianza con pesos actuales y covarianza histórica."""
    weights = weights.reindex(returns.columns)
    covariance = returns.cov().to_numpy(dtype=float)
    amounts = weights.to_numpy(dtype=float)
    variance = float(amounts @ covariance @ amounts)
    if variance <= 0 or not np.isfinite(variance):
        return pd.Series(np.nan, index=weights.index, name="risk_share")
    shares = amounts * (covariance @ amounts) / variance
    return pd.Series(shares, index=weights.index, name="risk_share")
