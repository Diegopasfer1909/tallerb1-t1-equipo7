"""Un activo y su historial, independiente de su peso en una cartera."""

from dataclasses import dataclass

import pandas as pd

from ..simulation.monte_carlo import MonteCarloMixin
from .price_history import PriceHistory

ASSET_TYPES = ("stock", "index", "etf", "fund", "unknown")


@dataclass
class Asset(MonteCarloMixin):
    history: PriceHistory
    currency: str = ""
    asset_type: str = "unknown"

    def __post_init__(self) -> None:
        if not isinstance(self.history, PriceHistory):
            raise TypeError("El activo necesita un objeto PriceHistory.")
        if not isinstance(self.history.symbol, str) or not self.history.symbol.strip():
            raise ValueError("El activo necesita un símbolo.")
        if self.history.info.get("price_adjustment") == "adjusted":
            raise ValueError(
                "La valoración necesita Close sin ajuste por dividendos. Descarga con adjusted=False; utiliza Adj Close para las rentabilidades."
            )
        reported = self.history.info.get("currency")
        if self.currency and reported and self.currency != reported:
            raise ValueError(
                f"{self.symbol} cotiza en {reported}; la divisa indicada es {self.currency}."
            )
        if not self.currency:
            self.currency = reported or ""
        if not isinstance(self.currency, str) or not self.currency.strip():
            raise ValueError(f"Falta la divisa de {self.symbol}. Indícala expresamente.")
        # GBp (peniques) y GBP (libras) son unidades distintas: conserva las mayúsculas.
        self.currency = self.currency.strip()
        if self.asset_type == "unknown":
            self.asset_type = self.history.info.get("asset_type") or "unknown"
        if self.asset_type not in ASSET_TYPES:
            raise ValueError(f"El tipo de activo debe ser uno de {', '.join(ASSET_TYPES)}.")

    @property
    def symbol(self) -> str:
        return self.history.symbol

    @property
    def name(self) -> str:
        return self.history.info.get("name") or self.symbol

    @property
    def latest_price(self) -> float:
        return float(self.history.closing_prices().iloc[-1])

    def _simulation_inputs(self, price_column: str):
        """Simula el valor de una unidad desde su último precio Close."""
        prices = self.history.closing_prices(price_column).to_frame()
        return prices, pd.Series({self.symbol: self.latest_price}), None
