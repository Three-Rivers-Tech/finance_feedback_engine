"""Tests for consolidated leverage and concentration validation in RiskGatekeeper."""

import pytest

from finance_feedback_engine.risk.gatekeeper import RiskGatekeeper


class TestLeverageAndConcentrationValidation:
    """Test suite for _validate_leverage_and_concentration method."""

    def setup_method(self):
        """Set up test fixtures."""
        self.gatekeeper = RiskGatekeeper()

    def test_leverage_within_limit_passes(self):
        """Test that leverage within limit passes validation."""
        decision = {
            "asset_pair": "BTCUSD",
            "action": "BUY",
        }
        context = {
            "risk_metrics": {"leverage_estimate": 3.5},
            "position_concentration": {"largest_position_pct": 15.0},
            "max_leverage": 5.0,
            "max_concentration": 25.0,
        }

        approved, reason = self.gatekeeper._validate_leverage_and_concentration(
            decision, context
        )

        assert approved is True
        assert "passed" in reason.lower()

    def test_leverage_exceeds_limit_fails(self):
        """Test that leverage exceeding limit fails validation."""
        decision = {
            "asset_pair": "BTCUSD",
            "action": "BUY",
        }
        context = {
            "risk_metrics": {"leverage_estimate": 6.5},
            "position_concentration": {"largest_position_pct": 15.0},
            "max_leverage": 5.0,
            "max_concentration": 25.0,
        }

        approved, reason = self.gatekeeper._validate_leverage_and_concentration(
            decision, context
        )

        assert approved is False
        assert "6.5" in reason
        assert "5" in reason
        assert "leverage" in reason.lower()

    def test_concentration_within_limit_passes(self):
        """Test that concentration within limit passes validation."""
        decision = {
            "asset_pair": "EURUSD",
            "action": "BUY",
        }
        context = {
            "risk_metrics": {"leverage_estimate": 2.0},
            "position_concentration": {"largest_position_pct": 20.0},
            "max_leverage": 5.0,
            "max_concentration": 25.0,
        }

        approved, reason = self.gatekeeper._validate_leverage_and_concentration(
            decision, context
        )

        assert approved is True
        assert "passed" in reason.lower()

    def test_concentration_exceeds_limit_fails(self):
        """Test that concentration exceeding limit fails validation."""
        decision = {
            "asset_pair": "EURUSD",
            "action": "BUY",
        }
        context = {
            "risk_metrics": {"leverage_estimate": 2.0},
            "position_concentration": {"largest_position_pct": 30.0},
            "max_leverage": 5.0,
            "max_concentration": 25.0,
        }

        approved, reason = self.gatekeeper._validate_leverage_and_concentration(
            decision, context
        )

        assert approved is False
        assert "30" in reason
        assert "25" in reason
        assert "position" in reason.lower()  # Changed from "concentration"

    def test_defaults_when_thresholds_not_provided(self):
        """Test that default thresholds are used when not provided in context."""
        decision = {
            "asset_pair": "BTCUSD",
            "action": "BUY",
        }
        context = {
            "risk_metrics": {"leverage_estimate": 3.0},
            "position_concentration": {"largest_position_pct": 15.0},
        }

        approved, reason = self.gatekeeper._validate_leverage_and_concentration(
            decision, context
        )

        # Should pass with defaults (max_leverage=5.0, max_concentration=25.0)
        assert approved is True

    def test_missing_risk_metrics_passes(self):
        """Test that missing risk metrics doesn't fail validation."""
        decision = {
            "asset_pair": "BTCUSD",
            "action": "BUY",
        }
        context = {
            "max_leverage": 5.0,
            "max_concentration": 25.0,
        }

        approved, reason = self.gatekeeper._validate_leverage_and_concentration(
            decision, context
        )

        # Should pass if no risk metrics provided (no leverage to check)
        assert approved is True

    def test_zero_leverage_passes(self):
        """Test that zero leverage passes validation."""
        decision = {
            "asset_pair": "BTCUSD",
            "action": "BUY",
        }
        context = {
            "risk_metrics": {"leverage_estimate": 0},
            "position_concentration": {"largest_position_pct": 10.0},
            "max_leverage": 5.0,
            "max_concentration": 25.0,
        }

        approved, reason = self.gatekeeper._validate_leverage_and_concentration(
            decision, context
        )

        assert approved is True

    def test_forex_asset_with_high_leverage_fails(self):
        """Test that forex assets respect leverage limits."""
        decision = {
            "asset_pair": "EURUSD",
            "action": "BUY",
        }
        context = {
            "risk_metrics": {"leverage_estimate": 7.0},
            "position_concentration": {"largest_position_pct": 10.0},
            "max_leverage": 5.0,
            "max_concentration": 25.0,
        }

        approved, reason = self.gatekeeper._validate_leverage_and_concentration(
            decision, context
        )

        assert approved is False
        assert "leverage" in reason.lower()


class TestRiskGatekeeperWithLeverageCheck:
    """Test that validate_trade now includes leverage/concentration checks."""

    def setup_method(self):
        """Set up test fixtures."""
        self.gatekeeper = RiskGatekeeper()

    def test_validate_trade_includes_leverage_check(self):
        """Test that validate_trade calls _validate_leverage_and_concentration."""
        decision = {
            "asset_pair": "BTCUSD",
            "action": "BUY",
            "confidence": 85,
            "volatility": 0.03,
        }
        context = {
            "recent_performance": {"total_pnl": 0.02},
            "holdings": {},
            "risk_metrics": {"leverage_estimate": 6.5},  # Exceeds default 5.0
            "position_concentration": {"largest_position_pct": 15.0},
            "max_leverage": 5.0,
            "max_concentration": 25.0,
        }

        approved, reason = self.gatekeeper.validate_trade(decision, context)

        # Should fail due to leverage
        assert approved is False
        assert "leverage" in reason.lower()

    def test_validate_trade_includes_concentration_check(self):
        """Test that validate_trade calls _validate_leverage_and_concentration."""
        decision = {
            "asset_pair": "BTCUSD",
            "action": "BUY",
            "confidence": 85,
            "volatility": 0.03,
        }
        context = {
            "recent_performance": {"total_pnl": 0.02},
            "holdings": {},
            "risk_metrics": {"leverage_estimate": 3.0},
            "position_concentration": {"largest_position_pct": 30.0},  # Exceeds 25%
            "max_leverage": 5.0,
            "max_concentration": 25.0,
        }

        approved, reason = self.gatekeeper.validate_trade(decision, context)

        # Should fail due to concentration
        assert approved is False
        assert "concentration" in reason.lower() or "position" in reason.lower()
