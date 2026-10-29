"""Cálculos locales, sin descargas ni exportaciones automáticas."""

from .backtest import backtest_allocation
from .portfolio_analysis import analyze_portfolio

__all__ = ["analyze_portfolio", "backtest_allocation"]
