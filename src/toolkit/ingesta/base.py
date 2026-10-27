"""Interfaz común de las fuentes de precios.

Cada API implementa solo `_cierres()` (cómo pedir los precios) y, si puede, `_metadatos()`.
La conversión a PriceSeries es siempre la misma, así que todas las fuentes devuelven
objetos idénticos. Añadir una API nueva = una subclase con esos dos métodos.
"""
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from ..modelos.series import PriceSeries


class ErrorDescarga(Exception):
    """La fuente no devolvió datos utilizables."""


def http_get(url: str, params: dict | None = None, timeout: int = 30):
    """GET con curl_cffi imitando a Chrome: algunas APIs rechazan el cliente de requests."""
    from curl_cffi import requests as cr

    respuesta = cr.get(url, params=params, impersonate="chrome", timeout=timeout)
    respuesta.raise_for_status()
    return respuesta


class FuentePrecios(ABC):
    nombre: str = ""
    ajustado: bool = True   # ¿los cierres incluyen dividendos y splits?
    max_hilos: int = 8      # descargas simultáneas en descargar_varios

    @abstractmethod
    def _cierres(self, symbol: str, inicio: str | None, fin: str | None) -> pd.Series:
        """Serie de cierres indexada por fecha, en la divisa en que cotiza el activo."""

    def _metadatos(self, symbol: str) -> dict:
        """Claves opcionales: nombre, divisa, tipo, sector, pais."""
        return {}

    def descargar(self, symbol: str, inicio: str | None = None, fin: str | None = None) -> PriceSeries:
        try:
            cierres = self._cierres(symbol, inicio, fin)
        except ErrorDescarga:
            raise
        except Exception as error:
            raise ErrorDescarga(f"{symbol}: {type(error).__name__}: {error}") from error
        if cierres is None or cierres.dropna().empty:
            raise ErrorDescarga(f"{symbol}: {self.nombre} no devolvió precios.")

        meta = {k: " ".join(v.split()) if isinstance(v, str) else v
                for k, v in self._metadatos(symbol).items() if v}
        divisa = meta.get("divisa", "EUR")
        if divisa[-1].islower():    # cotizaciones en centavos: GBp (peniques), ZAc...
            cierres, meta["divisa"] = cierres / 100, divisa.upper()
        return PriceSeries(symbol=symbol, source=self.nombre, datos=cierres, ajustado=self.ajustado, **meta)

    def descargar_varios(self, symbols: list[str], inicio: str | None = None,
                         fin: str | None = None) -> dict[str, PriceSeries]:
        """Descarga N series a la vez (en paralelo). Si falla alguna, dice cuáles."""
        symbols = list(dict.fromkeys(symbols))     # sin repetidos, en el orden dado

        def una(symbol):
            try:
                return symbol, self.descargar(symbol, inicio, fin), None
            except Exception as error:
                return symbol, None, error

        with ThreadPoolExecutor(max_workers=max(1, min(self.max_hilos, len(symbols)))) as hilos:
            resultados = list(hilos.map(una, symbols))

        fallidos = {s: e for s, _, e in resultados if e is not None}
        if fallidos:
            detalle = "; ".join(str(e) if str(e).startswith(s) else f"{s}: {e}" for s, e in fallidos.items())
            raise ErrorDescarga(f"{self.nombre}: fallaron {len(fallidos)} de {len(symbols)} series. {detalle}")
        return {s: serie for s, serie, _ in resultados}
