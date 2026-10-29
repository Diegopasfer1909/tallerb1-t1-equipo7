"""Precios diarios de Alpha Vantage y ficha opcional de la empresa."""

import pandas as pd

from ..models.price_history import PriceHistory
from .base import ApiClient, DataCoverageError, ProviderError, date_range


class AlphaVantageAPI:
    def __init__(self, api_key=None, cache_dir=None, cache_ttl=86400, session=None):
        self.client = ApiClient(
            api_key,
            "ALPHA_VANTAGE_API_KEY",
            cache_dir=cache_dir,
            cache_ttl=cache_ttl,
            session=session,
            min_interval=1.1,
        )

    def get_info(self, symbol: str) -> dict:
        """Consulta opcional de la ficha de la empresa; consume una petición adicional."""
        params = {
            "function": "OVERVIEW",
            "symbol": symbol,
            "apikey": self.client.api_key,
        }
        info = self.client.get_json("https://www.alphavantage.co/query", params)
        if "Symbol" not in info:
            raise ProviderError("Alpha Vantage no ha devuelto la ficha de la empresa.")
        return info

    def get_prices(
        self,
        symbol: str,
        start: str,
        end: str,
        *,
        adjusted: bool = False,
        outputsize: str = "compact",
        allow_partial: bool = False,
        include_info: bool = False,
    ) -> PriceHistory:
        """Descarga, normaliza y selecciona los precios antes de crear el modelo."""
        first, last = date_range(start, end)
        if adjusted:
            raise ValueError(
                "Este adaptador gratuito de Alpha Vantage solo admite precios sin ajustar."
            )
        if outputsize not in ("compact", "full"):
            raise ValueError("outputsize debe ser 'compact' o 'full'.")
        params = {
            "function": "TIME_SERIES_DAILY",
            "symbol": symbol,
            "outputsize": outputsize,
            "apikey": self.client.api_key,
        }
        payload = self.client.get_json("https://www.alphavantage.co/query", params)
        prices = self._parse_prices(payload)
        coverage = self._check_coverage(prices, first, allow_partial)
        prices = prices.loc[(prices.index >= first) & (prices.index < last)]
        if prices.empty:
            raise DataCoverageError(
                "No hay precios de Alpha Vantage dentro de las fechas solicitadas."
            )

        info = {}
        if include_info:
            try:
                info = self.get_info(symbol)
            except ProviderError:
                info["metadata_issue"] = (
                    "No se ha podido consultar la información de la empresa en Alpha Vantage. Es posible que se haya alcanzado el límite de consultas o que el plan no permita acceder a ella."
                )
        info["provider_metadata"] = payload.get("Meta Data", {})
        info["price_adjustment"] = "unadjusted"
        info["requested_start"] = start
        info["requested_end_exclusive"] = end
        info.update(coverage)
        return PriceHistory(symbol, "alpha_vantage", prices, info=info)

    def _parse_prices(self, payload: dict) -> pd.DataFrame:
        """Normaliza las columnas, las fechas y los números de Alpha Vantage."""
        rows = payload.get("Time Series (Daily)")
        if not isinstance(rows, dict) or not rows:
            raise ProviderError("Alpha Vantage no ha devuelto una serie de precios diarios.")
        try:
            prices = pd.DataFrame.from_dict(rows, orient="index").rename(
                columns={
                    "1. open": "Open",
                    "2. high": "High",
                    "3. low": "Low",
                    "4. close": "Close",
                    "5. volume": "Volume",
                }
            )
            prices.index = pd.to_datetime(prices.index)
            for column in prices.columns:
                prices[column] = pd.to_numeric(prices[column], errors="raise")
            prices = prices.sort_index()
        except (ValueError, TypeError):
            raise ProviderError(
                "Los registros de precios de Alpha Vantage tienen un formato incorrecto."
            ) from None
        return prices

    def _check_coverage(
        self,
        prices: pd.DataFrame,
        first: pd.Timestamp,
        allow_partial: bool,
    ) -> dict:
        """Registra la cobertura de fechas y rechaza por defecto los historiales incompletos."""
        dates = pd.DatetimeIndex(prices.index)
        if dates.hasnans:
            raise ProviderError("Alpha Vantage ha devuelto fechas no válidas.")
        earliest, latest = dates[0], dates[-1]
        if not isinstance(earliest, pd.Timestamp) or not isinstance(latest, pd.Timestamp):
            raise ProviderError("Los límites de fechas devueltos por Alpha Vantage no son válidos.")
        partial = first < earliest
        if partial and not allow_partial:
            raise DataCoverageError(
                f"El historial disponible de Alpha Vantage comienza el {earliest.date()}; "
                "el inicio solicitado es anterior. El modo compact proporciona las últimas 100 observaciones. "
                "Elige una fecha de inicio dentro del historial disponible. Desde Python también "
                "puedes solicitar outputsize='full' si tu plan lo permite, o aceptar un historial "
                "parcial con allow_partial=True. No se han recortado las fechas sin tu autorización."
            )
        available_end = latest.date().isoformat()
        coverage = {
            "partial_history": partial,
            "available_start": earliest.date().isoformat(),
            "available_end": available_end,
        }
        return coverage
