"""Descargas de tipos de cambio y referencias económicas para la cartera."""

from datetime import date, timedelta
from pathlib import Path

from .constants import FX_MAX_AGE_DAYS, MONTHLY_REFERENCE_MAX_AGE_DAYS
from .errors import ConfigurationError, PortfolioError
from .models import Asset, EconomicIndicator, ExchangeRate, FxRates, MarketReferences, Notice
from .models.currency import MINOR_UNITS
from .providers import FRED_KEY, FredAPI, PriceProvider, ProviderError, YahooFinanceAPI

# Referencias iniciales que el usuario puede cambiar expresamente, por ejemplo con --benchmark.
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
    return _fx_rates({asset.currency for asset in assets}, target, start, end, provider)


def _fx_rates(
    currencies: set[str], target: str, start: str, end: str, provider: PriceProvider | None
) -> FxRates:
    """Descarga un cambio directo por cada divisa distinta de target; GBp cuenta como GBP."""
    # De un tipo de cambio solo se usan los precios; la ficha costaría otra petición.
    provider = provider or YahooFinanceAPI(include_info=False)
    currencies = {MINOR_UNITS.get(currency, currency) for currency in currencies}
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
    currency: str = "",
) -> MarketReferences:
    """Descarga las referencias opcionales y registra sus fallos sin detener el informe.

    La inflación requiere un índice de precios; el tipo de referencia, un porcentaje anual.
    La inflación y el tipo de interés se toman de FRED. Consultar solo un índice bursátil
    no requiere clave. Con currency, la divisa de la cartera, se descarga también el tipo de
    cambio que necesite un índice que cotice en otra divisa.
    """
    notices = []

    def attempt(failure: str, download, *args):
        try:
            return download(*args)
        except (ProviderError, PortfolioError) as error:
            notices.append(Notice(f"{failure} Motivo: {error}"))
            return None

    benchmark = inflation = risk_free_rate = None
    fx_rates = FxRates()
    if benchmark_symbol:
        provider = price_provider or YahooFinanceAPI(cache_dir=cache_dir, cache_ttl=cache_ttl)
        benchmark = attempt(
            f"No se ha podido descargar el índice de referencia {benchmark_symbol}.",
            provider.get_prices,
            benchmark_symbol,
            start,
            end,
        )
        quoted = benchmark.profile.currency if benchmark is not None else None
        if currency and quoted and MINOR_UNITS.get(quoted, quoted) != currency:
            fx_rates = (
                attempt(
                    f"No se ha podido descargar el tipo de cambio {quoted}/{currency} para comparar "
                    f"la cartera con {benchmark_symbol}.",
                    _fx_rates,
                    {quoted},
                    currency,
                    start,
                    end,
                    price_provider
                    or YahooFinanceAPI(
                        cache_dir=cache_dir, cache_ttl=cache_ttl, include_info=False
                    ),
                )
                or FxRates()
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
    return MarketReferences(benchmark, inflation, risk_free_rate, notices, fx_rates)


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
    """Elige las referencias predeterminadas de la divisa del informe; se pueden cambiar.

    benchmark_symbol sustituye al índice predeterminado; puede cotizar en otra divisa.
    """
    defaults = REPORT_DEFAULTS.get(currency, {})
    chosen = {
        "benchmark_symbol": benchmark_symbol,
        "inflation_series": inflation_series,
        "risk_free_series": risk_free_series,
    }
    references = load_market_references(
        start,
        end,
        cache_dir=cache_dir,
        cache_ttl=cache_ttl,
        currency=currency,
        **{name: value or defaults.get(name) for name, value in chosen.items()},
    )
    notes = []
    if benchmark_symbol:
        notes.append(
            Notice(
                f"Índice de referencia elegido por el usuario: {benchmark_symbol}. Si cotiza en "
                f"otra divisa, se convierte a {currency} para compararlo con la cartera.",
                kind="method",
            )
        )
    defaulted = [name for name, value in chosen.items() if not value and name in defaults]
    if defaulted:
        notes.append(
            Notice(
                "Las referencias no indicadas se han elegido según la divisa del informe. "
                "Comprueba si se ajustan al mercado y a la zona geográfica que quieres analizar.",
                kind="method",
            )
        )
    elif not defaults:
        notes.append(
            Notice(
                f"No hay referencias económicas predeterminadas para {currency}. Las medidas que "
                "necesitan las referencias no indicadas quedan sin calcular."
            )
        )
    return MarketReferences(
        references.benchmark,
        references.inflation,
        references.risk_free_rate,
        (*references.notices, *notes),
        references.fx_rates,
    )
