"""Estructura del informe: diez secciones, contexto de mercado y criterios de Monte Carlo."""

import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from fixtures import history, indicator

from src.analysis import WarningThresholds
from src.analysis.metrics import jensen_alpha
from src.analysis.warnings import evaluate_simulation
from src.errors import ConfigurationError
from src.main import main, parse_arguments
from src.market_loader import load_market_references, load_references, load_risk_free_rate
from src.models import Asset, ExchangeRate, FxRates, MarketReferences, Portfolio
from src.providers import AAA_3M_YIELD, EcbAPI, ProviderError, YahooFinanceAPI, is_ecb_series
from src.reporting.formatting import format_number
from src.reporting.plots import CHARTS, plot_report
from src.reporting.sections import SECTION_QUESTIONS, SECTION_TITLES
from src.reporting.texts import COSTS_NOTE, SIMULATION_LIMITATIONS, SIMULATION_NOT_CONFIGURED
from src.simulation import MODEL_RETURN, SimulationSettings

DATES = pd.bdate_range("2025-01-01", periods=120)
RANDOM = np.random.default_rng(7)


def walk(start=100.0, scale=0.01):
    return start * np.exp(np.cumsum(RANDOM.normal(0.0005, scale, len(DATES))))


def daily_rate(value):
    return indicator([value] * len(DATES), DATES, "Percent", "RATE")


def market_references(currency="USD"):
    """Todas las referencias, con las mismas fechas que la cartera."""
    return MarketReferences(
        benchmark=history("IDX", walk(), currency, dates=DATES, name="Índice de prueba"),
        inflation=indicator(
            100 + np.arange(len(DATES)) * 0.01, DATES, "Index 2015=100", "HICP", "Monthly"
        ),
        risk_free_rate=indicator([2.0] * len(DATES), DATES, "Percent", "DGS3MO"),
        vix=indicator(np.linspace(15, 35, len(DATES)), DATES, "Index", "VIXCLS"),
        brent=indicator(walk(70), DATES, "Dollars per Barrel", "BRENT"),
        gold=history("GC=F", walk(2000), dates=DATES),
        bund_etf=history("EXHD.DE", walk(50, 0.004), "EUR", dates=DATES),
    )


def portfolio(currency="USD", **options):
    assets = [
        Asset(history("A", walk(), currency, dates=DATES, sector="Technology")),
        Asset(history("B", walk(), currency, dates=DATES, sector="Energy")),
    ]
    return Portfolio(assets, {"A": 0.6, "B": 0.4}, **options)


class StructureTests(unittest.TestCase):
    def setUp(self):
        self.portfolio = portfolio()
        self.analysis = self.portfolio.analyze(market_references())
        self.addCleanup(plt.close, "all")

    def test_ten_sections_in_order_with_their_questions(self):
        text = self.analysis.markdown()
        positions = []
        for number, (key, title) in enumerate(SECTION_TITLES.items(), 1):
            summary = f"<summary><b>{number}. {title}</b> — {SECTION_QUESTIONS[key]}</summary>"
            self.assertIn(summary, text)
            positions.append(text.index(summary))
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(len(SECTION_TITLES), 10)

    def test_returns_section_details_each_asset_and_year(self):
        text = self.analysis.markdown(sections=["returns"])
        self.assertIn(
            "| Ticker | Rentabilidad total | CAGR | Volatilidad | Caída máxima | Beta |", text
        )
        row = self.analysis.asset_details.loc["A"]
        total = format_number(row["total_return"], True, signed=True)
        self.assertIn(f"| A | {total} |", text)
        # La historia empieza y acaba a mitad de año: no se presenta como un año completo.
        self.assertIn("| 2025 |", text)
        self.assertIn("| Parcial |", text)

    def test_costs_and_model_limits_are_stated(self):
        self.assertIn(COSTS_NOTE, self.analysis.markdown(sections=["composition"]))
        simulation = self.portfolio.monte_carlo(steps=5, simulations=10)
        with tempfile.TemporaryDirectory() as folder:
            path = self.analysis.report(simulation, sections=["simulation"], directory=folder)
            self.assertIn(SIMULATION_LIMITATIONS, path.read_text(encoding="utf-8"))

    def test_selected_sections_keep_their_number(self):
        text = self.analysis.markdown(sections=["risk", "data"])
        self.assertIn("<b>5. Riesgo</b>", text)
        self.assertIn("<b>10. Calidad de los datos</b>", text)
        self.assertNotIn("<b>1. Resumen</b>", text)

    def test_without_simulation_the_section_shows_the_notice(self):
        text = self.analysis.markdown(sections=["simulation"])
        self.assertIn(SIMULATION_NOT_CONFIGURED, text)
        self.assertIn("No se ha configurado la simulación", text)

    def test_market_section_has_context_and_every_chart_is_available(self):
        text = self.analysis.markdown(sections=["market"])
        for label in ("VIX actual", "Brent", "oro", "ETF de Bunds", "5 % de peores días"):
            self.assertIn(label, text)
        self.assertNotIn("| Correlación con el oro | No disponible", text)
        simulation = self.portfolio.monte_carlo(steps=5, simulations=10)
        figures = plot_report(self.analysis, simulation)
        self.assertEqual(set(figures), set(CHARTS))

    def test_missing_market_data_is_unavailable_and_skips_its_charts(self):
        analysis = self.portfolio.analyze()
        self.assertIn("| VIX actual | No disponible", analysis.markdown(sections=["market"]))
        figures = plot_report(analysis)
        self.assertNotIn("volatility_vix", figures)
        self.assertNotIn("bund_correlation", figures)

    def test_risk_free_rate_and_alpha(self):
        metrics = self.analysis.metrics
        self.assertAlmostEqual(metrics["reference_annualized_return"], 0.02, places=6)
        self.assertTrue(np.isfinite(metrics["alpha"]))
        text = self.analysis.markdown(sections=["risk_adjusted"])
        self.assertIn("Alfa de Jensen", text)
        self.assertIn("medio del periodo", text)
        euro = portfolio("EUR").analyze(
            replace(
                market_references(),
                risk_free_rate=indicator([2.0] * len(DATES), DATES, "Percent", AAA_3M_YIELD),
            )
        )
        self.assertIn(
            "Tipo libre de riesgo (deuda AAA de la zona euro a 3 meses), medio del periodo",
            euro.markdown(sections=["risk_adjusted"]),
        )

    def test_jensen_alpha_recovers_a_known_excess(self):
        index = pd.RangeIndex(100)
        market = pd.Series(RANDOM.normal(0, 0.01, 100), index=index)
        reference = pd.Series(0.0001, index=index)
        returns = reference + 1.5 * (market - reference) + 0.001
        self.assertAlmostEqual(jensen_alpha(returns, market, reference, 252), 0.252)
        self.assertTrue(np.isnan(jensen_alpha(returns, reference, reference, 252)))

    def test_missing_data_is_shown_without_units_and_without_inventing_an_index(self):
        text = portfolio().analyze().markdown(sections=["summary"])
        self.assertIn("**No disponible**", text)
        self.assertNotIn("No disponible/año", text)
        self.assertIn("referencia: sin índice", text)

    def test_summary_compares_with_the_risk_free_rate_in_every_currency(self):
        for currency in ("USD", "EUR"):
            text = portfolio(currency).analyze(market_references()).markdown(sections=["summary"])
            self.assertIn("Diferencia frente al tipo libre de riesgo", text)
            self.assertRegex(
                text, r"rindió [\d.,]+ p\. p\. (más|menos) que el tipo libre de riesgo"
            )
            self.assertNotIn("Bund", text)

    def test_german_debt_is_compared_with_what_the_etf_really_earned(self):
        prices = [100, 110, 105, 115]
        dates = DATES[:4]
        assets = [Asset(history("A", prices, "EUR", dates=dates))]
        falling = history("EXHD.DE", [100, 99, 98, 97], "EUR", dates=dates)
        references = MarketReferences(bund_etf=falling)
        analysis = Portfolio(assets, {"A": 1}).analyze(references)
        expected = 0.97 ** (252 / 3) - 1
        self.assertAlmostEqual(analysis.metrics["bund_etf_annualized_return"], expected)
        self.assertAlmostEqual(
            analysis.metrics["difference_from_bund_etf"],
            analysis.metrics["annualized_return"] - expected,
        )
        text = analysis.markdown(sections=["risk_adjusted"])
        self.assertIn("Diferencia frente a deuda alemana", text)
        self.assertIn("más que la deuda alemana (CAGR del ETF de Bunds:", text)

    def test_german_debt_is_compared_on_common_dates(self):
        dates = DATES[:5]
        assets = [Asset(history("A", [50, 100, 110, 121, 133.1], "EUR", dates=dates))]
        late = history("EXHD.DE", [100, 110, 121, 133.1], "EUR", dates=dates[1:])
        analysis = Portfolio(assets, {"A": 1}).analyze(MarketReferences(bund_etf=late))
        self.assertAlmostEqual(analysis.metrics["difference_from_bund_etf"], 0)

    def test_german_debt_is_only_compared_with_euro_portfolios(self):
        self.assertTrue(np.isnan(self.analysis.metrics["difference_from_bund_etf"]))
        self.assertNotIn("deuda alemana", self.analysis.markdown(sections=["risk_adjusted"]))
        text = self.analysis.markdown(sections=["summary"])
        self.assertIn(
            "Diferencia frente al tipo libre de riesgo (letra de EE. UU. a 3 meses)", text
        )

    def test_currency_effect_and_currency_risk(self):
        rate = [1 + 0.001 * day for day in range(len(DATES))]
        fx_rates = FxRates([ExchangeRate("USD", "EUR", indicator(rate, DATES))])
        mixed = Portfolio(
            [
                Asset(history("A", walk(), "USD", dates=DATES)),
                Asset(history("B", walk(), "EUR", dates=DATES)),
            ],
            {"A": 0.5, "B": 0.5},
            "EUR",
            fx_rates,
        ).analyze()
        self.assertEqual(list(mixed.market.fx_effect.index), ["A"])
        self.assertGreater(mixed.market.fx_effect["A"], 0)
        self.assertIn("Efecto divisa", mixed.markdown(sections=["market"]))
        self.assertIn("currency_risk", {warning.code for warning in mixed.risk_warnings})


class WarningRulesTests(unittest.TestCase):
    def codes(self, analysis):
        return {warning.code for warning in analysis.risk_warnings}

    def test_market_and_history_rules(self):
        analysis = portfolio().analyze(market_references())
        codes = self.codes(analysis)
        self.assertIn("market_stress", codes)
        self.assertIn("short_history", codes)
        relaxed = portfolio().analyze(
            market_references(), warning_thresholds=WarningThresholds(vix=50, short_history=10)
        )
        self.assertNotIn("market_stress", self.codes(relaxed))
        self.assertNotIn("short_history", self.codes(relaxed))

    def test_missing_data_does_not_trigger_rules(self):
        codes = self.codes(portfolio().analyze())
        for code in ("market_stress", "uncompensated_risk", "low_premium", "inflation_loss"):
            self.assertNotIn(code, codes)

    def test_simulation_rule_only_applies_with_a_simulation(self):
        item = portfolio()
        analysis = item.analyze(warning_thresholds=WarningThresholds(simulation_loss=0.001))
        title = "Escenarios desfavorables"
        self.assertNotIn(title, analysis.markdown(sections=["warnings"]))
        simulation = item.monte_carlo(steps=20, simulations=50)
        with tempfile.TemporaryDirectory() as folder:
            path = analysis.report(simulation, sections=["warnings"], directory=folder)
            self.assertIn(title, path.read_text(encoding="utf-8"))


class SimulationCriteriaTests(unittest.TestCase):
    def report(self, **options):
        item = portfolio()
        simulation = item.monte_carlo(**options)
        analysis = item.analyze()
        with tempfile.TemporaryDirectory() as folder:
            path = analysis.report(simulation, sections=["simulation"], directory=folder)
            return path.read_text(encoding="utf-8")

    def test_default_criteria_are_stated_with_the_command_to_change_them(self):
        text = self.report()
        self.assertIn("criterios por defecto: 10.000 escenarios, 252 sesiones", text)
        self.assertIn("confianza del 95 %, semilla 42 y retorno y volatilidad históricos", text)
        self.assertIn("python src/main.py --assets A:0.6 B:0.4 --simulate", text)

    def test_custom_criteria_are_not_presented_as_defaults(self):
        text = self.report(steps=10, simulations=20, seed=3, expected_returns=0.05)
        self.assertNotIn("criterios por defecto", text)
        self.assertIn("20 escenarios, 10 sesiones", text)
        self.assertIn("indicados por el usuario", text)
        self.assertIn("Retorno anual (supuesto)", text)


def classified(symbol, seed, **profile):
    closes = walk(100.0)
    return Asset(history(symbol, closes, "EUR", dates=DATES, **profile))


class ModelReturnTests(unittest.TestCase):
    def setUp(self):
        self.assets = {
            "STOCK": classified("STOCK", 1, asset_type="stock"),
            "BOND": classified("BOND", 2, asset_type="etf", equity_share=0.0),
            "MIXED": classified("MIXED", 3, asset_type="etf", equity_share=0.6),
            "GOLD": classified("GOLD", 4, asset_type="etf", equity_share=0.0),
            "ODD": classified("ODD", 5),
        }

    def simulate(self, **options):
        weights = dict.fromkeys(self.assets, 0.2)
        item = Portfolio(list(self.assets.values()), weights)
        return item.monte_carlo(steps=5, simulations=20, **options)

    def test_the_premium_only_applies_to_the_equity_part(self):
        result = self.simulate(risk_free_rate=0.02, equity_premium=0.05)
        returns = result.assumptions["annual_return"]
        self.assertAlmostEqual(returns["STOCK"], 0.07)
        self.assertAlmostEqual(returns["BOND"], 0.02)
        self.assertAlmostEqual(returns["MIXED"], 0.05)
        self.assertAlmostEqual(returns["GOLD"], 0.02)
        self.assertAlmostEqual(returns["ODD"], 0.02)
        self.assertTrue(np.isnan(result.assumptions.loc["ODD", "equity_share"]))

    def test_indexes_count_as_equity_and_unclassified_funds_do_not(self):
        self.assertEqual(classified("I", 1, asset_type="index").equity_share, 1)
        self.assertTrue(np.isnan(classified("F", 1, asset_type="fund").equity_share))

    def test_user_returns_override_the_model_only_where_indicated(self):
        result = self.simulate(risk_free_rate=0.02, expected_returns={"BOND": 0.03})
        self.assertAlmostEqual(result.assumptions.loc["BOND", "annual_return"], 0.03)
        self.assertEqual(result.assumptions.loc["BOND", "return_source"], "usuario")
        self.assertAlmostEqual(result.assumptions.loc["STOCK", "annual_return"], 0.065)
        self.assertEqual(result.assumptions.loc["STOCK", "return_source"], MODEL_RETURN)

    def test_without_a_risk_free_rate_the_return_is_historical(self):
        result = self.simulate()
        self.assertTrue((result.assumptions["return_source"] == "histórico").all())

    def test_settings_validate_the_premium(self):
        for premium in (-0.01, float("nan")):
            with self.assertRaises(ValueError):
                SimulationSettings(equity_premium=premium)

    def test_yahoo_profile_reads_the_composition_of_funds_only(self):
        history_frame = pd.DataFrame(
            {"Close": [1.0, 2.0]}, index=pd.bdate_range("2026-01-01", periods=2)
        )
        for quote, classes, expected in (
            ("ETF", {"bondPosition": 0.99, "cashPosition": 0.01}, 0.0),
            ("ETF", {"stockPosition": 0.62, "bondPosition": 0.37}, 0.62),
            ("MUTUALFUND", {"stockPosition": 1.0}, 1.0),
        ):
            with patch("src.providers.yahoo.yf.Ticker") as ticker:
                ticker.return_value.get_info.return_value = {"quoteType": quote, "currency": "EUR"}
                ticker.return_value.funds_data.asset_classes = classes
                ticker.return_value.history.return_value = history_frame
                result = YahooFinanceAPI().get_prices("X", "2026-01-01", "2026-01-03")
            self.assertAlmostEqual(result.profile.equity_share, expected)

    def test_yahoo_without_composition_leaves_the_fund_unclassified(self):
        history_frame = pd.DataFrame(
            {"Close": [1.0, 2.0]}, index=pd.bdate_range("2026-01-01", periods=2)
        )
        with patch("src.providers.yahoo.yf.Ticker") as ticker:
            ticker.return_value.get_info.return_value = {"quoteType": "ETF", "currency": "EUR"}
            type(ticker.return_value).funds_data = property(
                lambda _: (_ for _ in ()).throw(RuntimeError("sin datos"))
            )
            ticker.return_value.history.return_value = history_frame
            result = YahooFinanceAPI().get_prices("X", "2026-01-01", "2026-01-03")
        self.assertTrue(np.isnan(result.profile.equity_share))


class ReturnSensitivityTests(unittest.TestCase):
    def setUp(self):
        self.item = portfolio()

    def test_cases_use_the_same_scenarios_as_a_direct_simulation(self):
        options = dict(steps=30, simulations=200, seed=9, volatilities=0.25)
        result = self.item.monte_carlo(risk_free_rate=0.03, **options)
        self.assertEqual(list(result.return_sensitivity), ["historical", "risk_free"])
        direct = self.item.monte_carlo(expected_returns=0.03, **options).paths.iloc[-1]
        np.testing.assert_allclose(result.return_sensitivity["risk_free"], direct)

    def test_without_a_risk_free_rate_it_contrasts_fixed_returns(self):
        options = dict(steps=30, simulations=200, seed=9, volatilities=0.25)
        result = self.item.monte_carlo(**options)
        self.assertEqual(list(result.return_sensitivity), ["prudent", "zero"])
        direct = self.item.monte_carlo(expected_returns=0.08, **options).paths.iloc[-1]
        np.testing.assert_allclose(result.return_sensitivity["prudent"], direct)

    def test_it_does_not_change_the_main_simulation(self):
        options = dict(steps=10, simulations=50, seed=4, risk_free_rate=0.02)
        first = self.item.monte_carlo(**options)
        second = self.item.monte_carlo(**options)
        pd.testing.assert_frame_equal(first.paths, second.paths)

    def section(self, references=None, **options):
        simulation = self.item.monte_carlo(steps=252, simulations=200, **options)
        analysis = self.item.analyze(references)
        with tempfile.TemporaryDirectory() as folder:
            path = analysis.report(simulation, sections=["simulation"], directory=folder)
            return path.read_text(encoding="utf-8")

    def test_the_section_explains_the_model_and_shows_the_cases(self):
        text = self.section(risk_free_rate=0.02)
        self.assertIn("Retorno anual (tipo libre de riesgo + prima)", text)
        self.assertIn("| Tipo libre de riesgo + prima (el usado arriba) |", text)
        self.assertIn("| Histórico puro |", text)
        self.assertIn("| Solo tipo libre de riesgo |", text)
        self.assertIn("| Tipo libre de riesgo actual | 2,00 % |", text)
        self.assertIn("| Prima de riesgo | 4,50 % |", text)
        self.assertIn("Importes nominales", text)
        self.assertIn("No se ha podido clasificar A, B", text.replace("portfolio", ""))

    def test_without_a_rate_the_section_warns_that_the_return_is_historical(self):
        text = self.section()
        self.assertIn("**Retorno:** histórico", text)
        self.assertIn("| Histórico (el usado arriba) |", text)
        self.assertIn("| 8 % en todos los activos |", text)

    def test_real_loss_needs_a_year_of_inflation_and_is_higher_than_the_nominal(self):
        self.assertIn("no se calcula porque falta la inflación interanual", self.section())
        dates = pd.date_range("2024-01-01", DATES[-1], freq="MS")
        inflation = indicator(
            100 * 1.04 ** (np.arange(len(dates)) / 12), dates, "Index 2015=100", "HICP", "Monthly"
        )
        references = MarketReferences(inflation=inflation)
        analysis = self.item.analyze(references)
        self.assertAlmostEqual(analysis.metrics["latest_inflation"], 0.04, places=6)
        simulation = self.item.monte_carlo(steps=252, simulations=500, risk_free_rate=0.02)
        final = simulation.paths.iloc[-1]
        start = simulation.paths.iloc[0, 0]
        self.assertGreater((final < start * 1.04).mean(), (final < start).mean())
        text = self.section(references, risk_free_rate=0.02)
        self.assertIn("se supone una inflación anual del 4,00 %", text)

    def test_the_warning_no_longer_fires_for_a_normal_equity_portfolio(self):
        self.assertEqual(WarningThresholds().simulation_loss, 0.45)
        self.assertEqual(evaluate_simulation(0.40, WarningThresholds()), [])
        self.assertEqual(len(evaluate_simulation(0.50, WarningThresholds())), 1)


class RiskFreeRateTests(unittest.TestCase):
    def test_uses_the_last_rate_of_each_currency_as_a_fraction(self):
        fred, ecb = Mock(), Mock()
        dates = pd.DatetimeIndex(["2026-10-28", "2026-10-29", "2026-10-30"])
        fred.get_series.return_value = indicator([4.0, 4.2, np.nan], dates, name="DGS3MO")
        ecb.get_series.return_value = indicator([2.5, 2.6, 2.56], dates, name=AAA_3M_YIELD)
        usd = load_risk_free_rate("USD", "2026-10-31", fred_provider=fred, ecb_provider=ecb)
        eur = load_risk_free_rate("EUR", "2026-10-31", fred_provider=fred, ecb_provider=ecb)
        self.assertAlmostEqual(usd, 0.042)
        self.assertAlmostEqual(eur, 0.0256)
        self.assertEqual(ecb.get_series.call_args.args[0], AAA_3M_YIELD)

    def test_no_series_or_a_failure_mean_no_rate(self):
        fred = Mock()
        fred.get_series.side_effect = ProviderError("sin red")
        self.assertIsNone(load_risk_free_rate("USD", "2026-10-31", fred_provider=fred))
        self.assertIsNone(load_risk_free_rate("GBP", "2026-10-31"))
        with patch("src.market_loader.FredAPI", side_effect=ConfigurationError("Falta")):
            self.assertIsNone(load_risk_free_rate("USD", "2026-10-31"))

    def test_report_from_python_takes_the_rate_from_the_references(self):
        item = portfolio()
        references = MarketReferences(
            risk_free_rate=indicator([3.0] * len(DATES), DATES, "Percent", "DGS3MO")
        )
        self.assertAlmostEqual(references.latest_risk_free_rate, 0.03)
        self.assertIsNone(MarketReferences().latest_risk_free_rate)
        with tempfile.TemporaryDirectory() as folder:
            path = item.report(references, steps=5, simulations=10, directory=folder)
            self.assertIn(
                "| Tipo libre de riesgo actual | 3,00 % |", path.read_text(encoding="utf-8")
            )


class CommandLineTests(unittest.TestCase):
    def test_equity_premium_is_a_simulation_option(self):
        config = parse_arguments(["--assets", "A:1", "--simulate", "--equity-premium", "0.03"])
        self.assertEqual(config.simulation.equity_premium, 0.03)
        for arguments in (["--equity-premium", "0.03"], ["--simulate", "--equity-premium", "-1"]):
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                parse_arguments(["--assets", "A:1", *arguments])

    def test_the_console_uses_the_rate_and_warns_when_there_is_none(self):
        data = history("IBM", walk(), dates=DATES, asset_type="stock")
        for rate, expected in ((0.03, 0.075), (None, None)):
            with (
                patch("src.main.load_dotenv"),
                patch("src.main.YahooFinanceAPI") as yahoo,
                patch("src.main.load_risk_free_rate", return_value=rate),
                patch("src.main.Portfolio.monte_carlo", wraps=None) as simulate,
                patch("src.main.print_simulation"),
                redirect_stdout(io.StringIO()),
                redirect_stderr(io.StringIO()) as errors,
            ):
                yahoo.return_value.get_prices.return_value = data
                self.assertEqual(main(["--assets", "IBM:1", "--simulate"]), 0)
            settings = simulate.call_args.args[0]
            self.assertEqual(settings.risk_free_rate, rate)
            self.assertEqual("retorno histórico" in errors.getvalue(), expected is None)

    def test_benchmark_is_optional_and_needs_an_output(self):
        self.assertIsNone(parse_arguments(["--assets", "A:1", "--report"]).benchmark)
        config = parse_arguments(["--assets", "A:1", "--report", "--benchmark", "^IBEX"])
        self.assertEqual(config.benchmark, "^IBEX")
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parse_arguments(["--assets", "A:1", "--benchmark", "^IBEX"])

    def test_console_passes_benchmark_and_uses_prices_with_dividends(self):
        data = history(
            "IBM", [100, 100, 100, 100], extra={"Adj Close": [90, 95, 100, 110]}, name="IBM Corp"
        )
        with tempfile.TemporaryDirectory() as folder:
            reports = Path(folder) / "informes"
            with (
                patch("src.main.load_dotenv"),
                patch("src.main.YahooFinanceAPI") as yahoo,
                patch("src.main.load_references", return_value=MarketReferences()) as references,
                patch("src.main.load_risk_free_rate", return_value=None),
                redirect_stdout(io.StringIO()),
            ):
                yahoo.return_value.get_prices.return_value = data
                arguments = ["--assets", "IBM:1", "--report", "--benchmark", "^IBEX"]
                self.assertEqual(main([*arguments, "--output-dir", str(reports)]), 0)
            text = next(reports.glob("*/*.md")).read_text(encoding="utf-8")
        self.assertEqual(references.call_args.kwargs["benchmark_symbol"], "^IBEX")
        self.assertIn("**Precios:** Adj Close", text)
        self.assertIn("+22,22 %", text)


class EcbTests(unittest.TestCase):
    CSV = (
        "KEY,TIME_PERIOD,OBS_VALUE,TITLE\n"
        "A,2026-10-28,2.5,AAA\nA,2026-10-29,,AAA\nA,2026-10-30,2.6,AAA\n"
    )

    def session(self, text):
        session = Mock()
        session.get.return_value.text = text
        return session

    def test_reads_the_series_without_a_key_and_keeps_missing_values(self):
        session = self.session(self.CSV)
        result = EcbAPI(session=session).get_series(AAA_3M_YIELD, "2026-10-28", "2026-10-31")
        self.assertEqual(
            (result.units, result.frequency, result.source), ("Percent", "Daily", "ecb")
        )
        self.assertEqual(result.missing_count, 1)
        self.assertAlmostEqual(result.mean, 2.55)
        self.assertIn(AAA_3M_YIELD, session.get.call_args.args[0])

    def test_reuses_the_cache_and_excludes_the_final_date(self):
        session = self.session(self.CSV)
        with tempfile.TemporaryDirectory() as folder:
            api = EcbAPI(cache_dir=Path(folder), session=session)
            api.get_series(AAA_3M_YIELD, "2026-10-28", "2026-10-31")
            result = api.get_series(AAA_3M_YIELD, "2026-10-28", "2026-10-30")
        self.assertEqual(session.get.call_count, 1)
        self.assertEqual(result.values.index[-1], pd.Timestamp("2026-10-29"))

    def test_failures_and_unexpected_tables_are_provider_errors(self):
        failing = Mock()
        failing.get.side_effect = ConnectionError("sin red")
        for session in (failing, self.session("a,b\n1,2\n")):
            with self.assertRaises(ProviderError):
                EcbAPI(session=session).get_series(AAA_3M_YIELD, "2026-10-28", "2026-10-31")

    def test_identifiers_choose_the_source(self):
        self.assertTrue(is_ecb_series(AAA_3M_YIELD))
        self.assertFalse(is_ecb_series("DGS3MO"))
        fred, ecb = Mock(), Mock()
        rate = indicator([2.5], pd.DatetimeIndex(["2026-01-05"]), name=AAA_3M_YIELD)
        ecb.get_series.return_value = rate
        references = load_market_references(
            "2026-01-05",
            "2026-02-01",
            fred_provider=fred,
            ecb_provider=ecb,
            risk_free_series=AAA_3M_YIELD,
        )
        self.assertIs(references.risk_free_rate, rate)
        fred.get_series.assert_not_called()


class MarketLoaderTests(unittest.TestCase):
    def test_failed_context_downloads_are_notices_not_errors(self):
        with (
            patch("src.market_loader.load_market_references", return_value=MarketReferences()),
            patch("src.market_loader.FredAPI") as fred,
            patch("src.market_loader.YahooFinanceAPI") as yahoo,
        ):
            fred.return_value.get_series.side_effect = ProviderError("sin red")
            yahoo.return_value.get_prices.side_effect = ProviderError("sin red")
            references = load_references("EUR", "2026-01-01", "2026-02-01")
        self.assertIsNone(references.vix)
        messages = " ".join(notice.message for notice in references.notices)
        for name in ("VIX", "Brent", "Oro", "ETF de Bunds"):
            self.assertIn(name, messages)

    def test_without_a_fred_key_the_ecb_and_yahoo_series_are_still_loaded(self):
        ecb_rate = indicator([2.5], pd.DatetimeIndex(["2026-01-05"]), name=AAA_3M_YIELD)
        gold = history("GC=F", [100, 101, 102], "USD", dates=DATES[:3])
        with (
            patch("src.market_loader.FredAPI", side_effect=ConfigurationError("Falta")),
            patch("src.market_loader.YahooFinanceAPI") as yahoo,
            patch("src.market_loader.EcbAPI") as ecb,
        ):
            yahoo.return_value.get_prices.return_value = gold
            ecb.return_value.get_series.return_value = ecb_rate
            references = load_references("EUR", "2026-01-01", "2026-02-01")
        self.assertIs(references.risk_free_rate, ecb_rate)
        self.assertIsNotNone(references.gold)
        self.assertIsNone(references.vix)
        self.assertIsNone(references.inflation)
        self.assertTrue(any("FRED_API_KEY" in notice.message for notice in references.notices))

    def test_benchmark_in_another_currency_gets_its_exchange_rate(self):
        benchmark = history("^GSPC", [100, 101, 102], "USD", dates=DATES[:3])
        with (
            patch(
                "src.market_loader.load_market_references",
                return_value=MarketReferences(benchmark=benchmark),
            ),
            patch("src.market_loader.load_market_context", return_value=({}, [])),
            patch("src.market_loader.YahooFinanceAPI") as yahoo,
        ):
            yahoo.return_value.get_prices.return_value = history(
                "USDEUR=X", [0.9, 0.9, 0.9], "EUR", dates=DATES[:3]
            )
            references = load_references("EUR", "2025-01-01", "2025-02-01")
        rate = references.benchmark_fx.rates[0]
        self.assertEqual((rate.base_currency, rate.quote_currency), ("USD", "EUR"))
        same = Asset(history("A", [100, 110, 121], "EUR", dates=DATES[:3]))
        analysis = Portfolio([same], {"A": 1}).analyze(references)
        self.assertTrue(np.isfinite(analysis.metrics["beta"]))


if __name__ == "__main__":
    unittest.main()
