"""Validaciones compartidas por los modelos, el análisis, la simulación y la carga de datos."""

from datetime import datetime
from math import isclose, isfinite
from numbers import Integral, Real

import numpy as np
import pandas as pd

from .constants import MONTHLY
from .errors import PortfolioError

# Admite pesos redondeados a seis decimales, como 0.333333 tres veces.
WEIGHT_TOLERANCE = 1e-5


def is_finite_number(value) -> bool:
    """Número real y finito; los booleanos no cuentan como números."""
    return not isinstance(value, bool) and isinstance(value, Real) and isfinite(value)


def is_numeric_data(values: pd.Series) -> bool:
    """Columna numérica; una columna de booleanos no se acepta como números."""
    return pd.api.types.is_numeric_dtype(values) and not pd.api.types.is_bool_dtype(values)


def validate_dates(index: pd.Index) -> None:
    if not isinstance(index, pd.DatetimeIndex):
        raise TypeError("Los datos deben tener un DatetimeIndex.")
    if index.hasnans or index.has_duplicates:
        raise PortfolioError("Las fechas deben ser válidas y no repetirse.")
    if index.tz is not None:
        raise PortfolioError("Utiliza fechas diarias sin zona horaria.")


def date_range(start: str, end: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Exige fechas AAAA-MM-DD; todos los proveedores incluyen el inicio y excluyen el final."""
    try:
        first = pd.Timestamp(datetime.strptime(start, "%Y-%m-%d"))
        last = pd.Timestamp(datetime.strptime(end, "%Y-%m-%d"))
    except (ValueError, TypeError):
        raise PortfolioError(
            "Utiliza fechas válidas con el formato AAAA-MM-DD, por ejemplo 2026-10-01."
        ) from None
    if first >= last:
        raise PortfolioError("La fecha de inicio debe ser anterior a la fecha final.")
    return first, last


def validate_symbols(symbols) -> None:
    """Rechaza símbolos vacíos o repetidos, sin distinguir mayúsculas de minúsculas."""
    seen = set()
    for symbol in symbols:
        if not isinstance(symbol, str) or not symbol.strip():
            raise PortfolioError(
                "Los símbolos de los activos deben ser cadenas de texto no vacías."
            )
        key = symbol.strip().lower()
        if key in seen:
            raise PortfolioError(f"Activo repetido: {symbol}. Combina antes sus pesos.")
        seen.add(key)


def validate_weights(weights: list[float]) -> None:
    if not weights:
        raise PortfolioError("Indica al menos un activo y su peso.")
    if not all(is_finite_number(weight) and 0 <= weight <= 1 for weight in weights):
        raise PortfolioError("Cada peso debe ser un número entre 0 y 1.")
    if not isclose(sum(weights), 1, rel_tol=0, abs_tol=WEIGHT_TOLERANCE):
        raise PortfolioError("Los pesos deben sumar 1. Por ejemplo: IBM:0.6 MSFT:0.4.")


def validate_target_weights(weights: pd.Series, columns: pd.Index) -> np.ndarray:
    """Exige un peso por columna y los devuelve en el mismo orden que las columnas."""
    if not weights.index.is_unique or set(weights.index) != set(columns):
        raise PortfolioError("Indica exactamente un peso objetivo por activo.")
    ordered = weights.reindex(columns).astype(float)
    validate_weights(ordered.tolist())
    return ordered.to_numpy()


def validate_price_table(prices: pd.DataFrame) -> None:
    """Una columna por activo, fechas ordenadas y precios positivos, finitos y completos."""
    if not isinstance(prices, pd.DataFrame) or prices.empty or prices.columns.has_duplicates:
        raise PortfolioError(
            "Se necesita una tabla de precios no vacía con una columna por activo."
        )
    validate_dates(prices.index)
    if not prices.index.is_monotonic_increasing:
        raise PortfolioError("Las fechas de los precios deben estar ordenadas.")
    values = prices.to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise PortfolioError(
            "Los precios deben ser positivos y finitos, y no puede faltar ningún dato."
        )


def validate_positive_int(name: str, value) -> None:
    if isinstance(value, bool) or not isinstance(value, Integral) or value < 1:
        raise PortfolioError(f"{name} debe ser un entero positivo.")


def validate_capital(capital) -> None:
    if not is_finite_number(capital) or capital <= 0:
        raise PortfolioError("El capital inicial debe ser positivo y finito.")


def validate_rebalance(rebalance) -> None:
    if rebalance not in (None, MONTHLY):
        raise PortfolioError("El rebalanceo debe ser 'monthly' o None.")


def validate_currency_code(code, label: str = "La divisa") -> None:
    """Código de tres letras en mayúsculas, como EUR; las unidades como GBp no valen aquí."""
    if not isinstance(code, str) or len(code) != 3 or not code.isalpha() or not code.isupper():
        raise PortfolioError(f"{label} debe ser un código de tres letras en mayúsculas, como EUR.")
