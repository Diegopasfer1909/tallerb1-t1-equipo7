"""Descarga los precios antes de crear los activos y la cartera."""

from .commissions import RebalanceRule
from .constants import DEFAULT_CAPITAL, MONTHLY, Rebalance
from .errors import PortfolioError
from .market_loader import load_fx_rates
from .models import Asset, FxRates, Portfolio
from .ports import PriceProvider
from .price_loader import load_price_histories
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
    rebalance_rule: RebalanceRule | None = None,
    *,
    max_workers: int = 1,
) -> Portfolio:
    """Descarga los activos de una asignación como {"IBM": 0.6, "MSFT": 0.4}.

    Valida los pesos antes de consultar el proveedor para no gastar peticiones. currency
    indica la divisa de los activos si el proveedor no la publica; con reporting_currency y
    sin fx_rates, los cambios necesarios se descargan con fx_provider.
    rebalance_rule fija las comisiones y cuándo compensa reajustar; por defecto, sin costes.
    max_workers (1 a 4) permite descargar varios activos a la vez si el proveedor lo admite;
    el resultado es el mismo que con una sola descarga.
    """
    validate_symbols(target_weights)
    validate_weights(list(target_weights.values()))
    assets, fx_rates = _load_assets(
        target_weights,
        provider,
        start,
        end,
        currency,
        reporting_currency,
        fx_rates,
        fx_provider,
        max_workers,
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
        rebalance_rule=rebalance_rule or RebalanceRule(),
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
    rebalance: Rebalance = None,
    rebalance_rule: RebalanceRule | None = None,
    *,
    max_workers: int = 1,
) -> Portfolio:
    """Descarga los activos de una cartera como {"AAPL": 10, "SPY": 5} (número de acciones).

    Los pesos resultan de los importes de esas acciones en la primera fecha. Sin rebalanceo,
    las cantidades se mantienen durante todo el historial y el valor final es el número de
    acciones por el último precio; con rebalance="monthly", cada mes se vuelve a esos pesos. Se
    admiten fracciones de acciones. Las demás opciones funcionan como en load_portfolio().
    Los cierres deben estar ajustados por splits, como los de Yahoo Finance.
    """
    validate_symbols(shares)
    validate_units(list(shares.values()))
    assets, fx_rates = _load_assets(
        shares,
        provider,
        start,
        end,
        currency,
        reporting_currency,
        fx_rates,
        fx_provider,
        max_workers,
    )
    unadjusted = [asset.symbol for asset in assets if asset.history.price_basis == "unadjusted"]
    if unadjusted:
        raise PortfolioError(
            f"Cierres sin ajustar por splits ({', '.join(unadjusted)}): con un número de acciones "
            "fijo, un split dentro del período falsearía el valor. Usa Yahoo Finance."
        )
    units = {asset.symbol: amount for asset, amount in zip(assets, shares.values(), strict=True)}
    return Portfolio.from_units(
        assets, units, reporting_currency, fx_rates, rebalance, rebalance_rule
    )


def _load_assets(
    symbols,
    provider: PriceProvider,
    start: str,
    end: str,
    currency: str,
    reporting_currency: str,
    fx_rates: FxRates | None,
    fx_provider: PriceProvider | None,
    max_workers: int,
) -> tuple[list[Asset], FxRates]:
    """Descarga los símbolos en lote y, después, los tipos de cambio que hagan falta.

    Los activos se crean aquí, en el orden de entrada, cuando ya han llegado todos los
    historiales; los cambios dependen de las divisas de esos activos.
    """
    histories = load_price_histories(symbols, provider, start, end, max_workers=max_workers)
    assets = [Asset(history, currency=currency) for history in histories]
    if fx_rates is None:
        fx_rates = FxRates()
        if reporting_currency:
            fx_rates = load_fx_rates(assets, reporting_currency, start, end, fx_provider)
    return assets, fx_rates
