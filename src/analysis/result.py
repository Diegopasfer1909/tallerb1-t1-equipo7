"""Resultados del análisis, independientes de las descargas y su presentación."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd

from ..simulation.result import SimulationResult


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

    @property
    def drawdown(self) -> pd.Series:
        return self.values / self.values.cummax() - 1

    def markdown(self) -> str:
        """Devuelve el informe Markdown en memoria, sin crear archivos."""
        from ..reporting.report import build_report

        return build_report(self)

    def report(
        self,
        generated_on: datetime | None = None,
        simulation: SimulationResult | None = None,
    ) -> Path:
        """Guarda el Markdown y sus imágenes juntos en una carpeta con fecha y hora."""
        from ..reporting.export import save_report

        return save_report(self, generated_on, simulation)

    def plot(self, show: bool = True):
        from ..reporting.plots import plot_analysis

        return plot_analysis(self, show)

    def plots_report(self, path: str | Path | None = None, show: bool = False):
        """Devuelve la figura y solo guarda una imagen si se indica una ruta."""
        destination = Path(path) if path is not None else None
        figure = self.plot(show)
        if destination is not None:
            destination.parent.mkdir(parents=True, exist_ok=True)
            figure.savefig(destination)
        return figure
