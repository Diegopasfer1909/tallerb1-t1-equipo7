"""Evalúa una estrategia hipotética con pesos objetivo."""

import numpy as np
import pandas as pd

from ..constants import DEFAULT_CAPITAL, MONTHLY, Rebalance
from ..errors import PortfolioError
from ..validation import (
    validate_capital,
    validate_price_table,
    validate_rebalance,
    validate_target_weights,
)


def backtest_allocation(
    prices: pd.DataFrame,
    weights: pd.Series,
    initial_capital: float = DEFAULT_CAPITAL,
    rebalance: Rebalance = None,
) -> pd.DataFrame:
    """Calcula el valor de cada posición, con reajuste mensual opcional de pesos.

    Los precios deben compartir divisa y fechas. No se incluyen comisiones, impuestos ni flujos.
    Los pesos se aplican en la primera fecha de la estrategia.
    """
    validate_price_table(prices)
    if len(prices) < 2:
        raise PortfolioError("La estrategia necesita precios en al menos dos fechas.")
    target = validate_target_weights(weights, prices.columns)
    validate_capital(initial_capital)
    validate_rebalance(rebalance)
    growth = (prices.pct_change(fill_method=None).fillna(0) + 1).to_numpy()
    month_ends = _month_ends(pd.DatetimeIndex(prices.index))
    positions = np.empty(prices.shape)
    current = initial_capital * target
    for row, factors in enumerate(growth):
        current = current * factors
        if rebalance == MONTHLY and month_ends[row]:
            current = current.sum() * target
        positions[row] = current
    return pd.DataFrame(positions, index=prices.index, columns=prices.columns)


def _month_ends(dates: pd.DatetimeIndex) -> np.ndarray:
    """Última fecha disponible de cada mes; la final solo si es el último día hábil del mes."""
    months = dates.to_period("M")
    ends = np.append(months[:-1] != months[1:], False)
    last = dates[-1]
    ends[-1] = (last + pd.offsets.BDay()).month != last.month
    return ends
