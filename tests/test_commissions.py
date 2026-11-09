"""Comisiones del bróker y reajustes que solo se hacen cuando compensan."""

import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import fixtures
import numpy as np
import pandas as pd

from src.commissions import (
    IBKR_COMMISSIONS,
    CommissionSchedule,
    RebalanceRule,
    rebalance_step,
)
from src.errors import PortfolioError
from src.main import main, parse_arguments
from src.models import MarketReferences, Portfolio
from src.models.backtest import backtest_allocation, backtest_with_costs
from src.simulation import SimulationSettings, simulate

IBKR = IBKR_COMMISSIONS
DEGIRO_LIKE = CommissionSchedule(fixed=2.0, name="Fija")
TARGET = np.array([0.6, 0.4])


def trending_prices(sessions: int = 70) -> pd.DataFrame:
    """A sube un 1 % cada sesión y B no se mueve: rebalancear vende siempre al ganador."""
    dates = pd.bdate_range("2026-01-01", periods=sessions)
    return pd.DataFrame({"A": 100 * 1.01 ** np.arange(sessions), "B": 100.0}, index=dates)


def mean_reverting_prices() -> pd.DataFrame:
    """A sube a 130 los meses impares y vuelve a 100 los pares: rebalancear aprovecha el vaivén."""
    dates = pd.bdate_range("2026-01-01", "2026-06-30")
    closes = []
    for month in sorted(set(dates.month)):
        sessions = int((dates.month == month).sum())
        start, end = (100, 130) if month % 2 else (130, 100)
        closes.extend(np.linspace(start, end, sessions + 1)[1:])
    return pd.DataFrame({"A": closes, "B": 100.0}, index=dates)


class CommissionScheduleTests(unittest.TestCase):
    def test_cost_applies_rate_minimum_and_maximum(self):
        schedule = CommissionSchedule(rate=0.001, fixed=1, minimum=3, maximum=10)
        np.testing.assert_allclose(schedule.cost([0, 500, -5_000, 100_000]), [0, 3, 6, 10])

    def test_ibkr_matches_the_documented_tariff(self):
        np.testing.assert_allclose(IBKR.cost([1_000, 20_000]), [3, 10])
        self.assertEqual(IBKR.name, "Interactive Brokers")
        self.assertFalse(IBKR.is_free)

    def test_invalid_tariffs_are_rejected(self):
        for options in ({"rate": -0.1}, {"rate": 1}, {"fixed": -1}, {"minimum": 5, "maximum": 2}):
            with self.subTest(options=options), self.assertRaises(PortfolioError):
                CommissionSchedule(**options)
        for options in ({"band": -0.01}, {"band": 1}, {"max_order_cost": 0}):
            with self.subTest(options=options), self.assertRaises(PortfolioError):
                RebalanceRule(**options)


class RebalanceStepTests(unittest.TestCase):
    def test_free_rule_returns_exactly_to_the_targets(self):
        step = rebalance_step([[7_000, 3_000]], TARGET, RebalanceRule())
        np.testing.assert_allclose(step.values, [[6_000, 4_000]])
        np.testing.assert_allclose(step.orders, [[-1_000, 1_000]])
        self.assertEqual(step.commissions.sum(), 0)

    def test_value_falls_exactly_by_the_commissions(self):
        values = np.array([[7_000.0, 3_000.0]])
        step = rebalance_step(values, TARGET, RebalanceRule(IBKR))
        self.assertTrue(step.rebalanced[0])
        self.assertAlmostEqual(step.commissions.sum(), 6.0)
        self.assertAlmostEqual(step.values.sum(), values.sum() - step.commissions.sum())
        np.testing.assert_allclose(step.values / step.values.sum(), [TARGET], atol=1e-12)

    def test_drift_inside_the_band_is_left_alone(self):
        values = np.array([[6_400.0, 3_600.0], [7_000.0, 3_000.0]])
        step = rebalance_step(values, TARGET, RebalanceRule(IBKR, band=0.05))
        np.testing.assert_array_equal(step.rebalanced, [False, True])
        np.testing.assert_allclose(step.values[0], values[0])
        self.assertEqual(step.commissions[0].sum(), 0)

    def test_expensive_orders_are_skipped_and_the_rest_rebalanced(self):
        # C apenas se desvía: su orden de 20 pagaría 3 de mínimo (15 %) y se descarta.
        values = np.array([[5_500.0, 2_500.0, 2_020.0]])
        target = np.array([0.5, 0.3, 0.2])
        rule = RebalanceRule(IBKR, max_order_cost=0.01)
        step = rebalance_step(values, target, rule)
        self.assertEqual(step.skipped[0], 1)
        self.assertEqual(step.values[0, 2], 2_020.0)
        self.assertEqual(step.orders[0, 2], 0)
        self.assertAlmostEqual(step.values[0].sum(), values.sum() - step.commissions.sum())
        self.assertAlmostEqual(step.values[0, 0] / step.values[0, 1], 5 / 3)

    def test_a_single_cheap_order_is_not_a_rebalance(self):
        values = np.array([[6_500.0, 3_490.0, 10.0]])
        step = rebalance_step(values, np.array([0.6, 0.39, 0.01]), RebalanceRule(IBKR, 0, 0.001))
        self.assertFalse(step.rebalanced[0])
        np.testing.assert_allclose(step.values, values)


class BacktestCostTests(unittest.TestCase):
    def test_free_rule_reproduces_the_previous_backtest(self):
        prices = trending_prices()
        weights = pd.Series({"A": 0.6, "B": 0.4})
        before = backtest_allocation(prices, weights, 10_000, "monthly")
        after = backtest_with_costs(prices, weights, 10_000, "monthly", RebalanceRule())
        pd.testing.assert_frame_equal(before, after.positions)
        self.assertEqual(after.total_commissions, 0)

    def test_trades_are_recorded_at_month_end_and_reduce_the_value(self):
        prices = trending_prices()
        weights = pd.Series({"A": 0.6, "B": 0.4})
        free = backtest_with_costs(prices, weights, 10_000, "monthly")
        paid = backtest_with_costs(prices, weights, 10_000, "monthly", RebalanceRule(IBKR))
        self.assertEqual(len(paid.rebalance_dates), 3)
        self.assertTrue(set(paid.trades["date"]) <= set(paid.rebalance_dates))
        self.assertTrue((paid.trades["commission"] >= 3).all())
        self.assertLess(paid.positions.iloc[-1].sum(), free.positions.iloc[-1].sum())

    def test_a_wide_band_avoids_rebalancing(self):
        prices = trending_prices()
        weights = pd.Series({"A": 0.6, "B": 0.4})
        rule = RebalanceRule(IBKR, band=0.5)
        result = backtest_with_costs(prices, weights, 10_000, "monthly", rule)
        self.assertEqual(len(result.rebalance_dates), 0)
        pd.testing.assert_frame_equal(
            result.positions, backtest_allocation(prices, weights, 10_000)
        )


class PortfolioCostTests(unittest.TestCase):
    def portfolio(self, rule: RebalanceRule, prices=None, capital=10_000) -> Portfolio:
        prices = trending_prices() if prices is None else prices
        assets = [
            fixtures.asset(symbol, prices[symbol].tolist(), dates=prices.index) for symbol in prices
        ]
        return Portfolio(assets, {"A": 0.6, "B": 0.4}, initial_capital=capital, rebalance_rule=rule)

    def test_analysis_compares_with_buy_and_hold(self):
        analysis = self.portfolio(RebalanceRule(IBKR)).analyze()
        costs = analysis.rebalance_costs
        self.assertGreater(costs.commissions, 0)
        self.assertEqual(costs.rebalances, 3)
        self.assertAlmostEqual(costs.final_value, analysis.values.iloc[-1])
        # Vender cada mes al ganador rinde menos incluso sin comisiones: no es culpa de ellas.
        self.assertLess(costs.gross_advantage, 0)
        codes = {warning.code for warning in analysis.risk_warnings}
        self.assertNotIn("costly_rebalancing", codes)
        report = analysis.markdown(detail="full")
        self.assertIn("**Coste del rebalanceo**", report)
        self.assertIn("Interactive Brokers: 0,05 % por orden, mínimo 3,00 USD", report)
        self.assertIn("rendiría menos incluso sin comisiones", report)

    def test_warns_when_commissions_erase_the_rebalancing_benefit(self):
        prices = mean_reverting_prices()
        free = self.portfolio(RebalanceRule(), prices, 1_000).analyze().rebalance_costs
        self.assertGreater(free.advantage, 0)
        rule = RebalanceRule(CommissionSchedule(fixed=5, name="Cara"))
        analysis = self.portfolio(rule, prices, 1_000).analyze()
        costs = analysis.rebalance_costs
        self.assertLess(costs.advantage, 0)
        self.assertGreaterEqual(costs.gross_advantage, 0)
        codes = {warning.code for warning in analysis.risk_warnings}
        self.assertIn("costly_rebalancing", codes)
        self.assertIn("high_commissions", codes)
        self.assertIn("las comisiones anulan", analysis.markdown(detail="full"))

    def test_free_portfolio_keeps_the_previous_note(self):
        report = self.portfolio(RebalanceRule()).analyze().markdown(detail="full")
        self.assertIn("Los resultados no incluyen comisiones", report)
        self.assertNotIn("costly_rebalancing", report)

    def test_simulation_pays_commissions_and_ends_lower(self):
        # Mismo punto de partida: solo cambia la regla de la simulación.
        inputs = self.portfolio(RebalanceRule(DEGIRO_LIKE)).simulation_inputs()
        settings = SimulationSettings(steps=63, simulations=200, seed=3, expected_returns=0.08)
        paid = simulate(inputs, settings)
        free = simulate(replace(inputs, rebalance_rule=RebalanceRule()), settings)
        self.assertEqual(free.mean_commissions, 0)
        self.assertGreater(paid.mean_commissions, 0)
        np.testing.assert_array_less(paid.paths.iloc[-1], free.paths.iloc[-1] + 1e-9)
        np.testing.assert_allclose(
            free.paths.iloc[-1] - paid.paths.iloc[-1], paid.commissions, rtol=0.05
        )


class CommissionOptionsTests(unittest.TestCase):
    def test_default_is_ibkr_with_band_and_order_cost(self):
        rule = parse_arguments(["--assets", "IBM:0.6", "MSFT:0.4"]).rebalance_rule
        self.assertEqual(rule.commissions, IBKR)
        self.assertEqual((rule.band, rule.max_order_cost), (0.05, 0.01))

    def test_ibkr_values_can_be_customised(self):
        rule = parse_arguments(
            [
                "--assets",
                "IBM:1",
                "--commission-fixed",
                "2",
                "--commission-min",
                "5",
                "--rebalance-band",
                "0",
                "--max-order-cost",
                "0.02",
            ]
        ).rebalance_rule
        self.assertEqual(rule.commissions.fixed, 2)
        self.assertEqual(rule.commissions.minimum, 5)
        self.assertEqual(rule.commissions.rate, IBKR.rate)
        self.assertEqual(rule.commissions.name, "Interactive Brokers (personalizada)")
        self.assertEqual((rule.band, rule.max_order_cost), (0, 0.02))

    def test_other_brokers_cannot_be_selected(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parse_arguments(["--assets", "IBM:1", "--broker", "degiro"])

    def test_cost_options_require_monthly_rebalancing(self):
        for arguments in (
            ["--assets", "IBM:1", "--rebalance", "none", "--commission-min", "5"],
            ["--shares", "IBM:10", "--commission-rate", "0.001"],
            ["--assets", "IBM:1", "--commission-min", "-1"],
        ):
            with (
                self.subTest(arguments=arguments),
                redirect_stderr(io.StringIO()),
                self.assertRaises(SystemExit),
            ):
                parse_arguments(arguments)

    def test_console_and_report_show_the_commissions(self):
        prices = trending_prices()
        histories = {
            symbol: fixtures.history(symbol, prices[column].tolist(), dates=prices.index)
            for symbol, column in (("IBM", "A"), ("MSFT", "B"))
        }
        with tempfile.TemporaryDirectory() as folder:
            reports = Path(folder) / "informes"
            with (
                patch("src.main.load_dotenv"),
                patch("src.main.YahooFinanceAPI") as yahoo,
                patch("src.main.load_references", return_value=MarketReferences()),
                redirect_stdout(io.StringIO()) as output,
                redirect_stderr(io.StringIO()),
            ):
                yahoo.return_value.get_prices.side_effect = lambda symbol, *a, **k: histories[
                    symbol
                ]
                arguments = ["--assets", "IBM:0.6", "MSFT:0.4", "--report"]
                self.assertEqual(main([*arguments, "--output-dir", str(reports)]), 0)
            report = next(reports.glob("*/*.md")).read_text(encoding="utf-8")
        self.assertIn(
            "Comisiones: Interactive Brokers, 0,05 % por orden, mínimo 3,00 USD", output.getvalue()
        )
        self.assertIn("**Coste del rebalanceo**", report)
        self.assertIn("Comisiones de rebalanceo", report)


if __name__ == "__main__":
    unittest.main()
