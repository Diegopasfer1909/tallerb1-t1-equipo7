"""Guarda el informe Markdown y las imágenes que utiliza."""

from __future__ import annotations

import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from ..errors import PortfolioError
from .plots import charts_by_section, close_figures, plot_report, save_charts
from .report import build_report
from .sections import select_sections

if TYPE_CHECKING:
    from ..analysis.result import PortfolioAnalysis
    from ..simulation.result import SimulationResult

# Carpeta por defecto, relativa a la carpeta desde la que se ejecuta el programa.
DEFAULT_DIRECTORY = Path("informes")


def save_report(
    analysis: PortfolioAnalysis,
    simulation: SimulationResult | None = None,
    *,
    sections=None,
    detail: str = "compact",
    directory: str | Path | None = None,
    generated_on: datetime | None = None,
) -> Path:
    """Guarda el informe en una carpeta nueva con fecha y hora dentro de directory.

    El informe se prepara en una carpeta temporal y solo se publica si todo se ha guardado;
    si algo falla, no quedan carpetas a medias ni figuras abiertas.
    """
    selected = select_sections(sections, detail, has_simulation=simulation is not None)
    if simulation is not None:
        _check_simulation_matches(analysis, simulation)
    generated_on = generated_on or datetime.now().astimezone()
    reports = Path(directory) if directory is not None else DEFAULT_DIRECTORY
    figures = plot_report(analysis, simulation, selected)
    try:
        reports.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".informe-", dir=reports))
        try:
            files = save_charts(figures, staging)
            text = build_report(
                analysis,
                generated_on,
                charts_by_section(files),
                simulation,
                sections=selected,
                detail=detail,
            )
            target = _new_report_folder(reports, generated_on)
            (staging / f"{target.name}.md").write_text(text, encoding="utf-8")
            staging.rename(target)
        except BaseException:
            shutil.rmtree(staging, ignore_errors=True)
            raise
    finally:
        close_figures(figures)
    return target / f"{target.name}.md"


def _new_report_folder(reports: Path, generated_on: datetime) -> Path:
    """Fecha y hora del informe; añade microsegundos si ya existe uno en ese segundo."""
    name = generated_on.strftime("%Y-%m-%d_%H-%M-%S")
    if (reports / name).exists():
        name += generated_on.strftime("_%f")
    return reports / name


def _check_simulation_matches(analysis: PortfolioAnalysis, simulation: SimulationResult) -> None:
    """Una simulación proporcionada debe partir de la misma cartera que el informe.

    Se comprueba en orden: fecha y divisa, posiciones iniciales y criterios de cálculo.
    """
    holdings = analysis.holdings
    same_start = (
        simulation.currency == analysis.currency
        and simulation.valuation_date == analysis.values.index[-1]
    )
    same_positions = (
        set(simulation.assumptions.index) == set(holdings.index)
        and np.allclose(simulation.starting_values.reindex(holdings.index), holdings["value"])
        and np.allclose(simulation.paths.iloc[0], holdings["value"].sum())
    )
    same_weights = simulation.rebalance is None or (
        simulation.target_weights is not None
        and np.allclose(
            simulation.target_weights.reindex(analysis.target_weights.index),
            analysis.target_weights,
        )
    )
    same_criteria = same_weights and (
        (simulation.price_column, simulation.periods_per_year, simulation.rebalance)
        == (analysis.price_column, analysis.periods_per_year, analysis.rebalance)
    )
    for matches, problem in (
        (same_start, "la misma divisa y fecha de valoración"),
        (same_positions, "los mismos activos y valor inicial"),
        (same_criteria, "los mismos criterios de cálculo"),
    ):
        if not matches:
            raise PortfolioError(f"La simulación debe utilizar {problem} que el informe.")
