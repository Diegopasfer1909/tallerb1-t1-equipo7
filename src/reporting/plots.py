"""Gráficos de evolución, caídas, correlaciones y contribución al riesgo."""

import numpy as np


def plot_analysis(analysis, show=True):
    import matplotlib.pyplot as plt

    figure, axes = plt.subplots(2, 2, figsize=(12, 8))
    axes[0, 0].plot(analysis.values.index, analysis.values.to_numpy())
    title = (
        "Crecimiento con precios ajustados"
        if analysis.price_column == "Adj Close"
        else "Valor histórico de la cartera"
    )
    axes[0, 0].set(title=title, ylabel=f"Valor ({analysis.currency})", xlabel="Fecha")
    axes[0, 1].plot(analysis.drawdown.index, analysis.drawdown.to_numpy() * 100)
    axes[0, 1].set(title="Caídas desde máximos anteriores", ylabel="Caída (%)", xlabel="Fecha")
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
        )
    else:
        axes[1, 1].bar(shares.index, shares * 100)
    axes[1, 1].set(title="Contribución al riesgo con los pesos actuales", ylabel="Contribución (%)")
    _spanish_axes(list(axes.flat))
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
