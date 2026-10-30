"""Gráficos de evolución, caídas, correlaciones y contribución al riesgo."""

import numpy as np


def plot_analysis(analysis, show=True):
    import matplotlib.pyplot as plt

    figure, axes = plt.subplots(2, 2, figsize=(12, 8))
    comparison = analysis.benchmark_comparison
    if comparison.empty:
        axes[0, 0].plot(
            analysis.values.index, analysis.values / analysis.values.iloc[0] * 100, label="Cartera"
        )
    else:
        normalized = comparison / comparison.iloc[0] * 100
        axes[0, 0].plot(normalized.index, normalized["portfolio"], label="Cartera")
        axes[0, 0].plot(normalized.index, normalized["benchmark"], label="Índice de referencia")
    axes[0, 0].set(
        title="Evolución en fechas comunes" if not comparison.empty else "Evolución de la cartera",
        ylabel=f"Base 100 ({analysis.currency})",
        xlabel="Fecha",
    )
    axes[0, 0].legend()
    axes[0, 1].plot(analysis.drawdown.index, analysis.drawdown.to_numpy() * 100)
    axes[0, 1].set(title="Caídas desde máximos anteriores", ylabel="Caída (%)", xlabel="Fecha")
    episode = analysis.drawdown_episode
    if episode.trough is not None:
        recovery = (
            f"Recuperación: {episode.recovery:%d/%m/%Y}"
            if episode.recovery is not None
            else "Sin recuperar"
        )
        axes[0, 1].scatter([episode.trough], [episode.depth * 100], color="tab:red", zorder=3)
        axes[0, 1].text(
            0.03,
            0.05,
            f"Valle: {episode.trough:%d/%m/%Y}\n{recovery}",
            transform=axes[0, 1].transAxes,
            fontsize=9,
            bbox={"facecolor": "white", "alpha": 0.8, "edgecolor": "none"},
        )
    correlations = analysis.correlations
    heatmap = axes[1, 0].imshow(correlations, vmin=-1, vmax=1, cmap="RdBu_r")
    ticks = np.arange(len(correlations))
    axes[1, 0].set(
        xticks=ticks,
        yticks=ticks,
        xticklabels=correlations.columns,
        yticklabels=correlations.index,
        title="Correlaciones históricas entre rentabilidades",
    )
    from matplotlib.ticker import FuncFormatter

    figure.colorbar(
        heatmap,
        ax=axes[1, 0],
        format=FuncFormatter(lambda value, _: f"{value:g}".replace(".", ",")),
    )
    # Omite las contribuciones ausentes para no presentarlas como riesgo cero.
    shares = analysis.risk_contributions.dropna()
    if shares.empty:
        axes[1, 1].text(
            0.5,
            0.5,
            "No hay datos suficientes para calcular la contribución al riesgo",
            ha="center",
            va="center",
            transform=axes[1, 1].transAxes,
            wrap=True,
        )
    else:
        positions = np.arange(len(shares))
        axes[1, 1].bar(
            positions - 0.2,
            analysis.holdings.loc[shares.index, "weight"] * 100,
            width=0.4,
            label="Peso actual",
        )
        axes[1, 1].bar(positions + 0.2, shares * 100, width=0.4, label="Contribución al riesgo")
        axes[1, 1].set(xticks=positions, xticklabels=shares.index)
        axes[1, 1].legend()
    axes[1, 1].set(title="Pesos actuales frente a contribución al riesgo", ylabel="Porcentaje (%)")
    _spanish_axes(list(axes.flat))
    figure.tight_layout()
    if show:
        plt.show()
    return figure


def plot_risk_return(analysis, show=True):
    """Usa los resultados ya calculados sobre el mismo historial de la cartera."""
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter

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
    axis.xaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:g}".replace(".", ",")))
    _spanish_axes([axis])
    axis.legend()
    axis.margins(0.15)
    figure.tight_layout()
    if show:
        plt.show()
    return figure


def _spanish_axes(axes):
    """Utiliza coma decimal y fechas numéricas sin depender del idioma del sistema."""
    import matplotlib.dates as mdates
    from matplotlib.ticker import FuncFormatter

    for axis in axes:
        if not axis.images:
            axis.yaxis.set_major_formatter(
                FuncFormatter(lambda value, _: f"{value:g}".replace(".", ","))
            )
        if axis.get_xlabel() == "Fecha":
            axis.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m/%Y"))
            axis.tick_params(axis="x", labelrotation=25)


def plot_assets(analysis, show=True):
    import matplotlib.pyplot as plt

    figure, axis = plt.subplots(figsize=(11, 5))
    normalized = analysis.asset_prices / analysis.asset_prices.iloc[0] * 100
    for symbol in normalized.columns:
        axis.plot(normalized.index, normalized[symbol].to_numpy(), label=symbol)
    axis.set(
        title="Evolución comparada de los activos", xlabel="Fecha", ylabel="Valor inicial = 100"
    )
    axis.legend(title="Activos")
    _spanish_axes([axis])
    figure.autofmt_xdate()
    figure.tight_layout()
    if show:
        plt.show()
    return figure


def plot_distribution(analysis, show=True):
    """Compara los incrementos logarítmicos históricos con la normal asumida por el GBM."""
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter

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
        values = np.linspace(low, high, 300)
        density = np.exp(-0.5 * ((values - mean) / deviation) ** 2) / (
            deviation * np.sqrt(2 * np.pi)
        )
        axis.plot(values, density, label="Distribución normal de referencia")
    else:
        axis.axvline(mean, label="Rentabilidad constante")
    axis.set(
        title="Rentabilidades logarítmicas frente a una distribución normal",
        xlabel="Rentabilidad logarítmica por período (%)",
        ylabel="Densidad",
    )
    axis.xaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:g}".replace(".", ",")))
    _spanish_axes([axis])
    axis.legend()
    figure.tight_layout()
    if show:
        plt.show()
    return figure


# Nombre de archivo de cada gráfico; el informe Markdown utiliza las mismas claves.
CHART_FILES = {
    "portfolio": "analisis_cartera.png",
    "assets": "evolucion_activos.png",
    "distribution": "distribucion_rentabilidades.png",
    "simulation": "simulacion_monte_carlo.png",
    "risk_return": "riesgo_rentabilidad.png",
}


def plot_report(analysis, keys=None) -> dict:
    """Crea el conjunto de gráficos históricos sin mostrarlos ni guardarlos."""
    builders = {
        "portfolio": plot_analysis,
        "assets": plot_assets,
        "distribution": plot_distribution,
        "risk_return": plot_risk_return,
    }
    return {
        key: build(analysis, show=False)
        for key, build in builders.items()
        if keys is None or key in keys
    }


def save_charts(figures: dict, directory, close: bool = False) -> dict[str, str]:
    """Guarda cada figura en la carpeta y devuelve el nombre de archivo de cada gráfico."""
    import matplotlib.pyplot as plt

    saved = {}
    try:
        for key, figure in figures.items():
            figure.savefig(directory / CHART_FILES[key], dpi=150, bbox_inches="tight")
            saved[key] = CHART_FILES[key]
    finally:
        if close:
            for figure in figures.values():
                plt.close(figure)
    return saved
