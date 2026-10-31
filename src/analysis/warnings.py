"""Reglas orientativas sobre resultados, independientes de la presentación."""

from dataclasses import dataclass, fields
from typing import Literal

import pandas as pd

from ..constants import UNKNOWN
from ..errors import PortfolioError
from ..validation import is_finite_number
from .metrics import DrawdownEpisode

Severity = Literal["high", "medium"]
# Cómo leer observed y threshold: fracción de la cartera, ratio sin unidades o días.
Unit = Literal["percent", "ratio", "days"]


@dataclass(frozen=True)
class WarningThresholds:
    """Umbrales de las advertencias; todos son fracciones salvo la volatilidad, que puede
    superar 1."""

    asset_weight: float = 0.4
    sector_weight: float = 0.5
    correlation: float = 0.8
    drawdown: float = 0.3
    volatility: float = 0.25

    def __post_init__(self):
        for field in fields(self):
            value = getattr(self, field.name)
            if not is_finite_number(value):
                raise PortfolioError(f"{field.name} debe ser un número finito.")
            if value <= 0 or (field.name != "volatility" and value > 1):
                raise PortfolioError(f"Umbral fuera de rango: {field.name}.")


@dataclass(frozen=True)
class RiskWarning:
    code: str
    severity: Severity
    message: str
    observed: float
    threshold: float | None = None
    unit: Unit = "percent"
    # Activo o sector afectado, tal como lo publica el proveedor; la presentación lo traduce.
    subject: str | None = None


def evaluate_risk(
    metrics: pd.Series,
    weights: pd.Series,
    sectors: pd.Series,
    pairs: pd.Series,
    episode: DrawdownEpisode,
    thresholds: WarningThresholds,
) -> list[RiskWarning]:
    """Evalúa pesos actuales; no interpreta datos ausentes como riesgo cero."""
    warnings = []
    largest = weights.idxmax()
    if weights[largest] > thresholds.asset_weight:
        warnings.append(
            RiskWarning(
                "asset_concentration",
                "high",
                f"{largest}: una posición supera el umbral de concentración.",
                float(weights[largest]),
                thresholds.asset_weight,
                subject=largest,
            )
        )
    for sector, weight in sectors.items():
        if sector != UNKNOWN and weight > thresholds.sector_weight:
            warnings.append(
                RiskWarning(
                    "sector_concentration",
                    "medium",
                    f"Concentración sectorial: {sector}.",
                    float(weight),
                    thresholds.sector_weight,
                    subject=sector,
                )
            )
    pairs = pairs[[weights[a] > 0 and weights[b] > 0 for a, b in pairs.index]]
    if not pairs.empty and pairs.iloc[0] > thresholds.correlation:
        a, b = pairs.index[0]
        warnings.append(
            RiskWarning(
                "high_correlation",
                "medium",
                f"{a} y {b}: correlación histórica elevada.",
                float(pairs.iloc[0]),
                thresholds.correlation,
                unit="ratio",
            )
        )
    if -metrics["max_drawdown"] > thresholds.drawdown:
        warnings.append(
            RiskWarning(
                "large_drawdown",
                "high",
                "La caída máxima supera el umbral configurado.",
                -float(metrics["max_drawdown"]),
                thresholds.drawdown,
            )
        )
    if episode.peak is not None and episode.recovery is None:
        warnings.append(
            RiskWarning(
                "unrecovered_drawdown",
                "medium",
                "La mayor caída sigue sin recuperar al final del historial.",
                float(episode.underwater_days),
                unit="days",
            )
        )
    if metrics["annualized_volatility"] > thresholds.volatility:
        warnings.append(
            RiskWarning(
                "high_volatility",
                "medium",
                "La volatilidad anual supera el umbral configurado.",
                float(metrics["annualized_volatility"]),
                thresholds.volatility,
            )
        )
    return sorted(warnings, key=lambda warning: warning.severity != "high")
