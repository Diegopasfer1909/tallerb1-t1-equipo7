"""Toolkit de extracción, análisis bursátil y gestión de carteras.

    from toolkit import Cartera

    cartera = Cartera(["SAN.MC", "ITX.MC", "AAPL"], [0.4, 0.3, 0.3], rebalanceo="monthly")
    cartera.report()                                         # Markdown con todas las secciones
    cartera.plots_report()                                   # todos los gráficos
    cartera.montecarlo(n_simulaciones=10_000, horizonte=252, mostrar=True)
"""
from .analisis.advertencias import UMBRALES
from .ingesta import AlphaVantage, Fred, YahooFinance
from .modelos import Cartera, MacroSeries, PriceSeries

__all__ = ["AlphaVantage", "Cartera", "Fred", "MacroSeries", "PriceSeries", "UMBRALES", "YahooFinance"]
