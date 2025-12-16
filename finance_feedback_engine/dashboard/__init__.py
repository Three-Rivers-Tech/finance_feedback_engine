"""Dashboard module for aggregating multi-platform portfolio metrics."""

from .portfolio_dashboard import (
    PortfolioDashboardAggregator,
    display_portfolio_dashboard,
)

__all__ = ["PortfolioDashboardAggregator", "display_portfolio_dashboard"]
