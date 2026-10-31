"""Datos de prueba compartidos: historiales, activos, indicadores y carteras sin descargas."""

import pandas as pd

from src.models import Asset, AssetProfile, EconomicIndicator, Portfolio, PriceHistory


def history(
    symbol,
    closes,
    currency="USD",
    dates=None,
    *,
    start="2026-01-01",
    extra=None,
    price_basis="unadjusted",
    partial_history=False,
    **profile,
) -> PriceHistory:
    """Historial diario con Close y columnas extra; profile completa la ficha del activo."""
    if dates is None:
        dates = pd.date_range(start, periods=len(closes))
    prices = pd.DataFrame({"Close": closes}, index=dates)
    for column, values in (extra or {}).items():
        prices[column] = values
    return PriceHistory(
        symbol,
        "test",
        prices,
        profile=AssetProfile(currency=currency or None, **profile),
        price_basis=price_basis,
        partial_history=partial_history,
    )


def asset(symbol, closes, currency="USD", **options) -> Asset:
    return Asset(history(symbol, closes, currency, **options))


def indicator(values, dates, units="Percent", name="TEST", frequency="Daily") -> EconomicIndicator:
    return EconomicIndicator(
        name, "test", pd.Series(values, index=dates, dtype=float), units, frequency
    )


def buy_and_hold(assets, units, reporting_currency="", fx_rates=None) -> Portfolio:
    """Cartera sin rebalanceo con las cantidades indicadas, en el orden de los activos."""
    quantities = {item.symbol: quantity for item, quantity in zip(assets, units, strict=True)}
    return Portfolio.from_units(assets, quantities, reporting_currency, fx_rates)
