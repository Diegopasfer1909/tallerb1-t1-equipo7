"""Descargas de referencias económicas y tipos de cambio para la cartera."""

from datetime import date, timedelta
from pathlib import Path

from .models.asset import Asset
from .models.economic_indicator import EconomicIndicator
from .models.market_context import MINOR_UNITS, ExchangeRate, MarketContext
from .providers import FredAPI, ProviderError, YahooFinanceAPI

# Referencias iniciales que el usuario puede cambiar expresamente.
REPORT_DEFAULTS = {
    "USD": {
        "benchmark_symbol": "^GSPC",
        "inflation_series": "CPIAUCSL",
        "risk_free_series": "DGS3MO",
    },
    "EUR": {
        "benchmark_symbol": "^STOXX50E",
        "inflation_series": "CP0000EZ19M086NEST",
        "risk_free_series": "ECBESTRVOLWGTTRMDMNRT",
    },
}


def load_currency_context(assets: list[Asset], target: str, start: str, end: str) -> MarketContext:
    """Obtiene los cambios directos necesarios sin pedir al usuario símbolos de divisas."""
    provider = YahooFinanceAPI()
    currencies = {MINOR_UNITS.get(asset.currency, asset.currency) for asset in assets}
    earlier = (date.fromisoformat(start) - timedelta(days=7)).isoformat()
    rates = []
    for source in sorted(currencies):
        if source == target:
            continue
        symbol = f"{source}{target}=X"
        history = provider.get_prices(symbol, earlier, end, adjusted=False)
        indicator = EconomicIndicator(
            symbol, "yahoo", history.closing_prices(), f"{target} por {source}", "Daily"
        )
        rates.append(ExchangeRate(source, target, indicator))
    return MarketContext(exchange_rates=rates)


def load_market_context(
    start: str,
    end: str,
    price_provider: YahooFinanceAPI | None = None,
    fred_provider: FredAPI | None = None,
    benchmark_symbol: str | None = None,
    inflation_series: str | None = None,
    risk_free_series: str | None = None,
    exchange_rate_series: dict[tuple[str, str], str] | None = None,
    cache_dir: Path | None = None,
    cache_ttl: float = 86400,
) -> MarketContext:
    """Registra fallos de referencias opcionales y exige los cambios solicitados.

    El par declara las unidades: {("EUR", "USD"): "DEXUSEU"} indica dólares por euro.
    La inflación requiere un índice de precios; el tipo de referencia, un porcentaje anual.
    Consultar solo un índice bursátil no requiere una clave FRED.
    """
    context = MarketContext()
    if benchmark_symbol:
        provider = price_provider or YahooFinanceAPI()
        try:
            context.benchmark = provider.get_prices(benchmark_symbol, start, end, adjusted=False)
        except (ProviderError, ValueError):
            context.issues.append(
                f"No se ha podido descargar el índice de referencia {benchmark_symbol}."
            )

    if not (inflation_series or risk_free_series or exchange_rate_series):
        return context
    try:
        fred = fred_provider or FredAPI(cache_dir=cache_dir, cache_ttl=cache_ttl)
    except ValueError:
        if exchange_rate_series:
            raise
        context.issues.append(
            "No se han descargado los datos económicos: configura FRED_API_KEY en el archivo .env del proyecto."
        )
        return context
    # Incluye datos anteriores para alinear el inicio sin utilizar observaciones futuras.
    earlier = (date.fromisoformat(start) - timedelta(days=75)).isoformat()
    if inflation_series:
        context.inflation = _optional_series(
            fred, inflation_series, earlier, end, context, "inflación"
        )
    if risk_free_series:
        context.risk_free_rate = _optional_series(
            fred, risk_free_series, earlier, end, context, "tipo de interés de referencia"
        )
    for (base, quote), series_id in (exchange_rate_series or {}).items():
        indicator = fred.get_series(series_id, earlier, end)
        context.exchange_rates.append(ExchangeRate(base, quote, indicator))
    return MarketContext(
        benchmark=context.benchmark,
        inflation=context.inflation,
        risk_free_rate=context.risk_free_rate,
        exchange_rates=context.exchange_rates,
        issues=context.issues,
    )


def _optional_series(fred, series_id, start, end, context, label):
    """Registra el fallo de una referencia opcional en lugar de detener el informe."""
    try:
        return fred.get_series(series_id, start, end)
    except (ProviderError, ValueError):
        context.issues.append(f"No se ha podido descargar la serie de {label} ({series_id}).")
        return None


def load_report_context(
    portfolio,
    start: str,
    end: str,
    benchmark_symbol: str | None = None,
    inflation_series: str | None = None,
    risk_free_series: str | None = None,
    cache_dir: Path | None = None,
    cache_ttl: float = 86400,
) -> MarketContext:
    """Carga las referencias una vez conocida la divisa del informe."""
    defaults = REPORT_DEFAULTS.get(portfolio.currency, {})
    context = load_market_context(
        start,
        end,
        benchmark_symbol=benchmark_symbol or defaults.get("benchmark_symbol"),
        inflation_series=inflation_series or defaults.get("inflation_series"),
        risk_free_series=risk_free_series or defaults.get("risk_free_series"),
        cache_dir=cache_dir,
        cache_ttl=cache_ttl,
    )
    if portfolio.market_context is not None:
        context.exchange_rates = list(portfolio.market_context.exchange_rates)
        context.issues.extend(portfolio.market_context.issues)
    if defaults:
        context.issues.append(
            "Las referencias se han elegido según la divisa del informe. Comprueba si se ajustan al mercado y a la zona geográfica que quieres analizar."
        )
    else:
        context.issues.append(
            f"No hay referencias económicas predeterminadas para {portfolio.currency}. Las medidas que necesitan esas referencias quedan sin calcular."
        )
    return context
