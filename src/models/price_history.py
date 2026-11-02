"""Historial de precios validado de un símbolo, con la ficha común del activo."""

from dataclasses import InitVar, dataclass, field

import numpy as np
import pandas as pd

from ..constants import CLOSE, PRICE_BASES, PRICE_COLUMNS, PriceBasis, PriceColumn
from ..errors import PortfolioError
from ..validation import is_numeric_data, validate_dates
from .asset_profile import AssetProfile

# Algunos fondos solo publican valor liquidativo o cierre; las demás columnas se conservan.
NUMERIC_COLUMNS = ("Open", "High", "Low", "Close", "Adj Close", "Volume")
# Columnas que son niveles de precio: las únicas que resumen mean y std.
PRICE_LEVEL_COLUMNS = ("Open", "High", "Low", "Close", "Adj Close")


def period_returns(prices, log: bool = False):
    """Rentabilidades entre observaciones consecutivas de una Series o un DataFrame."""
    if log:
        return np.log(prices / prices.shift(1)).dropna()
    return prices.pct_change(fill_method=None).dropna()


@dataclass(frozen=True, eq=False)
class PriceHistory:
    """Precios de un símbolo con su procedencia.

    price_basis indica cómo ajusta el proveedor los cierres; partial_history, si el historial
    empieza después de la fecha pedida, y dropped_rows, cuántas fechas sin cierre descartó
    el adaptador.

    El historial es una instantánea: prices devuelve una copia, de modo que modificarla no
    altera el historial ni las carteras que lo usan. Por eso la media y la desviación típica
    se calculan una sola vez, al crearlo.
    """

    symbol: str
    source: str
    prices: InitVar[pd.DataFrame]
    profile: AssetProfile = field(default_factory=AssetProfile)
    price_basis: PriceBasis = "unknown"
    partial_history: bool = False
    dropped_rows: int = 0
    _prices: pd.DataFrame = field(init=False, repr=False)
    _mean: pd.Series = field(init=False, repr=False)
    _std: pd.Series = field(init=False, repr=False)

    def __post_init__(self, prices: pd.DataFrame) -> None:
        """Valida los precios, guarda una copia ordenada y calcula sus estadísticos."""
        self._validate(prices)
        prices = prices.copy().sort_index()
        levels = prices[[column for column in PRICE_LEVEL_COLUMNS if column in prices.columns]]
        object.__setattr__(self, "_prices", prices)
        object.__setattr__(self, "_mean", levels.mean(axis="index").rename("mean"))
        object.__setattr__(self, "_std", levels.std(axis="index").rename("std"))

    def _validate(self, prices: pd.DataFrame) -> None:
        """Comprueba fechas, columnas obligatorias, datos ausentes y la procedencia."""
        if not isinstance(prices, pd.DataFrame):
            raise TypeError("Los precios deben ser un DataFrame.")
        if not isinstance(self.profile, AssetProfile):
            raise TypeError("La ficha del activo debe ser un AssetProfile.")
        if self.price_basis not in PRICE_BASES:
            raise PortfolioError(f"El ajuste de precios debe ser uno de {', '.join(PRICE_BASES)}.")
        validate_dates(prices.index)
        if prices.columns.has_duplicates:
            raise PortfolioError("Las columnas de precios deben tener nombres únicos.")
        if CLOSE not in prices.columns:
            raise PortfolioError("Falta la columna de precios Close.")
        if prices.empty:
            raise PortfolioError("La tabla de precios no puede estar vacía.")
        for column in NUMERIC_COLUMNS:
            if column in prices.columns and not is_numeric_data(prices[column]):
                raise TypeError(f"{column} debe contener números.")
        for column in PRICE_COLUMNS:
            if column in prices.columns:
                values = prices[column].to_numpy(dtype=float)
                if not np.isfinite(values).all() or (values <= 0).any():
                    raise PortfolioError(
                        f"{column} debe contener precios positivos, finitos y sin datos ausentes."
                    )
        numeric = prices.select_dtypes(include="number")
        if np.isinf(numeric.to_numpy(dtype=float)).any():
            raise PortfolioError("Los precios deben contener números finitos.")

    @property
    def mean(self) -> pd.Series:
        """Media de cada columna de precios (Open, High, Low, Close, Adj Close), sin Volume."""
        return self._mean.copy()

    @property
    def std(self) -> pd.Series:
        """Desviación típica muestral de cada columna de precios."""
        return self._std.copy()

    def closing_prices(self, column: PriceColumn = CLOSE) -> pd.Series:
        """Selecciona Close o Adj Close con el símbolo como nombre de la serie."""
        if column not in PRICE_COLUMNS or column not in self._prices.columns:
            raise PortfolioError(
                f"{self.symbol} no dispone de la columna de precios admitida {column}."
            )
        return self._prices[column].copy().rename(self.symbol)

    def returns(self, log: bool = False, column: PriceColumn = CLOSE) -> pd.Series:
        return period_returns(self.closing_prices(column), log)


def _copy_of_prices(self: PriceHistory) -> pd.DataFrame:
    """Copia de los precios validados; los cambios en ella no afectan al historial."""
    return self._prices.copy()


# Se asigna tras crear la dataclass para que prices siga siendo el argumento del constructor.
PriceHistory.prices = property(_copy_of_prices)
