"""Evalúa una estrategia hipotética con pesos objetivo."""

import numpy as np
import pandas as pd

from ..models.validation import validate_dates


def backtest_allocation(
    prices: pd.DataFrame,
    weights: pd.Series,
    initial_capital: float = 10_000,
    rebalance: str | None = None,
) -> pd.DataFrame:
    """Calcula el valor de cada posición, con reajuste mensual opcional de pesos.

    Los precios deben compartir divisa y fechas. No se incluyen comisiones, impuestos ni flujos.
    Los pesos se aplican en la primera fecha de la estrategia.
    """
    validate_dates(prices.index)
    if (
        not prices.index.is_monotonic_increasing
        or len(prices) < 2
        or prices.columns.has_duplicates
        or prices.shape[1] == 0
    ):
        raise ValueError(
            "Proporciona precios ordenados con al menos dos fechas y activos sin repetir."
        )
    if not np.isfinite(prices.to_numpy(dtype=float)).all() or (prices <= 0).any().any():
        raise ValueError("Los precios deben ser positivos y finitos, en una misma divisa.")
    if not weights.index.is_unique or set(weights.index) != set(prices.columns):
        raise ValueError("Indica exactamente un peso objetivo por activo.")
    weights = weights.reindex(prices.columns).astype(float)
    if (
        not np.isfinite(weights).all()
        or (weights < 0).any()
        or not np.isclose(weights.sum(), 1, rtol=0, atol=1e-10)
    ):
        raise ValueError("Los pesos objetivo deben ser finitos, no negativos y sumar uno.")
    if (
        isinstance(initial_capital, bool)
        or not np.isfinite(initial_capital)
        or initial_capital <= 0
    ):
        raise ValueError("El capital inicial debe ser positivo y finito.")
    if rebalance not in (None, "monthly"):
        raise ValueError("rebalance debe ser None o 'monthly'.")
    growth = prices.pct_change(fill_method=None).fillna(0) + 1
    positions = np.empty(prices.shape)
    current = initial_capital * weights.to_numpy()
    months = pd.DatetimeIndex(prices.index).to_period("M")
    for row in range(len(prices)):
        current = current * growth.iloc[row].to_numpy()
        if row + 1 < len(prices):
            month_end = months[row] != months[row + 1]
        else:
            last_date = pd.Timestamp(prices.index[row])
            month_end = (last_date + pd.offsets.BDay()).month != last_date.month
        if rebalance == "monthly" and month_end:
            current = current.sum() * weights.to_numpy()
        positions[row] = current
    if not np.isfinite(positions).all() or (positions < 0).any():
        raise ValueError("La evolución de la cartera ha producido valores no válidos.")
    return pd.DataFrame(positions, index=prices.index, columns=prices.columns)
