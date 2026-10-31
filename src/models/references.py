"""Referencias opcionales del análisis: índice, inflación y tipo de interés."""

from dataclasses import dataclass, field

from .currency import FxRates
from .economic_indicator import EconomicIndicator
from .notice import Notice
from .price_history import PriceHistory


@dataclass(frozen=True)
class MarketReferences:
    """Una referencia ausente deja sin calcular sus medidas; notices explica los fallos.

    fx_rates contiene los cambios que necesita un índice que cotiza en otra divisa que la
    cartera; se añaden a los de la cartera solo para compararla con él.
    """

    benchmark: PriceHistory | None = None
    inflation: EconomicIndicator | None = None
    risk_free_rate: EconomicIndicator | None = None
    notices: tuple[Notice, ...] = ()
    fx_rates: FxRates = field(default_factory=FxRates)

    def __post_init__(self) -> None:
        object.__setattr__(self, "notices", tuple(self.notices))
        if not isinstance(self.fx_rates, FxRates):
            raise TypeError("fx_rates debe ser FxRates.")
