"""Serie económica validada, como la inflación, un tipo de interés o un tipo de cambio."""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..errors import PortfolioError
from ..validation import is_numeric_data, validate_dates


@dataclass(frozen=True)
class EconomicIndicator:
    """point_in_time indica que cada fecha muestra el último dato publicado hasta entonces,
    sin revisiones posteriores; si es False, los valores están en su fecha de observación."""

    series_id: str
    source: str
    values: pd.Series
    units: str
    frequency: str
    info: dict = field(default_factory=dict)
    point_in_time: bool = False

    def __post_init__(self) -> None:
        """Valida las observaciones y conserva los datos ausentes en una copia ordenada."""
        self._validate()
        object.__setattr__(self, "values", self.values.copy().sort_index())

    def _validate(self) -> None:
        """Admite datos ausentes, pero exige al menos una observación finita."""
        if not isinstance(self.values, pd.Series):
            raise TypeError("Los valores del indicador deben ser una Series.")
        validate_dates(self.values.index)
        if not is_numeric_data(self.values):
            raise TypeError("Los valores del indicador deben ser numéricos, no booleanos.")
        valid = self.values.dropna()
        if valid.empty or not np.isfinite(valid.to_numpy(dtype=float)).all():
            raise PortfolioError(
                "El indicador debe contener al menos un valor numérico válido y no puede "
                "incluir valores infinitos."
            )

    @property
    def missing_count(self) -> int:
        return int(self.values.isna().sum())

    @property
    def mean(self) -> float:
        """Media de los valores observados."""
        return float(self.values.mean())

    @property
    def std(self) -> float:
        """Desviación típica muestral; NaN si solo hay una observación."""
        return float(self.values.std(ddof=1))

    def as_of(self, dates: pd.DatetimeIndex, max_age_days: int) -> pd.Series:
        """Último valor publicado en cada fecha, o NaN si es más antiguo que max_age_days."""
        return self.values.dropna().reindex(
            dates, method="ffill", tolerance=pd.Timedelta(days=max_age_days)
        )
