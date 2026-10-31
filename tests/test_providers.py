"""Offline contract tests: no API keys, network requests, or paid endpoints."""

import os
import tempfile
import time
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
from src.providers.base import ApiClient, has_api_key


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
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        usage = patch.dict(
            os.environ, {"ALPHA_VANTAGE_USAGE_DB": str(Path(folder.name) / "usage.sqlite3")}
        )
        usage.start()
        self.addCleanup(usage.stop)

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
        self.assertEqual(series.price_basis, "unadjusted")
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
        self.assertTrue(result.partial_history)

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
        self.assertEqual(result.profile.name, "IBM Corp")
        self.assertEqual(result.profile.currency, "USD")
        self.assertEqual(result.profile.asset_type, "stock")
        self.assertEqual(result.profile.beta, 0)
        self.assertEqual(result.profile.market_cap, 1000000)
        self.assertTrue(pd.isna(result.profile.pe_ratio))
        self.assertEqual(result.profile.raw, overview)
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
        self.assertIn("Alpha Vantage", result.profile.issue)

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
        self.assertEqual(result.source, "fred")
        params = session.get.call_args.kwargs["params"]
        self.assertEqual(params["observation_end"], "2026-10-24")
        # Última versión de la serie, sin consultar el archivo de versiones (ALFRED).
        self.assertNotIn("realtime_start", params)

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
        self.assertEqual(result.profile.name, "Example")
        self.assertEqual(result.profile.currency, "USD")
        self.assertEqual(result.profile.asset_type, "index")
        self.assertEqual(result.profile.pe_ratio, 12.5)
        self.assertIsNone(result.profile.sector)
        self.assertEqual(result.profile.raw["longName"], "Example")
        self.assertEqual(result.prices.index[0], pd.Timestamp("2026-10-22"))
        self.assertEqual(result.price_basis, "split_adjusted")
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
                self.assertIn("Yahoo Finance", result.profile.issue)
                self.assertIsNone(result.profile.currency)
                self.assertEqual(result.profile.raw, {})

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

    def test_yahoo_cache_reuses_each_symbol_and_covered_dates(self):
        prices = pd.DataFrame(
            {"Open": [1.0, float("nan"), 2.0], "Close": [1.5, 2.0, 2.5], "Volume": [100, 200, 300]},
            index=pd.date_range("2026-01-05", periods=3, tz="America/New_York"),
        )
        with tempfile.TemporaryDirectory() as tmp, patch("src.providers.yahoo.yf.Ticker") as ticker:
            ticker.return_value.history.return_value = prices
            ticker.return_value.get_info.return_value = {"quoteType": "EQUITY", "currency": "USD"}
            first = YahooFinanceAPI(cache_dir=Path(tmp)).get_prices(
                "IBM", "2026-01-01", "2026-02-01"
            )
            # Otra ejecución con un intervalo contenido no vuelve a descargar nada.
            second = YahooFinanceAPI(cache_dir=Path(tmp)).get_prices(
                "IBM", "2026-01-06", "2026-02-01"
            )
            self.assertEqual(ticker.return_value.history.call_count, 1)
            self.assertEqual(ticker.return_value.get_info.call_count, 1)
            pd.testing.assert_frame_equal(second.prices, first.prices.iloc[1:], check_freq=False)
            self.assertEqual(second.profile.currency, "USD")

            YahooFinanceAPI(cache_dir=Path(tmp)).get_prices("MSFT", "2026-01-01", "2026-02-01")
            self.assertEqual(ticker.return_value.history.call_count, 2)

            # Ampliar el intervalo descarga una vez lo guardado y lo nuevo.
            YahooFinanceAPI(cache_dir=Path(tmp)).get_prices("IBM", "2025-12-01", "2026-01-15")
            ticker.return_value.history.assert_called_with(
                start="2025-12-01", end="2026-02-01", auto_adjust=False
            )
            YahooFinanceAPI(cache_dir=Path(tmp)).get_prices("IBM", "2025-12-01", "2026-02-01")
            self.assertEqual(ticker.return_value.history.call_count, 3)

    def test_yahoo_cache_does_not_trust_sessions_that_may_be_open(self):
        today = pd.Timestamp.today().normalize()
        prices = pd.DataFrame(
            {"Close": [1.5, 2.5]}, index=pd.date_range(today - pd.Timedelta(days=1), periods=2)
        )
        start = (today - pd.Timedelta(days=5)).date().isoformat()
        end = (today + pd.Timedelta(days=1)).date().isoformat()
        with tempfile.TemporaryDirectory() as tmp, patch("src.providers.yahoo.yf.Ticker") as ticker:
            ticker.return_value.history.return_value = prices
            api = YahooFinanceAPI(cache_dir=Path(tmp), include_info=False)
            api.get_prices("IBM", start, end)
            api.get_prices("IBM", start, end)
            self.assertEqual(ticker.return_value.history.call_count, 2)
            api.get_prices("IBM", start, today.date().isoformat())
            self.assertEqual(ticker.return_value.history.call_count, 2)
            ticker.return_value.get_info.assert_not_called()

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

    def test_rejected_key_shows_the_provider_reason_without_the_key(self):
        response = Mock()
        response.status_code = 400
        response.json.return_value = {
            "error_message": "Bad Request. The value for variable api_key is not registered: bad-key"
        }
        response.raise_for_status.side_effect = requests.HTTPError(response=response)
        session = Mock(spec=requests.Session)
        session.get.return_value = response
        with self.assertRaises(ProviderError) as caught:
            FredAPI("bad-key", session=session).get_series("DGS10", "2026-10-22", "2026-10-25")
        self.assertIn("HTTP 400", str(caught.exception))
        self.assertIn("not registered", str(caught.exception))
        self.assertNotIn("bad-key", str(caught.exception))

    def test_has_api_key_ignores_empty_values(self):
        with patch.dict(os.environ, {"TEST_KEY": "  "}):
            self.assertFalse(has_api_key("TEST_KEY"))
        with patch.dict(os.environ, {"TEST_KEY": "abc"}):
            self.assertTrue(has_api_key("TEST_KEY"))

    def test_cache_prunes_expired_responses_and_keeps_unrelated_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            expired = folder / f"{'a' * 64}.json"
            fresh = folder / f"{'b' * 64}.json"
            unrelated = folder / "notas.json"
            for path in (expired, fresh, unrelated):
                path.write_text('{"cached": true}', encoding="utf-8")
            two_days_ago = time.time() - 2 * 86400
            for path in (expired, unrelated):
                os.utime(path, (two_days_ago, two_days_ago))
            ApiClient("test-key", "TEST_KEY", cache_dir=folder, session=session_for())
            self.assertFalse(expired.exists())
            self.assertTrue(fresh.exists())
            self.assertTrue(unrelated.exists())

    def test_cache_writes_leave_no_temporary_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = session_for(alpha_payload())
            api = AlphaVantageAPI("test-key", session=session, cache_dir=Path(tmp))
            api.get_prices("IBM", "2026-10-22", "2026-10-24")
            names = [path.name for path in Path(tmp).iterdir()]
            self.assertEqual(len(names), 1)
            self.assertTrue(names[0].endswith(".json"))

    def test_yahoo_drops_dates_without_close_and_counts_them(self):
        index = pd.date_range("2026-10-21", periods=3, tz="America/New_York")
        prices = pd.DataFrame({"Close": [1.5, float("nan"), 2.5]}, index=index)
        with patch("src.providers.yahoo.yf.Ticker") as ticker:
            ticker.return_value.history.return_value = prices
            ticker.return_value.get_info.return_value = {"quoteType": "EQUITY", "currency": "USD"}
            result = YahooFinanceAPI().get_prices("IBM", "2026-10-21", "2026-10-24")
        self.assertEqual(result.prices["Close"].tolist(), [1.5, 2.5])
        self.assertEqual(result.dropped_rows, 1)

    def test_yahoo_prices_outside_the_requested_dates_name_the_symbol(self):
        prices = pd.DataFrame(
            {"Close": [1.5]}, index=pd.date_range("2026-09-01", periods=1, tz="UTC")
        )
        with patch("src.providers.yahoo.yf.Ticker") as ticker:
            ticker.return_value.history.return_value = prices
            with self.assertRaisesRegex(DataCoverageError, "IBM"):
                YahooFinanceAPI().get_prices("IBM", "2026-10-22", "2026-10-24")

    def test_fred_rejects_incomplete_metadata_before_downloading_observations(self):
        session = session_for({"seriess": [{"id": "DGS10", "units": "Percent"}]}, OBSERVATIONS)
        with self.assertRaises(ProviderError):
            FredAPI("test-key", session=session).get_series("DGS10", "2026-10-22", "2026-10-25")
        self.assertEqual(session.get.call_count, 1)


if __name__ == "__main__":
    unittest.main()
