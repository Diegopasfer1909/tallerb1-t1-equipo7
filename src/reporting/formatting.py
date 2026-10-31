"""Formato de números y fechas en español, compartido por la consola, los informes y los gráficos."""

import pandas as pd

UNAVAILABLE = "No disponible"
DATE_FORMAT = "%d/%m/%Y"
# Intercambia los separadores: 1,234.5 pasa a 1.234,5.
SPANISH_DIGITS = str.maketrans({",": ".", ".": ","})


def format_number(value: float, percentage: bool = False) -> str:
    if pd.isna(value):
        return UNAVAILABLE
    number = value * 100 if percentage else value
    text = f"{number:,.2f}".translate(SPANISH_DIGITS)
    return text + " %" if percentage else text


def format_points(value: float) -> str:
    """Diferencia entre dos rentabilidades, en puntos porcentuales."""
    if pd.isna(value):
        return UNAVAILABLE
    return format_number(value * 100) + " p. p."


def format_date(value) -> str:
    return f"{value:{DATE_FORMAT}}"


def format_tick(value: float, _position=None) -> str:
    """Etiqueta compacta para los ejes de los gráficos, como 10.000 o 0,5."""
    return f"{value:,.12g}".translate(SPANISH_DIGITS)
