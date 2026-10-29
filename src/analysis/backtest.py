"""Evalúa una estrategia hipotética con pesos objetivo."""

import numpy as np
import pandas as pd

from ..validation import validate_price_table, validate_target_weights


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
    validate_price_table(prices)
    if len(prices) < 2:
        raise ValueError("La estrategia necesita precios en al menos dos fechas.")
    target = validate_target_weights(weights, prices.columns)
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
    current = initial_capital * target
    months = pd.DatetimeIndex(prices.index).to_period("M")
    for row in range(len(prices)):
        current = current * growth.iloc[row].to_numpy()
        if row + 1 < len(prices):
            month_end = months[row] != months[row + 1]
        else:
            last_date = pd.Timestamp(prices.index[row])
            month_end = (last_date + pd.offsets.BDay()).month != last_date.month
        if rebalance == "monthly" and month_end:
            current = current.sum() * target
        positions[row] = current
    return pd.DataFrame(positions, index=prices.index, columns=prices.columns)
