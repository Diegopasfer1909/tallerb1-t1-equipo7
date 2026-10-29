"""Check mathematical properties, not just the shape of a returned array."""

import unittest

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")

from src.models import Asset, Portfolio, PriceHistory
from src.simulation.monte_carlo import _covariance_factor, estimate_parameters


def make_asset(symbol="A", values=None):
    if values is None:
        values = [100, 102, 101, 104, 103, 107]
    history = PriceHistory(
        symbol,
        "test",
        pd.DataFrame({"Close": values}, index=pd.date_range("2026-10-01", periods=len(values))),
        info={"currency": "USD"},
    )
    return Asset(history)


def buy_and_hold_portfolio(assets, units):
    prices = pd.concat([asset.history.closing_prices() for asset in assets], axis=1)
    amounts = prices.iloc[0].to_numpy() * units
    capital = float(amounts.sum())
    return Portfolio(assets, list(amounts / capital), initial_capital=capital, rebalance=None)


class SimulationTests(unittest.TestCase):
    def test_historical_parameters_use_annualized_simple_returns(self):
        returns = pd.DataFrame({"A": [0.01, -0.02, 0.03]})
        parameters = estimate_parameters(returns, 252)
        self.assertAlmostEqual(parameters.loc["A", "annual_return"], returns["A"].mean() * 252)
        self.assertAlmostEqual(
            parameters.loc["A", "annual_volatility"], returns["A"].std() * np.sqrt(252)
        )
        self.assertEqual(parameters.loc["A", "return_source"], "histórico")
        changed = estimate_parameters(returns, 252, expected_returns=-1.5, volatilities=0)
        self.assertEqual(changed.loc["A", "annual_return"], -1.5)
        self.assertEqual(changed.loc["A", "annual_volatility"], 0)
        self.assertEqual(changed.loc["A", "return_source"], "usuario")

    def test_one_step_matches_the_gbm_formula_with_cholesky(self):
        result = make_asset().monte_carlo(
            steps=1, simulations=5, seed=42, expected_returns=0.08, volatilities=0.2
        )
        shocks = np.random.default_rng(42).standard_normal((5, 1)).ravel()
        expected = 107 * np.exp((0.08 - 0.2**2 / 2) / 252 + 0.2 / np.sqrt(252) * shocks)
        np.testing.assert_allclose(result.paths.iloc[1], expected, rtol=1e-14)
        self.assertEqual(result.correlation_method, "Cholesky")

    def test_cholesky_and_singular_fallback_preserve_covariance(self):
        for covariance, expected_method in [
            (np.array([[0.04, 0.03], [0.03, 0.09]]), "Cholesky"),
            (np.array([[0.04, 0.04], [0.04, 0.04]]), "Autovalores (matriz singular)"),
            (np.zeros((2, 2)), "Autovalores (matriz singular)"),
        ]:
            factor, method = _covariance_factor(covariance)
            np.testing.assert_allclose(factor @ factor.T, covariance, atol=1e-14)
            self.assertEqual(method, expected_method)
        with self.assertRaises(ValueError):
            _covariance_factor(np.array([[1.0, 2.0], [2.0, 1.0]]))

    def test_volatility_overrides_keep_historical_correlations(self):
        a = make_asset("A")
        b = make_asset("B", [50, 49, 50, 49, 52, 51])
        portfolio = Portfolio([a, b], [0.6, 0.4])
        historical = portfolio.monte_carlo(steps=1, simulations=5, seed=42)
        changed = portfolio.monte_carlo(
            steps=1,
            simulations=5,
            seed=42,
            expected_returns={"A": 0.08},
            volatilities={"A": 0.5, "B": 0.1},
        )
        pd.testing.assert_frame_equal(historical.correlation, changed.correlation)
        self.assertEqual(changed.assumptions.loc["A", "annual_volatility"], 0.5)
        self.assertEqual(changed.assumptions.loc["B", "annual_volatility"], 0.1)
        self.assertEqual(changed.assumptions.loc["B", "return_source"], "histórico")

    def test_confidence_changes_tail_metrics_without_changing_paths(self):
        asset = make_asset()
        first = asset.monte_carlo(steps=10, simulations=100, seed=42, confidence=0.95)
        second = asset.monte_carlo(steps=10, simulations=100, seed=42, confidence=0.99)
        pd.testing.assert_frame_equal(first.paths, second.paths)
        final = second.paths.iloc[-1]
        summary = second.summary()
        self.assertAlmostEqual(summary["lower_percentile"], final.quantile(0.01))
        self.assertAlmostEqual(summary["upper_percentile"], final.quantile(0.99))
        self.assertAlmostEqual(summary["value_at_risk"], 107 - final.quantile(0.01))
        self.assertAlmostEqual(
            summary["conditional_value_at_risk"], 107 - final[final <= final.quantile(0.01)].mean()
        )
        for confidence in (0.5, 1, float("nan"), True):
            with self.assertRaises(ValueError):
                asset.monte_carlo(confidence=confidence)

    def test_monthly_simulation_rebalances_every_21_sessions(self):
        dates = pd.date_range("2026-01-27", periods=3)
        assets = [
            Asset(
                PriceHistory(
                    symbol,
                    "test",
                    pd.DataFrame({"Close": [100] * 3}, index=dates),
                    info={"currency": "USD"},
                )
            )
            for symbol in ("A", "B")
        ]
        portfolio = Portfolio(assets, [0.5, 0.5], initial_capital=100)
        options = dict(
            steps=22,
            simulations=3,
            seed=42,
            expected_returns={"A": 252 * np.log(1.1), "B": 0},
            volatilities={"A": 0, "B": 0},
        )
        monthly = portfolio.monte_carlo(**options)
        self.assertEqual(monthly.rebalance, "monthly")
        np.testing.assert_allclose(monthly.paths.iloc[21], 50 * 1.1**21 + 50)
        np.testing.assert_allclose(monthly.paths.iloc[22], (50 * 1.1**21 + 50) * 1.05)
        portfolio.rebalance = None
        without = portfolio.monte_carlo(**options)
        np.testing.assert_allclose(without.paths.iloc[22], 50 * 1.1**22 + 50)

    def test_shape_initial_value_seed_and_positive_paths(self):
        asset = make_asset()
        first = asset.monte_carlo(steps=10, simulations=30, seed=42)
        second = asset.monte_carlo(steps=10, simulations=30, seed=42)
        other = asset.monte_carlo(steps=10, simulations=30, seed=43)
        self.assertEqual(first.paths.shape, (11, 30))
        np.testing.assert_allclose(first.paths.iloc[0], 107)
        self.assertTrue((first.paths > 0).to_numpy().all())
        pd.testing.assert_frame_equal(first.paths, second.paths)
        self.assertFalse(first.paths.equals(other.paths))

    def test_asset_and_portfolio_share_one_simulation_method(self):
        self.assertIs(Asset.monte_carlo, Portfolio.monte_carlo)
        asset = make_asset()
        options = dict(steps=5, simulations=10, seed=3, expected_returns={"A": 0.1})
        single = asset.monte_carlo(**options)
        portfolio = buy_and_hold_portfolio([asset], [1]).monte_carlo(**options)
        np.testing.assert_allclose(portfolio.paths, single.paths)
        self.assertEqual(single.assumptions.loc["A", "return_source"], "usuario")

    def test_single_holding_matches_the_asset_times_its_quantity(self):
        asset = make_asset()
        single = asset.monte_carlo(steps=10, simulations=20, seed=7)
        portfolio = buy_and_hold_portfolio([asset], [12]).monte_carlo(
            steps=10, simulations=20, seed=7
        )
        np.testing.assert_allclose(portfolio.paths, single.paths * 12)

    def test_flat_history_stays_flat(self):
        result = make_asset(values=[100] * 6).monte_carlo(steps=10, simulations=20, seed=1)
        np.testing.assert_allclose(result.paths, 100)

    def test_return_parameter_is_the_annual_gbm_drift(self):
        result = make_asset().monte_carlo(
            steps=1,
            simulations=50000,
            seed=99,
            periods_per_year=1,
            expected_returns=0.1,
            volatilities=0.3,
        )
        expected_final = 107 * np.exp(0.1)
        self.assertAlmostEqual(
            float(np.mean(result.paths.iloc[-1].to_numpy())), expected_final, delta=0.75
        )

    def test_zero_volatility_matches_the_requested_annual_return(self):
        asset = make_asset(values=[100] * 6)
        for periods in [12, 252]:
            result = asset.monte_carlo(
                steps=periods,
                simulations=3,
                expected_returns=0.1,
                volatilities=0,
                periods_per_year=periods,
            )
            np.testing.assert_allclose(result.paths.iloc[-1], 100 * np.exp(0.1), rtol=1e-12)
            self.assertAlmostEqual(result.assumptions.loc["A", "annual_return"], 0.1)

    def test_valuation_and_adjusted_return_columns_are_separate(self):
        asset = make_asset(values=[100, 100, 100, 100])
        asset.history.prices["Adj Close"] = [40, 42, 44, 46]
        result = asset.monte_carlo(steps=1, simulations=4, seed=2, price_column="Adj Close")
        np.testing.assert_allclose(result.paths.iloc[0], 100)
        self.assertEqual(result.price_column, "Adj Close")
        with self.assertRaises(ValueError):
            make_asset().monte_carlo(price_column="Adj Close")

    def test_joint_simulation_uses_negative_correlation(self):
        log_changes = np.array([0.01, -0.02, 0.015, -0.005, 0.025, -0.015])
        a = make_asset("A", 100 * np.cumprod(np.r_[1, 1 + log_changes]))
        b = make_asset("B", 100 * np.cumprod(np.r_[1, 1 - log_changes]))
        portfolio = buy_and_hold_portfolio([a, b], [100 / a.latest_price, 100 / b.latest_price])
        result = portfolio.monte_carlo(
            steps=1,
            simulations=10000,
            seed=4,
            expected_returns={"A": 0, "B": 0},
            volatilities={"A": 0.2, "B": 0.2},
        )
        self.assertAlmostEqual(result.correlation.loc["A", "B"], -1)
        # Equal positions with opposite shocks almost cancel over one short step.
        # Independent draws would produce a standard deviation around 1.8 here.
        self.assertLess(float(np.std(result.paths.iloc[-1].to_numpy())), 0.1)

    def test_reject_invalid_parameters_and_short_history(self):
        asset = make_asset()
        for options in [
            {"steps": 0},
            {"steps": True},
            {"simulations": -1},
            {"steps": 1.5},
            {"periods_per_year": 0},
            {"seed": -1},
            {"volatilities": -0.1},
            {"expected_returns": float("nan")},
            {"steps": 100000, "simulations": 100000},
        ]:
            with self.subTest(options=options), self.assertRaises(ValueError):
                asset.monte_carlo(**options)
        with self.assertRaisesRegex(ValueError, "al menos tres fechas"):
            make_asset(values=[100, 101]).monte_carlo()
        with self.assertRaisesRegex(ValueError, "Activo desconocido"):
            buy_and_hold_portfolio([asset], [1]).monte_carlo(expected_returns={"UNKNOWN": 0.1})

    def test_summary_and_plot_without_files_or_a_gui(self):
        import matplotlib.pyplot as plt

        result = make_asset().monte_carlo(steps=5, simulations=20, seed=1)
        summary = result.summary()
        self.assertEqual(summary["initial_value"], 107)
        self.assertLessEqual(summary["lower_percentile"], summary["upper_percentile"])
        self.assertGreaterEqual(summary["probability_of_loss"], 0)
        self.assertLessEqual(summary["probability_of_loss"], 1)
        figure = result.plot(show=False, max_paths=3)
        self.assertEqual(len(figure.axes), 2)
        self.assertEqual(len(figure.axes[0].lines), 3)
        plt.close(figure)
