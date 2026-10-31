"""Descarga los precios antes de crear los activos y la cartera."""

from pathlib import Path

from .market_loader import load_currency_context
from .models.asset import Asset
from .models.market_context import MarketContext
from .models.portfolio import Portfolio
from .providers.base import PriceProvider
from .validation import validate_symbols, validate_weights


def load_portfolio(
    weights: dict[str, float],
    provider: PriceProvider,
    start: str,
    end: str,
    currency: str = "",
    reporting_currency: str = "",
    market_context: MarketContext | None = None,
    initial_capital: float = 10_000,
    rebalance: str | None = "monthly",
    cache_dir: Path | None = None,
) -> Portfolio:
    """Descarga los activos de una asignación como {"IBM": 0.6, "MSFT": 0.4}.

    Valida los pesos antes de consultar el proveedor para no gastar peticiones.
    cache_dir permite reutilizar los tipos de cambio ya descargados.
    """
    validate_symbols(weights)
    validate_weights(list(weights.values()))
    assets = []
    for symbol in weights:
        history = provider.get_prices(symbol.strip(), start, end)
        assets.append(Asset(history, currency=currency))
    if reporting_currency and market_context is None:
        market_context = load_currency_context(
            assets, reporting_currency, start, end, cache_dir=cache_dir
        )
    return Portfolio(
        assets,
        list(weights.values()),
        reporting_currency,
        market_context,
        initial_capital=initial_capital,
        rebalance=rebalance,
    )
