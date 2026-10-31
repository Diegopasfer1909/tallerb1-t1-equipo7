"""Pruebas de integración contra las API reales; necesitan red y, según el caso, claves.

No se ejecutan con `unittest discover` (el archivo no empieza por test_). En GitHub Actions
las lanza el trabajo de integración con los secretos del repositorio; en local:

    python -m unittest tests.integration_apis -v

Cada prueba que necesita una clave se omite si no está configurada. Alpha Vantage gratuito
admite pocas consultas al día, así que sus pruebas hacen una sola petición; con
ALPHA_VANTAGE_INTEGRATION=0 no se consulta, y si la cuota está agotada la prueba se omite
con un aviso en lugar de fallar.
"""

import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date, timedelta
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import numpy as np
import pandas as pd

from src.constants import DAILY_REFERENCE_MAX_AGE_DAYS, MONTHLY_REFERENCE_MAX_AGE_DAYS
from src.main import main
from src.market_loader import REPORT_DEFAULTS
from src.providers import (
    ALPHA_VANTAGE_KEY,
    FRED_KEY,
    AlphaVantageAPI,
    AlphaVantageQuotaError,
    FredAPI,
    ProviderError,
    YahooFinanceAPI,
    has_api_key,
)

TODAY = date.today()
END = TODAY.isoformat()
ONE_YEAR_AGO = (TODAY - timedelta(days=365)).isoformat()
# En GitHub Actions, las pull requests que no cambian el adaptador lo ponen a 0 para no
# gastar la cuota diaria compartida.
ALPHA_VANTAGE_ENABLED = os.getenv("ALPHA_VANTAGE_INTEGRATION", "1") != "0"
# Frases con las que Alpha Vantage avisa, en una respuesta HTTP 200, de que la cuota se agotó.
QUOTA_PHRASES = ("rate limit", "requests per day", "call frequency", "sparingly")


@unittest.skipUnless(has_api_key(FRED_KEY), f"Falta {FRED_KEY}")
class FredIntegrationTests(unittest.TestCase):
    def test_default_references_are_recent(self):
        """Las series predeterminadas deben tener observaciones recientes.

        Si una serie deja de actualizarse, el informe deja sus medidas sin calcular: esta
        prueba lo detecta antes de que lo descubra un usuario.
        """
        fred = FredAPI()
        series = sorted(
            {
                (currency, kind, series_id)
                for currency, defaults in REPORT_DEFAULTS.items()
                for kind, series_id in defaults.items()
                if kind != "benchmark_symbol"
            }
        )
        for currency, kind, series_id in series:
            with self.subTest(currency=currency, series=series_id):
                indicator = fred.get_series(series_id, ONE_YEAR_AGO, END)
                monthly = indicator.frequency.lower().startswith("month")
                limit = MONTHLY_REFERENCE_MAX_AGE_DAYS if monthly else DAILY_REFERENCE_MAX_AGE_DAYS
                latest = indicator.values.dropna().index[-1]
                self.assertLessEqual(
                    (pd.Timestamp(TODAY) - latest).days,
                    limit,
                    f"{series_id} ({kind}): última observación el {latest.date()}",
                )

    def test_exchange_rates(self):
        indicator = FredAPI().get_series("DEXUSEU", ONE_YEAR_AGO, END)
        self.assertGreater(indicator.values.notna().sum(), 150)
        self.assertTrue((indicator.values.dropna() > 0).all())


class YahooIntegrationTests(unittest.TestCase):
    def test_prices_and_profile(self):
        start = (TODAY - timedelta(days=60)).isoformat()
        history = YahooFinanceAPI().get_prices("IBM", start, END)
        self.assertGreater(len(history.prices), 20)
        self.assertEqual(history.price_basis, "split_adjusted")
        # La ficha es complementaria: si Yahoo la limita, se informa en lugar de fallar.
        if history.profile.issue is None:
            self.assertEqual(history.profile.currency, "USD")


@unittest.skipUnless(has_api_key(ALPHA_VANTAGE_KEY), f"Falta {ALPHA_VANTAGE_KEY}")
@unittest.skipUnless(ALPHA_VANTAGE_ENABLED, "ALPHA_VANTAGE_INTEGRATION=0")
class AlphaVantageIntegrationTests(unittest.TestCase):
    def test_compact_daily_prices_with_one_request(self):
        # Unas 40 sesiones caben en las últimas 100 que devuelve el modo compact.
        start = (TODAY - timedelta(days=60)).isoformat()
        try:
            history = AlphaVantageAPI().get_prices("IBM", start, END)
        except ProviderError as error:
            if not isinstance(error, AlphaVantageQuotaError) and not any(
                phrase in str(error).lower() for phrase in QUOTA_PHRASES
            ):
                raise
            # La cuota agotada no indica un fallo del adaptador: se avisa sin bloquear main.
            if os.getenv("GITHUB_ACTIONS"):
                print(f"::warning title=Cuota de Alpha Vantage agotada::{error}")
            self.skipTest(f"Cuota de Alpha Vantage agotada: {error}")
        self.assertGreater(len(history.prices), 20)
        self.assertEqual(history.price_basis, "unadjusted")
        self.assertTrue(np.isfinite(history.prices["Close"]).all())


@unittest.skipUnless(has_api_key(FRED_KEY), f"Falta {FRED_KEY}")
class ReportIntegrationTests(unittest.TestCase):
    def test_console_report_includes_economic_references(self):
        with tempfile.TemporaryDirectory() as folder:
            arguments = ["--assets", "IBM:0.6", "MSFT:0.4", "--start", ONE_YEAR_AGO, "--report"]
            arguments += ["--report-detail", "full", "--output-dir", folder, "--simulations", "200"]
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()) as errors:
                code = main(arguments)
            self.assertEqual(code, 0, errors.getvalue())
            report = next(Path(folder).glob("*/*.md")).read_text(encoding="utf-8")
        self.assertIn("incluyen las revisiones", report)
        self.assertIn("FRED", report)
        for metric in ("Ratio de Sharpe", "Inflación anualizada"):
            line = next(line for line in report.splitlines() if line.startswith(f"| {metric} |"))
            self.assertNotIn("No disponible", line, line)


if __name__ == "__main__":
    unittest.main()
