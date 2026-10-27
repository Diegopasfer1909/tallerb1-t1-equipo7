"""DataClasses de series temporales: el formato común en que llegan los datos de cualquier fuente.

    Serie            valores + metadatos; media y desviación típica de los valores
    ├── PriceSeries  precios de un activo; media y desviación típica de sus rentabilidades
    └── MacroSeries  indicador económico (tipos, inflación, VIX...) con su unidad
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

SESIONES = 252
TIPOS_ACTIVO = ("accion", "indice", "etf", "materia_prima", "divisa", "otro")


def _normalizar(datos: pd.Series, symbol: str) -> pd.Series:
    """Índice de fechas sin hora ni zona, ordenado y sin duplicados; valores numéricos sin vacíos."""
    if not isinstance(datos, pd.Series):
        raise TypeError(f"{symbol}: los datos deben ser una pandas.Series, no {type(datos).__name__}.")
    try:
        indice = pd.DatetimeIndex(datos.index)
    except (TypeError, ValueError) as error:
        raise TypeError(f"{symbol}: el índice debe ser de fechas.") from error
    if indice.tz is not None:
        indice = indice.tz_localize(None)
    datos = pd.Series(pd.to_numeric(datos.to_numpy(), errors="coerce"),
                      index=indice.normalize().rename("fecha"))
    # Si una fuente repite una fecha (p. ej. el cierre provisional del día), vale el último dato.
    datos = datos[~datos.index.duplicated(keep="last")].sort_index().dropna()
    if len(datos) < 2:
        raise ValueError(f"{symbol}: hacen falta al menos dos observaciones válidas.")
    return datos.rename(symbol)


@dataclass(eq=False)
class Serie:
    symbol: str
    source: str
    datos: pd.Series = field(repr=False)
    nombre: str = ""
    media: float = field(init=False)
    desviacion: float = field(init=False)

    def __post_init__(self) -> None:
        self.datos = _normalizar(self.datos, self.symbol)
        self.nombre = self.nombre or self.symbol
        self._calcular_estadisticos()

    def _calcular_estadisticos(self) -> None:
        self.media = float(self.datos.mean())
        self.desviacion = float(self.datos.std())

    @property
    def inicio(self) -> pd.Timestamp:
        return self.datos.index[0]

    @property
    def fin(self) -> pd.Timestamp:
        return self.datos.index[-1]


@dataclass(eq=False)
class PriceSeries(Serie):
    """Cierres de un activo cotizado. Los estadísticos se calculan sobre las rentabilidades
    diarias: `media` y `desviacion` son diarias; `media_anual` y `volatilidad_anual`, anualizadas."""
    divisa: str = "EUR"
    tipo: str = "accion"
    sector: str = "Desconocido"
    pais: str = ""
    ajustado: bool = True       # ¿incluye dividendos y splits?
    rentabilidades: pd.Series = field(init=False, repr=False)
    media_anual: float = field(init=False)
    volatilidad_anual: float = field(init=False)

    def __post_init__(self) -> None:
        if self.tipo not in TIPOS_ACTIVO:
            raise ValueError(f"{self.symbol}: tipo '{self.tipo}' no válido ({', '.join(TIPOS_ACTIVO)}).")
        self.divisa = self.divisa.upper()
        super().__post_init__()

    def _calcular_estadisticos(self) -> None:
        if (self.datos <= 0).any():
            raise ValueError(f"{self.symbol}: hay precios negativos o cero.")
        self.rentabilidades = self.datos.pct_change().dropna()
        self.media = float(self.rentabilidades.mean())
        self.desviacion = float(self.rentabilidades.std())
        self.media_anual = self.media * SESIONES
        self.volatilidad_anual = self.desviacion * np.sqrt(SESIONES)

    def convertir(self, tipo_cambio: Serie, divisa: str = "EUR") -> PriceSeries:
        """La misma serie en otra divisa. `tipo_cambio`: unidades de self.divisa por 1 `divisa`."""
        cambio = tipo_cambio.datos.reindex(self.datos.index, method="ffill")
        return PriceSeries(
            symbol=self.symbol, source=f"{self.source} + {tipo_cambio.source} ({tipo_cambio.symbol})",
            datos=self.datos / cambio, nombre=self.nombre, divisa=divisa, tipo=self.tipo,
            sector=self.sector, pais=self.pais, ajustado=self.ajustado)


@dataclass(eq=False)
class MacroSeries(Serie):
    """Indicador económico. `unidad` dice cómo leer los valores ("%", "índice", "USD"...)."""
    unidad: str = ""
    frecuencia: str = "diaria"

    def en_tanto_por_uno(self) -> pd.Series:
        return self.datos / 100 if self.unidad == "%" else self.datos
