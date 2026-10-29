"""Offline contract tests: no API keys, network requests, or paid endpoints."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
import requests

from src.models.economic_indicator import EconomicIndicator
from src.models.price_history import PriceHistory
from src.providers import (
    AlphaVantageAPI,
    DataCoverageError,
    FredAPI,
    ProviderError,
    YahooFinanceAPI,
)


def session_for(*payloads):
    session = Mock(spec=requests.Session)
    responses = []
    for payload in payloads:
        response = Mock()
        response.json.return_value = payload
        responses.append(response)
    session.get.side_effect = responses
    return session


def alpha_payload():
    return {
        "Meta Data": {"2. Symbol": "IBM"},
        "Time Series (Daily)": {
            "2026-10-23": {
                "1. open": "103",
                "2. high": "105",
                "3. low": "102",
                "4. close": "104",
                "5. volume": "200",
            },
            "2026-10-22": {
                "1. open": "101",
                "2. high": "103",
                "3. low": "100",
                "4. close": "102",
                "5. volume": "100",
            },
        },
    }


METADATA = {
    "seriess": [
        {"id": "DGS10", "title": "Treasury yield", "units": "Percent", "frequency": "Daily"}
    ]
}
OBSERVATIONS = {
    "count": 3,
    "observations": [
        {"date": "2026-10-22", "value": "4.0"},
        {"date": "2026-10-23", "value": "."},
        {"date": "2026-10-24", "value": "4.2"},
    ],
}


class ProviderTests(unittest.TestCase):
    def test_economic_indicator_rejects_booleans(self):
        dates = pd.date_range("2026-10-01", periods=2)
        with self.assertRaisesRegex(TypeError, "no booleanos"):
            EconomicIndicator("TEST", "test", pd.Series([True, False], index=dates), "%", "Daily")

    def test_daily_models_reject_timezone_aware_dates(self):
        dates = pd.date_range("2026-10-01", periods=2, tz="Europe/Madrid")
        with self.assertRaisesRegex(ValueError, "sin zona horaria"):
            EconomicIndicator("TEST", "test", pd.Series([1, 2], index=dates), "%", "Daily")
        with self.assertRaisesRegex(ValueError, "sin zona horaria"):
            PriceHistory("TEST", "test", pd.DataFrame({"Close": [1, 2]}, index=dates))

    def test_alpha_normalizes_ohlcv_and_calculates_statistics(self):
        session = session_for(alpha_payload())
        series = AlphaVantageAPI("test-key", session=session).get_prices(
            "IBM", "2026-10-22", "2026-10-24"
        )
        self.assertEqual(list(series.prices.columns), ["Open", "High", "Low", "Close", "Volume"])
        self.assertEqual(series.prices["Close"].tolist(), [102, 104])
        self.assertEqual(series.mean["Close"], 103)
        self.assertAlmostEqual(series.std["Close"], 2**0.5)
        self.assertEqual(series.info["price_adjustment"], "unadjusted")
        self.assertEqual(session.get.call_args.kwargs["timeout"], 30)

    def test_end_date_is_exclusive(self):
        series = AlphaVantageAPI("test-key", session=session_for(alpha_payload())).get_prices(
            "IBM", "2026-10-22", "2026-10-23"
        )
        self.assertEqual(len(series.prices), 1)

    def test_alpha_rejects_truncation_unless_explicit(self):
        api = AlphaVantageAPI("test-key", session=session_for(alpha_payload()))
        with self.assertRaises(DataCoverageError):
            api.get_prices("IBM", "2026-01-01", "2026-10-24")
        partial = AlphaVantageAPI(
            "test-key", session=session_for(alpha_payload()), allow_partial=True
        )
        result = partial.get_prices("IBM", "2026-01-01", "2026-10-24")
        self.assertTrue(result.info["partial_history"])

    def test_alpha_rejects_adjusted_and_invalid_dates_before_request(self):
        session = session_for()
        api = AlphaVantageAPI("test-key", session=session)
        with self.assertRaises(ValueError):
            api.get_prices("IBM", "2026-10-22", "2026-10-24", adjusted=True)
        with self.assertRaises(ValueError):
            AlphaVantageAPI("test-key", session=session, outputsize="wrong")
        for start, end in [("2026-10-24", "2026-10-22"), ("22/10/2026", "2026-10-24")]:
            with self.assertRaises(ValueError):
                api.get_prices("IBM", start, end)
        session.get.assert_not_called()

    def test_alpha_optional_overview_preserves_fundamentals(self):
        overview = {
            "Symbol": "IBM",
            "Name": "IBM Corp",
            "Currency": "USD",
            "Beta": "0",
            "MarketCapitalization": "1000000",
            "PERatio": "None",
            "AssetType": "Common Stock",
        }
        session = session_for(alpha_payload(), overview)
        result = AlphaVantageAPI("test-key", session=session, include_info=True).get_prices(
            "IBM", "2026-10-22", "2026-10-24"
        )
        self.assertEqual(result.info["name"], "IBM Corp")
        self.assertEqual(result.info["currency"], "USD")
        self.assertEqual(result.info["asset_type"], "stock")
        self.assertEqual(result.info["beta"], 0)
        self.assertEqual(result.info["market_cap"], 1000000)
        self.assertTrue(pd.isna(result.info["pe_ratio"]))
        self.assertEqual(result.info["raw"], overview)
        self.assertEqual(session.get.call_count, 2)

    def test_provider_errors_in_http_200_are_not_cached(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = session_for({"Information": "Quota reached for test-key"})
            api = AlphaVantageAPI("test-key", session=session, cache_dir=Path(tmp))
            with self.assertRaises(ProviderError) as caught:
                api.get_prices("IBM", "2026-10-22", "2026-10-24")
            self.assertNotIn("test-key", str(caught.exception))
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_optional_alpha_metadata_failure_does_not_discard_prices(self):
        session = session_for(alpha_payload(), {"Information": "Quota reached"})
        result = AlphaVantageAPI("test-key", session=session, include_info=True).get_prices(
            "IBM", "2026-10-22", "2026-10-24"
        )
        self.assertEqual(len(result.prices), 2)
        self.assertIn("metadata_issue", result.info)

    def test_network_errors_do_not_leak_keys(self):
        session = Mock(spec=requests.Session)
        session.get.side_effect = requests.Timeout("https://example.com?apikey=secret-key")
        with self.assertRaises(ProviderError) as caught:
            AlphaVantageAPI("secret-key", session=session).get_prices(
                "IBM", "2026-10-22", "2026-10-24"
            )
        self.assertNotIn("secret-key", str(caught.exception))

    def test_invalid_json_and_empty_payloads(self):
        session = session_for({}, [])
        api = AlphaVantageAPI("test-key", session=session)
        for _ in range(2):
            with self.assertRaises(ProviderError):
                api.get_prices("IBM", "2026-10-22", "2026-10-24")

    def test_cache_reuses_response_without_storing_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = session_for(alpha_payload())
            api = AlphaVantageAPI("secret-key", session=session, cache_dir=Path(tmp))
            for _ in range(2):
                api.get_prices("IBM", "2026-10-22", "2026-10-24")
            self.assertEqual(session.get.call_count, 1)
            for path in Path(tmp).iterdir():
                self.assertNotIn("secret-key", path.name + path.read_text())

    def test_alpha_spaces_sequential_requests(self):
        session = session_for(alpha_payload(), {"Symbol": "IBM"})
        api = AlphaVantageAPI("test-key", session=session, include_info=True)
        with (
            patch("src.providers.base.time.monotonic", return_value=100.0),
            patch("src.providers.base.time.sleep") as sleep,
        ):
            api.get_prices("IBM", "2026-10-22", "2026-10-24")
        sleep.assert_called_once_with(1.1)

    def test_fred_retains_missing_values_and_metadata(self):
        session = session_for(METADATA, OBSERVATIONS)
        result = FredAPI("test-key", session=session).get_series(
            "DGS10", "2026-10-22", "2026-10-25"
        )
        self.assertEqual(result.units, "Percent")
        self.assertEqual(result.frequency, "Daily")
        self.assertEqual(result.missing_count, 1)
        self.assertTrue(pd.isna(result.values.iloc[1]))
        self.assertAlmostEqual(result.mean, 4.1)
        params = session.get.call_args.kwargs["params"]
        self.assertEqual(params["observation_end"], "2026-10-24")

    def test_fred_pagination(self):
        first = {"count": 3, "observations": OBSERVATIONS["observations"][:2]}
        second = {"count": 3, "observations": OBSERVATIONS["observations"][2:]}
        session = session_for(METADATA, first, second)
        result = FredAPI("test-key", session=session).get_series(
            "DGS10", "2026-10-22", "2026-10-25"
        )
        self.assertEqual(len(result.values), 3)
        self.assertEqual(session.get.call_args.kwargs["params"]["offset"], 2)

    def test_fred_rejects_malformed_and_all_missing_values(self):
        for value in ("bad-number", "."):
            observations = {"count": 1, "observations": [{"date": "2026-10-22", "value": value}]}
            with self.assertRaises((ProviderError, ValueError)):
                FredAPI("test-key", session=session_for(METADATA, observations)).get_series(
                    "DGS10", "2026-10-22", "2026-10-25"
                )

    def test_yahoo_preserves_extras_and_normalizes_local_dates(self):
        index = pd.date_range("2026-10-22", periods=2, tz="America/New_York")
        prices = pd.DataFrame(
            {
                "Open": [1.0, 2.0],
                "High": [2.0, 3.0],
                "Low": [0.5, 1.5],
                "Close": [1.5, 2.5],
                "Volume": [100, 200],
                "Dividends": [0.0, 0.1],
                "Stock Splits": [0.0, 0.0],
            },
            index=index,
        )
        with patch("src.providers.yahoo.yf.Ticker") as ticker:
            ticker.return_value.history.return_value = prices
            ticker.return_value.get_info.return_value = {
                "longName": "Example",
                "currency": "USD",
                "quoteType": "INDEX",
                "trailingPE": 12.5,
            }
            result = YahooFinanceAPI().get_prices("IBM", "2026-10-22", "2026-10-24")
        self.assertEqual(len(result.prices.columns), 7)
        self.assertIsNone(result.prices.index.tz)
        self.assertEqual(result.info["name"], "Example")
        self.assertEqual(result.info["currency"], "USD")
        self.assertEqual(result.info["asset_type"], "index")
        self.assertEqual(result.info["pe_ratio"], 12.5)
        self.assertIsNone(result.info["sector"])
        self.assertEqual(result.info["raw"]["longName"], "Example")
        self.assertEqual(result.prices.index[0], pd.Timestamp("2026-10-22"))
        self.assertEqual(result.info["price_adjustment"], "split_adjusted")
        self.assertFalse(result.info["auto_adjust"])
        ticker.return_value.history.assert_called_once_with(
            start="2026-10-22", end="2026-10-24", auto_adjust=False
        )

    def test_yahoo_profile_failure_keeps_downloaded_prices(self):
        prices = pd.DataFrame(
            {"Close": [1.5, 2.5]}, index=pd.date_range("2026-10-22", periods=2, tz="UTC")
        )
        failures = {
            "error": {"side_effect": RuntimeError("429 Too Many Requests")},
            "empty profile": {"return_value": {"trailingPegRatio": None}},
        }
        for case, behaviour in failures.items():
            with self.subTest(case=case), patch("src.providers.yahoo.yf.Ticker") as ticker:
                ticker.return_value.history.return_value = prices
                ticker.return_value.get_info.configure_mock(**behaviour)
                result = YahooFinanceAPI().get_prices("IBM", "2026-10-22", "2026-10-24")
                self.assertEqual(len(result.prices), 2)
                self.assertIn("metadata_issue", result.info)
                self.assertIsNone(result.info["currency"])
                self.assertEqual(result.info["raw"], {})

    def test_yahoo_info_raises_provider_error_without_a_profile(self):
        with patch("src.providers.yahoo.yf.Ticker") as ticker:
            ticker.return_value.get_info.return_value = {"quoteType": "EQUITY", "currency": "USD"}
            self.assertEqual(YahooFinanceAPI().get_info("IBM")["currency"], "USD")
            ticker.return_value.get_info.side_effect = RuntimeError("connection reset")
            with self.assertRaises(ProviderError):
                YahooFinanceAPI().get_info("IBM")

    def test_yahoo_download_failures_become_provider_errors(self):
        with patch("src.providers.yahoo.yf.Ticker") as ticker:
            ticker.return_value.history.side_effect = RuntimeError("connection reset")
            with self.assertRaises(ProviderError):
                YahooFinanceAPI().get_prices("IBM", "2026-10-22", "2026-10-24")

    def test_models_reject_duplicate_dates_and_copy_input(self):
        result = AlphaVantageAPI("test-key", session=session_for(alpha_payload())).get_prices(
            "IBM", "2026-10-22", "2026-10-24"
        )
        frame = result.prices.copy()
        copied = PriceHistory("IBM", "manual", frame)
        frame.iloc[0, 0] = 999
        self.assertNotEqual(copied.prices.iloc[0, 0], 999)
        duplicate = pd.concat([frame, frame])
        with self.assertRaises(ValueError):
            PriceHistory("IBM", "manual", duplicate)

    def test_missing_key_is_actionable(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(ValueError, "FRED_API_KEY"):
                FredAPI()


if __name__ == "__main__":
    unittest.main()
