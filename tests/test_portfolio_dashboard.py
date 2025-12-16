"""Tests for dashboard.portfolio_dashboard module."""

from unittest.mock import Mock, patch

from finance_feedback_engine.dashboard.portfolio_dashboard import (
    PortfolioDashboardAggregator,
    display_portfolio_dashboard,
)


class TestPortfolioDashboardAggregator:
    """Test PortfolioDashboardAggregator class."""

    def test_aggregator_initialization_with_platforms(self):
        """Test creating a dashboard aggregator with platforms."""
        platforms = ["coinbase_advanced", "oanda", "mock"]
        aggregator = PortfolioDashboardAggregator(platforms=platforms)
        assert aggregator is not None

    def test_aggregator_stores_platforms(self):
        """Test that aggregator stores platform list."""
        platforms = ["mock"]
        aggregator = PortfolioDashboardAggregator(platforms=platforms)

        # Check that aggregator has platforms attribute
        assert hasattr(aggregator, "platforms") or hasattr(aggregator, "_platforms")


class TestDisplayPortfolioDashboard:
    """Test display_portfolio_dashboard function."""

    def test_display_with_aggregated_data(self):
        """Test displaying portfolio with aggregated data."""
        aggregated_data = {"total_balance": 10000.0, "platforms": []}

        # Should not raise exception
        display_portfolio_dashboard(aggregated_data)

    def test_display_accepts_dict(self):
        """Test that display accepts dictionary parameter."""
        # Minimal aggregated data
        data = {}

        display_portfolio_dashboard(data)


class TestPortfolioDashboardIntegration:
    """Integration tests for portfolio dashboard."""

    @patch(
        "finance_feedback_engine.trading_platforms.platform_factory.PlatformFactory.create_platform"
    )
    def test_aggregator_to_display_workflow(self, mock_create):
        """Test creating aggregator and displaying."""
        # Mock platform creation
        mock_platform = Mock()
        mock_platform.get_balance.return_value = 10000.0
        mock_platform.get_account_info.return_value = {"balance": 10000.0}
        mock_create.return_value = mock_platform

        platforms = ["mock"]
        aggregator = PortfolioDashboardAggregator(platforms=platforms)

        # Aggregator should be created successfully
        assert aggregator is not None

    def test_aggregator_with_single_platform(self):
        """Test aggregator with single platform."""
        aggregator = PortfolioDashboardAggregator(platforms=["mock"])
        assert hasattr(aggregator, "platforms") or hasattr(aggregator, "_platforms")


class TestPortfolioDashboardEdgeCases:
    """Test edge cases for portfolio dashboard."""

    def test_aggregator_with_empty_platforms(self):
        """Test aggregator with empty platform list."""
        aggregator = PortfolioDashboardAggregator(platforms=[])
        assert aggregator is not None

    def test_display_with_empty_data(self):
        """Test displaying empty aggregated data."""
        result = display_portfolio_dashboard({})
        assert result is None
