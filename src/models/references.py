"""Referencias opcionales del análisis: índice, inflación y tipo de interés."""

from dataclasses import dataclass

from .economic_indicator import EconomicIndicator
from .notice import Notice
from .price_history import PriceHistory


@dataclass(frozen=True)
class MarketReferences:
    """Una referencia ausente deja sin calcular sus medidas; notices explica los fallos."""

    benchmark: PriceHistory | None = None
    inflation: EconomicIndicator | None = None
    risk_free_rate: EconomicIndicator | None = None
    notices: tuple[Notice, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "notices", tuple(self.notices))
