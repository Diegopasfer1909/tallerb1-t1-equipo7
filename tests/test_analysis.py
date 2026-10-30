"""Known financial examples, independent of APIs and historical market prices."""

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import matplotlib
import numpy as np
import pandas as pd

from src.analysis import backtest_allocation
from src.market_loader import load_currency_context, load_market_context, load_report_context
from src.models import (
    Asset,
    EconomicIndicator,
    ExchangeRate,
    MarketContext,
    Portfolio,
    PriceHistory,
)
from src.providers import FredAPI, ProviderError, YahooFinanceAPI

matplotlib.use("Agg")


def history(symbol, closes, currency="USD", dates=None, extra=None):
    if dates is None:
        dates = pd.date_range("2026-01-01", periods=len(closes))
    prices = pd.DataFrame({"Close": closes}, index=dates)
    if extra:
        for column, values in extra.items():
            prices[column] = values
    return PriceHistory(
        symbol, "test", prices, info={"currency": currency, "price_adjustment": "unadjusted"}
    )


def indicator(values, dates, units="Percent", name="TEST"):
    return EconomicIndicator(
        name, "test", pd.Series(values, index=dates, dtype=float), units, "Daily"
    )


def buy_and_hold_portfolio(assets, units, reporting_currency="", market_context=None):
    """Convierte los ejemplos numéricos de posiciones a pesos iniciales, sin rebalanceo."""
    currency = reporting_currency or assets[0].currency
    context = market_context or MarketContext()
    columns = []
    for asset in assets:
        prices = asset.history.closing_prices()
        columns.append(context.convert(prices, asset.currency, currency))
    prices = pd.concat(columns, axis=1, join="inner").sort_index()
    amounts = prices.iloc[0].to_numpy() * units
    capital = float(amounts.sum())
    return Portfolio(
        assets,
        list(amounts / capital),
        reporting_currency,
        market_context,
        initial_capital=capital,
        rebalance=None,
    )


class CurrencyTests(unittest.TestCase):
    def setUp(self):
        self.dates = pd.date_range("2026-01-01", periods=3)
        self.rate = ExchangeRate("EUR", "USD", indicator([1.1, 1.1, 1], self.dates))

    def test_foreign_value_weights_and_original_history(self):
        foreign = Asset(history("US", [110, 110, 110]))
        local = Asset(history("EU", [100, 100, 100], "EUR"))
        portfolio = buy_and_hold_portfolio(
            [foreign, local], [1, 1], "EUR", MarketContext(exchange_rates=[self.rate])
        )
        self.assertEqual(portfolio.currency, "EUR")
        self.assertEqual(portfolio.total_value, 210)
        self.assertAlmostEqual(portfolio.weights["US"], 110 / 210)
        self.assertAlmostEqual(portfolio.close_prices()["US"].iloc[0], 100)
        self.assertEqual(foreign.history.prices["Close"].iloc[0], 110)
        self.assertAlmostEqual(portfolio.analyze().metrics["total_return"], 0.05)
        result = portfolio.monte_carlo(steps=2, simulations=3, seed=1)
        np.testing.assert_allclose(result.paths.iloc[0], 210)

    def test_rate_multiplies_in_forward_direction(self):
        prices = pd.Series([100, 100, 100], index=self.dates, name="A")
        converted = MarketContext(exchange_rates=[self.rate]).convert(prices, "EUR", "USD")
        np.testing.assert_allclose(converted, [110, 110, 100])

    def test_past_rate_allowed_but_future_and_stale_rates_rejected(self):
        rate = ExchangeRate("EUR", "USD", indicator([1.1], self.dates[:1]), max_age_days=1)
        self.assertEqual(rate.on_dates(self.dates[1:2]).iloc[0], 1.1)
        for dates in [self.dates[2:], pd.DatetimeIndex(["2025-12-31"])]:
            with self.assertRaisesRegex(ValueError, "Faltan tipos de cambio"):
                rate.on_dates(dates)

    def test_no_missing_currency_or_exchange_rate_is_guessed(self):
        with self.assertRaisesRegex(ValueError, "Proporciona un tipo de cambio"):
            buy_and_hold_portfolio([Asset(history("A", [1, 2, 3]))], [1], "EUR")
        with self.assertRaisesRegex(ValueError, "una sola serie de tipos de cambio"):
            MarketContext(exchange_rates=[self.rate, self.rate])
        with self.assertRaisesRegex(ValueError, "positivo"):
            ExchangeRate("EUR", "USD", indicator([0], self.dates[:1]))

    def test_pence_are_normalized_only_for_explicit_conversion(self):
        asset = Asset(history("UK", [100, 200, 300], "GBp"))
        self.assertEqual(buy_and_hold_portfolio([asset], [2]).total_value, 600)
        portfolio = buy_and_hold_portfolio([asset], [2], "GBP")
        self.assertEqual(portfolio.total_value, 6)
        self.assertEqual(asset.latest_price, 300)


class AnalysisTests(unittest.TestCase):
    def test_report_estimates_match_the_parameters_used_in_simulation(self):
        portfolio = buy_and_hold_portfolio([Asset(history("A", [100, 102, 99, 103]))], [2])
        analysis = portfolio.analyze()
        simulation = portfolio.monte_carlo(steps=2, simulations=5, seed=42)
        self.assertAlmostEqual(
            analysis.asset_details.loc["A", "expected_annual_return"],
            simulation.assumptions.loc["A", "annual_return"],
        )
        self.assertAlmostEqual(
            analysis.asset_details.loc["A", "expected_annual_volatility"],
            simulation.assumptions.loc["A", "annual_volatility"],
        )

    def test_compounding_drawdown_and_current_concentration(self):
        portfolio = buy_and_hold_portfolio([Asset(history("A", [100, 120, 96]))], [10])
        analysis = portfolio.analyze(periods_per_year=2)
        self.assertAlmostEqual(analysis.metrics["total_return"], -0.04)
        self.assertAlmostEqual(analysis.metrics["annualized_return"], -0.04)
        self.assertAlmostEqual(analysis.metrics["max_drawdown"], -0.2)
        self.assertAlmostEqual(analysis.metrics["effective_asset_count"], 1)
        self.assertAlmostEqual(analysis.risk_contributions["A"], 1)
        self.assertTrue(np.isnan(analysis.metrics["sharpe"]))

    def test_inflation_reference_and_benchmark_use_consistent_periods(self):
        dates = pd.to_datetime(["2026-01-01", "2026-02-01", "2026-03-01"])
        context = MarketContext(
            benchmark=history("INDEX", [100, 102, 104], dates=dates),
            inflation=indicator([100, 101, 103], dates, "Index 2020=100"),
            risk_free_rate=indicator([2, 2, 2], dates),
        )
        portfolio = buy_and_hold_portfolio(
            [Asset(history("A", [100, 110, 108], dates=dates))], [1], market_context=context
        )
        metrics = portfolio.analyze(periods_per_year=2).metrics
        self.assertAlmostEqual(metrics["annualized_return"], 0.08)
        self.assertAlmostEqual(metrics["annualized_inflation"], 0.03)
        self.assertAlmostEqual(metrics["real_annualized_return"], 1.08 / 1.03 - 1)
        self.assertAlmostEqual(metrics["reference_annualized_return"], 0.02)
        self.assertAlmostEqual(metrics["difference_from_benchmark"], 0.04)
        self.assertTrue(np.isfinite(metrics["sharpe"]))

    def test_bad_or_stale_economic_data_omits_metrics_instead_of_assuming_zero(self):
        dates = pd.date_range("2026-01-01", periods=3)
        context = MarketContext(
            inflation=indicator([3], dates[:1], "Percent"),
            risk_free_rate=indicator([2], pd.DatetimeIndex(["2025-01-01"])),
        )
        portfolio = buy_and_hold_portfolio(
            [Asset(history("A", [100, 110, 108]))], [1], market_context=context
        )
        analysis = portfolio.analyze()
        self.assertTrue(np.isnan(analysis.metrics["real_annualized_return"]))
        self.assertTrue(np.isnan(analysis.metrics["sharpe"]))
        self.assertTrue(
            any("suficientemente recientes" in warning for warning in analysis.warnings)
        )

    def test_benchmark_does_not_fill_missing_prices_or_assume_currency(self):
        for benchmark in [history("INDEX", [1, 2]), history("INDEX", [1, 2, 3], currency="")]:
            with self.subTest(currency=benchmark.info["currency"]):
                portfolio = buy_and_hold_portfolio(
                    [Asset(history("A", [100, 110, 108]))],
                    [1],
                    market_context=MarketContext(benchmark=benchmark),
                )
                analysis = portfolio.analyze()
                self.assertTrue(np.isnan(analysis.metrics["benchmark_annualized_return"]))
                self.assertTrue(any("referencia" in warning for warning in analysis.warnings))

    def test_current_weights_not_starting_weights_drive_risk_and_sectors(self):
        a = history("A", [100, 150, 200])
        b = history("B", [100, 110, 100])
        a.info["sector"] = "Technology"
        b.info["sector"] = "Utilities"
        portfolio = buy_and_hold_portfolio([Asset(a), Asset(b)], [1, 1])
        analysis = portfolio.analyze()
        self.assertAlmostEqual(analysis.sector_weights["Technology"], 2 / 3)
        covariance = portfolio.returns().cov()
        weights = portfolio.weights
        expected = weights * (covariance @ weights) / (weights @ covariance @ weights)
        np.testing.assert_allclose(analysis.risk_contributions, expected)
        self.assertAlmostEqual(analysis.metrics["concentration_hhi"], 5 / 9)

    def test_quality_records_discarded_dates_and_partial_history(self):
        a = history("A", [1, 2, 3, 4])
        b = history("B", [1, 2, 3])
        b.info["partial_history"] = True
        analysis = buy_and_hold_portfolio([Asset(a), Asset(b)], [1, 1]).analyze()
        self.assertEqual(analysis.data_quality.loc["A", "excluded_observations"], 1)
        self.assertEqual(analysis.data_quality["filled_asset_prices"].sum(), 0)
        self.assertTrue(any("parte del historial" in warning for warning in analysis.warnings))

    def test_adjusted_growth_is_anchored_to_raw_starting_values(self):
        data = history("A", [100, 100, 100], extra={"Adj Close": [50, 55, 60]})
        portfolio = buy_and_hold_portfolio([Asset(data)], [2])
        analysis = portfolio.analyze(price_column="Adj Close")
        np.testing.assert_allclose(analysis.values, [200, 220, 240])
        self.assertEqual(analysis.holdings["value"].sum(), 240)
        self.assertAlmostEqual(analysis.metrics["total_return"], 0.2)

    def test_spanish_markdown_can_be_built_without_writing_files(self):
        analysis = buy_and_hold_portfolio([Asset(history("A", [100, 120, 96]))], [1]).analyze()
        with patch("pathlib.Path.write_text") as write:
            report = analysis.markdown()
        write.assert_not_called()
        self.assertIn("Caída máxima", report)
        self.assertIn("-20,00 %", report)
        self.assertIn("No disponible", report)
        self.assertNotIn("Maximum drawdown", report)

    def test_report_uses_date_filename_and_references_existing_images(self):
        import re

        import matplotlib.pyplot as plt

        analysis = buy_and_hold_portfolio([Asset(history("A", [100, 120, 96]))], [1]).analyze()
        date_of_report = datetime(2026, 10, 28, 15, 30, 45)
        with (
            tempfile.TemporaryDirectory() as folder,
            patch("src.reporting.export.REPORTS_DIR", Path(folder) / "informes"),
        ):
            text_path = analysis.report(generated_on=date_of_report)
            report = text_path.read_text(encoding="utf-8")
            self.assertEqual(text_path.name, "2026-10-28_15-30-45.md")
            self.assertEqual(text_path.parent.name, text_path.stem)
            self.assertEqual(text_path.parent.parent, Path(folder) / "informes")
            self.assertIn("28/10/2026", report)
            self.assertIn("Información de los activos seleccionados", report)
            images = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", report)
            self.assertEqual(len(images), 4)
            for relative_path in images:
                self.assertEqual(Path(relative_path).parent, Path("."))
                self.assertGreater((text_path.parent / relative_path).stat().st_size, 0)
            figures = analysis.plots_report(Path(folder) / "graficos")
            self.assertEqual(set(figures), {"portfolio", "assets", "distribution", "risk_return"})
            for name in (
                "analisis_cartera",
                "evolucion_activos",
                "distribucion_rentabilidades",
                "riesgo_rentabilidad",
            ):
                self.assertGreater((Path(folder) / "graficos" / f"{name}.png").stat().st_size, 0)
            for figure in figures.values():
                plt.close(figure)
        self.assertEqual(plt.get_fignums(), [])

    def test_report_includes_instrument_information_and_individual_results(self):
        data = history("A", [100, 120, 96])
        data.info.update(
            {
                "name": "Empresa A",
                "asset_type": "stock",
                "sector": "Technology",
                "country": "United States",
            }
        )
        analysis = buy_and_hold_portfolio([Asset(data)], [10]).analyze()
        report = analysis.markdown()
        for text in [
            "Empresa A",
            "Acción",
            "Tecnología",
            "Estados Unidos",
            "USD",
            "Análisis de cada activo",
            "960,00",
        ]:
            self.assertIn(text, report)
        self.assertAlmostEqual(analysis.asset_details.loc["A", "total_return"], -0.04)
        self.assertAlmostEqual(analysis.asset_details.loc["A", "max_drawdown"], -0.2)

    def test_report_includes_simulation_and_its_chart(self):
        portfolio = buy_and_hold_portfolio([Asset(history("A", [100, 120, 96]))], [1])
        result = portfolio.monte_carlo(steps=2, simulations=5, seed=2)
        with (
            tempfile.TemporaryDirectory() as folder,
            patch("src.reporting.export.REPORTS_DIR", Path(folder) / "informes"),
        ):
            path = portfolio.report(simulation=result)
            report = path.read_text(encoding="utf-8")
            self.assertIn("Simulación de Monte Carlo", report)
            self.assertIn("Retorno anual μ", report)
            self.assertIn("Probabilidad estimada de pérdida", report)
            self.assertTrue((path.parent / "simulacion_monte_carlo.png").is_file())

    def test_reports_generated_in_the_same_second_do_not_overwrite(self):
        analysis = buy_and_hold_portfolio([Asset(history("A", [100, 120, 96]))], [1]).analyze()
        instant = datetime(2026, 10, 28, 15, 30, 45, 123456)
        with (
            tempfile.TemporaryDirectory() as folder,
            patch("src.reporting.export.REPORTS_DIR", Path(folder) / "informes"),
        ):
            first = analysis.report(generated_on=instant)
            second = analysis.report(generated_on=instant)
            self.assertNotEqual(first, second)
            self.assertTrue(first.is_file())
            self.assertTrue(second.is_file())

    def test_quality_distinguishes_yahoo_close_from_adjusted_close(self):
        data = history("A", [100, 100, 100], extra={"Adj Close": [90, 95, 100]})
        data.info["price_adjustment"] = "split_adjusted"
        portfolio = buy_and_hold_portfolio([Asset(data)], [1])
        close_report = portfolio.analyze().markdown()
        adjusted_report = portfolio.analyze(price_column="Adj Close").markdown()
        self.assertIn(
            "Yahoo: ajustado por desdoblamientos; sin ajuste por dividendos", close_report
        )
        self.assertIn(
            "Crecimiento con cierre ajustado por desdoblamientos y distribuciones", adjusted_report
        )
        self.assertTrue(portfolio.analyze().data_quality.loc["A", "adjusted_close_available"])

    def test_report_rejects_mismatched_simulation(self):
        portfolio = buy_and_hold_portfolio([Asset(history("A", [100, 120, 96]))], [1])
        result = portfolio.monte_carlo(steps=2, simulations=5, seed=2)
        result.currency = "EUR"
        with (
            tempfile.TemporaryDirectory() as folder,
            patch("src.reporting.export.REPORTS_DIR", Path(folder) / "informes"),
        ):
            with self.assertRaisesRegex(ValueError, "misma divisa"):
                portfolio.report(simulation=result)

    def test_flat_history_has_undefined_risk_ratios_without_infinity(self):
        analysis = buy_and_hold_portfolio([Asset(history("A", [100, 100, 100]))], [1]).analyze()
        self.assertEqual(analysis.metrics["annualized_volatility"], 0)
        self.assertEqual(analysis.metrics["max_drawdown"], 0)
        self.assertTrue(analysis.risk_contributions.isna().all())

    def test_report_rejects_simulation_with_same_total_but_different_weights(self):
        assets = [Asset(history("A", [100, 120, 100])), Asset(history("B", [100, 90, 100]))]
        portfolio = buy_and_hold_portfolio(assets, [1, 2])
        other = buy_and_hold_portfolio(assets, [2, 1])
        simulation = other.monte_carlo(steps=2, simulations=5, seed=2)
        with (
            tempfile.TemporaryDirectory() as folder,
            patch("src.reporting.export.REPORTS_DIR", Path(folder) / "informes"),
        ):
            with self.assertRaisesRegex(ValueError, "mismos activos"):
                portfolio.report(simulation=simulation)
            self.assertFalse((Path(folder) / "informes").exists())

    def test_adjusted_analysis_accepts_simulation_starting_at_current_holding_value(self):
        data = history("A", [100, 100, 100], extra={"Adj Close": [90, 95, 100]})
        portfolio = buy_and_hold_portfolio([Asset(data)], [2])
        simulation = portfolio.monte_carlo(steps=2, simulations=5, seed=2, price_column="Adj Close")
        with (
            tempfile.TemporaryDirectory() as folder,
            patch("src.reporting.export.REPORTS_DIR", Path(folder) / "informes"),
        ):
            path = portfolio.report(price_column="Adj Close", simulation=simulation)
            self.assertTrue(path.is_file())

    def test_report_rejects_simulation_with_different_calculation_criteria(self):
        portfolio = buy_and_hold_portfolio([Asset(history("A", [100, 120, 96]))], [1])
        simulation = portfolio.monte_carlo(steps=2, simulations=5, seed=2, periods_per_year=12)
        with (
            tempfile.TemporaryDirectory() as folder,
            patch("src.reporting.export.REPORTS_DIR", Path(folder) / "informes"),
        ):
            with self.assertRaisesRegex(ValueError, "criterios de cálculo"):
                portfolio.report(simulation=simulation)

    def test_reported_beta_is_separate_from_calculated_asset_and_portfolio_beta(self):
        data = history("A", [100, 120, 96])
        data.info.update({"beta": 7, "market_cap": 1000000, "pe_ratio": 15})
        benchmark = history("INDEX", [100, 110, 99])
        portfolio = buy_and_hold_portfolio(
            [Asset(data)], [1], market_context=MarketContext(benchmark=benchmark)
        )
        analysis = portfolio.analyze()
        self.assertAlmostEqual(analysis.metrics["beta"], 2)
        self.assertAlmostEqual(analysis.asset_details.loc["A", "calculated_beta"], 2)
        self.assertEqual(analysis.asset_details.loc["A", "reported_beta"], 7)
        text = analysis.markdown()
        self.assertIn("Beta publicada", text)
        self.assertIn("Beta calculada de la cartera", text)
        self.assertIn("1.000.000,00", text)
        self.assertNotIn("beta", analysis.metric_notes)

    def test_benchmark_uses_common_observations_without_filling_other_market_holidays(self):
        dates = pd.date_range("2026-01-01", periods=5)
        data = history("A", [100, 105, 110, 108, 115], dates=dates)
        selected = dates[[0, 2, 3, 4]]
        benchmark = history("INDEX", [100, 110, 108, 115], dates=selected)
        analysis = buy_and_hold_portfolio(
            [Asset(data)], [1], market_context=MarketContext(benchmark=benchmark)
        ).analyze()
        self.assertAlmostEqual(analysis.metrics["beta"], 1)
        self.assertAlmostEqual(analysis.metrics["difference_from_benchmark"], 0)
        self.assertTrue(any("4 fechas comunes" in message for message in analysis.warnings))

    def test_missing_fundamentals_are_nan_and_zero_beta_is_kept(self):
        data = history("A", [100, 120, 96])
        data.info.update({"beta": 0.0, "pe_ratio": float("nan"), "asset_type": "stock"})
        analysis = buy_and_hold_portfolio([Asset(data)], [1]).analyze()
        self.assertEqual(analysis.asset_details.loc["A", "reported_beta"], 0)
        self.assertEqual(analysis.asset_details.loc["A", "asset_type"], "stock")
        self.assertTrue(np.isnan(analysis.asset_details.loc["A", "pe_ratio"]))
        self.assertTrue(np.isnan(analysis.asset_details.loc["A", "market_cap"]))

    def test_monthly_data_with_daily_annualization_is_flagged(self):
        dates = pd.to_datetime(["2025-01-31", "2025-02-28", "2025-03-31"])
        portfolio = buy_and_hold_portfolio([Asset(history("A", [100, 110, 121], dates=dates))], [1])
        daily = portfolio.analyze()
        self.assertTrue(any("periods_per_year" in message for message in daily.warnings))
        monthly = portfolio.analyze(periods_per_year=12)
        self.assertFalse(any("periods_per_year" in message for message in monthly.warnings))
        self.assertAlmostEqual(monthly.metrics["annualized_return"], 1.1**12 - 1)

    def test_monthly_inflation_allows_normal_publication_lag(self):
        dates = pd.to_datetime(["2026-09-01", "2026-10-01", "2026-10-27"])
        prices = history("A", [100, 110, 108], dates=dates)
        inflation = indicator(
            [100, 103], pd.to_datetime(["2026-08-01", "2026-09-01"]), "Index 2020=100"
        )
        inflation.frequency = "Monthly"
        analysis = buy_and_hold_portfolio(
            [Asset(prices)], [1], market_context=MarketContext(inflation=inflation)
        ).analyze(periods_per_year=2)
        # September's observation is 56 days old at the end, not an invalid monthly value.
        self.assertTrue(np.isfinite(analysis.metrics["real_annualized_return"]))

    def test_unavailable_metrics_explain_which_data_is_missing(self):
        text = (
            buy_and_hold_portfolio([Asset(history("A", [100, 120, 96]))], [1]).analyze().markdown()
        )
        self.assertIn("Motivo: No se ha cargado un índice de referencia", text)
        self.assertIn("Motivo: No se ha cargado un tipo de interés de referencia", text)
        self.assertIn("Motivo: No se ha cargado un índice de precios de consumo", text)


class BacktestTests(unittest.TestCase):
    def test_month_end_rebalance_changes_strategy_but_not_input_weights(self):
        prices = pd.DataFrame(
            {"A": [100, 200, 100], "B": [100, 100, 100]},
            index=pd.to_datetime(["2026-01-30", "2026-01-31", "2026-02-01"]),
        )
        weights = pd.Series({"A": 0.5, "B": 0.5})
        buy_hold = backtest_allocation(prices, weights, initial_capital=100)
        monthly = backtest_allocation(prices, weights, initial_capital=100, rebalance="monthly")
        np.testing.assert_allclose(buy_hold.sum(axis=1), [100, 150, 100])
        np.testing.assert_allclose(monthly.sum(axis=1), [100, 150, 112.5])
        np.testing.assert_allclose(monthly.iloc[1], [75, 75])
        np.testing.assert_allclose(weights, [0.5, 0.5])

    def test_invalid_strategy_inputs_are_rejected(self):
        prices = history("A", [100, 120, 96]).prices.rename(columns={"Close": "A"})
        for weights in [pd.Series({"A": 2}), pd.Series({"OTHER": 1}), pd.Series({"A": np.nan})]:
            with self.assertRaises(ValueError):
                backtest_allocation(prices, weights)
        with self.assertRaises(ValueError):
            backtest_allocation(prices.iloc[::-1], pd.Series({"A": 1}))


class MarketLoaderTests(unittest.TestCase):
    def test_currency_loader_downloads_one_direct_pair_per_currency(self):
        assets = [Asset(history("A", [100, 102, 99])), Asset(history("B", [100, 101, 103]))]
        rate_history = history("USDEUR=X", [0.9, 0.91, 0.92], "EUR")
        with patch("src.market_loader.YahooFinanceAPI") as yahoo:
            yahoo.return_value.get_prices.return_value = rate_history
            context = load_currency_context(assets, "EUR", "2026-01-01", "2026-02-01")
        yahoo.return_value.get_prices.assert_called_once_with(
            "USDEUR=X", "2025-12-25", "2026-02-01", adjusted=False
        )
        converted = context.convert(assets[0].history.closing_prices(), "USD", "EUR")
        np.testing.assert_allclose(converted, [90, 92.82, 91.08])

    def test_currency_loader_avoids_requests_for_same_currency_and_pence(self):
        for source in ("GBP", "GBp"):
            assets = [Asset(history("A", [100, 102, 99], source))]
            with patch("src.market_loader.YahooFinanceAPI") as yahoo:
                context = load_currency_context(assets, "GBP", "2026-01-01", "2026-02-01")
                yahoo.return_value.get_prices.assert_not_called()
            converted = context.convert(assets[0].history.closing_prices(), source, "GBP")
            factor = 0.01 if source == "GBp" else 1
            np.testing.assert_allclose(converted, np.array([100, 102, 99]) * factor)

    def test_currency_loader_propagates_missing_exchange_rates(self):
        assets = [Asset(history("A", [100, 102, 99]))]
        with patch("src.market_loader.YahooFinanceAPI") as yahoo:
            yahoo.return_value.get_prices.side_effect = ProviderError("Cambio no disponible")
            with self.assertRaisesRegex(ProviderError, "Cambio no disponible"):
                load_currency_context(assets, "EUR", "2026-01-01", "2026-02-01")

    def test_no_provider_is_constructed_for_empty_context(self):
        with (
            patch("src.market_loader.FredAPI") as fred,
            patch("src.market_loader.YahooFinanceAPI") as yahoo,
        ):
            context = load_market_context("2026-01-01", "2026-02-01")
        fred.assert_not_called()
        yahoo.assert_not_called()
        self.assertIsNone(context.benchmark)

    def test_optional_failure_is_recorded_but_requested_fx_failure_is_fatal(self):
        yahoo = Mock(spec=YahooFinanceAPI)
        yahoo.get_prices.side_effect = ProviderError("Unavailable")
        context = load_market_context(
            "2026-01-01", "2026-02-01", price_provider=yahoo, benchmark_symbol="INDEX"
        )
        self.assertIn("No se ha podido descargar", context.issues[0])
        fred = Mock(spec=FredAPI)
        fred.get_series.side_effect = ProviderError("Unavailable")
        with self.assertRaises(ProviderError):
            load_market_context(
                "2026-01-01",
                "2026-02-01",
                fred_provider=fred,
                exchange_rate_series={("EUR", "USD"): "DEXUSEU"},
            )

    def test_loader_fetches_earlier_observations_and_declares_fx_direction(self):
        fred = Mock(spec=FredAPI)
        fred.get_series.return_value = indicator([1.1], pd.DatetimeIndex(["2026-01-01"]))
        context = load_market_context(
            "2026-01-01",
            "2026-02-01",
            fred_provider=fred,
            exchange_rate_series={("EUR", "USD"): "DEXUSEU"},
        )
        fred.get_series.assert_called_once_with("DEXUSEU", "2025-10-18", "2026-02-01")
        self.assertEqual(context.exchange_rates[0].base_currency, "EUR")

    def test_report_defaults_follow_reporting_currency_and_can_be_overridden(self):
        for currency, benchmark, rate in [
            ("USD", "^GSPC", "DGS3MO"),
            ("EUR", "^STOXX50E", "ECBESTRVOLWGTTRMDMNRT"),
        ]:
            portfolio = buy_and_hold_portfolio([Asset(history("A", [100, 120, 96], currency))], [1])
            with patch(
                "src.market_loader.load_market_context", return_value=MarketContext()
            ) as load:
                load_report_context(portfolio, "2026-01-01", "2026-02-01")
                self.assertEqual(load.call_args.kwargs["benchmark_symbol"], benchmark)
                self.assertEqual(load.call_args.kwargs["risk_free_series"], rate)
                load_report_context(
                    portfolio, "2026-01-01", "2026-02-01", benchmark_symbol="CUSTOM"
                )
                self.assertEqual(load.call_args.kwargs["benchmark_symbol"], "CUSTOM")

    def test_unknown_currency_does_not_get_a_us_reference_by_accident(self):
        portfolio = buy_and_hold_portfolio([Asset(history("A", [100, 120, 96], "CAD"))], [1])
        with patch("src.market_loader.load_market_context", return_value=MarketContext()) as load:
            context = load_report_context(portfolio, "2026-01-01", "2026-02-01")
        self.assertIsNone(load.call_args.kwargs["risk_free_series"])
        self.assertTrue(
            any(
                "No hay referencias económicas predeterminadas" in issue for issue in context.issues
            )
        )

    def test_missing_fred_key_is_an_optional_context_issue_but_fx_still_requires_it(self):
        with patch("src.market_loader.FredAPI", side_effect=ValueError("Missing key")):
            context = load_market_context("2026-01-01", "2026-02-01", inflation_series="CPIAUCSL")
            self.assertIn("FRED_API_KEY", context.issues[0])
            with self.assertRaises(ValueError):
                load_market_context(
                    "2026-01-01", "2026-02-01", exchange_rate_series={("EUR", "USD"): "DEXUSEU"}
                )
