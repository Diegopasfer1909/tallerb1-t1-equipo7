import numpy as np
import pandas as pd
import pytest

from toolkit.analisis.montecarlo import simular


def test_sin_volatilidad_es_determinista():
    rent = pd.Series(0.001, index=pd.bdate_range("2024-01-01", periods=300))
    res = simular(rent, capital=1000, horizonte=252, n_simulaciones=100)
    assert res.final == pytest.approx(1000 * np.exp(0.001 * 252))
    assert res.metricas["prob_perdida"] == 0


def test_retorno_y_volatilidad_supuestos():
    rent = pd.Series(np.random.default_rng(1).normal(0, 0.01, 500))
    res = simular(rent, retorno=0.05, volatilidad=0.0, horizonte=252, n_simulaciones=50, capital=100)
    assert res.final == pytest.approx(100 * np.exp(0.05))
    assert res.parametros["retorno_origen"] == "supuesto"


def test_mas_volatilidad_ensancha_la_distribucion():
    rent = pd.Series(np.random.default_rng(1).normal(0.0004, 0.01, 500))
    estrecha = simular(rent, volatilidad=0.10, n_simulaciones=4000).metricas
    ancha = simular(rent, volatilidad=0.40, n_simulaciones=4000).metricas
    assert ancha["p_alto"] - ancha["p_bajo"] > 2 * (estrecha["p_alto"] - estrecha["p_bajo"])


def test_semilla_reproducible_y_confianza():
    rent = pd.Series(np.random.default_rng(1).normal(0.0004, 0.01, 500))
    a, b = simular(rent, semilla=7, n_simulaciones=1000), simular(rent, semilla=7, n_simulaciones=1000)
    np.testing.assert_array_equal(a.final, b.final)
    r99 = simular(rent, semilla=7, n_simulaciones=1000, confianza=0.99)
    assert r99.metricas["var_horizonte"] == pytest.approx(10_000 - np.percentile(r99.final, 1))


@pytest.mark.parametrize("kwargs", [{"n_simulaciones": 0}, {"horizonte": 0}, {"confianza": 1.2},
                                    {"capital": -5}])
def test_parametros_invalidos(kwargs):
    with pytest.raises(ValueError):
        simular(pd.Series([0.01, -0.01, 0.0]), **kwargs)


def test_montecarlo_de_la_cartera(cartera):
    assert cartera.simulacion is None
    res = cartera.montecarlo(n_simulaciones=500, horizonte=30)
    assert cartera.simulacion is res and res.trayectorias.shape == (500, 31)


def test_montecarlo_de_un_activo_no_sustituye_al_de_la_cartera(cartera):
    cartera.montecarlo(n_simulaciones=200)
    de_cartera = cartera.simulacion
    res = cartera.montecarlo(n_simulaciones=200, activo="AAA")
    assert list(res.parametros["retorno"]) == ["AAA"] and cartera.simulacion is de_cartera
    with pytest.raises(ValueError, match="no está en la cartera"):
        cartera.montecarlo(activo="ZZZ")


def test_montecarlo_por_activos(cartera):
    basico = cartera.montecarlo(n_simulaciones=4000).metricas
    activos = cartera.montecarlo(n_simulaciones=4000, por_activos=True).metricas
    assert activos["mediana"] == pytest.approx(basico["mediana"], rel=0.05)
    res = cartera.montecarlo(n_simulaciones=20, retorno=0.1, volatilidad={"AAA": 0, "BBB": 0, "CCC": 0},
                             por_activos=True)
    assert res.final == pytest.approx(10_000 * np.exp(0.1), rel=1e-6)
    with pytest.raises(ValueError, match="Falta volatilidad"):
        cartera.montecarlo(volatilidad={"AAA": 0.2}, por_activos=True)


def test_visualizacion(cartera):
    fig = cartera.montecarlo(n_simulaciones=200).plot(mostrar=False)
    assert len(fig.axes) == 2
