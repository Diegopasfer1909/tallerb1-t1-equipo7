"""Casos numéricos y contratos de presentación sin descargas."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from fixtures import buy_and_hold, history, indicator

from src.analysis import WarningThresholds
from src.analysis.metrics import calendar_returns, drawdown_episode
from src.main import parse_arguments
from src.models import Asset, ExchangeRate, FxRates, MarketReferences, Portfolio
from src.reporting.plots import plot_analysis, save_charts


class DrawdownTests(unittest.TestCase):
    def episode(self, prices):
        return drawdown_episode(
            pd.Series(prices, index=pd.date_range("2025-01-01", periods=len(prices)))
        )

    def test_initial_capital_is_a_peak_and_unrecovered_duration_ends_at_last_date(self):
        episode = self.episode([100, 80, 88])
        self.assertAlmostEqual(episode.depth, -0.2)
        self.assertEqual(episode.peak, pd.Timestamp("2025-01-01"))
        self.assertEqual(episode.trough, pd.Timestamp("2025-01-02"))
        self.assertIsNone(episode.recovery)
        self.assertEqual(episode.underwater_days, 2)

    def test_last_tied_peak_and_first_recovery_are_used(self):
        episode = self.episode([100, 110, 105, 110, 80, 110, 120])
        self.assertEqual(episode.peak, pd.Timestamp("2025-01-04"))
        self.assertEqual(episode.trough, pd.Timestamp("2025-01-05"))
        self.assertEqual(episode.recovery, pd.Timestamp("2025-01-06"))
        self.assertEqual(episode.underwater_days, 2)

    def test_flat_and_increasing_histories_have_no_episode(self):
        for values in ([100, 100, 100], [100, 110, 120]):
            episode = self.episode(values)
            self.assertEqual(episode.depth, 0)
            self.assertIsNone(episode.peak)
            self.assertIsNone(episode.trough)
            self.assertEqual(episode.underwater_days, 0)


class CalendarTests(unittest.TestCase):
    def test_returns_compound_and_partial_months_are_flagged(self):
        values = pd.Series(
            [100, 110, 99, 108.9, 120],
            index=pd.to_datetime(
                ["2025-01-15", "2025-01-31", "2025-02-14", "2025-02-28", "2025-03-10"]
            ),
        )
        monthly = calendar_returns(values, "M")
        np.testing.assert_allclose(monthly["return"], [0.1, -0.01, 120 / 108.9 - 1])
        self.assertEqual(monthly["partial"].tolist(), [True, False, True])
        self.assertEqual(monthly["observations"].tolist(), [1, 2, 1])
        self.assertAlmostEqual((1 + monthly["return"]).prod() - 1, 0.2)

    def test_empty_months_do_not_become_zero_and_cross_month_gap_is_not_attributed(self):
        values = pd.Series(
            [100, 120, 125], index=pd.to_datetime(["2025-01-31", "2025-03-31", "2025-04-30"])
        )
        monthly = calendar_returns(values, "M")
        self.assertNotIn(pd.Period("2025-02"), monthly.index)
        self.assertTrue(np.isnan(monthly.loc[pd.Period("2025-03"), "return"]))
        self.assertAlmostEqual(monthly.loc[pd.Period("2025-04"), "return"], 125 / 120 - 1)

    def test_annual_returns_require_prior_year_close_and_mark_current_year_partial(self):
        values = pd.Series(
            [100, 110, 121, 130],
            index=pd.to_datetime(["2024-12-31", "2025-06-30", "2025-12-31", "2026-03-31"]),
        )
        annual = calendar_returns(values, "Y")
        self.assertAlmostEqual(annual.loc[pd.Period("2025", freq="Y"), "return"], 0.21)
        self.assertEqual(annual["partial"].tolist(), [False, True])

    def test_only_complete_months_participate_in_best_and_worst(self):
        dates = pd.to_datetime(["2025-01-15", "2025-01-31", "2025-02-28", "2025-03-10"])
        analysis = buy_and_hold([Asset(history("A", [100, 200, 210, 400], dates=dates))], [1])
        text = analysis.analyze().markdown(sections=["performance"])
        self.assertIn("| Mejor | 2025-02 | 5,00 % |", text)
        self.assertIn("| Peor | 2025-02 | 5,00 % |", text)


class DiagnosticsTests(unittest.TestCase):
    def test_current_weights_drive_threshold_and_unknown_sector_is_not_a_sector_bet(self):
        portfolio = Portfolio(
            [Asset(history("A", [100, 200, 400])), Asset(history("B", [100, 99, 100]))],
            {"A": 0.25, "B": 0.75},
            rebalance=None,
        )
        analysis = portfolio.analyze(warning_thresholds=WarningThresholds(asset_weight=0.55))
        warnings = {warning.code: warning for warning in analysis.risk_warnings}
        self.assertIn("A:", warnings["asset_concentration"].message)
        self.assertAlmostEqual(warnings["asset_concentration"].observed, 4 / 7)
        self.assertNotIn("sector_concentration", warnings)
        relaxed = portfolio.analyze(warning_thresholds=WarningThresholds(asset_weight=0.8))
        self.assertNotIn("asset_concentration", {w.code for w in relaxed.risk_warnings})

    def test_thresholds_are_validated_and_configurable(self):
        for kwargs in (
            {"correlation": 1.1},
            {"drawdown": -0.3},
            {"sector_weight": True},
            {"asset_weight": 1.5},
            {"volatility": np.nan},
            {"volatility": "high"},
        ):
            with self.assertRaises(ValueError):
                WarningThresholds(**kwargs)
        portfolio = Portfolio([Asset(history("A", [100, 80, 85]))], {"A": 1}, rebalance=None)
        low = portfolio.analyze(warning_thresholds=WarningThresholds(drawdown=0.1))
        high = portfolio.analyze(warning_thresholds=WarningThresholds(drawdown=0.4))
        self.assertIn("large_drawdown", {w.code for w in low.risk_warnings})
        self.assertNotIn("large_drawdown", {w.code for w in high.risk_warnings})
        with self.assertRaises(TypeError):
            portfolio.analyze(warning_thresholds={"drawdown": 0.4})

    def test_identical_assets_have_one_pair_and_flat_assets_have_none(self):
        for values, expected_pairs in (([100, 103, 99, 105], 1), ([100, 100, 100, 100], 0)):
            portfolio = Portfolio(
                [Asset(history("A", values)), Asset(history("B", values))], {"A": 0.5, "B": 0.5}
            )
            analysis = portfolio.analyze()
            self.assertEqual(len(analysis.correlation_pairs), expected_pairs)
            self.assertEqual(
                "high_correlation" in {w.code for w in analysis.risk_warnings}, bool(expected_pairs)
            )
            text = analysis.markdown()
            self.assertNotRegex(text, r"\| -?inf(?: %)? \|")
            if not expected_pairs:
                self.assertIn("No hay pares", text)
            plt.close(plot_analysis(analysis))

    def test_each_warning_is_formatted_with_its_unit(self):
        values = [100, 103, 99, 105]
        correlated = Portfolio(
            [Asset(history("A", values)), Asset(history("B", values))], {"A": 0.5, "B": 0.5}
        )
        self.assertIn("| 1,00 | 0,80 |", correlated.analyze().markdown(sections=["warnings"]))
        underwater = Portfolio([Asset(history("A", [100, 80, 85]))], {"A": 1})
        thresholds = WarningThresholds(drawdown=0.1)
        text = underwater.analyze(warning_thresholds=thresholds).markdown(sections=["warnings"])
        self.assertIn("| 20,00 % | 10,00 % |", text)
        self.assertIn("| 2 días naturales | — |", text)

    def test_missing_reference_stays_unavailable_and_is_visible_in_warning_only_report(self):
        analysis = Portfolio([Asset(history("A", [100, 101, 99]))], {"A": 1}).analyze()
        self.assertTrue(np.isnan(analysis.metrics["sharpe"]))
        text = analysis.markdown(sections=["warnings"])
        self.assertIn("tipo de interés", text)
        self.assertIn("índice de referencia", text)

    def test_warnings_separate_data_problems_from_methodology_notes(self):
        dates = pd.bdate_range("2025-01-01", periods=5)
        portfolio = Portfolio(
            [Asset(history("A", [100, 101, 99, 102, 103], dates=dates))], {"A": 1}
        )
        references = MarketReferences(
            benchmark=history("INDEX", [100, 100, 101, 102, 101], dates=dates)
        )
        text = portfolio.analyze(references).markdown(sections=["warnings"])
        data, method = text.split("### Notas de metodología")
        self.assertIn("### Datos que revisar", data)
        self.assertIn("No se ha cargado un tipo de interés de referencia", data)
        self.assertIn("Comparación con el índice INDEX basada en 5 fechas comunes", method)

    def test_benchmark_chart_uses_matching_dates_and_converted_currency(self):
        dates = pd.bdate_range("2025-01-01", periods=5)
        asset = Asset(history("A", [100] * 5, dates=dates))
        fx_rates = FxRates(
            [ExchangeRate("EUR", "USD", indicator([1, 1.05, 1.1, 1.15, 1.2], dates))]
        )
        references = MarketReferences(benchmark=history("INDEX", [100] * 3, dates=dates[[0, 2, 4]]))
        analysis = Portfolio([asset], {"A": 1}, "EUR", fx_rates).analyze(references)
        comparison = analysis.benchmark_comparison
        np.testing.assert_allclose(
            comparison["portfolio"] / comparison["portfolio"].iloc[0],
            comparison["benchmark"] / comparison["benchmark"].iloc[0],
        )
        self.assertEqual(len(comparison), 3)
        figure = plot_analysis(analysis)
        lines = figure.axes[0].lines
        self.assertEqual(len(lines), 2)
        np.testing.assert_allclose(lines[0].get_ydata(), lines[1].get_ydata())
        self.assertAlmostEqual(lines[0].get_ydata()[0], 100)
        plt.close(figure)


class ReportSelectionTests(unittest.TestCase):
    def setUp(self):
        self.portfolio = Portfolio([Asset(history("A", [100, 95, 102]))], {"A": 1})
        self.analysis = self.portfolio.analyze()

    def test_default_shows_summary_and_warnings_and_full_has_no_details(self):
        text = self.analysis.markdown()
        self.assertLess(text.index("## 1. Resumen"), text.index("## 2. Advertencias"))
        self.assertLess(text.index("## 2. Advertencias"), text.index("<details>"))
        self.assertNotIn("<details>", self.analysis.markdown(detail="full"))

    def test_selective_export_generates_only_referenced_figures(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.analysis.report(
                sections=["diversification"], detail="full", directory=folder
            )
            self.assertEqual(
                {p.name for p in path.parent.glob("*.png")}, {"distribucion_rentabilidades.png"}
            )
            self.assertIn("distribucion_rentabilidades.png", path.read_text())
            self.assertNotIn("Resultados históricos", path.read_text())
        self.assertEqual(plt.get_fignums(), [])

    def test_summary_only_skips_simulation_and_charts(self):
        with (
            tempfile.TemporaryDirectory() as folder,
            patch.object(Portfolio, "monte_carlo") as simulate,
        ):
            path = self.portfolio.report(sections=["summary", "warnings"], directory=folder)
            self.assertEqual(list(path.parent.glob("*.png")), [])
        simulate.assert_not_called()

    def test_invalid_options_fail_before_simulation_or_creating_a_directory(self):
        for options in (
            {"sections": "summary"},
            {"sections": []},
            {"sections": ["typo"]},
            {"detail": "typo"},
        ):
            with (
                patch.object(Portfolio, "monte_carlo") as simulate,
                patch("pathlib.Path.mkdir") as mkdir,
            ):
                with self.assertRaises(ValueError):
                    self.portfolio.report(**options)
            simulate.assert_not_called()
            mkdir.assert_not_called()

    def test_failed_export_leaves_no_folder_or_open_figures(self):
        with (
            tempfile.TemporaryDirectory() as folder,
            patch("src.reporting.export.build_report", side_effect=RuntimeError("disco lleno")),
        ):
            with self.assertRaises(RuntimeError):
                self.analysis.report(directory=folder)
            self.assertEqual(list(Path(folder).iterdir()), [])
        self.assertEqual(plt.get_fignums(), [])

    def test_reports_default_to_a_folder_in_the_current_directory(self):
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as folder:
            os.chdir(folder)
            try:
                path = self.analysis.report(sections=["summary"])
                self.assertEqual(path.resolve().parent.parent, Path(folder).resolve() / "informes")
            finally:
                os.chdir(previous)

    def test_cli_selection_skips_unrequested_simulation(self):
        config = parse_arguments(
            [
                "--assets",
                "A:1",
                "--report",
                "--report-sections",
                "summary",
                "warnings",
                "--report-detail",
                "full",
            ]
        )
        self.assertIsNone(config.simulation)
        self.assertEqual(config.report_detail, "full")
        config = parse_arguments(
            ["--assets", "A:1", "--report", "--report-sections", "summary", "--simulate"]
        )
        self.assertIsNotNone(config.simulation)

    def test_all_figures_close_when_saving_fails(self):
        figures = {"portfolio": plt.figure(), "assets": plt.figure()}
        with patch.object(figures["portfolio"], "savefig", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                save_charts(figures, Path("unused"), close=True)
        self.assertEqual(plt.get_fignums(), [])
