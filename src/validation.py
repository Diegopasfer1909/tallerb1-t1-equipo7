"""Validaciones compartidas por los modelos, el análisis, la simulación y la carga de datos."""

from math import isclose, isfinite
from numbers import Integral, Real

import numpy as np
import pandas as pd


def validate_dates(index: pd.Index) -> None:
    if not isinstance(index, pd.DatetimeIndex):
        raise TypeError("Los datos deben tener un DatetimeIndex.")
    if index.hasnans or index.has_duplicates:
        raise ValueError("Las fechas deben ser válidas y no repetirse.")
    if index.tz is not None:
        raise ValueError("Utiliza fechas diarias sin zona horaria.")


def validate_symbols(symbols) -> None:
    """Rechaza símbolos vacíos o repetidos, sin distinguir mayúsculas de minúsculas."""
    seen = set()
    for symbol in symbols:
        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("Los símbolos de los activos deben ser cadenas de texto no vacías.")
        key = symbol.strip().lower()
        if key in seen:
            raise ValueError(f"Activo repetido: {symbol}. Combina antes sus pesos.")
        seen.add(key)


def validate_weights(weights: list[float]) -> None:
    if not weights:
        raise ValueError("Indica al menos un activo y su peso.")
    for weight in weights:
        if (
            isinstance(weight, bool)
            or not isinstance(weight, Real)
            or not isfinite(weight)
            or not 0 <= weight <= 1
        ):
            raise ValueError("Cada peso debe ser un número entre 0 y 1.")
    if not isclose(sum(weights), 1, rel_tol=0, abs_tol=1e-10):
        raise ValueError("Los pesos deben sumar 1. Por ejemplo: IBM:0.6 MSFT:0.4.")


def validate_target_weights(weights: pd.Series, columns: pd.Index) -> np.ndarray:
    """Exige un peso por columna y los devuelve en el mismo orden que las columnas."""
    if not weights.index.is_unique or set(weights.index) != set(columns):
        raise ValueError("Indica exactamente un peso objetivo por activo.")
    ordered = weights.reindex(columns).astype(float)
    validate_weights(ordered.tolist())
    return ordered.to_numpy()


def validate_price_table(prices: pd.DataFrame) -> None:
    """Una columna por activo, fechas ordenadas y precios positivos, finitos y completos."""
    if not isinstance(prices, pd.DataFrame) or prices.empty or prices.columns.has_duplicates:
        raise ValueError("Se necesita una tabla de precios no vacía con una columna por activo.")
    validate_dates(prices.index)
    if not prices.index.is_monotonic_increasing:
        raise ValueError("Las fechas de los precios deben estar ordenadas.")
    values = prices.to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError(
            "Los precios deben ser positivos y finitos, y no puede faltar ningún dato."
        )


def validate_positive_int(name: str, value) -> None:
    if isinstance(value, bool) or not isinstance(value, Integral) or value < 1:
        raise ValueError(f"{name} debe ser un entero positivo.")
