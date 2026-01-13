"""
THR-108: Comprehensive tests for drawdown check type mismatch fix.

This test suite specifically validates the fix for comparing dollars vs percentages
in the max drawdown check. The fix ensures:

1. Prefer `risk_metrics.unrealized_pnl_percent` when available (divide by 100)
2. Fallback: if `total_pnl` magnitude > 1.0, normalize by portfolio value
3. Else treat `total_pnl` as a decimal fraction

These tests prevent regression of the "death by type mismatch" bug where
-$300 (dollars) was compared against 0.05 (5% threshold), incorrectly
blocking all trades.
"""

from unittest.mock import patch

import pytest

from finance_feedback_engine.risk.exposure_reservation import get_exposure_manager
from finance_feedback_engine.risk.gatekeeper import RiskGatekeeper


@pytest.fixture(autouse=True)
def clear_reservations():
    """Clear any stale reservations before each test.

    This is needed because ExposureReservationManager is a singleton
    and may have reservations from other tests.
    """
    manager = get_exposure_manager()
    manager.clear_all_reservations()
    yield
    manager.clear_all_reservations()


@pytest.fixture
def gatekeeper():
    """Create a RiskGatekeeper with 5% max drawdown."""
    return RiskGatekeeper(max_drawdown_pct=0.05, is_backtest=False)


@pytest.fixture
def base_decision():
    """Base decision for testing."""
    return {
        "action": "BUY",
        "asset_pair": "BTCUSD",
        "confidence": 85,
        "volatility": 0.02,
    }


class TestDrawdownNormalization:
    """Tests for THR-108: Drawdown check type mismatch fix."""

    @patch("finance_feedback_engine.risk.gatekeeper.MarketSchedule")
    def test_dollar_value_normalized_to_percentage_within_limit(
        self, mock_schedule, gatekeeper, base_decision
    ):
        """
        THR-108: Dollar loss should be normalized to percentage.

        -$300 loss on $10,000 portfolio = -3%, which is within 5% limit.
        Before fix: -300 < -0.05 was True (INCORRECT BLOCK)
        After fix: -0.03 < -0.05 is False (CORRECT PASS)
        """
        mock_schedule.get_market_status.return_value = {"is_open": True, "warning": None}

        context = {
            "asset_type": "crypto",
            "recent_performance": {"total_pnl": -300.0},  # -$300 (dollars)
            "total_value_usd": 10000.0,  # $10,000 portfolio
            "holdings": {},
        }

        allowed, message = gatekeeper.validate_trade(base_decision, context)

        assert allowed is True, f"Should pass: -$300 on $10k = -3% < 5% limit. Got: {message}"

    @patch("finance_feedback_engine.risk.gatekeeper.MarketSchedule")
    def test_dollar_value_normalized_to_percentage_exceeds_limit(
        self, mock_schedule, gatekeeper, base_decision
    ):
        """
        THR-108: Dollar loss exceeding limit should be blocked.

        -$800 loss on $10,000 portfolio = -8%, which exceeds 5% limit.
        """
        mock_schedule.get_market_status.return_value = {"is_open": True, "warning": None}

        context = {
            "asset_type": "crypto",
            "recent_performance": {"total_pnl": -800.0},  # -$800 (dollars)
            "total_value_usd": 10000.0,  # $10,000 portfolio
            "holdings": {},
        }

        allowed, message = gatekeeper.validate_trade(base_decision, context)

        assert allowed is False, "Should block: -$800 on $10k = -8% > 5% limit"
        assert "drawdown" in message.lower()

    @patch("finance_feedback_engine.risk.gatekeeper.MarketSchedule")
    def test_risk_metrics_unrealized_pnl_percent_preferred(
        self, mock_schedule, gatekeeper, base_decision
    ):
        """
        THR-108: unrealized_pnl_percent from risk_metrics should be preferred.

        When risk_metrics provides unrealized_pnl_percent = -3.0 (meaning -3%),
        this should be used instead of total_pnl.
        """
        mock_schedule.get_market_status.return_value = {"is_open": True, "warning": None}

        context = {
            "asset_type": "crypto",
            "risk_metrics": {"unrealized_pnl_percent": -3.0},  # -3% (preferred)
            "recent_performance": {"total_pnl": -9999.0},  # Should be ignored
            "holdings": {},
        }

        allowed, message = gatekeeper.validate_trade(base_decision, context)

        # -3% < 5% limit, should pass
        assert allowed is True, f"Should pass using risk_metrics -3%. Got: {message}"

    @patch("finance_feedback_engine.risk.gatekeeper.MarketSchedule")
    def test_risk_metrics_unrealized_pnl_percent_exceeds_limit(
        self, mock_schedule, gatekeeper, base_decision
    ):
        """
        THR-108: unrealized_pnl_percent exceeding limit should block.
        """
        mock_schedule.get_market_status.return_value = {"is_open": True, "warning": None}

        context = {
            "asset_type": "crypto",
            "risk_metrics": {"unrealized_pnl_percent": -7.5},  # -7.5%
            "recent_performance": {"total_pnl": 0.01},  # Should be ignored
            "holdings": {},
        }

        allowed, message = gatekeeper.validate_trade(base_decision, context)

        assert allowed is False, "Should block: -7.5% > 5% limit"
        assert "drawdown" in message.lower()

    @patch("finance_feedback_engine.risk.gatekeeper.MarketSchedule")
    def test_decimal_fraction_used_directly(
        self, mock_schedule, gatekeeper, base_decision
    ):
        """
        THR-108: Small decimal values (magnitude <= 1.0) treated as fractions.

        -0.03 is already a percentage in decimal form (-3%).
        """
        mock_schedule.get_market_status.return_value = {"is_open": True, "warning": None}

        context = {
            "asset_type": "crypto",
            "recent_performance": {"total_pnl": -0.03},  # -3% as decimal
            "holdings": {},
        }

        allowed, message = gatekeeper.validate_trade(base_decision, context)

        assert allowed is True, f"Should pass: -3% < 5% limit. Got: {message}"

    @patch("finance_feedback_engine.risk.gatekeeper.MarketSchedule")
    def test_decimal_fraction_exceeds_limit(
        self, mock_schedule, gatekeeper, base_decision
    ):
        """
        THR-108: Decimal fraction exceeding limit should block.
        """
        mock_schedule.get_market_status.return_value = {"is_open": True, "warning": None}

        context = {
            "asset_type": "crypto",
            "recent_performance": {"total_pnl": -0.08},  # -8% as decimal
            "holdings": {},
        }

        allowed, message = gatekeeper.validate_trade(base_decision, context)

        assert allowed is False, "Should block: -8% > 5% limit"
        assert "drawdown" in message.lower()

    @patch("finance_feedback_engine.risk.gatekeeper.MarketSchedule")
    def test_portfolio_breakdown_used_for_normalization(
        self, mock_schedule, gatekeeper, base_decision
    ):
        """
        THR-108: portfolio_breakdown.total_value_usd should work for normalization.
        """
        mock_schedule.get_market_status.return_value = {"is_open": True, "warning": None}

        context = {
            "asset_type": "crypto",
            "recent_performance": {"total_pnl": -250.0},  # -$250
            "portfolio_breakdown": {"total_value_usd": 10000.0},  # $10k
            "holdings": {},
        }

        allowed, message = gatekeeper.validate_trade(base_decision, context)

        # -$250 / $10k = -2.5%, which is < 5% limit
        assert allowed is True, f"Should pass: -2.5% < 5%. Got: {message}"

    @patch("finance_feedback_engine.risk.gatekeeper.MarketSchedule")
    def test_portfolio_snapshot_used_for_normalization(
        self, mock_schedule, gatekeeper, base_decision
    ):
        """
        THR-108: portfolio_snapshot.total_value_usd should work for normalization.
        """
        mock_schedule.get_market_status.return_value = {"is_open": True, "warning": None}

        context = {
            "asset_type": "crypto",
            "recent_performance": {"total_pnl": -600.0},  # -$600
            "portfolio_snapshot": {"total_value_usd": 10000.0},  # $10k
            "holdings": {},
        }

        allowed, message = gatekeeper.validate_trade(base_decision, context)

        # -$600 / $10k = -6%, which is > 5% limit
        assert allowed is False, "Should block: -6% > 5% limit"


class TestDrawdownEdgeCases:
    """Edge cases for drawdown normalization."""

    @patch("finance_feedback_engine.risk.gatekeeper.MarketSchedule")
    def test_missing_portfolio_value_uses_raw_value(
        self, mock_schedule, gatekeeper, base_decision
    ):
        """
        THR-108: When no portfolio value available, large dollar values
        fall back to being treated as-is (potential false negative, but
        better than blocking everything).
        """
        mock_schedule.get_market_status.return_value = {"is_open": True, "warning": None}

        context = {
            "asset_type": "crypto",
            "recent_performance": {"total_pnl": -50.0},  # -$50, no normalization
            # No portfolio value provided
            "holdings": {},
        }

        allowed, message = gatekeeper.validate_trade(base_decision, context)

        # Without normalization, -50.0 is compared directly to -0.05
        # -50.0 < -0.05 is True, so this will block
        # This is a known limitation - but better to be safe
        assert allowed is False

    @patch("finance_feedback_engine.risk.gatekeeper.MarketSchedule")
    def test_zero_portfolio_value_fallback(
        self, mock_schedule, gatekeeper, base_decision
    ):
        """
        THR-108: Zero portfolio value should not cause division by zero.
        """
        mock_schedule.get_market_status.return_value = {"is_open": True, "warning": None}

        context = {
            "asset_type": "crypto",
            "recent_performance": {"total_pnl": -100.0},
            "total_value_usd": 0.0,  # Zero portfolio value
            "holdings": {},
        }

        # Should not raise an exception
        allowed, message = gatekeeper.validate_trade(base_decision, context)

        # Falls back to using raw value when portfolio is 0
        assert allowed is False  # -100 < -0.05

    @patch("finance_feedback_engine.risk.gatekeeper.MarketSchedule")
    def test_positive_pnl_always_passes(
        self, mock_schedule, gatekeeper, base_decision
    ):
        """
        THR-108: Positive P&L (gains) should always pass drawdown check.
        """
        mock_schedule.get_market_status.return_value = {"is_open": True, "warning": None}

        context = {
            "asset_type": "crypto",
            "recent_performance": {"total_pnl": 500.0},  # +$500 profit
            "total_value_usd": 10000.0,
            "holdings": {},
        }

        allowed, message = gatekeeper.validate_trade(base_decision, context)

        assert allowed is True, "Positive P&L should always pass drawdown check"

    @patch("finance_feedback_engine.risk.gatekeeper.MarketSchedule")
    def test_exactly_at_limit_passes(
        self, mock_schedule, gatekeeper, base_decision
    ):
        """
        THR-108: Drawdown exactly at limit should pass (not exceed).
        """
        mock_schedule.get_market_status.return_value = {"is_open": True, "warning": None}

        context = {
            "asset_type": "crypto",
            "recent_performance": {"total_pnl": -0.05},  # Exactly -5%
            "holdings": {},
        }

        allowed, message = gatekeeper.validate_trade(base_decision, context)

        # -0.05 is NOT less than -0.05, so it passes
        assert allowed is True, "Exactly at limit should pass"

    @patch("finance_feedback_engine.risk.gatekeeper.MarketSchedule")
    def test_slightly_over_limit_fails(
        self, mock_schedule, gatekeeper, base_decision
    ):
        """
        THR-108: Drawdown slightly over limit should fail.
        """
        mock_schedule.get_market_status.return_value = {"is_open": True, "warning": None}

        context = {
            "asset_type": "crypto",
            "recent_performance": {"total_pnl": -0.051},  # -5.1%
            "holdings": {},
        }

        allowed, message = gatekeeper.validate_trade(base_decision, context)

        assert allowed is False, "Slightly over limit should fail"

    @patch("finance_feedback_engine.risk.gatekeeper.MarketSchedule")
    def test_none_pnl_treated_as_zero(
        self, mock_schedule, gatekeeper, base_decision
    ):
        """
        THR-108: None or missing P&L should be treated as zero.
        """
        mock_schedule.get_market_status.return_value = {"is_open": True, "warning": None}

        context = {
            "asset_type": "crypto",
            "recent_performance": {},  # No total_pnl
            "holdings": {},
        }

        allowed, message = gatekeeper.validate_trade(base_decision, context)

        assert allowed is True, "Missing P&L (0) should pass"


class TestDrawdownWithDifferentThresholds:
    """Test drawdown with various max_drawdown_pct settings."""

    @patch("finance_feedback_engine.risk.gatekeeper.MarketSchedule")
    def test_custom_10_percent_threshold(self, mock_schedule, base_decision):
        """Test with 10% max drawdown threshold."""
        gk = RiskGatekeeper(max_drawdown_pct=0.10)
        mock_schedule.get_market_status.return_value = {"is_open": True, "warning": None}

        # -$800 on $10k = -8%, which is < 10% limit
        context = {
            "asset_type": "crypto",
            "recent_performance": {"total_pnl": -800.0},
            "total_value_usd": 10000.0,
            "holdings": {},
        }

        allowed, message = gk.validate_trade(base_decision, context)
        assert allowed is True, "-8% should pass with 10% limit"

    @patch("finance_feedback_engine.risk.gatekeeper.MarketSchedule")
    def test_strict_2_percent_threshold(self, mock_schedule, base_decision):
        """Test with strict 2% max drawdown threshold."""
        gk = RiskGatekeeper(max_drawdown_pct=0.02)
        mock_schedule.get_market_status.return_value = {"is_open": True, "warning": None}

        # -$250 on $10k = -2.5%, which is > 2% limit
        context = {
            "asset_type": "crypto",
            "recent_performance": {"total_pnl": -250.0},
            "total_value_usd": 10000.0,
            "holdings": {},
        }

        allowed, message = gk.validate_trade(base_decision, context)
        assert allowed is False, "-2.5% should fail with 2% limit"


class TestDrawdownIntegrationScenarios:
    """Real-world integration scenarios."""

    @patch("finance_feedback_engine.risk.gatekeeper.MarketSchedule")
    def test_realistic_crypto_portfolio_scenario(self, mock_schedule, base_decision):
        """
        THR-108: Realistic crypto portfolio scenario.

        Portfolio: $50,000
        Current loss: $1,500
        Expected: -3%, should pass 5% limit
        """
        gk = RiskGatekeeper(max_drawdown_pct=0.05)
        mock_schedule.get_market_status.return_value = {"is_open": True, "warning": None}

        context = {
            "asset_type": "crypto",
            "recent_performance": {"total_pnl": -1500.0},
            "total_value_usd": 50000.0,
            "holdings": {"BTC": "crypto"},
        }

        allowed, message = gk.validate_trade(base_decision, context)
        assert allowed is True, f"$1.5k loss on $50k = -3% should pass. Got: {message}"

    @patch("finance_feedback_engine.risk.gatekeeper.MarketSchedule")
    def test_realistic_forex_portfolio_scenario(self, mock_schedule):
        """
        THR-108: Realistic forex portfolio scenario with risk_metrics.
        """
        gk = RiskGatekeeper(max_drawdown_pct=0.05)
        mock_schedule.get_market_status.return_value = {"is_open": True, "warning": None}

        decision = {
            "action": "BUY",
            "asset_pair": "EUR_USD",
            "confidence": 85,
            "volatility": 0.02,
        }

        context = {
            "asset_type": "forex",
            "risk_metrics": {
                "unrealized_pnl_percent": -4.2,  # -4.2% from risk metrics
                "leverage_estimate": 2.0,
            },
            "recent_performance": {"total_pnl": -2100.0},  # $2.1k loss (ignored)
            "total_value_usd": 50000.0,
            "holdings": {},
        }

        allowed, message = gk.validate_trade(decision, context)
        assert allowed is True, f"-4.2% from risk_metrics should pass. Got: {message}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
