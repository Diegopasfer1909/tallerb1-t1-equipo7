"""FRED (Reserva Federal de St. Louis): series macroeconómicas sin clave, como en el
notebook de clase (fredgraph.csv pedido con curl_cffi)."""
import io

import pandas as pd

from ..modelos.series import MacroSeries
from .base import ErrorDescarga, http_get

URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"

# Series que usa el report: identificador → (nombre, unidad, frecuencia)
SERIES = {
    "IRLTLT01DEM156N": ("Bund 10 años", "%", "mensual"),
    "CP0000EZ19M086NEST": ("HICP zona euro", "índice", "mensual"),
    "DEXUSEU": ("Dólares por euro", "USD por EUR", "diaria"),
    "VIXCLS": ("VIX", "puntos", "diaria"),
    "DCOILBRENTEU": ("Brent", "USD por barril", "diaria"),
}


class Fred:
    nombre = "FRED"

    def descargar(self, symbol: str, inicio: str | None = None, fin: str | None = None) -> MacroSeries:
        try:
            tabla = pd.read_csv(io.StringIO(http_get(URL, {"id": symbol}).text))
        except Exception as error:
            raise ErrorDescarga(f"{symbol}: {type(error).__name__}: {error}") from error
        if tabla.shape[1] < 2:
            raise ErrorDescarga(f"{symbol}: FRED no devolvió datos.")
        datos = tabla.set_index(pd.to_datetime(tabla.iloc[:, 0])).iloc[:, 1]
        # Los datos mensuales llevan fecha del día 1: se pide desde el inicio de ese mes.
        desde = pd.Timestamp(inicio).to_period("M").to_timestamp() if inicio else None
        nombre, unidad, frecuencia = SERIES.get(symbol, (symbol, "", ""))
        return MacroSeries(symbol=symbol, source=self.nombre, datos=datos.loc[desde:fin],
                           nombre=nombre, unidad=unidad, frecuencia=frecuencia)
