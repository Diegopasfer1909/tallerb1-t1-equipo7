from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..validation import validate_dates


@dataclass
class EconomicIndicator:
    series_id: str
    source: str
    values: pd.Series
    units: str
    frequency: str
    info: dict = field(default_factory=dict)
    mean: float = field(init=False)
    std: float = field(init=False)
    missing_count: int = field(init=False)

    def __post_init__(self) -> None:
        """Valida las observaciones, conserva los datos ausentes y calcula las estadísticas."""
        self._validate()
        self.values = self.values.copy().sort_index()
        self._calculate_statistics()

    def _validate(self) -> None:
        """Admite datos ausentes, pero exige al menos una observación finita."""
        if not isinstance(self.values, pd.Series):
            raise TypeError("Los valores del indicador deben ser una Series.")
        validate_dates(self.values.index)
        if pd.api.types.is_bool_dtype(self.values) or not pd.api.types.is_numeric_dtype(
            self.values
        ):
            raise TypeError("Los valores del indicador deben ser numéricos, no booleanos.")
        valid = self.values.dropna()
        if valid.empty or not np.isfinite(valid.to_numpy(dtype=float)).all():
            raise ValueError(
                "El indicador debe contener al menos un valor numérico válido y no puede incluir valores infinitos."
            )

    def _calculate_statistics(self) -> None:
        """Cuenta los datos ausentes y calcula las estadísticas con los valores observados."""
        self.missing_count = int(self.values.isna().sum())
        observed = self.values.dropna().to_numpy(dtype=float)
        self.mean = float(np.mean(observed))
        if len(observed) > 1:
            self.std = float(np.std(observed, ddof=1))
        else:
            self.std = float("nan")
