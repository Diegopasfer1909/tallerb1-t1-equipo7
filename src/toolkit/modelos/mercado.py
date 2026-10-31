"""DataClass con lo que rodea a la cartera: índice de referencia, tipo libre de riesgo,
inflación, materias primas y tipos de cambio. Todo es opcional: la cartera calcula lo que
puede con lo que haya."""
from dataclasses import dataclass, field

from .series import MacroSeries, PriceSeries, Serie


@dataclass(eq=False)
class ContextoMercado:
    indice: PriceSeries | None = None
    bund: MacroSeries | None = None          # rentabilidad del Bund a 10 años
    inflacion: MacroSeries | None = None     # índice HICP
    vix: MacroSeries | None = None
    brent: Serie | None = None
    oro: Serie | None = None
    etf_bund: PriceSeries | None = None
    tipos_cambio: dict[str, Serie] = field(default_factory=dict)   # divisa → unidades por 1 EUR
    fallos: list[str] = field(default_factory=list)                # fuentes que no se pudieron bajar

    def series(self) -> dict[str, Serie]:
        nombres = {"Índice": self.indice, "Bund 10 años": self.bund, "Inflación (HICP)": self.inflacion,
                   "VIX": self.vix, "Brent": self.brent, "Oro": self.oro, "ETF de Bunds": self.etf_bund}
        nombres.update({f"EUR/{d}": s for d, s in self.tipos_cambio.items()})
        return {k: s for k, s in nombres.items() if s is not None}
