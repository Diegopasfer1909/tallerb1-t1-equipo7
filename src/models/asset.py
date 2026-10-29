"""Un activo y su historial, independiente de su peso en una cartera."""

from dataclasses import dataclass

import pandas as pd

from ..simulation.monte_carlo import simulate_paths
from ..simulation.result import SimulationResult
from .price_history import PriceHistory


@dataclass
class Asset:
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
        reported = self.history.info.get("currency") or self.history.info.get("Currency")
        if self.currency and reported and self.currency != reported:
            raise ValueError(
                f"{self.symbol} cotiza en {reported}; la divisa indicada es {self.currency}."
            )
        if not self.currency:
            self.currency = reported or ""
        if not isinstance(self.currency, str) or not self.currency.strip():
            raise ValueError(f"Falta la divisa de {self.symbol}. Indícala expresamente.")
        self.currency = self.currency.strip()
        # GBp (peniques) y GBP (libras) son unidades distintas: conserva las mayúsculas.
        if self.asset_type == "unknown":
            kinds = {"EQUITY": "stock", "INDEX": "index", "ETF": "etf", "MUTUALFUND": "fund"}
            kinds.update({"Common Stock": "stock", "Mutual Fund": "fund"})
            kind = self.history.info.get("quoteType") or self.history.info.get("AssetType", "")
            self.asset_type = kinds.get(str(kind), "unknown")

    @property
    def symbol(self) -> str:
        return self.history.symbol

    @property
    def name(self) -> str:
        return self.history.info.get("longName") or self.history.info.get("Name") or self.symbol

    @property
    def latest_price(self) -> float:
        return float(self.history.closing_prices().iloc[-1])

    def monte_carlo(
        self,
        steps: int = 252,
        simulations: int = 1000,
        seed: int | None = None,
        expected_return: float | None = None,
        volatility: float | None = None,
        periods_per_year: int = 252,
        price_column: str = "Close",
        confidence: float = 0.95,
    ) -> SimulationResult:
        """Simula el valor de una unidad desde su último precio Close."""
        prices = self.history.closing_prices(price_column).to_frame()
        expected_returns = {}
        volatilities = {}
        if expected_return is not None:
            expected_returns[self.symbol] = expected_return
        if volatility is not None:
            volatilities[self.symbol] = volatility
        initial = pd.Series({self.symbol: self.latest_price})
        return simulate_paths(
            prices,
            initial,
            self.currency,
            steps=steps,
            simulations=simulations,
            seed=seed,
            expected_returns=expected_returns,
            volatilities=volatilities,
            periods_per_year=periods_per_year,
            price_column=price_column,
            confidence=confidence,
        )
