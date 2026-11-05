"""Descarga los precios antes de crear los activos y la cartera."""

from .constants import DEFAULT_CAPITAL, MONTHLY, Rebalance
from .errors import PortfolioError
from .market_loader import load_fx_rates
from .models import Asset, FxRates, Portfolio
from .providers import PriceProvider
from .validation import validate_symbols, validate_units, validate_weights


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
    assets, fx_rates = _load_assets(
        target_weights, provider, start, end, currency, reporting_currency, fx_rates, fx_provider
    )
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


def load_portfolio_from_shares(
    shares: dict[str, float],
    provider: PriceProvider,
    start: str,
    end: str,
    currency: str = "",
    reporting_currency: str = "",
    fx_rates: FxRates | None = None,
    fx_provider: PriceProvider | None = None,
) -> Portfolio:
    """Descarga los activos de una cartera como {"AAPL": 10, "SPY": 5} (número de acciones).

    Las cantidades se mantienen durante todo el historial, sin rebalanceo: el valor final es
    el número de acciones por el último precio, y los pesos resultan de esos importes. Se
    admiten fracciones de acciones. Las demás opciones funcionan como en load_portfolio().
    Los cierres deben estar ajustados por splits, como los de Yahoo Finance.
    """
    validate_symbols(shares)
    validate_units(list(shares.values()))
    assets, fx_rates = _load_assets(
        shares, provider, start, end, currency, reporting_currency, fx_rates, fx_provider
    )
    unadjusted = [asset.symbol for asset in assets if asset.history.price_basis == "unadjusted"]
    if unadjusted:
        raise PortfolioError(
            f"Cierres sin ajustar por splits ({', '.join(unadjusted)}): con un número de acciones "
            "fijo, un split dentro del período falsearía el valor. Usa Yahoo Finance."
        )
    units = {asset.symbol: amount for asset, amount in zip(assets, shares.values(), strict=True)}
    return Portfolio.from_units(assets, units, reporting_currency, fx_rates)


def _load_assets(
    symbols,
    provider: PriceProvider,
    start: str,
    end: str,
    currency: str,
    reporting_currency: str,
    fx_rates: FxRates | None,
    fx_provider: PriceProvider | None,
) -> tuple[list[Asset], FxRates]:
    """Descarga cada símbolo en lote y, si hace falta, los tipos de cambio."""
    assets = [
        Asset(provider.get_prices(symbol.strip(), start, end), currency=currency)
        for symbol in symbols
    ]
    if fx_rates is None:
        fx_rates = FxRates()
        if reporting_currency:
            fx_rates = load_fx_rates(assets, reporting_currency, start, end, fx_provider)
    return assets, fx_rates
