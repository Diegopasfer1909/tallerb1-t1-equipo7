"""Resultado de una simulación, sin descargas ni guardado automático."""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..commissions import RebalanceRule
from ..constants import DAYS_PER_YEAR, Rebalance


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
    # Valores finales con otros retornos, para contrastar el supuesto utilizado.
    return_sensitivity: dict[str, np.ndarray] = field(default_factory=dict)
    risk_free_rate: float | None = None
    equity_premium: float | None = None
    # Regla de reajuste (comisiones, banda y coste máximo por orden), si se rebalancea, y
    # comisiones pagadas en cada escenario; ya están descontadas de paths.
    rebalance_rule: RebalanceRule | None = None
    commissions: pd.Series | None = None
    # Primera y última fecha de los precios con los que se estimaron σ y las correlaciones, y
    # número de rentabilidades utilizadas.
    estimation_start: pd.Timestamp | None = None
    estimation_end: pd.Timestamp | None = None
    estimation_returns: int | None = None

    @property
    def estimation_years(self) -> float:
        """Años naturales entre la primera y la última fecha de la estimación; NaN si no consta."""
        if self.estimation_start is None or self.estimation_end is None:
            return float("nan")
        return (self.estimation_end - self.estimation_start).days / DAYS_PER_YEAR

    @property
    def mean_commissions(self) -> float:
        """Comisión media pagada por escenario; 0 si no se rebalancea."""
        return 0.0 if self.commissions is None else float(self.commissions.mean())

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
