"""Genera el report en Markdown: hasta diez secciones, todas por defecto.

Solo lee métricas ya calculadas por la Cartera; no calcula ni simula nada por su cuenta.
"""
import base64
import io
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from . import graficos

SECCIONES = {
    "resumen": ("1. Resumen", "¿Cómo ha ido, en cinco cifras?"),
    "advertencias": ("2. Advertencias", "¿Qué hay que vigilar?"),
    "composicion": ("3. Composición", "¿Qué contiene la cartera?"),
    "rentabilidad": ("4. Rentabilidad", "¿Cuánto ha ganado?"),
    "riesgo": ("5. Riesgo", "¿Cuánto ha arriesgado?"),
    "ajustada": ("6. Rentabilidad ajustada al riesgo", "¿Ha compensado el riesgo?"),
    "diversificacion": ("7. Diversificación", "¿Está bien repartida?"),
    "mercado": ("8. Contexto de mercado", "¿Qué pasa fuera de la cartera que le afecte?"),
    "montecarlo": ("9. Monte Carlo", "¿Qué puede pasar a futuro?"),
    "calidad": ("10. Calidad de los datos", "¿Cuánto fiarse de todo lo anterior?"),
}
REBALANCEO = {"monthly": "rebalanceo mensual", None: "sin rebalanceo (comprar y mantener)"}


class Informe(str):
    """Texto Markdown: en la consola se lee tal cual y Jupyter lo muestra ya renderizado.
    `archivo`: dónde se ha guardado."""
    archivo: Path | None = None

    def __repr__(self) -> str:
        pie = f"\n[Guardado en {self.archivo}]" if self.archivo else ""
        return str(self) + pie

    def _repr_markdown_(self) -> str:
        return str(self)


# ------------------------------------------------------------------ formato español

def _nd(x) -> bool:
    return x is None or pd.isna(x)


def pct(x, dec: int = 1, signo: bool = False) -> str:
    if _nd(x):
        return "n/d"
    return f"{x * 100:{'+' if signo else ''}.{dec}f} %".replace(".", ",")


def pts(x) -> str:
    """Diferencia de rentabilidades en puntos porcentuales por año."""
    return "n/d" if _nd(x) else f"{x * 100:+.1f}".replace(".", ",") + " p.p./año"


def num(x, dec: int = 2) -> str:
    return "n/d" if _nd(x) else f"{x:.{dec}f}".replace(".", ",")


def eur(x) -> str:
    return "n/d" if _nd(x) else f"{x:,.0f} €".replace(",", ".")


def fecha(d) -> str:
    return "—" if _nd(d) else f"{d:%d/%m/%Y}"


def tabla(cabecera: list[str], filas: list[list]) -> str:
    lineas = ["| " + " | ".join(cabecera) + " |", "|" + "---|" * len(cabecera)]
    lineas += ["| " + " | ".join(str(v) for v in fila) + " |" for fila in filas]
    return "\n".join(lineas)


# ------------------------------------------------------------------ lecturas (umbrales de la guía)

def _tramos(x, cortes: list[tuple[float, str]], ultimo: str) -> str:
    if _nd(x):
        return ""
    for limite, texto in cortes:
        if x < limite:
            return texto
    return ultimo


def lee_sharpe(x):
    return _tramos(x, [(0, "malo"), (0.5, "pobre"), (1, "aceptable")], "bueno")


def lee_volatilidad(x):
    return _tramos(x, [(0.15, "baja"), (0.20, "como un índice amplio"), (0.25, "elevada")],
                   "como una acción suelta")


def lee_drawdown(x):
    return _tramos(x, [(-0.30, "caída de crisis fuerte"), (-0.15, "caída notable")], "caída moderada")


def lee_beta(x):
    return _tramos(x, [(0.8, "defensiva"), (1.2, "se mueve como el índice")], "amplifica al mercado")


def lee_corr_media(x):
    return _tramos(x, [(0.3, "buena diversificación"), (0.6, "moderada")], "los activos caen a la vez")


def lee_vix(x):
    return _tramos(x, [(15, "calma"), (25, "normal"), (30, "nerviosismo")], "estrés")


def lee_signo(x, positivo: str, negativo: str):
    return "" if _nd(x) else (positivo if x > 0 else negativo)


# ------------------------------------------------------------------ secciones

def _resumen(c, **_) -> str:
    rent, riesgo, aj = c.rentabilidad, c.riesgo, c.ajustada
    cal = c.calidad
    cabecera = (f"{fecha(cal['desde'])} – {fecha(cal['hasta'])} · {cal['historia']} sesiones · "
                f"referencia: {c.nombre_indice} · "
                f"{REBALANCEO[c.rebalanceo]}")
    filas = [
        [f"Valor final de {eur(c.capital_inicial)}", f"**{eur(c.capital_inicial * rent['multiplo'])}**",
         f"{pct(rent['acumulada'], signo=True)} en total, {pct(rent['cagr'])} al año"],
        ["Diferencia frente al índice", f"**{pts(rent['dif_indice'])}**",
         lee_signo(rent["dif_indice"], "batió al índice", "habría sido mejor comprar el índice")],
        ["Diferencia frente al Bund", f"**{pts(rent['dif_bund'])}**",
         lee_signo(rent["dif_bund"], "la bolsa compensó", "el Bund habría rendido más")],
        ["Drawdown máximo", f"**{pct(riesgo['drawdown'])}**", lee_drawdown(riesgo["drawdown"])],
        ["Ratio de Sharpe", f"**{num(aj['sharpe'])}**", lee_sharpe(aj["sharpe"])],
    ]
    return cabecera + "\n\n" + tabla(["Cifra", "Valor", "Lectura"], filas)


def _advertencias(c, umbrales: dict | None, **_) -> str:
    lista = c.advertencias(umbrales)
    if not lista:
        return "Ninguna advertencia salta con los umbrales actuales."
    icono = {"alta": "🔴 **Alta**", "media": "🟠 **Media**"}
    filas = [[icono[a["nivel"]], a["nombre"], a["detalle"]] for a in lista]
    return tabla(["Nivel", "Advertencia", "Detalle"], filas)


def _composicion(c, **_) -> str:
    comp = c.composicion
    cab = ["Ticker", "Nombre", "Sector", "Divisa", "País", "Peso objetivo", "Importe inicial", "Peso actual",
           "Media diaria", "Desv. típica diaria"]
    filas = [[t, f["nombre"], f["sector"], f["divisa"], f["pais"] or "—", pct(f["peso_objetivo"]),
              eur(c.capital_inicial * f["peso_objetivo"]), pct(f["peso_actual"]), pct(f["media_diaria"], 3),
              pct(f["std_diaria"], 2)]
             for t, f in comp.iterrows()]
    nota = ("Valores diarios: se entienden mejor anualizados en las secciones 4 y 5. "
            "Precios convertidos a euros." if (comp["divisa"] != "EUR").any() else
            "Valores diarios: se entienden mejor anualizados en las secciones 4 y 5.")
    return tabla(cab, filas) + "\n\n" + nota


def _rentabilidad(c, **_) -> str:
    m = c.rentabilidad
    filas = [
        ["Rentabilidad acumulada", pct(m["acumulada"], signo=True), "de principio a fin"],
        ["Rentabilidad anualizada (CAGR)", pct(m["cagr"]), "en renta variable, 6–9 % anual es lo habitual"],
        [f"CAGR de {c.nombre_indice}", pct(m["cagr_indice"]), ""],
        ["Diferencia frente al índice", pts(m["dif_indice"]),
         lee_signo(m["dif_indice"], "la cartera batió al índice", "el índice rindió más")],
        ["Inflación media anual (HICP)", pct(m["inflacion"]), ""],
        ["Rentabilidad real", pct(m["real"]),
         lee_signo(m["real"], "ganó poder de compra", "perdió frente a la inflación")],
        ["Mejor mes", pct(m["mejor_mes"], signo=True), f"{m['mejor_mes_fecha']:%m/%Y}"],
        ["Peor mes", pct(m["peor_mes"], signo=True), f"{m['peor_mes_fecha']:%m/%Y}"],
    ]
    return tabla(["Métrica", "Valor", "Lectura"], filas)


def _riesgo(c, **_) -> str:
    m = c.riesgo
    rec = fecha(m["dd_recuperacion"]) if pd.notna(m["dd_recuperacion"]) else "sin recuperar"
    filas = [
        ["Volatilidad anualizada", pct(m["volatilidad"]), lee_volatilidad(m["volatilidad"])],
        ["Drawdown máximo", pct(m["drawdown"]),
         f"{lee_drawdown(m['drawdown'])}: pico {fecha(m['dd_pico'])}, valle {fecha(m['dd_valle'])}, "
         f"recuperación {rec}"],
        ["VaR 95 % diario", pct(m["var95"], 2), "uno de cada 20 días se pierde al menos esto"],
        ["CVaR 95 % diario", pct(m["cvar95"], 2), "pérdida media en ese 5 % de peores días"],
        ["Beta", num(m["beta"]), lee_beta(m["beta"])],
    ]
    return tabla(["Métrica", "Valor", "Lectura"], filas)


def _ajustada(c, **_) -> str:
    m = c.ajustada
    sortino_lee = ""
    if not (_nd(m["sortino"]) or _nd(m["sharpe"])):
        sortino_lee = ("volatilidad sobre todo al alza" if m["sortino"] > 1.5 * m["sharpe"] > 0
                       else "similar al Sharpe")
    filas = [
        ["Ratio de Sharpe", num(m["sharpe"]), lee_sharpe(m["sharpe"])],
        ["Ratio de Sortino", num(m["sortino"]), sortino_lee],
        ["Alfa de Jensen (anual)", pct(m["alfa"], signo=True),
         lee_signo(m["alfa"], "la selección de valores aportó", "habría sido mejor comprar el índice")],
        ["Prima frente al Bund", pts(m["prima_bund"]),
         "" if _nd(m["prima_bund"]) else
         ("poca compensación para el riesgo de la bolsa" if m["prima_bund"] < 0.02 else "compensó")],
        ["Bund 10 años medio del periodo", pct(m["rf_anual"], 2), "tipo libre de riesgo"],
    ]
    return tabla(["Métrica", "Valor", "Lectura"], filas)


def _diversificacion(c, **_) -> str:
    m = c.diversificacion
    par = m["par_max"]
    filas = [
        ["Correlación media", num(m["corr_media"]), lee_corr_media(m["corr_media"])],
        ["Par más correlacionado", f"{par[0]} – {par[1]}: {num(m['corr_par_max'])}" if par else "n/d",
         "casi redundantes" if m["corr_par_max"] > 0.8 else ""],
        ["Nº efectivo de activos", f"{num(m['n_efectivo'], 1)} de {len(c.pesos)}",
         f"en la práctica, unas {m['n_efectivo']:.0f} apuestas distintas"],
    ]
    contrib = tabla(["Ticker", "Peso", "Contribución al riesgo"],
                    [[t, pct(c.pesos[t]), pct(m["contribucion"][t])] for t in c.pesos.index])
    sector = ", ".join(f"{s} {pct(p, 0)}" for s, p in m["sector"].items())
    divisa = ", ".join(f"{d} {pct(p, 0)}" for d, p in m["divisa"].items())
    return (tabla(["Métrica", "Valor", "Lectura"], filas) + "\n\n" + contrib +
            f"\n\n**Por sector:** {sector}  \n**Por divisa:** {divisa}")


def _mercado(c, **_) -> str:
    m = c.contexto
    filas = [
        ["VIX actual", f"{num(m['vix_actual'], 1)} (media del periodo {num(m['vix_media'], 1)})",
         lee_vix(m["vix_actual"])],
        ["Correlación con el Brent", num(m["corr_brent"]),
         lee_signo(m["corr_brent"], "sensible al petróleo", "le perjudica que suba el petróleo")],
        ["Correlación con el oro", num(m["corr_oro"]),
         "" if _nd(m["corr_oro"]) else
         ("el oro aportaría diversificación" if m["corr_oro"] < 0.2 else "el oro diversifica poco")],
        ["Correlación con el ETF de Bunds", num(m["corr_etf_bund"]),
         lee_signo(m["corr_etf_bund"], "caen juntos", "el Bund hace de refugio")],
        ["Bund en el 5 % de peores días", pct(m["bund_peores_dias"], 2, signo=True),
         lee_signo(m["bund_peores_dias"], "protegió", "no protegió")],
    ]
    partes = [tabla(["Métrica", "Valor", "Lectura"], filas)]

    efecto = m["efecto_divisa"]
    if not efecto.empty:
        partes.append("**Efecto divisa** (CAGR en EUR − CAGR en la divisa original):\n\n" + tabla(
            ["Ticker", "Divisa", "Efecto"],
            [[t, c.info[t]["divisa"], pts(e) + " · " + lee_signo(e, "el tipo de cambio sumó", "restó")]
             for t, e in efecto.items()]))

    ausentes = [f for f in c.mercado.fallos if f in ("Índice", "VIX", "Brent", "Oro", "ETF de Bunds")]
    if ausentes:
        partes.append(f"_Sin datos de: {', '.join(ausentes)}._")
    return "\n\n".join(partes)


AVISO_MC = ("> ⚠️ **No se ha configurado la simulación.** Ejecuta `cartera.montecarlo(...)` "
            "antes de `report()` para incluir esta sección; por ejemplo, "
            "`cartera.montecarlo(n_simulaciones=10_000, horizonte=252)`.")


def _montecarlo(c, **_) -> str:
    res = c.simulacion
    if res is None:
        return AVISO_MC
    p, m = res.parametros, res.metricas
    cola = round((1 - p["confianza"]) * 100, 1)
    bajo, alto = f"{cola:g}".replace(".", ","), f"{100 - cola:g}".replace(".", ",")
    retorno = ", ".join(f"{k} {pct(v)}" for k, v in p["retorno"].items())
    volatilidad = ", ".join(f"{k} {pct(v)}" for k, v in p["volatilidad"].items())
    filas = [
        ["Método", p["metodo"]],
        ["Capital inicial", eur(p["capital"])],
        ["Horizonte", f"{p['horizonte']} sesiones (~{p['horizonte'] / 252:.1f} años)".replace(".", ",")],
        ["Simulaciones", f"{p['n_simulaciones']:,}".replace(",", ".")],
        [f"Retorno anual ({p['retorno_origen']})", retorno],
        [f"Volatilidad anual ({p['volatilidad_origen']})", volatilidad],
        ["Historia usada para estimar", f"{fecha(p['datos_desde'])} – {fecha(p['datos_hasta'])}"],
        ["Nivel de confianza", pct(p["confianza"], 0)],
        ["Semilla", p["semilla"] if p["semilla"] is not None else "aleatoria"],
    ]
    if p["metodo"] != "un activo":
        filas.insert(1, ["Rebalanceo", REBALANCEO[p["rebalanceo"]]])
    resultados = tabla(["Métrica", "Valor", "Lectura"], [
        ["Mediana del valor final", eur(m["mediana"]), "escenario central, no una predicción"],
        [f"Percentiles {bajo} y {alto}", f"{eur(m['p_bajo'])} – {eur(m['p_alto'])}",
         f"el {pct(2 * p['confianza'] - 1, 0)} de los escenarios cae aquí"],
        ["Probabilidad de pérdida", pct(m["prob_perdida"]),
         "se pierde en casi 1 de cada 3 escenarios o más" if m["prob_perdida"] > 0.3 else ""],
        [f"VaR al horizonte ({pct(p['confianza'], 0)})", eur(m["var_horizonte"]),
         f"con un {pct(p['confianza'], 0)} de confianza no se perdería más de esto" if m["var_horizonte"] > 0
         else f"negativo: incluso el percentil {bajo} acaba con ganancia"],
        ["CVaR al horizonte", eur(m["cvar_horizonte"]), "pérdida media en los escenarios peores que el VaR"],
    ])
    return ("**Parámetros**\n\n" + tabla(["Parámetro", "Valor"], filas) +
            "\n\n**Resultados**\n\n" + resultados)


def _calidad(c, **_) -> str:
    m = c.calidad
    imput = tabla(["Ticker", "% imputado", "Lectura"],
                  [[t, pct(v, 2), "menos fiable" if v > 0.05 else ""] for t, v in m["imputados"].items()])
    fuentes = tabla(["Serie", "Fuente"], [[k, v] for k, v in m["fuentes"].items()]) if m["fuentes"] else \
        "_Datos proporcionados por el usuario._"
    historia = (f"**Historia común:** {m['historia']} sesiones ({fecha(m['desde'])} – {fecha(m['hasta'])})"
                + (" — menos de un año: métricas poco fiables." if m["historia"] < 252 else "."))
    limpieza = (f"**Limpieza:** {m['fechas_descartadas']} sesiones descartadas por huecos largos; "
                f"{m['fines_de_semana']} fechas en fin de semana eliminadas.")
    if m["saltos"]:
        limpieza += " Saltos diarios sospechosos (> 50 %): " + ", ".join(
            f"{t} {fecha(f)} ({pct(v, 0, signo=True)})" for t, f, v in m["saltos"][:10]) + "."
    if m["sin_ajustar"]:
        limpieza += (f" Precios sin ajustar por dividendos: {', '.join(m['sin_ajustar'])} "
                     "(su rentabilidad está infravalorada).")
    fallos = (f"**Fuentes que fallaron:** {', '.join(m['fallos'])}." if m["fallos"]
              else "**Fuentes que fallaron:** ninguna.")
    return "\n\n".join([historia, imput, limpieza, fuentes, fallos])


CONSTRUCTORES = {
    "resumen": _resumen, "advertencias": _advertencias, "composicion": _composicion,
    "rentabilidad": _rentabilidad, "riesgo": _riesgo, "ajustada": _ajustada,
    "diversificacion": _diversificacion, "mercado": _mercado, "montecarlo": _montecarlo,
    "calidad": _calidad,
}


# ------------------------------------------------------------------ montaje

def _imagen(fig, nombre: str, ruta: Path | None, cerrar: bool = True) -> str:
    if ruta is not None:
        (ruta / "graficos").mkdir(parents=True, exist_ok=True)
        fig.savefig(ruta / "graficos" / f"{nombre}.png")
        texto = f"![{nombre}](graficos/{nombre}.png)"
    else:
        buffer = io.BytesIO()
        fig.savefig(buffer, format="png")
        datos = base64.b64encode(buffer.getvalue()).decode()
        texto = f'<img src="data:image/png;base64,{datos}" alt="{nombre}" style="max-width:100%">'
    if cerrar:
        plt.close(fig)
    return texto


def _graficos(c, clave: str, ruta: Path | None) -> list[str]:
    salida = []
    for nombre in graficos.POR_SECCION.get(clave, []):
        fig = graficos.CATALOGO[nombre](c)
        if fig is not None:
            salida.append(_imagen(fig, nombre, ruta))
    return salida


def _desplegable(clave: str, cuerpo: str) -> str:
    """Cada sección es un desplegable: en el .md se ve el título y se abre con un clic."""
    titulo, pregunta = SECCIONES[clave]
    return f"<details>\n<summary><b>{titulo}</b> — {pregunta}</summary>\n\n{cuerpo}\n\n</details>"


def generar(c, secciones: list[str] | None = None, *, umbrales: dict | None = None, graficos: bool = False, ruta: str | Path | None = "informe") -> Informe:
    if secciones is None:
        secciones = list(SECCIONES)
    desconocidas = set(secciones) - SECCIONES.keys()
    if desconocidas:
        raise ValueError(f"Secciones desconocidas: {', '.join(desconocidas)}. Disponibles: {', '.join(SECCIONES)}.")

    ruta = Path(ruta) if ruta is not None else None
    bloques = [f"# {c.nombre}"]
    for clave in [s for s in SECCIONES if s in secciones]:
        cuerpo = CONSTRUCTORES[clave](c, umbrales=umbrales)
        if graficos:
            cuerpo = "\n\n".join([cuerpo, *_graficos(c, clave, ruta)])
        bloques.append(_desplegable(clave, cuerpo))

    return _guardar("\n\n".join(bloques), ruta, "report.md")


def generar_graficos(c, nombres: list[str] | None = None, *, ruta: str | Path | None = "informe",
                     mostrar: bool = False) -> Informe:
    """Report de gráficos: un desplegable por gráfico, en <ruta>/graficos.md."""
    nombres = list(graficos.CATALOGO) if nombres is None else list(nombres)
    desconocidos = set(nombres) - graficos.CATALOGO.keys()
    if desconocidos:
        raise ValueError(f"Gráficos desconocidos: {', '.join(desconocidos)}. "
                         f"Disponibles: {', '.join(graficos.CATALOGO)}.")

    ruta = Path(ruta) if ruta is not None else None
    bloques, figuras = [f"## {c.nombre} — gráficos"], []
    for nombre in nombres:
        titulo, descripcion = graficos.TITULOS[nombre]
        fig = graficos.CATALOGO[nombre](c)
        if fig is not None:
            figuras.append(fig)
            cuerpo = f"_{descripcion}_\n\n{_imagen(fig, nombre, ruta, cerrar=False)}"
        elif nombre == "montecarlo":
            cuerpo = AVISO_MC
        else:
            cuerpo = "_Sin datos para este gráfico: la fuente no estaba disponible (ver calidad de los datos)._"
        bloques.append(f"<details>\n<summary><b>{titulo}</b></summary>\n\n{cuerpo}\n\n</details>")

    if mostrar:
        plt.show()
    for fig in figuras:
        plt.close(fig)
    return _guardar("\n\n".join(bloques), ruta, "graficos.md")


def _guardar(texto: str, ruta: Path | None, archivo: str) -> Informe:
    informe = Informe(texto + "\n")
    if ruta is not None:
        ruta.mkdir(parents=True, exist_ok=True)
        informe.archivo = (ruta / archivo).resolve()
        informe.archivo.write_text(informe, encoding="utf-8")
    return informe
