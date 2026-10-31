"""Un activo y su historial, independiente de su peso en una cartera."""

from dataclasses import dataclass

import pandas as pd

from ..constants import ASSET_TYPES, CLOSE, PERIODS_PER_YEAR, AssetType, PriceColumn
from ..errors import PortfolioError
from ..simulation import SimulationInputs, SimulationResult, SimulationSettings, simulate
from .price_history import PriceHistory


@dataclass(frozen=True)
class Asset:
    """currency y asset_type completan o confirman los datos de la ficha del proveedor."""

    history: PriceHistory
    currency: str = ""
    asset_type: AssetType = "unknown"

    def __post_init__(self) -> None:
        if not isinstance(self.history, PriceHistory):
            raise TypeError("El activo necesita un objeto PriceHistory.")
        if not isinstance(self.history.symbol, str) or not self.history.symbol.strip():
            raise PortfolioError("El activo necesita un símbolo.")
        if self.history.price_basis == "adjusted":
            raise PortfolioError(
                "La valoración necesita Close sin ajuste por dividendos. Descarga con "
                "adjusted=False; utiliza Adj Close para las rentabilidades."
            )
        object.__setattr__(self, "currency", self._resolve_currency())
        if self.asset_type == "unknown":
            object.__setattr__(self, "asset_type", self.history.profile.asset_type)
        if self.asset_type not in ASSET_TYPES:
            raise PortfolioError(f"El tipo de activo debe ser uno de {', '.join(ASSET_TYPES)}.")

    def _resolve_currency(self) -> str:
        """La divisa indicada debe coincidir con la publicada; nunca se supone ninguna."""
        if not isinstance(self.currency, str):
            raise TypeError("La divisa debe indicarse como texto, por ejemplo USD.")
        given = self.currency.strip()
        reported = (self.history.profile.currency or "").strip()
        if given and reported and given != reported:
            raise PortfolioError(
                f"{self.symbol} cotiza en {reported}; la divisa indicada es {given}."
            )
        # GBp (peniques) y GBP (libras) son unidades distintas: conserva las mayúsculas.
        currency = given or reported
        if not currency:
            raise PortfolioError(f"Falta la divisa de {self.symbol}. Indícala expresamente.")
        return currency

    @property
    def symbol(self) -> str:
        return self.history.symbol

    @property
    def name(self) -> str:
        return self.history.profile.name or self.symbol

    @property
    def latest_price(self) -> float:
        return float(self.history.closing_prices().iloc[-1])

    def simulation_inputs(self, price_column: PriceColumn = CLOSE) -> SimulationInputs:
        """Simula el valor de una unidad desde su último precio Close."""
        return SimulationInputs(
            prices=self.history.closing_prices(price_column).to_frame(),
            starting_values=pd.Series({self.symbol: self.latest_price}),
            currency=self.currency,
            price_column=price_column,
        )

    def monte_carlo(
        self,
        settings: SimulationSettings | None = None,
        *,
        periods_per_year: int = PERIODS_PER_YEAR,
        price_column: PriceColumn = CLOSE,
        **options,
    ) -> SimulationResult:
        """Simula una unidad del activo; options admite los campos de SimulationSettings."""
        return simulate(
            self.simulation_inputs(price_column),
            SimulationSettings.from_options(settings, **options),
            periods_per_year,
        )
