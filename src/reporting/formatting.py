"""Formato de números compartido por la consola y los informes."""

import pandas as pd


def format_number(value: float, percentage: bool = False) -> str:
    if pd.isna(value):
        return "No disponible"
    number = value * 100 if percentage else value
    text = f"{number:,.2f}".translate(str.maketrans({",": ".", ".": ","}))
    return text + " %" if percentage else text
