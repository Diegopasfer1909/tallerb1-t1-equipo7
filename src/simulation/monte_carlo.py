"""Simulación de activos correlacionados, con rebalanceo mensual opcional."""

from numbers import Integral, Real

import numpy as np
import pandas as pd

from .result import SimulationResult

MAX_SIMULATION_VALUES = 20_000_000


def estimate_parameters(
    returns: pd.DataFrame,
    periods_per_year: int,
    expected_returns: float | dict[str, float] | None = None,
    volatilities: float | dict[str, float] | None = None,
) -> pd.DataFrame:
    """Estima μ y σ con rentabilidades simples y aplica los supuestos indicados."""
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
        raise ValueError("No se han podido estimar parámetros finitos para la simulación.")
    return parameters


def simulate_paths(
    prices: pd.DataFrame,
    starting_values: pd.Series,
    currency: str,
    steps: int = 252,
    simulations: int = 1000,
    seed: int | None = None,
    expected_returns: float | dict[str, float] | None = None,
    volatilities: float | dict[str, float] | None = None,
    periods_per_year: int = 252,
    price_column: str = "Close",
    rebalance_weights: pd.Series | None = None,
    confidence: float = 0.95,
) -> SimulationResult:
    """Prepara los datos, estima el modelo y devuelve las trayectorias de la cartera."""
    _validate_settings(steps, simulations, periods_per_year, seed)
    if (
        isinstance(confidence, bool)
        or not isinstance(confidence, Real)
        or not np.isfinite(confidence)
        or not 0.5 < confidence < 1
    ):
        raise ValueError("La confianza debe estar entre 0,5 y 1, sin incluir los extremos.")
    prices = _prepare_prices(prices)
    valuation_date = pd.DatetimeIndex(prices.index)[-1]
    if not isinstance(valuation_date, pd.Timestamp):
        raise ValueError("La fecha de valoración no es válida.")
    initial = _prepare_starting_values(starting_values, prices.columns)
    target = None
    rebalance_steps = set()
    if rebalance_weights is not None:
        if not rebalance_weights.index.is_unique or set(rebalance_weights.index) != set(
            prices.columns
        ):
            raise ValueError("Indica un peso objetivo por cada activo de la simulación.")
        target = rebalance_weights.reindex(prices.columns).to_numpy(dtype=float)
        if (
            not np.isfinite(target).all()
            or (target < 0).any()
            or (target > 1).any()
            or not np.isclose(target.sum(), 1, rtol=0, atol=1e-10)
        ):
            raise ValueError(
                "Los pesos objetivo de la simulación deben estar entre 0 y 1 y sumar 1."
            )
        rebalance_steps = _monthly_rebalance_steps(steps, periods_per_year)
    if simulations * (steps + 1 + 2 * len(initial)) > MAX_SIMULATION_VALUES:
        raise ValueError(
            "La simulación es demasiado grande. Reduce los períodos o el número de simulaciones."
        )

    returns = prices.pct_change(fill_method=None).iloc[1:]
    parameters = estimate_parameters(returns, periods_per_year, expected_returns, volatilities)
    correlation, covariance = _calculate_covariance(returns, parameters)
    factor, method = _covariance_factor(covariance)
    mean = parameters["mean_log_return"].to_numpy(dtype=float)
    paths = _generate_paths(
        initial, mean, factor, steps, simulations, seed, target, rebalance_steps
    )

    table = pd.DataFrame(
        paths,
        index=pd.RangeIndex(steps + 1, name="Step"),
        columns=pd.RangeIndex(simulations, name="Simulation"),
    )
    assumptions = parameters.reindex(
        columns=["annual_return", "annual_volatility", "return_source", "volatility_source"]
    ).copy()
    return SimulationResult(
        paths=table,
        currency=currency,
        valuation_date=valuation_date,
        assumptions=assumptions,
        correlation=correlation,
        periods_per_year=periods_per_year,
        price_column=price_column,
        seed=seed,
        confidence=float(confidence),
        correlation_method=method,
        starting_values=pd.Series(initial, index=prices.columns),
        rebalance="monthly" if target is not None else None,
        target_weights=pd.Series(target, index=prices.columns) if target is not None else None,
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
                raise ValueError(f"Activo desconocido en los supuestos: {symbol}.")
            if (
                isinstance(value, bool)
                or not isinstance(value, Real)
                or not np.isfinite(float(value))
            ):
                raise ValueError(
                    "Los supuestos de retorno y volatilidad deben ser números finitos."
                )
            if column == "annual_volatility" and value < 0:
                raise ValueError("La volatilidad no puede ser negativa.")
            parameters.loc[symbol, column] = float(value)
            parameters.loc[symbol, source] = "usuario"


def _validate_settings(steps, simulations, periods_per_year, seed) -> None:
    """Comprueba el número de períodos, escenarios y la semilla aleatoria."""
    for name, value in [
        ("steps", steps),
        ("simulations", simulations),
        ("periods_per_year", periods_per_year),
    ]:
        if isinstance(value, bool) or not isinstance(value, Integral) or value < 1:
            raise ValueError(f"{name} debe ser un entero positivo.")
    if seed is not None and (isinstance(seed, bool) or not isinstance(seed, Integral) or seed < 0):
        raise ValueError("seed debe ser un entero no negativo o None.")


def _prepare_prices(prices: pd.DataFrame) -> pd.DataFrame:
    """Valida y ordena los precios sin rellenar observaciones que falten."""
    if not isinstance(prices, pd.DataFrame) or prices.empty or prices.columns.has_duplicates:
        raise ValueError("La simulación necesita una tabla no vacía con una columna por activo.")
    if (
        not isinstance(prices.index, pd.DatetimeIndex)
        or prices.index.has_duplicates
        or prices.index.hasnans
    ):
        raise ValueError("Los precios históricos necesitan fechas válidas y sin repetir.")
    prices = prices.sort_index().astype(float)
    if len(prices) < 3:
        raise ValueError(
            "Para realizar la simulación hacen falta precios de todos los activos en al menos tres fechas."
        )
    if not np.isfinite(prices.to_numpy()).all() or (prices <= 0).to_numpy().any():
        raise ValueError(
            "Los precios de la simulación deben ser positivos y finitos, y no puede faltar ningún dato."
        )
    return prices


def _prepare_starting_values(starting_values: pd.Series, symbols: pd.Index) -> np.ndarray:
    """Ordena los valores iniciales igual que las columnas de precios."""
    if not isinstance(starting_values, pd.Series) or starting_values.index.has_duplicates:
        raise ValueError(
            "Los valores iniciales deben ser una Series con el símbolo de cada activo como índice."
        )
    if set(starting_values.index) != set(symbols):
        raise ValueError(
            "Los valores iniciales deben corresponder a las columnas de los activos históricos."
        )
    initial = starting_values.reindex(symbols).to_numpy(dtype=float)
    if (
        not np.isfinite(initial).all()
        or (initial < 0).any()
        or not np.isfinite(initial.sum())
        or initial.sum() <= 0
    ):
        raise ValueError(
            "Los valores iniciales no pueden ser negativos y el total debe ser positivo y finito."
        )
    return initial


def _calculate_covariance(returns: pd.DataFrame, parameters: pd.DataFrame):
    """Combina la correlación histórica con las volatilidades utilizadas en el modelo."""
    correlation_values = returns.corr().fillna(0).to_numpy(dtype=float, copy=True)
    # Un activo sin variación carece de correlación estimable; con volatilidad indicada se trata como independiente.
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
            raise ValueError("La matriz de covarianzas no es válida para la simulación.") from None
        factor = vectors @ np.diag(np.sqrt(np.clip(values, 0, None)))
        return factor, "Autovalores (matriz singular)"


def _monthly_rebalance_steps(steps: int, periods_per_year: int) -> set[int]:
    """Aproxima un mes con 21 sesiones diarias o un período mensual."""
    if periods_per_year == 252:
        interval = 21
    elif periods_per_year == 12:
        interval = 1
    else:
        raise ValueError(
            "El rebalanceo mensual admite 252 sesiones diarias o 12 períodos mensuales por año."
        )
    return set(range(interval, steps + 1, interval))


def _generate_paths(
    initial, mean, factor, steps, simulations, seed, target=None, rebalance_steps=()
) -> np.ndarray:
    """Actualiza las posiciones en cada escenario y suma el valor de la cartera."""
    random_generator = np.random.default_rng(seed)
    # Cada escenario empieza con las mismas posiciones.
    asset_values = np.tile(initial, (simulations, 1))
    portfolio_values = np.zeros((steps + 1, simulations))
    portfolio_values[0] = initial.sum()
    try:
        with np.errstate(over="raise", invalid="raise", under="ignore"):
            for step in range(1, steps + 1):
                independent_shocks = random_generator.standard_normal((simulations, len(initial)))
                log_changes = mean + independent_shocks @ factor.T
                asset_values = asset_values * np.exp(log_changes)
                # Suma los activos de cada escenario, sin mezclar escenarios entre sí.
                portfolio_values[step] = asset_values.sum(axis=1)
                if step in rebalance_steps:
                    asset_values = portfolio_values[step].reshape(simulations, 1) * target
    except FloatingPointError:
        raise ValueError(
            "Los valores de la simulación han superado el límite numérico del programa. Reduce el número de períodos o revisa las estimaciones de rentabilidad y volatilidad."
        ) from None
    if not np.isfinite(portfolio_values).all() or (portfolio_values <= 0).any():
        raise ValueError(
            "La simulación ha producido valores no válidos. Reduce el número de períodos o revisa las estimaciones de rentabilidad y volatilidad."
        )

    return portfolio_values
