"""Períodos por año con los que se anualizan las métricas y se simula, según las fechas."""

import pandas as pd

from .constants import CALENDAR_PERIODS_PER_YEAR, PERIODS_PER_YEAR

# Con cotización todos los días, 2 de cada 7 fechas caen en fin de semana; con sesiones
# bursátiles, ninguna.
MIN_WEEKEND_SHARE = 0.2


def periods_per_year(dates: pd.DatetimeIndex) -> int:
    """365 si los datos son diarios e incluyen los fines de semana; 252 en otro caso.

    Solo una cartera de criptomonedas cotiza en fin de semana: si mezcla acciones, las fechas
    comunes son sesiones bursátiles.
    """
    if len(dates) < 2:
        return PERIODS_PER_YEAR
    daily = pd.Series(dates).diff().dt.days.median() == 1
    weekends = (dates.day_of_week >= 5).mean()
    if daily and weekends >= MIN_WEEKEND_SHARE:
        return CALENDAR_PERIODS_PER_YEAR
    return PERIODS_PER_YEAR
