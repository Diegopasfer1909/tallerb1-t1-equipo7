"""Guarda el informe Markdown y las imágenes que utiliza."""

from datetime import datetime
from pathlib import Path

import numpy as np

from .plots import plot_assets, plot_distribution
from .report import build_report

REPORTS_DIR = Path(__file__).resolve().parents[2] / "informes"


def save_report(
    analysis,
    generated_on: datetime | None = None,
    simulation=None,
) -> Path:
    import matplotlib.pyplot as plt

    generated_on = generated_on or datetime.now().astimezone()
    if simulation is not None:
        if (
            simulation.currency != analysis.currency
            or simulation.valuation_date != analysis.values.index[-1]
        ):
            raise ValueError(
                "La simulación debe utilizar la misma divisa y fecha de valoración que el informe."
            )
        if (
            set(simulation.assumptions.index) != set(analysis.holdings.index)
            or not np.allclose(
                simulation.starting_values.reindex(analysis.holdings.index),
                analysis.holdings["value"],
            )
            or not np.allclose(simulation.paths.iloc[0], analysis.holdings["value"].sum())
            or simulation.price_column != analysis.price_column
            or simulation.periods_per_year != analysis.periods_per_year
            or simulation.rebalance != analysis.rebalance
            or (
                simulation.rebalance == "monthly"
                and (
                    simulation.target_weights is None
                    or not np.allclose(
                        simulation.target_weights.reindex(analysis.target_weights.index),
                        analysis.target_weights,
                    )
                )
            )
        ):
            raise ValueError(
                "La simulación debe corresponder a los mismos activos, valor inicial y criterios de cálculo del informe."
            )
    name = generated_on.strftime("%Y-%m-%d_%H-%M-%S")
    report_dir = REPORTS_DIR / name
    if report_dir.exists():
        name += generated_on.strftime("_%f")
        report_dir = REPORTS_DIR / name
    # Evita sobrescribir informes anteriores, incluso si coinciden en el mismo segundo.
    report_dir.mkdir(parents=True, exist_ok=False)
    charts = {}

    def save_chart(key, filename, figure):
        try:
            figure.savefig(report_dir / filename, dpi=150, bbox_inches="tight")
        finally:
            plt.close(figure)
        charts[key] = filename

    save_chart("portfolio", "analisis_cartera.png", analysis.plot(show=False))
    save_chart("assets", "evolucion_activos.png", plot_assets(analysis, show=False))
    save_chart(
        "distribution", "distribucion_rentabilidades.png", plot_distribution(analysis, show=False)
    )
    if simulation is not None:
        save_chart("simulation", "simulacion_monte_carlo.png", simulation.plot(show=False))
    text = build_report(analysis, generated_on, charts, simulation)
    path = report_dir / f"{name}.md"
    path.write_text(text, encoding="utf-8")
    return path
