"""Series del Banco Central Europeo, sin clave: API de datos en formato CSV.

Los identificadores tienen la forma CONJUNTO/CLAVE. AAA_3M_YIELD es el tipo al contado a tres
meses de la curva de deuda pública AAA de la zona euro, estimada a partir de los bonos que
cotizan; no es el precio de una letra concreta.
"""

import io
import math
from pathlib import Path

import pandas as pd
from curl_cffi import requests as curl_requests

from ..models.economic_indicator import EconomicIndicator
from ..validation import date_range
from .base import ProviderError, cache_path, prune_cache, read_cache, write_cache

URL = "https://data-api.ecb.europa.eu/service/data"
AAA_3M_YIELD = "YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_3M"
FORMAT_ERROR = "Las observaciones del BCE tienen un formato incorrecto."
# El CSV no publica estos metadatos: unidades y frecuencia de las series que usa el programa.
SERIES = {AAA_3M_YIELD: ("Percent", "Daily")}


def is_ecb_series(series_id: str) -> bool:
    """Solo los identificadores del BCE incluyen una barra; los de FRED, no."""
    return "/" in series_id


class EcbAPI:
    """Con cache_dir, cada serie se guarda completa; con cache_ttl igual a cero no hay caché."""

    def __init__(self, cache_dir: Path | None = None, cache_ttl: float = 86400, session=None):
        self.cache_dir = Path(cache_dir) if cache_dir is not None and cache_ttl > 0 else None
        self.cache_ttl = cache_ttl
        self.session = session if session is not None else curl_requests
        prune_cache(self.cache_dir, cache_ttl)

    def get_series(self, series_id: str, start: str, end: str) -> EconomicIndicator:
        """Descarga las observaciones y crea el indicador validado; la fecha final se excluye."""
        first, last = date_range(start, end)
        values = self._observations(series_id)
        values = values.loc[(values.index >= first) & (values.index < last)]
        units, frequency = SERIES.get(series_id, ("", ""))
        return EconomicIndicator(series_id, "ecb", values, units, frequency)

    def _observations(self, series_id: str) -> pd.Series:
        cache = cache_path(self.cache_dir, ["ecb", series_id])
        cached = read_cache(cache, self.cache_ttl)
        if cached is not None:
            return _series(cached["dates"], cached["values"], series_id)
        records = self._download(series_id)
        write_cache(cache, records)
        return _series(records["dates"], records["values"], series_id)

    def _download(self, series_id: str) -> dict:
        try:
            response = self.session.get(
                f"{URL}/{series_id}", params={"format": "csvdata"}, impersonate="chrome", timeout=30
            )
            response.raise_for_status()
            table = pd.read_csv(io.StringIO(response.text))
        except Exception:
            # curl_cffi no comparte excepciones con requests; se traducen al error común.
            raise ProviderError(f"El BCE no ha podido descargar la serie {series_id}.") from None
        if table.empty or not {"TIME_PERIOD", "OBS_VALUE"} <= set(table.columns):
            raise ProviderError(FORMAT_ERROR)
        values = pd.to_numeric(table["OBS_VALUE"], errors="coerce")
        return {
            "dates": table["TIME_PERIOD"].astype(str).tolist(),
            # Un dato ausente se guarda como null: JSON no admite NaN.
            "values": [None if math.isnan(value) else float(value) for value in values],
        }


def _series(dates: list[str], values: list, series_id: str) -> pd.Series:
    """Convierte los registros en una Series conservando los datos ausentes."""
    try:
        index = pd.DatetimeIndex(pd.to_datetime(dates))
    except (ValueError, TypeError):
        raise ProviderError(FORMAT_ERROR) from None
    return pd.Series(values, index=index, name=series_id, dtype=float).sort_index()
