"""Estandarización: cada API entrega los datos en un formato distinto, pero todas devuelven
el mismo objeto PriceSeries.

Los tests sin marca no usan internet (respuestas grabadas con el formato real de cada API).
Los marcados con `red` descargan datos reales:  python -m pytest -m red
"""
import os

import pandas as pd
import pytest

from toolkit import AlphaVantage, Cartera, Fred, MacroSeries, PriceSeries, YahooFinance
from toolkit.ingesta import ErrorDescarga, FuentePrecios
from toolkit.modelos import ContextoMercado

FECHAS = ["2024-01-02", "2024-01-03", "2024-01-04"]
CIERRES = [10.0, 10.5, 11.0]


class YahooSinRed(YahooFinance):
    """Formato de yfinance: índice con hora y zona horaria; metadatos en `.info`."""

    def _cierres(self, symbol, inicio, fin):
        indice = pd.DatetimeIndex(FECHAS, name="Date").tz_localize("America/New_York")
        return pd.Series(CIERRES, index=indice, name="Close")

    def _metadatos(self, symbol):
        return {"nombre": "Ejemplo SA", "divisa": "USD", "tipo": "accion", "sector": "Technology", "pais": "USA"}


class AlphaVantageSinRed(AlphaVantage):
    """Formato de Alpha Vantage: JSON con fechas en texto, de la más reciente a la más antigua."""

    def _consultar(self, funcion, symbol, **extra):
        if funcion == "TIME_SERIES_DAILY":
            return {"Time Series (Daily)": {f: {"4. close": str(c)} for f, c in reversed(list(zip(FECHAS, CIERRES)))}}
        return {"Name": "Ejemplo SA", "Sector": "TECHNOLOGY", "Currency": "USD", "Country": "USA",
                "AssetType": "Common Stock"}


def test_dos_apis_devuelven_objetos_identicos():
    de_yahoo = YahooSinRed().descargar("EJ")
    de_av = AlphaVantageSinRed(api_key="x").descargar("EJ")
    for serie in (de_yahoo, de_av):
        assert type(serie) is PriceSeries
        assert (serie.divisa, serie.nombre, serie.sector, serie.pais) == ("USD", "Ejemplo SA", "Technology", "USA")
    pd.testing.assert_series_equal(de_yahoo.datos, de_av.datos)
    assert de_yahoo.media == de_av.media
    assert (de_yahoo.source, de_av.source) == ("yfinance", "Alpha Vantage")


def test_descarga_de_varios_a_la_vez_y_errores():
    class ConFallo(YahooSinRed):
        def _cierres(self, symbol, inicio, fin):
            if symbol == "MAL":
                raise ValueError("no existe")
            return super()._cierres(symbol, inicio, fin)

    assert list(ConFallo().descargar_varios(["A", "B", "A"])) == ["A", "B"]
    with pytest.raises(ErrorDescarga, match="MAL"):
        ConFallo().descargar_varios(["A", "MAL"])


def test_cartera_con_tickers_y_otra_fuente(datos):
    class FuenteSintetica(FuentePrecios):
        nombre = "sintética"

        def _cierres(self, symbol, inicio, fin):
            return datos["precios"][symbol].loc[inicio:fin]

    c = Cartera(["AAA", "BBB"], [0.7, 0.3], rebalanceo="monthly", fecha_inicio="2022-01-01",
                fuente=FuenteSintetica(), mercado=ContextoMercado())
    assert [a.source for a in c.activos] == ["sintética", "sintética"]


def test_divisa_en_centavos():
    class Peniques(FuentePrecios):
        nombre = "test"

        def _cierres(self, symbol, inicio, fin):
            return pd.Series([500.0, 510.0], index=pd.to_datetime(FECHAS[:2]))

        def _metadatos(self, symbol):
            return {"divisa": "GBp"}

    serie = Peniques().descargar("X.L")
    assert serie.divisa == "GBP" and serie.datos.iloc[0] == 5.0


def test_alphavantage_sin_clave(monkeypatch):
    monkeypatch.delenv("ALPHAVANTAGE_API_KEY", raising=False)
    with pytest.raises(ValueError, match="clave"):
        AlphaVantage()


@pytest.mark.red
def test_yahoo_acciones_e_indices_en_lote():
    series = YahooFinance().descargar_varios(["SAN.MC", "AAPL", "^STOXX50E"], "2024-01-01", "2024-06-30")
    assert all(type(s) is PriceSeries for s in series.values())
    assert series["AAPL"].divisa == "USD" and series["^STOXX50E"].tipo == "indice"


@pytest.mark.red
def test_fred():
    bund = Fred().descargar("IRLTLT01DEM156N", "2024-01-01", "2024-12-31")
    assert type(bund) is MacroSeries and bund.unidad == "%" and len(bund.datos) == 12


@pytest.mark.red
def test_cartera_en_una_linea():
    c = Cartera(["SAN.MC", "AAPL"], [0.5, 0.5], rebalanceo="monthly", benchmark="^IBEX",
                fecha_inicio="2024-01-01", fecha_fin="2024-12-31")
    assert c.mercado.tipos_cambio["USD"].symbol == "DEXUSEU" and c.mercado.indice.symbol == "^IBEX"


@pytest.mark.red
@pytest.mark.skipif(not os.environ.get("ALPHAVANTAGE_API_KEY"), reason="sin ALPHAVANTAGE_API_KEY")
def test_alphavantage_real():
    serie = AlphaVantage(tamano="compact").descargar("IBM")
    assert type(serie) is PriceSeries and serie.divisa == "USD"
