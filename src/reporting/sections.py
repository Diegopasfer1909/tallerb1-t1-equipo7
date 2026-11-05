"""Secciones disponibles en los informes y validación de la selección."""

from ..errors import PortfolioError

DETAILS = ("compact", "full")
SECTION_TITLES = {
    "summary": "Resumen",
    "warnings": "Advertencias",
    "composition": "Composición",
    "returns": "Rentabilidad",
    "risk": "Riesgo",
    "risk_adjusted": "Rentabilidad ajustada al riesgo",
    "diversification": "Diversificación",
    "market": "Contexto de mercado",
    "simulation": "Monte Carlo",
    "data": "Calidad de los datos",
}
SECTION_QUESTIONS = {
    "summary": "¿Cómo ha ido, en cinco cifras?",
    "warnings": "¿Qué hay que vigilar?",
    "composition": "¿Qué contiene la cartera?",
    "returns": "¿Cuánto ha ganado?",
    "risk": "¿Cuánto ha arriesgado?",
    "risk_adjusted": "¿Ha compensado el riesgo?",
    "diversification": "¿Está bien repartida?",
    "market": "¿Qué pasa fuera de la cartera que le afecte?",
    "simulation": "¿Qué puede pasar a futuro?",
    "data": "¿Cuánto fiarse de todo lo anterior?",
}


def select_sections(sections=None, detail="compact") -> tuple[str, ...]:
    """Valida la selección y la devuelve en orden de lectura; None significa todas."""
    if detail not in DETAILS:
        raise PortfolioError("detail debe ser compact o full.")
    if sections is None:
        return tuple(SECTION_TITLES)
    if not isinstance(sections, (list, tuple)) or not sections:
        raise PortfolioError("sections debe ser una lista no vacía de secciones.")
    if any(not isinstance(key, str) or key not in SECTION_TITLES for key in sections):
        raise PortfolioError("Secciones disponibles: " + ", ".join(SECTION_TITLES))
    return tuple(key for key in SECTION_TITLES if key in sections)
