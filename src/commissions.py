"""Comisiones de los brókers y regla que decide si un rebalanceo compensa sus costes.

Las tarifas de BROKER_PRESETS se consultaron en noviembre de 2026 en las webs de los brókers y
en comparadores españoles; cambian con frecuencia, así que conviene comprobar la tarifa vigente
y ajustarla con las opciones --commission-* si es necesario.
"""

from dataclasses import dataclass, field

import numpy as np

from .errors import PortfolioError
from .validation import is_finite_number

# Una orden menor que esta fracción del valor de la cartera se trata como inexistente: evita
# cobrar la comisión mínima por diferencias de redondeo.
ORDER_TOLERANCE = 1e-9


@dataclass(frozen=True)
class CommissionSchedule:
    """Tarifa por orden: fixed + rate × importe, entre minimum y maximum.

    rate es una fracción del importe (0.0005 = 0,05 %). fixed, minimum y maximum se expresan en
    la divisa de la cartera. Una orden de importe cero no paga comisión.
    """

    rate: float = 0.0
    fixed: float = 0.0
    minimum: float = 0.0
    maximum: float | None = None
    name: str = "Sin comisiones"

    def __post_init__(self) -> None:
        if not is_finite_number(self.rate) or not 0 <= self.rate < 1:
            raise PortfolioError("La comisión porcentual debe estar entre 0 y 1.")
        for label, value in (("fija", self.fixed), ("mínima", self.minimum)):
            if not is_finite_number(value) or value < 0:
                raise PortfolioError(f"La comisión {label} debe ser un número no negativo.")
        if self.maximum is not None and (
            not is_finite_number(self.maximum) or self.maximum < max(self.minimum, self.fixed)
        ):
            raise PortfolioError(
                "La comisión máxima debe ser un número no menor que la mínima ni que la fija."
            )

    @property
    def is_free(self) -> bool:
        return self.rate == 0 and self.fixed == 0 and self.minimum == 0

    def cost(self, amounts) -> np.ndarray:
        """Comisión de cada orden; el signo del importe (compra o venta) no importa."""
        size = np.abs(np.asarray(amounts, dtype=float))
        fee = np.maximum(self.fixed + self.rate * size, self.minimum)
        if self.maximum is not None:
            fee = np.minimum(fee, self.maximum)
        return np.where(size > 0, fee, 0.0)


# Tarifas por orden de acciones y ETF para un inversor en España (noviembre de 2026).
BROKER_PRESETS: dict[str, CommissionSchedule] = {
    # Plan fijo en bolsas europeas: 0,05 % del importe, mínimo 3 €.
    "ibkr": CommissionSchedule(rate=0.0005, minimum=3.0, name="Interactive Brokers"),
    # 1 € de comisión más 1 € de costes de tramitación por orden.
    "degiro": CommissionSchedule(fixed=2.0, name="DEGIRO"),
    # 1 € de costes externos por orden.
    "trade_republic": CommissionSchedule(fixed=1.0, name="Trade Republic"),
    # Sin comisión hasta 100.000 € de volumen mensual.
    "xtb": CommissionSchedule(name="XTB"),
    "none": CommissionSchedule(),
}
DEFAULT_BROKER = "ibkr"
# Valores por defecto de la consola: reajustar solo si un peso se desvía más de 5 puntos y no
# enviar órdenes cuya comisión supere el 1 % de su importe.
DEFAULT_REBALANCE_BAND = 0.05
DEFAULT_MAX_ORDER_COST = 0.01


@dataclass(frozen=True)
class RebalanceRule:
    """Cuándo y cómo se rebalancea, y cuánto cuesta.

    band es la desviación máxima de cualquier peso respecto a su objetivo (0.05 = 5 puntos)
    antes de reajustar; con 0 se reajusta siempre. max_order_cost descarta las órdenes cuya
    comisión supere esa fracción de su importe; None no descarta ninguna. Los valores por
    defecto reproducen un rebalanceo sin costes que siempre vuelve a los pesos objetivo.
    """

    commissions: CommissionSchedule = field(default_factory=CommissionSchedule)
    band: float = 0.0
    max_order_cost: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.commissions, CommissionSchedule):
            raise TypeError("commissions debe ser CommissionSchedule.")
        if not is_finite_number(self.band) or not 0 <= self.band < 1:
            raise PortfolioError("La banda de rebalanceo debe estar entre 0 y 1.")
        if self.max_order_cost is not None and (
            not is_finite_number(self.max_order_cost) or self.max_order_cost <= 0
        ):
            raise PortfolioError("El coste máximo por orden debe ser un número positivo.")

    @property
    def is_free(self) -> bool:
        """Sin comisiones ni banda: siempre se vuelve exactamente a los pesos objetivo."""
        return self.commissions.is_free and self.band == 0


@dataclass(frozen=True)
class RebalanceStep:
    """Resultado de un reajuste por escenario (filas) y activo (columnas).

    orders son los importes comprados (+) o vendidos (−) y commissions, lo pagado por activo.
    rebalanced indica en qué escenarios se ha reajustado y skipped, cuántas órdenes se han
    descartado por caras.
    """

    values: np.ndarray
    orders: np.ndarray
    commissions: np.ndarray
    rebalanced: np.ndarray
    skipped: np.ndarray


def rebalance_step(values, target, rule: RebalanceRule) -> RebalanceStep:
    """Reajusta las posiciones de cada escenario a los pesos objetivo según la regla.

    1. Si ningún peso se desvía más que la banda, el escenario no se toca.
    2. Se descartan las órdenes cuya comisión supere max_order_cost de su importe; esos activos
       conservan su valor y el resto, descontadas las comisiones, se reparte entre los demás
       según sus pesos objetivo.
    3. Si quedan menos de dos activos con orden no hay nada que intercambiar y no se reajusta.
    """
    values = np.atleast_2d(np.asarray(values, dtype=float))
    target = np.asarray(target, dtype=float)
    total = values.sum(axis=1, keepdims=True)
    if rule.is_free:
        new = total * target
        orders = new - values
        moved = np.abs(orders) > ORDER_TOLERANCE * total
        return RebalanceStep(
            new,
            np.where(moved, orders, 0.0),
            np.zeros_like(values),
            moved.any(axis=1),
            np.zeros(len(values), dtype=int),
        )

    drift = np.abs(values / total - target).max(axis=1)
    due = drift > rule.band
    orders = total * target - values
    orders = np.where(np.abs(orders) > ORDER_TOLERANCE * total, orders, 0.0)
    fees = rule.commissions.cost(orders)
    trade = (orders != 0) & due[:, None]
    skipped_orders = np.zeros_like(trade)
    if rule.max_order_cost is not None:
        with np.errstate(divide="ignore", invalid="ignore"):
            expensive = trade & (fees > rule.max_order_cost * np.abs(orders))
        skipped_orders = expensive
        trade &= ~expensive
    active = trade.sum(axis=1) >= 2
    trade &= active[:, None]

    kept = np.where(trade, 0.0, values).sum(axis=1)
    traded_weight = np.where(trade, target, 0.0).sum(axis=1)
    # La comisión depende de la orden y la orden, de lo que queda tras la comisión: unas pocas
    # pasadas bastan para que la diferencia sea despreciable. El valor baja exactamente lo
    # cobrado en la última pasada.
    for _ in range(3):
        commissions = np.where(trade, fees, 0.0)
        available = total[:, 0] - kept - commissions.sum(axis=1)
        share = np.divide(
            available, traded_weight, out=np.zeros_like(available), where=traded_weight > 0
        )
        new = np.where(trade, share[:, None] * target, values)
        fees = rule.commissions.cost(new - values)
    invalid = active & ((new < 0).any(axis=1) | (available <= 0))
    if invalid.any():
        # Una cartera tan pequeña que las comisiones la agotarían no se reajusta.
        new[invalid] = values[invalid]
        commissions[invalid] = 0.0
        trade[invalid] = False
        active = active & ~invalid
    return RebalanceStep(
        new,
        np.where(trade, new - values, 0.0),
        commissions,
        active,
        (skipped_orders & due[:, None]).sum(axis=1),
    )
