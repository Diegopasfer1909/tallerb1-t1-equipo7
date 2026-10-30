"""Reglas orientativas sobre resultados, independientes de la presentación."""

from dataclasses import dataclass, fields
from numbers import Real

import numpy as np


@dataclass(frozen=True)
class WarningThresholds:
    sector_weight: float = 0.5
    correlation: float = 0.8
    drawdown: float = 0.3
    volatility: float = 0.25

    def __post_init__(self):
        for field in fields(self):
            value = getattr(self, field.name)
            if isinstance(value, bool) or not isinstance(value, Real) or not np.isfinite(value):
                raise ValueError(f"{field.name} debe ser un número finito.")
            if value <= 0 or (field.name != "volatility" and value > 1):
                raise ValueError(f"Umbral fuera de rango: {field.name}.")


@dataclass(frozen=True)
class RiskWarning:
    code: str
    severity: str
    message: str
    observed: float
    threshold: float | None = None


def evaluate_risk(metrics, weights, sectors, pairs, episode, concentration_limit, thresholds):
    """Evalúa pesos actuales; no interpreta datos ausentes como riesgo cero."""
    warnings = []
    largest = weights.idxmax()
    if weights[largest] > concentration_limit:
        warnings.append(
            RiskWarning(
                "asset_concentration",
                "high",
                f"{largest}: una posición supera el umbral de concentración.",
                float(weights[largest]),
                concentration_limit,
            )
        )
    for sector, weight in sectors.items():
        if sector != "Unknown" and weight > thresholds.sector_weight:
            warnings.append(
                RiskWarning(
                    "sector_concentration",
                    "medium",
                    f"Concentración sectorial: {sector}.",
                    float(weight),
                    thresholds.sector_weight,
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
