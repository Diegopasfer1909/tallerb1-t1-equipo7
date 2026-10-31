"""Tipos de cambio y conversión de precios entre divisas. Su creación no descarga datos."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..constants import FX_MAX_AGE_DAYS
from ..errors import PortfolioError
from ..validation import validate_currency_code
from .economic_indicator import EconomicIndicator

# Estas unidades de cotización son centésimas de su divisa principal.
MINOR_UNITS = {"GBp": "GBP", "ZAc": "ZAR"}


@dataclass(frozen=True)
class ExchangeRate:
    """Unidades de contrapartida por unidad base: EUR/USD indica dólares por euro."""

    base_currency: str
    quote_currency: str
    indicator: EconomicIndicator
    max_age_days: int = FX_MAX_AGE_DAYS

    def __post_init__(self) -> None:
        for currency in (self.base_currency, self.quote_currency):
            validate_currency_code(currency, "Cada divisa de un tipo de cambio")
        if self.base_currency == self.quote_currency:
            raise PortfolioError("El tipo de cambio necesita dos divisas distintas.")
        if (
            isinstance(self.max_age_days, bool)
            or not isinstance(self.max_age_days, int)
            or self.max_age_days < 0
        ):
            raise PortfolioError("max_age_days debe ser un entero no negativo.")
        if (self.indicator.values.dropna() <= 0).any():
            raise PortfolioError("Los tipos de cambio deben ser positivos.")

    def on_dates(self, dates: pd.DatetimeIndex) -> pd.Series:
        """Utiliza datos pasados con un límite de antigüedad."""
        rates = self.indicator.as_of(dates, self.max_age_days)
        if rates.isna().any():
            raise PortfolioError(
                f"Faltan tipos de cambio {self.base_currency}/{self.quote_currency} "
                "o son demasiado antiguos."
            )
        return rates


@dataclass(frozen=True)
class FxRates:
    """Cambios disponibles para valorar una cartera en su divisa; uno por par de divisas."""

    rates: tuple[ExchangeRate, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "rates", tuple(self.rates))
        pairs = [frozenset((rate.base_currency, rate.quote_currency)) for rate in self.rates]
        if len(set(pairs)) != len(pairs):
            raise PortfolioError("Indica una sola serie de tipos de cambio por par de divisas.")

    def convert(self, prices: pd.Series, source: str, target: str) -> pd.Series:
        """Convierte una copia y conserva los precios originales y su divisa."""
        if not isinstance(prices.index, pd.DatetimeIndex):
            raise TypeError("La conversión de divisas requiere un DatetimeIndex.")
        if source != target and source in MINOR_UNITS:
            prices, source = prices / 100, MINOR_UNITS[source]
        if source == target:
            return prices.copy()
        for rate in self.rates:
            pair = (rate.base_currency, rate.quote_currency)
            if pair == (source, target):
                converted = prices * rate.on_dates(prices.index)
                break
            if pair == (target, source):
                converted = prices / rate.on_dates(prices.index)
                break
        else:
            raise PortfolioError(
                f"Proporciona un tipo de cambio para convertir {source} a {target}."
            )
        if not np.isfinite(converted.to_numpy(dtype=float)).all() or (converted <= 0).any():
            raise PortfolioError(
                "La conversión de divisas debe producir precios positivos y finitos."
            )
        return converted.rename(prices.name)
