"""Descarga los precios antes de crear los activos y la cartera."""

from .constants import DEFAULT_CAPITAL, MONTHLY, Rebalance
from .market_loader import load_fx_rates
from .models import Asset, FxRates, Portfolio
from .providers import PriceProvider
from .validation import validate_symbols, validate_weights


def load_portfolio(
    target_weights: dict[str, float],
    provider: PriceProvider,
    start: str,
    end: str,
    currency: str = "",
    reporting_currency: str = "",
    fx_rates: FxRates | None = None,
    initial_capital: float = DEFAULT_CAPITAL,
    rebalance: Rebalance = MONTHLY,
    fx_provider: PriceProvider | None = None,
) -> Portfolio:
    """Descarga los activos de una asignación como {"IBM": 0.6, "MSFT": 0.4}.

    Valida los pesos antes de consultar el proveedor para no gastar peticiones. currency
    indica la divisa de los activos si el proveedor no la publica; con reporting_currency y
    sin fx_rates, los cambios necesarios se descargan con fx_provider (Yahoo por defecto).
    """
    validate_symbols(target_weights)
    validate_weights(list(target_weights.values()))
    assets = [
        Asset(provider.get_prices(symbol.strip(), start, end), currency=currency)
        for symbol in target_weights
    ]
    if fx_rates is None:
        fx_rates = FxRates()
        if reporting_currency:
            fx_rates = load_fx_rates(assets, reporting_currency, start, end, fx_provider)
    weights = {
        asset.symbol: weight for asset, weight in zip(assets, target_weights.values(), strict=True)
    }
    return Portfolio(
        assets,
        weights,
        reporting_currency,
        fx_rates,
        initial_capital=initial_capital,
        rebalance=rebalance,
    )
