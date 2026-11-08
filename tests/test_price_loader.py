"""Descarga en lote con varios hilos, sin red: los proveedores falsos responden por símbolo.

La coordinación entre hilos se comprueba con Event y Barrier con esperas acotadas, no con
pausas arbitrarias ni con la duración de las pruebas.
"""

import io
import json
import os
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

import fixtures
import numpy as np
import pandas as pd

from src.errors import PortfolioError
from src.main import main
from src.portfolio_loader import load_portfolio, load_portfolio_from_shares
from src.price_loader import (
    MAX_DOWNLOAD_WORKERS,
    download_capacity,
    effective_download_workers,
    load_price_histories,
    validate_download_workers,
)
from src.providers import (
    AlphaVantageAPI,
    AlphaVantageQuotaError,
    DataCoverageError,
    ProviderError,
    YahooFinanceAPI,
)
from src.providers.base import cache_lock, cache_path, prune_cache, read_cache, write_cache

WAIT = 5  # Segundos máximos de cualquier espera entre hilos: un fallo no bloquea la suite.
START, END = "2026-01-01", "2026-01-10"
CLOSES = {
    "A": [90, 100, 110],
    "B": [40, 50, 45],
    "C": [10, 11, 12],
    "D": [20, 19, 21],
    "E": [5, 6, 7],
    "F": [70, 71, 69],
    "G": [33, 34, 35],
    "H": [8, 9, 10],
}


class FakeProvider:
    """Responde por símbolo y registra cuántas llamadas hay activas a la vez."""

    def __init__(self, capacity=MAX_DOWNLOAD_WORKERS, behaviour=None, price_basis="split_adjusted"):
        if capacity is not None:
            self.max_download_workers = capacity
        self.behaviour = behaviour or {}
        self.price_basis = price_basis
        self.calls = []
        self.active = 0
        self.max_active = 0
        self._lock = threading.Lock()

    def get_prices(self, symbol, start, end, *, adjusted=False):
        with self._lock:
            self.calls.append(symbol)
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            action = self.behaviour.get(symbol)
            if action is not None:
                action()
            return fixtures.history(symbol, CLOSES[symbol], price_basis=self.price_basis)
        finally:
            with self._lock:
                self.active -= 1


class RecordingExecutor(ThreadPoolExecutor):
    """Executor real que anota lo enviado y cómo se cierra; release desbloquea a los hilos."""

    instances = []

    def __init__(self, *args, release=None, fail_shutdown=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.submitted = []
        self.shutdowns = []
        self.release = release
        self.fail_shutdown = fail_shutdown
        RecordingExecutor.instances.append(self)

    def submit(self, fn, *args, **kwargs):
        self.submitted.append(args[1])
        return super().submit(fn, *args, **kwargs)

    def shutdown(self, wait=True, *, cancel_futures=False):
        self.shutdowns.append(cancel_futures)
        if self.release is not None:
            self.release.set()
        super().shutdown(wait=wait, cancel_futures=cancel_futures)
        if self.fail_shutdown:
            raise RuntimeError("fallo al cerrar")


def recording_executor(**options):
    RecordingExecutor.instances = []
    return patch(
        "src.price_loader.ThreadPoolExecutor",
        side_effect=lambda *args, **kwargs: RecordingExecutor(*args, **options, **kwargs),
    )


class BatchLoaderTests(unittest.TestCase):
    def test_order_follows_the_input_even_if_b_finishes_first(self):
        b_done = threading.Event()
        provider = FakeProvider(
            behaviour={
                "A": lambda: self.assertTrue(b_done.wait(WAIT)),
                "B": b_done.set,
            }
        )
        # B termina antes que A, pero cada activo conserva su peso y su número de acciones.
        weighted = load_portfolio({"A": 0.7, "B": 0.3}, provider, START, END, max_workers=2)
        self.assertEqual([asset.symbol for asset in weighted.assets], ["A", "B"])
        self.assertEqual(weighted.target_weights.to_dict(), {"A": 0.7, "B": 0.3})

        b_done.clear()
        shares = load_portfolio_from_shares({"A": 10, "B": 3}, provider, START, END, max_workers=2)
        self.assertEqual([asset.symbol for asset in shares.assets], ["A", "B"])
        self.assertEqual(shares.units.to_dict(), {"A": 10, "B": 3})

    def test_four_workers_overlap_and_never_exceed_four_calls(self):
        # La barrera solo se abre si cuatro llamadas están activas a la vez.
        barrier = threading.Barrier(4, timeout=WAIT)
        provider = FakeProvider(behaviour={symbol: barrier.wait for symbol in CLOSES})
        with recording_executor():
            histories = load_price_histories(list(CLOSES), provider, START, END, max_workers=4)
        self.assertEqual([history.symbol for history in histories], list(CLOSES))
        self.assertEqual(provider.max_active, 4)
        self.assertEqual(sorted(provider.calls), sorted(CLOSES))
        executor = RecordingExecutor.instances[0]
        self.assertEqual(executor._max_workers, 4)
        self.assertEqual(executor.submitted, list(CLOSES))

    def test_one_worker_or_one_asset_runs_sequentially_without_an_executor(self):
        parallel = load_price_histories(list(CLOSES), FakeProvider(), START, END, max_workers=4)
        with patch("src.price_loader.ThreadPoolExecutor") as executor:
            sequential = load_price_histories(
                [f" {symbol} " for symbol in CLOSES], FakeProvider(), START, END
            )
            single = load_price_histories(["A"], FakeProvider(), START, END, max_workers=4)
        executor.assert_not_called()
        self.assertEqual(len(sequential), len(parallel))
        for left, right in zip(sequential, parallel, strict=True):
            self.assertEqual(left.symbol, right.symbol)
            pd.testing.assert_frame_equal(left.prices, right.prices)
        self.assertEqual(single[0].symbol, "A")

    def test_invalid_input_fails_before_calling_the_provider(self):
        provider = FakeProvider()
        cases = {
            "pesos": lambda: load_portfolio({"A": 0.5, "B": 0.4}, provider, START, END),
            "acciones": lambda: load_portfolio_from_shares({"A": -1}, provider, START, END),
            "repetidos": lambda: load_price_histories(["A", " a "], provider, START, END),
            "vacío": lambda: load_price_histories(["A", " "], provider, START, END),
            "fechas": lambda: load_price_histories(["A"], provider, "2026-01-10", START),
            "formato": lambda: load_price_histories(["A"], provider, "01/01/2026", END),
        }
        for workers in (0, 5, True, 2.0, "2", None):
            cases[f"workers={workers!r}"] = lambda workers=workers: load_portfolio(
                {"A": 0.5, "B": 0.5}, provider, START, END, max_workers=workers
            )
        for name, call in cases.items():
            with self.subTest(case=name), self.assertRaises(PortfolioError):
                call()
        self.assertEqual(provider.calls, [])

    def test_validate_download_workers_accepts_one_to_four(self):
        for workers in range(1, MAX_DOWNLOAD_WORKERS + 1):
            validate_download_workers(workers)
        with self.assertRaisesRegex(PortfolioError, "entre 1 y 4"):
            validate_download_workers(False)

    def test_a_failure_names_the_symbol_and_stops_sending_downloads(self):
        release = threading.Event()

        def fail():
            raise DataCoverageError("No hay precios dentro de las fechas solicitadas.")

        provider = FakeProvider(
            behaviour={"A": lambda: self.assertTrue(release.wait(WAIT)), "B": fail}
        )
        with (
            recording_executor(release=release),
            self.assertRaisesRegex(DataCoverageError, r"^B: No hay precios") as caught,
        ):
            load_portfolio({s: 0.25 for s in "ABCD"}, provider, START, END, max_workers=2)
        self.assertIsNone(caught.exception.__cause__)
        executor = RecordingExecutor.instances[0]
        # A seguía descargando cuando falló B: no se envió nada más y se cancelaron pendientes.
        self.assertEqual(executor.submitted, ["A", "B"])
        self.assertEqual(sorted(provider.calls), ["A", "B"])
        self.assertEqual(executor.shutdowns, [True])

    def test_errors_keep_their_type_attributes_and_existing_symbol(self):
        quota = AlphaVantageQuotaError(time.time() + 3600)
        failures = {
            "quota": (quota, AlphaVantageQuotaError),
            "named": (ProviderError("Yahoo no ha devuelto precios para B."), ProviderError),
            "complex": (ProviderError("motivo", 2), ProviderError),
        }
        for name, (error, kind) in failures.items():
            original = str(error)

            def fail(error=error):
                raise error

            provider = FakeProvider(capacity=None, behaviour={"B": fail})
            with self.subTest(case=name), self.assertRaises(kind) as caught:
                load_price_histories(["A", "B"], provider, START, END)
            self.assertIs(caught.exception, error)
            if name == "quota":
                self.assertEqual(caught.exception.retry_at, quota.retry_at)
                self.assertEqual(str(caught.exception), f"B: {original}")
            else:
                self.assertEqual(str(caught.exception), original)

    def test_cleanup_failures_and_interruptions_keep_the_original_error(self):
        for error in (ProviderError("rechazada"), KeyboardInterrupt()):
            release = threading.Event()

            def fail(error=error):
                raise error

            provider = FakeProvider(
                behaviour={"A": lambda release=release: release.wait(WAIT), "B": fail}
            )
            with (
                self.subTest(error=type(error).__name__),
                recording_executor(release=release, fail_shutdown=True),
                self.assertRaises(type(error)) as caught,
            ):
                load_price_histories(["A", "B", "C"], provider, START, END, max_workers=2)
            self.assertIs(caught.exception, error)
            self.assertEqual(RecordingExecutor.instances[0].shutdowns, [True])
            self.assertNotIn("C", provider.calls)

    def test_providers_without_declared_capacity_download_one_at_a_time(self):
        class Flagged(FakeProvider):
            max_download_workers = True

        providers = {
            "sin atributo": FakeProvider(capacity=None),
            "una": FakeProvider(capacity=1),
            "booleano": Flagged(capacity=None),
            "mock": Mock(spec=YahooFinanceAPI),
            "texto": FakeProvider(capacity="4"),
        }
        providers["mock"].get_prices.side_effect = lambda symbol, *args: fixtures.history(
            symbol, CLOSES[symbol]
        )
        for name, provider in providers.items():
            with self.subTest(provider=name), patch("src.price_loader.ThreadPoolExecutor") as pool:
                self.assertEqual(download_capacity(provider), 1)
                load_price_histories(["A", "B", "C"], provider, START, END, max_workers=4)
                pool.assert_not_called()
        self.assertEqual(providers["sin atributo"].max_active, 1)
        self.assertEqual(AlphaVantageAPI.max_download_workers, 1)
        self.assertEqual(YahooFinanceAPI.max_download_workers, 4)
        self.assertEqual(effective_download_workers(FakeProvider(capacity=2), 4, 8), 2)
        self.assertEqual(effective_download_workers(FakeProvider(capacity=9), 4, 8), 4)
        self.assertEqual(effective_download_workers(FakeProvider(), 4, 3), 3)

    def test_financial_results_do_not_depend_on_the_number_of_workers(self):
        results = []
        for workers in (1, 4):
            portfolio = load_portfolio(
                {"A": 0.4, "B": 0.3, "C": 0.2, "D": 0.1},
                FakeProvider(),
                START,
                END,
                max_workers=workers,
            )
            shares = load_portfolio_from_shares(
                {"A": 1, "B": 2, "C": 3}, FakeProvider(), START, END, max_workers=workers
            )
            simulation = portfolio.monte_carlo(steps=5, simulations=50, seed=7)
            results.append((portfolio, shares, simulation))
        (first, first_shares, first_sim), (second, second_shares, second_sim) = results
        pd.testing.assert_frame_equal(first.close_prices(), second.close_prices())
        pd.testing.assert_series_equal(first.current_weights, second.current_weights)
        self.assertEqual(first.total_value, second.total_value)
        self.assertEqual(first_shares.total_value, second_shares.total_value)
        pd.testing.assert_series_equal(first_shares.units, second_shares.units)
        for key, value in first_sim.summary().items():
            other = second_sim.summary()[key]
            if isinstance(value, pd.Series | pd.DataFrame):
                self.assertTrue(value.equals(other), key)
            else:
                np.testing.assert_array_equal(value, other, err_msg=key)


def yahoo_frame(start, end, tz="America/New_York"):
    dates = pd.bdate_range(start, end, inclusive="left", tz=tz)
    return pd.DataFrame({"Close": np.linspace(10, 20, len(dates))}, index=dates)


class YahooConcurrencyTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)

    def test_distinct_cache_entries_download_in_parallel(self):
        # Cada descarga espera a la otra mientras tiene su entrada bloqueada.
        barrier = threading.Barrier(2, timeout=WAIT)

        def history(**kwargs):
            barrier.wait()
            return yahoo_frame(kwargs["start"], kwargs["end"])

        with patch("src.providers.yahoo.yf.Ticker") as ticker:
            ticker.return_value.history.side_effect = history
            api = YahooFinanceAPI(cache_dir=self.folder, include_info=False)
            histories = load_price_histories(
                ["IBM", "MSFT"], api, "2026-01-05", "2026-01-20", max_workers=2
            )
        self.assertEqual([item.symbol for item in histories], ["IBM", "MSFT"])
        self.assertEqual(len(list(self.folder.glob("*.json"))), 2)

    def test_same_entry_from_two_instances_keeps_valid_json_and_both_ranges(self):
        lock = threading.Lock()
        state = {"active": 0, "max": 0}

        def history(**kwargs):
            with lock:
                state["active"] += 1
                state["max"] = max(state["max"], state["active"])
            try:
                return yahoo_frame(kwargs["start"], kwargs["end"])
            finally:
                with lock:
                    state["active"] -= 1

        start = threading.Barrier(2, timeout=WAIT)
        errors = []

        def load(first, last):
            try:
                start.wait()
                YahooFinanceAPI(cache_dir=self.folder, include_info=False).get_prices(
                    "IBM", first, last
                )
            except Exception as error:  # noqa: BLE001 - se comprueba abajo
                errors.append(error)

        with patch("src.providers.yahoo.yf.Ticker") as ticker:
            ticker.return_value.history.side_effect = history
            threads = [
                threading.Thread(target=load, args=("2026-01-05", "2026-02-01")),
                threading.Thread(target=load, args=("2026-03-02", "2026-04-01")),
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(WAIT)
                self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        # La misma entrada nunca se descarga dos veces a la vez y la segunda une los intervalos.
        self.assertEqual(state["max"], 1)
        self.assertEqual(ticker.return_value.history.call_count, 2)
        files = list(self.folder.iterdir())
        self.assertEqual(len(files), 1)
        cached = json.loads(files[0].read_text(encoding="utf-8"))
        self.assertEqual((cached["start"], cached["end"]), ("2026-01-05", "2026-04-01"))

    def test_missing_profiles_keep_their_issue_and_the_currency_check(self):
        tickers = {}

        def make_ticker(symbol):
            item = tickers.setdefault(symbol, Mock())
            item.history.side_effect = lambda **kwargs: yahoo_frame(
                kwargs["start"], kwargs["end"], tz="UTC"
            )
            if symbol == "IBM":
                item.get_info.side_effect = RuntimeError("429 Too Many Requests")
            else:
                item.get_info.return_value = {"quoteType": "EQUITY", "currency": "USD"}
            return item

        weights = {"IBM": 0.5, "MSFT": 0.5}
        with patch("src.providers.yahoo.yf.Ticker", side_effect=make_ticker):
            with self.assertRaisesRegex(PortfolioError, "IBM"):
                load_portfolio(
                    weights, YahooFinanceAPI(), "2026-01-05", "2026-01-20", max_workers=2
                )
            portfolio = load_portfolio(
                weights, YahooFinanceAPI(), "2026-01-05", "2026-01-20", "USD", max_workers=2
            )
        issues = {asset.symbol: asset.history.profile.issue for asset in portfolio.assets}
        self.assertIn("Yahoo Finance", issues["IBM"])
        self.assertIsNone(issues["MSFT"])


class CacheTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        self.entry = cache_path(self.folder, ["test"])

    def test_concurrent_writes_use_their_own_temporaries(self):
        barrier = threading.Barrier(4, timeout=WAIT)

        def write(number):
            barrier.wait()
            write_cache(self.entry, {"value": number})

        with ThreadPoolExecutor(4) as pool:
            list(pool.map(write, range(4)))
        self.assertEqual([path.name for path in self.folder.iterdir()], [self.entry.name])
        self.assertIn(read_cache(self.entry, 60)["value"], range(4))

    def test_write_errors_remove_only_their_temporary_and_keep_the_answer(self):
        unrelated = self.folder / "notas.json"
        unrelated.write_text("{}", encoding="utf-8")
        write_cache(self.entry, {"value": object()})
        with patch("src.providers.base.os.replace", side_effect=PermissionError):
            write_cache(self.entry, {"value": 1})
        self.assertEqual([path.name for path in self.folder.iterdir()], ["notas.json"])

    def test_prune_waits_for_writes_and_only_removes_expired_cache_files(self):
        old = time.time() - 2 * 86400
        stale_temporary = self.folder / f".{self.entry.name}.1234.tmp"
        expired = cache_path(self.folder, ["expired"])
        unrelated = self.folder / "notas.json.1234.tmp"
        for path in (self.entry, stale_temporary, expired, unrelated):
            path.write_text("{}", encoding="utf-8")
            os.utime(path, (old, old))
        # Mientras se escribe la entrada, la limpieza espera y después la encuentra vigente.
        with cache_lock(self.entry):
            thread = threading.Thread(target=prune_cache, args=(self.folder, 86400))
            thread.start()
            write_cache(self.entry, {"value": 1})
        thread.join(WAIT)
        self.assertFalse(thread.is_alive())
        remaining = sorted(path.name for path in self.folder.iterdir())
        self.assertEqual(remaining, sorted([self.entry.name, unrelated.name]))

    def test_zero_ttl_disables_the_yahoo_cache(self):
        with patch("src.providers.yahoo.yf.Ticker") as ticker:
            ticker.return_value.history.side_effect = lambda **kwargs: yahoo_frame(
                kwargs["start"], kwargs["end"]
            )
            api = YahooFinanceAPI(cache_dir=self.folder, cache_ttl=0, include_info=False)
            load_price_histories(["IBM", "MSFT"], api, "2026-01-05", "2026-01-20", max_workers=2)
        self.assertEqual(list(self.folder.iterdir()), [])


class CliTests(unittest.TestCase):
    def setUp(self):
        for name in ("load_risk_free_rate", "load_dotenv"):
            patcher = patch(f"src.main.{name}", return_value=None)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_main(self, arguments, provider_name="YahooFinanceAPI", provider=None):
        provider = provider or FakeProvider()
        with (
            patch(f"src.main.{provider_name}", return_value=provider),
            patch("src.main.load_portfolio", wraps=load_portfolio) as weights,
            patch("src.main.load_portfolio_from_shares", wraps=load_portfolio_from_shares) as units,
            patch.dict(os.environ, {"ALPHA_VANTAGE_API_KEY": "test-key"}),
            redirect_stdout(io.StringIO()),
            redirect_stderr(io.StringIO()) as errors,
        ):
            code = main(arguments)
        return code, weights, units, errors.getvalue()

    def test_download_workers_reach_weights_shares_and_the_estimation(self):
        dates = ["--start", "2026-01-01", "--end", "2026-01-10"]
        code, weights, _, errors = self.run_main(
            ["--assets", "A:0.6", "B:0.4", "--download-workers", "4", "--simulate"]
            + ["--simulations", "10", "--estimation-start", "2025-12-01", *dates]
        )
        self.assertEqual(code, 0, errors)
        self.assertEqual([c.kwargs["max_workers"] for c in weights.call_args_list], [4, 4])
        self.assertNotIn("--download-workers", errors)

        code, _, units, errors = self.run_main(
            ["--shares", "A:10", "B:5", "--download-workers", "2", *dates],
            provider=FakeProvider(),
        )
        self.assertEqual(code, 0, errors)
        self.assertEqual(units.call_args.kwargs["max_workers"], 2)

    def test_alpha_vantage_warns_once_and_downloads_one_at_a_time(self):
        provider = FakeProvider(capacity=1, price_basis="unadjusted")
        code, weights, _, errors = self.run_main(
            ["--provider", "alpha_vantage", "--assets", "A:0.6", "B:0.4", "--simulate"]
            + ["--simulations", "10", "--download-workers", "4", "--start", "2026-01-01"]
            + ["--end", "2026-01-10", "--estimation-start", "2025-12-01"],
            "AlphaVantageAPI",
            provider,
        )
        self.assertEqual(code, 0, errors)
        self.assertEqual(errors.count("--download-workers 4"), 1)
        self.assertIn("de uno en uno", errors)
        self.assertEqual(provider.max_active, 1)
        self.assertEqual(len(weights.call_args_list), 2)

    def test_invalid_download_workers_are_rejected_by_the_parser(self):
        for value in ("0", "5", "dos", "1.5"):
            with (
                self.subTest(value=value),
                redirect_stderr(io.StringIO()),
                self.assertRaises(SystemExit),
            ):
                main(["--assets", "A:1", "--download-workers", value])


if __name__ == "__main__":
    unittest.main()
