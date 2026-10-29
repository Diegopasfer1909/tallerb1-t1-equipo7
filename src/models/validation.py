"""Validaciones compartidas por los modelos y la carga de datos."""

from math import isclose, isfinite
from numbers import Real

import pandas as pd


def validate_dates(index: pd.Index) -> None:
    if not isinstance(index, pd.DatetimeIndex):
        raise TypeError("Los datos deben tener un DatetimeIndex.")
    if index.hasnans or index.has_duplicates:
        raise ValueError("Las fechas deben ser válidas y no repetirse.")
    if index.tz is not None:
        raise ValueError("Utiliza fechas diarias sin zona horaria.")


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
