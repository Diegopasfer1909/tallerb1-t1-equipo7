"""Descargas de tipos de cambio y referencias económicas para la cartera."""

from datetime import date, timedelta
from pathlib import Path

from .constants import FX_MAX_AGE_DAYS, MONTHLY_REFERENCE_MAX_AGE_DAYS
from .errors import ConfigurationError, PortfolioError
from .models import Asset, EconomicIndicator, ExchangeRate, FxRates, MarketReferences, Notice
from .models.currency import MINOR_UNITS
from .providers import FRED_KEY, FredAPI, PriceProvider, ProviderError, YahooFinanceAPI

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


def _days_before(day: str, days: int) -> str:
    """Incluye datos anteriores para alinear el inicio sin utilizar observaciones futuras."""
    return (date.fromisoformat(day) - timedelta(days=days)).isoformat()


def load_fx_rates(
    assets: list[Asset],
    target: str,
    start: str,
    end: str,
    provider: PriceProvider | None = None,
) -> FxRates:
    """Obtiene los cambios directos necesarios sin pedir al usuario símbolos de divisas.

    Por defecto consulta pares como USDEUR=X en Yahoo Finance.
    """
    # De un tipo de cambio solo se usan los precios; la ficha costaría otra petición.
    provider = provider or YahooFinanceAPI(include_info=False)
    currencies = {MINOR_UNITS.get(asset.currency, asset.currency) for asset in assets}
    earlier = _days_before(start, FX_MAX_AGE_DAYS)
    rates = []
    for source in sorted(currencies - {target}):
        symbol = f"{source}{target}=X"
        history = provider.get_prices(symbol, earlier, end, adjusted=False)
        indicator = EconomicIndicator(
            symbol, history.source, history.closing_prices(), f"{target} por {source}", "Daily"
        )
        rates.append(ExchangeRate(source, target, indicator))
    return FxRates(rates)


def load_fred_fx_rates(
    series: dict[tuple[str, str], str],
    start: str,
    end: str,
    fred_provider: FredAPI | None = None,
    cache_dir: Path | None = None,
    cache_ttl: float = 86400,
) -> FxRates:
    """Cambios publicados en FRED; a diferencia de las referencias, un fallo detiene la carga.

    El par declara las unidades: {("EUR", "USD"): "DEXUSEU"} indica dólares por euro.
    """
    fred = fred_provider or FredAPI(cache_dir=cache_dir, cache_ttl=cache_ttl)
    earlier = _days_before(start, MONTHLY_REFERENCE_MAX_AGE_DAYS)
    return FxRates(
        [
            ExchangeRate(base, quote, fred.get_series(series_id, earlier, end))
            for (base, quote), series_id in series.items()
        ]
    )


def load_market_references(
    start: str,
    end: str,
    price_provider: PriceProvider | None = None,
    fred_provider: FredAPI | None = None,
    benchmark_symbol: str | None = None,
    inflation_series: str | None = None,
    risk_free_series: str | None = None,
    cache_dir: Path | None = None,
    cache_ttl: float = 86400,
) -> MarketReferences:
    """Descarga las referencias opcionales y registra sus fallos sin detener el informe.

    La inflación requiere un índice de precios; el tipo de referencia, un porcentaje anual.
    La inflación y el tipo de interés se toman de FRED. Consultar solo un índice bursátil
    no requiere clave.
    """
    notices = []

    def attempt(failure: str, download, *args):
        try:
            return download(*args)
        except (ProviderError, PortfolioError) as error:
            notices.append(Notice(f"{failure} Motivo: {error}"))
            return None

    benchmark = inflation = risk_free_rate = None
    if benchmark_symbol:
        provider = price_provider or YahooFinanceAPI(cache_dir=cache_dir, cache_ttl=cache_ttl)
        benchmark = attempt(
            f"No se ha podido descargar el índice de referencia {benchmark_symbol}.",
            provider.get_prices,
            benchmark_symbol,
            start,
            end,
        )
    if inflation_series or risk_free_series:
        try:
            fred = fred_provider or FredAPI(cache_dir=cache_dir, cache_ttl=cache_ttl)
        except ConfigurationError:
            notices.append(
                Notice(
                    "No se han descargado la inflación ni el tipo de interés porque falta "
                    f"{FRED_KEY}. Configúrala en el archivo .env o en el entorno para calcular "
                    "la rentabilidad real y las ratios de Sharpe y Sortino."
                )
            )
        else:
            earlier = _days_before(start, MONTHLY_REFERENCE_MAX_AGE_DAYS)
            if inflation_series:
                inflation = attempt(
                    f"No se ha podido descargar la serie de inflación ({inflation_series}).",
                    fred.get_series,
                    inflation_series,
                    earlier,
                    end,
                )
            if risk_free_series:
                risk_free_rate = attempt(
                    "No se ha podido descargar la serie de tipo de interés de referencia "
                    f"({risk_free_series}).",
                    fred.get_series,
                    risk_free_series,
                    earlier,
                    end,
                )
    return MarketReferences(benchmark, inflation, risk_free_rate, notices)


def load_references(
    currency: str,
    start: str,
    end: str,
    benchmark_symbol: str | None = None,
    inflation_series: str | None = None,
    risk_free_series: str | None = None,
    cache_dir: Path | None = None,
    cache_ttl: float = 86400,
) -> MarketReferences:
    """Elige las referencias predeterminadas de la divisa del informe; se pueden cambiar."""
    defaults = REPORT_DEFAULTS.get(currency, {})
    references = load_market_references(
        start,
        end,
        benchmark_symbol=benchmark_symbol or defaults.get("benchmark_symbol"),
        inflation_series=inflation_series or defaults.get("inflation_series"),
        risk_free_series=risk_free_series or defaults.get("risk_free_series"),
        cache_dir=cache_dir,
        cache_ttl=cache_ttl,
    )
    if defaults:
        note = Notice(
            "Las referencias se han elegido según la divisa del informe. Comprueba si se ajustan "
            "al mercado y a la zona geográfica que quieres analizar.",
            kind="method",
        )
    else:
        note = Notice(
            f"No hay referencias económicas predeterminadas para {currency}. Las medidas que "
            "necesitan esas referencias quedan sin calcular."
        )
    return MarketReferences(
        references.benchmark,
        references.inflation,
        references.risk_free_rate,
        (*references.notices, note),
    )
