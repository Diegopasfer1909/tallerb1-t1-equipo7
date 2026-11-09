"""Series del Banco Central Europeo, sin clave: API de datos en formato CSV.

Los identificadores tienen la forma CONJUNTO/CLAVE. AAA_3M_YIELD (definido en constants, porque
el núcleo lo elige como referencia en EUR) es el tipo al contado a tres meses de la curva de
deuda pública AAA de la zona euro, estimada a partir de los bonos que cotizan; no es el precio
de una letra concreta.
"""

import io
import math
import time
from pathlib import Path

import pandas as pd
from curl_cffi import requests as curl_requests

from ..constants import AAA_3M_YIELD
from ..errors import ProviderError
from ..models.economic_indicator import EconomicIndicator
from ..validation import date_range
from .base import cache_path, prune_cache, read_cache, write_cache

URL = "https://data-api.ecb.europa.eu/service/data"
FORMAT_ERROR = "Las observaciones del BCE tienen un formato incorrecto."
# El CSV no publica estos metadatos: unidades y frecuencia de las series que usa el programa.
SERIES = {AAA_3M_YIELD: ("Percent", "Daily")}
# La API del BCE falla a veces de forma pasajera (sin conexión, tiempo agotado, 429 o 5xx).
# Se reintenta dos veces, esperando 1 s y luego 2 s; un 4xx, como una serie inexistente, no.
RETRIES = 2
RETRY_WAIT = 1.0
TRANSIENT_STATUS = (429, 500, 502, 503, 504)


class EcbAPI:
    """Con cache_dir, cada serie se guarda completa; con cache_ttl igual a cero no hay caché.

    retries son los reintentos ante fallos pasajeros y retry_wait, la primera espera en segundos,
    que se duplica en cada reintento.
    """

    def __init__(
        self,
        cache_dir: Path | None = None,
        cache_ttl: float = 86400,
        session=None,
        retries: int = RETRIES,
        retry_wait: float = RETRY_WAIT,
    ):
        self.cache_dir = Path(cache_dir) if cache_dir is not None and cache_ttl > 0 else None
        self.cache_ttl = cache_ttl
        self.session = session if session is not None else curl_requests
        self.retries = retries
        self.retry_wait = retry_wait
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

    def _get(self, series_id: str):
        """Respuesta de la API; reintenta los fallos pasajeros y devuelve la última respuesta.

        Si todos los intentos fallan sin respuesta (red o tiempo agotado), lanza ProviderError.
        """
        response = None
        for attempt in range(self.retries + 1):
            if attempt:
                time.sleep(self.retry_wait * 2 ** (attempt - 1))
            try:
                response = self.session.get(
                    f"{URL}/{series_id}",
                    params={"format": "csvdata"},
                    impersonate="chrome",
                    timeout=30,
                )
            except Exception:
                # curl_cffi no comparte excepciones con requests: cualquier fallo de envío
                # (sin conexión, tiempo agotado) se trata como pasajero.
                response = None
                continue
            if response.status_code not in TRANSIENT_STATUS:
                return response
        if response is None:
            raise ProviderError(f"El BCE no ha podido descargar la serie {series_id}.")
        return response

    def _download(self, series_id: str) -> dict:
        response = self._get(series_id)
        try:
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
