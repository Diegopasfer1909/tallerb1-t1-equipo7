from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..validation import validate_dates


def period_returns(prices, log: bool = False):
    """Rentabilidades entre observaciones consecutivas de una Series o un DataFrame."""
    if log:
        return np.log(prices / prices.shift(1)).dropna()
    return prices.pct_change(fill_method=None).dropna()


@dataclass
class PriceHistory:
    """Historial validado de un símbolo. info usa las claves comunes de los proveedores.

    mean y std se calculan al crear el objeto sobre las columnas de precios; si cambian los
    precios, crea un historial nuevo para que las estadísticas sigan siendo correctas.
    """

    symbol: str
    source: str
    prices: pd.DataFrame
    mean: pd.Series = field(init=False)
    std: pd.Series = field(init=False)
    info: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Valida los precios, ordena una copia y calcula las estadísticas."""
        self._validate()
        self.prices = self.prices.copy().sort_index()
        self._calculate_statistics()

    def _validate(self) -> None:
        """Comprueba fechas, columnas obligatorias y datos ausentes."""
        if not isinstance(self.prices, pd.DataFrame):
            raise TypeError("Los precios deben ser un DataFrame.")
        validate_dates(self.prices.index)
        if self.prices.columns.has_duplicates:
            raise ValueError("Las columnas de precios deben tener nombres únicos.")
        if "Close" not in self.prices.columns:
            raise ValueError("Falta la columna de precios Close.")
        if self.prices.empty:
            raise ValueError("La tabla de precios no puede estar vacía.")
        # Algunos fondos solo publican valor liquidativo o cierre; conserva las demás columnas.
        for column in ["Open", "High", "Low", "Close", "Adj Close", "Volume"]:
            if column not in self.prices.columns:
                continue
            if pd.api.types.is_bool_dtype(self.prices[column]) or not pd.api.types.is_numeric_dtype(
                self.prices[column]
            ):
                raise TypeError(f"{column} debe contener números.")
        for column in ["Close", "Adj Close"]:
            if column in self.prices.columns:
                values = self.prices[column].to_numpy(dtype=float)
                if not np.isfinite(values).all() or (values <= 0).any():
                    raise ValueError(
                        f"{column} debe contener precios positivos, finitos y sin datos ausentes."
                    )
        numeric = self.prices.select_dtypes(include="number")
        if np.isinf(numeric.to_numpy(dtype=float)).any():
            raise ValueError("Los precios deben contener números finitos.")

    def _calculate_statistics(self) -> None:
        """Calcula la media y la desviación típica muestral por columna numérica."""
        self.mean = self.prices.mean(axis="index", numeric_only=True)
        self.std = self.prices.std(axis="index", numeric_only=True)

    def closing_prices(self, column: str = "Close") -> pd.Series:
        """Selecciona Close o Adj Close conservando el resto del historial."""
        if column not in ("Close", "Adj Close") or column not in self.prices.columns:
            raise ValueError(
                f"{self.symbol} no dispone de la columna de precios admitida {column}."
            )
        values = self.prices[column]
        if not isinstance(values, pd.Series):
            raise TypeError("Se esperaba una columna de precios de cierre.")
        return values.copy().rename(self.symbol)

    def returns(self, log: bool = False, column: str = "Close") -> pd.Series:
        return period_returns(self.closing_prices(column), log)
