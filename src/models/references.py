"""Referencias opcionales del análisis: índice, inflación, tipo de interés y mercado."""

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
    # Contexto de mercado: se compara con la cartera, pero no interviene en su valoración.
    vix: EconomicIndicator | None = None
    brent: EconomicIndicator | None = None
    gold: PriceHistory | None = None
    bund_etf: PriceHistory | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "notices", tuple(self.notices))
        if not isinstance(self.fx_rates, FxRates):
            raise TypeError("fx_rates debe ser FxRates.")

    @property
    def latest_risk_free_rate(self) -> float | None:
        """Último tipo anual publicado, como fracción; None si no está disponible."""
        rate = self.risk_free_rate
        if rate is None or rate.units.strip().lower() not in ("percent", "%"):
            return None
        return float(rate.values.dropna().iloc[-1]) / 100
