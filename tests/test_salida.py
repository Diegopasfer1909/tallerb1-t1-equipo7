import pytest

from toolkit.salida.graficos import CATALOGO, TITULOS
from toolkit.salida.report import AVISO_MC, SECCIONES


def test_report_por_defecto_incluye_todas_las_secciones_y_graficos(cartera, tmp_path):
    texto = cartera.report()
    for titulo, _ in SECCIONES.values():
        assert f"<summary><b>{titulo}</b>" in texto
    assert texto.count("<details>") == len(SECCIONES)
    assert "Valor final de 10.000 €" in texto and "rebalanceo mensual" in texto
    assert "![evolucion](graficos/evolucion.png)" in texto
    assert (tmp_path / "informe" / "graficos" / "evolucion.png").exists()


def test_report_se_guarda_automaticamente(cartera, tmp_path):
    texto = cartera.report(graficos=False)
    assert texto.archivo == (tmp_path / "informe" / "report.md").resolve()
    assert texto.archivo.read_text(encoding="utf-8") == texto
    assert "![" not in texto
    assert cartera.report(ruta=None, graficos=False).archivo is None


def test_noticias_en_contexto_de_mercado(activos, datos):
    import numpy as np
    import pandas as pd

    from toolkit import Cartera
    from toolkit.modelos import ContextoMercado

    hoy = pd.Timestamp.now().normalize()
    noticias = pd.DataFrame({
        "ticker": ["AAA"] * 6 + ["BBB"] * 2,
        "fecha": [hoy - pd.Timedelta(days=d) for d in (1, 2, 3, 10, 20, 25, 1, 2)],
        "titular": [f"Titular {i}" for i in range(8)],
        "score": [0.5, 0.5, 0.5, -0.5, -0.5, -0.5, np.nan, np.nan],
    })
    c = Cartera(activos, datos["pesos"], mercado=ContextoMercado(noticias=noticias))
    s = c.contexto["sentimiento"]
    assert s.loc["AAA", "noticias"] == 6 and s.loc["AAA", "score"] == pytest.approx(0)
    assert s.loc["AAA", "tendencia"] == pytest.approx(0.5)            # última semana más positiva
    assert s.loc["BBB", "noticias"] == 2 and np.isnan(s.loc["BBB", "score"])

    texto = c.report(["mercado"], graficos=False)
    assert "Noticias y sentimiento" in texto and "| BBB | 2 | n/d |" in texto and "sin puntuar" in texto
    assert "**AAA** · " in texto and "Titular 0" in texto              # últimos titulares
    assert "Google News" in c.report(["calidad"], graficos=False)


def test_aviso_si_no_hay_simulacion(cartera):
    assert AVISO_MC in cartera.report(["montecarlo"])
    cartera.montecarlo(n_simulaciones=500)
    texto = cartera.report(["montecarlo"])
    assert AVISO_MC not in texto and "Probabilidad de pérdida" in texto


def test_report_parametrizable(cartera, tmp_path):
    texto = cartera.report(["resumen", "riesgo"])
    assert "<b>5. Riesgo</b>" in texto and "Diversificación" not in texto

    sin_aviso = cartera.report(["advertencias"], umbrales={"peso_alto": 0.9, "peso_medio": 0.9})
    assert "Concentración en un activo" not in sin_aviso

    cartera.report(ruta=tmp_path / "otra")
    assert (tmp_path / "otra" / "report.md").exists()

    with pytest.raises(ValueError, match="desconocidas"):
        cartera.report(["inventada"])


def test_plots_report_genera_su_propio_md(cartera, tmp_path):
    texto = cartera.plots_report()
    assert texto.archivo == (tmp_path / "informe" / "graficos.md").resolve()
    assert texto.count("<details>") == len(CATALOGO)
    for nombre, (titulo, _) in TITULOS.items():
        assert f"<summary><b>{titulo}</b>" in texto
    assert "![correlaciones](graficos/correlaciones.png)" in texto
    assert (tmp_path / "informe" / "graficos" / "correlaciones.png").exists()
    assert AVISO_MC in texto                                   # Monte Carlo sin ejecutar


def test_plots_report_parametrizable(cartera, tmp_path):
    cartera.montecarlo(n_simulaciones=200)
    texto = cartera.plots_report(["correlaciones", "montecarlo"])
    assert texto.count("<details>") == 2 and "![montecarlo](graficos/montecarlo.png)" in texto
    assert (tmp_path / "informe" / "graficos" / "montecarlo.png").exists()
    assert cartera.plots_report(["drawdown"], ruta=None).archivo is None
    with pytest.raises(ValueError, match="desconocidos"):
        cartera.plots_report(["inventado"])
