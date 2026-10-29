import sys

# Evita generar bytecode cuando importas los modulos durnate la ejecución del main.py
sys.dont_write_bytecode = True

import argparse
import math
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

from src.market_loader import load_report_context
from src.models.validation import validate_weights
from src.portfolio_loader import load_portfolio
from src.providers import AlphaVantageAPI, ProviderError, YahooFinanceAPI
from src.providers.base import date_range
from src.reporting.formatting import format_number

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_values(items: list[str]) -> dict[str, float]:
    """Interpreta los pesos indicados en consola o en un archivo de texto."""
    if len(items) == 1 and items[0].lower().endswith(".txt"):
        path = Path(items[0]).expanduser()
        try:
            text = path.read_text(encoding="utf-8-sig")
        except OSError:
            raise ValueError(f"No se ha podido leer el archivo de cartera: {path}.") from None
        except UnicodeError:
            raise ValueError("El archivo de cartera debe estar guardado en UTF-8.") from None
        items = []
        for line in text.splitlines():
            items.extend(line.split("#", 1)[0].split())
    elif any(item.lower().endswith(".txt") for item in items):
        raise ValueError(
            "Indica un solo archivo .txt o los pesos en consola, sin mezclar ambos formatos."
        )
    values = {}
    seen = set()
    for item in items:
        try:
            symbol, text = item.rsplit(":", 1)
            symbol = symbol.strip()
            value = float(text)
        except ValueError:
            raise ValueError(
                f"Usa el formato SÍMBOLO:PESO, por ejemplo IBM:0.6. Has indicado: {item!r}."
            ) from None
        if not symbol or not math.isfinite(value):
            raise ValueError("Los símbolos no pueden estar vacíos y los valores deben ser finitos.")
        if symbol.lower() in seen:
            raise ValueError(f"Activo repetido: {symbol}.")
        seen.add(symbol.lower())
        values[symbol] = value
    validate_weights(list(values.values()))
    return values


def parse_arguments() -> argparse.Namespace:
    """Lee las opciones y valida la entrada antes de descargar."""
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False, add_help=False)
    options = parser.add_argument_group("Opciones")
    options.add_argument("-h", "--help", action="help", help="Mostrar esta ayuda y salir")
    options.add_argument(
        "--provider",
        choices=["yahoo", "alpha_vantage"],
        default="yahoo",
        help="Proveedor de precios de los activos. Por defecto: yahoo",
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
        default=(date.today() - timedelta(days=30)).isoformat(),
        help="Fecha de inicio, incluida (AAAA-MM-DD). Por defecto: hace 30 días",
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
        help="Guardar el informe en formato Markdown y sus gráficos en la carpeta informes",
    )
    options.add_argument(
        "--currency",
        metavar="DIVISA",
        default="",
        help="Divisa a la que convertir la cartera, por ejemplo EUR",
    )
    options.add_argument(
        "--steps", type=int, default=252, help="Sesiones futuras de Monte Carlo (252)"
    )
    options.add_argument(
        "--simulations", type=int, default=1000, help="Número de escenarios (1000)"
    )
    options.add_argument("--seed", type=int, default=42, help="Semilla aleatoria (42)")
    options.add_argument(
        "--confidence", type=float, default=0.95, help="Confianza del VaR y CVaR (0.95)"
    )
    options.add_argument(
        "--capital", type=float, default=10_000, help="Capital hipotético inicial (10000)"
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
    args = parser.parse_args()
    try:
        date_range(args.start, args.end)
        args.weights = parse_values(args.assets)
        args.expected_returns = parse_assumptions(args.expected_returns, args.weights)
        args.volatilities = parse_assumptions(args.volatilities, args.weights)
        if args.volatilities is not None:
            values = (
                args.volatilities.values()
                if isinstance(args.volatilities, dict)
                else [args.volatilities]
            )
            if any(value < 0 for value in values):
                raise ValueError("La volatilidad no puede ser negativa.")
        if args.steps < 1 or args.simulations < 1 or args.seed < 0:
            raise ValueError(
                "Las sesiones y los escenarios deben ser positivos; la semilla no puede ser negativa."
            )
        if not 0.5 < args.confidence < 1:
            raise ValueError("La confianza debe estar entre 0,5 y 1.")
        if not math.isfinite(args.capital) or args.capital <= 0:
            raise ValueError("El capital debe ser positivo y finito.")
        if not (args.simulate or args.report) and (
            args.expected_returns is not None
            or args.volatilities is not None
            or args.steps != 252
            or args.simulations != 1000
            or args.confidence != 0.95
            or args.seed != 42
        ):
            raise ValueError("Los parámetros de Monte Carlo requieren --simulate o --report.")
        args.rebalance = None if args.rebalance == "none" else "monthly"
        args.currency = args.currency.strip().upper()
        if args.currency and (len(args.currency) != 3 or not args.currency.isalpha()):
            raise ValueError(
                "Indica la divisa de destino con un código de tres letras, por ejemplo EUR."
            )
    except (ValueError, OSError) as error:
        parser.error(str(error))
    return args


def parse_assumptions(items: list[str] | None, weights: dict[str, float]):
    """Lee un supuesto común o cambios por activo; el resto conserva su estimación histórica."""
    if items is None:
        return None
    try:
        if len(items) == 1 and ":" not in items[0]:
            value = float(items[0])
            if not math.isfinite(value):
                raise ValueError
            return value
        symbols = {symbol.lower(): symbol for symbol in weights}
        values = {}
        for item in items:
            symbol, text = item.rsplit(":", 1)
            symbol = symbols[symbol.strip().lower()]
            value = float(text)
            if symbol in values or not math.isfinite(value):
                raise ValueError
            values[symbol] = value
        return values
    except (ValueError, KeyError):
        raise ValueError(
            "Indica un número finito o valores SÍMBOLO:número sin repetir activos. Los símbolos deben pertenecer a la cartera."
        ) from None


def run_portfolio(args) -> None:
    """Coordina la carga, la simulación y las salidas solicitadas."""
    if args.provider == "alpha_vantage":
        provider = AlphaVantageAPI(cache_dir=PROJECT_ROOT / ".cache" / "market-data")
    else:
        provider = YahooFinanceAPI()
    portfolio = load_portfolio(
        args.weights,
        provider,
        args.start,
        args.end,
        include_info=True,
        reporting_currency=args.currency,
        initial_capital=args.capital,
        rebalance=args.rebalance,
    )
    if args.report:
        portfolio.market_context = load_report_context(
            portfolio,
            args.start,
            args.end,
            cache_dir=PROJECT_ROOT / ".cache" / "market-data",
        )
    print_portfolio(portfolio)
    simulation = None
    if args.simulate or args.report:
        # El informe muestra el horizonte, los escenarios, la semilla y los supuestos utilizados.
        simulation = portfolio.monte_carlo(
            steps=args.steps,
            simulations=args.simulations,
            seed=args.seed,
            expected_returns=args.expected_returns,
            volatilities=args.volatilities,
            confidence=args.confidence,
        )
        print_simulation(simulation)
    if args.report or args.plots_report:
        analysis = portfolio.analyze()
        if args.report:
            path = analysis.report(simulation=simulation)
            print(f"Informe generado: {path.resolve()}")
        if args.plots_report:
            show_plots(analysis, simulation)


def show_plots(analysis, simulation=None) -> None:
    """Muestra los gráficos históricos y, si existe, la simulación, sin guardar archivos."""
    import matplotlib.pyplot as plt

    from src.reporting.plots import plot_assets, plot_distribution

    analysis.plot(show=False)
    plot_assets(analysis, show=False)
    plot_distribution(analysis, show=False)
    if simulation is not None:
        simulation.plot(show=False)
    plt.show()


def print_portfolio(portfolio) -> None:
    """Presenta las posiciones sin modificar los nombres internos del modelo."""
    holdings = portfolio.holdings()
    for column in ("target_weight", "weight"):
        holdings[column] = holdings[column].map(lambda value: format_number(value, True))
    holdings = holdings.rename(
        columns={
            "price": "Precio",
            "value": "Valor",
            "target_weight": "Peso objetivo",
            "weight": "Peso actual",
        }
    ).rename_axis("Activo")
    print(f"Fecha de valoración: {portfolio.valuation_date:%d/%m/%Y} ({portfolio.currency})")
    print(holdings.to_string(float_format=lambda value: f"{value:.4f}".replace(".", ",")))
    print(
        f"Capital hipotético inicial: {format_number(portfolio.initial_capital)} {portfolio.currency}"
    )
    print("Rebalanceo: mensual" if portfolio.rebalance else "Rebalanceo: sin reajustes")
    print(f"Valor total: {format_number(portfolio.total_value)} {portfolio.currency}")
    print(f"Fechas con precios para todos los activos: {len(portfolio.close_prices())}")


def print_simulation(result) -> None:
    """Distingue los importes de las rentabilidades y probabilidades."""
    labels = {
        "initial_value": "Valor inicial",
        "mean_final_value": "Valor final medio",
        "median_final_value": "Mediana del valor final",
        "lower_percentile": f"Percentil {100 * (1 - result.confidence):g} del valor final",
        "upper_percentile": f"Percentil {100 * result.confidence:g} del valor final",
        "mean_return": "Rentabilidad media",
        "probability_of_loss": "Probabilidad de pérdida",
        "value_at_risk": "VaR al final del horizonte",
        "conditional_value_at_risk": "CVaR al final del horizonte",
    }
    print("\nResumen de la simulación:")
    for key, value in result.summary().items():
        percentage = key in ("mean_return", "probability_of_loss")
        suffix = "" if percentage else f" {result.currency}"
        print(f"{labels[key]}: {format_number(value, percentage)}{suffix}")


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    args = parse_arguments()
    try:
        run_portfolio(args)
    except (ProviderError, ValueError, TypeError, OSError) as error:
        print(f"No se ha podido completar el análisis: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
