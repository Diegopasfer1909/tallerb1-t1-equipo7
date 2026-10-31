"""Simulación de activos correlacionados, con rebalanceo mensual opcional."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..constants import CLOSE, MONTHLY, PERIODS_PER_YEAR, SESSIONS_PER_MONTH
from ..errors import PortfolioError
from ..validation import validate_positive_int, validate_price_table, validate_target_weights
from .result import SimulationResult
from .settings import Assumption, SimulationSettings, validate_assumptions

MAX_SIMULATION_VALUES = 20_000_000


@dataclass(frozen=True)
class SimulationInputs:
    """Precios históricos, valor inicial de cada posición y pesos de rebalanceo, si los hay."""

    prices: pd.DataFrame
    starting_values: pd.Series
    currency: str
    price_column: str = CLOSE
    rebalance_weights: pd.Series | None = None


def estimate_parameters(
    returns: pd.DataFrame,
    periods_per_year: int,
    expected_returns: Assumption = None,
    volatilities: Assumption = None,
) -> pd.DataFrame:
    """Estima μ y σ con rentabilidades simples y aplica los supuestos indicados."""
    validate_assumptions(expected_returns, volatilities)
    parameters = pd.DataFrame(index=returns.columns)
    parameters["annual_return"] = returns.mean() * periods_per_year
    parameters["annual_volatility"] = returns.std(ddof=1) * np.sqrt(periods_per_year)
    parameters["return_source"] = "histórico"
    parameters["volatility_source"] = "histórica"
    _apply_assumptions(parameters, expected_returns, volatilities)
    parameters["period_volatility"] = parameters["annual_volatility"] / np.sqrt(periods_per_year)
    parameters["mean_log_return"] = (
        parameters["annual_return"] - parameters["annual_volatility"] ** 2 / 2
    ) / periods_per_year
    if not np.isfinite(parameters.select_dtypes(include="number").to_numpy()).all():
        raise PortfolioError("No se han podido estimar parámetros finitos para la simulación.")
    return parameters


def simulate(
    inputs: SimulationInputs,
    settings: SimulationSettings | None = None,
    periods_per_year: int = PERIODS_PER_YEAR,
) -> SimulationResult:
    """Estima el modelo con los precios históricos y simula el valor desde la última fecha.

    periods_per_year debe corresponder a la frecuencia de los precios (252 si son diarios).
    """
    settings = settings or SimulationSettings()
    validate_positive_int("periods_per_year", periods_per_year)
    prices = _prepare_prices(inputs.prices)
    initial = _prepare_starting_values(inputs.starting_values, prices.columns)
    target = interval = None
    if inputs.rebalance_weights is not None:
        target = validate_target_weights(inputs.rebalance_weights, prices.columns)
        interval = rebalance_interval(periods_per_year)
    if settings.simulations * (settings.steps + 1 + 2 * len(initial)) > MAX_SIMULATION_VALUES:
        raise PortfolioError(
            "La simulación es demasiado grande. Reduce los períodos o el número de simulaciones."
        )

    returns = prices.pct_change(fill_method=None).iloc[1:]
    parameters = estimate_parameters(
        returns, periods_per_year, settings.expected_returns, settings.volatilities
    )
    correlation, covariance = _calculate_covariance(returns, parameters)
    factor, method = _covariance_factor(covariance)
    mean = parameters["mean_log_return"].to_numpy(dtype=float)
    paths = _generate_paths(initial, mean, factor, settings, target, interval)
    return SimulationResult(
        paths=pd.DataFrame(
            paths,
            index=pd.RangeIndex(settings.steps + 1, name="Step"),
            columns=pd.RangeIndex(settings.simulations, name="Simulation"),
        ),
        currency=inputs.currency,
        valuation_date=prices.index[-1],
        assumptions=parameters[
            ["annual_return", "annual_volatility", "return_source", "volatility_source"]
        ].copy(),
        correlation=correlation,
        periods_per_year=periods_per_year,
        price_column=inputs.price_column,
        seed=settings.seed,
        starting_values=pd.Series(initial, index=prices.columns),
        rebalance=MONTHLY if target is not None else None,
        target_weights=pd.Series(target, index=prices.columns) if target is not None else None,
        rebalance_interval=interval,
        confidence=float(settings.confidence),
        correlation_method=method,
    )


def rebalance_interval(periods_per_year: int) -> int:
    """Períodos entre reajustes: 21 sesiones con datos diarios o 1 con datos mensuales."""
    if periods_per_year == PERIODS_PER_YEAR:
        return SESSIONS_PER_MONTH
    if periods_per_year == 12:
        return 1
    raise PortfolioError(
        "El rebalanceo mensual admite 252 sesiones diarias o 12 períodos mensuales por año."
    )


def _apply_assumptions(parameters, expected_returns, volatilities) -> None:
    """Admite un valor para todos los activos o un diccionario con cambios por símbolo."""
    for column, values, source in [
        ("annual_return", expected_returns, "return_source"),
        ("annual_volatility", volatilities, "volatility_source"),
    ]:
        if values is None:
            continue
        overrides = values if isinstance(values, dict) else dict.fromkeys(parameters.index, values)
        for symbol, value in overrides.items():
            if symbol not in parameters.index:
                raise PortfolioError(f"Activo desconocido en los supuestos: {symbol}.")
            parameters.loc[symbol, column] = float(value)
            parameters.loc[symbol, source] = "usuario"


def _prepare_prices(prices: pd.DataFrame) -> pd.DataFrame:
    """Valida y ordena los precios sin rellenar observaciones que falten."""
    if isinstance(prices, pd.DataFrame):
        prices = prices.sort_index().astype(float)
    validate_price_table(prices)
    if len(prices) < 3:
        raise PortfolioError(
            "Para realizar la simulación hacen falta precios de todos los activos en al menos "
            "tres fechas."
        )
    return prices


def _prepare_starting_values(starting_values: pd.Series, symbols: pd.Index) -> np.ndarray:
    """Ordena los valores iniciales igual que las columnas de precios."""
    if not isinstance(starting_values, pd.Series) or starting_values.index.has_duplicates:
        raise PortfolioError(
            "Los valores iniciales deben ser una Series con el símbolo de cada activo como índice."
        )
    if set(starting_values.index) != set(symbols):
        raise PortfolioError(
            "Los valores iniciales deben corresponder a las columnas de los activos históricos."
        )
    initial = starting_values.reindex(symbols).to_numpy(dtype=float)
    if (
        not np.isfinite(initial).all()
        or (initial < 0).any()
        or not np.isfinite(initial.sum())
        or initial.sum() <= 0
    ):
        raise PortfolioError(
            "Los valores iniciales no pueden ser negativos y el total debe ser positivo y finito."
        )
    return initial


def _calculate_covariance(returns: pd.DataFrame, parameters: pd.DataFrame):
    """Combina la correlación histórica con las volatilidades utilizadas en el modelo."""
    correlation_values = returns.corr().fillna(0).to_numpy(dtype=float, copy=True)
    # Un activo sin variación carece de correlación estimable; con volatilidad indicada se
    # trata como independiente.
    np.fill_diagonal(correlation_values, 1)
    correlation = pd.DataFrame(correlation_values, index=returns.columns, columns=returns.columns)
    period_volatility = parameters["period_volatility"].to_numpy(dtype=float)
    covariance = correlation_values * np.outer(period_volatility, period_volatility)
    return correlation, covariance


def _covariance_factor(covariance: np.ndarray) -> tuple[np.ndarray, str]:
    """Usa Cholesky; para matrices singulares conserva la covarianza con autovalores."""
    try:
        return np.linalg.cholesky(covariance), "Cholesky"
    except np.linalg.LinAlgError:
        values, vectors = np.linalg.eigh(covariance)
        if values.min() < -1e-10:
            raise PortfolioError(
                "La matriz de covarianzas no es válida para la simulación."
            ) from None
        factor = vectors @ np.diag(np.sqrt(np.clip(values, 0, None)))
        return factor, "Autovalores (matriz singular)"


def _generate_paths(
    initial: np.ndarray,
    mean: np.ndarray,
    factor: np.ndarray,
    settings: SimulationSettings,
    target: np.ndarray | None = None,
    interval: int | None = None,
) -> np.ndarray:
    """Actualiza las posiciones en cada escenario y suma el valor de la cartera."""
    random_generator = np.random.default_rng(settings.seed)
    # Cada escenario empieza con las mismas posiciones.
    asset_values = np.tile(initial, (settings.simulations, 1))
    portfolio_values = np.zeros((settings.steps + 1, settings.simulations))
    portfolio_values[0] = initial.sum()
    try:
        with np.errstate(over="raise", invalid="raise", under="ignore"):
            for step in range(1, settings.steps + 1):
                shocks = random_generator.standard_normal((settings.simulations, len(initial)))
                asset_values = asset_values * np.exp(mean + shocks @ factor.T)
                # Suma los activos de cada escenario, sin mezclar escenarios entre sí.
                portfolio_values[step] = asset_values.sum(axis=1)
                if interval and step % interval == 0:
                    asset_values = portfolio_values[step].reshape(-1, 1) * target
    except FloatingPointError:
        raise PortfolioError(
            "Los valores de la simulación han superado el límite numérico del programa. Reduce "
            "el número de períodos o revisa las estimaciones de rentabilidad y volatilidad."
        ) from None
    if not np.isfinite(portfolio_values).all() or (portfolio_values <= 0).any():
        raise PortfolioError(
            "La simulación ha producido valores no válidos. Reduce el número de períodos o "
            "revisa las estimaciones de rentabilidad y volatilidad."
        )
    return portfolio_values
