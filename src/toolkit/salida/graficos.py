"""Gráficos del report. Cada función recibe la cartera y devuelve una Figure, o None
si falta el dato que necesita (p. ej. el VIX no se pudo descargar)."""
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.ticker import FuncFormatter, PercentFormatter

from ..analisis.metricas import SESIONES, cagr

# Paleta validada (categórica en orden fijo, tinta y superficie).
SERIE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
GRIS = "#898781"
CRITICO = "#d03b3b"
TINTA, TINTA_2 = "#0b0b0b", "#52514e"
SUPERFICIE, REJILLA, EJE = "#fcfcfb", "#e1e0d9", "#c3c2b7"
DIVERGENTE = LinearSegmentedColormap.from_list(
    "azul_rojo", ["#184f95", "#6da7ec", "#f0efec", "#f08f8e", "#b5302f"])
AZUL_SECUENCIAL = ["#cde2fb", "#9ec5f4", "#5598e7", "#1c5cab"]

_INSTALADAS = {f.name for f in font_manager.fontManager.ttflist}
ESTILO = {
    "font.family": [f for f in ("Segoe UI", "Helvetica Neue", "Arial") if f in _INSTALADAS] + ["DejaVu Sans"],
    "font.size": 10,
    "figure.facecolor": SUPERFICIE,
    "axes.facecolor": SUPERFICIE,
    "axes.edgecolor": EJE,
    "axes.linewidth": 0.8,
    "axes.labelcolor": TINTA_2,
    "axes.titlesize": 12,
    "axes.titleweight": "bold",
    "axes.titlecolor": TINTA,
    "axes.titlelocation": "left",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "axes.grid.axis": "y",
    "axes.axisbelow": True,
    "grid.color": REJILLA,
    "grid.linewidth": 0.6,
    "xtick.color": GRIS,
    "ytick.color": GRIS,
    "xtick.labelcolor": TINTA_2,
    "ytick.labelcolor": TINTA_2,
    "lines.linewidth": 2,
    "legend.frameon": False,
    "legend.labelcolor": TINTA_2,
    "savefig.dpi": 150,
    "savefig.bbox": "tight",
}

PCT = PercentFormatter(1.0, decimals=0)
EUROS = FuncFormatter(lambda x, _: f"{x:,.0f} €".replace(",", "."))


def _con_estilo(funcion):
    def envuelta(*args, **kwargs):
        with mpl.rc_context(ESTILO):
            return funcion(*args, **kwargs)
    envuelta.__name__ = funcion.__name__
    envuelta.__doc__ = funcion.__doc__
    return envuelta


def _base100(serie: pd.Series) -> pd.Series:
    serie = serie.dropna()
    return serie / serie.iloc[0] * 100


# ------------------------------------------------------------------ 1–4: esenciales

@_con_estilo
def evolucion(c, ax=None):
    """1. Evolución en base 100: cartera, índice y ETF de Bunds."""
    fig, ax = (ax.figure, ax) if ax else plt.subplots(figsize=(9, 4.5))
    ax.plot(c.valor.index, c.valor * 100, color=SERIE[0], label="Cartera")
    if c.indice_precios is not None:
        ax.plot(c.indice_precios.dropna().index, _base100(c.indice_precios), color=SERIE[1],
                label=c.nombre_indice)
    if c.mercado.etf_bund is not None:
        ax.plot(c.precios.index, _base100(c.alinear_externa(c.mercado.etf_bund.datos)),
                color=SERIE[2], label="ETF de Bunds")
    ax.axhline(100, color=EJE, linewidth=0.8)
    ax.annotate(f"{c.valor.iloc[-1] * 100:.0f}", (c.valor.index[-1], c.valor.iloc[-1] * 100),
                xytext=(6, 0), textcoords="offset points", va="center", color=TINTA, fontweight="bold")
    ax.set_title("Evolución de 100 € invertidos")
    ax.legend(loc="upper left", ncols=3)
    return fig


@_con_estilo
def drawdown(c, ax=None):
    """2. Caída desde el máximo previo a lo largo del tiempo."""
    fig, ax = (ax.figure, ax) if ax else plt.subplots(figsize=(9, 3.5))
    dd = c.riesgo["dd_serie"]
    ax.fill_between(dd.index, dd, 0, color=SERIE[0], alpha=0.25, linewidth=0)
    ax.plot(dd.index, dd, color=SERIE[0], linewidth=1.2)
    valle = c.riesgo["dd_valle"]
    rec = c.riesgo["dd_recuperacion"]
    texto = f"{dd.min() * 100:.1f} % · {valle:%d/%m/%Y}".replace(".", ",", 1)
    texto += f"\nrecuperado el {rec:%d/%m/%Y}" if pd.notna(rec) else "\nsin recuperar"
    ax.plot([valle], [dd.min()], "o", color=SERIE[0], markersize=8, markeredgecolor=SUPERFICIE, markeredgewidth=2)
    ax.annotate(texto, (valle, dd.min()), xytext=(10, 4), textcoords="offset points", color=TINTA, fontsize=9)
    ax.yaxis.set_major_formatter(PCT)
    ax.set_title("Drawdown: caída desde el máximo anterior")
    return fig


@_con_estilo
def correlaciones(c, ax=None):
    """3. Matriz de correlaciones entre activos."""
    corr = c.diversificacion["corr"]
    n = len(corr)
    fig, ax = (ax.figure, ax) if ax else plt.subplots(figsize=(1.2 + 0.7 * n, 0.8 + 0.6 * n))
    im = ax.imshow(corr, cmap=DIVERGENTE, vmin=-1, vmax=1)
    ax.set_xticks(range(n), corr.columns, rotation=45, ha="right")
    ax.set_yticks(range(n), corr.index)
    ax.grid(False)
    ax.spines[:].set_visible(False)
    ax.tick_params(length=0)
    if n <= 12:
        for i in range(n):
            for j in range(n):
                ax.text(j, i, f"{corr.iat[i, j]:.2f}", ha="center", va="center", fontsize=8,
                        color="white" if abs(corr.iat[i, j]) > 0.6 else TINTA)
    barra = fig.colorbar(im, ax=ax, shrink=0.8)
    barra.outline.set_visible(False)
    barra.ax.tick_params(colors=GRIS, labelcolor=TINTA_2)
    ax.set_title("Correlaciones de rentabilidades diarias")
    return fig


@_con_estilo
def riesgo_rentabilidad(c, ax=None):
    """4. Volatilidad frente a rentabilidad anualizada de cada activo, la cartera y el índice."""
    fig, ax = (ax.figure, ax) if ax else plt.subplots(figsize=(7, 5))
    vol = c.r.std() * np.sqrt(SESIONES)
    rent = c.r.apply(cagr)
    ax.scatter(vol, rent, s=60, color=SERIE[0], edgecolor=SUPERFICIE, linewidth=2, label="Activos", zorder=3)
    for t in vol.index:
        ax.annotate(t, (vol[t], rent[t]), xytext=(6, 4), textcoords="offset points", fontsize=8, color=TINTA_2)
    ax.scatter([c.riesgo["volatilidad"]], [c.rentabilidad["cagr"]], s=110, color=SERIE[1],
               edgecolor=SUPERFICIE, linewidth=2, label="Cartera", zorder=4)
    if c.rm is not None:
        ax.scatter([c.rm.std() * np.sqrt(SESIONES)], [cagr(c.rm)], s=80, marker="D", color=GRIS,
                   edgecolor=SUPERFICIE, linewidth=2, label=c.nombre_indice, zorder=3)
    ax.axhline(0, color=EJE, linewidth=0.8)
    ax.xaxis.set_major_formatter(PCT)
    ax.yaxis.set_major_formatter(PCT)
    ax.set_xlabel("Volatilidad anualizada")
    ax.set_ylabel("Rentabilidad anualizada")
    ax.grid(True, axis="both")
    ax.set_title("Riesgo frente a rentabilidad")
    ax.legend(loc="best")
    return fig


# ------------------------------------------------------------------ 5–10: secundarios

def _barras_agrupadas(ax, etiquetas, columnas: dict[str, pd.Series]):
    n = len(columnas)
    ancho = 0.8 / n
    x = np.arange(len(etiquetas))
    for i, (nombre, valores) in enumerate(columnas.items()):
        ax.bar(x + (i - (n - 1) / 2) * ancho, valores, width=ancho, color=SERIE[i], label=nombre,
               edgecolor=SUPERFICIE, linewidth=2)
    ax.set_xticks(x, etiquetas)
    ax.axhline(0, color=EJE, linewidth=0.8)
    ax.legend(loc="upper right", ncols=n)


@_con_estilo
def pesos_contribucion(c):
    """5. Peso de cada activo frente a su contribución al riesgo."""
    fig, ax = plt.subplots(figsize=(max(6, 1.1 * len(c.pesos)), 4))
    _barras_agrupadas(ax, c.pesos.index, {"Peso": c.pesos,
                                         "Contribución al riesgo": c.diversificacion["contribucion"]})
    ax.yaxis.set_major_formatter(PCT)
    ax.set_title("Peso frente a contribución al riesgo")
    return fig


@_con_estilo
def rentabilidad_anual(c):
    """6. Rentabilidad de cada año natural, cartera frente al índice."""
    anual = {"Cartera": (1 + c.rp).resample("YE").prod() - 1}
    if c.rm is not None:
        anual[c.nombre_indice] = (1 + c.rm.fillna(0)).resample("YE").prod() - 1
    fig, ax = plt.subplots(figsize=(max(6, 0.9 * len(anual["Cartera"])), 4))
    _barras_agrupadas(ax, anual["Cartera"].index.year, anual)
    ax.yaxis.set_major_formatter(PCT)
    ax.set_title("Rentabilidad por año")
    return fig


@_con_estilo
def distribucion(c):
    """7. Histograma de rentabilidades diarias frente a una normal con la misma media y desviación."""
    fig, ax = plt.subplots(figsize=(8, 4))
    rp = c.rp
    ax.hist(rp, bins=80, density=True, color=SERIE[0], alpha=0.75, edgecolor=SUPERFICIE, linewidth=0.5,
            label="Cartera")
    x = np.linspace(rp.min(), rp.max(), 300)
    normal = np.exp(-((x - rp.mean()) ** 2) / (2 * rp.var())) / np.sqrt(2 * np.pi * rp.var())
    ax.plot(x, normal, color=SERIE[1], label="Normal equivalente")
    ax.axvline(c.riesgo["var95"], color=TINTA_2, linewidth=1)
    ax.annotate(" VaR 95 %", (c.riesgo["var95"], ax.get_ylim()[1] * 0.9), color=TINTA_2, fontsize=9)
    ax.xaxis.set_major_formatter(PercentFormatter(1.0, decimals=1))
    ax.set_yticks([])
    ax.grid(False)
    ax.set_title("Distribución de rentabilidades diarias")
    ax.legend(loc="upper right")
    return fig


@_con_estilo
def volatilidad_vix(c):
    """8. Volatilidad móvil de 21 sesiones (anualizada) frente al VIX, en la misma escala (%)."""
    if c.mercado.vix is None:
        return None
    fig, ax = plt.subplots(figsize=(9, 4))
    vol = c.rp.rolling(21).std() * np.sqrt(SESIONES) * 100
    ax.plot(vol.index, vol, color=SERIE[0], linewidth=1.5, label="Volatilidad de la cartera (21 sesiones)")
    vix = c.alinear_externa(c.mercado.vix.datos).reindex(c.rp.index)
    ax.plot(vix.index, vix, color=SERIE[1], linewidth=1.5, label="VIX")
    ax.set_ylabel("Volatilidad anualizada (%)")
    ax.set_title("Volatilidad de la cartera frente al VIX")
    ax.legend(loc="upper right", ncols=2)
    return fig


@_con_estilo
def correlacion_bund(c):
    """9. Correlación móvil de 60 sesiones con el ETF de Bunds."""
    serie = c.contexto.get("corr_bund_movil")
    if serie is None:
        return None
    fig, ax = plt.subplots(figsize=(9, 3.5))
    ax.plot(serie.index, serie, color=SERIE[0], linewidth=1.5)
    ax.axhline(0, color=EJE, linewidth=0.8)
    ax.set_ylim(-1, 1)
    ax.annotate("Por debajo de 0: el Bund hace de refugio", (serie.index[0], -0.92), color=TINTA_2, fontsize=9)
    ax.set_title("Correlación móvil (60 sesiones) con el ETF de Bunds")
    return fig


@_con_estilo
def exposicion(c):
    """10. Exposición por sector y por divisa."""
    div = c.diversificacion
    filas = max(len(div["sector"]), len(div["divisa"]))
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 1 + 0.45 * filas))
    for ax, datos, titulo in ((a1, div["sector"], "Por sector"), (a2, div["divisa"], "Por divisa")):
        datos = datos.sort_values()
        ax.barh(datos.index, datos, color=SERIE[0], height=0.7, edgecolor=SUPERFICIE, linewidth=2)
        for y, v in enumerate(datos):
            ax.annotate(f"{v * 100:.0f} %", (v, y), xytext=(4, 0), textcoords="offset points",
                        va="center", fontsize=9, color=TINTA_2)
        ax.xaxis.set_major_formatter(PCT)
        ax.grid(True, axis="x")
        ax.grid(False, axis="y")
        ax.set_xlim(0, max(1, datos.max() * 1.15))
        ax.set_title(titulo)
    fig.tight_layout()
    return fig


# ------------------------------------------------------------------ Monte Carlo

@_con_estilo
def abanico(res, ax=None):
    """MC1. Percentiles de las trayectorias simuladas día a día."""
    tray = res.trayectorias
    t = np.arange(tray.shape[1])
    cola = round((1 - res.parametros["confianza"]) * 100, 1)
    p = np.percentile(tray, [cola, 25, 50, 75, 100 - cola], axis=0)
    fig, ax = (ax.figure, ax) if ax else plt.subplots(figsize=(9, 4.5))
    for i in range(min(40, len(tray))):
        ax.plot(t, tray[i], color=EJE, linewidth=0.4, alpha=0.6)
    etiqueta = f"Percentiles {cola:g}–{100 - cola:g}".replace(".", ",")
    ax.fill_between(t, p[0], p[4], color=AZUL_SECUENCIAL[0], label=etiqueta, linewidth=0)
    ax.fill_between(t, p[1], p[3], color=AZUL_SECUENCIAL[1], label="Percentiles 25–75", linewidth=0)
    ax.plot(t, p[2], color=AZUL_SECUENCIAL[3], label="Mediana")
    ax.axhline(res.parametros["capital"], color=TINTA_2, linewidth=0.8)
    ax.yaxis.set_major_formatter(EUROS)
    ax.set_xlabel("Sesiones")
    ax.set_title(f"Abanico de {res.parametros['n_simulaciones']:,} trayectorias simuladas".replace(",", "."))
    ax.legend(loc="upper left", ncols=3)
    return fig


@_con_estilo
def histograma_final(res, ax=None):
    """MC2. Distribución del valor final; en rojo, los escenarios con pérdidas."""
    capital = res.parametros["capital"]
    final = res.final
    fig, ax = (ax.figure, ax) if ax else plt.subplots(figsize=(8, 4))
    bins = np.linspace(np.percentile(final, 0.5), np.percentile(final, 99.5), 70)
    ax.hist(final[final >= capital], bins=bins, color=SERIE[0], edgecolor=SUPERFICIE, linewidth=0.5,
            label="Ganancia")
    ax.hist(final[final < capital], bins=bins, color=CRITICO, edgecolor=SUPERFICIE, linewidth=0.5,
            label=f"Pérdida ({(final < capital).mean() * 100:.0f} %)")
    ax.axvline(capital, color=TINTA_2, linewidth=1)
    ax.xaxis.set_major_formatter(EUROS)
    ax.set_yticks([])
    ax.grid(False)
    ax.set_title("Valor final de los escenarios simulados")
    ax.legend(loc="upper right")
    return fig


@_con_estilo
def montecarlo_completo(res):
    """Trayectorias y distribución final juntas (lo que enseña ResultadoMC.plot)."""
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(15, 4.8), gridspec_kw={"width_ratios": [1.4, 1]})
    abanico(res, ax=a1)
    histograma_final(res, ax=a2)
    fig.tight_layout()
    return fig


# ------------------------------------------------------------------ catálogo y plots_report

CATALOGO = {
    "evolucion": evolucion,
    "drawdown": drawdown,
    "correlaciones": correlaciones,
    "riesgo_rentabilidad": riesgo_rentabilidad,
    "pesos_contribucion": pesos_contribucion,
    "rentabilidad_anual": rentabilidad_anual,
    "distribucion": distribucion,
    "volatilidad_vix": volatilidad_vix,
    "correlacion_bund": correlacion_bund,
    "exposicion": exposicion,
    "montecarlo": lambda c: montecarlo_completo(c.simulacion) if c.simulacion is not None else None,
}

TITULOS = {
    "evolucion": ("Evolución de 100 € invertidos", "Cartera frente al benchmark y al ETF de Bunds: quién ha ganado más y por qué camino."),
    "drawdown": ("Drawdown", "Cuánto cayó la cartera desde sus máximos y cuánto tardó en recuperarse."),
    "correlaciones": ("Matriz de correlaciones", "Qué activos se mueven juntos y cuál diversifica más."),
    "riesgo_rentabilidad": ("Riesgo frente a rentabilidad", "Qué activos compensan su riesgo y si la cartera arriesga menos que sus partes."),
    "pesos_contribucion": ("Peso frente a contribución al riesgo", "Qué activo pesa poco pero genera mucho riesgo."),
    "rentabilidad_anual": ("Rentabilidad por año", "Años buenos y malos, y en cuáles se batió al benchmark."),
    "distribucion": ("Distribución de rentabilidades diarias", "Si las caídas extremas son más frecuentes de lo que supone una distribución normal."),
    "volatilidad_vix": ("Volatilidad frente al VIX", "Si la cartera se agita cuando el mercado se estresa."),
    "correlacion_bund": ("Correlación móvil con el Bund", "En qué periodos el bono actuó de refugio y en cuáles no."),
    "exposicion": ("Exposición por sector y divisa", "Concentraciones que no se ven en la lista de tickers."),
    "montecarlo": ("Monte Carlo", "Trayectorias simuladas y distribución del valor final."),
}

POR_SECCION = {
    "composicion": ["exposicion"],
    "rentabilidad": ["evolucion", "rentabilidad_anual"],
    "riesgo": ["drawdown", "distribucion"],
    "ajustada": ["riesgo_rentabilidad"],
    "diversificacion": ["correlaciones", "pesos_contribucion"],
    "mercado": ["volatilidad_vix", "correlacion_bund"],
    "montecarlo": ["montecarlo"],
}
