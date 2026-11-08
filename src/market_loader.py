"""Descargas de tipos de cambio y referencias económicas para la cartera."""

from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

from .constants import (
    DAILY_REFERENCE_MAX_AGE_DAYS,
    FX_MAX_AGE_DAYS,
    MONTHLY_REFERENCE_MAX_AGE_DAYS,
)
from .errors import ConfigurationError, PortfolioError
from .models import Asset, EconomicIndicator, ExchangeRate, FxRates, MarketReferences, Notice
from .models.currency import MINOR_UNITS
from .providers import (
    AAA_3M_YIELD,
    EcbAPI,
    FredAPI,
    PriceProvider,
    ProviderError,
    YahooFinanceAPI,
    is_ecb_series,
)

# Referencias iniciales que el usuario puede cambiar expresamente, por ejemplo con --benchmark.
# Se usan ETF porque sus precios ajustados incluyen dividendos, como los de la cartera; los
# índices habituales (^GSPC, ^STOXX50E) no los incluyen e inflarían la ventaja frente a ellos.
REPORT_DEFAULTS = {
    "USD": {
        "benchmark_symbol": "SPY",
        "inflation_series": "CPIAUCSL",
        "risk_free_series": "DGS3MO",
    },
    "EUR": {
        "benchmark_symbol": "EXW1.DE",
        "inflation_series": "CP0000EZ19M086NEST",
        "risk_free_series": AAA_3M_YIELD,
    },
}

# Contexto de mercado del informe: campo de MarketReferences, nombre y serie.
MARKET_SERIES = {
    "vix": ("VIX", "VIXCLS"),
    "brent": ("Brent", "DCOILBRENTEU"),
}
MARKET_PRICES = {
    "gold": ("Oro", "GC=F"),
    "bund_etf": ("ETF de Bunds", "EXHD.DE"),
}

NO_FRED_KEY = (
    "No se han descargado las series de FRED (inflación, VIX, Brent y tipo de interés en USD) "
    "porque falta la clave de FRED. El README explica cómo configurarla."
)


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


def _fred_or_notice(
    provider: FredAPI | None, notices: list[Notice], cache_dir: Path | None, cache_ttl: float
) -> FredAPI | None:
    """Sin clave, las series de FRED quedan sin calcular y el informe explica el motivo."""
    try:
        return provider or FredAPI(cache_dir=cache_dir, cache_ttl=cache_ttl)
    except ConfigurationError:
        notices.append(Notice(NO_FRED_KEY))
        return None


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
    ecb_provider: EcbAPI | None = None,
) -> MarketReferences:
    """Descarga las referencias opcionales y registra sus fallos sin detener el informe.

    El índice se consulta en Yahoo Finance y no requiere clave. La inflación (un índice de
    precios) y el tipo de interés (un porcentaje anual) se toman de FRED, que la requiere, o, si
    el identificador es del BCE, de este, que no. Con currency, la divisa de la cartera, se
    descarga también el cambio que necesite un índice cotizado en otra divisa.
    """
    notices = []

    def attempt(failure: str, download, *args):
        """Una referencia que falla se registra como aviso y queda sin calcular."""
        try:
            return download(*args)
        except (ProviderError, PortfolioError) as error:
            notices.append(Notice(f"{failure} Motivo: {error}"))
            return None

    benchmark = inflation = risk_free_rate = None
    fx_rates = FxRates()
    if benchmark_symbol:
        yahoo = price_provider or YahooFinanceAPI(cache_dir=cache_dir, cache_ttl=cache_ttl)
        benchmark = attempt(
            f"No se ha podido descargar el índice de referencia {benchmark_symbol}.",
            yahoo.get_prices,
            benchmark_symbol,
            start,
            end,
        )
        quoted = benchmark.profile.currency if benchmark is not None else None
        if currency and quoted:
            # _fx_rates no descarga nada si el índice ya cotiza en la divisa de la cartera.
            fx_provider = price_provider or YahooFinanceAPI(
                cache_dir=cache_dir, cache_ttl=cache_ttl, include_info=False
            )
            fx_rates = (
                attempt(
                    f"No se ha podido descargar el tipo de cambio {quoted}/{currency} para comparar "
                    f"la cartera con {benchmark_symbol}.",
                    _fx_rates,
                    {quoted},
                    currency,
                    start,
                    end,
                    fx_provider,
                )
                or FxRates()
            )

    fred = None
    if inflation_series or (risk_free_series and not is_ecb_series(risk_free_series)):
        fred = _fred_or_notice(fred_provider, notices, cache_dir, cache_ttl)
    earlier = _days_before(start, MONTHLY_REFERENCE_MAX_AGE_DAYS)
    if inflation_series and fred is not None:
        inflation = attempt(
            f"No se ha podido descargar la serie de inflación ({inflation_series}).",
            fred.get_series,
            inflation_series,
            earlier,
            end,
        )
    source = fred
    if risk_free_series and is_ecb_series(risk_free_series):
        source = ecb_provider or EcbAPI(cache_dir=cache_dir, cache_ttl=cache_ttl)
    if risk_free_series and source is not None:
        risk_free_rate = attempt(
            "No se ha podido descargar la serie de tipo de interés de referencia "
            f"({risk_free_series}).",
            source.get_series,
            risk_free_series,
            earlier,
            end,
        )
    return MarketReferences(benchmark, inflation, risk_free_rate, notices, fx_rates)


def load_risk_free_rate(
    currency: str,
    end: str,
    fred_provider: FredAPI | None = None,
    ecb_provider: EcbAPI | None = None,
    cache_dir: Path | None = None,
    cache_ttl: float = 86400,
) -> float | None:
    """Último tipo anual de la divisa antes de end, como fracción; None si no está disponible."""
    series = REPORT_DEFAULTS.get(currency, {}).get("risk_free_series")
    if series is None:
        return None
    try:
        if is_ecb_series(series):
            source = ecb_provider or EcbAPI(cache_dir=cache_dir, cache_ttl=cache_ttl)
        else:
            source = fred_provider or FredAPI(cache_dir=cache_dir, cache_ttl=cache_ttl)
        indicator = source.get_series(series, _days_before(end, DAILY_REFERENCE_MAX_AGE_DAYS), end)
    except (ConfigurationError, ProviderError, PortfolioError):
        return None
    return float(indicator.values.dropna().iloc[-1]) / 100


def load_market_context(
    start: str,
    end: str,
    price_provider: PriceProvider | None = None,
    fred_provider: FredAPI | None = None,
    cache_dir: Path | None = None,
    cache_ttl: float = 86400,
) -> tuple[dict, list[Notice]]:
    """VIX, Brent, oro y ETF de Bunds; un fallo solo deja sin calcular sus medidas."""
    context, notices = {}, []
    fred = _fred_or_notice(fred_provider, notices, cache_dir, cache_ttl)
    prices = price_provider or YahooFinanceAPI(
        cache_dir=cache_dir, cache_ttl=cache_ttl, include_info=False
    )
    earlier = _days_before(start, MONTHLY_REFERENCE_MAX_AGE_DAYS)
    downloads = [(key, *item, prices.get_prices, start) for key, item in MARKET_PRICES.items()]
    if fred is not None:
        downloads += [(key, *item, fred.get_series, earlier) for key, item in MARKET_SERIES.items()]
    for key, name, symbol, download, first in downloads:
        try:
            context[key] = download(symbol, first, end)
        except (ProviderError, PortfolioError) as error:
            notices.append(Notice(f"No se ha podido descargar {name} ({symbol}). Motivo: {error}"))
    return context, notices


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
    """Completa con las referencias predeterminadas de la divisa las que no se indiquen.

    benchmark_symbol sustituye al índice predeterminado; puede cotizar en otra divisa.
    """
    defaults = REPORT_DEFAULTS.get(currency, {})
    references = load_market_references(
        start,
        end,
        benchmark_symbol=benchmark_symbol or defaults.get("benchmark_symbol"),
        inflation_series=inflation_series or defaults.get("inflation_series"),
        risk_free_series=risk_free_series or defaults.get("risk_free_series"),
        cache_dir=cache_dir,
        cache_ttl=cache_ttl,
        currency=currency,
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
    if not defaults:
        notes.append(
            Notice(
                f"No hay referencias económicas predeterminadas para {currency}. Las medidas que "
                "necesitan las referencias no indicadas quedan sin calcular."
            )
        )
    elif not all((benchmark_symbol, inflation_series, risk_free_series)):
        notes.append(
            Notice(
                "Las referencias no indicadas se han elegido según la divisa del informe. "
                "Comprueba si se ajustan al mercado y a la zona geográfica que quieres analizar.",
                kind="method",
            )
        )
    context, context_notices = load_market_context(
        start, end, cache_dir=cache_dir, cache_ttl=cache_ttl
    )
    return replace(references, notices=(*references.notices, *context_notices, *notes), **context)
