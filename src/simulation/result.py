"""Resultado de una simulación, sin descargas ni guardado automático."""

from dataclasses import dataclass

import pandas as pd

from ..constants import Rebalance


@dataclass
class SimulationResult:
    """rebalance_interval es el número de períodos simulados entre reajustes, si los hay."""

    paths: pd.DataFrame
    currency: str
    valuation_date: pd.Timestamp
    assumptions: pd.DataFrame
    correlation: pd.DataFrame
    periods_per_year: int
    price_column: str
    seed: int | None
    starting_values: pd.Series
    rebalance: Rebalance
    target_weights: pd.Series | None
    rebalance_interval: int | None
    confidence: float
    correlation_method: str

    def summary(self) -> pd.Series:
        initial = float(self.paths.iloc[0, 0])
        final = self.paths.iloc[-1]
        lower = final.quantile(1 - self.confidence)
        upper = final.quantile(self.confidence)
        return pd.Series(
            {
                "initial_value": initial,
                "mean_final_value": final.mean(),
                "median_final_value": final.median(),
                "lower_percentile": lower,
                "upper_percentile": upper,
                "mean_return": final.mean() / initial - 1,
                "probability_of_loss": (final < initial).mean(),
                "value_at_risk": initial - lower,
                "conditional_value_at_risk": initial - final[final <= lower].mean(),
            },
            dtype=float,
        )

    def plot(self, show: bool = True, max_paths: int = 100):
        """Trayectorias y distribución del valor final; show las muestra en pantalla."""
        from ..reporting.plots import plot_simulation, show_figures

        figure = plot_simulation(self, max_paths)
        if show:
            show_figures()
        return figure
