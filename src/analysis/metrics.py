"""Cálculos con rentabilidades expresadas como fracción (0.05 equivale al 5 %)."""

from dataclasses import dataclass

import numpy as np
import pandas as pd


def annualized_return(returns: pd.Series, periods_per_year: int) -> float:
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
    El cierre se aproxima con lunes-viernes; no se presume un calendario bursátil.
    """
    if frequency not in ("M", "Y"):
        raise ValueError("frequency debe ser M o Y.")
    returns = values.pct_change(fill_method=None).iloc[1:]
    starts = pd.Series(values.index[:-1], index=returns.index)
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
        records.append(
            {
                "period": period,
                "return": np.nan if skipped else (1 + group).prod() - 1,
                "observations": len(group),
                "partial": start != previous_end or end < period_end or skipped,
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
            "annualized_return": annualized_return(returns, periods_per_year),
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
