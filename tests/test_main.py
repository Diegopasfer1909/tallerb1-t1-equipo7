"""Pruebas de la interfaz de consola sin consultar las API."""

import io
import os
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

from src.errors import ConfigurationError
from src.main import build_parser, check_api_keys, main, parse_arguments, parse_values
from src.models import (
    AssetProfile,
    EconomicIndicator,
    ExchangeRate,
    FxRates,
    MarketReferences,
    PriceHistory,
)
from src.providers import AlphaVantageAPI, ProviderError, YahooFinanceAPI


class MainTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        usage = patch.dict(
            os.environ, {"ALPHA_VANTAGE_USAGE_DB": str(Path(folder.name) / "usage.sqlite3")}
        )
        usage.start()
        self.addCleanup(usage.stop)
        self.dates = pd.date_range("2026-01-01", periods=4)
        self.history = PriceHistory(
            "IBM",
            "yahoo",
            pd.DataFrame({"Close": [100, 102, 99, 100]}, index=self.dates),
            profile=AssetProfile(currency="USD", name="International Business Machines", beta=0.8),
        )

    def test_monte_carlo_parameters_are_parsed_for_simulate_and_report(self):
        for action in ("--simulate", "--report"):
            config = parse_arguments(
                [
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
                ]
            )
            settings = config.simulation
            self.assertEqual(settings.expected_returns, {"IBM": 0.08})
            self.assertEqual(settings.volatilities, 0.2)
            self.assertEqual(settings.steps, 63)
            self.assertEqual(settings.simulations, 250)
            self.assertEqual(settings.confidence, 0.99)
            self.assertEqual(settings.seed, 7)
            self.assertEqual(config.capital, 20000)
            self.assertIsNone(config.rebalance)

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
                patch("src.main.YahooFinanceAPI") as yahoo,
                redirect_stderr(io.StringIO()),
            ):
                with self.assertRaises(SystemExit):
                    parse_arguments(["--assets", "IBM:1", "--report", *options])
                yahoo.assert_not_called()

    def test_simulation_options_require_a_simulation_even_with_default_values(self):
        for options in (["--steps", "252"], ["--seed", "42"], ["--confidence", "0.95"]):
            with self.subTest(options=options), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    parse_arguments(["--assets", "IBM:1", *options])

    def test_presentation_options_require_report(self):
        for options in (["--report-detail", "compact"], ["--output-dir", "informes"]):
            with self.subTest(options=options), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    parse_arguments(["--assets", "IBM:1", *options])

    def test_report_uses_custom_simulation_parameters_without_simulate_flag(self):
        with tempfile.TemporaryDirectory() as folder:
            reports = Path(folder) / "informes"
            with (
                patch("src.main.load_dotenv"),
                patch("src.main.YahooFinanceAPI") as yahoo,
                patch("src.main.load_references", return_value=MarketReferences()),
                redirect_stdout(io.StringIO()),
            ):
                yahoo.return_value.get_prices.return_value = self.history
                arguments = [
                    "--assets",
                    "IBM:1",
                    "--report",
                    "--output-dir",
                    str(reports),
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
                ]
                self.assertEqual(main(arguments), 0)
            path = next(reports.glob("*/*.md"))
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
            reports = Path(folder) / "informes"
            with (
                patch("src.main.load_dotenv"),
                patch("src.main.YahooFinanceAPI") as yahoo,
                patch("src.main.load_references", return_value=MarketReferences()),
                redirect_stdout(io.StringIO()),
            ):
                yahoo.return_value.get_prices.return_value = self.history
                arguments = ["--assets", str(path), "--report", "--simulate"]
                self.assertEqual(main([*arguments, "--output-dir", str(reports)]), 0)
            report = next(reports.glob("*/*.md")).read_text(encoding="utf-8")
            self.assertIn("Peso objetivo", report)
            self.assertIn("capital inicial de 10.000,00 USD", report)
            self.assertIn("Rebalanceo mensual", report)

    def test_holdings_summary_does_not_write_files(self):
        with (
            patch("src.main.load_dotenv"),
            patch("src.main.YahooFinanceAPI") as yahoo,
            patch("pathlib.Path.write_text") as write_file,
            redirect_stdout(io.StringIO()) as output,
        ):
            yahoo.return_value.get_prices.return_value = self.history
            self.assertEqual(main(["--assets", "IBM:1"]), 0)
        self.assertIn("Valor total: 10.000,00 USD", output.getvalue())
        self.assertIn("Peso objetivo", output.getvalue())
        write_file.assert_not_called()

    def test_simulation_uses_internal_defaults(self):
        with (
            patch("src.main.load_dotenv"),
            patch("src.main.YahooFinanceAPI") as yahoo,
            patch("pathlib.Path.write_text") as write_file,
            redirect_stdout(io.StringIO()) as output,
        ):
            yahoo.return_value.get_prices.return_value = self.history
            self.assertEqual(main(["--assets", "IBM:1", "--simulate"]), 0)
        self.assertIn("Resumen de la simulación", output.getvalue())
        write_file.assert_not_called()

    def test_provider_failure_returns_error_status_on_stderr(self):
        with (
            patch("src.main.load_dotenv"),
            patch("src.main.YahooFinanceAPI") as yahoo,
            redirect_stdout(io.StringIO()) as output,
            redirect_stderr(io.StringIO()) as errors,
        ):
            yahoo.return_value.get_prices.side_effect = ProviderError("Servicio no disponible")
            self.assertEqual(main(["--assets", "IBM:1"]), 1)
        self.assertIn("Servicio no disponible", errors.getvalue())
        self.assertNotIn("Servicio no disponible", output.getvalue())

    def test_programming_errors_are_not_reported_as_user_errors(self):
        with (
            patch("src.main.load_dotenv"),
            patch("src.main.run", side_effect=TypeError("fallo interno")),
        ):
            with self.assertRaises(TypeError):
                main(["--assets", "IBM:1"])

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
                patch("src.main.load_dotenv"),
                patch("src.main.YahooFinanceAPI") as yahoo,
                redirect_stderr(io.StringIO()),
            ):
                with self.assertRaises(SystemExit) as error:
                    main(arguments)
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
            arguments = ["--assets", "IBM:1", option]
            if value is not None:
                arguments.append(value)
            with self.subTest(option=option), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    parse_arguments(arguments)

    def test_default_history_depends_on_the_provider(self):
        for provider, days in (("yahoo", 365), ("alpha_vantage", 120)):
            config = parse_arguments(["--provider", provider, "--assets", "IBM:1"])
            start = pd.Timestamp(config.start)
            self.assertEqual((pd.Timestamp(config.end) - start).days, days)

    def test_currency_is_normalized_as_a_target_currency(self):
        config = parse_arguments(["--assets", "IBM:1", "--currency", "eur"])
        self.assertEqual(config.currency, "EUR")

    def test_help_describes_the_program(self):
        self.assertIn("Analiza una cartera", build_parser().format_help())

    def test_both_providers_support_one_or_multiple_assets_and_all_outputs(self):
        for name in ("yahoo", "alpha_vantage"):
            for symbols in (("IBM",), ("IBM", "MSFT")):
                with self.subTest(provider=name, symbols=symbols):
                    histories = [
                        PriceHistory(
                            symbol, "yahoo", self.history.prices, profile=self.history.profile
                        )
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
                    with tempfile.TemporaryDirectory() as folder:
                        reports = Path(folder) / "informes"
                        arguments = [
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
                            "--output-dir",
                            str(reports),
                        ]
                        with (
                            patch("src.main.load_dotenv"),
                            patch("src.main.YahooFinanceAPI", return_value=yahoo) as yahoo_factory,
                            patch("src.main.AlphaVantageAPI", return_value=alpha) as alpha_factory,
                            patch("src.providers.base.time.sleep"),
                            patch.dict(os.environ, {"ALPHA_VANTAGE_API_KEY": "test-key"}),
                            patch("src.main.load_references", return_value=MarketReferences()),
                            patch("matplotlib.pyplot.show") as show,
                            redirect_stdout(io.StringIO()) as output,
                        ):
                            try:
                                self.assertEqual(main(arguments), 0, output.getvalue())
                                path = next(reports.glob("*/*.md"))
                                report = path.read_text(encoding="utf-8")
                                self.assertEqual(len(list(path.parent.glob("*.png"))), 5)
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

    def test_alpha_without_key_stops_before_downloading_and_suggests_yahoo(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("src.main.load_dotenv"),
            patch("src.main.AlphaVantageAPI") as alpha,
            patch("src.main.YahooFinanceAPI") as yahoo,
            redirect_stderr(io.StringIO()) as errors,
        ):
            self.assertEqual(main(["--provider", "alpha_vantage", "--assets", "IBM:1"]), 1)
        self.assertIn("ALPHA_VANTAGE_API_KEY", errors.getvalue())
        self.assertIn("--provider yahoo", errors.getvalue())
        alpha.assert_not_called()
        yahoo.assert_not_called()

    def test_rejected_key_is_reported_without_switching_provider(self):
        with (
            patch.dict(os.environ, {"ALPHA_VANTAGE_API_KEY": "test-key"}),
            patch("src.main.load_dotenv"),
            patch(
                "src.main.AlphaVantageAPI",
                side_effect=ConfigurationError("Configura ALPHA_VANTAGE_API_KEY"),
            ),
            patch("src.main.YahooFinanceAPI") as yahoo,
            redirect_stderr(io.StringIO()) as errors,
        ):
            self.assertEqual(main(["--provider", "alpha_vantage", "--assets", "IBM:1"]), 1)
        self.assertIn("ALPHA_VANTAGE_API_KEY", errors.getvalue())
        yahoo.assert_not_called()

    def test_report_without_fred_key_warns_and_keeps_what_it_can(self):
        benchmark = PriceHistory(
            "^GSPC",
            "yahoo",
            pd.DataFrame({"Close": [100, 101, 99, 102]}, index=self.dates),
            profile=AssetProfile(currency="USD"),
        )
        with tempfile.TemporaryDirectory() as folder:
            reports = Path(folder) / "informes"
            with (
                patch.dict(os.environ, {}, clear=True),
                patch("src.main.load_dotenv"),
                patch("src.main.YahooFinanceAPI") as yahoo,
                patch("src.market_loader.YahooFinanceAPI") as index_provider,
                patch("src.providers.alfred.AlfredAPI._query") as alfred_requests,
                redirect_stdout(io.StringIO()),
                redirect_stderr(io.StringIO()) as errors,
            ):
                yahoo.return_value.get_prices.return_value = self.history
                index_provider.return_value.get_prices.return_value = benchmark
                arguments = ["--assets", "IBM:1", "--report", "--report-sections", "summary"]
                self.assertEqual(main([*arguments, "warnings", "--output-dir", str(reports)]), 0)
            report = next(reports.glob("*/*.md")).read_text(encoding="utf-8")
        alfred_requests.assert_not_called()
        self.assertIn("Aviso: FRED_API_KEY no está configurada", errors.getvalue())
        self.assertIn("porque falta FRED_API_KEY", report)
        self.assertIn("Comparación con el índice", report)

    def test_no_key_warnings_when_the_keys_are_configured(self):
        keys = {"ALPHA_VANTAGE_API_KEY": "a", "FRED_API_KEY": "f"}
        config = parse_arguments(["--provider", "alpha_vantage", "--assets", "IBM:1", "--report"])
        with patch.dict(os.environ, keys):
            self.assertEqual(check_api_keys(config), [])
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ConfigurationError):
                check_api_keys(config)
        yahoo = parse_arguments(["--assets", "IBM:1"])
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(check_api_keys(yahoo), [])

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
        with tempfile.TemporaryDirectory() as folder:
            reports = Path(folder) / "informes"
            with (
                patch("src.main.load_dotenv"),
                patch("src.main.YahooFinanceAPI") as yahoo,
                patch("src.main.load_references", return_value=MarketReferences()) as references,
                redirect_stdout(io.StringIO()),
            ):
                yahoo.return_value.get_prices.return_value = self.history
                self.assertEqual(
                    main(["--assets", "IBM:1", "--report", "--output-dir", str(reports)]), 0
                )
            path = next(reports.glob("*/*.md"))
            report = path.read_text(encoding="utf-8")
            self.assertEqual(len(list(path.parent.glob("*.png"))), 5)
        references.assert_called_once()
        self.assertIn("International Business Machines", report)
        self.assertIn("Retorno anual μ", report)
        self.assertIn("Configuración utilizada", report)

    def test_report_includes_simulation_and_its_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            reports = Path(folder) / "informes"
            with (
                patch("src.main.load_dotenv"),
                patch("src.main.YahooFinanceAPI") as yahoo,
                patch("src.main.load_references", return_value=MarketReferences()),
                redirect_stdout(io.StringIO()),
            ):
                yahoo.return_value.get_prices.return_value = self.history
                arguments = ["--assets", "IBM:1", "--simulate", "--report"]
                self.assertEqual(main([*arguments, "--output-dir", str(reports)]), 0)
            path = next(reports.glob("*/*.md"))
            report = path.read_text(encoding="utf-8")
            self.assertEqual(len(list(path.parent.glob("*.png"))), 5)
        self.assertIn("1000 escenarios", report)
        self.assertIn("252 períodos", report)
        self.assertIn("Semilla aleatoria: 42", report)

    def test_plots_report_shows_figures_without_creating_markdown(self):
        with (
            patch("src.main.load_dotenv"),
            patch("src.main.YahooFinanceAPI") as yahoo,
            patch("src.main.load_references") as references,
            patch("pathlib.Path.write_text") as write_file,
            patch("matplotlib.pyplot.show") as show,
            redirect_stdout(io.StringIO()),
        ):
            yahoo.return_value.get_prices.return_value = self.history
            try:
                self.assertEqual(main(["--assets", "IBM:1", "--simulate", "--plots-report"]), 0)
                self.assertEqual(len(plt.get_fignums()), 5)
            finally:
                plt.close("all")
        show.assert_called_once()
        write_file.assert_not_called()
        references.assert_not_called()

    def test_currency_conversion_is_loaded_automatically(self):
        indicator = EconomicIndicator(
            "USDEUR=X",
            "yahoo",
            pd.Series([0.9] * 4, index=self.dates),
            "EUR por USD",
            "Daily",
        )
        fx_rates = FxRates([ExchangeRate("USD", "EUR", indicator)])
        with (
            patch("src.main.load_dotenv"),
            patch("src.main.YahooFinanceAPI") as yahoo,
            patch("src.portfolio_loader.load_fx_rates", return_value=fx_rates) as exchange,
            redirect_stdout(io.StringIO()) as output,
        ):
            yahoo.return_value.get_prices.return_value = self.history
            self.assertEqual(main(["--assets", "IBM:1", "--currency", "EUR"]), 0)
        self.assertEqual(exchange.call_args.args[1], "EUR")
        self.assertIn("Valor total: 10.000,00 EUR", output.getvalue())
        np.testing.assert_allclose(self.history.prices["Close"], [100, 102, 99, 100])
