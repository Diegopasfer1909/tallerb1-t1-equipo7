import numpy as np
import pandas as pd
import pytest

from toolkit import MacroSeries, PriceSeries


def test_estadisticos_automaticos_al_instanciar(datos):
    precios = datos["precios"]["AAA"]
    serie = PriceSeries("AAA", "sintético", precios)
    rent = precios.pct_change().dropna()
    assert serie.media == pytest.approx(rent.mean())
    assert serie.desviacion == pytest.approx(rent.std())
    assert serie.volatilidad_anual == pytest.approx(rent.std() * np.sqrt(252))


def test_macro_calcula_estadisticos_sobre_niveles(datos):
    vix = MacroSeries("VIX", "sintético", datos["vix"])
    assert vix.media == 18 and vix.desviacion == 0


def test_normaliza_zona_horaria_duplicados_y_huecos():
    fechas = pd.DatetimeIndex(["2024-01-03 09:00", "2024-01-02 09:00", "2024-01-03 17:00", "2024-01-04"],
                              tz="Europe/Madrid")
    serie = PriceSeries("X", "test", pd.Series([10.0, 9.0, 11.0, np.nan], index=fechas))
    assert list(serie.datos) == [9.0, 11.0]               # ordenada, último duplicado, sin NaN
    assert serie.datos.index.tz is None


@pytest.mark.parametrize("datos, error", [
    (pd.Series([1.0, 2.0], index=["a", "b"]), TypeError),
    (pd.Series([1.0], index=pd.to_datetime(["2024-01-01"])), ValueError),
    (pd.Series([1.0, -2.0], index=pd.to_datetime(["2024-01-01", "2024-01-02"])), ValueError),
    ([1.0, 2.0], TypeError),
])
def test_rechaza_inputs_invalidos(datos, error):
    with pytest.raises(error):
        PriceSeries("X", "test", datos)


def test_tipo_de_activo_valido(datos):
    with pytest.raises(ValueError, match="tipo"):
        PriceSeries("X", "test", datos["precios"]["AAA"], tipo="bono")


def test_conversion_de_divisa(datos):
    usd = PriceSeries("AAA", "sintético", datos["precios"]["AAA"], divisa="usd")
    cambio = MacroSeries("DEXUSEU", "sintético", pd.Series(1.25, index=datos["fechas"]))
    eur = usd.convertir(cambio)
    assert eur.divisa == "EUR" and usd.divisa == "USD"
    assert eur.datos.iloc[-1] == pytest.approx(usd.datos.iloc[-1] / 1.25)
    assert eur.media == pytest.approx(usd.media)             # cambio constante: misma rentabilidad
