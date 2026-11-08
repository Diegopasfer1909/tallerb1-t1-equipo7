"""Errores propios del programa, para distinguirlos de los fallos de programación."""


class PortfolioError(ValueError):
    """Datos, parámetros o configuración que impiden completar el análisis."""


class ConfigurationError(PortfolioError):
    """Falta configuración necesaria, como la clave de una API."""


class ProviderError(RuntimeError):
    """Fallo de consulta, acceso denegado o respuesta inesperada de una fuente externa.

    Pertenece al núcleo porque forma parte del contrato de los puertos: la carga lo trata sin
    conocer qué adaptador lo ha producido.
    """


class DataCoverageError(ProviderError):
    """Los datos disponibles no cubren el intervalo solicitado."""
