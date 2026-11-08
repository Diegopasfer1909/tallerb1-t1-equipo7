"""Etiquetas en español compartidas por la consola y los informes."""

from ..constants import AAA_3M_YIELD

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
    "ecb": "BCE",
}
PRICE_BASES = {
    "unadjusted": "Sin ajustar, según el proveedor",
    "split_adjusted": "Ajustado por desdoblamientos; sin ajuste por dividendos",
    "adjusted": "Ajustado por desdoblamientos y distribuciones",
    "unknown": "No consta",
    "adjusted_growth": "Crecimiento con cierre ajustado por desdoblamientos y distribuciones",
}
SEVERITIES = {"high": "🔴 **Alta**", "medium": "🟠 **Media**"}
# Nombre legible de los tipos libres de riesgo predeterminados.
RISK_FREE_NAMES = {
    AAA_3M_YIELD: "deuda AAA de la zona euro a 3 meses",
    "DGS3MO": "letra de EE. UU. a 3 meses",
}

# Texto alternativo de cada gráfico del informe, con las claves de CHARTS.
CHART_TITLES = {
    "exposure": "Exposición de la cartera por sector y por divisa",
    "evolution": "Evolución de la cartera frente al índice y al ETF de Bunds",
    "assets": "Evolución comparada de los activos",
    "annual_returns": "Rentabilidad de cada año, cartera frente al índice",
    "drawdown": "Caídas de la cartera desde sus máximos",
    "distribution": "Rentabilidades diarias frente a una distribución normal",
    "risk_return": "Riesgo y rentabilidad de los activos, la cartera y el índice",
    "correlations": "Correlaciones entre las rentabilidades de los activos",
    "risk_shares": "Peso de cada activo frente a su contribución al riesgo",
    "volatility_vix": "Volatilidad de la cartera frente al VIX",
    "bund_correlation": "Correlación móvil de la cartera con el ETF de Bunds",
    "simulation": "Trayectorias simuladas y distribución del valor final",
}
# Casos con los que se contrasta el retorno de la simulación.
SENSITIVITY_CASES = {
    "historical": "Histórico puro",
    "risk_free": "Solo tipo libre de riesgo",
    "prudent": "8 % en todos los activos",
    "zero": "0 % en todos los activos",
}
# Columnas de Portfolio.holdings() en el orden en que se presentan.
HOLDINGS_COLUMNS = {
    "target_weight": "Peso objetivo",
    "price": "Precio de cierre",
    "value": "Valor hipotético",
    "weight": "Peso actual",
}
# Con una cartera definida por número de acciones, los pesos de partida no son un objetivo
# y el valor no es hipotético: es el de esas acciones. Con Adj Close, el valor incluye los
# dividendos reinvertidos y el valor de mercado, acciones por precio, se muestra aparte.
SHARES_HOLDINGS_COLUMNS = {
    "shares": "Acciones",
    "target_weight": "Peso inicial",
    "price": "Precio de cierre",
    "market_value": "Valor de mercado",
    "value": "Valor",
    "weight": "Peso actual",
}
DIVIDEND_VALUE_LABEL = "Valor con dividendos"
# Precios con los que se valora la cartera, como los entiende quien lee el informe.
PRICE_COLUMN_LABELS = {
    "Close": "cierre sin ajustar por dividendos",
    "Adj Close": "ajustados por dividendos",
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
