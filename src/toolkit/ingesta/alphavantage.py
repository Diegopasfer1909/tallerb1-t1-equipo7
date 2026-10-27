"""Alpha Vantage: acciones, con clave gratuita (https://www.alphavantage.co/support/#api-key).

La clave se lee de la variable de entorno ALPHAVANTAGE_API_KEY o se pasa al crear el
proveedor. El plan gratuito da cierres SIN ajustar por dividendos (ajustado=False),
25 peticiones al día y solo los últimos 100 días con tamano="compact".
"""
import os

import pandas as pd

from .base import ErrorDescarga, FuentePrecios, http_get

URL = "https://www.alphavantage.co/query"
TIPOS = {"Common Stock": "accion", "ETF": "etf"}


class AlphaVantage(FuentePrecios):
    nombre = "Alpha Vantage"
    ajustado = False
    max_hilos = 1           # el plan gratuito limita las peticiones por minuto

    def __init__(self, api_key: str | None = None, tamano: str = "full", con_metadatos: bool = True):
        self.api_key = api_key or os.environ.get("ALPHAVANTAGE_API_KEY")
        if not self.api_key:
            raise ValueError("Falta la clave de Alpha Vantage: pásala como api_key o define ALPHAVANTAGE_API_KEY.")
        self.tamano = tamano
        self.con_metadatos = con_metadatos

    def _consultar(self, funcion: str, symbol: str, **extra) -> dict:
        datos = http_get(URL, {"function": funcion, "symbol": symbol, "apikey": self.api_key, **extra}).json()
        for aviso in ("Error Message", "Information", "Note"):
            if aviso in datos:
                raise ErrorDescarga(f"{symbol}: Alpha Vantage: {datos[aviso]}")
        return datos

    def _cierres(self, symbol, inicio, fin) -> pd.Series:
        datos = self._consultar("TIME_SERIES_DAILY", symbol, outputsize=self.tamano)
        return self.parsear_cierres(datos).loc[inicio:fin]

    @staticmethod
    def parsear_cierres(datos: dict) -> pd.Series:
        serie = datos.get("Time Series (Daily)", {})
        return pd.Series({pd.Timestamp(f): float(v["4. close"]) for f, v in serie.items()}).sort_index()

    def _metadatos(self, symbol) -> dict:
        if not self.con_metadatos:
            return {}
        try:
            info = self._consultar("OVERVIEW", symbol)
        except ErrorDescarga:
            return {}
        return self.parsear_metadatos(info)

    @staticmethod
    def parsear_metadatos(info: dict) -> dict:
        return {
            "nombre": info.get("Name"),
            "divisa": info.get("Currency"),
            "tipo": TIPOS.get(info.get("AssetType"), "otro"),
            "sector": (info.get("Sector") or "").title() or None,
            "pais": info.get("Country"),
        }
