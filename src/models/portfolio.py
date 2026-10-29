"""Cartera definida por pesos objetivo y un capital hipotético de referencia."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from ..simulation.monte_carlo import MonteCarloMixin
from ..simulation.result import SimulationResult
from ..validation import validate_symbols, validate_weights
from .asset import Asset
from .market_context import MarketContext
from .price_history import period_returns


@dataclass
class Portfolio(MonteCarloMixin):
    assets: list[Asset]
    allocations: list[float]
    reporting_currency: str = ""
    market_context: MarketContext | None = None

    initial_capital: float = 10_000
    rebalance: str | None = "monthly"

    def __post_init__(self) -> None:
        if not self.assets or len(self.assets) != len(self.allocations):
            raise ValueError("Indica un peso objetivo por cada activo.")
        self.assets = list(self.assets)
        self.allocations = list(self.allocations)
        validate_weights(self.allocations)
        if self.rebalance not in (None, "monthly"):
            raise ValueError("El rebalanceo debe ser mensual o None.")
        if not all(isinstance(asset, Asset) for asset in self.assets):
            raise TypeError("Los activos de la cartera deben ser objetos Asset.")
        validate_symbols(asset.symbol for asset in self.assets)
        currencies = {asset.currency for asset in self.assets}
        if self.reporting_currency and (
            len(self.reporting_currency) != 3
            or not self.reporting_currency.isalpha()
            or not self.reporting_currency.isupper()
        ):
            raise ValueError(
                "La divisa del informe debe ser un código en mayúsculas, por ejemplo EUR."
            )
        if len(currencies) != 1 and not self.reporting_currency:
            raise ValueError(
                "Todos los activos deben utilizar la misma divisa y unidad de cotización; en caso contrario, indica la divisa del informe y los tipos de cambio."
            )
        # Comprueba al crear la cartera que haya fechas comunes y tipos de cambio suficientes.
        self.close_prices()

    @property
    def currency(self) -> str:
        return self.reporting_currency or self.assets[0].currency

    def close_prices(self, column: str = "Close") -> pd.DataFrame:
        """Alinea las fechas comunes antes de calcular rentabilidades, sin rellenar precios."""
        columns = []
        for asset in self.assets:
            columns.append(asset.history.closing_prices(column))
        prices = pd.concat(columns, axis=1, join="inner").sort_index()
        if prices.empty:
            raise ValueError("Los activos no tienen fechas de precios comunes.")
        for asset in self.assets:
            if asset.currency != self.currency:
                context = self.market_context or MarketContext()
                values = prices[asset.symbol]
                if not isinstance(values, pd.Series):
                    raise TypeError("Se esperaba una serie de precios por activo.")
                prices[asset.symbol] = context.convert(values, asset.currency, self.currency)
        return prices

    def analyze(
        self,
        periods_per_year: int = 252,
        price_column: str = "Close",
        concentration_limit: float = 0.4,
    ):
        """Analiza la asignación de capital y su rebalanceo sin realizar descargas."""
        from ..analysis.portfolio_analysis import analyze_portfolio

        return analyze_portfolio(self, periods_per_year, price_column, concentration_limit)

    def report(
        self,
        periods_per_year: int = 252,
        price_column: str = "Close",
        generated_on: datetime | None = None,
        simulation: SimulationResult | None = None,
        **simulation_options,
    ) -> Path:
        """Guarda un informe Markdown en español con fecha y gráficos.

        Sin un resultado previo, simula con los mismos parámetros que monte_carlo()
        (steps, simulations, expected_returns, volatilities, confidence, seed=42).
        """
        if simulation is None:
            simulation_options.setdefault("seed", 42)
            simulation = self.monte_carlo(
                periods_per_year=periods_per_year,
                price_column=price_column,
                **simulation_options,
            )
        return self.analyze(periods_per_year, price_column).report(generated_on, simulation)

    def plots_report(
        self,
        directory: str | Path | None = None,
        show: bool = False,
        periods_per_year: int = 252,
        price_column: str = "Close",
    ):
        """Devuelve todos los gráficos históricos y solo los guarda si se indica una carpeta."""
        return self.analyze(periods_per_year, price_column).plots_report(directory, show)

    @property
    def valuation_date(self) -> pd.Timestamp:
        date = pd.DatetimeIndex(self.close_prices().index)[-1]
        if not isinstance(date, pd.Timestamp):
            raise ValueError("La fecha de valoración no es válida.")
        return date

    @property
    def target_weights(self) -> pd.Series:
        return pd.Series(
            self.allocations, index=[asset.symbol for asset in self.assets], dtype=float
        )

    def position_values(self, price_column: str = "Close") -> pd.DataFrame:
        """Invierte el capital inicial según los pesos y aplica el rebalanceo mensual."""
        from ..analysis.backtest import backtest_allocation

        return backtest_allocation(
            self.close_prices(price_column),
            self.target_weights,
            initial_capital=self.initial_capital,
            rebalance=self.rebalance,
        )

    def holdings(self, price_column: str = "Close") -> pd.DataFrame:
        """Muestra los pesos objetivo y la composición al final del período histórico."""
        values = self.position_values(price_column).iloc[-1]
        table = pd.DataFrame(index=values.index)
        table.index.name = "asset"
        table["price"] = self.close_prices().iloc[-1]
        table["value"] = values
        table["target_weight"] = self.target_weights
        total = float(values.sum())
        if not np.isfinite(values).all() or not np.isfinite(total) or total <= 0:
            raise ValueError("El valor de la cartera debe ser positivo y finito.")
        table["weight"] = values / total
        return table

    @property
    def weights(self) -> pd.Series:
        return self.holdings()["weight"].copy()

    @property
    def total_value(self) -> float:
        return float(self.holdings()["value"].sum())

    def returns(self, log: bool = False, price_column: str = "Close") -> pd.DataFrame:
        return period_returns(self.close_prices(price_column), log)

    def _simulation_inputs(self, price_column: str):
        """Simula las posiciones actuales con los mismos pesos objetivo y rebalanceo."""
        prices = self.close_prices(price_column)
        starting_values = self.holdings(price_column)["value"]
        weights = self.target_weights if self.rebalance == "monthly" else None
        return prices, starting_values, weights
