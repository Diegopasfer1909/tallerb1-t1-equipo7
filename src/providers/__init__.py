"""Adaptadores de las fuentes de datos externas.

Los contratos (PriceProvider, IndicatorProvider) y los errores comunes pertenecen al núcleo
(ports y errors); se reexportan aquí para que quien use los adaptadores los encuentre juntos.
"""

from ..constants import AAA_3M_YIELD
from ..errors import DataCoverageError, ProviderError
from ..ports import IndicatorProvider, PriceProvider, is_ecb_series
from .alpha_quota import AlphaVantageQuotaError
from .alpha_vantage import API_KEY_ENV as ALPHA_VANTAGE_KEY
from .alpha_vantage import AlphaVantageAPI
from .base import has_api_key
from .ecb import EcbAPI
from .fred import API_KEY_ENV as FRED_KEY
from .fred import FredAPI
from .yahoo import YahooFinanceAPI

__all__ = [
    "ALPHA_VANTAGE_KEY",
    "AlphaVantageAPI",
    "AlphaVantageQuotaError",
    "AAA_3M_YIELD",
    "DataCoverageError",
    "EcbAPI",
    "FRED_KEY",
    "FredAPI",
    "IndicatorProvider",
    "PriceProvider",
    "ProviderError",
    "YahooFinanceAPI",
    "has_api_key",
    "is_ecb_series",
]
