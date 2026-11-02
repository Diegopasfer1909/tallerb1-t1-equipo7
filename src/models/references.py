"""Referencias opcionales del análisis: índice, inflación, tipo de interés y mercado."""

from dataclasses import dataclass, field

from .currency import FxRates
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
    # Contexto de mercado: se compara con la cartera, pero no interviene en su valoración.
    vix: EconomicIndicator | None = None
    brent: EconomicIndicator | None = None
    gold: PriceHistory | None = None
    bund_etf: PriceHistory | None = None
    # Cambio para llevar el índice a la divisa de la cartera, si esta no lo necesita.
    benchmark_fx: FxRates = field(default_factory=FxRates)

    def __post_init__(self) -> None:
        object.__setattr__(self, "notices", tuple(self.notices))

    @property
    def latest_risk_free_rate(self) -> float | None:
        """Último tipo anual publicado, como fracción; None si no está disponible."""
        rate = self.risk_free_rate
        if rate is None or rate.units.strip().lower() not in ("percent", "%"):
            return None
        return float(rate.values.dropna().iloc[-1]) / 100
