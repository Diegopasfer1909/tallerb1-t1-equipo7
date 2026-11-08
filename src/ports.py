"""Puertos del núcleo: lo que la carga de datos necesita de cualquier fuente externa.

Los contratos pertenecen al núcleo y los adaptadores de providers los cumplen; así la carga y
el análisis no importan ningún adaptador concreto. Solo main elige y crea los adaptadores.
"""

from dataclasses import dataclass
from typing import Protocol

from .models.economic_indicator import EconomicIndicator
from .models.price_history import PriceHistory


class PriceProvider(Protocol):
    """Lo que el resto del programa necesita de cualquier fuente de precios.

    Las opciones propias de cada proveedor se indican al crear el adaptador, de modo
    que añadir una fuente nueva no obliga a cambiar la carga ni el análisis.
    """

    def get_prices(
        self, symbol: str, start: str, end: str, *, adjusted: bool = False
    ) -> PriceHistory: ...


class IndicatorProvider(Protocol):
    """Fuente de series económicas, como FRED o el BCE; la fecha final se excluye."""

    def get_series(self, series_id: str, start: str, end: str) -> EconomicIndicator: ...


def is_ecb_series(series_id: str) -> bool:
    """Solo los identificadores del BCE incluyen una barra (CONJUNTO/CLAVE); los de FRED, no."""
    return "/" in series_id


@dataclass(frozen=True)
class ReferenceSources:
    """Adaptadores de las referencias del informe, elegidos por quien compone la aplicación.

    benchmark descarga el índice con su ficha, que indica la divisa en la que cotiza; market,
    los cambios, el oro y el ETF de Bunds, que solo necesitan precios (sin market se usa
    benchmark). fred es None cuando falta su clave: sus series quedan sin calcular y el informe
    lo explica.
    """

    benchmark: PriceProvider
    market: PriceProvider | None = None
    fred: IndicatorProvider | None = None
    ecb: IndicatorProvider | None = None

    @property
    def prices(self) -> PriceProvider:
        return self.market if self.market is not None else self.benchmark

    def for_series(self, series_id: str) -> IndicatorProvider | None:
        """Fuente que publica la serie: el BCE para sus identificadores y FRED para el resto."""
        return self.ecb if is_ecb_series(series_id) else self.fred
