"""Capa de ingesta: fuentes de datos que devuelven siempre PriceSeries o MacroSeries."""
from .alphavantage import AlphaVantage
from .base import ErrorDescarga, FuentePrecios
from .fred import Fred
from .mercado import descargar_contexto
from .yahoo import YahooFinance

__all__ = ["AlphaVantage", "ErrorDescarga", "Fred", "FuentePrecios", "YahooFinance", "descargar_contexto"]
