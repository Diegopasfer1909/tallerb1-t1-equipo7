"""Copias de solo lectura para los datos que guardan los modelos inmutables."""

import pandas as pd

READ_ONLY_MESSAGE = (
    "Estos datos pertenecen a un modelo inmutable y no se pueden modificar; trabaja con una "
    "copia (.copy()) o crea otro objeto."
)
# Atributos cuyo cambio sustituiría las etiquetas, el nombre o los datos de la Series.
_PROTECTED = frozenset({"index", "name", "_mgr"})


class _ReadOnlySeries(pd.Series):
    """Series cuyo contenido, etiquetas y nombre no cambian.

    Bloquear la escritura del array no basta: añadir una etiqueta con .loc o usar inplace=True
    sustituye el array por otro. Operar con ella devuelve una Series normal, que sí se puede
    modificar.
    """

    @property
    def _constructor(self):
        return pd.Series

    def _update_inplace(self, result, **kwargs):
        raise ValueError(READ_ONLY_MESSAGE)

    def __setattr__(self, name, value):
        if name in _PROTECTED and getattr(self, "_read_only", False):
            raise ValueError(READ_ONLY_MESSAGE)
        super().__setattr__(name, value)


def read_only(values: pd.Series) -> pd.Series:
    """Copia cuyos valores, etiquetas y nombre no se pueden modificar.

    frozen=True impide reasignar atributos, pero no cambiar el contenido de una Series.
    """
    data = values.to_numpy(copy=True)
    data.flags.writeable = False
    snapshot = _ReadOnlySeries(data, index=values.index.copy(), name=values.name, copy=False)
    object.__setattr__(snapshot, "_read_only", True)
    return snapshot
