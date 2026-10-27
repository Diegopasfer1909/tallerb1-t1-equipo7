import matplotlib
import numpy as np
import pandas as pd
import pytest

matplotlib.use("Agg")

from toolkit import Cartera, MacroSeries, PriceSeries  # noqa: E402
from toolkit.modelos import ContextoMercado  # noqa: E402


@pytest.fixture(autouse=True)
def carpeta_temporal(tmp_path, monkeypatch):
    """report() guarda en ./informe: cada test trabaja en su propia carpeta temporal."""
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def datos():
    """Tres activos e índice sintéticos (600 sesiones), Bund al 2,5 % y contexto de mercado."""
    rng = np.random.default_rng(0)
    fechas = pd.bdate_range("2022-01-03", periods=600)
    mercado = rng.normal(0.0003, 0.01, len(fechas))
    rent = pd.DataFrame({
        "AAA": 0.0002 + 1.2 * mercado + rng.normal(0, 0.008, len(fechas)),
        "BBB": 0.0001 + 0.8 * mercado + rng.normal(0, 0.006, len(fechas)),
        "CCC": 0.0004 + rng.normal(0, 0.015, len(fechas)),
    }, index=fechas)
    meses = pd.date_range("2021-12-01", fechas[-1], freq="MS")
    return {
        "fechas": fechas,
        "precios": 100 * (1 + rent).cumprod(),
        "pesos": [0.5, 0.3, 0.2],
        "indice": pd.Series(1000 * np.cumprod(1 + mercado), index=fechas),
        "bund": pd.Series(2.5, index=meses),
        "hicp": pd.Series(100 * 1.002 ** np.arange(len(meses)), index=meses),
        "vix": pd.Series(18.0, index=fechas),
        "oro": pd.Series(2000 * np.cumprod(1 + rng.normal(0, 0.01, len(fechas))), index=fechas),
        "etf_bund": pd.Series(100 * np.cumprod(1 - 0.3 * mercado), index=fechas),
        "sectores": {"AAA": "Tecnología", "BBB": "Tecnología", "CCC": "Energía"},
    }


@pytest.fixture
def activos(datos):
    return [PriceSeries(symbol=t, source="sintético", datos=datos["precios"][t], nombre=t.title(),
                        sector=datos["sectores"][t]) for t in datos["precios"]]


@pytest.fixture
def mercado(datos):
    """Contexto ya construido: así los tests no descargan nada."""
    return ContextoMercado(
        indice=PriceSeries("IDX", "sintético", datos["indice"], nombre="Índice sintético", tipo="indice"),
        bund=MacroSeries("BUND", "sintético", datos["bund"], unidad="%", frecuencia="mensual"),
        inflacion=MacroSeries("HICP", "sintético", datos["hicp"], unidad="índice", frecuencia="mensual"),
        vix=MacroSeries("VIX", "sintético", datos["vix"], unidad="puntos"),
        oro=PriceSeries("ORO", "sintético", datos["oro"], tipo="materia_prima"),
        etf_bund=PriceSeries("ETF", "sintético", datos["etf_bund"], tipo="etf"),
    )


@pytest.fixture
def cartera(activos, datos, mercado):
    return Cartera(activos, datos["pesos"], rebalanceo="monthly", mercado=mercado)
