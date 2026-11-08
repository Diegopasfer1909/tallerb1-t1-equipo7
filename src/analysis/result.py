"""Resultados del análisis, independientes de las descargas.

Los métodos de presentación solo delegan en el paquete reporting.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

import pandas as pd

from ..commissions import RebalanceRule
from ..constants import Rebalance
from ..models.notice import Notice
from ..simulation.result import SimulationResult
from .metrics import (
    DrawdownEpisode,
    MarketContext,
    calendar_returns,
    correlation_pairs,
    drawdown_episode,
    drawdowns,
    price_jumps,
)
from .warnings import RiskWarning, WarningThresholds

# Dividendos en la comparación: en los dos lados, referencia que es un índice o en ninguno.
BenchmarkDividends = Literal["both", "index", "none"]


@dataclass(frozen=True)
class RebalanceCosts:
    """Lo que ha costado rebalancear y si ha compensado frente a comprar y mantener.

    final_value es el valor final con rebalanceo, ya descontadas las comisiones;
    buy_and_hold_value, el de la misma cartera sin reajustes (sin comisiones tras la compra
    inicial, que comparten ambas estrategias). trades es el registro de órdenes.
    """

    rule: RebalanceRule
    rebalances: int
    skipped_orders: int
    commissions: float
    final_value: float
    buy_and_hold_value: float
    initial_capital: float
    trades: pd.DataFrame

    @property
    def orders(self) -> int:
        return len(self.trades)

    @property
    def advantage(self) -> float:
        """Valor final con rebalanceo menos el de comprar y mantener; negativo si no compensó."""
        return self.final_value - self.buy_and_hold_value

    @property
    def gross_advantage(self) -> float:
        """Ventaja aproximada antes de comisiones: indica si son ellas las que la eliminan."""
        return self.advantage + self.commissions

    @property
    def gain(self) -> float:
        """Ganancia de la estrategia con rebalanceo antes de comisiones."""
        return self.final_value + self.commissions - self.initial_capital


@dataclass
class PortfolioAnalysis:
    """notices reúne los avisos de datos y metodología; risk_warnings, las reglas de riesgo.

    metric_notes explica por qué falta cada medida sin calcular, y reference_table cita la
    serie y la fuente de cada referencia utilizada. units es el número de acciones de una
    cartera creada con Portfolio.from_units(), o None si se definió por pesos.
    """

    currency: str
    price_column: str
    periods_per_year: int
    values: pd.Series
    metrics: pd.Series
    holdings: pd.DataFrame
    correlations: pd.DataFrame
    risk_contributions: pd.Series
    sector_weights: pd.Series
    data_quality: pd.DataFrame
    notices: list[Notice]
    metric_notes: dict[str, str]
    reference_table: pd.DataFrame
    asset_details: pd.DataFrame
    asset_prices: pd.DataFrame
    initial_capital: float
    target_weights: pd.Series
    rebalance: Rebalance
    benchmark_prices: pd.Series | None
    risk_warnings: list[RiskWarning]
    market: MarketContext
    currency_weights: pd.Series
    benchmark_name: str
    risk_free_series: str
    warning_thresholds: WarningThresholds
    units: pd.Series | None = None
    # Solo con rebalanceo mensual: comisiones y comparación con comprar y mantener.
    rebalance_costs: RebalanceCosts | None = None
    # Si la comparación con la referencia incluye dividendos; None si no hay referencia.
    benchmark_dividends: BenchmarkDividends | None = None

    @property
    def drawdown(self) -> pd.Series:
        return drawdowns(self.values)

    @property
    def drawdown_episode(self) -> DrawdownEpisode:
        return drawdown_episode(self.values)

    @property
    def monthly_returns(self) -> pd.DataFrame:
        return calendar_returns(self.values, "M")

    @property
    def annual_returns(self) -> pd.DataFrame:
        return calendar_returns(self.values, "Y")

    @property
    def correlation_pairs(self) -> pd.Series:
        return correlation_pairs(self.correlations)

    @property
    def asset_returns(self) -> pd.DataFrame:
        return self.asset_prices.pct_change(fill_method=None).dropna()

    @property
    def price_jumps(self) -> pd.Series:
        return price_jumps(self.asset_prices)

    @property
    def benchmark_symbol(self) -> str | None:
        """Símbolo del índice con el que se compara la cartera, si la comparación fue posible."""
        return None if self.benchmark_prices is None else str(self.benchmark_prices.name)

    @property
    def benchmark_comparison(self) -> pd.DataFrame:
        """Valores comparables: misma divisa, fechas y base de precios."""
        if self.benchmark_prices is None:
            return pd.DataFrame(columns=["portfolio", "benchmark"], dtype=float)
        return pd.concat(
            {"portfolio": self.values, "benchmark": self.benchmark_prices}, axis=1, join="inner"
        ).dropna()

    def markdown(self, *, sections=None, detail: str = "compact") -> str:
        """Devuelve el informe Markdown en memoria, sin crear archivos."""
        from ..reporting.report import build_report

        return build_report(self, sections=sections, detail=detail)

    def report(
        self,
        simulation: SimulationResult | None = None,
        *,
        sections=None,
        detail: str = "compact",
        directory: str | Path | None = None,
        generated_on: datetime | None = None,
    ) -> Path:
        """Guarda el Markdown y sus imágenes juntos en una carpeta con fecha y hora."""
        from ..reporting.export import save_report

        return save_report(
            self,
            simulation,
            sections=sections,
            detail=detail,
            directory=directory,
            generated_on=generated_on,
        )

    def plot(self, show: bool = True):
        from ..reporting.plots import plot_analysis, show_figures

        figure = plot_analysis(self)
        if show:
            show_figures()
        return figure

    def plots_report(self, directory: str | Path | None = None, show: bool = False) -> dict:
        """Devuelve los gráficos de cartera, activos, distribución y riesgo/rentabilidad.

        Solo guarda archivos si se indica una carpeta, con los mismos nombres que el informe.
        """
        from ..reporting.plots import plot_report, save_charts, show_figures

        figures = plot_report(self)
        if directory is not None:
            directory = Path(directory)
            directory.mkdir(parents=True, exist_ok=True)
            save_charts(figures, directory)
        if show:
            show_figures()
        return figures
