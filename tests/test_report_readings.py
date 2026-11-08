"""Las lecturas del informe deben corresponder a la magnitud de cada cifra."""

import math
import unittest
from unittest.mock import Mock, patch

import pandas as pd
from fixtures import asset, history

from src.analysis.warnings import WarningThresholds, evaluate_risk
from src.constants import ADJ_CLOSE, CLOSE
from src.market_loader import DEFAULT_BENCHMARK_NOTE, REPORT_DEFAULTS, load_references
from src.models import MarketReferences, Portfolio
from src.models.notice import Notice
from src.reporting.report import (
    _read_alpha,
    _read_diversifier,
    _read_loss_probability,
    _read_mean_correlation,
    _read_oil,
    _read_sortino,
)

DATES = pd.bdate_range("2026-01-05", periods=6)
CLOSES = [100, 101, 99, 103, 102, 105]
ADJUSTED = [95, 96, 94, 98, 97, 100]


class ReadingsTests(unittest.TestCase):
    def test_a_weak_correlation_is_not_read_as_falling_together(self):
        read = _read_diversifier(0.18, "el Bund", "el Bund hace de refugio")
        self.assertEqual(read, "el Bund diversifica bien")

    def test_diversifier_bands(self):
        for value, expected in (
            (-0.5, "refugio"),
            (0.2, "el oro diversifica bien"),
            (0.45, "el oro diversifica en parte"),
            (0.7, "el oro diversifica poco"),
        ):
            with self.subTest(value=value):
                self.assertEqual(_read_diversifier(value, "el oro", "refugio"), expected)
        self.assertEqual(_read_diversifier(math.nan, "el oro", "refugio"), "")

    def test_gold_and_mean_correlation_use_the_same_criteria(self):
        self.assertEqual(_read_mean_correlation(0.25), "buena diversificación")
        self.assertIn("diversifica bien", _read_diversifier(0.25, "el oro", "refugio"))

    def test_oil_needs_a_clear_correlation(self):
        self.assertEqual(_read_oil(0.1), "poco sensible al petróleo")
        self.assertEqual(_read_oil(-0.1), "poco sensible al petróleo")
        self.assertEqual(_read_oil(0.5), "sensible al petróleo")
        self.assertEqual(_read_oil(-0.5), "le perjudica que suba el petróleo")

    def test_alpha_is_not_presented_as_skill(self):
        for value in (0.21, -0.21):
            with self.subTest(value=value):
                read = _read_alpha(value)
                self.assertIn("puede ser azar", read)
                self.assertIn("beta", read)
                self.assertNotIn("selección de valores", read)
                self.assertNotIn("comprar", read)
        self.assertEqual(_read_alpha(math.nan), "")

    def test_sortino_compares_with_what_symmetric_returns_would_give(self):
        self.assertEqual(_read_sortino(1.4, 1.0), "subidas y caídas equilibradas")
        self.assertEqual(_read_sortino(2.0, 1.0), "las caídas pesan menos que las subidas")
        self.assertEqual(_read_sortino(1.1, 1.0), "las caídas pesan más que las subidas")
        self.assertEqual(_read_sortino(-1.0, -0.5), "")

    def test_loss_probability_states_the_actual_proportion(self):
        self.assertEqual(_read_loss_probability(0.39), "se pierde en unos 4 de cada 10 escenarios")
        self.assertEqual(_read_loss_probability(0.82), "se pierde en unos 8 de cada 10 escenarios")
        self.assertEqual(
            _read_loss_probability(0.01), "se pierde en menos de 1 de cada 20 escenarios"
        )
        self.assertEqual(_read_loss_probability(math.nan), "")

    def test_currency_warning_names_the_main_currency(self):
        metrics = pd.Series(
            {"max_drawdown": -0.1, "annualized_volatility": 0.1, "history_days": 400.0}
        )
        weights = pd.Series({"A": 0.2, "B": 0.2, "C": 0.2, "D": 0.2, "E": 0.2})
        warnings = evaluate_risk(
            metrics,
            weights,
            pd.Series(dtype=float),
            pd.Series(dtype=float),
            _no_drawdown(),
            WarningThresholds(),
            currencies=pd.Series({"EUR": 0.6, "USD": 0.4}),
        )
        message = next(w.message for w in warnings if w.code == "currency_risk")
        self.assertIn("la principal es EUR.", message)


class BenchmarkDividendTests(unittest.TestCase):
    def notices(self, benchmark_type, column):
        extra = {"Adj Close": ADJUSTED}
        portfolio = Portfolio(
            [asset("A", CLOSES, dates=DATES, extra=extra)], {"A": 1.0}, rebalance=None
        )
        benchmark = history("REF", CLOSES, dates=DATES, extra=extra, asset_type=benchmark_type)
        analysis = portfolio.analyze(MarketReferences(benchmark=benchmark), price_column=column)
        return [n.message for n in analysis.notices if isinstance(n, Notice) and "REF" in n.message]

    def summary(self, benchmark_type, column):
        extra = {"Adj Close": ADJUSTED}
        portfolio = Portfolio(
            [asset("A", CLOSES, dates=DATES, extra=extra)], {"A": 1.0}, rebalance=None
        )
        benchmark = history("REF", CLOSES, dates=DATES, extra=extra, asset_type=benchmark_type)
        analysis = portfolio.analyze(MarketReferences(benchmark=benchmark), price_column=column)
        return analysis.markdown(sections=["summary"], detail="full")

    def test_summary_states_the_dividends_of_the_comparison(self):
        for benchmark_type, column, expected in (
            ("etf", ADJ_CLOSE, "Con dividendos en los dos lados."),
            ("index", ADJ_CLOSE, "si es de precios, no incluye dividendos."),
            ("etf", CLOSE, "Sin dividendos en ninguno de los dos lados."),
        ):
            with self.subTest(benchmark_type=benchmark_type, column=column):
                self.assertIn(expected, self.summary(benchmark_type, column))

    def test_summary_without_benchmark_does_not_mention_dividends(self):
        portfolio = Portfolio(
            [asset("A", CLOSES, dates=DATES, extra={"Adj Close": ADJUSTED})],
            {"A": 1.0},
            rebalance=None,
        )
        text = portfolio.analyze(price_column=ADJ_CLOSE).markdown(
            sections=["summary"], detail="full"
        )
        self.assertNotIn("dos lados", text)

    def explanation_shown(self, **options):
        with (
            patch("src.market_loader.load_market_references", return_value=MarketReferences()),
            patch("src.market_loader.load_market_context", return_value=({}, [])),
        ):
            references = load_references("EUR", "2026-01-01", "2026-02-01", Mock(), **options)
        return DEFAULT_BENCHMARK_NOTE in [notice.message for notice in references.notices]

    def test_only_a_default_benchmark_is_explained_as_an_etf(self):
        self.assertTrue(self.explanation_shown())
        self.assertFalse(self.explanation_shown(benchmark_symbol="^IBEX"))

    def test_default_references_are_funds_with_dividends(self):
        self.assertEqual(REPORT_DEFAULTS["USD"]["benchmark_symbol"], "SPY")
        self.assertEqual(REPORT_DEFAULTS["EUR"]["benchmark_symbol"], "EXW1.DE")

    def test_a_fund_is_compared_with_dividends_on_both_sides(self):
        notes = " ".join(self.notices("etf", ADJ_CLOSE))
        self.assertIn("ajustados por dividendos en los dos lados", notes)
        self.assertNotIn("sobrestimada", notes)

    def test_an_index_warns_that_the_advantage_may_be_overstated(self):
        notes = " ".join(self.notices("index", ADJ_CLOSE))
        self.assertIn("no incluye dividendos", notes)
        self.assertIn("sobrestimada", notes)
        self.assertIn("--benchmark", notes)

    def test_without_adjusted_prices_neither_side_has_dividends(self):
        notes = " ".join(self.notices("etf", CLOSE))
        self.assertIn("sin dividendos en ninguno de los dos lados", notes)


def _no_drawdown():
    from src.analysis.metrics import DrawdownEpisode

    return DrawdownEpisode(0.0, None, None, None, 0)


if __name__ == "__main__":
    unittest.main()
