"""Mide la descarga en lote con 1, 2 y 4 trabajadores; no forma parte de la suite de pruebas.

Uso:
    python -m tests.benchmark_downloads                 # red simulada, sin conexión
    python -m tests.benchmark_downloads --real          # Yahoo real, muestra pequeña

Cada medición usa un directorio de caché temporal propio, primero vacío y después poblado,
de modo que no toca la caché personal (.cache/market-data). Con red simulada, cada petición
de yfinance espera una latencia fija: valida el mecanismo, pero no acredita la aceleración
real de Yahoo. Con --real no se repite la medición si Yahoo limita las consultas.
"""

import argparse
import json
import platform
import sys
import tempfile
import threading
import time
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
import yfinance

from src.price_loader import load_price_histories
from src.providers import ProviderError, YahooFinanceAPI
from src.providers.yahoo import quiet_yfinance_warnings

SYMBOLS = ["IBM", "MSFT", "AAPL", "KO", "JNJ", "XOM", "PG", "SPY"]
START, END = "2025-01-02", "2026-01-02"
WORKERS = (1, 2, 4)


class CountingProvider:
    """Cuenta las llamadas lógicas a get_prices() sin cambiar el proveedor medido."""

    def __init__(self, provider: YahooFinanceAPI):
        self.provider = provider
        self.max_download_workers = provider.max_download_workers
        self.calls = 0
        self._lock = threading.Lock()

    def get_prices(self, symbol, start, end, *, adjusted=False):
        with self._lock:
            self.calls += 1
        return self.provider.get_prices(symbol, start, end, adjusted=adjusted)


def simulated_yfinance(latency: float):
    """Sustituye yf.Ticker por uno que espera latency segundos en cada petición."""

    def ticker(symbol):
        item = Mock()

        def history(start, end, **kwargs):
            time.sleep(latency)
            dates = pd.bdate_range(start, end, inclusive="left", tz="America/New_York")
            return pd.DataFrame({"Close": range(1, len(dates) + 1)}, index=dates, dtype=float)

        def info():
            time.sleep(latency)
            return {"quoteType": "EQUITY", "currency": "USD", "longName": symbol}

        item.history.side_effect = history
        item.get_info.side_effect = info
        return item

    return patch("src.providers.yahoo.yf.Ticker", side_effect=ticker)


def measure(symbols, workers, cache_dir) -> dict:
    provider = CountingProvider(YahooFinanceAPI(cache_dir=cache_dir))
    started = time.perf_counter()
    error = None
    try:
        load_price_histories(symbols, provider, START, END, max_workers=workers)
    except ProviderError as failure:
        error = str(failure)
    return {
        "seconds": round(time.perf_counter() - started, 3),
        "calls": provider.calls,
        "error": error,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--real", action="store_true", help="Consultar Yahoo Finance de verdad")
    parser.add_argument("--latency", type=float, default=0.2, help="Segundos simulados (0.2)")
    parser.add_argument("--symbols", nargs="+", default=SYMBOLS)
    args = parser.parse_args(argv)
    quiet_yfinance_warnings()
    mode = "yahoo" if args.real else f"simulado ({args.latency} s por petición)"
    print(
        json.dumps(
            {
                "modo": mode,
                "python": platform.python_version(),
                "yfinance": yfinance.__version__,
                "pandas": pd.__version__,
                "activos": args.symbols,
                "fechas": [START, END],
            },
            ensure_ascii=False,
        )
    )
    context = nullcontext() if args.real else simulated_yfinance(args.latency)
    with context:
        for workers in WORKERS:
            with tempfile.TemporaryDirectory() as folder:
                for cache in ("vacía", "poblada"):
                    row = measure(args.symbols, workers, Path(folder))
                    print(json.dumps({"trabajadores": workers, "caché": cache, **row}))
                    if args.real and row["error"]:
                        print("Yahoo ha devuelto un error: no se repite la medición.")
                        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
