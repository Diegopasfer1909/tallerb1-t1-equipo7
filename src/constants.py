"""Valores por defecto y nombres compartidos por los modelos, el análisis y los informes."""

from typing import Literal

PERIODS_PER_YEAR = 252
DEFAULT_CAPITAL = 10_000
DEFAULT_SEED = 42

CLOSE = "Close"
ADJ_CLOSE = "Adj Close"
PRICE_COLUMNS = (CLOSE, ADJ_CLOSE)

MONTHLY = "monthly"
# Sesiones bursátiles con las que la simulación aproxima un mes.
SESSIONS_PER_MONTH = 21

# Sector o país que el proveedor no publica.
UNKNOWN = "Unknown"

# Antigüedad máxima de un dato para utilizarlo en una fecha posterior.
FX_MAX_AGE_DAYS = 7
DAILY_REFERENCE_MAX_AGE_DAYS = 45
MONTHLY_REFERENCE_MAX_AGE_DAYS = 75

PriceColumn = Literal["Close", "Adj Close"]
Rebalance = Literal["monthly"] | None
AssetType = Literal["stock", "index", "etf", "fund", "unknown"]
PriceBasis = Literal["unadjusted", "split_adjusted", "adjusted", "unknown"]

ASSET_TYPES: tuple[AssetType, ...] = ("stock", "index", "etf", "fund", "unknown")
PRICE_BASES: tuple[PriceBasis, ...] = ("unadjusted", "split_adjusted", "adjusted", "unknown")
