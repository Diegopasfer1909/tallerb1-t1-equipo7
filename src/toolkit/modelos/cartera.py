"""Cartera de inversión: la clase con la que trabaja el usuario.

    cartera = Cartera(["SAN.MC", "ITX.MC", "AAPL"], [0.4, 0.3, 0.3], rebalanceo="monthly")
    cartera.report()
    cartera.plots_report()
    cartera.montecarlo(n_simulaciones=10_000, horizonte=252)
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

import pandas as pd

from ..analisis import advertencias, metricas, montecarlo, preprocesado
from .mercado import ContextoMercado
from .series import SESIONES, PriceSeries

REBALANCEOS = ("monthly", None)
AÑOS_POR_DEFECTO = 5


@dataclass(eq=False)
class Cartera:
    """
    activos:      tickers de Yahoo Finance (["SAN.MC", "AAPL"]) o PriceSeries ya creadas.
    pesos:        lista en el mismo orden que `activos`, o dict {ticker: peso}. Deben sumar 1.
    rebalanceo:   "monthly" (vuelve a los pesos al cierre de cada mes) o None (comprar y mantener).
    benchmark:    índice de referencia ("^STOXX50E", "^IBEX", "^GSPC"...); None = sin benchmark.
    fecha_inicio: primera fecha de los datos, "AAAA-MM-DD" (por defecto, hace 5 años).
    fecha_fin:    última fecha de los datos, "AAAA-MM-DD" (por defecto, hoy).
    capital_inicial: euros invertidos al inicio; lo usan el report y Monte Carlo.
    fuente:       de dónde se descargan los precios: YahooFinance() por defecto, AlphaVantage()...
    nombre:       título del report.
    mercado:      contexto ya descargado; si no se da, se descarga solo.
    """
    activos: list[str | PriceSeries]
    pesos: list[float] | dict[str, float]
    rebalanceo: str | None = None
    benchmark: str | None = "^STOXX50E"
    fecha_inicio: str | None = None
    fecha_fin: str | None = None
    capital_inicial: float = 10_000
    fuente: object | None = field(default=None, repr=False)
    nombre: str = "Cartera"
    mercado: ContextoMercado | None = field(default=None, repr=False)

    # Calculados al instanciar
    precios: pd.DataFrame = field(init=False, repr=False)     # en EUR, alineados y limpios
    r: pd.DataFrame = field(init=False, repr=False)           # rentabilidades diarias de cada activo
    rp: pd.Series = field(init=False, repr=False)             # rentabilidades diarias de la cartera
    valor: pd.Series = field(init=False, repr=False)          # valor de 1 € invertido al inicio
    rm: pd.Series | None = field(init=False, repr=False)      # rentabilidades diarias del índice
    rf: pd.Series = field(init=False, repr=False)             # tipo libre de riesgo diario (Bund)
    rf_anual: float = field(init=False, repr=False)
    pesos_actuales: pd.Series = field(init=False, repr=False)
    simulacion: montecarlo.ResultadoMC | None = field(init=False, default=None, repr=False)

    def __post_init__(self) -> None:
        if isinstance(self.rebalanceo, str) and self.rebalanceo.lower() == "none":
            self.rebalanceo = None
        if self.rebalanceo not in REBALANCEOS:
            raise ValueError('rebalanceo debe ser "monthly" o None.')
        try:
            desde = pd.Timestamp(self.fecha_inicio) if self.fecha_inicio else None
            hasta = pd.Timestamp(self.fecha_fin) if self.fecha_fin else None
        except ValueError as error:
            raise ValueError(f'Fecha no válida ({error}); usa el formato "AAAA-MM-DD".') from error
        if desde and hasta and desde >= hasta:
            raise ValueError("fecha_inicio debe ser anterior a fecha_fin.")
        if not isinstance(self.capital_inicial, (int, float)) or self.capital_inicial <= 0:
            raise ValueError("capital_inicial debe ser un número positivo.")
        if isinstance(self.activos, (str, PriceSeries)):
            self.activos = [self.activos]

        self.activos = preprocesado.validar_activos(self._obtener_series())
        symbols = [a.symbol for a in self.activos]
        self.pesos = preprocesado.validar_pesos(self.pesos, symbols)
        if self.mercado is None:
            self.mercado = self._descargar_mercado()

        en_eur = {a.symbol: self._a_eur(a).datos for a in self.activos}
        self.precios, self.limpieza = preprocesado.alinear(en_eur)
        if len(self.precios) <= preprocesado.MIN_SESIONES:
            raise ValueError(f"Solo hay {len(self.precios)} sesiones comunes (mínimo {preprocesado.MIN_SESIONES}).")

        # Base común de cálculo (mismos nombres que la guía del report).
        posiciones = metricas.evolucion_cartera(self.precios, self.pesos, self.rebalanceo)
        self.valor = posiciones.sum(axis=1)
        self.pesos_actuales = posiciones.iloc[-1] / self.valor.iloc[-1]
        self.r = self.precios.pct_change().dropna()
        self.rp = self.valor.pct_change().dropna()

        indice = self.mercado.indice
        self.indice_precios = self.alinear_externa(indice.datos) if indice is not None else None
        self.rm = self.indice_precios.pct_change().reindex(self.rp.index) if indice is not None else None

        if self.mercado.bund is not None:
            bund = self.mercado.bund.en_tanto_por_uno()
            self.rf = ((1 + bund) ** (1 / SESIONES) - 1).reindex(self.rp.index, method="ffill").fillna(0)
            rf_anual = bund.loc[self.rp.index[0]:self.rp.index[-1]].mean()
            self.rf_anual = rf_anual if pd.notna(rf_anual) else bund.loc[:self.rp.index[-1]].iloc[-1]
        else:   # sin Bund, el tipo libre de riesgo es 0 y se avisa en la sección de calidad
            self.rf = pd.Series(0.0, index=self.rp.index)
            self.rf_anual = 0.0
            self.mercado.fallos.append("Bund (tipo libre de riesgo = 0)")

    # ------------------------------------------------------------------ obtención de datos

    def _obtener_series(self) -> list[PriceSeries]:
        tickers = [a for a in self.activos if isinstance(a, str)]
        descargadas = {}
        if tickers:
            from ..ingesta import YahooFinance   # solo se toca la capa de ingesta si hay que descargar

            inicio = self.fecha_inicio or (pd.Timestamp.today() - pd.DateOffset(years=AÑOS_POR_DEFECTO)).strftime("%Y-%m-%d")
            descargadas = (self.fuente or YahooFinance()).descargar_varios(tickers, inicio, self.fecha_fin)

        series = []
        for activo in self.activos:
            if isinstance(activo, str):
                series.append(descargadas[activo])
            elif self.fecha_inicio or self.fecha_fin:
                series.append(dataclasses.replace(activo, datos=activo.datos.loc[self.fecha_inicio:self.fecha_fin]))
            else:
                series.append(activo)
        return series

    def _descargar_mercado(self) -> ContextoMercado:
        from ..ingesta import descargar_contexto

        inicio = min(a.inicio for a in self.activos).strftime("%Y-%m-%d")
        return descargar_contexto(inicio, self.fecha_fin, divisas={a.divisa for a in self.activos},
                                  indice=self.benchmark, fuente=self.fuente)

    def _a_eur(self, activo: PriceSeries) -> PriceSeries:
        if activo.divisa == "EUR":
            return activo
        cambio = self.mercado.tipos_cambio.get(activo.divisa)
        if cambio is None:
            raise ValueError(f"{activo.symbol} cotiza en {activo.divisa} y falta el tipo de cambio EUR/{activo.divisa}.")
        return activo.convertir(cambio, "EUR")

    def alinear_externa(self, serie: pd.Series) -> pd.Series:
        """Lleva una serie externa a las fechas de la cartera con el último dato conocido."""
        return serie.reindex(self.precios.index, method="ffill")

    @property
    def info(self) -> dict[str, dict]:
        return {a.symbol: {"nombre": a.nombre, "sector": a.sector, "divisa": a.divisa, "pais": a.pais}
                for a in self.activos}

    @property
    def nombre_indice(self) -> str:
        return self.mercado.indice.nombre if self.mercado.indice is not None else "Índice"

    # ------------------------------------------------------------------ métricas por sección

    @cached_property
    def composicion(self) -> pd.DataFrame:
        return metricas.composicion(self.r, self.pesos, self.pesos_actuales, self.info)

    @cached_property
    def rentabilidad(self) -> dict:
        hicp = self.mercado.inflacion.datos if self.mercado.inflacion is not None else None
        return metricas.rentabilidad(self.rp, self.valor, self.rm, self.rf_anual, hicp)

    @cached_property
    def riesgo(self) -> dict:
        return metricas.riesgo(self.rp, self.valor, self.rm)

    @cached_property
    def ajustada(self) -> dict:
        return metricas.ajustada(self.rp, self.rm, self.rf, self.rf_anual)

    @cached_property
    def diversificacion(self) -> dict:
        sector = pd.Series({a.symbol: a.sector for a in self.activos})
        divisa = pd.Series({a.symbol: a.divisa for a in self.activos})
        return metricas.diversificacion(self.r, self.pesos, sector, divisa)

    @cached_property
    def contexto(self) -> dict:
        m = self.mercado
        externas = {"brent": m.brent, "oro": m.oro, "etf_bund": m.etf_bund}
        rent = {k: self.alinear_externa(s.datos).pct_change().reindex(self.rp.index)
                for k, s in externas.items() if s is not None}
        salida = metricas.mercado(self.rp, m.vix.datos if m.vix is not None else None, rent)
        desde, hasta = self.precios.index[0], self.precios.index[-1]
        salida["efecto_divisa"] = pd.Series({
            a.symbol: metricas.efecto_divisa(a.datos.loc[desde:hasta], self.precios[a.symbol])
            for a in self.activos if a.divisa != "EUR"}, dtype=float)
        return salida

    @cached_property
    def calidad(self) -> dict:
        fuentes = {a.symbol: f"{a.source} ({a.symbol})" for a in self.activos}
        fuentes.update({k: f"{s.source} ({s.symbol})" for k, s in self.mercado.series().items()})
        sin_ajustar = [a.symbol for a in self.activos if not a.ajustado]
        return metricas.calidad(self.limpieza, self.rp, fuentes, self.mercado.fallos, sin_ajustar)

    def advertencias(self, umbrales: dict | None = None) -> list[dict]:
        """Advertencias activas, de mayor a menor nivel. `umbrales`: ver toolkit.UMBRALES."""
        m = {"composicion": self.composicion, "rentabilidad": self.rentabilidad, "riesgo": self.riesgo,
             "ajustada": self.ajustada, "diversificacion": self.diversificacion, "mercado": self.contexto,
             "calidad": self.calidad}
        if self.simulacion is not None:
            m["montecarlo"] = self.simulacion.metricas
        return advertencias.evaluar(m, umbrales)

    # ------------------------------------------------------------------ métodos del usuario

    def montecarlo(self, n_simulaciones: int = 10_000, horizonte: int = SESIONES,
                   retorno: float | dict | None = None, volatilidad: float | dict | None = None, *,
                   activo: str | None = None, por_activos: bool = False, confianza: float = 0.95, semilla: int | None = 42,
                   mostrar: bool = False) -> montecarlo.ResultadoMC:
        """Simulación de Monte Carlo (movimiento browniano geométrico).

        n_simulaciones: número de trayectorias.
        horizonte:      sesiones a simular (252 ≈ 1 año).
        retorno:        rentabilidad anual supuesta; None = la histórica.
        volatilidad:    volatilidad anual supuesta; None = la histórica.
        activo:         ticker para simular un solo activo en lugar de la cartera.
        por_activos:    simula cada activo con sus correlaciones (Cholesky) y respeta el rebalanceo;
                        retorno/volatilidad pueden ser entonces un dict por ticker.
        confianza:      nivel del VaR y de los percentiles extremos.
        semilla:        para reproducir el resultado (None = aleatorio).
        mostrar:        dibuja las trayectorias y la distribución final al terminar.

        Parte del capital_inicial de la cartera. El resultado de la cartera se guarda en
        `cartera.simulacion` y aparece en el report.
        """
        opciones = dict(n_simulaciones=n_simulaciones, horizonte=horizonte, capital=self.capital_inicial,
                        retorno=retorno, volatilidad=volatilidad, confianza=confianza, semilla=semilla)
        if activo is not None:
            if activo not in self.r:
                raise ValueError(f"{activo} no está en la cartera ({', '.join(self.r.columns)}).")
            resultado = montecarlo.simular(self.r[activo], **opciones)
        elif por_activos:
            resultado = self.simulacion = montecarlo.simular(self.r, self.pesos, rebalanceo=self.rebalanceo,
                                                             **opciones)
        else:
            resultado = self.simulacion = montecarlo.simular(self.rp.rename(self.nombre), **opciones)
        if mostrar:
            resultado.plot()
        return resultado

    def report(self, secciones: list[str] | None = None, *, umbrales: dict | None = None, graficos: bool = True, ruta: str | Path | None = "informe"):
        """Report en Markdown con métricas, diagnósticos, advertencias de riesgo y gráficos.
        Cada sección es un desplegable. Se guarda automáticamente en <ruta>/report.md y
        además se devuelve como texto.

        secciones: cuáles incluir (por defecto, todas): resumen, advertencias, composicion,
                   rentabilidad, riesgo, ajustada, diversificacion, mercado, montecarlo, calidad.
        umbrales:  cambia los umbrales de las advertencias, p. ej. {"peso_alto": 0.5}.
        graficos:  incluye los gráficos de cada sección (se guardan en <ruta>/graficos/).
        ruta:      carpeta donde se guarda (por defecto "informe", relativa a la carpeta
                   desde la que se ejecuta Python); None = no guardar.
        """
        from ..salida.report import generar

        return generar(self, secciones, umbrales=umbrales, graficos=graficos, ruta=ruta)

    def plots_report(self, graficos: list[str] | None = None, *, ruta: str | Path | None = "informe",
                     mostrar: bool = False):
        """Report de gráficos en Markdown, aparte del report de métricas. Cada gráfico es un
        desplegable. Se guarda automáticamente en <ruta>/graficos.md (imágenes en <ruta>/graficos/).

        graficos: cuáles (por defecto, todos): evolucion, drawdown, correlaciones,
                  riesgo_rentabilidad, pesos_contribucion, rentabilidad_anual, distribucion,
                  volatilidad_vix, correlacion_bund, exposicion, montecarlo.
        ruta:     carpeta donde se guarda (por defecto "informe"); None = no guardar.
        mostrar:  además, abrirlos en ventanas.
        """
        from ..salida.report import generar_graficos

        return generar_graficos(self, graficos, ruta=ruta, mostrar=mostrar)
