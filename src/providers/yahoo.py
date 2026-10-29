"""Precios históricos y ficha del activo en Yahoo Finance."""

import pandas as pd
import yfinance as yf

from ..models.price_history import PriceHistory
from .base import ProviderError, date_range


class YahooFinanceAPI:
    def get_prices(
        self, symbol: str, start: str, end: str, *, adjusted: bool = False
    ) -> PriceHistory:
        """Descarga los datos de Yahoo, normaliza las fechas y crea el historial."""
        first, last = date_range(start, end)
        ticker = yf.Ticker(symbol)
        history = ticker.history(start=start, end=end, auto_adjust=adjusted)
        if history.empty:
            raise ProviderError(f"Yahoo no ha devuelto precios para {symbol}.")
        if not isinstance(history.index, pd.DatetimeIndex):
            raise ProviderError("Yahoo ha devuelto un índice de fechas no válido.")
        # Las fechas diarias corresponden al calendario de la bolsa, no a instantes UTC.
        history.index = history.index.tz_localize(None)
        history = history.loc[(history.index >= first) & (history.index < last)]
        info = dict(ticker.get_info())
        # Yahoo ajusta Close por desdoblamientos incluso con auto_adjust=False.
        info["price_adjustment"] = "adjusted" if adjusted else "split_adjusted"
        info["auto_adjust"] = adjusted
        return PriceHistory(symbol, "yahoo", history, info=info)
