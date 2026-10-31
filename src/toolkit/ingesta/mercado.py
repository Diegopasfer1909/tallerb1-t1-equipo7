"""Descarga del contexto de mercado de una cartera: índice, Bund, inflación, VIX, Brent,
oro, ETF de Bunds y los tipos de cambio necesarios para pasar a EUR."""
from ..modelos.mercado import ContextoMercado
from .base import ErrorDescarga, FuentePrecios
from .fred import Fred
from .yahoo import YahooFinance

ETF_BUND = "EXX6.DE"


def descargar_contexto(inicio: str, fin: str | None = None, *, divisas: set[str] = frozenset(),
                       indice: str | None = "^STOXX50E", fuente: FuentePrecios | None = None) -> ContextoMercado:
    """Los tipos de cambio son obligatorios (sin ellos no se puede pasar a EUR); el resto es
    opcional y, si falla, se anota en `fallos` y la métrica correspondiente sale "n/d"."""
    fuente = fuente or YahooFinance()
    fred = Fred()
    mercado = ContextoMercado()

    for divisa in sorted(set(divisas) - {"EUR"}):
        mercado.tipos_cambio[divisa] = (fred.descargar("DEXUSEU", inicio, fin) if divisa == "USD"
                                        else fuente.descargar(f"EUR{divisa}=X", inicio, fin))

    opcionales = [
        ("indice", "Índice", fuente, indice),
        ("etf_bund", "ETF de Bunds", fuente, ETF_BUND),
        ("oro", "Oro", fuente, "GC=F"),
        ("bund", "Bund 10 años", fred, "IRLTLT01DEM156N"),
        ("inflacion", "Inflación (HICP)", fred, "CP0000EZ19M086NEST"),
        ("vix", "VIX", fred, "VIXCLS"),
        ("brent", "Brent", fred, "DCOILBRENTEU"),
    ]
    for campo, nombre, origen, symbol in opcionales:
        if symbol is None:
            continue
        try:
            setattr(mercado, campo, origen.descargar(symbol, inicio, fin))
        except ErrorDescarga:
            mercado.fallos.append(nombre)
    return mercado
