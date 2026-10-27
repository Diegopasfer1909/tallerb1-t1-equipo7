"""Yahoo Finance (yfinance): acciones, índices, ETF, materias primas y divisas, sin clave."""
import warnings

import pandas as pd

from .base import FuentePrecios

TIPOS = {"EQUITY": "accion", "INDEX": "indice", "ETF": "etf", "MUTUALFUND": "etf",
         "FUTURE": "materia_prima", "CURRENCY": "divisa"}


class YahooFinance(FuentePrecios):
    nombre = "yfinance"
    ajustado = True

    def __init__(self, con_metadatos: bool = True):
        self.con_metadatos = con_metadatos

    def _cierres(self, symbol, inicio, fin) -> pd.Series:
        import yfinance as yf

        # yfinance usa argumentos que pandas 3 marca como obsoletos y llena la salida de avisos.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            historia = yf.Ticker(symbol).history(start=inicio, end=fin, period=None if inicio else "max",
                                                 auto_adjust=True)
        return historia["Close"] if not historia.empty else pd.Series(dtype=float)

    def _metadatos(self, symbol) -> dict:
        if not self.con_metadatos:
            return {}
        import yfinance as yf

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                info = yf.Ticker(symbol).info
        except Exception:
            return {}
        return {
            "nombre": info.get("shortName") or info.get("longName"),
            "divisa": info.get("currency"),
            "tipo": TIPOS.get(info.get("quoteType"), "otro"),
            "sector": info.get("sector"),
            "pais": info.get("country"),
        }
