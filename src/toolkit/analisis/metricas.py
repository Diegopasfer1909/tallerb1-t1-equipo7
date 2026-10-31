"""Métricas del report, una función por sección.

Usan los mismos nombres que la guía: `r` (rentabilidad diaria de cada activo),
`rp` (cartera), `rm` (índice), `valor` (1 € invertido), `rf` (Bund diario) y
`rf_anual` (Bund medio del periodo). Todas devuelven un dict de cifras; si falta
el dato necesario, la cifra es NaN y el report la muestra como "n/d".
"""
import numpy as np
import pandas as pd

SESIONES = 252
NAN = float("nan")


def cagr(rent: pd.Series) -> float:
    """Rentabilidad anualizada de una serie diaria."""
    rent = rent.dropna()
    if rent.empty:
        return NAN
    return (1 + rent).prod() ** (SESIONES / len(rent)) - 1


def _juntas(*series: pd.Series) -> pd.DataFrame:
    """Alinea varias series y quita las fechas con algún vacío (dropna sobre todas a la vez)."""
    return pd.concat(series, axis=1).dropna()


# ---------------------------------------------------------------- Base: valor de la cartera

def evolucion_cartera(precios: pd.DataFrame, pesos: pd.Series, rebalanceo: str | None) -> pd.DataFrame:
    """Valor de cada posición de 1 € invertido al inicio.

    rebalanceo=None:      comprar y mantener; los pesos derivan con los precios.
    rebalanceo="monthly": al cierre de cada mes se vuelve a los pesos objetivo.
    """
    crecimiento = 1 + precios.pct_change().fillna(0)
    if rebalanceo is None:
        return crecimiento.cumprod() * pesos
    tramos, capital = [], 1.0
    for _, mes in crecimiento.groupby(precios.index.to_period("M")):
        tramo = capital * pesos * mes.cumprod()
        tramos.append(tramo)
        capital = tramo.iloc[-1].sum()
    return pd.concat(tramos)


# ---------------------------------------------------------------- 3. Composición

def composicion(r: pd.DataFrame, pesos: pd.Series, pesos_actuales: pd.Series, info: dict) -> pd.DataFrame:
    tabla = pd.DataFrame({
        "nombre": {t: info[t]["nombre"] for t in pesos.index},
        "sector": {t: info[t]["sector"] for t in pesos.index},
        "divisa": {t: info[t]["divisa"] for t in pesos.index},
        "pais": {t: info[t]["pais"] for t in pesos.index},
        "peso_objetivo": pesos,
        "peso_actual": pesos_actuales,
        "media_diaria": r.mean(),
        "std_diaria": r.std(),
    })
    return tabla.loc[pesos.index]


# ---------------------------------------------------------------- 4. Rentabilidad

def rentabilidad(rp: pd.Series, valor: pd.Series, rm: pd.Series | None,
                 rf_anual: float, hicp: pd.Series | None) -> dict:
    cagr_p = cagr(rp)
    mensual = (1 + rp).resample("ME").prod() - 1

    pi = NAN
    if hicp is not None:
        hicp_p = hicp.loc[rp.index[0]:rp.index[-1]]
        if len(hicp_p) >= 2:
            pi = (hicp_p.iloc[-1] / hicp_p.iloc[0]) ** (12 / (len(hicp_p) - 1)) - 1

    return {
        "multiplo": valor.iloc[-1],          # valor final de 1 € invertido
        "acumulada": valor.iloc[-1] - 1,
        "cagr": cagr_p,
        "cagr_indice": cagr(rm) if rm is not None else NAN,
        "dif_indice": cagr_p - cagr(rm) if rm is not None else NAN,
        "dif_bund": cagr_p - rf_anual,
        "inflacion": pi,
        "real": (1 + cagr_p) / (1 + pi) - 1,
        "mejor_mes": mensual.max(),
        "mejor_mes_fecha": mensual.idxmax(),
        "peor_mes": mensual.min(),
        "peor_mes_fecha": mensual.idxmin(),
        "mensual": mensual,
    }


# ---------------------------------------------------------------- 5. Riesgo

def riesgo(rp: pd.Series, valor: pd.Series, rm: pd.Series | None) -> dict:
    dd = valor / valor.cummax() - 1
    valle = dd.idxmin()
    pico = valor[:valle].idxmax()
    tras_valle = valor[valle:]
    rec = tras_valle[tras_valle >= valor[pico]].index.min()   # NaT si no se recupera

    var = rp.quantile(0.05)

    beta = NAN
    if rm is not None:
        datos = _juntas(rp, rm)
        beta = datos.iloc[:, 0].cov(datos.iloc[:, 1]) / datos.iloc[:, 1].var()

    return {
        "volatilidad": rp.std() * np.sqrt(SESIONES),
        "drawdown": dd.min(),
        "dd_serie": dd,
        "dd_pico": pico,
        "dd_valle": valle,
        "dd_recuperacion": rec,
        "var95": var,
        "cvar95": rp[rp <= var].mean(),
        "beta": beta,
    }


# ---------------------------------------------------------------- 6. Rentabilidad ajustada al riesgo

def ajustada(rp: pd.Series, rm: pd.Series | None, rf: pd.Series, rf_anual: float) -> dict:
    exceso = rp - rf
    sharpe = exceso.mean() / exceso.std() * np.sqrt(SESIONES)
    down = np.sqrt((exceso.clip(upper=0) ** 2).mean()) * np.sqrt(SESIONES)
    sortino = exceso.mean() * SESIONES / down if down > 0 else NAN

    alfa = NAN
    if rm is not None:
        datos = _juntas(rm - rf, exceso)
        if len(datos) > 2:
            _, alfa_d = np.polyfit(datos.iloc[:, 0], datos.iloc[:, 1], 1)
            alfa = alfa_d * SESIONES

    return {
        "sharpe": sharpe,
        "sortino": sortino,
        "alfa": alfa,
        "prima_bund": cagr(rp) - rf_anual,
        "rf_anual": rf_anual,
    }


# ---------------------------------------------------------------- 7. Diversificación

def diversificacion(r: pd.DataFrame, pesos: pd.Series, sector: pd.Series, divisa: pd.Series) -> dict:
    corr = r.corr()
    mask = np.triu(np.ones(corr.shape, dtype=bool), k=1)
    hay_pares = mask.any()

    cov = r.cov() * SESIONES
    w = pesos[cov.index]
    sigma_p = np.sqrt(w @ cov @ w)
    rc = w * (cov @ w) / sigma_p

    return {
        "corr": corr,
        "corr_media": corr.values[np.triu_indices_from(corr, k=1)].mean() if hay_pares else NAN,
        "par_max": corr.where(mask).stack().idxmax() if hay_pares else None,
        "corr_par_max": corr.where(mask).max().max() if hay_pares else NAN,
        "hhi": (pesos ** 2).sum(),
        "n_efectivo": 1 / (pesos ** 2).sum(),
        "contribucion": rc / sigma_p,
        "sigma_p": sigma_p,
        "sector": pesos.groupby(sector).sum().sort_values(ascending=False),
        "divisa": pesos.groupby(divisa).sum().sort_values(ascending=False),
    }


# ---------------------------------------------------------------- 8. Contexto de mercado

def efecto_divisa(p_local: pd.Series, p_eur: pd.Series) -> float:
    """CAGR en EUR − CAGR en la divisa original."""
    return cagr(p_eur.pct_change().dropna()) - cagr(p_local.pct_change().dropna())


def mercado(rp: pd.Series, vix: pd.Series | None, rent_externas: dict[str, pd.Series]) -> dict:
    """`rent_externas`: rentabilidades diarias ya alineadas a rp (brent, oro, etf_bund)."""
    salida = {"vix_actual": NAN, "vix_media": NAN}
    if vix is not None:
        vix_p = vix.loc[rp.index[0]:rp.index[-1]]
        if not vix_p.empty:
            salida.update(vix_actual=vix_p.iloc[-1], vix_media=vix_p.mean(), vix_fecha=vix_p.index[-1])

    for nombre in ("brent", "oro", "etf_bund"):
        x = rent_externas.get(nombre)
        salida[f"corr_{nombre}"] = rp.corr(x) if x is not None else NAN

    rb = rent_externas.get("etf_bund")
    if rb is not None:
        salida["corr_bund_movil"] = rp.rolling(60).corr(rb)
        salida["bund_peores_dias"] = rb[rp <= rp.quantile(0.05)].mean()
    else:
        salida["bund_peores_dias"] = NAN
    return salida


# ---------------------------------------------------------------- 10. Calidad de los datos

def calidad(limpieza, rp: pd.Series, fuentes: dict, fallos: list, sin_ajustar: list[str]) -> dict:
    """`limpieza`: InformeLimpieza del preprocesado (la calidad se mide antes de limpiar)."""
    return {
        "imputados": limpieza.imputados,
        "fechas_descartadas": limpieza.fechas_descartadas,
        "fines_de_semana": limpieza.fines_de_semana,
        "saltos": limpieza.saltos,
        "historia": len(rp),
        "desde": rp.index[0],
        "hasta": rp.index[-1],
        "fuentes": fuentes,
        "fallos": fallos,
        "sin_ajustar": sin_ajustar,
    }
