"""Gráficos del informe. Cada uno devuelve una Figure, o None si falta el dato que necesita."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps
from pathlib import Path
from typing import TYPE_CHECKING

import matplotlib as mpl
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter, PercentFormatter

from ..analysis.metrics import annualized_growth
from ..validation import validate_positive_int
from .formatting import DATE_FORMAT, format_date, format_number, format_tick
from .labels import SECTORS

if TYPE_CHECKING:
    import pandas as pd

    from ..analysis.result import PortfolioAnalysis
    from ..simulation.result import SimulationResult

# Paleta categórica en orden fijo, tinta y superficie.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
GREY = "#898781"
CRITICAL = "#d03b3b"
INK, INK_SECONDARY = "#0b0b0b", "#52514e"
SURFACE, GRID, AXIS = "#fcfcfb", "#e1e0d9", "#c3c2b7"
DIVERGING = LinearSegmentedColormap.from_list(
    "azul_rojo", ["#184f95", "#6da7ec", "#f0efec", "#f08f8e", "#b5302f"]
)
SEQUENTIAL_BLUE = ["#cde2fb", "#9ec5f4", "#5598e7", "#1c5cab"]

_INSTALLED = {font.name for font in font_manager.fontManager.ttflist}
STYLE = {
    "font.family": [font for font in ("Segoe UI", "Helvetica Neue", "Arial") if font in _INSTALLED]
    + ["DejaVu Sans"],
    "font.size": 10,
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "axes.edgecolor": AXIS,
    "axes.linewidth": 0.8,
    "axes.labelcolor": INK_SECONDARY,
    "axes.titlesize": 12,
    "axes.titleweight": "bold",
    "axes.titlecolor": INK,
    "axes.titlelocation": "left",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "axes.grid.axis": "y",
    "axes.axisbelow": True,
    "grid.color": GRID,
    "grid.linewidth": 0.6,
    "xtick.color": GREY,
    "ytick.color": GREY,
    "xtick.labelcolor": INK_SECONDARY,
    "ytick.labelcolor": INK_SECONDARY,
    "lines.linewidth": 2,
    "legend.frameon": False,
    "legend.labelcolor": INK_SECONDARY,
}
PERCENT = PercentFormatter(1.0, decimals=0)


def _styled(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        with mpl.rc_context(STYLE):
            return function(*args, **kwargs)

    return wrapper


def _dates(axis) -> None:
    """Fechas numéricas, sin depender del idioma del sistema."""
    axis.xaxis.set_major_formatter(mdates.DateFormatter(DATE_FORMAT))
    axis.tick_params(axis="x", labelrotation=25)


def _axis(axis, **size) -> tuple[Figure, object]:
    """Dibuja en el eje indicado o en una figura nueva."""
    return (axis.figure, axis) if axis is not None else plt.subplots(**size)


@_styled
def plot_evolution(analysis: PortfolioAnalysis, axis=None) -> Figure:
    """Evolución en base 100: cartera, índice y ETF de Bunds."""
    figure, axis = _axis(axis, figsize=(9, 4.5))
    # Con índice, ambos se comparan en sus fechas comunes y en la misma divisa.
    comparison = analysis.benchmark_comparison
    values = analysis.values if comparison.empty else comparison["portfolio"]
    values = values / values.iloc[0] * 100
    axis.plot(values.index, values.to_numpy(), color=SERIES[0], label="Cartera")
    if not comparison.empty:
        benchmark = comparison["benchmark"] / comparison["benchmark"].iloc[0] * 100
        axis.plot(
            benchmark.index, benchmark.to_numpy(), color=SERIES[1], label=analysis.benchmark_name
        )
    bund_etf = analysis.market.bund_etf_prices
    if bund_etf is not None and not bund_etf.dropna().empty:
        bund_etf = bund_etf.dropna()
        axis.plot(
            bund_etf.index,
            (bund_etf / bund_etf.iloc[0] * 100).to_numpy(),
            color=SERIES[2],
            label="ETF de Bunds",
        )
    axis.axhline(100, color=AXIS, linewidth=0.8)
    axis.annotate(
        f"{values.iloc[-1]:.0f}",
        (values.index[-1], values.iloc[-1]),
        xytext=(6, 0),
        textcoords="offset points",
        va="center",
        color=INK,
        fontweight="bold",
    )
    axis.set_title(f"Evolución de 100 {analysis.currency} invertidos")
    axis.legend(loc="upper left", ncols=3)
    _dates(axis)
    return figure


@_styled
def plot_assets(analysis: PortfolioAnalysis) -> Figure:
    """Evolución de cada activo en base 100, en la divisa de la cartera."""
    prices = analysis.asset_prices
    normalized = prices / prices.iloc[0] * 100
    # Con muchos activos, la paleta fija repetiría colores.
    colors = SERIES if len(prices.columns) <= len(SERIES) else plt.get_cmap("tab20").colors
    figure, axis = plt.subplots(figsize=(9, 4.5))
    for number, symbol in enumerate(normalized.columns):
        axis.plot(
            normalized.index,
            normalized[symbol].to_numpy(),
            color=colors[number % len(colors)],
            linewidth=1.5,
            label=symbol,
        )
    axis.axhline(100, color=AXIS, linewidth=0.8)
    axis.set_title(f"Evolución de 100 {analysis.currency} invertidos en cada activo")
    axis.legend(loc="upper left", ncols=min(5, len(prices.columns)))
    _dates(axis)
    return figure


@_styled
def plot_drawdown(analysis: PortfolioAnalysis, axis=None) -> Figure:
    """Caída desde el máximo previo a lo largo del tiempo."""
    figure, axis = _axis(axis, figsize=(9, 3.5))
    drawdown = analysis.drawdown
    axis.fill_between(drawdown.index, drawdown.to_numpy(), 0, color=SERIES[0], alpha=0.25, lw=0)
    axis.plot(drawdown.index, drawdown.to_numpy(), color=SERIES[0], linewidth=1.2)
    episode = analysis.drawdown_episode
    if episode.trough is not None:
        recovery = (
            f"recuperado el {format_date(episode.recovery)}"
            if episode.recovery is not None
            else "sin recuperar"
        )
        axis.plot(
            [episode.trough],
            [episode.depth],
            "o",
            color=SERIES[0],
            markersize=8,
            markeredgecolor=SURFACE,
            markeredgewidth=2,
        )
        axis.annotate(
            f"{format_number(episode.depth, True)} · {format_date(episode.trough)}\n{recovery}",
            (episode.trough, episode.depth),
            xytext=(10, 4),
            textcoords="offset points",
            color=INK,
            fontsize=9,
        )
    axis.yaxis.set_major_formatter(PERCENT)
    axis.set_title("Drawdown: caída desde el máximo anterior")
    _dates(axis)
    return figure


@_styled
def plot_correlations(analysis: PortfolioAnalysis, axis=None) -> Figure:
    """Matriz de correlaciones entre activos."""
    correlations = analysis.correlations
    count = len(correlations)
    figure, axis = _axis(axis, figsize=(1.2 + 0.7 * count, 0.8 + 0.6 * count))
    heatmap = axis.imshow(correlations, cmap=DIVERGING, vmin=-1, vmax=1)
    axis.set_xticks(range(count), correlations.columns, rotation=45, ha="right")
    axis.set_yticks(range(count), correlations.index)
    axis.grid(False)
    axis.spines[:].set_visible(False)
    axis.tick_params(length=0)
    if count <= 12:
        for row in range(count):
            for column in range(count):
                value = correlations.iat[row, column]
                axis.text(
                    column,
                    row,
                    format_number(value),
                    ha="center",
                    va="center",
                    fontsize=8,
                    color="white" if abs(value) > 0.6 else INK,
                )
    bar = figure.colorbar(heatmap, ax=axis, shrink=0.8, format=FuncFormatter(format_tick))
    bar.outline.set_visible(False)
    bar.ax.tick_params(colors=GREY, labelcolor=INK_SECONDARY)
    axis.set_title("Correlaciones de rentabilidades diarias")
    return figure


@_styled
def plot_risk_return(analysis: PortfolioAnalysis, axis=None) -> Figure:
    """Volatilidad frente a rentabilidad anualizada de cada activo, la cartera y el índice."""
    figure, axis = _axis(axis, figsize=(7, 5))
    details = analysis.asset_details
    axis.scatter(
        details["annualized_volatility"],
        details["annualized_return"],
        s=60,
        color=SERIES[0],
        edgecolor=SURFACE,
        linewidth=2,
        label="Activos",
        zorder=3,
    )
    for symbol, row in details.iterrows():
        axis.annotate(
            symbol,
            (row["annualized_volatility"], row["annualized_return"]),
            xytext=(6, 4),
            textcoords="offset points",
            fontsize=8,
            color=INK_SECONDARY,
        )
    axis.scatter(
        [analysis.metrics["annualized_volatility"]],
        [analysis.metrics["annualized_return"]],
        s=110,
        color=SERIES[1],
        edgecolor=SURFACE,
        linewidth=2,
        label="Cartera",
        zorder=4,
    )
    comparison = analysis.benchmark_comparison
    if not comparison.empty:
        market = comparison["benchmark"].pct_change(fill_method=None).dropna()
        axis.scatter(
            [market.std() * np.sqrt(analysis.periods_per_year)],
            [annualized_growth(comparison["benchmark"])],
            s=80,
            marker="D",
            color=GREY,
            edgecolor=SURFACE,
            linewidth=2,
            label=analysis.benchmark_name,
            zorder=3,
        )
    axis.axhline(0, color=AXIS, linewidth=0.8)
    axis.xaxis.set_major_formatter(PERCENT)
    axis.yaxis.set_major_formatter(PERCENT)
    axis.set(xlabel="Volatilidad anualizada", ylabel="Rentabilidad anualizada")
    axis.grid(True, axis="both")
    axis.set_title("Riesgo frente a rentabilidad")
    axis.margins(0.15)
    axis.legend(loc="best")
    return figure


def _grouped_bars(axis, labels, columns: dict[str, pd.Series]) -> None:
    count = len(columns)
    width = 0.8 / count
    positions = np.arange(len(labels))
    for number, (name, values) in enumerate(columns.items()):
        axis.bar(
            positions + (number - (count - 1) / 2) * width,
            values,
            width=width,
            color=SERIES[number],
            label=name,
            edgecolor=SURFACE,
            linewidth=2,
        )
    axis.set_xticks(positions, labels)
    axis.axhline(0, color=AXIS, linewidth=0.8)
    axis.legend(loc="upper right", ncols=count)


@_styled
def plot_risk_shares(analysis: PortfolioAnalysis) -> Figure | None:
    """Peso de cada activo frente a su contribución al riesgo."""
    # Omite las contribuciones ausentes para no presentarlas como riesgo cero.
    shares = analysis.risk_contributions.dropna()
    if shares.empty:
        return None
    weights = analysis.holdings.loc[shares.index, "weight"]
    figure, axis = plt.subplots(figsize=(max(6, 1.1 * len(shares)), 4))
    _grouped_bars(axis, shares.index, {"Peso actual": weights, "Contribución al riesgo": shares})
    axis.yaxis.set_major_formatter(PERCENT)
    axis.set_title("Peso frente a contribución al riesgo")
    return figure


@_styled
def plot_annual_returns(analysis: PortfolioAnalysis) -> Figure:
    """Rentabilidad de cada año natural, cartera frente al índice."""
    returns = analysis.values.pct_change(fill_method=None).dropna()
    annual = {"Cartera": (1 + returns).resample("YE").prod() - 1}
    comparison = analysis.benchmark_comparison
    if not comparison.empty:
        market = comparison["benchmark"].pct_change(fill_method=None).dropna()
        yearly = (1 + market).resample("YE").prod() - 1
        annual[analysis.benchmark_name] = yearly.reindex(annual["Cartera"].index)
    figure, axis = plt.subplots(figsize=(max(6, 0.9 * len(annual["Cartera"])), 4))
    _grouped_bars(axis, annual["Cartera"].index.year, annual)
    axis.yaxis.set_major_formatter(PERCENT)
    axis.set_title("Rentabilidad por año")
    return figure


@_styled
def plot_distribution(analysis: PortfolioAnalysis) -> Figure:
    """Histograma de rentabilidades diarias frente a una normal con igual media y desviación."""
    returns = analysis.values.pct_change(fill_method=None).dropna()
    figure, axis = plt.subplots(figsize=(8, 4))
    axis.hist(
        returns,
        bins=min(80, max(5, len(returns) // 5)),
        density=True,
        color=SERIES[0],
        alpha=0.75,
        edgecolor=SURFACE,
        linewidth=0.5,
        label="Cartera",
    )
    deviation = returns.std()
    if deviation > 0:
        grid = np.linspace(returns.min(), returns.max(), 300)
        density = np.exp(-(((grid - returns.mean()) / deviation) ** 2) / 2) / (
            deviation * np.sqrt(2 * np.pi)
        )
        axis.plot(grid, density, color=SERIES[1], label="Normal equivalente")
    var = analysis.metrics["period_var_95_return"]
    axis.axvline(var, color=INK_SECONDARY, linewidth=1)
    axis.annotate(" VaR 95 %", (var, axis.get_ylim()[1] * 0.9), color=INK_SECONDARY, fontsize=9)
    axis.xaxis.set_major_formatter(PercentFormatter(1.0, decimals=1))
    axis.set_yticks([])
    axis.grid(False)
    axis.set_title("Distribución de rentabilidades diarias")
    axis.legend(loc="upper right")
    return figure


@_styled
def plot_volatility_vix(analysis: PortfolioAnalysis) -> Figure | None:
    """Volatilidad móvil de 21 sesiones (anualizada) frente al VIX, en la misma escala (%)."""
    vix = analysis.market.vix
    if vix is None:
        return None
    returns = analysis.values.pct_change(fill_method=None).dropna()
    volatility = returns.rolling(21).std() * np.sqrt(analysis.periods_per_year) * 100
    figure, axis = plt.subplots(figsize=(9, 4))
    axis.plot(
        volatility.index,
        volatility.to_numpy(),
        color=SERIES[0],
        linewidth=1.5,
        label="Volatilidad de la cartera (21 sesiones)",
    )
    axis.plot(vix.index, vix.to_numpy(), color=SERIES[1], linewidth=1.5, label="VIX")
    axis.set_ylabel("Volatilidad anualizada (%)")
    axis.set_title("Volatilidad de la cartera frente al VIX")
    axis.legend(loc="upper right", ncols=2)
    _dates(axis)
    return figure


@_styled
def plot_bund_correlation(analysis: PortfolioAnalysis) -> Figure | None:
    """Correlación móvil de 60 sesiones con el ETF de Bunds."""
    series = analysis.market.bund_rolling_correlation
    if series is None or series.dropna().empty:
        return None
    figure, axis = plt.subplots(figsize=(9, 3.5))
    axis.plot(series.index, series.to_numpy(), color=SERIES[0], linewidth=1.5)
    axis.axhline(0, color=AXIS, linewidth=0.8)
    axis.set_ylim(-1, 1)
    axis.annotate(
        "Por debajo de 0: el Bund hace de refugio",
        (series.index[0], -0.92),
        color=INK_SECONDARY,
        fontsize=9,
    )
    axis.set_title("Correlación móvil (60 sesiones) con el ETF de Bunds")
    _dates(axis)
    return figure


@_styled
def plot_exposure(analysis: PortfolioAnalysis) -> Figure:
    """Exposición por sector y por divisa."""
    sectors = analysis.sector_weights.rename(index=lambda sector: SECTORS.get(sector, sector))
    currencies = analysis.currency_weights
    rows = max(len(sectors), len(currencies))
    figure, axes = plt.subplots(1, 2, figsize=(10, 1 + 0.45 * rows))
    for axis, data, title in (
        (axes[0], sectors, "Por sector"),
        (axes[1], currencies, "Por divisa"),
    ):
        data = data.sort_values()
        axis.barh(data.index, data, color=SERIES[0], height=0.7, edgecolor=SURFACE, linewidth=2)
        for row, value in enumerate(data):
            axis.annotate(
                f"{value * 100:.0f} %",
                (value, row),
                xytext=(4, 0),
                textcoords="offset points",
                va="center",
                fontsize=9,
                color=INK_SECONDARY,
            )
        axis.xaxis.set_major_formatter(PERCENT)
        axis.grid(True, axis="x")
        axis.grid(False, axis="y")
        axis.set_xlim(0, max(1, data.max() * 1.15))
        axis.set_title(title)
    figure.tight_layout()
    return figure


@_styled
def plot_analysis(analysis: PortfolioAnalysis) -> Figure:
    """Evolución, caídas, correlaciones y riesgo frente a rentabilidad, en una sola figura."""
    figure, axes = plt.subplots(2, 2, figsize=(14, 9))
    plot_evolution(analysis, axes[0, 0])
    plot_drawdown(analysis, axes[0, 1])
    plot_correlations(analysis, axes[1, 0])
    plot_risk_return(analysis, axes[1, 1])
    figure.tight_layout()
    return figure


def _money(currency: str) -> FuncFormatter:
    return FuncFormatter(lambda value, _: f"{format_tick(round(value))} {currency}")


def _fan(axis, simulation: SimulationResult, max_paths: int) -> None:
    """Percentiles de las trayectorias simuladas sesión a sesión."""
    paths = simulation.paths.to_numpy().T
    steps = np.arange(paths.shape[1])
    tail = round((1 - simulation.confidence) * 100, 1)
    low, q1, median, q3, high = np.percentile(paths, [tail, 25, 50, 75, 100 - tail], axis=0)
    for path in paths[:max_paths]:
        axis.plot(steps, path, color=AXIS, linewidth=0.4, alpha=0.6)
    label = f"Percentiles {tail:g}–{100 - tail:g}".replace(".", ",")
    axis.fill_between(steps, low, high, color=SEQUENTIAL_BLUE[0], label=label, linewidth=0)
    axis.fill_between(steps, q1, q3, color=SEQUENTIAL_BLUE[1], label="Percentiles 25–75", lw=0)
    axis.plot(steps, median, color=SEQUENTIAL_BLUE[3], label="Mediana")
    axis.axhline(paths[0, 0], color=INK_SECONDARY, linewidth=0.8)
    axis.yaxis.set_major_formatter(_money(simulation.currency))
    axis.set_xlabel("Sesiones")
    count = f"{len(paths):,}".replace(",", ".")
    axis.set_title(f"Abanico de {count} trayectorias simuladas")
    axis.legend(loc="upper left", ncols=3)


def _final_values(axis, simulation: SimulationResult) -> None:
    """Distribución del valor final; en rojo, los escenarios con pérdidas."""
    initial = float(simulation.paths.iloc[0, 0])
    final = simulation.paths.iloc[-1].to_numpy()
    low, high = np.percentile(final, [0.5, 99.5])
    bins = np.linspace(low, high, 70) if high > low else 10
    axis.hist(
        final[final >= initial],
        bins=bins,
        color=SERIES[0],
        edgecolor=SURFACE,
        linewidth=0.5,
        label="Ganancia",
    )
    axis.hist(
        final[final < initial],
        bins=bins,
        color=CRITICAL,
        edgecolor=SURFACE,
        linewidth=0.5,
        label=f"Pérdida ({(final < initial).mean() * 100:.0f} %)",
    )
    axis.axvline(initial, color=INK_SECONDARY, linewidth=1)
    axis.xaxis.set_major_formatter(_money(simulation.currency))
    axis.set_yticks([])
    axis.grid(False)
    axis.set_title("Valor final de los escenarios simulados")
    axis.legend(loc="upper right")


@_styled
def plot_simulation(simulation: SimulationResult, max_paths: int = 40) -> Figure:
    """Trayectorias simuladas y distribución del valor final."""
    validate_positive_int("max_paths", max_paths)
    figure, axes = plt.subplots(1, 2, figsize=(15, 4.8), gridspec_kw={"width_ratios": [1.4, 1]})
    _fan(axes[0], simulation, max_paths)
    _final_values(axes[1], simulation)
    figure.tight_layout()
    return figure


@dataclass(frozen=True)
class ChartSpec:
    """Archivo del gráfico, sección del informe que lo muestra y función que lo crea."""

    file: str
    section: str
    build: Callable[..., Figure | None]


# Las claves también nombran los gráficos que devuelve plots_report().
CHARTS = {
    "exposure": ChartSpec("exposicion.png", "composition", plot_exposure),
    "evolution": ChartSpec("evolucion.png", "returns", plot_evolution),
    "assets": ChartSpec("evolucion_activos.png", "returns", plot_assets),
    "annual_returns": ChartSpec("rentabilidad_anual.png", "returns", plot_annual_returns),
    "drawdown": ChartSpec("drawdown.png", "risk", plot_drawdown),
    "distribution": ChartSpec("distribucion.png", "risk", plot_distribution),
    "risk_return": ChartSpec("riesgo_rentabilidad.png", "risk_adjusted", plot_risk_return),
    "correlations": ChartSpec("correlaciones.png", "diversification", plot_correlations),
    "risk_shares": ChartSpec("pesos_contribucion.png", "diversification", plot_risk_shares),
    "volatility_vix": ChartSpec("volatilidad_vix.png", "market", plot_volatility_vix),
    "bund_correlation": ChartSpec("correlacion_bund.png", "market", plot_bund_correlation),
    "simulation": ChartSpec("montecarlo.png", "simulation", plot_simulation),
}


def plot_report(
    analysis: PortfolioAnalysis,
    simulation: SimulationResult | None = None,
    sections=None,
) -> dict[str, Figure]:
    """Crea los gráficos de las secciones indicadas (todas si es None) sin mostrarlos.

    El gráfico de la simulación solo se crea si se proporciona un resultado, y los de mercado,
    si se han podido descargar sus datos.
    """
    figures = {}
    try:
        for key, chart in CHARTS.items():
            source = simulation if chart.section == "simulation" else analysis
            if source is not None and (sections is None or chart.section in sections):
                figure = chart.build(source)
                if figure is not None:
                    figures[key] = figure
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
