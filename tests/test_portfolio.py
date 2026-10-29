"""Small, known holdings make valuation and weight errors easy to catch."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd

from src.models import Asset, Portfolio, PriceHistory
from src.portfolio_loader import load_portfolio
from src.providers import AlphaVantageAPI, YahooFinanceAPI


def asset(symbol, closes, currency="USD", dates=None, info=None):
    if dates is None:
        dates = pd.date_range("2026-10-01", periods=len(closes))
    metadata = {"currency": currency}
    if info:
        metadata.update(info)
    history = PriceHistory(
        symbol, "test", pd.DataFrame({"Close": closes}, index=dates), info=metadata
    )
    return Asset(history)


class PortfolioTests(unittest.TestCase):
    def test_report_accepts_parameters_and_matches_a_direct_simulation(self):
        portfolio = Portfolio([asset("A", [100, 101, 100])], [1], initial_capital=100)
        options = dict(
            steps=21, simulations=5, expected_returns=0.08, volatilities=0, confidence=0.99, seed=7
        )
        direct = portfolio.monte_carlo(**options)
        np.testing.assert_allclose(direct.paths.iloc[-1], 100 * np.exp(0.08 * 21 / 252))
        with patch(
            "src.analysis.result.PortfolioAnalysis.report", return_value=Path("unused.md")
        ) as save:
            portfolio.report(**options)
        generated = save.call_args.args[1]
        pd.testing.assert_frame_equal(generated.paths, direct.paths)
        self.assertEqual(generated.confidence, direct.confidence)

    def test_report_rejects_a_different_rebalancing_strategy(self):
        portfolio = Portfolio([asset("A", [100, 102, 100]), asset("B", [100, 99, 100])], [0.5, 0.5])
        simulation = portfolio.monte_carlo(steps=2, simulations=3, seed=42)
        with (
            tempfile.TemporaryDirectory() as folder,
            patch("src.reporting.export.REPORTS_DIR", Path(folder) / "informes"),
        ):
            simulation.rebalance = None
            with self.assertRaisesRegex(ValueError, "criterios de cálculo"):
                portfolio.report(simulation=simulation)
            simulation.rebalance = "monthly"
            simulation.target_weights = pd.Series({"A": 0.6, "B": 0.4})
            with self.assertRaisesRegex(ValueError, "criterios de cálculo"):
                portfolio.report(simulation=simulation)
            self.assertFalse((Path(folder) / "informes").exists())

    def test_monthly_rebalance_restores_targets_without_changing_total_value(self):
        dates = pd.to_datetime(["2026-01-30", "2026-01-31", "2026-02-01"])
        assets = [
            asset("A", [100, 200, 100], dates=dates),
            asset("B", [100, 100, 100], dates=dates),
        ]
        portfolio = Portfolio(assets, [0.5, 0.5], initial_capital=100)
        positions = portfolio.position_values()
        np.testing.assert_allclose(positions.sum(axis=1), [100, 150, 112.5])
        np.testing.assert_allclose(positions.iloc[1], [75, 75])
        np.testing.assert_allclose(portfolio.target_weights, [0.5, 0.5])
        np.testing.assert_allclose(portfolio.weights, [1 / 3, 2 / 3])
        np.testing.assert_allclose(portfolio.analyze().values, [100, 150, 112.5])

    def test_final_business_day_rebalances_but_a_partial_month_does_not(self):
        for end, expected in [("2026-01-29", [100, 50]), ("2026-01-30", [75, 75])]:
            dates = pd.to_datetime(["2026-01-28", end])
            assets = [asset("A", [100, 200], dates=dates), asset("B", [100, 100], dates=dates)]
            portfolio = Portfolio(assets, [0.5, 0.5], initial_capital=100)
            np.testing.assert_allclose(portfolio.position_values().iloc[-1], expected)

    def test_zero_weight_is_allowed_without_investing_in_that_asset(self):
        portfolio = Portfolio([asset("A", [100, 100, 100]), asset("B", [100, 200, 300])], [1, 0])
        np.testing.assert_allclose(portfolio.position_values()["B"], 0)
        self.assertEqual(portfolio.total_value, 10000)
        simulation = portfolio.monte_carlo(steps=2, simulations=3, seed=42)
        np.testing.assert_allclose(simulation.paths, 10000)

    def test_target_weights_allocate_initial_capital(self):
        a = asset("A", [80, 90, 100])
        b = asset("B", [40, 45, 50])
        portfolio = Portfolio([a, b], [0.5, 0.5], initial_capital=1600)
        self.assertEqual(portfolio.total_value, 2000)
        np.testing.assert_allclose(portfolio.weights, [0.5, 0.5])
        self.assertEqual(portfolio.holdings().loc["A", "value"], 1000)

    def test_all_prices_use_the_latest_common_date(self):
        a = asset("A", [80, 90, 100, 110])
        b = asset("B", [40, 45, 50])
        portfolio = Portfolio([a, b], [0.5, 0.5], initial_capital=1600)
        self.assertEqual(a.latest_price, 110)
        self.assertEqual(portfolio.valuation_date, pd.Timestamp("2026-10-03"))
        self.assertEqual(portfolio.holdings().loc["A", "price"], 100)
        self.assertEqual(portfolio.total_value, 2000)

    def test_align_prices_before_returns_without_filling_gaps(self):
        a = asset("A", [100, 200, 400])
        b = asset("B", [10, 40], dates=pd.to_datetime(["2026-10-01", "2026-10-03"]))
        portfolio = Portfolio([a, b], [0.5, 0.5])
        np.testing.assert_allclose(portfolio.returns().iloc[0], [3, 3])
        self.assertEqual(len(portfolio.close_prices()), 2)

    def test_reference_capital_controls_the_value_scale(self):
        portfolio = Portfolio([asset("A", [90, 100])], [1], initial_capital=22.5)
        self.assertEqual(portfolio.total_value, 25)
        self.assertEqual(portfolio.weights.iloc[0], 1)

    def test_reject_bad_weights_duplicates_and_mismatches(self):
        a = asset("A", [90, 100])
        for quantity in [0, 0.25, -1, 2, float("nan"), float("inf"), True, "1"]:
            with self.subTest(quantity=quantity), self.assertRaises(ValueError):
                Portfolio([a], [quantity])
        for assets, quantities in [([], []), ([a], []), ([a, a], [1, 2])]:
            with self.assertRaises(ValueError):
                Portfolio(assets, quantities)

    def test_reject_mixed_currencies_and_minor_price_units(self):
        for first, second in [("USD", "EUR"), ("GBP", "GBp")]:
            with self.assertRaisesRegex(ValueError, "misma divisa"):
                Portfolio([asset("A", [1, 2], first), asset("B", [1, 2], second)], [0.5, 0.5])

    def test_missing_or_conflicting_currency_is_not_guessed(self):
        history = PriceHistory(
            "A",
            "test",
            pd.DataFrame({"Close": [1, 2]}, index=pd.date_range("2026-10-01", periods=2)),
        )
        with self.assertRaisesRegex(ValueError, "Falta la divisa"):
            Asset(history)
        self.assertEqual(Asset(history, currency="USD").currency, "USD")
        history.info["currency"] = "EUR"
        with self.assertRaisesRegex(ValueError, "cotiza en EUR"):
            Asset(history, currency="USD")

    def test_reject_disjoint_dates_and_adjusted_valuation(self):
        a = asset("A", [1, 2])
        b = asset("B", [1, 2], dates=pd.date_range("2025-01-01", periods=2))
        with self.assertRaisesRegex(ValueError, "no tienen fechas de precios comunes"):
            Portfolio([a, b], [0.5, 0.5])
        with self.assertRaisesRegex(ValueError, "Close sin ajuste por dividendos"):
            asset("A", [1, 2], info={"price_adjustment": "adjusted"})

    def test_close_only_nav_and_return_calculations(self):
        fund = asset("FUND", [100, 110, 99], info={"asset_type": "fund"})
        self.assertEqual(fund.asset_type, "fund")
        np.testing.assert_allclose(fund.history.returns(), [0.1, -0.1])
        np.testing.assert_allclose(fund.history.returns(log=True), np.log([1.1, 0.9]))
        self.assertEqual(list(fund.history.prices.columns), ["Close"])

    def test_reject_invalid_close_and_duplicate_columns(self):
        for values in [[0, 1], [-1, 2], [float("nan"), 2], [True, False]]:
            with self.assertRaises((ValueError, TypeError)):
                asset("A", values)
        frame = pd.DataFrame(
            [[1, 2]], columns=["Close", "Close"], index=pd.date_range("2026-10-01", periods=1)
        )
        with self.assertRaisesRegex(ValueError, "nombres únicos"):
            PriceHistory("A", "test", frame)

    def test_loader_preserves_target_weights(self):
        provider = Mock(spec=YahooFinanceAPI)
        provider.get_prices.side_effect = [
            asset("A", [90, 100]).history,
            asset("B", [40, 50]).history,
        ]
        portfolio = load_portfolio({"A": 0.5, "B": 0.5}, provider, "2026-10-01", "2026-10-03")
        np.testing.assert_allclose(portfolio.target_weights, [0.5, 0.5])
        self.assertAlmostEqual(portfolio.weights["A"], (100 / 90) / (100 / 90 + 50 / 40))
        self.assertEqual(provider.get_prices.call_count, 2)
        provider.get_prices.assert_any_call("A", "2026-10-01", "2026-10-03")

    def test_loader_validates_weights_before_network_calls(self):
        provider = Mock(spec=YahooFinanceAPI)
        for holdings in [{}, {"A": 0}, {"A": 0.5, "a": 0.5}, {"A": 0.8}, {" ": 1}]:
            with self.assertRaises(ValueError):
                load_portfolio(holdings, provider, "2026-10-01", "2026-10-03")
        provider.get_prices.assert_not_called()

    def test_loader_uses_the_common_interface_and_accepts_explicit_currency(self):
        provider = Mock(spec=AlphaVantageAPI)
        history = asset("A", [90, 100]).history
        history.info.clear()
        provider.get_prices.return_value = history
        portfolio = load_portfolio({"A": 1}, provider, "2026-10-01", "2026-10-03", currency="USD")
        self.assertAlmostEqual(portfolio.total_value, 10000 * 100 / 90)
        provider.get_prices.assert_called_once_with("A", "2026-10-01", "2026-10-03")
