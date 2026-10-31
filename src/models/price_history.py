"""Historial de precios validado de un símbolo, con la ficha común del activo."""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..constants import CLOSE, PRICE_BASES, PRICE_COLUMNS, PriceBasis, PriceColumn
from ..errors import PortfolioError
from ..validation import is_numeric_data, validate_dates
from .asset_profile import AssetProfile

# Algunos fondos solo publican valor liquidativo o cierre; las demás columnas se conservan.
NUMERIC_COLUMNS = ("Open", "High", "Low", "Close", "Adj Close", "Volume")


def period_returns(prices, log: bool = False):
    """Rentabilidades entre observaciones consecutivas de una Series o un DataFrame."""
    if log:
        return np.log(prices / prices.shift(1)).dropna()
    return prices.pct_change(fill_method=None).dropna()


@dataclass(frozen=True)
class PriceHistory:
    """Precios de un símbolo con su procedencia.

    price_basis indica cómo ajusta el proveedor los cierres; partial_history, si el historial
    empieza después de la fecha pedida, y dropped_rows, cuántas fechas sin cierre descartó
    el adaptador.
    """

    symbol: str
    source: str
    prices: pd.DataFrame
    profile: AssetProfile = field(default_factory=AssetProfile)
    price_basis: PriceBasis = "unknown"
    partial_history: bool = False
    dropped_rows: int = 0

    def __post_init__(self) -> None:
        """Valida los precios y guarda una copia ordenada, ajena a cambios externos."""
        self._validate()
        object.__setattr__(self, "prices", self.prices.copy().sort_index())

    def _validate(self) -> None:
        """Comprueba fechas, columnas obligatorias, datos ausentes y la procedencia."""
        if not isinstance(self.prices, pd.DataFrame):
            raise TypeError("Los precios deben ser un DataFrame.")
        if not isinstance(self.profile, AssetProfile):
            raise TypeError("La ficha del activo debe ser un AssetProfile.")
        if self.price_basis not in PRICE_BASES:
            raise PortfolioError(f"El ajuste de precios debe ser uno de {', '.join(PRICE_BASES)}.")
        validate_dates(self.prices.index)
        if self.prices.columns.has_duplicates:
            raise PortfolioError("Las columnas de precios deben tener nombres únicos.")
        if CLOSE not in self.prices.columns:
            raise PortfolioError("Falta la columna de precios Close.")
        if self.prices.empty:
            raise PortfolioError("La tabla de precios no puede estar vacía.")
        for column in NUMERIC_COLUMNS:
            if column in self.prices.columns and not is_numeric_data(self.prices[column]):
                raise TypeError(f"{column} debe contener números.")
        for column in PRICE_COLUMNS:
            if column in self.prices.columns:
                values = self.prices[column].to_numpy(dtype=float)
                if not np.isfinite(values).all() or (values <= 0).any():
                    raise PortfolioError(
                        f"{column} debe contener precios positivos, finitos y sin datos ausentes."
                    )
        numeric = self.prices.select_dtypes(include="number")
        if np.isinf(numeric.to_numpy(dtype=float)).any():
            raise PortfolioError("Los precios deben contener números finitos.")

    @property
    def mean(self) -> pd.Series:
        """Media de cada columna numérica, siempre acorde con los precios actuales."""
        return self.prices.mean(axis="index", numeric_only=True)

    @property
    def std(self) -> pd.Series:
        """Desviación típica muestral de cada columna numérica."""
        return self.prices.std(axis="index", numeric_only=True)

    def closing_prices(self, column: PriceColumn = CLOSE) -> pd.Series:
        """Selecciona Close o Adj Close con el símbolo como nombre de la serie."""
        if column not in PRICE_COLUMNS or column not in self.prices.columns:
            raise PortfolioError(
                f"{self.symbol} no dispone de la columna de precios admitida {column}."
            )
        return self.prices[column].copy().rename(self.symbol)

    def returns(self, log: bool = False, column: PriceColumn = CLOSE) -> pd.Series:
        return period_returns(self.closing_prices(column), log)
