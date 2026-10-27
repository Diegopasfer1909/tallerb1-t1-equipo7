"""Advertencias: reglas (nombre, condición, nivel, detalle) sobre las métricas ya calculadas.

Se evalúan todas y se devuelven las que se cumplen, de mayor a menor nivel.
Una condición con NaN (dato ausente) nunca salta.
"""
import pandas as pd

UMBRALES = {
    "peso_alto": 0.40,
    "peso_medio": 0.25,
    "sector_max": 0.50,
    "corr_par": 0.80,
    "corr_media": 0.60,
    "prima_min": 0.02,
    "dd_max": -0.30,
    "vol_max": 0.25,
    "vix_max": 30,
    "mc_perdida": 0.30,
    "historia_min": 252,
    "imputados_max": 0.05,
}

ORDEN_NIVEL = {"alta": 0, "media": 1}


def _pct(x: float) -> str:
    return f"{x * 100:.1f} %".replace(".", ",")


def _num(x: float) -> str:
    return f"{x:.2f}".replace(".", ",")


def evaluar(m: dict, umbrales: dict | None = None) -> list[dict]:
    """`m` agrupa las métricas por sección: composicion, rentabilidad, riesgo, ajustada,
    diversificacion, mercado, calidad y, si se ha simulado, montecarlo."""
    u = {**UMBRALES, **(umbrales or {})}
    pesos = m["composicion"]["peso_objetivo"]
    rent, riesgo, aj = m["rentabilidad"], m["riesgo"], m["ajustada"]
    div, mer, cal = m["diversificacion"], m["mercado"], m["calidad"]
    imputados = cal["imputados"]
    peso_max, ticker_max = pesos.max(), pesos.idxmax()
    sector_max = div["sector"].iloc[0]
    par = div["par_max"]

    reglas = [
        ("Concentración en un activo", peso_max > u["peso_alto"], "alta",
         f"{ticker_max} pesa un {_pct(peso_max)} (> {_pct(u['peso_alto'])})."),
        ("Concentración en un activo", u["peso_medio"] < peso_max <= u["peso_alto"], "media",
         f"{ticker_max} pesa un {_pct(peso_max)} (> {_pct(u['peso_medio'])})."),
        ("Concentración sectorial", sector_max > u["sector_max"], "media",
         f"{div['sector'].index[0]} supone un {_pct(sector_max)} de la cartera."),
        ("Activos redundantes", div["corr_par_max"] > u["corr_par"], "media",
         f"{par[0]} y {par[1]} tienen correlación {_num(div['corr_par_max'])}." if par else ""),
        ("Poca diversificación", div["corr_media"] > u["corr_media"], "media",
         f"Correlación media entre activos de {_num(div['corr_media'])}."),
        ("Riesgo no compensado", aj["sharpe"] < 0, "alta",
         f"Sharpe de {_num(aj['sharpe'])}: el Bund habría rendido más por unidad de riesgo."),
        ("Riesgo no compensado", aj["sharpe"] >= 0 and aj["prima_bund"] < u["prima_min"], "media",
         f"Prima frente al Bund de {_pct(aj['prima_bund'])} anual (< {_pct(u['prima_min'])})."),
        ("Caída máxima elevada", riesgo["drawdown"] < u["dd_max"], "alta",
         f"Drawdown máximo del {_pct(riesgo['drawdown'])}."),
        ("Volatilidad elevada", riesgo["volatilidad"] > u["vol_max"], "media",
         f"Volatilidad anualizada del {_pct(riesgo['volatilidad'])}."),
        ("Pérdida frente a la inflación", rent["real"] < 0, "media",
         f"Rentabilidad real de {_pct(rent['real'])} anual."),
        ("Riesgo de divisa", len(div["divisa"]) > 1, "media",
         "Divisas en cartera: " + ", ".join(f"{d} {_pct(p)}" for d, p in div["divisa"].items()) + "."),
        ("Mercado en estrés", mer["vix_actual"] > u["vix_max"], "media",
         f"VIX en {_num(mer['vix_actual'])}: el riesgo histórico probablemente se queda corto."),
        ("Historia corta", cal["historia"] < u["historia_min"], "alta",
         f"Solo {cal['historia']} sesiones comunes (< {u['historia_min']})."),
        ("Datos poco fiables", imputados.max() > u["imputados_max"], "media",
         "Datos imputados: " + ", ".join(f"{t} {_pct(p)}" for t, p in
                                         imputados[imputados > u["imputados_max"]].items()) + "."),
    ]
    if "montecarlo" in m:
        prob = m["montecarlo"]["prob_perdida"]
        reglas.append(("Escenarios desfavorables", prob > u["mc_perdida"], "media",
                       f"Se pierde dinero en el {_pct(prob)} de los escenarios simulados."))

    salida = [{"nombre": n, "nivel": nivel, "detalle": d}
              for n, cumple, nivel, d in reglas if bool(cumple) and not pd.isna(cumple)]
    return sorted(salida, key=lambda a: ORDEN_NIVEL[a["nivel"]])
