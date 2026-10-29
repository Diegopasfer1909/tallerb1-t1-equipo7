"""Referencias opcionales de mercado. Su creación no descarga datos."""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .economic_indicator import EconomicIndicator
from .price_history import PriceHistory


@dataclass
class ExchangeRate:
    """Unidades de contrapartida por unidad base: EUR/USD indica dólares por euro."""

    base_currency: str
    quote_currency: str
    indicator: EconomicIndicator
    max_age_days: int = 7

    def __post_init__(self) -> None:
        for currency in (self.base_currency, self.quote_currency):
            if len(currency) != 3 or not currency.isalpha() or not currency.isupper():
                raise ValueError(
                    "Los tipos de cambio requieren códigos de divisa en mayúsculas, por ejemplo EUR/USD."
                )
        if self.base_currency == self.quote_currency:
            raise ValueError("El tipo de cambio necesita dos divisas distintas.")
        if (
            isinstance(self.max_age_days, bool)
            or not isinstance(self.max_age_days, int)
            or self.max_age_days < 0
        ):
            raise ValueError("max_age_days debe ser un entero no negativo.")
        if (self.indicator.values.dropna() <= 0).any():
            raise ValueError("Los tipos de cambio deben ser positivos.")

    def on_dates(self, dates: pd.DatetimeIndex) -> pd.Series:
        """Utiliza datos pasados con un límite de antigüedad."""
        rates = self.indicator.values.dropna().reindex(
            dates, method="ffill", tolerance=pd.Timedelta(days=self.max_age_days)
        )
        if rates.isna().any():
            raise ValueError(
                f"Faltan tipos de cambio {self.base_currency}/{self.quote_currency} o son demasiado antiguos."
            )
        return rates


@dataclass
class MarketContext:
    benchmark: PriceHistory | None = None
    inflation: EconomicIndicator | None = None
    risk_free_rate: EconomicIndicator | None = None
    exchange_rates: list[ExchangeRate] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        pairs = [
            frozenset((rate.base_currency, rate.quote_currency)) for rate in self.exchange_rates
        ]
        if len(set(pairs)) != len(pairs):
            raise ValueError("Indica una sola serie de tipos de cambio por par de divisas.")

    def convert(self, prices: pd.Series, source: str, target: str) -> pd.Series:
        """Convierte una copia y conserva los precios originales y su divisa."""
        dates = prices.index
        if not isinstance(dates, pd.DatetimeIndex):
            raise TypeError("La conversión de divisas requiere un DatetimeIndex.")
        if source == target:
            return prices.copy()
        # Estas unidades de cotización son centésimas de su divisa principal.
        minor_units = {"GBp": "GBP", "ZAc": "ZAR"}
        if source in minor_units:
            prices = prices / 100
            source = minor_units[source]
        if source == target:
            return prices.copy()
        for rate in self.exchange_rates:
            pair = (rate.base_currency, rate.quote_currency)
            if pair == (source, target):
                converted = prices * rate.on_dates(dates)
                break
            if pair == (target, source):
                converted = prices / rate.on_dates(dates)
                break
        else:
            raise ValueError(f"Proporciona un tipo de cambio para convertir {source} a {target}.")
        if not np.isfinite(converted.to_numpy(dtype=float)).all() or (converted <= 0).any():
            raise ValueError("La conversión de divisas debe producir precios positivos y finitos.")
        return converted.rename(prices.name)
