"""Observaciones económicas de ALFRED, el archivo histórico de FRED.

ALFRED conserva cada versión publicada de una serie. Así se reconstruye lo que se sabía en
cada fecha y se evita el sesgo de anticipación (look-ahead bias): una cifra revisada después
o publicada semanas más tarde no se utiliza antes de que existiera.
"""

import math

import pandas as pd

from ..models.economic_indicator import EconomicIndicator
from ..validation import date_range
from .base import ApiClient, ProviderError

URL = "https://api.stlouisfed.org/fred"
# ALFRED forma parte de la API de FRED y utiliza las mismas claves.
API_KEY_ENV = "FRED_API_KEY"
# Las series mensuales se publican semanas después del periodo: se piden observaciones
# anteriores para conocer el último dato publicado al empezar el intervalo.
PUBLICATION_LAG = pd.Timedelta(days=120)
FORMAT_ERROR = "Las observaciones o los metadatos de ALFRED tienen un formato incorrecto."


class AlfredAPI:
    def __init__(self, api_key=None, cache_dir=None, cache_ttl: float = 86400, session=None):
        self.client = ApiClient(
            api_key,
            API_KEY_ENV,
            error_keys=("error_message",),
            cache_dir=cache_dir,
            cache_ttl=cache_ttl,
            session=session,
        )

    def _query(self, endpoint: str, series_id: str, options: dict | None = None) -> dict:
        params = {"series_id": series_id, "api_key": self.client.api_key, "file_type": "json"}
        if options is not None:
            params.update(options)
        return self.client.get_json(f"{URL}/{endpoint}", params)

    def get_series(
        self, series_id: str, start: str, end: str, *, point_in_time: bool = True
    ) -> EconomicIndicator:
        """Descarga la serie y crea el indicador validado.

        Con point_in_time, cada fecha del índice es una publicación o revisión, y su valor es
        el de la observación más reciente que se conocía entonces. Sin él, se obtiene la
        última versión por fecha de observación, adecuada para datos que no se revisan y se
        conocían en su fecha, como los tipos de cambio.
        """
        first, last = date_range(start, end)
        info = self._get_metadata(series_id)
        if point_in_time:
            records = self._get_observations(
                series_id, first - PUBLICATION_LAG, last, realtime=(first, last)
            )
            values = self._known_values(records, series_id, first)
        else:
            records = self._get_observations(series_id, first, last)
            values = self._parse_observations(records, series_id)
        values = values.loc[(values.index >= first) & (values.index < last)]
        return EconomicIndicator(
            series_id,
            "alfred",
            values,
            info["units"],
            info["frequency"],
            info=info,
            point_in_time=point_in_time,
        )

    def _get_metadata(self, series_id: str) -> dict:
        """Obtiene el nombre, las unidades, la frecuencia y los demás metadatos."""
        payload = self._query("series", series_id)
        metadata = payload.get("seriess")
        if not isinstance(metadata, list) or not metadata:
            raise ProviderError("ALFRED no ha devuelto los metadatos de la serie.")
        info = dict(metadata[0])
        if "units" not in info or "frequency" not in info:
            raise ProviderError(FORMAT_ERROR)
        return info

    def _get_observations(
        self,
        series_id: str,
        first: pd.Timestamp,
        last: pd.Timestamp,
        realtime: tuple[pd.Timestamp, pd.Timestamp] | None = None,
    ) -> list[dict]:
        """Descarga todas las páginas; realtime pide todas las versiones de ese periodo."""
        # La API incluye las fechas finales; nuestra interfaz las excluye.
        options = {
            "observation_start": first.date().isoformat(),
            "observation_end": (last - pd.Timedelta(days=1)).date().isoformat(),
            "sort_order": "asc",
            "limit": 100000,
        }
        if realtime is not None:
            options["realtime_start"] = realtime[0].date().isoformat()
            options["realtime_end"] = (realtime[1] - pd.Timedelta(days=1)).date().isoformat()
        records = []
        while True:
            payload = self._query(
                "series/observations", series_id, {**options, "offset": len(records)}
            )
            batch = payload.get("observations")
            if not isinstance(batch, list) or not batch:
                raise ProviderError(
                    "ALFRED no ha devuelto observaciones o ha enviado una página incompleta."
                )
            records.extend(batch)
            if len(records) >= int(payload.get("count", len(records))):
                return records

    def _parse_observations(self, records: list[dict], series_id: str) -> pd.Series:
        """Convierte los registros en una Series conservando los datos ausentes."""
        dates = []
        values = []
        try:
            for record in records:
                dates.append(pd.Timestamp(record["date"]))
                values.append(_value(record))
        except (KeyError, ValueError, TypeError):
            raise ProviderError(FORMAT_ERROR) from None
        return pd.Series(values, index=pd.DatetimeIndex(dates), name=series_id)

    def _known_values(self, records: list[dict], series_id: str, since: pd.Timestamp) -> pd.Series:
        """Último dato conocido en cada publicación o revisión, sin información posterior.

        Cada registro dice qué valor tuvo una observación entre realtime_start y
        realtime_end. Las fechas ISO se comparan como texto, que conserva el orden, y así
        se evita convertir el final abierto 9999-12-31.
        """
        start = since.date().isoformat()
        try:
            versions = [
                (
                    record["date"],
                    _value(record),
                    max(record["realtime_start"], start),
                    record["realtime_end"],
                )
                for record in records
            ]
        except (KeyError, ValueError, TypeError):
            raise ProviderError(FORMAT_ERROR) from None
        known = {}
        for moment in sorted({begin for _, _, begin, _ in versions}):
            visible = [
                (date, value)
                for date, value, begin, end in versions
                if begin <= moment <= end and not math.isnan(value)
            ]
            if visible:
                known[pd.Timestamp(moment)] = max(visible)[1]
        return pd.Series(
            list(known.values()),
            index=pd.DatetimeIndex(list(known)),
            name=series_id,
            dtype=float,
        )


def _value(record: dict) -> float:
    """El punto indica un dato ausente."""
    return math.nan if record["value"] == "." else float(record["value"])
