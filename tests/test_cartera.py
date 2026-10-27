import dataclasses

import numpy as np
import pandas as pd
import pytest

from toolkit import Cartera, MacroSeries, PriceSeries
from toolkit.analisis.metricas import cagr
from toolkit.modelos import ContextoMercado


def test_cartera_es_dataclass_con_los_metodos_del_enunciado(cartera):
    assert dataclasses.is_dataclass(cartera)
    for metodo in ("report", "plots_report", "montecarlo"):
        assert callable(getattr(cartera, metodo))


def test_cagr_de_rentabilidad_constante():
    rent = pd.Series(0.001, index=pd.bdate_range("2024-01-01", periods=100))
    assert cagr(rent) == pytest.approx(1.001 ** 252 - 1)


# ------------------------------------------------------------------ rebalanceo

def test_sin_rebalanceo_es_comprar_y_mantener(activos, datos):
    c = Cartera(activos, datos["pesos"], rebalanceo=None, mercado=ContextoMercado())
    p, w = datos["precios"], pd.Series(datos["pesos"], index=["AAA", "BBB", "CCC"])
    assert c.valor.iloc[-1] == pytest.approx((p.iloc[-1] / p.iloc[0] * w).sum())
    deriva = w * p.iloc[-1] / p.iloc[0]
    pd.testing.assert_series_equal(c.pesos_actuales, deriva / deriva.sum(), check_names=False)


def test_rebalanceo_mensual(activos, datos):
    c = Cartera(activos, datos["pesos"], rebalanceo="monthly", mercado=ContextoMercado())
    p, w = datos["precios"], pd.Series(datos["pesos"], index=["AAA", "BBB", "CCC"])
    # A mano: cada mes se invierte el valor acumulado con los pesos objetivo.
    capital, anterior = 1.0, p.iloc[0]
    for _, mes in p.groupby(p.index.to_period("M")):
        capital *= (w * mes.iloc[-1] / anterior).sum()
        anterior = mes.iloc[-1]
    assert c.valor.iloc[-1] == pytest.approx(capital)
    # Los pesos actuales solo derivan desde el último rebalanceo, no desde el inicio.
    ultimo_mes = p[p.index.to_period("M") == p.index[-1].to_period("M")]
    deriva = w * p.iloc[-1] / p.loc[:ultimo_mes.index[0]].iloc[-2]
    pd.testing.assert_series_equal(c.pesos_actuales, deriva / deriva.sum(), check_names=False)


@pytest.mark.parametrize("valor", ["none", "None"])
def test_rebalanceo_none_como_texto(activos, datos, valor):
    assert Cartera(activos, datos["pesos"], rebalanceo=valor, mercado=ContextoMercado()).rebalanceo is None


def test_rebalanceo_invalido(activos, datos):
    with pytest.raises(ValueError, match="monthly"):
        Cartera(activos, datos["pesos"], rebalanceo="daily", mercado=ContextoMercado())


# ------------------------------------------------------------------ validación de inputs

@pytest.mark.parametrize("pesos, mensaje", [
    ([0.5, 0.3, 0.1], "sumar 1"),
    ({"AAA": 0.5, "BBB": 0.5}, "no coinciden"),
    ([1.2, -0.4, 0.2], "negativos"),
    ([0.5, 0.5], "3 activos"),
])
def test_pesos_invalidos(activos, pesos, mensaje):
    with pytest.raises(ValueError, match=mensaje):
        Cartera(activos, pesos, mercado=ContextoMercado())


def test_pesos_como_dict(activos):
    c = Cartera(activos, {"CCC": 0.2, "AAA": 0.5, "BBB": 0.3}, mercado=ContextoMercado())
    assert list(c.pesos.index) == ["AAA", "BBB", "CCC"]


def test_activos_deben_ser_tickers_o_priceseries(datos):
    with pytest.raises(TypeError, match="PriceSeries"):
        Cartera([datos["precios"]["AAA"]], [1.0], mercado=ContextoMercado())


def test_activo_repetido(activos):
    with pytest.raises(ValueError, match="repetidos"):
        Cartera([activos[0], activos[0]], [0.5, 0.5], mercado=ContextoMercado())


def test_divisa_sin_tipo_de_cambio(datos):
    usd = PriceSeries("AAA", "test", datos["precios"]["AAA"], divisa="USD")
    with pytest.raises(ValueError, match="tipo de cambio"):
        Cartera([usd], [1.0], mercado=ContextoMercado())
    cambio = MacroSeries("DEXUSEU", "test", pd.Series(1.1, index=datos["fechas"]))
    c = Cartera([usd], [1.0], mercado=ContextoMercado(tipos_cambio={"USD": cambio}))
    assert c.precios["AAA"].iloc[0] == pytest.approx(usd.datos.iloc[0] / 1.1)
    assert c.contexto["efecto_divisa"]["AAA"] == pytest.approx(0, abs=1e-12)


def test_historia_insuficiente(datos):
    corta = PriceSeries("X", "test", datos["precios"]["AAA"].iloc[:20])
    with pytest.raises(ValueError, match="sesiones comunes"):
        Cartera([corta], [1.0], mercado=ContextoMercado())


@pytest.mark.parametrize("fechas, mensaje", [
    ({"fecha_inicio": "2023-01-01", "fecha_fin": "2022-01-01"}, "anterior"),
    ({"fecha_inicio": "ayer"}, "AAAA-MM-DD"),
])
def test_fechas_invalidas(activos, datos, fechas, mensaje):
    with pytest.raises(ValueError, match=mensaje):
        Cartera(activos, datos["pesos"], mercado=ContextoMercado(), **fechas)


def test_capital_inicial(activos, datos, mercado):
    c = Cartera(activos, datos["pesos"], capital_inicial=50_000, mercado=mercado)
    texto = c.report(["resumen", "composicion"])
    assert "Valor final de 50.000 €" in texto and "25.000 €" in texto        # 50 % de AAA
    assert c.montecarlo(n_simulaciones=100).parametros["capital"] == 50_000
    with pytest.raises(ValueError, match="capital_inicial"):
        Cartera(activos, datos["pesos"], capital_inicial=-1, mercado=mercado)


def test_sin_benchmark(activos, datos):
    c = Cartera(activos, datos["pesos"], benchmark=None, mercado=ContextoMercado())
    assert c.rm is None and c.rentabilidad["dif_indice"] != c.rentabilidad["dif_indice"]   # NaN


def test_inicio_y_fin_recortan_el_periodo(activos, datos):
    c = Cartera(activos, datos["pesos"], fecha_inicio="2022-06-01", fecha_fin="2023-06-30",
                mercado=ContextoMercado())
    assert c.precios.index[0] >= pd.Timestamp("2022-06-01")
    assert c.precios.index[-1] <= pd.Timestamp("2023-06-30")


# ------------------------------------------------------------------ limpieza

def test_alinea_calendarios_distintos(datos):
    """Un activo sin cotizar algunos días (festivos de su mercado): se rellena y se cuenta."""
    a = PriceSeries("A", "test", datos["precios"]["AAA"])
    b = PriceSeries("B", "test", datos["precios"]["BBB"].drop(datos["fechas"][100:103]))
    c = Cartera([a, b], [0.5, 0.5], mercado=ContextoMercado())
    assert len(c.precios) == 600 and not c.precios.isna().any().any()
    assert c.calidad["imputados"]["B"] == pytest.approx(3 / 600)


def test_hueco_largo_se_descarta(datos):
    b = datos["precios"]["BBB"].drop(datos["fechas"][100:110])     # 10 sesiones > límite de 5
    c = Cartera([PriceSeries("A", "t", datos["precios"]["AAA"]), PriceSeries("B", "t", b)], [0.5, 0.5],
                mercado=ContextoMercado())
    assert c.calidad["fechas_descartadas"] == 5
    assert len(c.precios) == 595


def test_quita_fines_de_semana_y_marca_saltos(datos):
    precios = datos["precios"]["AAA"].copy()
    precios.iloc[300:] *= 3                                          # split mal ajustado
    finde = pd.Series(precios.iloc[-1], index=[pd.Timestamp("2024-04-13")])   # sábado
    c = Cartera([PriceSeries("A", "t", pd.concat([precios, finde]))], [1.0], mercado=ContextoMercado())
    assert c.calidad["fines_de_semana"] == 1
    assert c.calidad["saltos"][0][0] == "A"


# ------------------------------------------------------------------ métricas

def test_base_comun(cartera):
    assert cartera.valor.iloc[0] == 1
    assert cartera.rentabilidad["multiplo"] == pytest.approx(cartera.valor.iloc[-1])
    assert cartera.rf_anual == pytest.approx(0.025)


def test_sin_bund_el_tipo_libre_es_cero(activos, datos):
    c = Cartera(activos, datos["pesos"], mercado=ContextoMercado())
    assert c.rf_anual == 0 and (c.rf == 0).all()
    assert any("Bund" in f for f in c.calidad["fallos"])


def test_drawdown_conocido():
    fechas = pd.bdate_range("2024-01-01", periods=40)
    precios = pd.Series(np.r_[[100, 120, 90, 60, 100, 130], np.linspace(131, 150, 34)], index=fechas)
    c = Cartera([PriceSeries("X", "t", precios)], [1.0], mercado=ContextoMercado())
    assert c.riesgo["drawdown"] == pytest.approx(60 / 120 - 1)
    assert (c.riesgo["dd_pico"], c.riesgo["dd_valle"], c.riesgo["dd_recuperacion"]) == \
        (fechas[1], fechas[3], fechas[5])


def test_cartera_que_replica_el_indice(mercado):
    c = Cartera([mercado.indice], [1.0], mercado=mercado)
    assert c.riesgo["beta"] == pytest.approx(1)
    assert c.ajustada["alfa"] == pytest.approx(0, abs=1e-10)
    assert c.rentabilidad["dif_indice"] == pytest.approx(0)


def test_sharpe(cartera):
    exceso = cartera.rp - cartera.rf
    assert cartera.ajustada["sharpe"] == pytest.approx(exceso.mean() / exceso.std() * np.sqrt(252))


def test_diversificacion(cartera):
    d = cartera.diversificacion
    assert d["contribucion"].sum() == pytest.approx(1)
    assert d["n_efectivo"] == pytest.approx(1 / (0.5 ** 2 + 0.3 ** 2 + 0.2 ** 2))
    assert set(d["par_max"]) == {"AAA", "BBB"}
    assert d["sector"]["Tecnología"] == pytest.approx(0.8)


def test_contexto_de_mercado(cartera):
    m = cartera.contexto
    assert m["vix_actual"] == 18
    assert m["corr_etf_bund"] < 0 and m["bund_peores_dias"] > 0
    assert np.isnan(m["corr_brent"])


def test_advertencias_y_umbrales(cartera):
    nombres = {a["nombre"]: a["nivel"] for a in cartera.advertencias()}
    assert nombres["Concentración en un activo"] == "alta"
    assert nombres["Concentración sectorial"] == "media"
    relajados = {a["nombre"] for a in cartera.advertencias({"peso_alto": 0.6, "peso_medio": 0.55,
                                                             "sector_max": 0.9})}
    assert "Concentración en un activo" not in relajados and "Concentración sectorial" not in relajados
