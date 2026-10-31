"""Analiza una cartera con precios de Yahoo Finance o Alpha Vantage y genera informes en español."""

import argparse
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

from src.analysis import PortfolioAnalysis
from src.constants import DEFAULT_CAPITAL, MONTHLY, Rebalance
from src.errors import ConfigurationError, PortfolioError
from src.market_loader import load_references
from src.models import Portfolio
from src.portfolio_loader import load_portfolio
from src.providers import (
    ALFRED_KEY,
    ALPHA_VANTAGE_KEY,
    AlphaVantageAPI,
    PriceProvider,
    ProviderError,
    YahooFinanceAPI,
    has_api_key,
)
from src.reporting.formatting import format_date, format_number
from src.reporting.labels import PERCENT_RESULTS, SOURCES, simulation_labels
from src.reporting.report import holdings_table
from src.reporting.sections import DETAILS, SECTION_TITLES, select_sections
from src.simulation import SimulationResult, SimulationSettings
from src.validation import (
    date_range,
    validate_capital,
    validate_currency_code,
    validate_symbols,
    validate_weights,
)

# Caché de Yahoo Finance, Alpha Vantage y ALFRED, relativa a la carpeta desde la que se
# ejecuta el programa. Las respuestas se reutilizan durante un día, por símbolo y serie.
CACHE_DIR = Path(".cache") / "market-data"
SIMULATION_OPTIONS = ("steps", "simulations", "seed", "confidence")
ASSUMPTIONS_FORMAT = (
    "Indica un número finito o valores SÍMBOLO:número sin repetir activos. Los símbolos deben "
    "pertenecer a la cartera."
)


@dataclass(frozen=True)
class ProviderOption:
    """Cómo crear cada proveedor, cuántos días pedir por defecto y qué clave necesita."""

    create: Callable[[], PriceProvider]
    default_history_days: int
    api_key_env: str | None = None


PROVIDERS = {
    "yahoo": ProviderOption(lambda: YahooFinanceAPI(cache_dir=CACHE_DIR), 365),
    # El modo compact de Alpha Vantage ofrece unas 100 sesiones.
    "alpha_vantage": ProviderOption(
        lambda: AlphaVantageAPI(cache_dir=CACHE_DIR, include_info=True),
        120,
        api_key_env=ALPHA_VANTAGE_KEY,
    ),
}


@dataclass(frozen=True)
class RunConfig:
    """Opciones de la consola ya validadas; simulation es None si no se pide Monte Carlo."""

    provider: str
    weights: dict[str, float]
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


def parse_values(items: list[str]) -> dict[str, float]:
    """Interpreta los pesos indicados en consola o en un archivo de texto."""
    if len(items) == 1 and items[0].lower().endswith(".txt"):
        items = _read_weights_file(Path(items[0]).expanduser())
    elif any(item.lower().endswith(".txt") for item in items):
        raise PortfolioError(
            "Indica un solo archivo .txt o los pesos en consola, sin mezclar ambos formatos."
        )
    pairs = [_parse_pair(item) for item in items]
    validate_symbols(symbol for symbol, _ in pairs)
    weights = dict(pairs)
    validate_weights(list(weights.values()))
    return weights


def _read_weights_file(path: Path) -> list[str]:
    """Una asignación por línea; se admiten líneas vacías y comentarios con #."""
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


def _parse_pair(item: str) -> tuple[str, float]:
    symbol, separator, text = item.rpartition(":")
    weight = _parse_number(text) if separator else None
    if weight is None:
        raise PortfolioError(
            f"Usa el formato SÍMBOLO:PESO, por ejemplo IBM:0.6. Has indicado: {item!r}."
        )
    return symbol.strip(), weight


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
    options.add_argument(
        "--assets",
        nargs="+",
        required=True,
        metavar="SÍMBOLO:PESO",
        help="Pesos objetivo, por ejemplo IBM:0.6 MSFT:0.4, o la ruta de un archivo .txt",
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
        help="Guardar el informe en formato Markdown con sus gráficos. Con "
        f"{ALFRED_KEY} incluye además inflación y tipo de interés de ALFRED",
    )
    options.add_argument(
        "--output-dir",
        type=Path,
        metavar="CARPETA",
        help="Carpeta de los informes. Por defecto: informes, dentro de la carpeta actual",
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
        "--steps", type=int, help=f"Sesiones futuras de Monte Carlo ({defaults.steps})"
    )
    options.add_argument(
        "--simulations", type=int, help=f"Número de escenarios ({defaults.simulations})"
    )
    options.add_argument("--seed", type=int, help=f"Semilla aleatoria ({defaults.seed})")
    options.add_argument(
        "--confidence", type=float, help=f"Confianza del VaR y CVaR ({defaults.confidence})"
    )
    options.add_argument(
        "--capital",
        type=float,
        default=DEFAULT_CAPITAL,
        help=f"Capital hipotético inicial ({DEFAULT_CAPITAL})",
    )
    options.add_argument(
        "--rebalance",
        choices=["monthly", "none"],
        default="monthly",
        help="Rebalanceo mensual o sin reajustes",
    )
    options.add_argument(
        "--return",
        dest="expected_returns",
        nargs="+",
        metavar="MU",
        help="Retorno anual mu para todos (0.08) o por activo (IBM:0.08 MSFT:0.1)",
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
    selected = select_sections(args.report_sections, detail, has_simulation=True)
    run_simulation = args.simulate or (args.report and "simulation" in selected)
    provider = PROVIDERS[args.provider]
    start = args.start or (
        (date.today() - timedelta(days=provider.default_history_days)).isoformat()
    )
    date_range(start, args.end)
    weights = parse_values(args.assets)
    options = {
        name: getattr(args, name) for name in SIMULATION_OPTIONS if getattr(args, name) is not None
    }
    for name in ("expected_returns", "volatilities"):
        assumption = parse_assumptions(getattr(args, name), weights)
        if assumption is not None:
            options[name] = assumption
    if options and not run_simulation:
        raise PortfolioError(
            "Los parámetros de Monte Carlo requieren --simulate o la sección simulation de "
            "--report."
        )
    validate_capital(args.capital)
    currency = args.currency.strip().upper()
    if currency:
        validate_currency_code(currency, "La divisa de destino")
    return RunConfig(
        provider=args.provider,
        weights=weights,
        start=start,
        end=args.end,
        currency=currency,
        capital=args.capital,
        rebalance=None if args.rebalance == "none" else MONTHLY,
        simulation=SimulationSettings(**options) if run_simulation else None,
        report=args.report,
        plots_report=args.plots_report,
        report_sections=args.report_sections,
        report_detail=detail,
        output_dir=args.output_dir,
    )


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
    if config.report and not has_api_key(ALFRED_KEY):
        warnings.append(
            f"{ALFRED_KEY} no está configurada: el informe se generará sin inflación ni tipo de "
            "interés de referencia, por lo que no incluirá la rentabilidad real ni las ratios "
            "de Sharpe y Sortino. El índice de referencia (Yahoo Finance) sí se incluye."
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
    portfolio = load_portfolio(
        config.weights,
        PROVIDERS[config.provider].create(),
        config.start,
        config.end,
        reporting_currency=config.currency,
        initial_capital=config.capital,
        rebalance=config.rebalance,
        fx_provider=fx_provider,
    )
    print_portfolio(portfolio)
    simulation = None
    if config.simulation is not None:
        # El informe muestra el horizonte, los escenarios, la semilla y los supuestos utilizados.
        simulation = portfolio.monte_carlo(config.simulation)
        print_simulation(simulation)
    if not (config.report or config.plots_report):
        return
    # Las referencias económicas solo se descargan para el informe.
    references = None
    if config.report:
        references = load_references(
            portfolio.currency, config.start, config.end, cache_dir=CACHE_DIR
        )
    analysis = portfolio.analyze(references)
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


def show_plots(analysis: PortfolioAnalysis, simulation: SimulationResult | None = None) -> None:
    """Muestra a la vez los gráficos históricos y, si existe, la simulación."""
    import matplotlib.pyplot as plt

    analysis.plots_report()
    if simulation is not None:
        simulation.plot(show=False)
    plt.show()


def print_portfolio(portfolio: Portfolio) -> None:
    """Presenta las posiciones con las mismas etiquetas y formato que el informe."""
    currency = portfolio.currency
    print(f"Fecha de valoración: {format_date(portfolio.valuation_date)} ({currency})")
    print(holdings_table(portfolio.holdings()).to_string())
    print(f"Capital hipotético inicial: {format_number(portfolio.initial_capital)} {currency}")
    print("Rebalanceo: mensual" if portfolio.rebalance == MONTHLY else "Rebalanceo: sin reajustes")
    print(f"Valor total: {format_number(portfolio.total_value)} {currency}")
    print(f"Fechas con precios para todos los activos: {len(portfolio.close_prices())}")


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
    try:
        run(config)
    except (PortfolioError, ProviderError, OSError) as error:
        print(f"No se ha podido completar el análisis: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
