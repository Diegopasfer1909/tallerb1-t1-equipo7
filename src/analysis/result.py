"""Resultados del análisis, independientes de las descargas y su presentación."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd

from ..simulation.result import SimulationResult
from .metrics import calendar_returns, correlation_pairs, drawdown_episode, drawdowns
from .warnings import RiskWarning


@dataclass
class PortfolioAnalysis:
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
    warnings: list[str]
    reference_names: dict[str, str]
    asset_details: pd.DataFrame
    asset_prices: pd.DataFrame
    metric_notes: dict[str, str] = field(default_factory=dict)
    initial_capital: float = 10_000
    target_weights: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    rebalance: str | None = "monthly"
    benchmark_prices: pd.Series | None = None
    risk_warnings: list[RiskWarning] = field(default_factory=list)

    @property
    def drawdown(self) -> pd.Series:
        return drawdowns(self.values)

    @property
    def drawdown_episode(self):
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
        generated_on: datetime | None = None,
        simulation: SimulationResult | None = None,
        *,
        sections=None,
        detail: str = "compact",
    ) -> Path:
        """Guarda el Markdown y sus imágenes juntos en una carpeta con fecha y hora."""
        from ..reporting.export import save_report

        return save_report(self, generated_on, simulation, sections=sections, detail=detail)

    def plot(self, show: bool = True):
        from ..reporting.plots import plot_analysis

        return plot_analysis(self, show)

    def plots_report(self, directory: str | Path | None = None, show: bool = False) -> dict:
        """Devuelve los gráficos de cartera, activos, distribución y riesgo/rentabilidad.

        Solo guarda archivos si se indica una carpeta, con los mismos nombres que el informe.
        """
        import matplotlib.pyplot as plt

        from ..reporting.plots import plot_report, save_charts

        figures = plot_report(self)
        if directory is not None:
            directory = Path(directory)
            directory.mkdir(parents=True, exist_ok=True)
            save_charts(figures, directory)
        if show:
            plt.show()
        return figures
