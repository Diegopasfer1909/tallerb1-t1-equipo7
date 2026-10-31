"""Comprueba el límite sin consumir peticiones reales ni modificar la cuota del usuario."""

import multiprocessing
import os
import sqlite3
import tempfile
import traceback
import unittest
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from unittest.mock import Mock, patch

import requests
from test_providers import alpha_payload, session_for

from src.providers import AlphaVantageAPI, AlphaVantageQuotaError, ProviderError
from src.providers.alpha_quota import THROTTLE_SECONDS, WINDOW_SECONDS, AlphaVantageQuota

DAILY_LIMIT_MESSAGE = "API key test-key: our standard API rate limit is 25 requests per day."


def http_error_session(status, url="https://www.alphavantage.co/query"):
    """Sesión cuya respuesta falla como requests: el HTTPError incluye la URL."""
    response = Mock(status_code=status)
    response.json.side_effect = ValueError("not JSON")
    response.raise_for_status.side_effect = requests.HTTPError(
        f"{status} Client Error for url: {url}", response=response
    )
    session = Mock(spec=requests.Session)
    session.get.return_value = response
    return session


def reserve_in_process(path):
    try:
        AlphaVantageQuota("shared-key", path).reserve()
        return True
    except AlphaVantageQuotaError:
        return False


class AlphaQuotaTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        self.db = self.folder / "state" / "usage.sqlite3"
        usage = patch.dict(os.environ, {"ALPHA_VANTAGE_USAGE_DB": str(self.db)})
        usage.start()
        self.addCleanup(usage.stop)
        sleep = patch("src.providers.base.time.sleep")
        sleep.start()
        self.addCleanup(sleep.stop)

    def fill_quota(self, count=25):
        for _ in range(count):
            AlphaVantageQuota("test-key").reserve()

    def test_twenty_sixth_request_blocked_across_instances_and_endpoints(self):
        session = session_for(*[{"Symbol": "IBM"}] * 25)
        for _ in range(25):
            AlphaVantageAPI("test-key", session=session).get_info("IBM")
        api = AlphaVantageAPI("test-key", session=session)
        with self.assertRaisesRegex(AlphaVantageQuotaError, "25 peticiones"):
            api.get_prices("IBM", "2026-10-22", "2026-10-24")
        with self.assertRaises(AlphaVantageQuotaError):
            api.get_info("MSFT")
        self.assertEqual(session.get.call_count, 25)
        self.assertFalse(session.get.call_args.kwargs["allow_redirects"])

    def test_window_does_not_reset_at_midnight_and_expires_requests_individually(self):
        with patch("src.providers.alpha_quota.time.time", return_value=86399):
            self.fill_quota(1)
        with patch("src.providers.alpha_quota.time.time", return_value=86401):
            self.fill_quota(24)
        with patch("src.providers.alpha_quota.time.time", return_value=86399 + WINDOW_SECONDS - 1):
            with self.assertRaises(AlphaVantageQuotaError) as error:
                self.fill_quota(1)
            self.assertEqual(error.exception.retry_at, 86399 + WINDOW_SECONDS)
            self.assertIn("UTC", str(error.exception))
        with patch("src.providers.alpha_quota.time.time", return_value=86399 + WINDOW_SECONDS):
            self.fill_quota(1)
            with self.assertRaises(AlphaVantageQuotaError):
                self.fill_quota(1)

    def test_cache_hit_works_at_limit_and_disabled_cache_still_obeys_limit(self):
        session = session_for(alpha_payload())
        cache = self.folder / "cache"
        api = AlphaVantageAPI("test-key", session=session, cache_dir=cache)
        api.get_prices("IBM", "2026-10-22", "2026-10-24")
        self.fill_quota(24)
        # Un cliente nuevo reutiliza la caché sin intentar reservar más cuota.
        AlphaVantageAPI("test-key", session=session, cache_dir=cache).get_prices(
            "IBM", "2026-10-22", "2026-10-24"
        )
        with self.assertRaises(AlphaVantageQuotaError):
            AlphaVantageAPI("test-key", session=session, cache_dir=cache, cache_ttl=0).get_prices(
                "IBM", "2026-10-22", "2026-10-24"
            )
        for entry in cache.iterdir():
            entry.unlink()
        with self.assertRaises(AlphaVantageQuotaError):
            api.get_prices("IBM", "2026-10-22", "2026-10-24")
        self.assertEqual(session.get.call_count, 1)

    def test_prices_survive_when_last_slot_leaves_no_quota_for_optional_overview(self):
        self.fill_quota(24)
        session = session_for(alpha_payload())
        result = AlphaVantageAPI("test-key", session=session, include_info=True).get_prices(
            "IBM", "2026-10-22", "2026-10-24"
        )
        self.assertEqual(len(result.prices), 2)
        self.assertIn("25 peticiones", result.profile.issue)
        self.assertEqual(session.get.call_count, 1)

    def test_all_failed_attempts_consume_quota(self):
        self.fill_quota(21)
        timeout_session = Mock(spec=requests.Session)
        timeout_session.get.side_effect = requests.Timeout("test-key")
        http_session = Mock(spec=requests.Session)
        response = Mock(status_code=500)
        response.json.return_value = {}
        http_session.get.return_value.raise_for_status.side_effect = requests.HTTPError(
            response=response
        )
        invalid_json = Mock(spec=requests.Session)
        invalid_json.get.return_value.json.side_effect = ValueError("invalid")
        for session in (
            timeout_session,
            http_session,
            invalid_json,
            session_for({"Information": "Quota reached for test-key"}),
        ):
            with self.assertRaises(ProviderError) as error:
                AlphaVantageAPI("test-key", session=session).get_info("IBM")
            self.assertNotIn("test-key", str(error.exception))
            session.get.assert_called_once()
        session = session_for()
        with self.assertRaises(AlphaVantageQuotaError):
            AlphaVantageAPI("test-key", session=session).get_info("IBM")
        session.get.assert_not_called()

    def test_invalid_input_does_not_consume_last_slot(self):
        self.fill_quota(24)
        session = session_for({"Symbol": "IBM"})
        api = AlphaVantageAPI("test-key", session=session)
        with self.assertRaises(ValueError):
            api.get_prices("IBM", "2026-10-24", "2026-10-22")
        api.get_info("IBM")
        session.get.assert_called_once()

    def test_separate_keys_have_separate_budgets_without_storing_secrets(self):
        self.fill_quota()
        AlphaVantageQuota("another-secret").reserve()
        contents = self.db.read_bytes()
        self.assertNotIn(b"test-key", contents)
        self.assertNotIn(b"another-secret", contents)
        with self.assertRaises(AlphaVantageQuotaError):
            self.fill_quota(1)

    def test_corrupt_or_unwritable_state_blocks_http(self):
        self.db.parent.mkdir()
        for path in (self.db, self.folder / "directory"):
            with self.subTest(path=path):
                if path == self.db:
                    path.write_text("broken database")
                else:
                    path.mkdir()
                session = session_for()
                api = AlphaVantageAPI("test-key", session=session, usage_db=path)
                with self.assertRaisesRegex(ProviderError, "No se ha enviado"):
                    api.get_info("IBM")
                session.get.assert_not_called()

    def test_failed_commit_blocks_http(self):
        session = session_for()
        with patch("src.providers.alpha_quota.sqlite3.connect") as connect:
            connect.return_value.__exit__.side_effect = sqlite3.OperationalError("disk full")
            connect.return_value.execute.return_value.fetchone.return_value = (0, None)
            with self.assertRaisesRegex(ProviderError, "No se ha enviado"):
                AlphaVantageAPI("test-key", session=session).get_info("IBM")
        session.get.assert_not_called()

    def test_parallel_processes_cannot_exceed_shared_budget(self):
        with ProcessPoolExecutor(
            max_workers=4, mp_context=multiprocessing.get_context("spawn")
        ) as pool:
            results = list(pool.map(reserve_in_process, [str(self.db)] * 40))
        self.assertEqual(sum(results), 25)
        self.assertFalse(reserve_in_process(str(self.db)))

    def test_remote_limit_blocks_fresh_clients_even_with_only_one_local_request(self):
        for field in ("Information", "Note"):
            with self.subTest(field=field):
                db = self.folder / f"{field}.sqlite3"
                session = session_for({field: DAILY_LIMIT_MESSAGE})
                api = AlphaVantageAPI("test-key", session=session, usage_db=db)
                with self.assertRaises(AlphaVantageQuotaError) as error:
                    api.get_info("IBM")
                self.assertTrue(error.exception.remote)
                self.assertIn("CI", str(error.exception))
                self.assertNotIn("No se ha enviado", str(error.exception))
                self.assertNotIn("test-key", str(error.exception))
                next_client = AlphaVantageAPI("test-key", session=session, usage_db=db)
                with self.assertRaisesRegex(AlphaVantageQuotaError, "No se ha enviado"):
                    next_client.get_prices("IBM", "2026-10-22", "2026-10-24")
                session.get.assert_called_once()
                self.assertNotIn(b"test-key", db.read_bytes())
                # Otra clave no hereda el bloqueo remoto.
                AlphaVantageAPI(
                    "different-key", session=session_for({"Symbol": "IBM"}), usage_db=db
                ).get_info("IBM")

    def test_http_429_without_json_also_persists_cooldown(self):
        session = http_error_session(429)
        with self.assertRaises(AlphaVantageQuotaError):
            AlphaVantageAPI("test-key", session=session).get_info("IBM")
        with self.assertRaises(AlphaVantageQuotaError):
            AlphaVantageAPI("test-key", session=session).get_info("IBM")
        session.get.assert_called_once()

    def test_http_errors_do_not_chain_the_url_with_the_key(self):
        # La traza completa es lo que ve quien usa el paquete desde Python o un cuaderno.
        url = "https://www.alphavantage.co/query?function=OVERVIEW&apikey=test-key"
        for status in (429, 500):
            with self.subTest(status=status):
                api = AlphaVantageAPI(
                    "test-key",
                    session=http_error_session(status, url),
                    usage_db=self.folder / f"{status}.sqlite3",
                )
                with self.assertRaises(ProviderError) as error:
                    api.get_info("IBM")
                self.assertIsNone(error.exception.__context__)
                trace = "".join(traceback.format_exception(error.exception))
                self.assertNotIn("test-key", trace)

    def test_throttle_warnings_pause_briefly_instead_of_a_whole_day(self):
        throttles = {
            "burst": lambda: session_for(
                {
                    "Information": "Please consider spreading out your free API requests "
                    "more sparingly (1 request per second)."
                },
                {"Symbol": "IBM"},
            ),
            "legacy": lambda: session_for(
                {"Note": "Our standard API call frequency is 5 calls per minute and 500 per day."},
                {"Symbol": "IBM"},
            ),
            "http-429": lambda: http_error_session(429),
        }
        for name, make_session in throttles.items():
            with self.subTest(warning=name):
                db = self.folder / f"{name}.sqlite3"
                session = make_session()
                with patch("src.providers.alpha_quota.time.time", return_value=1000):
                    with self.assertRaises(AlphaVantageQuotaError) as error:
                        AlphaVantageAPI("test-key", session=session, usage_db=db).get_info("IBM")
                    self.assertEqual(error.exception.retry_at, 1000 + THROTTLE_SECONDS)
                # Un cliente nuevo respeta la pausa sin enviar nada y continúa al terminar.
                with patch(
                    "src.providers.alpha_quota.time.time", return_value=1000 + THROTTLE_SECONDS - 1
                ):
                    with self.assertRaisesRegex(AlphaVantageQuotaError, "No se ha enviado"):
                        AlphaVantageAPI("test-key", session=session, usage_db=db).get_info("IBM")
                session.get.assert_called_once()
                if name != "http-429":
                    with patch(
                        "src.providers.alpha_quota.time.time", return_value=1000 + THROTTLE_SECONDS
                    ):
                        api = AlphaVantageAPI("test-key", session=session, usage_db=db)
                        self.assertEqual(api.get_info("IBM"), {"Symbol": "IBM"})

    def test_throttle_does_not_shorten_a_stored_daily_block(self):
        daily, other = AlphaVantageQuota("test-key"), AlphaVantageQuota("test-key")
        with patch("src.providers.alpha_quota.time.time", return_value=1000):
            # Dos procesos reservan y envían a la vez; el primero recibe el aviso diario.
            daily.reserve()
            other.reserve()
            with self.assertRaises(AlphaVantageQuotaError):
                daily.handle_rejection(200, DAILY_LIMIT_MESSAGE)
            # El segundo recibe un aviso de ritmo: prevalece el bloqueo diario.
            with self.assertRaises(AlphaVantageQuotaError) as error:
                other.handle_rejection(429, None)
            self.assertEqual(error.exception.retry_at, 1000 + WINDOW_SECONDS)
        with patch("src.providers.alpha_quota.time.time", return_value=1000 + THROTTLE_SECONDS):
            with self.assertRaises(AlphaVantageQuotaError):
                AlphaVantageQuota("test-key").reserve()

    def test_remote_cooldown_expires_without_extending_on_blocked_attempts(self):
        session = session_for({"Note": "Quota reached"}, {"Symbol": "IBM"})
        with patch("src.providers.alpha_quota.time.time", return_value=1000):
            with self.assertRaises(AlphaVantageQuotaError) as error:
                AlphaVantageAPI("test-key", session=session).get_info("IBM")
            self.assertEqual(error.exception.retry_at, 1000 + WINDOW_SECONDS)
        with patch("src.providers.alpha_quota.time.time", return_value=1000 + WINDOW_SECONDS - 1):
            with self.assertRaises(AlphaVantageQuotaError) as error:
                AlphaVantageAPI("test-key", session=session).get_info("IBM")
            self.assertEqual(error.exception.retry_at, 1000 + WINDOW_SECONDS)
        with patch("src.providers.alpha_quota.time.time", return_value=1000 + WINDOW_SECONDS):
            self.assertEqual(
                AlphaVantageAPI("test-key", session=session).get_info("IBM"), {"Symbol": "IBM"}
            )
        self.assertEqual(session.get.call_count, 2)

    def test_remote_overview_limit_preserves_prices_and_cache_during_cooldown(self):
        cache = self.folder / "cache"
        session = session_for(alpha_payload(), {"Information": "Quota reached"})
        api = AlphaVantageAPI("test-key", session=session, include_info=True, cache_dir=cache)
        first = api.get_prices("IBM", "2026-10-22", "2026-10-24")
        cached = AlphaVantageAPI(
            "test-key", session=session, include_info=True, cache_dir=cache
        ).get_prices("IBM", "2026-10-22", "2026-10-24")
        self.assertEqual(len(first.prices), 2)
        self.assertEqual(len(cached.prices), 2)
        self.assertIn("CI", first.profile.issue)
        self.assertIn("CI", cached.profile.issue)
        self.assertEqual(session.get.call_count, 2)
        self.assertEqual(len(list(cache.glob("*.json"))), 1)

    def test_non_quota_errors_do_not_block_other_requests(self):
        session = session_for(
            {"Information": "This is a premium endpoint. Please subscribe to a premium plan."},
            {"Error Message": "Invalid API key test-key"},
            {"Symbol": "IBM"},
        )
        api = AlphaVantageAPI("test-key", session=session)
        for _ in range(2):
            with self.assertRaises(ProviderError) as error:
                api.get_info("IBM")
            self.assertNotIsInstance(error.exception, AlphaVantageQuotaError)
        self.assertEqual(api.get_info("IBM"), {"Symbol": "IBM"})
        self.assertEqual(session.get.call_count, 3)

    def test_cooldown_write_failure_still_blocks_the_current_client(self):
        session = session_for({"Information": "Quota reached"})
        api = AlphaVantageAPI("test-key", session=session)
        real_connect = sqlite3.connect
        calls = 0

        def fail_second_connection(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise sqlite3.OperationalError("disk full")
            return real_connect(*args, **kwargs)

        with patch("src.providers.alpha_quota.sqlite3.connect", side_effect=fail_second_connection):
            with self.assertRaisesRegex(ProviderError, "no se ha podido guardar el bloqueo"):
                api.get_info("IBM")
            with self.assertRaises(AlphaVantageQuotaError):
                api.get_info("IBM")
        session.get.assert_called_once()


if __name__ == "__main__":
    unittest.main()
