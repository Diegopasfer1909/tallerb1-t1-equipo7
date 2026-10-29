"""Consulta y representación de simulaciones, sin descargas ni guardado automático."""

from dataclasses import dataclass

import pandas as pd


@dataclass
class SimulationResult:
    paths: pd.DataFrame
    currency: str
    valuation_date: pd.Timestamp
    assumptions: pd.DataFrame
    correlation: pd.DataFrame
    periods_per_year: int
    price_column: str
    seed: int | None
    starting_values: pd.Series
    rebalance: str | None = None
    target_weights: pd.Series | None = None
    confidence: float = 0.95
    correlation_method: str = "Cholesky"

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
        import matplotlib.pyplot as plt
        from matplotlib.ticker import FuncFormatter

        if isinstance(max_paths, bool) or not isinstance(max_paths, int) or max_paths < 1:
            raise ValueError("max_paths debe ser un entero positivo.")
        figure, axes = plt.subplots(1, 2, figsize=(12, 4))
        self.paths.iloc[:, :max_paths].plot(ax=axes[0], legend=False, alpha=0.25)
        axes[0].set(
            title="Trayectorias simuladas", xlabel="Período", ylabel=f"Valor ({self.currency})"
        )
        axes[1].hist(self.paths.iloc[-1], bins=30, edgecolor="white")
        axes[1].set(
            title="Distribución del valor final",
            xlabel=f"Valor ({self.currency})",
            ylabel="Número de simulaciones",
        )
        for axis in axes:
            for scale in (axis.xaxis, axis.yaxis):
                scale.set_major_formatter(
                    FuncFormatter(lambda value, _: f"{value:g}".replace(".", ","))
                )
        figure.tight_layout()
        if show:
            plt.show()
        return figure
