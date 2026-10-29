"""Descarga los precios antes de crear los activos y la cartera."""

from .market_loader import load_currency_context
from .models.asset import Asset
from .models.market_context import MarketContext
from .models.portfolio import Portfolio
from .models.validation import validate_weights
from .providers import AlphaVantageAPI, YahooFinanceAPI


def load_portfolio(
    weights: dict[str, float],
    provider: YahooFinanceAPI | AlphaVantageAPI,
    start: str,
    end: str,
    currency: str = "",
    allow_partial: bool = False,
    outputsize: str = "compact",
    include_info: bool = False,
    reporting_currency: str = "",
    market_context: MarketContext | None = None,
    initial_capital: float = 10_000,
    rebalance: str | None = "monthly",
) -> Portfolio:
    """Descarga los activos de una asignación como {"IBM": 0.6, "MSFT": 0.4}."""
    validate_weights(list(weights.values()))
    symbols = set()
    for symbol in weights:
        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("Los símbolos de los activos deben ser cadenas de texto no vacías.")
        normalized = symbol.strip().lower()
        if normalized in symbols:
            raise ValueError(f"Activo repetido: {symbol}.")
        symbols.add(normalized)

    assets = []
    for symbol in weights:
        symbol = symbol.strip()
        if isinstance(provider, AlphaVantageAPI):
            history = provider.get_prices(
                symbol,
                start,
                end,
                allow_partial=allow_partial,
                outputsize=outputsize,
                include_info=include_info,
            )
        else:
            history = provider.get_prices(symbol, start, end, adjusted=False)
        assets.append(Asset(history, currency=currency))
    if reporting_currency and market_context is None:
        market_context = load_currency_context(assets, reporting_currency, start, end)
    return Portfolio(
        assets,
        list(weights.values()),
        reporting_currency,
        market_context,
        initial_capital=initial_capital,
        rebalance=rebalance,
    )
