"""Selección de secciones común al texto, la exportación y la API de la cartera."""

from ..errors import PortfolioError

DETAILS = ("compact", "full")
SECTION_TITLES = {
    "summary": "Resumen",
    "warnings": "Advertencias",
    "composition": "Composición de la cartera",
    "performance": "Resultados históricos",
    "diversification": "Diversificación",
    "simulation": "Simulación de Monte Carlo",
    "data": "Datos y referencias",
}
# Secciones que se muestran desplegadas incluso en el informe compacto.
ALWAYS_OPEN = ("summary", "warnings")


def select_sections(sections=None, detail="compact", *, has_simulation=False) -> tuple[str, ...]:
    """Valida la selección y la devuelve en orden de lectura; None significa todas."""
    if detail not in DETAILS:
        raise PortfolioError("detail debe ser compact o full.")
    if sections is None:
        return tuple(key for key in SECTION_TITLES if key != "simulation" or has_simulation)
    if not isinstance(sections, (list, tuple)) or not sections:
        raise PortfolioError("sections debe ser una lista no vacía de secciones.")
    if any(not isinstance(key, str) or key not in SECTION_TITLES for key in sections):
        raise PortfolioError("Secciones disponibles: " + ", ".join(SECTION_TITLES))
    return tuple(key for key in SECTION_TITLES if key in sections)
