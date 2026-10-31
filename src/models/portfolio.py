"""Cartera definida por pesos objetivo y un capital hipotético de referencia."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from ..constants import CLOSE, DEFAULT_CAPITAL, MONTHLY, PERIODS_PER_YEAR, PriceColumn, Rebalance
from ..errors import PortfolioError
from ..simulation import SimulationInputs, SimulationResult, SimulationSettings, simulate
from ..validation import (
    validate_capital,
    validate_currency_code,
    validate_rebalance,
    validate_symbols,
    validate_weights,
)
from .asset import Asset
from .backtest import backtest_allocation
from .currency import FxRates
from .price_history import period_returns
from .snapshot import read_only

if TYPE_CHECKING:
    from ..analysis.result import PortfolioAnalysis
    from ..analysis.warnings import WarningThresholds
    from .references import MarketReferences


@dataclass(frozen=True)
class Portfolio:
    """target_weights asigna a cada símbolo su peso objetivo; los pesos deben sumar 1.

    Los pesos se guardan como una Series de solo lectura en el orden de los activos. Sin
    reporting_currency, todos los activos deben compartir divisa. La cartera no cambia después
    de crearse: los historiales, los tipos de cambio y los pesos no se pueden modificar, por lo
    que la valoración se calcula una sola vez por columna de precios. Para otra composición,
    crea otra cartera, por ejemplo con dataclasses.replace().
    """

    assets: Sequence[Asset]
    target_weights: Mapping[str, float] | pd.Series
    reporting_currency: str = ""
    fx_rates: FxRates = field(default_factory=FxRates)
    initial_capital: float = DEFAULT_CAPITAL
    rebalance: Rebalance = MONTHLY
    _cache: dict = field(default_factory=dict, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        assets = tuple(self.assets)
        if not assets:
            raise PortfolioError("Indica al menos un activo y su peso.")
        if not all(isinstance(asset, Asset) for asset in assets):
            raise TypeError("Los activos de la cartera deben ser objetos Asset.")
        validate_symbols(asset.symbol for asset in assets)
        object.__setattr__(self, "assets", assets)
        object.__setattr__(self, "target_weights", self._ordered_weights())
        validate_capital(self.initial_capital)
        validate_rebalance(self.rebalance)
        if not isinstance(self.fx_rates, FxRates):
            raise TypeError("fx_rates debe ser FxRates.")
        if self.reporting_currency:
            validate_currency_code(self.reporting_currency, "La divisa del informe")
        if len({asset.currency for asset in assets}) != 1 and not self.reporting_currency:
            raise PortfolioError(
                "Todos los activos deben utilizar la misma divisa y unidad de cotización; en caso "
                "contrario, indica la divisa del informe y los tipos de cambio."
            )
        # Comprueba al crear la cartera que haya fechas comunes y tipos de cambio suficientes.
        self.close_prices()

    @classmethod
    def from_units(
        cls,
        assets: Sequence[Asset],
        units: Mapping[str, float],
        reporting_currency: str = "",
        fx_rates: FxRates | None = None,
    ) -> Portfolio:
        """Cartera sin rebalanceo que empieza con las cantidades indicadas de cada activo.

        El capital inicial es el valor de esas cantidades en la primera fecha común.
        """
        assets = tuple(assets)
        if not assets:
            raise PortfolioError("Indica al menos un activo y su cantidad.")
        fx_rates = fx_rates or FxRates()
        equal = {asset.symbol: 1 / len(assets) for asset in assets}
        first = cls(assets, equal, reporting_currency, fx_rates, rebalance=None).close_prices()
        if set(units) != set(first.columns):
            raise PortfolioError("Indica una cantidad por cada activo.")
        amounts = first.iloc[0] * pd.Series(units, dtype=float)
        capital = float(amounts.sum())
        if not capital > 0:
            raise PortfolioError("Las cantidades deben tener un valor inicial positivo.")
        weights = (amounts / capital).to_dict()
        return cls(
            assets, weights, reporting_currency, fx_rates, initial_capital=capital, rebalance=None
        )

    def _ordered_weights(self) -> pd.Series:
        """Un peso por activo, en su orden; el redondeo admitido se reparte para sumar 1."""
        if not isinstance(self.target_weights, Mapping | pd.Series):
            raise TypeError("Indica los pesos objetivo como un diccionario {símbolo: peso}.")
        weights = dict(self.target_weights)
        symbols = [asset.symbol for asset in self.assets]
        if set(weights) != set(symbols):
            raise PortfolioError("Indica un peso objetivo por cada activo.")
        values = [weights[symbol] for symbol in symbols]
        validate_weights(values)
        ordered = pd.Series(values, index=symbols, dtype=float)
        return read_only(ordered / ordered.sum())

    @property
    def currency(self) -> str:
        return self.reporting_currency or self.assets[0].currency

    @property
    def valuation_date(self) -> pd.Timestamp:
        return self._prices(CLOSE).index[-1]

    @property
    def current_weights(self) -> pd.Series:
        """Pesos al final del histórico, después de la evolución de los precios."""
        return self.holdings()["weight"]

    @property
    def total_value(self) -> float:
        return float(self.holdings()["value"].sum())

    def close_prices(self, column: PriceColumn = CLOSE) -> pd.DataFrame:
        """Precios de las fechas comunes en la divisa de la cartera, sin rellenar huecos."""
        return self._prices(column).copy()

    def position_values(self, price_column: PriceColumn = CLOSE) -> pd.DataFrame:
        """Invierte el capital inicial según los pesos y aplica el rebalanceo mensual."""
        return self._positions(price_column).copy()

    def holdings(self, price_column: PriceColumn = CLOSE) -> pd.DataFrame:
        """Muestra los pesos objetivo y la composición al final del período histórico."""
        values = self._positions(price_column).iloc[-1]
        total = float(values.sum())
        if not np.isfinite(values).all() or not np.isfinite(total) or total <= 0:
            raise PortfolioError("El valor de la cartera debe ser positivo y finito.")
        table = pd.DataFrame(
            {
                "price": self._prices(price_column).iloc[-1],
                "value": values,
                "target_weight": self.target_weights,
                "weight": values / total,
            }
        )
        return table.rename_axis("asset")

    def returns(self, log: bool = False, price_column: PriceColumn = CLOSE) -> pd.DataFrame:
        return period_returns(self._prices(price_column), log)

    def simulation_inputs(self, price_column: PriceColumn = CLOSE) -> SimulationInputs:
        """Parte de las posiciones actuales con los mismos pesos objetivo y rebalanceo."""
        return SimulationInputs(
            prices=self.close_prices(price_column),
            starting_values=self.holdings(price_column)["value"],
            currency=self.currency,
            price_column=price_column,
            rebalance_weights=self.target_weights if self.rebalance == MONTHLY else None,
        )

    def monte_carlo(
        self,
        settings: SimulationSettings | None = None,
        *,
        periods_per_year: int = PERIODS_PER_YEAR,
        price_column: PriceColumn = CLOSE,
        **options,
    ) -> SimulationResult:
        """Simula la cartera desde su valor final; options admite los campos de SimulationSettings."""
        return simulate(
            self.simulation_inputs(price_column),
            SimulationSettings.from_options(settings, **options),
            periods_per_year,
        )

    def analyze(
        self,
        references: MarketReferences | None = None,
        *,
        periods_per_year: int = PERIODS_PER_YEAR,
        price_column: PriceColumn = CLOSE,
        warning_thresholds: WarningThresholds | None = None,
    ) -> PortfolioAnalysis:
        """Analiza la asignación de capital y su rebalanceo sin realizar descargas."""
        from ..analysis.portfolio_analysis import analyze_portfolio

        return analyze_portfolio(
            self,
            references,
            periods_per_year=periods_per_year,
            price_column=price_column,
            warning_thresholds=warning_thresholds,
        )

    def report(
        self,
        references: MarketReferences | None = None,
        *,
        simulation: SimulationResult | None = None,
        simulation_settings: SimulationSettings | None = None,
        sections=None,
        detail: str = "compact",
        directory: str | Path | None = None,
        generated_on: datetime | None = None,
        periods_per_year: int = PERIODS_PER_YEAR,
        price_column: PriceColumn = CLOSE,
        warning_thresholds: WarningThresholds | None = None,
        **simulation_options,
    ) -> Path:
        """Guarda un informe Markdown en español con fecha y gráficos.

        Si el informe incluye la simulación y no se proporciona un resultado, ejecuta
        monte_carlo() con simulation_settings o con sus campos en simulation_options.
        """
        from ..reporting.sections import select_sections

        selected = select_sections(sections, detail, has_simulation=True)
        analysis = self.analyze(
            references,
            periods_per_year=periods_per_year,
            price_column=price_column,
            warning_thresholds=warning_thresholds,
        )
        if simulation is None and "simulation" in selected:
            simulation = self.monte_carlo(
                simulation_settings,
                periods_per_year=periods_per_year,
                price_column=price_column,
                **simulation_options,
            )
        return analysis.report(
            simulation,
            sections=sections,
            detail=detail,
            directory=directory,
            generated_on=generated_on,
        )

    def plots_report(
        self,
        directory: str | Path | None = None,
        show: bool = False,
        *,
        references: MarketReferences | None = None,
        periods_per_year: int = PERIODS_PER_YEAR,
        price_column: PriceColumn = CLOSE,
    ) -> dict:
        """Devuelve todos los gráficos históricos y solo los guarda si se indica una carpeta."""
        analysis = self.analyze(
            references, periods_per_year=periods_per_year, price_column=price_column
        )
        return analysis.plots_report(directory, show)

    def _cached(self, key: tuple, compute):
        """Guarda cada cálculo de la valoración para no repetirlo en cada consulta."""
        if key not in self._cache:
            self._cache[key] = compute()
        return self._cache[key]

    def _prices(self, column: PriceColumn) -> pd.DataFrame:
        return self._cached(("prices", column), lambda: self._aligned_prices(column))

    def _positions(self, column: PriceColumn) -> pd.DataFrame:
        return self._cached(
            ("positions", column),
            lambda: backtest_allocation(
                self._prices(column),
                self.target_weights,
                initial_capital=self.initial_capital,
                rebalance=self.rebalance,
            ),
        )

    def _aligned_prices(self, column: PriceColumn) -> pd.DataFrame:
        """Alinea las fechas comunes antes de calcular rentabilidades, sin rellenar precios."""
        prices = pd.concat(
            [asset.history.closing_prices(column) for asset in self.assets], axis=1, join="inner"
        ).sort_index()
        if prices.empty:
            raise PortfolioError("Los activos no tienen fechas de precios comunes.")
        for asset in self.assets:
            if asset.currency != self.currency:
                prices[asset.symbol] = self.fx_rates.convert(
                    prices[asset.symbol], asset.currency, self.currency
                )
        return prices
