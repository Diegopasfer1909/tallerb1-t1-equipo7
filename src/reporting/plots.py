"""Gráficos de evolución, caídas, correlaciones, riesgo y simulación."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter

from ..validation import validate_positive_int
from .formatting import DATE_FORMAT, format_date, format_tick

if TYPE_CHECKING:
    import pandas as pd

    from ..analysis.result import PortfolioAnalysis
    from ..simulation.result import SimulationResult


def _numbers(*scales) -> None:
    """Coma decimal y separador de miles en los ejes indicados (axis.xaxis o axis.yaxis)."""
    for scale in scales:
        scale.set_major_formatter(FuncFormatter(format_tick))


def _dates(axis) -> None:
    """Fechas numéricas, sin depender del idioma del sistema."""
    axis.xaxis.set_major_formatter(mdates.DateFormatter(DATE_FORMAT))
    axis.tick_params(axis="x", labelrotation=25)


def plot_analysis(analysis: PortfolioAnalysis) -> Figure:
    """Evolución frente al índice, caídas, correlaciones y contribución al riesgo."""
    figure, axes = plt.subplots(2, 2, figsize=(12, 8))
    _plot_value(axes[0, 0], analysis)
    _plot_drawdown(axes[0, 1], analysis)
    _plot_correlations(figure, axes[1, 0], analysis.correlations)
    _plot_risk_shares(axes[1, 1], analysis)
    figure.tight_layout()
    return figure


def _plot_value(axis, analysis: PortfolioAnalysis) -> None:
    """Cartera e índice en base 100 sobre las mismas fechas y en la misma divisa."""
    comparison = analysis.benchmark_comparison
    if comparison.empty:
        values = analysis.values
        axis.plot(values.index, values / values.iloc[0] * 100, label="Cartera")
        title = "Evolución de la cartera"
    else:
        normalized = comparison / comparison.iloc[0] * 100
        axis.plot(normalized.index, normalized["portfolio"], label="Cartera")
        axis.plot(
            normalized.index,
            normalized["benchmark"],
            label=f"Índice de referencia ({analysis.benchmark_symbol})",
        )
        title = "Evolución en fechas comunes"
    axis.set(title=title, ylabel=f"Base 100 ({analysis.currency})", xlabel="Fecha")
    axis.legend()
    _numbers(axis.yaxis)
    _dates(axis)


def _plot_drawdown(axis, analysis: PortfolioAnalysis) -> None:
    """Caídas desde máximos, con el valle y la recuperación de la mayor de ellas."""
    drawdown = analysis.drawdown
    axis.plot(drawdown.index, drawdown.to_numpy() * 100)
    axis.set(title="Caídas desde máximos anteriores", ylabel="Caída (%)", xlabel="Fecha")
    episode = analysis.drawdown_episode
    if episode.trough is not None:
        recovery = (
            f"Recuperación: {format_date(episode.recovery)}"
            if episode.recovery is not None
            else "Sin recuperar"
        )
        axis.scatter([episode.trough], [episode.depth * 100], color="tab:red", zorder=3)
        axis.text(
            0.03,
            0.05,
            f"Valle: {format_date(episode.trough)}\n{recovery}",
            transform=axis.transAxes,
            fontsize=9,
            bbox={"facecolor": "white", "alpha": 0.8, "edgecolor": "none"},
        )
    _numbers(axis.yaxis)
    _dates(axis)


def _plot_correlations(figure: Figure, axis, correlations: pd.DataFrame) -> None:
    heatmap = axis.imshow(correlations, vmin=-1, vmax=1, cmap="RdBu_r")
    ticks = np.arange(len(correlations))
    axis.set(
        xticks=ticks,
        yticks=ticks,
        xticklabels=correlations.columns,
        yticklabels=correlations.index,
        title="Correlaciones históricas entre rentabilidades",
    )
    figure.colorbar(heatmap, ax=axis, format=FuncFormatter(format_tick))


def _plot_risk_shares(axis, analysis: PortfolioAnalysis) -> None:
    # Omite las contribuciones ausentes para no presentarlas como riesgo cero.
    shares = analysis.risk_contributions.dropna()
    if shares.empty:
        axis.text(
            0.5,
            0.5,
            "No hay datos suficientes para calcular la contribución al riesgo",
            ha="center",
            va="center",
            transform=axis.transAxes,
            wrap=True,
        )
    else:
        positions = np.arange(len(shares))
        weights = analysis.holdings.loc[shares.index, "weight"]
        axis.bar(positions - 0.2, weights * 100, width=0.4, label="Peso actual")
        axis.bar(positions + 0.2, shares * 100, width=0.4, label="Contribución al riesgo")
        axis.set(xticks=positions, xticklabels=shares.index)
        axis.legend()
    axis.set(title="Pesos actuales frente a contribución al riesgo", ylabel="Porcentaje (%)")
    _numbers(axis.yaxis)


def plot_risk_return(analysis: PortfolioAnalysis) -> Figure:
    """Usa los resultados ya calculados sobre el mismo historial de la cartera."""
    figure, axis = plt.subplots(figsize=(9, 5))
    details = analysis.asset_details
    axis.scatter(
        details["annualized_volatility"] * 100,
        details["annualized_return"] * 100,
        label="Activos",
        alpha=0.75,
    )
    for symbol, row in details.iterrows():
        axis.annotate(
            symbol,
            (row["annualized_volatility"] * 100, row["annualized_return"] * 100),
            xytext=(5, 5),
            textcoords="offset points",
        )
    axis.scatter(
        [analysis.metrics["annualized_volatility"] * 100],
        [analysis.metrics["annualized_return"] * 100],
        marker="*",
        s=160,
        label="Cartera",
    )
    axis.set(
        title="Riesgo y rentabilidad histórica",
        xlabel="Volatilidad anual (%)",
        ylabel="Rentabilidad anualizada (%)",
    )
    axis.axhline(0, color="grey", linewidth=0.7)
    _numbers(axis.xaxis, axis.yaxis)
    axis.legend()
    axis.margins(0.15)
    figure.tight_layout()
    return figure


def plot_assets(analysis: PortfolioAnalysis) -> Figure:
    figure, axis = plt.subplots(figsize=(11, 5))
    normalized = analysis.asset_prices / analysis.asset_prices.iloc[0] * 100
    for symbol in normalized.columns:
        axis.plot(normalized.index, normalized[symbol].to_numpy(), label=symbol)
    axis.set(
        title="Evolución comparada de los activos", xlabel="Fecha", ylabel="Valor inicial = 100"
    )
    axis.legend(title="Activos")
    _numbers(axis.yaxis)
    _dates(axis)
    figure.autofmt_xdate()
    figure.tight_layout()
    return figure


def plot_distribution(analysis: PortfolioAnalysis) -> Figure:
    """Compara los incrementos logarítmicos históricos con la normal asumida por el GBM."""
    values = analysis.values.to_numpy(dtype=float)
    returns = np.log(values[1:] / values[:-1]) * 100
    figure, axis = plt.subplots(figsize=(10, 5))
    axis.hist(
        returns,
        bins=min(40, max(5, len(returns) // 5)),
        density=True,
        alpha=0.6,
        label="Rentabilidades logarítmicas históricas",
        edgecolor="white",
    )
    mean = returns.mean()
    deviation = returns.std(ddof=1)
    if deviation > 0:
        low = min(returns.min(), mean - 4 * deviation)
        high = max(returns.max(), mean + 4 * deviation)
        grid = np.linspace(low, high, 300)
        density = np.exp(-0.5 * ((grid - mean) / deviation) ** 2) / (deviation * np.sqrt(2 * np.pi))
        axis.plot(grid, density, label="Distribución normal de referencia")
    else:
        axis.axvline(mean, label="Rentabilidad constante")
    axis.set(
        title="Rentabilidades logarítmicas frente a una distribución normal",
        xlabel="Rentabilidad logarítmica por período (%)",
        ylabel="Densidad",
    )
    _numbers(axis.xaxis, axis.yaxis)
    axis.legend()
    figure.tight_layout()
    return figure


def plot_simulation(simulation: SimulationResult, max_paths: int = 100) -> Figure:
    """Trayectorias simuladas y distribución del valor final."""
    validate_positive_int("max_paths", max_paths)
    figure, axes = plt.subplots(1, 2, figsize=(12, 4))
    simulation.paths.iloc[:, :max_paths].plot(ax=axes[0], legend=False, alpha=0.25)
    axes[0].set(
        title="Trayectorias simuladas",
        xlabel="Período",
        ylabel=f"Valor ({simulation.currency})",
    )
    axes[1].hist(simulation.paths.iloc[-1], bins=30, edgecolor="white")
    axes[1].set(
        title="Distribución del valor final",
        xlabel=f"Valor ({simulation.currency})",
        ylabel="Número de simulaciones",
    )
    for axis in axes:
        _numbers(axis.xaxis, axis.yaxis)
    figure.tight_layout()
    return figure


@dataclass(frozen=True)
class ChartSpec:
    """Archivo del gráfico, sección del informe que lo muestra y función que lo crea."""

    file: str
    section: str
    build: Callable[..., Figure]


# Las claves también nombran los gráficos que devuelve plots_report().
CHARTS = {
    "portfolio": ChartSpec("analisis_cartera.png", "performance", plot_analysis),
    "assets": ChartSpec("evolucion_activos.png", "performance", plot_assets),
    "risk_return": ChartSpec("riesgo_rentabilidad.png", "performance", plot_risk_return),
    "distribution": ChartSpec(
        "distribucion_rentabilidades.png", "diversification", plot_distribution
    ),
    "simulation": ChartSpec("simulacion_monte_carlo.png", "simulation", plot_simulation),
}


def plot_report(
    analysis: PortfolioAnalysis,
    simulation: SimulationResult | None = None,
    sections=None,
) -> dict[str, Figure]:
    """Crea los gráficos de las secciones indicadas (todas si es None) sin mostrarlos.

    El gráfico de la simulación solo se crea si se proporciona un resultado.
    """
    figures = {}
    try:
        for key, chart in CHARTS.items():
            source = simulation if chart.section == "simulation" else analysis
            if source is not None and (sections is None or chart.section in sections):
                figures[key] = chart.build(source)
    except BaseException:
        close_figures(figures)
        raise
    return figures


def save_charts(figures: dict[str, Figure], directory: Path, close: bool = False) -> dict[str, str]:
    """Guarda cada figura en la carpeta y devuelve el nombre de archivo de cada gráfico."""
    saved = {}
    try:
        for key, figure in figures.items():
            figure.savefig(directory / CHARTS[key].file, dpi=150, bbox_inches="tight")
            saved[key] = CHARTS[key].file
    finally:
        if close:
            close_figures(figures)
    return saved


def charts_by_section(files: dict[str, str]) -> dict[str, dict[str, str]]:
    """Agrupa los archivos guardados según la sección del informe que los muestra."""
    grouped: dict[str, dict[str, str]] = {}
    for key, file in files.items():
        grouped.setdefault(CHARTS[key].section, {})[key] = file
    return grouped


def close_figures(figures: dict[str, Figure]) -> None:
    for figure in figures.values():
        plt.close(figure)


def show_figures() -> None:
    """Muestra en pantalla todas las figuras abiertas."""
    plt.show()
