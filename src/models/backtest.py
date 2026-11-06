"""Evalúa una estrategia hipotética con pesos objetivo."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..commissions import RebalanceRule, rebalance_step
from ..constants import DEFAULT_CAPITAL, MONTHLY, Rebalance
from ..errors import PortfolioError
from ..validation import (
    validate_capital,
    validate_price_table,
    validate_rebalance,
    validate_target_weights,
)

TRADE_COLUMNS = ["date", "asset", "amount", "commission"]


@dataclass(frozen=True)
class BacktestResult:
    """positions es el valor de cada posición por fecha; trades, las órdenes de rebalanceo.

    Cada orden indica la fecha, el activo, el importe comprado (+) o vendido (−) y su comisión.
    rebalance_dates son los cierres de mes en que se ha reajustado y skipped_orders, las
    órdenes descartadas porque su comisión superaba el máximo de la regla.
    """

    positions: pd.DataFrame
    trades: pd.DataFrame
    rebalance_dates: pd.DatetimeIndex
    skipped_orders: int

    @property
    def total_commissions(self) -> float:
        return float(self.trades["commission"].sum())


def backtest_allocation(
    prices: pd.DataFrame,
    weights: pd.Series,
    initial_capital: float = DEFAULT_CAPITAL,
    rebalance: Rebalance = None,
    rule: RebalanceRule | None = None,
) -> pd.DataFrame:
    """Calcula el valor de cada posición, con reajuste mensual opcional de pesos.

    Los precios deben compartir divisa y fechas. Sin regla no se incluyen comisiones; en ningún
    caso impuestos ni flujos. Los pesos se aplican en la primera fecha de la estrategia.
    """
    return backtest_with_costs(prices, weights, initial_capital, rebalance, rule).positions


def backtest_with_costs(
    prices: pd.DataFrame,
    weights: pd.Series,
    initial_capital: float = DEFAULT_CAPITAL,
    rebalance: Rebalance = None,
    rule: RebalanceRule | None = None,
) -> BacktestResult:
    """Como backtest_allocation(), y además registra las órdenes y comisiones de cada reajuste.

    La compra inicial no paga comisión: sería la misma con o sin rebalanceo y no cambia la
    decisión de rebalancear.
    """
    validate_price_table(prices)
    if len(prices) < 2:
        raise PortfolioError("La estrategia necesita precios en al menos dos fechas.")
    target = validate_target_weights(weights, prices.columns)
    validate_capital(initial_capital)
    validate_rebalance(rebalance)
    rule = rule or RebalanceRule()
    growth = (prices.pct_change(fill_method=None).fillna(0) + 1).to_numpy()
    trades = []
    dates = []
    skipped = 0
    current = initial_capital * target
    if rebalance != MONTHLY:
        # Sin reajustes cada posición crece solo con su precio: basta el producto acumulado.
        positions = current * np.cumprod(growth, axis=0)
        return _result(prices, positions, trades, dates, skipped)
    month_ends = _month_ends(pd.DatetimeIndex(prices.index))
    positions = np.empty(prices.shape)
    for row, factors in enumerate(growth):
        current = current * factors
        if month_ends[row]:
            step = rebalance_step(current, target, rule)
            current = step.values[0]
            skipped += int(step.skipped[0])
            if step.rebalanced[0]:
                date = prices.index[row]
                dates.append(date)
                trades.extend(
                    (date, symbol, amount, fee)
                    for symbol, amount, fee in zip(
                        prices.columns, step.orders[0], step.commissions[0], strict=True
                    )
                    if amount != 0
                )
        positions[row] = current
    return _result(prices, positions, trades, dates, skipped)


def _result(prices, positions, trades, dates, skipped) -> BacktestResult:
    """Empaqueta posiciones y órdenes con las fechas y activos de la tabla de precios."""
    return BacktestResult(
        pd.DataFrame(positions, index=prices.index, columns=prices.columns),
        pd.DataFrame(trades, columns=TRADE_COLUMNS).astype({"amount": float, "commission": float}),
        pd.DatetimeIndex(dates),
        skipped,
    )


def _month_ends(dates: pd.DatetimeIndex) -> np.ndarray:
    """Última fecha disponible de cada mes; la final solo si es el último día hábil del mes."""
    months = dates.to_period("M")
    ends = np.append(months[:-1] != months[1:], False)
    last = dates[-1]
    ends[-1] = (last + pd.offsets.BDay()).month != last.month
    return ends
