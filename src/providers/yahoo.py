"""Precios históricos y ficha del activo en Yahoo Finance."""

import pandas as pd
import yfinance as yf

from ..models.asset_profile import AssetProfile
from ..models.price_history import PriceHistory
from ..validation import date_range
from .base import DataCoverageError, ProviderError, build_profile, drop_missing_closes

FIELDS = {
    "currency": ("currency",),
    "name": ("longName", "shortName"),
    "asset_type": ("quoteType",),
    "sector": ("sector",),
    "country": ("country",),
    "beta": ("beta", "beta3Year"),
    "market_cap": ("marketCap",),
    "pe_ratio": ("trailingPE",),
}
ASSET_TYPES = {"EQUITY": "stock", "INDEX": "index", "ETF": "etf", "MUTUALFUND": "fund"}
PROFILE_ISSUE = (
    "No se ha podido consultar la ficha del activo en Yahoo Finance. Es posible que se haya "
    "alcanzado el límite de consultas o que el símbolo no tenga ficha. Faltan la divisa y los "
    "datos de la empresa; indica la divisa expresamente."
)


class YahooFinanceAPI:
    def get_info(self, symbol: str) -> dict:
        """Consulta la ficha del activo; yfinance la obtiene con una petición adicional."""
        try:
            info = dict(yf.Ticker(symbol).get_info())
        except Exception:
            # yfinance no documenta sus excepciones; se traducen al error común.
            raise ProviderError("Yahoo Finance no ha devuelto la ficha del activo.") from None
        # Para símbolos sin ficha, yfinance puede devolver un diccionario casi vacío.
        if not info.get("quoteType"):
            raise ProviderError("Yahoo Finance no ha devuelto la ficha del activo.")
        return info

    def get_prices(
        self, symbol: str, start: str, end: str, *, adjusted: bool = False
    ) -> PriceHistory:
        """Descarga los datos de Yahoo, normaliza las fechas y crea el historial."""
        first, last = date_range(start, end)
        try:
            history = yf.Ticker(symbol).history(start=start, end=end, auto_adjust=adjusted)
        except Exception:
            # yfinance no documenta sus excepciones; se traducen al error común.
            raise ProviderError(f"Yahoo no ha podido descargar los precios de {symbol}.") from None
        if history.empty:
            raise ProviderError(f"Yahoo no ha devuelto precios para {symbol}.")
        if not isinstance(history.index, pd.DatetimeIndex):
            raise ProviderError("Yahoo ha devuelto un índice de fechas no válido.")
        # Las fechas diarias corresponden al calendario de la bolsa, no a instantes UTC.
        history.index = history.index.tz_localize(None)
        history = history.loc[(history.index >= first) & (history.index < last)]
        prices, dropped = drop_missing_closes(history)
        if prices.empty:
            raise DataCoverageError(
                f"Yahoo no ha devuelto precios de {symbol} dentro de las fechas solicitadas."
            )
        return PriceHistory(
            symbol,
            "yahoo",
            prices,
            profile=self._profile(symbol),
            # Yahoo ajusta Close por desdoblamientos incluso con auto_adjust=False.
            price_basis="adjusted" if adjusted else "split_adjusted",
            dropped_rows=dropped,
        )

    def _profile(self, symbol: str) -> AssetProfile:
        """La ficha es complementaria: si falla, se conservan los precios ya descargados."""
        try:
            return build_profile(self.get_info(symbol), FIELDS, ASSET_TYPES)
        except ProviderError:
            return build_profile({}, FIELDS, ASSET_TYPES, issue=PROFILE_ISSUE)
