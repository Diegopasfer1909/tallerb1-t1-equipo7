"""Cálculos con rentabilidades expresadas como fracción (0.05 equivale al 5 %)."""

import numpy as np
import pandas as pd


def annualized_return(returns: pd.Series, periods_per_year: int) -> float:
    return float((1 + returns).prod() ** (periods_per_year / len(returns)) - 1)


def performance(values: pd.Series, periods_per_year: int) -> pd.Series:
    returns = values.pct_change(fill_method=None).dropna()
    drawdown = values / values.cummax() - 1
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
