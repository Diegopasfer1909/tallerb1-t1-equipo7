"""Monte Carlo estima σ y correlaciones con su propio período, sin cambiar el del análisis."""

import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import matplotlib
import numpy as np
import pandas as pd

from src.commissions import IBKR_COMMISSIONS, RebalanceRule
from src.errors import PortfolioError
from src.main import main, parse_arguments
from src.models import Asset, AssetProfile, MarketReferences, Portfolio, PriceHistory

matplotlib.use("Agg")

# Sesiones bursátiles: con días naturales la cartera parecería de criptomonedas.
LONG_DATES = pd.bdate_range("2020-06-01", "2026-01-06")


def walk(seed: int, volatility: float) -> np.ndarray:
    returns = np.random.default_rng(seed).normal(0.0003, volatility, len(LONG_DATES))
    return 100 * np.cumprod(1 + returns)


LONG_PRICES = {"A": walk(1, 0.02), "B": walk(2, 0.01)}


def price_history(symbol: str, start: str | None = None, end: str | None = None) -> PriceHistory:
    """Historial completo o el tramo [start, end) que devolvería un proveedor."""
    prices = pd.DataFrame({"Close": LONG_PRICES[symbol]}, index=LONG_DATES)
    if start is not None:
        prices = prices.loc[(prices.index >= start) & (prices.index < end)]
    return PriceHistory(symbol, "yahoo", prices, profile=AssetProfile(currency="USD", name=symbol))


def provider_prices(symbol, start, end, **_):
    return price_history(symbol, start, end)


class PortfolioEstimationTests(unittest.TestCase):
    def setUp(self):
        self.rule = RebalanceRule(IBKR_COMMISSIONS, band=0.05, max_order_cost=0.01)
        analysis = [Asset(price_history(s, "2025-10-01", "2026-01-07")) for s in ("A", "B")]
        self.portfolio = Portfolio.from_units(
            analysis, {"A": 10, "B": 5}, rebalance="monthly", rebalance_rule=self.rule
        )
        long = [Asset(price_history(s)) for s in ("A", "B")]
        self.long_prices = Portfolio(long, {"A": 0.5, "B": 0.5}).close_prices()

    def simulate(self, estimation_prices=None):
        return self.portfolio.monte_carlo(
            estimation_prices=estimation_prices, simulations=200, steps=42, seed=3
        )

    def test_volatility_and_correlations_come_from_the_estimation_prices(self):
        result = self.simulate(self.long_prices)
        returns = self.long_prices.pct_change().dropna()
        np.testing.assert_allclose(
            result.assumptions["annual_volatility"],
            returns.std() * np.sqrt(252),
        )
        np.testing.assert_allclose(result.correlation, returns.corr())
        self.assertEqual(result.estimation_start, LONG_DATES[0])
        self.assertEqual(result.estimation_end, self.portfolio.valuation_date)
        self.assertEqual(result.estimation_returns, len(self.long_prices) - 1)
        self.assertGreater(result.estimation_years, 5)

    def test_the_simulation_keeps_the_analysed_positions_and_rebalancing(self):
        result = self.simulate(self.long_prices)
        # Valor actual de las posiciones y pesos de las acciones al inicio del análisis, no
        # los que darían esas acciones al inicio de la estimación.
        pd.testing.assert_series_equal(
            result.starting_values, self.portfolio.holdings()["value"], check_names=False
        )
        np.testing.assert_allclose(result.target_weights, self.portfolio.target_weights)
        self.assertEqual(list(result.target_weights.index), ["A", "B"])
        first = self.long_prices.iloc[0] * pd.Series({"A": 10, "B": 5})
        self.assertFalse(np.allclose(result.target_weights, first / first.sum()))
        self.assertEqual(result.rebalance_rule, self.rule)
        self.assertEqual(result.rebalance_interval, 21)
        self.assertEqual(result.valuation_date, self.portfolio.valuation_date)

    def test_without_estimation_prices_the_analysis_period_is_used(self):
        result = self.simulate()
        self.assertEqual(result.estimation_start, self.portfolio.close_prices().index[0])
        self.assertLess(result.estimation_years, 1)

    def test_estimation_prices_must_match_the_portfolio(self):
        for prices in (
            self.long_prices[["A"]],
            self.long_prices.rename(columns={"B": "C"}),
            self.long_prices.iloc[:-1],
            self.long_prices.iloc[:0],
            self.long_prices["A"],
        ):
            with self.subTest(columns=getattr(prices, "columns", None)):
                with self.assertRaises(PortfolioError):
                    self.simulate(prices)


class ConsoleEstimationTests(unittest.TestCase):
    def test_yahoo_estimates_with_five_years_unless_the_analysis_is_longer(self):
        end = date(2026, 1, 7)
        five_years = (end - timedelta(days=1826)).isoformat()
        cases = (
            (["--simulate"], five_years),
            (["--report"], five_years),
            (["--simulate", "--start", "2015-01-01"], None),
            (["--simulate", "--provider", "alpha_vantage", "--start", "2025-10-01"], None),
            (["--simulate", "--estimation-start", "2010-01-01"], "2010-01-01"),
            ([], None),
            (["--report", "--report-sections", "summary"], None),
        )
        for options, expected in cases:
            with self.subTest(options=options):
                arguments = ["--assets", "IBM:1", "--end", end.isoformat(), *options]
                self.assertEqual(parse_arguments(arguments).estimation_start, expected)

    def test_estimation_start_needs_a_simulation_and_a_valid_date(self):
        for options in (
            ["--estimation-start", "2020-01-01"],
            ["--simulate", "--estimation-start", "2020-13-01"],
            ["--simulate", "--estimation-start", "2026-02-01"],
        ):
            with self.subTest(options=options):
                with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    parse_arguments(["--assets", "IBM:1", "--end", "2026-01-07", *options])


class RunEstimationTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.reports = Path(folder.name) / "informes"
        for target, value in (
            ("src.main.load_dotenv", None),
            ("src.main.load_risk_free_rate", None),
            ("src.main.load_references", MarketReferences()),
        ):
            patcher = patch(target, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_main(self, *options):
        with (
            patch("src.main.YahooFinanceAPI") as yahoo,
            redirect_stdout(io.StringIO()),
            redirect_stderr(io.StringIO()) as errors,
        ):
            yahoo.return_value.get_prices.side_effect = provider_prices
            arguments = [
                *("--shares", "A:10", "B:5", "--rebalance", "monthly"),
                *("--start", "2025-10-01", "--end", "2026-01-07", "--simulate", "--report"),
                *("--output-dir", str(self.reports), *options),
            ]
            self.assertEqual(main(arguments), 0, errors.getvalue())
        report = next(self.reports.glob("*/*.md")).read_text(encoding="utf-8")
        starts = {call.args[1] for call in yahoo.return_value.get_prices.call_args_list}
        return report, errors.getvalue(), starts

    def test_the_report_keeps_its_period_and_explains_the_estimation(self):
        report, errors, starts = self.run_main()
        self.assertEqual(starts, {"2025-10-01", "2021-01-07"})
        self.assertIn("**Período:** 01/10/2025", report)
        self.assertIn("| Datos para estimar volatilidad y correlaciones | 07/01/2021 –", report)
        self.assertIn("**Volatilidad y correlaciones:**", report)
        self.assertNotIn("Pocos datos para estimar", report)
        self.assertNotIn("menos de 3 años", errors)
        # El rebalanceo del análisis y de la simulación indica la banda.
        self.assertIn(
            "Rebalanceo mensual a los pesos iniciales de las acciones si algún peso se desvía "
            "más de 5,00 p. p. de su objetivo",
            report,
        )
        self.assertIn(
            "Revisión cada 21 sesiones simuladas; se vuelve a los pesos objetivo si algún peso "
            "se desvía más de 5,00 p. p. de su objetivo",
            report,
        )

    def test_a_short_estimation_is_warned_in_the_console_and_the_report(self):
        report, errors, starts = self.run_main("--estimation-start", "2025-06-02")
        self.assertEqual(starts, {"2025-10-01", "2025-06-02"})
        self.assertIn("menos de 3 años", errors)
        self.assertIn("Pocos datos para estimar", report)

    def test_without_a_band_the_rebalancing_has_no_condition(self):
        report, _, _ = self.run_main(
            "--commission-rate", "0", "--commission-min", "0", "--rebalance-band", "0"
        )
        self.assertIn(
            "Revisión cada 21 sesiones simuladas; se vuelve a los pesos objetivo |", report
        )
        self.assertNotIn("si algún peso se desvía", report)


if __name__ == "__main__":
    unittest.main()
