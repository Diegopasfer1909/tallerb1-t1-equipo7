"""Observaciones económicas de FRED con sus unidades y frecuencia.

Se usa la última versión de cada serie, con cada dato en la fecha a la que corresponde. Las
referencias solo intervienen en medidas calculadas al final del periodo (rentabilidad real,
Sharpe, Sortino), que deben reflejar lo que ocurrió: para eso la cifra revisada es la mejor
estimación, y ninguna decisión depende de ellas, así que no hay sesgo de anticipación.
"""

import math

import pandas as pd

from ..models.economic_indicator import EconomicIndicator
from ..validation import date_range
from .base import ApiClient, ProviderError

URL = "https://api.stlouisfed.org/fred"
API_KEY_ENV = "FRED_API_KEY"
FORMAT_ERROR = "Las observaciones o los metadatos de FRED tienen un formato incorrecto."


class FredAPI:
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

    def get_series(self, series_id: str, start: str, end: str) -> EconomicIndicator:
        """Descarga los metadatos y las observaciones y crea el indicador validado."""
        first, last = date_range(start, end)
        info = self._get_metadata(series_id)
        records = self._get_observations(series_id, first, last)
        values = self._parse_observations(records, series_id)
        values = values.loc[(values.index >= first) & (values.index < last)]
        return EconomicIndicator(
            series_id, "fred", values, info["units"], info["frequency"], info=info
        )

    def _get_metadata(self, series_id: str) -> dict:
        """Obtiene el nombre, las unidades, la frecuencia y los demás metadatos."""
        payload = self._query("series", series_id)
        metadata = payload.get("seriess")
        if not isinstance(metadata, list) or not metadata:
            raise ProviderError("FRED no ha devuelto los metadatos de la serie.")
        info = dict(metadata[0])
        if "units" not in info or "frequency" not in info:
            raise ProviderError(FORMAT_ERROR)
        return info

    def _get_observations(
        self, series_id: str, first: pd.Timestamp, last: pd.Timestamp
    ) -> list[dict]:
        """Descarga todas las páginas de observaciones del intervalo solicitado."""
        # La API incluye la fecha final; nuestra interfaz la excluye.
        options = {
            "observation_start": first.date().isoformat(),
            "observation_end": (last - pd.Timedelta(days=1)).date().isoformat(),
            "sort_order": "asc",
            "limit": 100000,
        }
        records = []
        while True:
            payload = self._query(
                "series/observations", series_id, {**options, "offset": len(records)}
            )
            batch = payload.get("observations")
            if not isinstance(batch, list) or not batch:
                raise ProviderError(
                    "FRED no ha devuelto observaciones o ha enviado una página incompleta."
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


def _value(record: dict) -> float:
    """El punto indica un dato ausente."""
    return math.nan if record["value"] == "." else float(record["value"])
