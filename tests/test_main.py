"""Pruebas de la interfaz simplificada sin consultar las API."""

import io
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests

from src.main import main, parse_arguments, parse_values
from src.models import EconomicIndicator, ExchangeRate, MarketContext, PriceHistory
from src.providers import AlphaVantageAPI, ProviderError, YahooFinanceAPI


class MainTests(unittest.TestCase):
    def test_monte_carlo_parameters_are_parsed_for_simulate_and_report(self):
        for action in ("--simulate", "--report"):
            with patch(
                "sys.argv",
                [
                    "main.py",
                    "--assets",
                    "IBM:0.6",
                    "MSFT:0.4",
                    action,
                    "--return",
                    "ibm:0.08",
                    "--volatility",
                    "0.2",
                    "--steps",
                    "63",
                    "--simulations",
                    "250",
                    "--confidence",
                    "0.99",
                    "--seed",
                    "7",
                    "--capital",
                    "20000",
                    "--rebalance",
                    "none",
                ],
            ):
                args = parse_arguments()
                self.assertEqual(args.expected_returns, {"IBM": 0.08})
                self.assertEqual(args.volatilities, 0.2)
                self.assertEqual(args.steps, 63)
                self.assertEqual(args.simulations, 250)
                self.assertEqual(args.confidence, 0.99)
                self.assertEqual(args.seed, 7)
                self.assertEqual(args.capital, 20000)
                self.assertIsNone(args.rebalance)

    def test_invalid_monte_carlo_parameters_fail_before_downloading(self):
        for options in (
            ["--return", "OTHER:0.1"],
            ["--return", "IBM:0.1", "ibm:0.2"],
            ["--return", "nan"],
            ["--volatility", "-0.1"],
            ["--volatility", "inf"],
            ["--confidence", "0.5"],
            ["--confidence", "1"],
            ["--confidence", "nan"],
            ["--capital", "0"],
            ["--steps", "0"],
            ["--simulations", "0"],
            ["--seed", "-1"],
        ):
            with (
                self.subTest(options=options),
                patch("sys.argv", ["main.py", "--assets", "IBM:1", "--report", *options]),
                patch("src.main.YahooFinanceAPI") as yahoo,
                redirect_stderr(io.StringIO()),
            ):
                with self.assertRaises(SystemExit):
                    parse_arguments()
                yahoo.assert_not_called()

    def test_report_uses_custom_simulation_parameters_without_simulate_flag(self):
        with (
            tempfile.TemporaryDirectory() as folder,
            patch("src.reporting.export.REPORTS_DIR", Path(folder) / "informes"),
            patch(
                "sys.argv",
                [
                    "main.py",
                    "--assets",
                    "IBM:1",
                    "--report",
                    "--return",
                    "0.08",
                    "--volatility",
                    "0",
                    "--steps",
                    "63",
                    "--simulations",
                    "5",
                    "--confidence",
                    "0.99",
                    "--seed",
                    "7",
                    "--capital",
                    "20000",
                ],
            ),
            patch("src.main.load_dotenv"),
            patch("src.main.YahooFinanceAPI") as yahoo,
            patch("src.main.load_report_context", return_value=MarketContext()),
            redirect_stdout(io.StringIO()),
        ):
            yahoo.return_value.get_prices.return_value = self.history
            self.assertEqual(main(), 0)
            path = next((Path(folder) / "informes").glob("*/*.md"))
            report = path.read_text(encoding="utf-8")
            self.assertTrue((path.parent / "distribucion_rentabilidades.png").is_file())
        for text in (
            "5 escenarios",
            "63 períodos",
            "Semilla aleatoria: 7",
            "20.000,00 USD",
            "| IBM | 8,00 % | usuario | 0,00 % | usuario |",
            "VaR al 99 %",
            "Percentil 1 del valor final",
            "Percentil 99 del valor final",
            "21 sesiones",
            "Autovalores (matriz singular)",
        ):
            self.assertIn(text, report)

    def test_text_file_and_console_weights_are_equivalent(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "mi cartera.txt"
            path.write_text(
                "# Pesos objetivo\nIBM:0.6\n\nMSFT:0.4 # Microsoft\n", encoding="utf-8-sig"
            )
            self.assertEqual(parse_values([str(path)]), parse_values(["IBM:0.6", "MSFT:0.4"]))

    def test_invalid_weight_files_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "cartera.txt"
            for text in (
                "",
                "# sin activos",
                "IBM:0.6",
                "IBM:0.5 ibm:0.5",
                "IBM:1.1 MSFT:-0.1",
                "IBM:nan",
                "IBM:true",
            ):
                with self.subTest(text=text):
                    path.write_text(text, encoding="utf-8")
                    with self.assertRaises(ValueError):
                        parse_values([str(path)])
            with self.assertRaises(ValueError):
                parse_values([str(path), "IBM:1"])
            with self.assertRaisesRegex(ValueError, "No se ha podido leer"):
                parse_values([str(Path(folder) / "no-existe.txt")])

    def test_weights_must_sum_to_one_without_automatic_normalization(self):
        for items in (["IBM:10", "MSFT:5"], ["IBM:0.6", "MSFT:0.3"], ["IBM:0.6", "MSFT:0.5"]):
            with self.assertRaises(ValueError):
                parse_values(items)
        self.assertEqual(parse_values(["IBM:1", "MSFT:0"]), {"IBM": 1, "MSFT": 0})

    def test_report_can_be_generated_from_a_text_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "cartera.txt"
            path.write_text("IBM:1\n", encoding="utf-8")
            with (
                patch("src.reporting.export.REPORTS_DIR", Path(folder) / "informes"),
                patch("sys.argv", ["main.py", "--assets", str(path), "--report", "--simulate"]),
                patch("src.main.load_dotenv"),
                patch("src.main.YahooFinanceAPI") as yahoo,
                patch("src.main.load_report_context", return_value=MarketContext()),
                redirect_stdout(io.StringIO()),
            ):
                yahoo.return_value.get_prices.return_value = self.history
                self.assertEqual(main(), 0)
            report = next((Path(folder) / "informes").glob("*/*.md")).read_text(encoding="utf-8")
            self.assertIn("Peso objetivo", report)
            self.assertIn("capital inicial de 10.000,00 USD", report)
            self.assertIn("Rebalanceo mensual", report)

    def setUp(self):
        self.dates = pd.date_range("2026-01-01", periods=4)
        self.history = PriceHistory(
            "IBM",
            "yahoo",
            pd.DataFrame({"Close": [100, 102, 99, 100]}, index=self.dates),
            info={"currency": "USD", "name": "International Business Machines", "beta": 0.8},
        )

    def test_holdings_summary_does_not_write_files(self):
        with (
            patch("sys.argv", ["main.py", "--assets", "IBM:1"]),
            patch("src.main.load_dotenv"),
            patch("src.main.YahooFinanceAPI") as yahoo,
            patch("pathlib.Path.write_text") as write_file,
            redirect_stdout(io.StringIO()) as output,
        ):
            yahoo.return_value.get_prices.return_value = self.history
            self.assertEqual(main(), 0)
        self.assertIn("Valor total: 10.000,00 USD", output.getvalue())
        self.assertIn("Peso", output.getvalue())
        write_file.assert_not_called()

    def test_simulation_uses_internal_defaults(self):
        with (
            patch("sys.argv", ["main.py", "--assets", "IBM:1", "--simulate"]),
            patch("src.main.load_dotenv"),
            patch("src.main.YahooFinanceAPI") as yahoo,
            patch("pathlib.Path.write_text") as write_file,
            redirect_stdout(io.StringIO()) as output,
        ):
            yahoo.return_value.get_prices.return_value = self.history
            self.assertEqual(main(), 0)
        self.assertIn("Resumen de la simulación", output.getvalue())
        write_file.assert_not_called()

    def test_provider_failure_returns_error_status(self):
        with (
            patch("sys.argv", ["main.py", "--assets", "IBM:1"]),
            patch("src.main.load_dotenv"),
            patch("src.main.YahooFinanceAPI") as yahoo,
            redirect_stdout(io.StringIO()) as output,
        ):
            yahoo.return_value.get_prices.side_effect = ProviderError("Servicio no disponible")
            self.assertEqual(main(), 1)
        self.assertIn("Servicio no disponible", output.getvalue())

    def test_invalid_inputs_fail_before_downloading(self):
        invalid = [
            [],
            ["--assets", "A:0"],
            ["--assets", "A:1", "a:2"],
            ["--assets", "A"],
            ["--assets", "A:nan"],
            ["--assets", "A:-1"],
            ["--assets", "A:1", "--provider", "fred"],
            ["--assets", "A:1", "--currency", "EU"],
            ["--assets", "A:1", "--start", "fecha incorrecta"],
            ["--assets", "A:1", "--start", "2026-10-03", "--end", "2026-10-01"],
            ["--assets", "A:1", "--start", "2026-10-01T12:00:00"],
        ]
        for arguments in invalid:
            with (
                self.subTest(arguments=arguments),
                patch("sys.argv", ["main.py", *arguments]),
                patch("src.main.load_dotenv"),
                patch("src.main.YahooFinanceAPI") as yahoo,
                redirect_stderr(io.StringIO()),
            ):
                with self.assertRaises(SystemExit) as error:
                    main()
                self.assertEqual(error.exception.code, 2)
                yahoo.assert_not_called()

    def test_advanced_options_are_no_longer_accepted(self):
        options = {
            "--symbol": "IBM",
            "--series-id": "DGS10",
            "--expected-returns": "IBM:0.1",
            "--volatilities": "IBM:0.2",
            "--periods-per-year": "12",
            "--return-column": "Adj Close",
            "--benchmark": "SPY",
            "--inflation-series": "CPIAUCSL",
            "--risk-free-series": "DGS3MO",
            "--fx-series": "EUR/USD:DEXUSEU",
            "--reporting-currency": "EUR",
            "--outputsize": "full",
            "--adjusted": None,
            "--allow-partial": None,
            "--refresh": None,
            "--company-info": None,
            "--plot": None,
            "--analysis-plot": None,
        }
        for option, value in options.items():
            arguments = ["main.py", "--assets", "IBM:1", option]
            if value is not None:
                arguments.append(value)
            with (
                self.subTest(option=option),
                patch("sys.argv", arguments),
                redirect_stderr(io.StringIO()),
            ):
                with self.assertRaises(SystemExit):
                    parse_arguments()

    def test_default_history_depends_on_the_provider(self):
        for provider, days in (("yahoo", 365), ("alpha_vantage", 120)):
            with patch("sys.argv", ["main.py", "--provider", provider, "--assets", "IBM:1"]):
                args = parse_arguments()
            start = pd.Timestamp(args.start)
            self.assertEqual((pd.Timestamp(args.end) - start).days, days)

    def test_currency_is_normalized_as_a_target_currency(self):
        with patch("sys.argv", ["main.py", "--assets", "IBM:1", "--currency", "eur"]):
            self.assertEqual(parse_arguments().currency, "EUR")

    def test_both_providers_support_one_or_multiple_assets_and_all_outputs(self):
        for name in ("yahoo", "alpha_vantage"):
            for symbols in (("IBM",), ("IBM", "MSFT")):
                with self.subTest(provider=name, symbols=symbols):
                    histories = [
                        PriceHistory(symbol, "yahoo", self.history.prices, info=self.history.info)
                        for symbol in symbols
                    ]
                    yahoo = Mock(spec=YahooFinanceAPI)
                    yahoo.get_prices.side_effect = histories
                    session = Mock(spec=requests.Session)
                    responses = []
                    for history in histories:
                        payloads = [
                            {
                                "Time Series (Daily)": {
                                    date.strftime("%Y-%m-%d"): {"4. close": str(price)}
                                    for date, price in history.closing_prices().items()
                                }
                            },
                            {
                                "Symbol": history.symbol,
                                "Name": history.symbol,
                                "Currency": "USD",
                                "Beta": "0.8",
                                "AssetType": "Common Stock",
                            },
                        ]
                        for payload in payloads:
                            response = Mock()
                            response.json.return_value = payload
                            responses.append(response)
                    session.get.side_effect = responses
                    alpha = AlphaVantageAPI("test-key", session=session, include_info=True)
                    arguments = [
                        "main.py",
                        "--provider",
                        name,
                        "--assets",
                        *[f"{symbol}:{1 / len(symbols)}" for symbol in symbols],
                        "--start",
                        "2026-01-01",
                        "--end",
                        "2026-01-05",
                        "--simulate",
                        "--plots-report",
                        "--report",
                    ]
                    with (
                        tempfile.TemporaryDirectory() as folder,
                        patch("src.reporting.export.REPORTS_DIR", Path(folder) / "informes"),
                        patch("sys.argv", arguments),
                        patch("src.main.load_dotenv"),
                        patch("src.main.YahooFinanceAPI", return_value=yahoo) as yahoo_factory,
                        patch("src.main.AlphaVantageAPI", return_value=alpha) as alpha_factory,
                        patch("src.providers.base.time.sleep"),
                        patch("src.main.load_report_context", return_value=MarketContext()),
                        patch("matplotlib.pyplot.show") as show,
                        redirect_stdout(io.StringIO()) as output,
                    ):
                        try:
                            self.assertEqual(main(), 0, output.getvalue())
                            path = next((Path(folder) / "informes").glob("*/*.md"))
                            report = path.read_text(encoding="utf-8")
                            self.assertEqual(len(list(path.parent.glob("*.png"))), 4)
                            self.assertIn("Simulación de Monte Carlo", report)
                            self.assertIn("Retorno anual μ", report)
                            for symbol in symbols:
                                self.assertIn(symbol, report)
                        finally:
                            plt.close("all")
                    show.assert_called_once()
                    if name == "alpha_vantage":
                        alpha_factory.assert_called_once()
                        self.assertTrue(alpha_factory.call_args.kwargs["include_info"])
                        yahoo_factory.assert_not_called()
                        self.assertEqual(session.get.call_count, 2 * len(symbols))
                        self.assertIn("Fuente: Alpha Vantage", report)
                        self.assertIn("distorsione las rentabilidades", report)
                    else:
                        yahoo_factory.assert_called_once()
                        alpha_factory.assert_not_called()
                        self.assertEqual(yahoo.get_prices.call_count, len(symbols))
                        self.assertIn("Fuente: Yahoo Finance", report)

    def test_alpha_without_key_reports_the_problem_without_switching_provider(self):
        with (
            patch("sys.argv", ["main.py", "--provider", "alpha_vantage", "--assets", "IBM:1"]),
            patch("src.main.load_dotenv"),
            patch(
                "src.main.AlphaVantageAPI",
                side_effect=ValueError("Configura ALPHA_VANTAGE_API_KEY"),
            ),
            patch("src.main.YahooFinanceAPI") as yahoo,
            redirect_stdout(io.StringIO()) as output,
        ):
            self.assertEqual(main(), 1)
        self.assertIn("ALPHA_VANTAGE_API_KEY", output.getvalue())
        yahoo.assert_not_called()

    def test_direct_script_runs_from_another_directory(self):
        script = Path(__file__).resolve().parents[1] / "src" / "main.py"
        with tempfile.TemporaryDirectory() as folder:
            result = subprocess.run(
                [sys.executable, str(script), "--help"],
                cwd=folder,
                capture_output=True,
                text=True,
                timeout=30,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--plots-report", result.stdout)
        self.assertIn("--provider", result.stdout)

    def test_report_includes_company_details_estimates_and_default_simulation(self):
        with (
            tempfile.TemporaryDirectory() as folder,
            patch("src.reporting.export.REPORTS_DIR", Path(folder) / "informes"),
            patch("sys.argv", ["main.py", "--assets", "IBM:1", "--report"]),
            patch("src.main.load_dotenv"),
            patch("src.main.YahooFinanceAPI") as yahoo,
            patch("src.main.load_report_context", return_value=MarketContext()) as context,
            redirect_stdout(io.StringIO()),
        ):
            yahoo.return_value.get_prices.return_value = self.history
            self.assertEqual(main(), 0)
            path = next((Path(folder) / "informes").glob("*/*.md"))
            report = path.read_text(encoding="utf-8")
            self.assertEqual(len(list(path.parent.glob("*.png"))), 4)
        context.assert_called_once()
        self.assertIn("International Business Machines", report)
        self.assertIn("Retorno anual μ", report)
        self.assertIn("Configuración utilizada", report)

    def test_report_includes_simulation_and_its_settings(self):
        with (
            tempfile.TemporaryDirectory() as folder,
            patch("src.reporting.export.REPORTS_DIR", Path(folder) / "informes"),
            patch("sys.argv", ["main.py", "--assets", "IBM:1", "--simulate", "--report"]),
            patch("src.main.load_dotenv"),
            patch("src.main.YahooFinanceAPI") as yahoo,
            patch("src.main.load_report_context", return_value=MarketContext()),
            redirect_stdout(io.StringIO()),
        ):
            yahoo.return_value.get_prices.return_value = self.history
            self.assertEqual(main(), 0)
            path = next((Path(folder) / "informes").glob("*/*.md"))
            report = path.read_text(encoding="utf-8")
            self.assertEqual(len(list(path.parent.glob("*.png"))), 4)
        self.assertIn("1000 escenarios", report)
        self.assertIn("252 períodos", report)
        self.assertIn("Semilla aleatoria: 42", report)

    def test_plots_report_shows_figures_without_creating_markdown(self):
        with (
            patch("sys.argv", ["main.py", "--assets", "IBM:1", "--simulate", "--plots-report"]),
            patch("src.main.load_dotenv"),
            patch("src.main.YahooFinanceAPI") as yahoo,
            patch("src.main.load_report_context") as context,
            patch("pathlib.Path.write_text") as write_file,
            patch("matplotlib.pyplot.show") as show,
            redirect_stdout(io.StringIO()),
        ):
            yahoo.return_value.get_prices.return_value = self.history
            try:
                self.assertEqual(main(), 0)
                self.assertEqual(len(plt.get_fignums()), 4)
            finally:
                plt.close("all")
        show.assert_called_once()
        write_file.assert_not_called()
        context.assert_not_called()

    def test_currency_conversion_is_loaded_automatically(self):
        indicator = EconomicIndicator(
            "USDEUR=X",
            "yahoo",
            pd.Series([0.9] * 4, index=self.dates),
            "EUR por USD",
            "Daily",
        )
        context = MarketContext(exchange_rates=[ExchangeRate("USD", "EUR", indicator)])
        with (
            patch("sys.argv", ["main.py", "--assets", "IBM:1", "--currency", "EUR"]),
            patch("src.main.load_dotenv"),
            patch("src.main.YahooFinanceAPI") as yahoo,
            patch("src.portfolio_loader.load_currency_context", return_value=context) as exchange,
            redirect_stdout(io.StringIO()) as output,
        ):
            yahoo.return_value.get_prices.return_value = self.history
            self.assertEqual(main(), 0)
        self.assertEqual(exchange.call_args.args[1], "EUR")
        self.assertIn("Valor total: 10.000,00 EUR", output.getvalue())
        np.testing.assert_allclose(self.history.prices["Close"], [100, 102, 99, 100])
