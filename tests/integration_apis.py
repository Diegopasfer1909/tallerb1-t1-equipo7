"""Pruebas de integración contra las API reales; necesitan red y, según el caso, claves.

No se ejecutan con `unittest discover` (el archivo no empieza por test_). En GitHub Actions
las lanza el trabajo de integración con los secretos del repositorio; en local:

    python -m unittest tests.integration_apis -v

Cada prueba que necesita una clave se omite si no está configurada. Alpha Vantage gratuito
admite pocas consultas al día, así que sus pruebas hacen una sola petición.
"""

import io
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
    ALFRED_KEY,
    ALPHA_VANTAGE_KEY,
    AlfredAPI,
    AlphaVantageAPI,
    YahooFinanceAPI,
    has_api_key,
)

TODAY = date.today()
END = TODAY.isoformat()
ONE_YEAR_AGO = (TODAY - timedelta(days=365)).isoformat()


@unittest.skipUnless(has_api_key(ALFRED_KEY), f"Falta {ALFRED_KEY}")
class AlfredIntegrationTests(unittest.TestCase):
    def test_default_references_have_published_versions(self):
        """Las series predeterminadas deben tener versiones archivadas recientes.

        Si una serie no las tiene, el informe deja sus medidas sin calcular: esta prueba lo
        detecta antes de que lo descubra un usuario.
        """
        alfred = AlfredAPI()
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
                indicator = alfred.get_series(series_id, ONE_YEAR_AGO, END)
                self.assertTrue(indicator.point_in_time)
                monthly = indicator.frequency.lower().startswith("month")
                limit = MONTHLY_REFERENCE_MAX_AGE_DAYS if monthly else DAILY_REFERENCE_MAX_AGE_DAYS
                latest = indicator.values.dropna().index[-1]
                self.assertLessEqual(
                    (pd.Timestamp(TODAY) - latest).days,
                    limit,
                    f"{series_id} ({kind}): última publicación archivada el {latest.date()}",
                )

    def test_exchange_rates_are_read_by_observation_date(self):
        indicator = AlfredAPI().get_series("DEXUSEU", ONE_YEAR_AGO, END, point_in_time=False)
        self.assertFalse(indicator.point_in_time)
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
class AlphaVantageIntegrationTests(unittest.TestCase):
    def test_compact_daily_prices_with_one_request(self):
        # Unas 40 sesiones caben en las últimas 100 que devuelve el modo compact.
        start = (TODAY - timedelta(days=60)).isoformat()
        history = AlphaVantageAPI().get_prices("IBM", start, END)
        self.assertGreater(len(history.prices), 20)
        self.assertEqual(history.price_basis, "unadjusted")
        self.assertTrue(np.isfinite(history.prices["Close"]).all())


@unittest.skipUnless(has_api_key(ALFRED_KEY), f"Falta {ALFRED_KEY}")
class ReportIntegrationTests(unittest.TestCase):
    def test_console_report_includes_references_as_published(self):
        with tempfile.TemporaryDirectory() as folder:
            arguments = ["--assets", "IBM:0.6", "MSFT:0.4", "--start", ONE_YEAR_AGO, "--report"]
            arguments += ["--report-detail", "full", "--output-dir", folder, "--simulations", "200"]
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()) as errors:
                code = main(arguments)
            self.assertEqual(code, 0, errors.getvalue())
            report = next(Path(folder).glob("*/*.md")).read_text(encoding="utf-8")
        self.assertIn("tal como se publicaron", report)
        self.assertIn("ALFRED", report)
        for metric in ("Ratio de Sharpe", "Inflación anualizada"):
            line = next(line for line in report.splitlines() if line.startswith(f"| {metric} |"))
            self.assertNotIn("No disponible", line, line)


if __name__ == "__main__":
    unittest.main()
