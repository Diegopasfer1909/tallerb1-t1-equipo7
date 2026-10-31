"""Contratos de inmutabilidad, tiempo y elección del índice de referencia, sin descargas."""

import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
from fixtures import asset, buy_and_hold, history, indicator

from src.analysis.metrics import annualized_growth
from src.constants import ADJ_CLOSE
from src.main import main, parse_arguments
from src.market_loader import load_market_references, load_references
from src.models import Asset, ExchangeRate, MarketReferences, Portfolio, PriceHistory
from src.providers import ProviderError
from src.reporting.report import build_report


class SnapshotTests(unittest.TestCase):
    def test_changing_a_copy_of_the_prices_keeps_asset_and_portfolio_consistent(self):
        item = asset("A", [100, 102, 104])
        portfolio = buy_and_hold([item], [100])
        prices = item.history.prices
        prices.loc[prices.index[-1], "Close"] = 208
        prices["Close"] = 1
        self.assertEqual(item.latest_price, 104)
        self.assertEqual(portfolio.total_value, 10_400)
        self.assertEqual(item.history.prices["Close"].iloc[-1], 104)

    def test_weights_and_exchange_rates_are_read_only(self):
        portfolio = Portfolio([asset("A", [1, 2, 3]), asset("B", [1, 2, 3])], {"A": 0.6, "B": 0.4})
        with self.assertRaises(ValueError):
            portfolio.target_weights["A"] = 1
        rate = ExchangeRate(
            "EUR", "USD", indicator([1.1, 1.1], pd.date_range("2026-01-01", periods=2))
        )
        with self.assertRaises(ValueError):
            rate.indicator.values.iloc[0] = 2
        other = replace(portfolio, target_weights={"A": 0.5, "B": 0.5})
        np.testing.assert_allclose(other.target_weights, [0.5, 0.5])
        np.testing.assert_allclose(portfolio.target_weights, [0.6, 0.4])

    def test_statistics_are_computed_at_creation_for_price_columns_only(self):
        data = history("A", [100, 104], extra={"Open": [99, 103], "Volume": [10, 2_000]})
        self.assertEqual(list(data.mean.index), ["Open", "Close"])
        self.assertEqual(data.mean["Close"], 102)
        self.assertAlmostEqual(data.std["Open"], 8**0.5)
        statistics = data.mean
        statistics["Close"] = 0
        self.assertEqual(data.mean["Close"], 102)

    def test_constructor_still_takes_prices_and_rejects_invalid_tables(self):
        frame = pd.DataFrame({"Close": [1.0, 2.0]}, index=pd.date_range("2026-01-01", periods=2))
        self.assertEqual(len(PriceHistory("A", "test", prices=frame).prices), 2)
        with self.assertRaises(TypeError):
            PriceHistory("A", "test", frame["Close"])


class TemporalContractTests(unittest.TestCase):
    def test_dropping_intermediate_dates_does_not_change_annualized_growth(self):
        dates = pd.bdate_range("2026-01-05", periods=5)
        values = pd.Series([100, 101, 103, 102, 105], index=dates, dtype=float)
        self.assertAlmostEqual(annualized_growth(values), annualized_growth(values.iloc[::2]))

    def test_benchmark_comparison_uses_the_elapsed_time_of_its_common_dates(self):
        dates = pd.bdate_range("2026-01-05", periods=5)
        data = history("A", [100, 101, 103, 102, 105], dates=dates)
        benchmark = history("INDEX", [100, 103, 105], dates=dates[[0, 2, 4]])
        analysis = buy_and_hold([Asset(data)], [1]).analyze(MarketReferences(benchmark=benchmark))
        metrics = analysis.metrics
        self.assertAlmostEqual(
            metrics["comparison_portfolio_annualized_return"], metrics["annualized_return"]
        )
        self.assertAlmostEqual(metrics["difference_from_benchmark"], 0)

    def test_short_history_is_measured_in_days_and_sparse_samples_are_flagged(self):
        year = pd.bdate_range("2025-01-02", "2026-01-02")
        complete = buy_and_hold([asset("A", np.linspace(100, 110, len(year)), dates=year)], [1])
        messages = [notice.message for notice in complete.analyze().notices]
        self.assertFalse(any("menos de un año" in message for message in messages))
        self.assertFalse(any("rentabilidades en" in message for message in messages))
        sparse = year[::2]
        thin = buy_and_hold([asset("A", np.linspace(100, 110, len(sparse)), dates=sparse)], [1])
        messages = [notice.message for notice in thin.analyze().notices]
        self.assertTrue(any("se esperarían" in message for message in messages))
        short = buy_and_hold([asset("A", [100, 101, 102, 103])], [1])
        messages = [notice.message for notice in short.analyze().notices]
        self.assertTrue(any("3 días naturales, menos de un año" in message for message in messages))


class BenchmarkChoiceTests(unittest.TestCase):
    def setUp(self):
        self.dates = pd.date_range("2026-01-01", periods=4)
        self.index = history("^STOXX50E", [100, 101, 99, 102], "EUR", dates=self.dates)
        self.rate = history("EURUSD=X", [1.1] * 4, "USD", dates=self.dates)

    def test_benchmark_in_another_currency_brings_its_exchange_rate(self):
        provider = Mock()
        provider.get_prices.side_effect = lambda symbol, *args, **kwargs: {
            "^STOXX50E": self.index,
            "EURUSD=X": self.rate,
        }[symbol]
        references = load_market_references(
            "2026-01-01",
            "2026-01-05",
            price_provider=provider,
            benchmark_symbol="^STOXX50E",
            currency="USD",
        )
        self.assertEqual(references.notices, ())
        self.assertEqual(len(references.fx_rates.rates), 1)
        portfolio = buy_and_hold([asset("A", [100, 102, 99, 103], dates=self.dates)], [1])
        analysis = portfolio.analyze(references)
        self.assertEqual(analysis.benchmark_symbol, "^STOXX50E")
        np.testing.assert_allclose(analysis.benchmark_prices, [110, 111.1, 108.9, 112.2])
        self.assertIn("Tipo de cambio EUR/USD", analysis.reference_table.index)

    def test_missing_exchange_rate_is_a_notice_and_skips_the_comparison(self):
        def get_prices(symbol, *args, **kwargs):
            if symbol == "^STOXX50E":
                return self.index
            raise ProviderError("sin datos")

        provider = Mock()
        provider.get_prices.side_effect = get_prices
        references = load_market_references(
            "2026-01-01",
            "2026-01-05",
            price_provider=provider,
            benchmark_symbol="^STOXX50E",
            currency="USD",
        )
        self.assertIn("EUR/USD", references.notices[0].message)
        analysis = buy_and_hold([asset("A", [100, 102, 99, 103], dates=self.dates)], [1]).analyze(
            references
        )
        self.assertTrue(np.isnan(analysis.metrics["difference_from_benchmark"]))

    def test_user_benchmark_replaces_the_default_and_is_reported(self):
        with patch("src.market_loader.load_market_references") as load:
            load.return_value = MarketReferences()
            references = load_references(
                "USD", "2026-01-01", "2026-02-01", benchmark_symbol="^IXIC"
            )
        self.assertEqual(load.call_args.kwargs["benchmark_symbol"], "^IXIC")
        self.assertEqual(load.call_args.kwargs["inflation_series"], "CPIAUCSL")
        messages = [notice.message for notice in references.notices]
        self.assertTrue(any("elegido por el usuario: ^IXIC" in message for message in messages))

    def test_cli_option_requires_an_output_and_reaches_the_loader(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parse_arguments(["--assets", "IBM:1", "--benchmark", "^IXIC"])
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parse_arguments(["--assets", "IBM:1", "--report", "--benchmark", " "])
        config = parse_arguments(["--assets", "IBM:1", "--report", "--benchmark", " ^IXIC "])
        self.assertEqual(config.benchmark, "^IXIC")
        data = history("IBM", [100, 102, 99, 100], dates=self.dates)
        with tempfile.TemporaryDirectory() as folder:
            arguments = ["--assets", "IBM:1", "--report", "--benchmark", "^IXIC"]
            with (
                patch.dict(os.environ, {"FRED_API_KEY": "x"}),
                patch("src.main.load_dotenv"),
                patch("src.main.YahooFinanceAPI") as yahoo,
                patch("src.main.load_references", return_value=MarketReferences()) as load,
                redirect_stdout(io.StringIO()),
            ):
                yahoo.return_value.get_prices.return_value = data
                self.assertEqual(main([*arguments, "--output-dir", str(Path(folder))]), 0)
        self.assertEqual(load.call_args.kwargs["benchmark_symbol"], "^IXIC")

    def test_plots_with_benchmark_only_download_the_index(self):
        data = history("IBM", [100, 102, 99, 100], dates=self.dates)
        with (
            patch("src.main.load_dotenv"),
            patch("src.main.YahooFinanceAPI") as yahoo,
            patch("src.main.load_references") as full,
            patch("src.main.load_market_references", return_value=MarketReferences()) as index,
            patch("src.main.show_plots"),
            redirect_stdout(io.StringIO()),
        ):
            yahoo.return_value.get_prices.return_value = data
            self.assertEqual(main(["--assets", "IBM:1", "--plots-report", "--benchmark", "SPY"]), 0)
        full.assert_not_called()
        self.assertEqual(index.call_args.kwargs["benchmark_symbol"], "SPY")
        self.assertNotIn("inflation_series", index.call_args.kwargs)


class ReportTextTests(unittest.TestCase):
    def test_price_note_follows_the_column_used(self):
        data = history("A", [100, 102, 104], extra={ADJ_CLOSE: [99, 101, 104]})
        portfolio = buy_and_hold([Asset(data)], [1])
        adjusted = build_report(portfolio.analyze(price_column=ADJ_CLOSE))
        self.assertIn("El análisis usa Adj Close", adjusted)
        self.assertNotIn("La valoración usa Close", adjusted)
        self.assertIn("La valoración usa Close", build_report(portfolio.analyze()))

    def test_sectors_are_translated_and_charts_have_descriptive_alt_text(self):
        portfolio = buy_and_hold(
            [asset("A", [1, 2, 3], sector="Technology"), asset("B", [3, 2, 3], sector="Energy")],
            [3, 0.1],
        )
        report = build_report(
            portfolio.analyze(), charts={"performance": {"portfolio": "analisis_cartera.png"}}
        )
        self.assertIn("Concentración sectorial: Tecnología.", report)
        self.assertNotIn("Concentración sectorial: Technology", report)
        self.assertIn("![Evolución, caídas, correlaciones", report)
        self.assertIn("Por qué las medidas de rentabilidad pueden discrepar", report)

    def test_summary_names_the_benchmark(self):
        benchmark = history("^IXIC", [100, 101, 103])
        portfolio = buy_and_hold([asset("A", [100, 102, 104])], [1])
        report = build_report(portfolio.analyze(MarketReferences(benchmark=benchmark)))
        self.assertIn("Diferencia anual frente al índice (^IXIC)", report)
        self.assertIn("Comparación con el índice ^IXIC:", report)


if __name__ == "__main__":
    unittest.main()
