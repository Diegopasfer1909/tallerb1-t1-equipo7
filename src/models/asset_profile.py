"""Ficha común de un activo, traducida por cada adaptador desde la respuesta del proveedor."""

import math
from dataclasses import dataclass, field

from ..constants import ASSET_TYPES, AssetType
from ..errors import PortfolioError


@dataclass(frozen=True)
class AssetProfile:
    """Los textos ausentes quedan como None y las cifras ausentes como NaN.

    raw conserva la respuesta original del proveedor; issue explica por qué no se pudo
    consultar la ficha, en cuyo caso la divisa debe indicarse expresamente.
    """

    currency: str | None = None
    name: str | None = None
    asset_type: AssetType = "unknown"
    sector: str | None = None
    country: str | None = None
    beta: float = math.nan
    market_cap: float = math.nan
    pe_ratio: float = math.nan
    raw: dict = field(default_factory=dict)
    issue: str | None = None

    def __post_init__(self) -> None:
        if self.asset_type not in ASSET_TYPES:
            raise PortfolioError(f"El tipo de activo debe ser uno de {', '.join(ASSET_TYPES)}.")
