"""Precios diarios de Alpha Vantage y ficha opcional de la empresa."""

import pandas as pd

from ..errors import PortfolioError
from ..models.asset_profile import AssetProfile
from ..models.price_history import PriceHistory
from ..validation import date_range
from .base import (
    ApiClient,
    DataCoverageError,
    ProviderError,
    build_profile,
    drop_missing_closes,
)

URL = "https://www.alphavantage.co/query"
API_KEY_ENV = "ALPHA_VANTAGE_API_KEY"
# Campos con los que Alpha Vantage comunica errores de cuota o permisos en un HTTP 200.
ERROR_KEYS = ("Error Message", "Note", "Information")
FIELDS = {
    "currency": ("Currency",),
    "name": ("Name",),
    "asset_type": ("AssetType",),
    "sector": ("Sector",),
    "country": ("Country",),
    "beta": ("Beta",),
    "market_cap": ("MarketCapitalization",),
    "pe_ratio": ("PERatio",),
}
ASSET_TYPES = {"Common Stock": "stock", "ETF": "etf", "Mutual Fund": "fund"}
COLUMNS = {
    "1. open": "Open",
    "2. high": "High",
    "3. low": "Low",
    "4. close": "Close",
    "5. volume": "Volume",
}
PROFILE_ISSUE = (
    "No se ha podido consultar la información de la empresa en Alpha Vantage. Es posible que "
    "se haya alcanzado el límite de consultas o que el plan no permita acceder a ella."
)


class AlphaVantageAPI:
    """Adaptador de Alpha Vantage; sus opciones propias se fijan al crearlo.

    outputsize="compact" devuelve las últimas 100 sesiones; "full" requiere un plan que lo
    permita. allow_partial acepta historiales que empiezan después de la fecha pedida.
    include_info consulta además la ficha OVERVIEW, que consume otra petición.
    """

    def __init__(
        self,
        api_key=None,
        cache_dir=None,
        cache_ttl=86400,
        session=None,
        *,
        outputsize: str = "compact",
        allow_partial: bool = False,
        include_info: bool = False,
    ):
        if outputsize not in ("compact", "full"):
            raise PortfolioError("outputsize debe ser 'compact' o 'full'.")
        self.outputsize = outputsize
        self.allow_partial = allow_partial
        self.include_info = include_info
        self.client = ApiClient(
            api_key,
            API_KEY_ENV,
            error_keys=ERROR_KEYS,
            cache_dir=cache_dir,
            cache_ttl=cache_ttl,
            session=session,
            min_interval=1.1,
        )

    def get_info(self, symbol: str) -> dict:
        """Consulta opcional de la ficha de la empresa; consume una petición adicional."""
        params = {"function": "OVERVIEW", "symbol": symbol, "apikey": self.client.api_key}
        info = self.client.get_json(URL, params)
        if "Symbol" not in info:
            raise ProviderError("Alpha Vantage no ha devuelto la ficha de la empresa.")
        return info

    def get_prices(
        self, symbol: str, start: str, end: str, *, adjusted: bool = False
    ) -> PriceHistory:
        """Descarga, normaliza y selecciona los precios antes de crear el modelo."""
        first, last = date_range(start, end)
        if adjusted:
            raise PortfolioError(
                "Este adaptador gratuito de Alpha Vantage solo admite precios sin ajustar."
            )
        params = {
            "function": "TIME_SERIES_DAILY",
            "symbol": symbol,
            "outputsize": self.outputsize,
            "apikey": self.client.api_key,
        }
        prices = self._parse_prices(self.client.get_json(URL, params))
        partial = self._is_partial(prices, first)
        prices = prices.loc[(prices.index >= first) & (prices.index < last)]
        prices, dropped = drop_missing_closes(prices)
        if prices.empty:
            raise DataCoverageError(
                f"No hay precios de Alpha Vantage para {symbol} dentro de las fechas solicitadas."
            )
        return PriceHistory(
            symbol,
            "alpha_vantage",
            prices,
            profile=self._profile(symbol),
            price_basis="unadjusted",
            partial_history=partial,
            dropped_rows=dropped,
        )

    def _profile(self, symbol: str) -> AssetProfile:
        """La ficha es opcional: si falla, se conservan los precios ya descargados."""
        if not self.include_info:
            return build_profile({}, FIELDS, ASSET_TYPES)
        try:
            return build_profile(self.get_info(symbol), FIELDS, ASSET_TYPES)
        except ProviderError:
            return build_profile({}, FIELDS, ASSET_TYPES, issue=PROFILE_ISSUE)

    def _parse_prices(self, payload: dict) -> pd.DataFrame:
        """Normaliza las columnas, las fechas y los números de Alpha Vantage."""
        rows = payload.get("Time Series (Daily)")
        if not isinstance(rows, dict) or not rows:
            raise ProviderError("Alpha Vantage no ha devuelto una serie de precios diarios.")
        try:
            prices = pd.DataFrame.from_dict(rows, orient="index").rename(columns=COLUMNS)
            prices.index = pd.to_datetime(prices.index)
            for column in prices.columns:
                prices[column] = pd.to_numeric(prices[column], errors="raise")
        except (ValueError, TypeError):
            raise ProviderError(
                "Los registros de precios de Alpha Vantage tienen un formato incorrecto."
            ) from None
        if prices.index.hasnans:
            raise ProviderError("Alpha Vantage ha devuelto fechas no válidas.")
        return prices.sort_index()

    def _is_partial(self, prices: pd.DataFrame, first: pd.Timestamp) -> bool:
        """Indica si el historial empieza tarde; por defecto, rechaza los incompletos."""
        earliest = prices.index[0]
        partial = first < earliest
        if partial and not self.allow_partial:
            raise DataCoverageError(
                f"El historial disponible de Alpha Vantage comienza el {earliest.date()}; "
                "el inicio solicitado es anterior. El modo compact proporciona las últimas 100 "
                "observaciones. Elige una fecha de inicio dentro del historial disponible. Desde "
                "Python también puedes crear AlphaVantageAPI(outputsize='full') si tu plan lo "
                "permite, o aceptar un historial parcial con AlphaVantageAPI(allow_partial=True). "
                "No se han recortado las fechas sin tu autorización."
            )
        return partial
