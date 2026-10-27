"""Motor de Monte Carlo con movimiento browniano geométrico (GBM).

Cada trayectoria avanza día a día:  S_{t+1} = S_t · exp[(μ − σ²/2)·Δt + σ·√Δt·Z],  Δt = 1/252.

El mismo motor sirve para:
  · un activo suelto o la cartera vista como un único activo  → `rent` es una Series;
  · la cartera por activos, respetando sus correlaciones       → `rent` es un DataFrame + `pesos`;
    los choques se correlacionan con la descomposición de Cholesky de la matriz de covarianzas.

Todos los supuestos son parámetros: si no se indican, retorno y volatilidad salen de la historia.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

SESIONES = 252


@dataclass(eq=False)
class ResultadoMC:
    trayectorias: np.ndarray = field(repr=False)   # n_simulaciones × (horizonte + 1); columna 0 = capital
    parametros: dict
    metricas: dict = field(init=False)

    def __post_init__(self) -> None:
        capital, confianza = self.parametros["capital"], self.parametros["confianza"]
        cola = (1 - confianza) * 100
        final = self.final
        p_bajo, p_alto = np.percentile(final, [cola, 100 - cola])
        self.metricas = {
            "media": final.mean(),
            "mediana": np.median(final),
            "p_bajo": p_bajo,
            "p_alto": p_alto,
            "prob_perdida": (final < capital).mean(),
            "var_horizonte": capital - p_bajo,
            "cvar_horizonte": capital - final[final <= p_bajo].mean(),
        }

    @property
    def final(self) -> np.ndarray:
        return self.trayectorias[:, -1]

    def plot(self, mostrar: bool = True):
        """Trayectorias (abanico de percentiles) y distribución del valor final, lado a lado."""
        from ..salida.graficos import montecarlo_completo

        fig = montecarlo_completo(self)
        if mostrar:
            import matplotlib.pyplot as plt
            plt.show()
        return fig


def _por_activo(valor, columnas: pd.Index, nombre: str) -> np.ndarray:
    """Admite un número (igual para todos), un dict/Series por activo o None."""
    if isinstance(valor, (dict, pd.Series)):
        valor = pd.Series(valor)
        faltan = set(columnas) - set(valor.index)
        if faltan:
            raise ValueError(f"Falta {nombre} para: {', '.join(sorted(map(str, faltan)))}.")
        return valor[columnas].to_numpy(dtype=float)
    return np.full(len(columnas), float(valor))


def _cholesky(cov: np.ndarray) -> np.ndarray:
    try:
        return np.linalg.cholesky(cov)
    except np.linalg.LinAlgError:
        # Activos casi idénticos dejan la matriz semidefinida: se recortan los autovalores negativos.
        valores, vectores = np.linalg.eigh(cov)
        return vectores @ np.diag(np.sqrt(np.clip(valores, 0, None)))


def simular(rent: pd.Series | pd.DataFrame, pesos: pd.Series | dict | None = None, *,
            n_simulaciones: int = 10_000, horizonte: int = SESIONES, capital: float = 10_000,
            retorno: float | dict | None = None, volatilidad: float | dict | None = None,
            confianza: float = 0.95, rebalanceo: str | None = None, semilla: int | None = 42) -> ResultadoMC:
    """Simula `n_simulaciones` trayectorias de `horizonte` sesiones.

    rent:        rentabilidades diarias históricas (Series = un activo; DataFrame = varios).
    pesos:       obligatorios con varios activos.
    retorno:     rentabilidad anual supuesta (None = la histórica). Con varios activos,
                 un número para todos o un dict por activo.
    volatilidad: volatilidad anual supuesta (None = la histórica). Igual que `retorno`;
                 cambiarla mantiene las correlaciones históricas.
    confianza:   nivel del VaR y de los percentiles extremos (0,95 → percentiles 5 y 95).
    rebalanceo:  con varios activos, "monthly" (cada 21 sesiones) o None (comprar y mantener).
    semilla:     para que el resultado sea reproducible (None = aleatorio).
    """
    if n_simulaciones < 1 or horizonte < 1:
        raise ValueError("n_simulaciones y horizonte deben ser al menos 1.")
    if not 0.5 < confianza < 1:
        raise ValueError("confianza debe estar entre 0,5 y 1.")
    if capital <= 0:
        raise ValueError("El capital debe ser positivo.")

    rent = (rent.to_frame() if isinstance(rent, pd.Series) else rent).dropna()
    if len(rent) < 2:
        raise ValueError("No hay suficiente historia para estimar los parámetros.")
    columnas = rent.columns
    if pesos is None:
        if len(columnas) > 1:
            raise ValueError("Con varios activos hay que indicar los pesos.")
        pesos = {columnas[0]: 1.0}
    w = _por_activo(pesos, columnas, "peso")

    cov_hist = rent.cov().to_numpy()
    vol_hist = np.sqrt(np.diag(cov_hist) * SESIONES)
    mu = rent.mean().to_numpy() * SESIONES if retorno is None else _por_activo(retorno, columnas, "retorno")
    sigma = vol_hist if volatilidad is None else _por_activo(volatilidad, columnas, "volatilidad")
    if (sigma < 0).any():
        raise ValueError("La volatilidad no puede ser negativa.")

    # Covarianza diaria con las volatilidades elegidas y las correlaciones históricas.
    with np.errstate(invalid="ignore", divide="ignore"):
        corr = np.nan_to_num(cov_hist / np.outer(vol_hist, vol_hist) * SESIONES)
    np.fill_diagonal(corr, 1)
    d = sigma / np.sqrt(SESIONES)
    L = _cholesky(corr * np.outer(d, d))

    deriva = (mu - sigma ** 2 / 2) / SESIONES      # (μ − σ²/2)·Δt
    rng = np.random.default_rng(semilla)
    trayectorias = np.empty((n_simulaciones, horizonte + 1))
    trayectorias[:, 0] = capital
    posiciones = np.outer(np.full(n_simulaciones, float(capital)), w)   # valor de cada activo
    for t in range(1, horizonte + 1):          # día a día: no guarda simulaciones × días × activos
        posiciones *= np.exp(deriva + rng.standard_normal((n_simulaciones, len(w))) @ L.T)
        valor = posiciones.sum(axis=1)
        if rebalanceo == "monthly" and t % 21 == 0:
            posiciones = np.outer(valor, w)
        trayectorias[:, t] = valor

    parametros = {
        "metodo": "un activo" if len(columnas) == 1 else "por activos (Cholesky)",
        "n_simulaciones": n_simulaciones,
        "horizonte": horizonte,
        "capital": capital,
        "retorno": dict(zip(columnas, mu)),
        "retorno_origen": "histórico" if retorno is None else "supuesto",
        "volatilidad": dict(zip(columnas, sigma)),
        "volatilidad_origen": "histórica" if volatilidad is None else "supuesta",
        "confianza": confianza,
        "rebalanceo": rebalanceo,
        "semilla": semilla,
        "datos_desde": rent.index[0],
        "datos_hasta": rent.index[-1],
    }
    return ResultadoMC(trayectorias, parametros)
