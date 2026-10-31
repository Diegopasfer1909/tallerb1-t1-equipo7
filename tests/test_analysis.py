"""Known financial examples, independent of APIs and historical market prices."""

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import matplotlib
import numpy as np
import pandas as pd
from fixtures import buy_and_hold, history, indicator

from src.errors import ConfigurationError
from src.market_loader import (
    load_alfred_fx_rates,
    load_fx_rates,
    load_market_references,
    load_references,
)
from src.models import Asset, ExchangeRate, FxRates, MarketReferences
from src.models.backtest import backtest_allocation
from src.providers import AlfredAPI, ProviderError, YahooFinanceAPI

matplotlib.use("Agg")


class CurrencyTests(unittest.TestCase):
    def setUp(self):
        self.dates = pd.date_range("2026-01-01", periods=3)
        self.rate = ExchangeRate("EUR", "USD", indicator([1.1, 1.1, 1], self.dates))

    def test_foreign_value_weights_and_original_history(self):
        foreign = Asset(history("US", [110, 110, 110]))
        local = Asset(history("EU", [100, 100, 100], "EUR"))
        portfolio = buy_and_hold([foreign, local], [1, 1], "EUR", FxRates([self.rate]))
        self.assertEqual(portfolio.currency, "EUR")
        self.assertEqual(portfolio.total_value, 210)
        self.assertAlmostEqual(portfolio.current_weights["US"], 110 / 210)
        self.assertAlmostEqual(portfolio.close_prices()["US"].iloc[0], 100)
        self.assertEqual(foreign.history.prices["Close"].iloc[0], 110)
        self.assertAlmostEqual(portfolio.analyze().metrics["total_return"], 0.05)
        result = portfolio.monte_carlo(steps=2, simulations=3, seed=1)
        np.testing.assert_allclose(result.paths.iloc[0], 210)

    def test_rate_multiplies_in_forward_direction(self):
        prices = pd.Series([100, 100, 100], index=self.dates, name="A")
        converted = FxRates([self.rate]).convert(prices, "EUR", "USD")
        np.testing.assert_allclose(converted, [110, 110, 100])

    def test_past_rate_allowed_but_future_and_stale_rates_rejected(self):
        rate = ExchangeRate("EUR", "USD", indicator([1.1], self.dates[:1]), max_age_days=1)
        self.assertEqual(rate.on_dates(self.dates[1:2]).iloc[0], 1.1)
        for dates in [self.dates[2:], pd.DatetimeIndex(["2025-12-31"])]:
            with self.assertRaisesRegex(ValueError, "Faltan tipos de cambio"):
                rate.on_dates(dates)

    def test_no_missing_currency_or_exchange_rate_is_guessed(self):
        with self.assertRaisesRegex(ValueError, "Proporciona un tipo de cambio"):
            buy_and_hold([Asset(history("A", [1, 2, 3]))], [1], "EUR")
        with self.assertRaisesRegex(ValueError, "una sola serie de tipos de cambio"):
            FxRates([self.rate, self.rate])
        with self.assertRaisesRegex(ValueError, "positivo"):
            ExchangeRate("EUR", "USD", indicator([0], self.dates[:1]))

    def test_pence_are_normalized_only_for_explicit_conversion(self):
        asset = Asset(history("UK", [100, 200, 300], "GBp"))
        self.assertEqual(buy_and_hold([asset], [2]).total_value, 600)
        portfolio = buy_and_hold([asset], [2], "GBP")
        self.assertEqual(portfolio.total_value, 6)
        self.assertEqual(asset.latest_price, 300)


class AnalysisTests(unittest.TestCase):
    def test_report_estimates_match_the_parameters_used_in_simulation(self):
        portfolio = buy_and_hold([Asset(history("A", [100, 102, 99, 103]))], [2])
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
        portfolio = buy_and_hold([Asset(history("A", [100, 120, 96]))], [10])
        analysis = portfolio.analyze(periods_per_year=2)
        self.assertAlmostEqual(analysis.metrics["total_return"], -0.04)
        self.assertAlmostEqual(analysis.metrics["annualized_return"], -0.04)
        self.assertAlmostEqual(analysis.metrics["max_drawdown"], -0.2)
        self.assertAlmostEqual(analysis.metrics["effective_asset_count"], 1)
        self.assertAlmostEqual(analysis.risk_contributions["A"], 1)
        self.assertTrue(np.isnan(analysis.metrics["sharpe"]))

    def test_inflation_reference_and_benchmark_use_consistent_periods(self):
        dates = pd.to_datetime(["2026-01-01", "2026-02-01", "2026-03-01"])
        references = MarketReferences(
            benchmark=history("INDEX", [100, 102, 104], dates=dates),
            inflation=indicator([100, 101, 103], dates, "Index 2020=100"),
            risk_free_rate=indicator([2, 2, 2], dates),
        )
        portfolio = buy_and_hold([Asset(history("A", [100, 110, 108], dates=dates))], [1])
        metrics = portfolio.analyze(references, periods_per_year=2).metrics
        self.assertAlmostEqual(metrics["annualized_return"], 0.08)
        self.assertAlmostEqual(metrics["annualized_inflation"], 0.03)
        self.assertAlmostEqual(metrics["real_annualized_return"], 1.08 / 1.03 - 1)
        self.assertAlmostEqual(metrics["reference_annualized_return"], 0.02)
        self.assertAlmostEqual(metrics["difference_from_benchmark"], 0.04)
        self.assertTrue(np.isfinite(metrics["sharpe"]))

    def test_bad_or_stale_economic_data_omits_metrics_instead_of_assuming_zero(self):
        dates = pd.date_range("2026-01-01", periods=3)
        references = MarketReferences(
            inflation=indicator([3], dates[:1], "Percent"),
            risk_free_rate=indicator([2], pd.DatetimeIndex(["2025-01-01"])),
        )
        portfolio = buy_and_hold([Asset(history("A", [100, 110, 108]))], [1])
        analysis = portfolio.analyze(references)
        self.assertTrue(np.isnan(analysis.metrics["real_annualized_return"]))
        self.assertTrue(np.isnan(analysis.metrics["sharpe"]))
        self.assertTrue(
            any("suficientemente recientes" in notice.message for notice in analysis.notices)
        )

    def test_benchmark_does_not_fill_missing_prices_or_assume_currency(self):
        for benchmark in [history("INDEX", [1, 2]), history("INDEX", [1, 2, 3], currency="")]:
            with self.subTest(currency=benchmark.profile.currency):
                portfolio = buy_and_hold([Asset(history("A", [100, 110, 108]))], [1])
                analysis = portfolio.analyze(MarketReferences(benchmark=benchmark))
                self.assertTrue(np.isnan(analysis.metrics["benchmark_annualized_return"]))
                self.assertTrue(any("referencia" in notice.message for notice in analysis.notices))

    def test_current_weights_not_starting_weights_drive_risk_and_sectors(self):
        a = history("A", [100, 150, 200], sector="Technology")
        b = history("B", [100, 110, 100], sector="Utilities")
        portfolio = buy_and_hold([Asset(a), Asset(b)], [1, 1])
        analysis = portfolio.analyze()
        self.assertAlmostEqual(analysis.sector_weights["Technology"], 2 / 3)
        covariance = portfolio.returns().cov()
        weights = portfolio.current_weights
        expected = weights * (covariance @ weights) / (weights @ covariance @ weights)
        np.testing.assert_allclose(analysis.risk_contributions, expected)
        self.assertAlmostEqual(analysis.metrics["concentration_hhi"], 5 / 9)

    def test_quality_records_discarded_dates_and_partial_history(self):
        a = history("A", [1, 2, 3, 4])
        b = history("B", [1, 2, 3], partial_history=True)
        analysis = buy_and_hold([Asset(a), Asset(b)], [1, 1]).analyze()
        self.assertEqual(analysis.data_quality.loc["A", "excluded_observations"], 1)
        self.assertEqual(analysis.data_quality["dropped_rows"].sum(), 0)
        self.assertTrue(any("parte del historial" in notice.message for notice in analysis.notices))

    def test_adjusted_growth_is_anchored_to_raw_starting_values(self):
        data = history("A", [100, 100, 100], extra={"Adj Close": [50, 55, 60]})
        portfolio = buy_and_hold([Asset(data)], [2])
        analysis = portfolio.analyze(price_column="Adj Close")
        np.testing.assert_allclose(analysis.values, [200, 220, 240])
        self.assertEqual(analysis.holdings["value"].sum(), 240)
        self.assertAlmostEqual(analysis.metrics["total_return"], 0.2)
        # El precio mostrado corresponde a la misma columna que el valor de la posición.
        self.assertEqual(analysis.holdings.loc["A", "price"], 60)

    def test_unadjusted_prices_are_flagged_whatever_the_provider(self):
        unadjusted = buy_and_hold([Asset(history("A", [100, 120, 96]))], [1]).analyze()
        self.assertTrue(
            any(
                notice.message.startswith("A: los precios se utilizan sin ajustar")
                for notice in unadjusted.notices
            )
        )
        adjusted = buy_and_hold(
            [Asset(history("A", [100, 120, 96], price_basis="split_adjusted"))], [1]
        ).analyze()
        self.assertFalse(any("sin ajustar" in notice.message for notice in adjusted.notices))

    def test_spanish_markdown_can_be_built_without_writing_files(self):
        analysis = buy_and_hold([Asset(history("A", [100, 120, 96]))], [1]).analyze()
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

        analysis = buy_and_hold([Asset(history("A", [100, 120, 96]))], [1]).analyze()
        date_of_report = datetime(2026, 10, 28, 15, 30, 45)
        with tempfile.TemporaryDirectory() as folder:
            reports = Path(folder) / "informes"
            text_path = analysis.report(generated_on=date_of_report, directory=reports)
            report = text_path.read_text(encoding="utf-8")
            self.assertEqual(text_path.name, "2026-10-28_15-30-45.md")
            self.assertEqual(text_path.parent.name, text_path.stem)
            self.assertEqual(text_path.parent.parent, reports)
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
        data = history(
            "A",
            [100, 120, 96],
            name="Empresa A",
            asset_type="stock",
            sector="Technology",
            country="United States",
        )
        analysis = buy_and_hold([Asset(data)], [10]).analyze()
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
        portfolio = buy_and_hold([Asset(history("A", [100, 120, 96]))], [1])
        result = portfolio.monte_carlo(steps=2, simulations=5, seed=2)
        with tempfile.TemporaryDirectory() as folder:
            path = portfolio.report(simulation=result, directory=folder)
            report = path.read_text(encoding="utf-8")
            self.assertIn("Simulación de Monte Carlo", report)
            self.assertIn("Retorno anual μ", report)
            self.assertIn("Probabilidad estimada de pérdida", report)
            self.assertTrue((path.parent / "simulacion_monte_carlo.png").is_file())

    def test_reports_generated_in_the_same_second_do_not_overwrite(self):
        analysis = buy_and_hold([Asset(history("A", [100, 120, 96]))], [1]).analyze()
        instant = datetime(2026, 10, 28, 15, 30, 45, 123456)
        with tempfile.TemporaryDirectory() as folder:
            first = analysis.report(generated_on=instant, directory=folder)
            second = analysis.report(generated_on=instant, directory=folder)
            self.assertNotEqual(first, second)
            self.assertTrue(first.is_file())
            self.assertTrue(second.is_file())

    def test_quality_distinguishes_split_adjusted_close_from_adjusted_close(self):
        data = history(
            "A", [100, 100, 100], extra={"Adj Close": [90, 95, 100]}, price_basis="split_adjusted"
        )
        portfolio = buy_and_hold([Asset(data)], [1])
        close_report = portfolio.analyze().markdown()
        adjusted_report = portfolio.analyze(price_column="Adj Close").markdown()
        self.assertIn("Ajustado por desdoblamientos; sin ajuste por dividendos", close_report)
        self.assertIn(
            "Crecimiento con cierre ajustado por desdoblamientos y distribuciones", adjusted_report
        )
        self.assertTrue(portfolio.analyze().data_quality.loc["A", "adjusted_close_available"])

    def test_report_rejects_mismatched_simulation(self):
        portfolio = buy_and_hold([Asset(history("A", [100, 120, 96]))], [1])
        result = portfolio.monte_carlo(steps=2, simulations=5, seed=2)
        result.currency = "EUR"
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, "misma divisa"):
                portfolio.report(simulation=result, directory=folder)

    def test_flat_history_has_undefined_risk_ratios_without_infinity(self):
        analysis = buy_and_hold([Asset(history("A", [100, 100, 100]))], [1]).analyze()
        self.assertEqual(analysis.metrics["annualized_volatility"], 0)
        self.assertEqual(analysis.metrics["max_drawdown"], 0)
        self.assertTrue(analysis.risk_contributions.isna().all())

    def test_report_rejects_simulation_with_same_total_but_different_weights(self):
        assets = [Asset(history("A", [100, 120, 100])), Asset(history("B", [100, 90, 100]))]
        portfolio = buy_and_hold(assets, [1, 2])
        other = buy_and_hold(assets, [2, 1])
        simulation = other.monte_carlo(steps=2, simulations=5, seed=2)
        with tempfile.TemporaryDirectory() as folder:
            reports = Path(folder) / "informes"
            with self.assertRaisesRegex(ValueError, "mismos activos"):
                portfolio.report(simulation=simulation, directory=reports)
            self.assertFalse(reports.exists())

    def test_adjusted_analysis_accepts_simulation_starting_at_current_holding_value(self):
        data = history("A", [100, 100, 100], extra={"Adj Close": [90, 95, 100]})
        portfolio = buy_and_hold([Asset(data)], [2])
        simulation = portfolio.monte_carlo(steps=2, simulations=5, seed=2, price_column="Adj Close")
        with tempfile.TemporaryDirectory() as folder:
            path = portfolio.report(
                price_column="Adj Close", simulation=simulation, directory=folder
            )
            self.assertTrue(path.is_file())

    def test_report_rejects_simulation_with_different_calculation_criteria(self):
        portfolio = buy_and_hold([Asset(history("A", [100, 120, 96]))], [1])
        simulation = portfolio.monte_carlo(steps=2, simulations=5, seed=2, periods_per_year=12)
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, "criterios de cálculo"):
                portfolio.report(simulation=simulation, directory=folder)

    def test_reported_beta_is_separate_from_calculated_asset_and_portfolio_beta(self):
        data = history("A", [100, 120, 96], beta=7, market_cap=1000000, pe_ratio=15)
        benchmark = history("INDEX", [100, 110, 99])
        portfolio = buy_and_hold([Asset(data)], [1])
        analysis = portfolio.analyze(MarketReferences(benchmark=benchmark))
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
        analysis = buy_and_hold([Asset(data)], [1]).analyze(MarketReferences(benchmark=benchmark))
        self.assertAlmostEqual(analysis.metrics["beta"], 1)
        self.assertAlmostEqual(analysis.metrics["difference_from_benchmark"], 0)
        comparison = [notice for notice in analysis.notices if "4 fechas comunes" in notice.message]
        self.assertEqual([notice.kind for notice in comparison], ["method"])

    def test_missing_fundamentals_are_nan_and_zero_beta_is_kept(self):
        data = history("A", [100, 120, 96], beta=0.0, pe_ratio=float("nan"), asset_type="stock")
        analysis = buy_and_hold([Asset(data)], [1]).analyze()
        self.assertEqual(analysis.asset_details.loc["A", "reported_beta"], 0)
        self.assertEqual(analysis.asset_details.loc["A", "asset_type"], "stock")
        self.assertTrue(np.isnan(analysis.asset_details.loc["A", "pe_ratio"]))
        self.assertTrue(np.isnan(analysis.asset_details.loc["A", "market_cap"]))

    def test_monthly_data_with_daily_annualization_is_flagged(self):
        dates = pd.to_datetime(["2025-01-31", "2025-02-28", "2025-03-31"])
        portfolio = buy_and_hold([Asset(history("A", [100, 110, 121], dates=dates))], [1])
        daily = portfolio.analyze()
        self.assertTrue(any("periods_per_year" in notice.message for notice in daily.notices))
        monthly = portfolio.analyze(periods_per_year=12)
        self.assertFalse(any("periods_per_year" in notice.message for notice in monthly.notices))
        self.assertAlmostEqual(monthly.metrics["annualized_return"], 1.1**12 - 1)

    def test_monthly_inflation_allows_normal_publication_lag(self):
        dates = pd.to_datetime(["2026-09-01", "2026-10-01", "2026-10-27"])
        prices = history("A", [100, 110, 108], dates=dates)
        inflation = indicator(
            [100, 103],
            pd.to_datetime(["2026-08-01", "2026-09-01"]),
            "Index 2020=100",
            frequency="Monthly",
        )
        analysis = buy_and_hold([Asset(prices)], [1]).analyze(
            MarketReferences(inflation=inflation), periods_per_year=2
        )
        # September's observation is 56 days old at the end, not an invalid monthly value.
        self.assertTrue(np.isfinite(analysis.metrics["real_annualized_return"]))

    def test_notice_says_whether_economic_data_was_used_as_published(self):
        dates = pd.date_range("2026-01-01", periods=3)
        portfolio = buy_and_hold([Asset(history("A", [100, 110, 108], dates=dates))], [1])
        for point_in_time, text in ((True, "tal como se publicaron"), (False, "anticipación")):
            rate = indicator([2, 2, 2], dates, point_in_time=point_in_time)
            notices = portfolio.analyze(MarketReferences(risk_free_rate=rate)).notices
            methods = [notice.message for notice in notices if notice.kind == "method"]
            self.assertTrue(any(text in message for message in methods), methods)

    def test_unavailable_metrics_explain_which_data_is_missing(self):
        text = buy_and_hold([Asset(history("A", [100, 120, 96]))], [1]).analyze().markdown()
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
        yahoo = Mock(spec=YahooFinanceAPI)
        yahoo.get_prices.return_value = history("USDEUR=X", [0.9, 0.91, 0.92], "EUR")
        fx_rates = load_fx_rates(assets, "EUR", "2026-01-01", "2026-02-01", provider=yahoo)
        yahoo.get_prices.assert_called_once_with(
            "USDEUR=X", "2025-12-25", "2026-02-01", adjusted=False
        )
        converted = fx_rates.convert(assets[0].history.closing_prices(), "USD", "EUR")
        np.testing.assert_allclose(converted, [90, 92.82, 91.08])

    def test_currency_loader_avoids_requests_for_same_currency_and_pence(self):
        for source in ("GBP", "GBp"):
            assets = [Asset(history("A", [100, 102, 99], source))]
            yahoo = Mock(spec=YahooFinanceAPI)
            fx_rates = load_fx_rates(assets, "GBP", "2026-01-01", "2026-02-01", provider=yahoo)
            yahoo.get_prices.assert_not_called()
            converted = fx_rates.convert(assets[0].history.closing_prices(), source, "GBP")
            factor = 0.01 if source == "GBp" else 1
            np.testing.assert_allclose(converted, np.array([100, 102, 99]) * factor)

    def test_currency_loader_propagates_missing_exchange_rates(self):
        assets = [Asset(history("A", [100, 102, 99]))]
        yahoo = Mock(spec=YahooFinanceAPI)
        yahoo.get_prices.side_effect = ProviderError("Cambio no disponible")
        with self.assertRaisesRegex(ProviderError, "Cambio no disponible"):
            load_fx_rates(assets, "EUR", "2026-01-01", "2026-02-01", provider=yahoo)

    def test_no_provider_is_constructed_for_empty_references(self):
        with (
            patch("src.market_loader.AlfredAPI") as alfred,
            patch("src.market_loader.YahooFinanceAPI") as yahoo,
        ):
            references = load_market_references("2026-01-01", "2026-02-01")
        alfred.assert_not_called()
        yahoo.assert_not_called()
        self.assertIsNone(references.benchmark)

    def test_optional_failure_is_recorded_but_requested_fx_failure_is_fatal(self):
        yahoo = Mock(spec=YahooFinanceAPI)
        yahoo.get_prices.side_effect = ProviderError("Unavailable")
        references = load_market_references(
            "2026-01-01", "2026-02-01", price_provider=yahoo, benchmark_symbol="INDEX"
        )
        self.assertIn("No se ha podido descargar", references.notices[0].message)
        alfred = Mock(spec=AlfredAPI)
        alfred.get_series.side_effect = ProviderError("Unavailable")
        with self.assertRaises(ProviderError):
            load_alfred_fx_rates(
                {("EUR", "USD"): "DEXUSEU"}, "2026-01-01", "2026-02-01", alfred_provider=alfred
            )

    def test_loader_fetches_earlier_observations_and_declares_fx_direction(self):
        alfred = Mock(spec=AlfredAPI)
        alfred.get_series.return_value = indicator([1.1], pd.DatetimeIndex(["2026-01-01"]))
        fx_rates = load_alfred_fx_rates(
            {("EUR", "USD"): "DEXUSEU"}, "2026-01-01", "2026-02-01", alfred_provider=alfred
        )
        alfred.get_series.assert_called_once_with(
            "DEXUSEU", "2025-10-18", "2026-02-01", point_in_time=False
        )
        self.assertEqual(fx_rates.rates[0].base_currency, "EUR")

    def test_economic_references_are_requested_as_published(self):
        alfred = Mock(spec=AlfredAPI)
        alfred.get_series.return_value = indicator([300], pd.DatetimeIndex(["2025-12-15"]))
        load_market_references(
            "2026-01-01", "2026-02-01", alfred_provider=alfred, inflation_series="CPIAUCSL"
        )
        # Sin point_in_time=False: la inflación se pide tal como se publicó.
        alfred.get_series.assert_called_once_with("CPIAUCSL", "2025-10-18", "2026-02-01")

    def test_report_defaults_follow_reporting_currency_and_can_be_overridden(self):
        for currency, benchmark, rate in [
            ("USD", "^GSPC", "DGS3MO"),
            ("EUR", "^STOXX50E", "ECBESTRVOLWGTTRMDMNRT"),
        ]:
            with patch(
                "src.market_loader.load_market_references", return_value=MarketReferences()
            ) as load:
                load_references(currency, "2026-01-01", "2026-02-01")
                self.assertEqual(load.call_args.kwargs["benchmark_symbol"], benchmark)
                self.assertEqual(load.call_args.kwargs["risk_free_series"], rate)
                load_references(currency, "2026-01-01", "2026-02-01", benchmark_symbol="CUSTOM")
                self.assertEqual(load.call_args.kwargs["benchmark_symbol"], "CUSTOM")

    def test_unknown_currency_does_not_get_a_us_reference_by_accident(self):
        with patch(
            "src.market_loader.load_market_references", return_value=MarketReferences()
        ) as load:
            references = load_references("CAD", "2026-01-01", "2026-02-01")
        self.assertIsNone(load.call_args.kwargs["risk_free_series"])
        self.assertTrue(
            any(
                "No hay referencias económicas predeterminadas" in notice.message
                for notice in references.notices
            )
        )

    def test_missing_fred_key_is_an_optional_reference_issue_but_fx_still_requires_it(self):
        with patch("src.market_loader.AlfredAPI", side_effect=ConfigurationError("Missing key")):
            references = load_market_references(
                "2026-01-01", "2026-02-01", inflation_series="CPIAUCSL"
            )
            self.assertIn("FRED_API_KEY", references.notices[0].message)
            with self.assertRaises(ConfigurationError):
                load_alfred_fx_rates({("EUR", "USD"): "DEXUSEU"}, "2026-01-01", "2026-02-01")
