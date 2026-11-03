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
from src.reporting.sections import SECTION_TITLES


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

    def test_holidays_at_the_close_of_a_period_do_not_make_it_partial(self):
        # 31/12/2021 sin cotización en Madrid: 2021 y 2022 siguen teniendo sus cierres.
        values = pd.Series(
            [100, 110, 121, 130],
            index=pd.to_datetime(["2020-12-31", "2021-12-30", "2022-12-30", "2023-03-31"]),
        )
        annual = calendar_returns(values, "Y")
        self.assertEqual(annual["partial"].tolist(), [False, False, True])
        # Viernes Santo a fin de marzo: el 28 cierra marzo y abre abril.
        monthly = calendar_returns(
            pd.Series(
                [100, 110, 121, 130],
                index=pd.to_datetime(["2024-02-29", "2024-03-28", "2024-04-30", "2024-05-31"]),
            ),
            "M",
        )
        self.assertEqual(monthly["partial"].tolist(), [False, False, False])

    def test_a_close_too_far_from_the_end_of_the_period_stays_partial(self):
        values = pd.Series(
            [100, 110, 121, 130],
            index=pd.to_datetime(["2025-01-31", "2025-02-20", "2025-03-31", "2025-04-30"]),
        )
        monthly = calendar_returns(values, "M")
        self.assertEqual(monthly["partial"].tolist(), [True, True, False])

    def test_the_last_period_is_partial_until_its_exact_close(self):
        # Sin datos posteriores, faltar unos días puede significar que no ha terminado.
        values = pd.Series(
            [100, 110, 121], index=pd.to_datetime(["2025-01-31", "2025-02-28", "2025-03-27"])
        )
        monthly = calendar_returns(values, "M")
        self.assertEqual(monthly["partial"].tolist(), [False, True])

    def test_only_complete_months_participate_in_best_and_worst(self):
        dates = pd.to_datetime(["2025-01-15", "2025-01-31", "2025-02-28", "2025-03-10"])
        analysis = buy_and_hold([Asset(history("A", [100, 200, 210, 400], dates=dates))], [1])
        text = analysis.analyze().markdown(sections=["returns"])
        self.assertIn("| Mejor mes | +5,00 % | 02/2025 |", text)
        self.assertIn("| Peor mes | +5,00 % | 02/2025 |", text)


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
        relaxed = portfolio.analyze(
            warning_thresholds=WarningThresholds(asset_weight=0.8, asset_weight_medium=0.8)
        )
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
                self.assertIn("| Par más correlacionado | No disponible |", text)
            plt.close(plot_analysis(analysis))

    def test_each_warning_is_formatted_with_its_unit(self):
        values = [100, 103, 99, 105]
        correlated = Portfolio(
            [Asset(history("A", values)), Asset(history("B", values))], {"A": 0.5, "B": 0.5}
        )
        self.assertIn(
            "Valor: 1,00; umbral: 0,80.", correlated.analyze().markdown(sections=["warnings"])
        )
        underwater = Portfolio([Asset(history("A", [100, 80, 85]))], {"A": 1})
        thresholds = WarningThresholds(drawdown=0.1)
        text = underwater.analyze(warning_thresholds=thresholds).markdown(sections=["warnings"])
        self.assertIn("Valor: 20,00 %; umbral: 10,00 %.", text)
        self.assertIn("Valor: 2 días naturales.", text)

    def test_missing_reference_stays_unavailable_and_is_visible_in_the_data_section(self):
        analysis = Portfolio([Asset(history("A", [100, 101, 99]))], {"A": 1}).analyze()
        self.assertTrue(np.isnan(analysis.metrics["sharpe"]))
        text = analysis.markdown(sections=["data"])
        self.assertIn("tipo de interés", text)
        self.assertIn("índice de referencia", text)

    def test_data_section_separates_data_problems_from_methodology_notes(self):
        dates = pd.bdate_range("2025-01-01", periods=5)
        portfolio = Portfolio(
            [Asset(history("A", [100, 101, 99, 102, 103], dates=dates))], {"A": 1}
        )
        references = MarketReferences(
            benchmark=history("INDEX", [100, 100, 101, 102, 101], dates=dates)
        )
        text = portfolio.analyze(references).markdown(sections=["data"])
        data, method = text.split("**Notas de metodología:**")
        self.assertIn("**Incidencias de los datos:**", data)
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
        # Cartera, índice y la línea de referencia en 100.
        lines = figure.axes[0].lines
        self.assertEqual(len(lines), 3)
        np.testing.assert_allclose(lines[0].get_ydata(), lines[1].get_ydata())
        self.assertAlmostEqual(lines[0].get_ydata()[0], 100)
        plt.close(figure)


class ReportSelectionTests(unittest.TestCase):
    def setUp(self):
        self.portfolio = Portfolio([Asset(history("A", [100, 95, 102]))], {"A": 1})
        self.analysis = self.portfolio.analyze()

    def test_every_section_is_collapsible_by_default_and_full_has_no_details(self):
        text = self.analysis.markdown()
        self.assertEqual(text.count("<details>"), len(SECTION_TITLES))
        self.assertLess(text.index("<b>1. Resumen</b>"), text.index("<b>2. Advertencias</b>"))
        full = self.analysis.markdown(detail="full")
        self.assertNotIn("<details>", full)
        self.assertIn("## 10. Calidad de los datos", full)

    def test_selective_export_generates_only_referenced_figures(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.analysis.report(
                sections=["diversification"], detail="full", directory=folder
            )
            self.assertEqual(
                {p.name for p in path.parent.glob("*.png")},
                {"correlaciones.png", "pesos_contribucion.png"},
            )
            text = path.read_text(encoding="utf-8")
            self.assertIn("correlaciones.png", text)
            self.assertNotIn("Rentabilidad", text)
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

    def test_export_retries_when_windows_briefly_locks_the_folder(self):
        # El antivirus de Windows puede bloquear un gráfico recién guardado unos instantes.
        rename = Path.rename
        attempts = []

        def locked_twice(source, target):
            attempts.append(target)
            if len(attempts) <= 2:
                raise PermissionError("[WinError 5] Acceso denegado")
            return rename(source, target)

        with (
            tempfile.TemporaryDirectory() as folder,
            patch.object(Path, "rename", locked_twice),
            patch("src.reporting.export.time.sleep") as wait,
        ):
            path = self.analysis.report(sections=["summary"], directory=folder)
            self.assertTrue(path.exists())
            self.assertEqual([p.name for p in Path(folder).iterdir()], [path.parent.name])
        self.assertEqual(len(attempts), 3)
        self.assertEqual(wait.call_count, 2)

    def test_export_gives_up_cleanly_if_the_folder_stays_locked(self):
        with (
            tempfile.TemporaryDirectory() as folder,
            patch.object(Path, "rename", side_effect=PermissionError("Acceso denegado")),
            patch("src.reporting.export.time.sleep") as wait,
        ):
            with self.assertRaises(PermissionError):
                self.analysis.report(sections=["summary"], directory=folder)
            self.assertEqual(list(Path(folder).iterdir()), [])
        self.assertEqual(wait.call_count, 5)
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
        figures = {"evolution": plt.figure(), "exposure": plt.figure()}
        with patch.object(figures["evolution"], "savefig", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                save_charts(figures, Path("unused"), close=True)
        self.assertEqual(plt.get_fignums(), [])
