"""Analiza una cartera con precios de Yahoo Finance o Alpha Vantage y genera informes en español."""

import argparse
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import date, timedelta
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

from src.analysis import PortfolioAnalysis
from src.commissions import (
    BROKER_PRESETS,
    DEFAULT_BROKER,
    DEFAULT_MAX_ORDER_COST,
    DEFAULT_REBALANCE_BAND,
    RebalanceRule,
)
from src.constants import (
    CLOSE,
    DAYS_PER_YEAR,
    DEFAULT_CAPITAL,
    DEFAULT_ESTIMATION_YEARS,
    MIN_ESTIMATION_YEARS,
    MONTHLY,
    PriceColumn,
    Rebalance,
)
from src.errors import ConfigurationError, PortfolioError
from src.market_loader import (
    REPORT_DEFAULTS,
    load_market_references,
    load_references,
    load_risk_free_rate,
)
from src.models import MarketReferences, Portfolio
from src.portfolio_loader import load_portfolio, load_portfolio_from_shares
from src.price_loader import MAX_DOWNLOAD_WORKERS, download_capacity, validate_download_workers
from src.providers import (
    ALPHA_VANTAGE_KEY,
    FRED_KEY,
    AlphaVantageAPI,
    PriceProvider,
    ProviderError,
    YahooFinanceAPI,
    has_api_key,
)
from src.providers.yahoo import quiet_yfinance_warnings
from src.reporting.formatting import format_date, format_number
from src.reporting.labels import PERCENT_RESULTS, SOURCES, simulation_labels
from src.reporting.report import commission_description, holdings_table
from src.reporting.sections import DETAILS, SECTION_TITLES, select_sections
from src.simulation import SimulationResult, SimulationSettings
from src.validation import (
    date_range,
    validate_capital,
    validate_currency_code,
    validate_symbols,
    validate_units,
    validate_weights,
)

# Caché de Yahoo Finance, Alpha Vantage y FRED, relativa a la carpeta desde la que se
# ejecuta el programa. Las respuestas se reutilizan durante un día, por símbolo y serie.
CACHE_DIR = Path(".cache") / "market-data"
SIMULATION_OPTIONS = ("steps", "simulations", "seed", "confidence", "equity_premium")
ASSUMPTIONS_FORMAT = (
    "Indica un número finito o valores SÍMBOLO:número sin repetir activos. Los símbolos deben "
    "pertenecer a la cartera."
)


@dataclass(frozen=True)
class ProviderOption:
    """Cómo crear cada proveedor, cuántos días pedir por defecto y qué clave necesita.

    split_adjusted indica si sus cierres están ajustados por splits, algo que necesita una
    cartera definida por número de acciones.
    """

    create: Callable[[], PriceProvider]
    default_history_days: int
    api_key_env: str | None = None
    split_adjusted: bool = True
    # Días hasta --end con los que Monte Carlo estima σ y las correlaciones; None usa el
    # período del análisis porque el proveedor no ofrece más historia gratis.
    default_estimation_days: int | None = None


PROVIDERS = {
    "yahoo": ProviderOption(
        lambda: YahooFinanceAPI(cache_dir=CACHE_DIR),
        365,
        default_estimation_days=round(DEFAULT_ESTIMATION_YEARS * DAYS_PER_YEAR),
    ),
    # El modo compact de Alpha Vantage ofrece unas 100 sesiones.
    "alpha_vantage": ProviderOption(
        lambda: AlphaVantageAPI(cache_dir=CACHE_DIR, include_info=True),
        120,
        api_key_env=ALPHA_VANTAGE_KEY,
        split_adjusted=False,
    ),
}


@dataclass(frozen=True)
class RunConfig:
    """Opciones de la consola ya validadas; simulation es None si no se pide Monte Carlo.

    La cartera se define con weights (--assets) o con shares (--shares): uno de los dos es None.
    """

    provider: str
    weights: dict[str, float] | None
    start: str
    end: str
    currency: str
    capital: float
    rebalance: Rebalance
    simulation: SimulationSettings | None
    report: bool
    plots_report: bool
    report_sections: list[str] | None
    report_detail: str
    output_dir: Path | None
    benchmark: str | None = None
    shares: dict[str, float] | None = None
    # Comisiones y criterio de reajuste; sin rebalanceo mensual no se usa.
    rebalance_rule: RebalanceRule = RebalanceRule()
    # Inicio de los precios con los que Monte Carlo estima σ y las correlaciones; None usa start.
    estimation_start: str | None = None
    # Activos que se descargan a la vez en cada lote, si el proveedor lo admite.
    download_workers: int = 1

    def __post_init__(self) -> None:
        if (self.weights is None) == (self.shares is None):
            raise ValueError("Indica la cartera con weights o con shares, no con ambos.")


def parse_values(items: list[str]) -> dict[str, float]:
    """Interpreta los pesos indicados en consola o en un archivo de texto."""
    weights = _parse_allocation(items, "PESO", "IBM:0.6")
    validate_weights(list(weights.values()))
    return weights


def parse_shares(items: list[str]) -> dict[str, float]:
    """Interpreta el número de acciones de cada activo, en consola o en un archivo de texto."""
    shares = _parse_allocation(items, "ACCIONES", "AAPL:10")
    validate_units(list(shares.values()))
    return shares


def _parse_allocation(items: list[str], value_name: str, example: str) -> dict[str, float]:
    """Lee pares SÍMBOLO:VALOR de la consola o de un único archivo .txt."""
    if len(items) == 1 and items[0].lower().endswith(".txt"):
        items = _read_allocation_file(Path(items[0]).expanduser())
    elif any(item.lower().endswith(".txt") for item in items):
        raise PortfolioError(
            "Indica un solo archivo .txt o los valores en consola, sin mezclar ambos formatos."
        )
    pairs = [_parse_pair(item, value_name, example) for item in items]
    validate_symbols(symbol for symbol, _ in pairs)
    return dict(pairs)


def _read_allocation_file(path: Path) -> list[str]:
    """Un par SÍMBOLO:VALOR por línea; se admiten líneas vacías y comentarios con #."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError:
        raise PortfolioError(f"No se ha podido leer el archivo de cartera: {path}.") from None
    except UnicodeError:
        raise PortfolioError("El archivo de cartera debe estar guardado en UTF-8.") from None
    return [item for line in text.splitlines() for item in line.split("#", 1)[0].split()]


def _parse_number(text: str) -> float | None:
    try:
        return float(text)
    except ValueError:
        return None


def _parse_pair(item: str, value_name: str = "PESO", example: str = "IBM:0.6") -> tuple[str, float]:
    symbol, separator, text = item.rpartition(":")
    value = _parse_number(text) if separator else None
    if value is None:
        raise PortfolioError(
            f"Usa el formato SÍMBOLO:{value_name}, por ejemplo {example}. Has indicado: {item!r}."
        )
    return symbol.strip(), value


def parse_assumptions(items: list[str] | None, weights: dict[str, float]):
    """Lee un supuesto común o cambios por activo; el resto conserva su estimación histórica."""
    if items is None:
        return None
    if len(items) == 1 and ":" not in items[0]:
        return _assumption(items[0])
    symbols = {symbol.lower(): symbol for symbol in weights}
    values = {}
    for item in items:
        name, _, text = item.rpartition(":")
        symbol = symbols.get(name.strip().lower())
        if symbol is None or symbol in values:
            raise PortfolioError(ASSUMPTIONS_FORMAT)
        values[symbol] = _assumption(text)
    return values


def _assumption(text: str) -> float:
    value = _parse_number(text)
    if value is None:
        raise PortfolioError(ASSUMPTIONS_FORMAT)
    return value


def build_parser() -> argparse.ArgumentParser:
    defaults = SimulationSettings()
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False, add_help=False)
    options = parser.add_argument_group("Opciones")
    options.add_argument("-h", "--help", action="help", help="Mostrar esta ayuda y salir")
    options.add_argument(
        "--provider",
        choices=list(PROVIDERS),
        default="yahoo",
        help="Proveedor de precios: yahoo (sin clave, por defecto) o alpha_vantage "
        f"(necesita {ALPHA_VANTAGE_KEY})",
    )
    # La cartera se define por pesos o por número de acciones, nunca por ambos.
    composition = options.add_mutually_exclusive_group(required=True)
    composition.add_argument(
        "--assets",
        nargs="+",
        metavar="SÍMBOLO:PESO",
        help="Pesos objetivo, por ejemplo IBM:0.6 MSFT:0.4, o la ruta de un archivo .txt",
    )
    composition.add_argument(
        "--shares",
        nargs="+",
        metavar="SÍMBOLO:ACCIONES",
        help="Número de acciones de cada activo, por ejemplo AAPL:10 SPY:5, o la ruta de un "
        "archivo .txt. Se mantienen durante todo el historial, salvo con --rebalance monthly",
    )
    options.add_argument(
        "--start",
        metavar="AAAA-MM-DD",
        help="Fecha de inicio, incluida (AAAA-MM-DD). Por defecto: hace un año con Yahoo "
        "y 120 días con Alpha Vantage",
    )
    options.add_argument(
        "--end",
        metavar="AAAA-MM-DD",
        default=date.today().isoformat(),
        help="Fecha de fin, excluida (AAAA-MM-DD). Por defecto: hoy",
    )
    options.add_argument(
        "--estimation-start",
        metavar="AAAA-MM-DD",
        help="Inicio de los precios con los que Monte Carlo estima la volatilidad y las "
        f"correlaciones, hasta --end. Por defecto: {DEFAULT_ESTIMATION_YEARS} años antes de "
        "--end con Yahoo, o --start si es anterior; con Alpha Vantage, --start",
    )
    options.add_argument(
        "--simulate",
        action="store_true",
        help="Simular la evolución de la cartera a partir de los datos históricos",
    )
    options.add_argument(
        "--plots-report",
        action="store_true",
        help="Mostrar los gráficos del análisis sin guardar un informe",
    )
    options.add_argument(
        "--report",
        action="store_true",
        help="Guardar el informe en formato Markdown con sus gráficos",
    )
    options.add_argument(
        "--output-dir",
        type=Path,
        metavar="CARPETA",
        help="Carpeta de los informes. Por defecto: informes, dentro de la carpeta actual",
    )
    options.add_argument(
        "--benchmark",
        metavar="SÍMBOLO",
        help="Índice o fondo de Yahoo Finance contra el que comparar la cartera, por ejemplo "
        "^IXIC, ^IBEX o URTH. Por defecto, según la divisa: "
        + ", ".join(f"{code} {item['benchmark_symbol']}" for code, item in REPORT_DEFAULTS.items())
        + ". Requiere --report o --plots-report",
    )
    options.add_argument(
        "--currency",
        metavar="DIVISA",
        default="",
        help="Divisa a la que convertir la cartera, por ejemplo EUR",
    )
    options.add_argument(
        "--report-detail",
        choices=list(DETAILS),
        help="Informe con secciones plegadas o todo desplegado. Por defecto: compact",
    )
    options.add_argument(
        "--report-sections",
        nargs="+",
        choices=list(SECTION_TITLES),
        help="Secciones del informe; por defecto, todas",
    )
    options.add_argument(
        "--download-workers",
        type=int,
        metavar="N",
        help=f"Activos que se descargan a la vez, de 1 a {MAX_DOWNLOAD_WORKERS} (1 por defecto). "
        "Solo Yahoo descarga en paralelo; Alpha Vantage usa siempre 1",
    )
    options.add_argument(
        "--steps",
        type=int,
        help="Sesiones futuras de Monte Carlo (un año: 252, o 365 si la cartera es solo cripto)",
    )
    options.add_argument(
        "--simulations", type=int, help=f"Número de escenarios ({defaults.simulations})"
    )
    options.add_argument("--seed", type=int, help=f"Semilla aleatoria ({defaults.seed})")
    options.add_argument(
        "--confidence", type=float, help=f"Confianza del VaR y CVaR ({defaults.confidence})"
    )
    options.add_argument(
        "--equity-premium",
        type=float,
        metavar="PRIMA",
        help="Retorno anual de la renta variable sobre el tipo libre de riesgo "
        f"({defaults.equity_premium})",
    )
    options.add_argument(
        "--capital",
        type=float,
        help=f"Capital hipotético inicial ({DEFAULT_CAPITAL}); no se usa con --shares",
    )
    options.add_argument(
        "--rebalance",
        choices=["monthly", "none"],
        help="Rebalanceo mensual o sin reajustes. Por defecto, mensual con --assets y sin "
        "reajustes con --shares; con --shares, monthly vuelve cada mes a los pesos iniciales",
    )
    costs = parser.add_argument_group("Comisiones del rebalanceo")
    costs.add_argument(
        "--broker",
        choices=list(BROKER_PRESETS),
        help="Tarifa de partida: "
        + "; ".join(
            f"{key} ({commission_description(schedule, 'EUR').replace('%', '%%')})"
            for key, schedule in BROKER_PRESETS.items()
        )
        + f". Por defecto: {DEFAULT_BROKER}",
    )
    costs.add_argument(
        "--commission-rate",
        type=float,
        metavar="FRACCIÓN",
        help="Comisión proporcional por orden, por ejemplo 0.0005 (0,05 %%)",
    )
    costs.add_argument(
        "--commission-fixed", type=float, metavar="IMPORTE", help="Comisión fija por orden"
    )
    costs.add_argument(
        "--commission-min", type=float, metavar="IMPORTE", help="Comisión mínima por orden"
    )
    costs.add_argument(
        "--commission-max", type=float, metavar="IMPORTE", help="Comisión máxima por orden"
    )
    costs.add_argument(
        "--rebalance-band",
        type=float,
        metavar="FRACCIÓN",
        help="Solo se reajusta si algún peso se desvía más que esto de su objetivo "
        f"({DEFAULT_REBALANCE_BAND}, 5 puntos); 0 reajusta todos los meses",
    )
    costs.add_argument(
        "--max-order-cost",
        type=float,
        metavar="FRACCIÓN",
        help="Descarta las órdenes cuya comisión supere esta fracción de su importe "
        f"({DEFAULT_MAX_ORDER_COST}, 1 %%)",
    )
    options.add_argument(
        "--return",
        dest="expected_returns",
        nargs="+",
        metavar="MU",
        help="Retorno anual mu para todos (0.08) o por activo (IBM:0.08 MSFT:0.1). Por defecto: "
        "tipo libre de riesgo + prima por la parte en renta variable",
    )
    options.add_argument(
        "--volatility",
        dest="volatilities",
        nargs="+",
        metavar="SIGMA",
        help="Volatilidad anual sigma para todos (0.2) o por activo (IBM:0.2 MSFT:0.3)",
    )
    return parser


def parse_arguments(argv: Sequence[str] | None = None) -> RunConfig:
    """Lee las opciones y valida la entrada antes de descargar."""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return _build_config(args)
    except (ValueError, OSError) as error:
        parser.error(str(error))


def _build_config(args: argparse.Namespace) -> RunConfig:
    """Valida y normaliza las opciones; los errores se muestran antes de descargar."""
    presentation = (args.report_sections, args.report_detail, args.output_dir)
    if not args.report and any(option is not None for option in presentation):
        raise PortfolioError("Las opciones de presentación requieren --report.")
    detail = args.report_detail or "compact"
    selected = select_sections(args.report_sections, detail)
    run_simulation = args.simulate or (args.report and "simulation" in selected)
    provider = PROVIDERS[args.provider]
    start = args.start or (
        (date.today() - timedelta(days=provider.default_history_days)).isoformat()
    )
    date_range(start, args.end)
    weights = shares = None
    if args.shares is not None:
        if args.capital is not None:
            raise PortfolioError(
                "--capital no se usa con --shares: el valor inicial sale del número de acciones."
            )
        if not provider.split_adjusted:
            raise PortfolioError(
                f"--shares necesita cierres ajustados por splits y {args.provider} no los "
                "ofrece: un split dentro del período falsearía el valor. Usa --provider yahoo."
            )
        shares = parse_shares(args.shares)
    else:
        weights = parse_values(args.assets)
    capital = DEFAULT_CAPITAL if args.capital is None else args.capital
    options = _simulation_options(args, shares or weights, run_simulation)
    benchmark = None
    if args.benchmark is not None:
        if not (args.report or args.plots_report):
            raise PortfolioError("--benchmark requiere --report o --plots-report.")
        validate_symbols([args.benchmark])
        benchmark = args.benchmark.strip()
    validate_capital(capital)
    currency = args.currency.strip().upper()
    if currency:
        validate_currency_code(currency, "La divisa de destino")
    rebalance = _rebalance(args.rebalance, by_shares=shares is not None)
    download_workers = 1 if args.download_workers is None else args.download_workers
    validate_download_workers(download_workers)
    return RunConfig(
        provider=args.provider,
        weights=weights,
        start=start,
        end=args.end,
        currency=currency,
        capital=capital,
        rebalance=rebalance,
        simulation=SimulationSettings(**options) if run_simulation else None,
        report=args.report,
        plots_report=args.plots_report,
        report_sections=args.report_sections,
        report_detail=detail,
        output_dir=args.output_dir,
        benchmark=benchmark,
        shares=shares,
        rebalance_rule=_rebalance_rule(args, rebalance),
        estimation_start=_estimation_start(args, provider, start, run_simulation),
        download_workers=download_workers,
    )


def _estimation_start(
    args: argparse.Namespace, provider: ProviderOption, start: str, enabled: bool
) -> str | None:
    """Inicio de la estimación de Monte Carlo; None si coincide con el del análisis.

    Por defecto, los años de DEFAULT_ESTIMATION_YEARS antes de --end o --start si es anterior,
    para no estimar nunca con menos datos de los que analiza el informe.
    """
    if args.estimation_start is not None:
        if not enabled:
            raise PortfolioError(
                "--estimation-start requiere --simulate o la sección simulation de --report."
            )
        date_range(args.estimation_start, args.end)
        return args.estimation_start
    if not enabled or provider.default_estimation_days is None:
        return None
    default = date.fromisoformat(args.end) - timedelta(days=provider.default_estimation_days)
    return default.isoformat() if default < date.fromisoformat(start) else None


COMMISSION_OPTIONS = {
    "commission_rate": "rate",
    "commission_fixed": "fixed",
    "commission_min": "minimum",
    "commission_max": "maximum",
}
COST_OPTIONS = ("broker", *COMMISSION_OPTIONS, "rebalance_band", "max_order_cost")


def _rebalance_rule(args: argparse.Namespace, rebalance: Rebalance) -> RebalanceRule:
    """Tarifa del bróker elegido, con los cambios indicados, y criterio de reajuste."""
    if rebalance != MONTHLY:
        if any(getattr(args, name) is not None for name in COST_OPTIONS):
            raise PortfolioError(
                "Las comisiones solo se aplican al rebalanceo: usa --rebalance monthly."
            )
        return RebalanceRule()
    schedule = BROKER_PRESETS[args.broker or DEFAULT_BROKER]
    changes = {
        field: getattr(args, option)
        for option, field in COMMISSION_OPTIONS.items()
        if getattr(args, option) is not None
    }
    if changes:
        schedule = replace(schedule, name=f"{schedule.name} (personalizada)", **changes)
    band = DEFAULT_REBALANCE_BAND if args.rebalance_band is None else args.rebalance_band
    max_cost = DEFAULT_MAX_ORDER_COST if args.max_order_cost is None else args.max_order_cost
    return RebalanceRule(schedule, band, max_cost)


def _rebalance(option: str | None, by_shares: bool) -> Rebalance:
    """Mensual por defecto con pesos; con acciones, solo si se pide."""
    if option is None:
        return None if by_shares else MONTHLY
    return MONTHLY if option == "monthly" else None


def _simulation_options(
    args: argparse.Namespace, holdings: dict[str, float], enabled: bool
) -> dict:
    """Normaliza los supuestos y rechaza opciones de simulación si no se va a simular."""
    options = {
        name: getattr(args, name) for name in SIMULATION_OPTIONS if getattr(args, name) is not None
    }
    for name in ("expected_returns", "volatilities"):
        assumption = parse_assumptions(getattr(args, name), holdings)
        if assumption is not None:
            options[name] = assumption
    if options and not enabled:
        raise PortfolioError(
            "Los parámetros de Monte Carlo requieren --simulate o la sección simulation de "
            "--report."
        )
    return options


def check_api_keys(config: RunConfig) -> list[str]:
    """Comprueba las claves antes de descargar nada.

    Falta la clave del proveedor elegido → ConfigurationError con una alternativa sin clave.
    Faltan claves opcionales → avisos que explican qué parte del resultado se omitirá.
    """
    env_name = PROVIDERS[config.provider].api_key_env
    if env_name and not has_api_key(env_name):
        name = SOURCES.get(config.provider, config.provider)
        raise ConfigurationError(
            f"{name} necesita una clave de API: configura {env_name} en el archivo .env o en "
            "el entorno. Sin clave puedes usar --provider yahoo, que no la necesita."
        )
    warnings = []
    if config.report and not has_api_key(FRED_KEY):
        warnings.append(
            f"{FRED_KEY} no está configurada: el informe se generará sin inflación, rentabilidad "
            "real, VIX ni Brent, y en USD tampoco tendrá tipo libre de riesgo, Sharpe ni Sortino. "
            "El índice de referencia, el oro, el ETF de Bunds y el tipo en EUR sí se incluyen."
        )
    return warnings


def run(config: RunConfig) -> None:
    """Coordina la carga, la simulación y las salidas solicitadas."""
    for warning in check_api_keys(config):
        print(f"Aviso: {warning}", file=sys.stderr)
    # Los cambios automáticos solo se consultan, en Yahoo, si hay que convertir divisas.
    fx_provider = None
    if config.currency:
        fx_provider = YahooFinanceAPI(cache_dir=CACHE_DIR, include_info=False)
    # Un solo proveedor para el análisis y la estimación de Monte Carlo: comparten caché.
    provider = PROVIDERS[config.provider].create()
    capacity = download_capacity(provider)
    if config.download_workers > capacity:
        name = SOURCES.get(config.provider, config.provider)
        limit = "de uno en uno" if capacity == 1 else f"como mucho {capacity} a la vez"
        print(
            f"Aviso: {name} descarga los activos {limit}; se ignora --download-workers "
            f"{config.download_workers}.",
            file=sys.stderr,
        )
    if config.shares is not None:
        portfolio = load_portfolio_from_shares(
            config.shares,
            provider,
            config.start,
            config.end,
            reporting_currency=config.currency,
            fx_provider=fx_provider,
            rebalance=config.rebalance,
            rebalance_rule=config.rebalance_rule,
            max_workers=config.download_workers,
        )
    else:
        portfolio = load_portfolio(
            config.weights,
            provider,
            config.start,
            config.end,
            reporting_currency=config.currency,
            initial_capital=config.capital,
            rebalance=config.rebalance,
            fx_provider=fx_provider,
            rebalance_rule=config.rebalance_rule,
            max_workers=config.download_workers,
        )
    # Con Adj Close las rentabilidades, la simulación y el informe incluyen los dividendos.
    price_column = portfolio.preferred_price_column
    print_portfolio(portfolio, price_column)
    # El análisis va antes que la simulación: si faltan datos, se avisa sin simular en balde.
    analysis = None
    if config.report or config.plots_report:
        analysis = portfolio.analyze(
            load_run_references(config, portfolio.currency), price_column=price_column
        )
    simulation = None
    if config.simulation is not None:
        simulation = run_simulation(config, portfolio, price_column, provider, fx_provider)
        print_simulation(simulation)
    if analysis is None:
        return
    if config.report:
        path = analysis.report(
            simulation,
            sections=config.report_sections,
            detail=config.report_detail,
            directory=config.output_dir,
        )
        print(f"Informe generado: {path.resolve()}")
    if config.plots_report:
        show_plots(analysis, simulation)


def run_simulation(
    config: RunConfig,
    portfolio: Portfolio,
    price_column: PriceColumn,
    provider: PriceProvider,
    fx_provider: PriceProvider | None = None,
) -> SimulationResult:
    """Simula desde el valor actual de la cartera, con σ y correlaciones de la estimación."""
    rate = load_risk_free_rate(portfolio.currency, config.end, cache_dir=CACHE_DIR)
    if rate is None:
        print(
            f"Aviso: no hay tipo libre de riesgo para {portfolio.currency}; la simulación usa "
            "el retorno histórico, que suele ser optimista. Puedes indicarlo con --return.",
            file=sys.stderr,
        )
    settings = replace(config.simulation, risk_free_rate=rate)
    estimation_prices = load_estimation_prices(
        config, portfolio, price_column, provider, fx_provider
    )
    # El informe muestra el horizonte, los escenarios, la semilla y los supuestos utilizados.
    simulation = portfolio.monte_carlo(
        settings, price_column=price_column, estimation_prices=estimation_prices
    )
    if simulation.estimation_years < MIN_ESTIMATION_YEARS:
        print(
            f"Aviso: la volatilidad y las correlaciones de la simulación se han estimado con "
            f"menos de {MIN_ESTIMATION_YEARS} años de datos; pueden no ser representativas. "
            "Amplía el período con --estimation-start o indica la volatilidad con --volatility.",
            file=sys.stderr,
        )
    return simulation


def load_estimation_prices(
    config: RunConfig,
    portfolio: Portfolio,
    price_column: PriceColumn,
    provider: PriceProvider,
    fx_provider: PriceProvider | None = None,
):
    """Precios del período de estimación, en la divisa de la cartera; None si es el del análisis.

    Solo se necesitan los precios: los valores de partida, los pesos objetivo del rebalanceo y
    las comisiones siguen siendo los de la cartera analizada.
    """
    if config.estimation_start is None or config.estimation_start == config.start:
        return None
    estimation = load_portfolio(
        dict(portfolio.target_weights),
        provider,
        config.estimation_start,
        config.end,
        reporting_currency=config.currency,
        rebalance=None,
        fx_provider=fx_provider,
        max_workers=config.download_workers,
    )
    return estimation.close_prices(price_column).loc[: portfolio.valuation_date]


def load_run_references(config: RunConfig, currency: str) -> MarketReferences | None:
    """El informe usa todas las referencias; los gráficos, solo el índice elegido, si lo hay."""
    if config.report:
        return load_references(
            currency,
            config.start,
            config.end,
            benchmark_symbol=config.benchmark,
            cache_dir=CACHE_DIR,
        )
    if not config.benchmark:
        return None
    references = load_market_references(
        config.start,
        config.end,
        benchmark_symbol=config.benchmark,
        cache_dir=CACHE_DIR,
        currency=currency,
    )
    # Sin informe no hay otro lugar donde explicar por qué falta la comparación.
    for notice in references.notices:
        print(f"Aviso: {notice.message}", file=sys.stderr)
    return references


def show_plots(analysis: PortfolioAnalysis, simulation: SimulationResult | None = None) -> None:
    """Muestra a la vez los gráficos históricos y, si existe, la simulación."""
    import matplotlib.pyplot as plt

    analysis.plots_report()
    if simulation is not None:
        simulation.plot(show=False)
    plt.show()


def print_portfolio(portfolio: Portfolio, price_column: PriceColumn = CLOSE) -> None:
    """Presenta las posiciones con las mismas etiquetas y formato que el informe."""
    currency = portfolio.currency
    holdings = portfolio.holdings(price_column)
    print(f"Fecha de valoración: {format_date(portfolio.valuation_date)} ({currency})")
    print(holdings_table(holdings, by_shares=portfolio.fixed_units).to_string())
    if portfolio.units is not None:
        start = format_date(portfolio.close_prices().index[0])
        print(
            f"Valor inicial de las acciones ({start}): "
            f"{format_number(portfolio.initial_capital)} {currency}"
        )
        print(
            "Rebalanceo: sin reajustes (el número de acciones no cambia)"
            if portfolio.fixed_units
            else "Rebalanceo: mensual, a los pesos iniciales de las acciones"
        )
    else:
        print(f"Capital hipotético inicial: {format_number(portfolio.initial_capital)} {currency}")
        print(
            "Rebalanceo: mensual" if portfolio.rebalance == MONTHLY else "Rebalanceo: sin reajustes"
        )
    if "market_value" in holdings:
        print(
            f"Valor de mercado de las acciones (acciones × último cierre): "
            f"{format_number(holdings['market_value'].sum())} {currency}"
        )
        print(f"Valor total con dividendos: {format_number(holdings['value'].sum())} {currency}")
    else:
        print(f"Valor total: {format_number(holdings['value'].sum())} {currency}")
    if portfolio.rebalance == MONTHLY:
        print_rebalance_costs(portfolio, price_column)
    print(f"Fechas con precios para todos los activos: {len(portfolio.close_prices())}")


def print_rebalance_costs(portfolio: Portfolio, price_column: PriceColumn = CLOSE) -> None:
    """Tarifa aplicada, reajustes realizados y comisiones pagadas en el historial."""
    rule = portfolio.rebalance_rule
    if rule.is_free:
        return
    result = portfolio.backtest(price_column)
    tariff = commission_description(rule.commissions, portfolio.currency)
    print(f"Comisiones: {rule.commissions.name}, {tariff}")
    print(
        f"Reajustes: {len(result.rebalance_dates)}, con {len(result.trades)} órdenes "
        f"({result.skipped_orders} descartadas por caras); comisiones pagadas: "
        f"{format_number(result.total_commissions)} {portfolio.currency}"
    )


def print_simulation(result: SimulationResult) -> None:
    """Distingue los importes de las rentabilidades y probabilidades."""
    labels = simulation_labels(result.confidence)
    print("\nResumen de la simulación:")
    for key, value in result.summary().items():
        percentage = key in PERCENT_RESULTS
        suffix = "" if percentage else f" {result.currency}"
        print(f"{labels[key]}: {format_number(value, percentage)}{suffix}")


def main(argv: Sequence[str] | None = None) -> int:
    load_dotenv(find_dotenv(usecwd=True), override=False)
    config = parse_arguments(argv)
    # Una sola vez y antes de cualquier descarga: los hilos no cambian filtros de avisos.
    quiet_yfinance_warnings()
    try:
        run(config)
    except (PortfolioError, ProviderError, OSError) as error:
        print(f"No se ha podido completar el análisis: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
