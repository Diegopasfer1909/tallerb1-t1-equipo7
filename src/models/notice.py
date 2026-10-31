"""Avisos sobre los datos y notas de metodología, separados de las advertencias de riesgo."""

from dataclasses import dataclass
from typing import Literal

NoticeKind = Literal["data", "method"]


@dataclass(frozen=True)
class Notice:
    """data señala un problema de los datos; method, un criterio que conviene conocer."""

    message: str
    kind: NoticeKind = "data"
