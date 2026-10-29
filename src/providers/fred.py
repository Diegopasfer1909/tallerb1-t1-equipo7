"""Observaciones económicas de FRED con sus unidades y frecuencia."""

import pandas as pd

from ..models.economic_indicator import EconomicIndicator
from .base import ApiClient, ProviderError, date_range


class FredAPI:
    def __init__(self, api_key=None, cache_dir=None, cache_ttl: float = 86400, session=None):
        self.client = ApiClient(
            api_key,
            "FRED_API_KEY",
            cache_dir=cache_dir,
            cache_ttl=cache_ttl,
            session=session,
        )

    def _query(self, endpoint: str, series_id: str, options: dict | None = None) -> dict:
        params = {
            "series_id": series_id,
            "api_key": self.client.api_key,
            "file_type": "json",
        }
        if options is not None:
            params.update(options)
        url = f"https://api.stlouisfed.org/fred/{endpoint}"
        return self.client.get_json(url, params)

    def get_series(self, series_id: str, start: str, end: str) -> EconomicIndicator:
        """Descarga los metadatos y las observaciones y crea el indicador validado."""
        first, last = date_range(start, end)
        info = self._get_metadata(series_id)
        records = self._get_observations(series_id, first, last)
        values = self._parse_observations(records, series_id)
        values = values.loc[(values.index >= first) & (values.index < last)]

        try:
            units = info["units"]
            frequency = info["frequency"]
        except KeyError:
            raise ProviderError(
                "Las observaciones o los metadatos de FRED tienen un formato incorrecto."
            ) from None

        info.update({"requested_start": start, "requested_end_exclusive": end})
        return EconomicIndicator(series_id, "fred", values, units, frequency, info=info)

    def _get_metadata(self, series_id: str) -> dict:
        """Obtiene el nombre, las unidades, la frecuencia y los demás metadatos."""
        payload = self._query("series", series_id)
        metadata = payload.get("seriess")
        if not isinstance(metadata, list) or not metadata:
            raise ProviderError("FRED no ha devuelto los metadatos de la serie.")
        return dict(metadata[0])

    def _get_observations(
        self, series_id: str, first: pd.Timestamp, last: pd.Timestamp
    ) -> list[dict]:
        """Descarga todas las páginas de observaciones del intervalo solicitado."""
        records = []
        offset = 0
        while True:
            options = {
                "observation_start": first.date().isoformat(),
                # FRED incluye la fecha final; nuestra interfaz la excluye.
                "observation_end": (last - pd.Timedelta(days=1)).date().isoformat(),
                "sort_order": "asc",
                "limit": 100000,
                "offset": offset,
            }
            payload = self._query("series/observations", series_id, options)
            batch = payload.get("observations")
            if not isinstance(batch, list) or not batch:
                raise ProviderError(
                    "FRED no ha devuelto observaciones o ha enviado una página incompleta."
                )
            records.extend(batch)
            offset += len(batch)
            if offset >= int(payload.get("count", offset)):
                return records

    def _parse_observations(self, records: list[dict], series_id: str) -> pd.Series:
        """Convierte los registros en una Series conservando los datos ausentes."""
        dates = []
        values = []
        try:
            for record in records:
                dates.append(pd.Timestamp(record["date"]))
                if record["value"] == ".":
                    values.append(float("nan"))
                else:
                    values.append(float(record["value"]))
            return pd.Series(values, index=pd.DatetimeIndex(dates), name=series_id)
        except (KeyError, ValueError, TypeError):
            raise ProviderError(
                "Las observaciones o los metadatos de FRED tienen un formato incorrecto."
            ) from None
