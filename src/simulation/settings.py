"""Parámetros de una simulación de Monte Carlo, con sus valores por defecto y validación."""

from dataclasses import dataclass, replace
from numbers import Integral

from ..constants import DEFAULT_SEED, PERIODS_PER_YEAR
from ..errors import PortfolioError
from ..validation import is_finite_number, validate_positive_int

Assumption = float | dict[str, float] | None


def _assumption_values(assumption: Assumption) -> list:
    if assumption is None:
        return []
    return list(assumption.values()) if isinstance(assumption, dict) else [assumption]


def validate_assumptions(expected_returns: Assumption, volatilities: Assumption) -> None:
    """Los supuestos deben ser números finitos y las volatilidades, no negativas."""
    values = [*_assumption_values(expected_returns), *_assumption_values(volatilities)]
    if not all(is_finite_number(value) for value in values):
        raise PortfolioError("Los supuestos de retorno y volatilidad deben ser números finitos.")
    if any(value < 0 for value in _assumption_values(volatilities)):
        raise PortfolioError("La volatilidad no puede ser negativa.")


@dataclass(frozen=True)
class SimulationSettings:
    """steps son sesiones futuras; confidence fija la cola del VaR y CVaR.

    expected_returns y volatilities admiten un valor para todos los activos o un diccionario
    por símbolo; los activos sin supuesto usan su estimación histórica.
    """

    steps: int = PERIODS_PER_YEAR
    simulations: int = 1000
    seed: int | None = DEFAULT_SEED
    confidence: float = 0.95
    expected_returns: Assumption = None
    volatilities: Assumption = None

    def __post_init__(self) -> None:
        validate_positive_int("steps", self.steps)
        validate_positive_int("simulations", self.simulations)
        if self.seed is not None and (
            isinstance(self.seed, bool) or not isinstance(self.seed, Integral) or self.seed < 0
        ):
            raise PortfolioError("seed debe ser un entero no negativo o None.")
        if not is_finite_number(self.confidence) or not 0.5 < self.confidence < 1:
            raise PortfolioError("La confianza debe estar entre 0,5 y 1, sin incluir los extremos.")
        validate_assumptions(self.expected_returns, self.volatilities)

    @classmethod
    def from_options(cls, settings=None, **options) -> "SimulationSettings":
        """Admite un objeto ya creado, sus mismos campos como argumentos con nombre o ambos."""
        if settings is None:
            return cls(**options)
        if not isinstance(settings, cls):
            raise TypeError("settings debe ser SimulationSettings.")
        return replace(settings, **options) if options else settings
