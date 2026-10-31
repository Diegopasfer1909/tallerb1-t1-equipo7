"""Errores propios del programa, para distinguirlos de los fallos de programación."""


class PortfolioError(ValueError):
    """Datos, parámetros o configuración que impiden completar el análisis."""


class ConfigurationError(PortfolioError):
    """Falta configuración necesaria, como la clave de una API."""
