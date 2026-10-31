"""Copias de solo lectura para los datos que guardan los modelos inmutables."""

import pandas as pd


def read_only(values: pd.Series) -> pd.Series:
    """Copia cuyos valores no se pueden modificar; operar con ella devuelve datos nuevos.

    frozen=True impide reasignar atributos, pero no cambiar el contenido de una Series.
    """
    data = values.to_numpy(copy=True)
    data.flags.writeable = False
    return pd.Series(data, index=values.index.copy(), name=values.name, copy=False)
