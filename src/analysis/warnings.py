"""Reglas orientativas sobre resultados, independientes de la presentación."""

from dataclasses import dataclass, fields
from typing import Literal

import pandas as pd

from ..constants import PERIODS_PER_YEAR, UNKNOWN
from ..errors import PortfolioError
from ..validation import is_finite_number
from .metrics import DrawdownEpisode

Severity = Literal["high", "medium"]
# Cómo leer observed y threshold: fracción de la cartera, ratio sin unidades, días o sesiones.
Unit = Literal["percent", "ratio", "days", "sessions"]
# Umbrales que no son fracciones y pueden superar 1.
UNBOUNDED = ("volatility", "vix", "short_history")


@dataclass(frozen=True)
class WarningThresholds:
    """Umbrales de las advertencias; todos son fracciones salvo los de UNBOUNDED."""

    asset_weight: float = 0.4
    asset_weight_medium: float = 0.25
    sector_weight: float = 0.5
    correlation: float = 0.8
    mean_correlation: float = 0.6
    premium: float = 0.02
    drawdown: float = 0.3
    volatility: float = 0.25
    vix: float = 30
    short_history: int = PERIODS_PER_YEAR
    excluded_dates: float = 0.05
    # A un año, una cartera de bolsa pierde en cerca del 40 % de los escenarios: es lo normal.
    simulation_loss: float = 0.45

    def __post_init__(self):
        for field in fields(self):
            value = getattr(self, field.name)
            if not is_finite_number(value):
                raise PortfolioError(f"{field.name} debe ser un número finito.")
            if value <= 0 or (field.name not in UNBOUNDED and value > 1):
                raise PortfolioError(f"Umbral fuera de rango: {field.name}.")


@dataclass(frozen=True)
class RiskWarning:
    code: str
    severity: Severity
    message: str
    observed: float
    threshold: float | None = None
    unit: Unit = "percent"
    title: str = ""


def evaluate_risk(
    metrics: pd.Series,
    weights: pd.Series,
    sectors: pd.Series,
    pairs: pd.Series,
    episode: DrawdownEpisode,
    thresholds: WarningThresholds,
    *,
    currencies: pd.Series | None = None,
    excluded_dates: pd.Series | None = None,
    vix: float = float("nan"),
) -> list[RiskWarning]:
    """Evalúa pesos actuales; no interpreta datos ausentes como riesgo cero.

    Una comparación con NaN nunca se cumple, de modo que un dato ausente no activa ninguna regla.
    """
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
                title="Concentración en un activo",
            )
        )
    elif weights[largest] > thresholds.asset_weight_medium:
        warnings.append(
            RiskWarning(
                "asset_concentration",
                "medium",
                f"{largest}: una posición supera el umbral de concentración moderada.",
                float(weights[largest]),
                thresholds.asset_weight_medium,
                title="Concentración en un activo",
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
                    title="Concentración sectorial",
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
                title="Activos redundantes",
            )
        )
    if metrics.get("correlation_mean", float("nan")) > thresholds.mean_correlation:
        warnings.append(
            RiskWarning(
                "low_diversification",
                "medium",
                "La correlación media entre activos es elevada.",
                float(metrics["correlation_mean"]),
                thresholds.mean_correlation,
                unit="ratio",
                title="Poca diversificación",
            )
        )
    sharpe = metrics.get("sharpe", float("nan"))
    premium = metrics.get("excess_annualized_return", float("nan"))
    if sharpe < 0:
        warnings.append(
            RiskWarning(
                "uncompensated_risk",
                "high",
                "El tipo libre de riesgo habría rendido más por unidad de riesgo.",
                float(sharpe),
                unit="ratio",
                title="Riesgo no compensado",
            )
        )
    elif sharpe >= 0 and premium < thresholds.premium:
        warnings.append(
            RiskWarning(
                "low_premium",
                "medium",
                "La prima anual frente al tipo libre de riesgo es reducida.",
                float(premium),
                thresholds.premium,
                title="Riesgo no compensado",
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
                title="Caída máxima elevada",
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
                title="Caída sin recuperar",
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
                title="Volatilidad elevada",
            )
        )
    if metrics.get("real_annualized_return", float("nan")) < 0:
        warnings.append(
            RiskWarning(
                "inflation_loss",
                "medium",
                "La rentabilidad anual real es negativa.",
                float(metrics["real_annualized_return"]),
                title="Pérdida frente a la inflación",
            )
        )
    if currencies is not None and len(currencies) > 1:
        warnings.append(
            RiskWarning(
                "currency_risk",
                "medium",
                "Cartera repartida en varias divisas ("
                + ", ".join(currencies.index)
                + "); principal:",
                float(currencies.max()),
                title="Riesgo de divisa",
            )
        )
    if vix > thresholds.vix:
        warnings.append(
            RiskWarning(
                "market_stress",
                "medium",
                "VIX elevado: el riesgo histórico probablemente se queda corto.",
                float(vix),
                thresholds.vix,
                unit="ratio",
                title="Mercado en estrés",
            )
        )
    sessions = metrics.get("sessions", float("nan"))
    if sessions < thresholds.short_history:
        warnings.append(
            RiskWarning(
                "short_history",
                "high",
                "Pocas sesiones comunes para estimar métricas anuales.",
                float(sessions),
                float(thresholds.short_history),
                unit="sessions",
                title="Historia corta",
            )
        )
    if excluded_dates is not None and not excluded_dates.empty:
        worst = excluded_dates.idxmax()
        if excluded_dates[worst] > thresholds.excluded_dates:
            warnings.append(
                RiskWarning(
                    "unreliable_data",
                    "medium",
                    f"{worst}: fechas descartadas por no coincidir con el resto de activos.",
                    float(excluded_dates[worst]),
                    thresholds.excluded_dates,
                    title="Datos poco fiables",
                )
            )
    return sorted(warnings, key=lambda warning: warning.severity != "high")


def evaluate_simulation(
    probability_of_loss: float, thresholds: WarningThresholds
) -> list[RiskWarning]:
    """Regla aparte: la simulación es opcional y no forma parte del análisis histórico."""
    if not probability_of_loss > thresholds.simulation_loss:
        return []
    return [
        RiskWarning(
            "simulation_loss",
            "medium",
            "Se pierde dinero en una parte elevada de los escenarios simulados.",
            float(probability_of_loss),
            thresholds.simulation_loss,
            title="Escenarios desfavorables",
        )
    ]
