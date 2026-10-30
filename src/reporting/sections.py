"""Selección común al texto, la exportación y la API de la cartera."""

SECTION_TITLES = {
    "summary": "Resumen",
    "warnings": "Advertencias",
    "composition": "Composición de la cartera",
    "performance": "Resultados históricos",
    "diversification": "Diversificación",
    "simulation": "Simulación de Monte Carlo",
    "data": "Datos y referencias",
}

SECTION_CHARTS = {
    "performance": ("portfolio", "assets", "risk_return"),
    "diversification": ("distribution",),
    "simulation": ("simulation",),
}


def select_sections(sections=None, detail="compact", *, has_simulation=False):
    if detail not in ("compact", "full"):
        raise ValueError("detail debe ser compact o full.")
    if sections is None:
        return tuple(key for key in SECTION_TITLES if key != "simulation" or has_simulation)
    if not isinstance(sections, (list, tuple)) or not sections:
        raise ValueError("sections debe ser una lista no vacía de secciones.")
    if any(not isinstance(key, str) or key not in SECTION_TITLES for key in sections):
        raise ValueError("Secciones disponibles: " + ", ".join(SECTION_TITLES))
    return tuple(key for key in SECTION_TITLES if key in sections)


def chart_keys(sections):
    return {key for section in sections for key in SECTION_CHARTS.get(section, ())}
