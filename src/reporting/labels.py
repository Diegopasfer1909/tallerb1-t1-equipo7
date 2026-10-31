"""Etiquetas en español compartidas por la consola y los informes."""

ASSET_TYPES = {
    "stock": "Acción",
    "fund": "Fondo de inversión",
    "etf": "Fondo cotizado (ETF)",
    "index": "Índice",
    "unknown": "No disponible",
}
SECTORS = {
    "Technology": "Tecnología",
    "Financial Services": "Servicios financieros",
    "Financials": "Finanzas",
    "Healthcare": "Salud",
    "Health Care": "Salud",
    "Consumer Cyclical": "Consumo cíclico",
    "Consumer Defensive": "Consumo defensivo",
    "Consumer Discretionary": "Consumo discrecional",
    "Consumer Staples": "Productos de primera necesidad",
    "Communication Services": "Servicios de comunicación",
    "Industrials": "Industria",
    "Energy": "Energía",
    "Utilities": "Servicios públicos",
    "Real Estate": "Sector inmobiliario",
    "Basic Materials": "Materias primas",
    "Materials": "Materiales",
    "Unknown": "No disponible",
}
COUNTRIES = {
    "United States": "Estados Unidos",
    "USA": "Estados Unidos",
    "Spain": "España",
    "United Kingdom": "Reino Unido",
    "Germany": "Alemania",
    "France": "Francia",
    "Italy": "Italia",
    "Portugal": "Portugal",
    "Netherlands": "Países Bajos",
    "Switzerland": "Suiza",
    "Japan": "Japón",
    "China": "China",
    "Canada": "Canadá",
    "Australia": "Australia",
    "Ireland": "Irlanda",
    "Unknown": "No disponible",
}
SOURCES = {
    "yahoo": "Yahoo Finance",
    "alpha_vantage": "Alpha Vantage",
    "fred": "FRED",
}
PRICE_BASES = {
    "unadjusted": "Sin ajustar, según el proveedor",
    "split_adjusted": "Ajustado por desdoblamientos; sin ajuste por dividendos",
    "adjusted": "Ajustado por desdoblamientos y distribuciones",
    "unknown": "No consta",
    "adjusted_growth": "Crecimiento con cierre ajustado por desdoblamientos y distribuciones",
}
SEVERITIES = {"high": "Alta", "medium": "Media"}

# Columnas de Portfolio.holdings() en el orden en que se presentan.
HOLDINGS_COLUMNS = {
    "target_weight": "Peso objetivo",
    "price": "Precio de cierre",
    "value": "Valor hipotético",
    "weight": "Peso actual",
}
WEIGHT_COLUMNS = ("target_weight", "weight")
# Resultados de SimulationResult.summary() que son rentabilidades o probabilidades.
PERCENT_RESULTS = ("mean_return", "probability_of_loss")


def simulation_labels(confidence: float) -> dict[str, str]:
    """Nombre de cada resultado de SimulationResult.summary()."""
    return {
        "initial_value": "Valor inicial",
        "mean_final_value": "Valor final medio",
        "median_final_value": "Mediana del valor final",
        "lower_percentile": f"Percentil {100 * (1 - confidence):g} del valor final",
        "upper_percentile": f"Percentil {100 * confidence:g} del valor final",
        "mean_return": "Rentabilidad media simulada",
        "probability_of_loss": "Probabilidad estimada de pérdida",
        "value_at_risk": f"VaR al {confidence * 100:g} % al final del horizonte",
        "conditional_value_at_risk": f"CVaR al {confidence * 100:g} % al final del horizonte",
    }
