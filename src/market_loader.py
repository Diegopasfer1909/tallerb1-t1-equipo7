"""Descargas de tipos de cambio y referencias económicas para la cartera.

Las funciones reciben las fuentes por los puertos de ports y no crean adaptadores: main los
elige y los configura (caché, claves), de modo que este módulo no conoce Yahoo, FRED ni el BCE.
"""

from dataclasses import replace
from datetime import date, timedelta

from .constants import (
    AAA_3M_YIELD,
    DAILY_REFERENCE_MAX_AGE_DAYS,
    FX_MAX_AGE_DAYS,
    MONTHLY_REFERENCE_MAX_AGE_DAYS,
)
from .errors import ConfigurationError, PortfolioError, ProviderError
from .models import Asset, EconomicIndicator, ExchangeRate, FxRates, MarketReferences, Notice
from .models.currency import MINOR_UNITS
from .ports import IndicatorProvider, PriceProvider, ReferenceSources, is_ecb_series

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

DEFAULT_BENCHMARK_NOTE = (
    "Por defecto, la referencia es un ETF porque sus precios ajustados incluyen dividendos; "
    "los índices habituales no los incluyen y, frente a una cartera con dividendos, "
    "sobrestimarían su ventaja."
)

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
NO_ECB_SOURCE = "No se han descargado las series del BCE porque no se ha indicado su fuente."


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

    Consulta en provider pares con la forma de Yahoo Finance, como USDEUR=X. Solo hace falta
    provider si alguna divisa difiere de target.
    """
    return _fx_rates({asset.currency for asset in assets}, target, start, end, provider)


def _fx_rates(
    currencies: set[str], target: str, start: str, end: str, provider: PriceProvider | None
) -> FxRates:
    """Descarga un cambio directo por cada divisa distinta de target; GBp cuenta como GBP."""
    currencies = {MINOR_UNITS.get(currency, currency) for currency in currencies}
    missing = sorted(currencies - {target})
    if missing and provider is None:
        raise ConfigurationError(
            f"Para convertir {', '.join(missing)} a {target} hace falta un proveedor de tipos de "
            "cambio (fx_provider)."
        )
    earlier = _days_before(start, FX_MAX_AGE_DAYS)
    rates = []
    for source in missing:
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
    fred_provider: IndicatorProvider,
) -> FxRates:
    """Cambios publicados en FRED; a diferencia de las referencias, un fallo detiene la carga.

    El par declara las unidades: {("EUR", "USD"): "DEXUSEU"} indica dólares por euro.
    """
    earlier = _days_before(start, MONTHLY_REFERENCE_MAX_AGE_DAYS)
    return FxRates(
        [
            ExchangeRate(base, quote, fred_provider.get_series(series_id, earlier, end))
            for (base, quote), series_id in series.items()
        ]
    )


def _source_or_notice(
    sources: ReferenceSources, series_id: str, notices: list[Notice]
) -> IndicatorProvider | None:
    """Sin fuente, la serie queda sin calcular y el informe explica el motivo una sola vez."""
    source = sources.for_series(series_id)
    if source is None:
        notice = Notice(NO_ECB_SOURCE if is_ecb_series(series_id) else NO_FRED_KEY)
        if notice not in notices:
            notices.append(notice)
    return source


def load_market_references(
    start: str,
    end: str,
    sources: ReferenceSources,
    benchmark_symbol: str | None = None,
    inflation_series: str | None = None,
    risk_free_series: str | None = None,
    currency: str = "",
) -> MarketReferences:
    """Descarga las referencias opcionales y registra sus fallos sin detener el informe.

    El índice se consulta en sources.benchmark. La inflación (un índice de precios) y el tipo
    de interés (un porcentaje anual) se toman de FRED o, si el identificador es del BCE, de
    este. Con currency, la divisa de la cartera, se descarga también el cambio que necesite un
    índice cotizado en otra divisa.
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
        benchmark = attempt(
            f"No se ha podido descargar el índice de referencia {benchmark_symbol}.",
            sources.benchmark.get_prices,
            benchmark_symbol,
            start,
            end,
        )
        quoted = benchmark.profile.currency if benchmark is not None else None
        if currency and quoted:
            # _fx_rates no descarga nada si el índice ya cotiza en la divisa de la cartera.
            fx_rates = (
                attempt(
                    f"No se ha podido descargar el tipo de cambio {quoted}/{currency} para comparar "
                    f"la cartera con {benchmark_symbol}.",
                    _fx_rates,
                    {quoted},
                    currency,
                    start,
                    end,
                    sources.prices,
                )
                or FxRates()
            )

    earlier = _days_before(start, MONTHLY_REFERENCE_MAX_AGE_DAYS)
    source = _source_or_notice(sources, inflation_series, notices) if inflation_series else None
    if source is not None:
        inflation = attempt(
            f"No se ha podido descargar la serie de inflación ({inflation_series}).",
            source.get_series,
            inflation_series,
            earlier,
            end,
        )
    source = _source_or_notice(sources, risk_free_series, notices) if risk_free_series else None
    if source is not None:
        risk_free_rate = attempt(
            "No se ha podido descargar la serie de tipo de interés de referencia "
            f"({risk_free_series}).",
            source.get_series,
            risk_free_series,
            earlier,
            end,
        )
    return MarketReferences(benchmark, inflation, risk_free_rate, notices, fx_rates)


def load_risk_free_rate(currency: str, end: str, sources: ReferenceSources) -> float | None:
    """Último tipo anual de la divisa antes de end, como fracción; None si no está disponible."""
    series = REPORT_DEFAULTS.get(currency, {}).get("risk_free_series")
    source = sources.for_series(series) if series is not None else None
    if source is None:
        return None
    try:
        indicator = source.get_series(series, _days_before(end, DAILY_REFERENCE_MAX_AGE_DAYS), end)
    except (ProviderError, PortfolioError):
        return None
    return float(indicator.values.dropna().iloc[-1]) / 100


def load_market_context(
    start: str, end: str, sources: ReferenceSources
) -> tuple[dict, list[Notice]]:
    """VIX, Brent, oro y ETF de Bunds; un fallo solo deja sin calcular sus medidas."""
    context, notices = {}, []
    earlier = _days_before(start, MONTHLY_REFERENCE_MAX_AGE_DAYS)
    prices = sources.prices
    downloads = [(key, *item, prices.get_prices, start) for key, item in MARKET_PRICES.items()]
    if sources.fred is None:
        notices.append(Notice(NO_FRED_KEY))
    else:
        downloads += [
            (key, *item, sources.fred.get_series, earlier) for key, item in MARKET_SERIES.items()
        ]
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
    sources: ReferenceSources,
    benchmark_symbol: str | None = None,
    inflation_series: str | None = None,
    risk_free_series: str | None = None,
) -> MarketReferences:
    """Completa con las referencias predeterminadas de la divisa las que no se indiquen.

    benchmark_symbol sustituye al índice predeterminado; puede cotizar en otra divisa.
    """
    defaults = REPORT_DEFAULTS.get(currency, {})
    references = load_market_references(
        start,
        end,
        sources,
        benchmark_symbol=benchmark_symbol or defaults.get("benchmark_symbol"),
        inflation_series=inflation_series or defaults.get("inflation_series"),
        risk_free_series=risk_free_series or defaults.get("risk_free_series"),
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
    elif not benchmark_symbol:
        notes.append(Notice(DEFAULT_BENCHMARK_NOTE, kind="method"))
    if defaults and not all((benchmark_symbol, inflation_series, risk_free_series)):
        notes.append(
            Notice(
                "Las referencias no indicadas se han elegido según la divisa del informe. "
                "Comprueba si se ajustan al mercado y a la zona geográfica que quieres analizar.",
                kind="method",
            )
        )
    context, context_notices = load_market_context(start, end, sources)
    # La falta de clave de FRED ya se explica una vez en las referencias.
    context_notices = [notice for notice in context_notices if notice not in references.notices]
    return replace(references, notices=(*references.notices, *context_notices, *notes), **context)
