"""Validación de inputs y limpieza de precios antes de calcular nada.

Criterio general (justificado en el README): los errores que harían que las cifras
fueran falsas detienen el programa; los defectos que solo las hacen menos fiables se
corrigen y se registran para que el report los muestre.
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..modelos.series import PriceSeries

MIN_SESIONES = 30          # por debajo, error; entre esto y 252, advertencia de historia corta


@dataclass
class InformeLimpieza:
    precios_brutos: pd.DataFrame      # periodo común, antes de rellenar: aquí se cuentan los huecos
    imputados: pd.Series              # % de valores rellenados por activo
    fechas_descartadas: int           # sesiones con huecos más largos que el límite de relleno
    fines_de_semana: int              # fechas en sábado o domingo eliminadas
    saltos: list[tuple] = field(default_factory=list)   # (ticker, fecha, rentabilidad) sospechosas


def validar_activos(activos: list) -> list[PriceSeries]:
    if not activos:
        raise ValueError("La cartera necesita al menos un activo.")
    ajenos = [type(a).__name__ for a in activos if not isinstance(a, PriceSeries)]
    if ajenos:
        raise TypeError(f"Los activos deben ser PriceSeries (recibido: {', '.join(set(ajenos))}). "
                        "Usa un proveedor de toolkit.ingesta o crea la PriceSeries a mano.")
    symbols = [a.symbol for a in activos]
    repetidos = {s for s in symbols if symbols.count(s) > 1}
    if repetidos:
        raise ValueError(f"Activos repetidos: {', '.join(repetidos)}.")
    return activos


def validar_pesos(pesos: dict | list | pd.Series, symbols: list[str]) -> pd.Series:
    if isinstance(pesos, (list, tuple, np.ndarray)):
        if len(pesos) != len(symbols):
            raise ValueError(f"Hay {len(pesos)} pesos para {len(symbols)} activos.")
        pesos = dict(zip(symbols, pesos))
    pesos = pd.Series(pesos, dtype=float)
    if set(pesos.index) != set(symbols):
        sobran, faltan = set(pesos.index) - set(symbols), set(symbols) - set(pesos.index)
        raise ValueError(f"Pesos y activos no coinciden. Sin activo: {sorted(sobran) or '—'}; "
                         f"sin peso: {sorted(faltan) or '—'}.")
    if pesos.isna().any():
        raise ValueError("Hay pesos vacíos.")
    if (pesos < 0).any():
        raise ValueError("Hay pesos negativos: la cartera no admite posiciones cortas.")
    if not np.isclose(pesos.sum(), 1):
        raise ValueError(f"Los pesos deben sumar 1 (suman {pesos.sum():.4f}).")
    return pesos[symbols]


def alinear(precios: dict[str, pd.Series], limite_relleno: int = 5,
            salto_maximo: float = 0.5) -> tuple[pd.DataFrame, InformeLimpieza]:
    """Lleva varias series de precios a un mismo calendario.

    1. Quita sábados y domingos (activos que cotizan siempre, como las criptomonedas,
       llenarían de ceros las rentabilidades del resto).
    2. Se queda con el periodo en que todos los activos tienen datos.
    3. Rellena con el último cierre los días en que un mercado estaba cerrado y otro no,
       hasta `limite_relleno` sesiones seguidas; si el hueco es más largo, descarta esas fechas.
    4. Marca (sin tocar) las rentabilidades diarias mayores que `salto_maximo`, que suelen
       ser splits mal ajustados o errores de la fuente.
    """
    tabla = pd.DataFrame(precios).sort_index()
    laborables = tabla.index.day_of_week < 5
    fines = int((~laborables).sum())
    tabla = tabla[laborables]

    inicio = max(tabla[c].first_valid_index() for c in tabla)
    fin = min(tabla[c].last_valid_index() for c in tabla)
    if inicio is None or fin is None or inicio >= fin:
        raise ValueError("Los activos no tienen ningún periodo en común.")
    brutos = tabla.loc[inicio:fin]
    rellenos = tabla.ffill(limit=limite_relleno).loc[inicio:fin]
    limpios = rellenos.dropna()

    rent = limpios.pct_change()
    saltos = [(t, f, v) for (f, t), v in rent.stack().items() if abs(v) > salto_maximo]

    informe = InformeLimpieza(
        precios_brutos=brutos,
        imputados=brutos.isna().mean(),
        fechas_descartadas=len(rellenos) - len(limpios),
        fines_de_semana=fines,
        saltos=saltos,
    )
    return limpios, informe
