"""
Comprehensive tests for RiskGatekeeper module.

This test suite covers:
- Initialization with various parameters
- Market hours and data freshness validation
- Trade validation with all 7 checks:
  1. Market hours/data freshness (temporal constraints)
  2. Max drawdown check
  3. Per-platform correlation check
  4. Combined portfolio VaR check
  5. Cross-platform correlation warning
  6. Leverage and concentration check
  7. Volatility/confidence check
- Helper methods (_count_holdings_by_category, etc.)
- Edge cases and error handling

Target: Achieve 80% coverage of risk/gatekeeper.py
"""

import datetime
from unittest.mock import Mock, patch

import pytest

from finance_feedback_engine.risk.gatekeeper import RiskGatekeeper


class TestRiskGatekeeperInitialization:
    """Test RiskGatekeeper initialization."""

    def test_default_initialization(self):
        """Test initialization with default parameters."""
        gk = RiskGatekeeper()

        assert gk.max_drawdown_pct == 0.05
        assert gk.correlation_threshold == 0.7
        assert gk.max_correlated_assets == 2
        assert gk.max_var_pct == 0.05
        assert gk.var_confidence == 0.95
        assert gk.is_backtest is False

    def test_custom_initialization(self):
        """Test initialization with custom parameters."""
        gk = RiskGatekeeper(
            max_drawdown_pct=0.10,
            correlation_threshold=0.8,
            max_correlated_assets=3,
            max_var_pct=0.08,
            var_confidence=0.99,
            is_backtest=True,
        )

        assert gk.max_drawdown_pct == 0.10
        assert gk.correlation_threshold == 0.8
        assert gk.max_correlated_assets == 3
        assert gk.max_var_pct == 0.08
        assert gk.var_confidence == 0.99
        assert gk.is_backtest is True

    def test_metrics_initialized(self):
        """Test that Prometheus metrics are initialized."""
        gk = RiskGatekeeper()

        assert gk._meter is not None
        assert gk._metrics is not None


class TestCountHoldingsByCategory:
    """Test the _count_holdings_by_category static method."""

    def test_empty_holdings(self):
        """Test with empty holdings."""
        result = RiskGatekeeper._count_holdings_by_category({})
        assert result == {}

    def test_single_category(self):
        """Test with holdings in a single category."""
        holdings = {"BTC": "crypto", "ETH": "crypto", "SOL": "crypto"}
        result = RiskGatekeeper._count_holdings_by_category(holdings)
        assert result == {"crypto": 3}

    def test_multiple_categories(self):
        """Test with holdings in multiple categories."""
        holdings = {
            "BTC": "crypto",
            "ETH": "crypto",
            "EUR_USD": "forex",
            "GBP_USD": "forex",
            "AAPL": "stocks",
        }
        result = RiskGatekeeper._count_holdings_by_category(holdings)
        assert result == {"crypto": 2, "forex": 2, "stocks": 1}


class TestCheckMarketHours:
    """Test the check_market_hours method."""

    def test_crypto_market_always_open(self):
        """Test that crypto markets are always considered open."""
        gk = RiskGatekeeper()
        decision = {
            "action": "BUY",
            "asset_pair": "BTCUSD",
            "market_data": {
                "market_status": {"is_open": False, "session": "Closed"},
                "asset_type": "crypto",
                "data_freshness": {"is_fresh": True},
            },
        }

        needs_override, modified = gk.check_market_hours(decision)

        # Crypto should NOT be overridden even if market_status says closed
        assert needs_override is False
        assert modified["action"] == "BUY"

    def test_forex_market_closed_override(self):
        """Test that non-crypto markets are blocked when closed."""
        gk = RiskGatekeeper()
        decision = {
            "action": "BUY",
            "asset_pair": "EURUSD",
            "reasoning": "Original reasoning",
            "market_data": {
                "market_status": {"is_open": False, "session": "Weekend"},
                "asset_type": "forex",
                "data_freshness": {"is_fresh": True},
            },
        }

        needs_override, modified = gk.check_market_hours(decision)

        assert needs_override is True
        assert modified["action"] == "HOLD"
        assert modified["suggested_amount"] == 0
        assert "BLOCKED BY GATEKEEPER" in modified["reasoning"]
        assert "Market is Closed" in modified["reasoning"]

    def test_stale_data_override_live_mode(self):
        """Test that stale data blocks trades in live mode."""
        gk = RiskGatekeeper(is_backtest=False)
        decision = {
            "action": "BUY",
            "asset_pair": "BTCUSD",
            "reasoning": "Original reasoning",
            "market_data": {
                "market_status": {"is_open": True},
                "asset_type": "crypto",
                "data_freshness": {
                    "is_fresh": False,
                    "age_minutes": "45 minutes",
                    "message": "Data is outdated",
                },
            },
        }

        needs_override, modified = gk.check_market_hours(decision)

        assert needs_override is True
        assert modified["action"] == "HOLD"
        assert "BLOCKED BY GATEKEEPER" in modified["reasoning"]
        assert "Data is Stale" in modified["reasoning"]

    def test_stale_data_allowed_in_backtest_mode(self):
        """Test that stale data is allowed in backtest mode."""
        gk = RiskGatekeeper(is_backtest=True)
        decision = {
            "action": "BUY",
            "asset_pair": "BTCUSD",
            "market_data": {
                "market_status": {"is_open": True},
                "asset_type": "crypto",
                "data_freshness": {"is_fresh": False, "age_minutes": "45 minutes"},
            },
        }

        needs_override, modified = gk.check_market_hours(decision)

        # Backtest mode should NOT override stale data
        assert needs_override is False
        assert modified["action"] == "BUY"

    def test_hold_action_not_overridden(self):
        """Test that HOLD actions are not overridden."""
        gk = RiskGatekeeper()
        decision = {
            "action": "HOLD",
            "asset_pair": "BTCUSD",
            "market_data": {
                "market_status": {"is_open": False, "session": "Closed"},
                "asset_type": "forex",
                "data_freshness": {"is_fresh": False},
            },
        }

        needs_override, modified = gk.check_market_hours(decision)

        # HOLD should not be overridden
        assert needs_override is False


class TestValidateTradeMaxDrawdown:
    """Test max drawdown validation."""

    def test_max_drawdown_passed(self):
        """Test that trade is allowed when drawdown is within limit."""
        gk = RiskGatekeeper(max_drawdown_pct=0.05)
        decision = {"action": "BUY", "asset_pair": "BTCUSD", "confidence": 85}
        context = {
            "recent_performance": {"total_pnl": -0.03},  # -3% (within -5% limit)
            "asset_type": "crypto",
        }

        with patch.object(gk, "check_market_hours", return_value=(False, decision)):
            allowed, message = gk.validate_trade(decision, context)

        assert allowed is True
        assert "approved" in message.lower()

    def test_max_drawdown_exceeded(self):
        """Test that trade is blocked when drawdown exceeds limit."""
        gk = RiskGatekeeper(max_drawdown_pct=0.05)
        decision = {"action": "BUY", "asset_pair": "BTCUSD", "confidence": 85}
        context = {
            "recent_performance": {"total_pnl": -0.08},  # -8% (exceeds -5% limit)
            "asset_type": "crypto",
        }

        with patch.object(gk, "check_market_hours", return_value=(False, decision)):
            allowed, message = gk.validate_trade(decision, context)

        assert allowed is False
        assert "Max drawdown exceeded" in message


class TestValidateTradeCorrelation:
    """Test correlation validation."""

    def test_correlation_with_enhanced_analysis(self):
        """Test correlation check with correlation analysis data."""
        gk = RiskGatekeeper()
        decision = {"action": "BUY", "asset_pair": "BTCUSD", "confidence": 85}
        context = {
            "recent_performance": {"total_pnl": 0},
            "correlation_analysis": {
                "coinbase": {
                    "concentration_warning": "Too many correlated assets",
                }
            },
            "asset_type": "crypto",
        }

        with patch.object(gk, "check_market_hours", return_value=(False, decision)):
            allowed, message = gk.validate_trade(decision, context)

        assert allowed is False
        assert "Correlation limit exceeded" in message

    def test_correlation_fallback_to_category_check(self):
        """Test fallback to category-based correlation check."""
        gk = RiskGatekeeper(max_correlated_assets=2)
        decision = {
            "action": "BUY",
            "asset_pair": "BTCUSD",
            "asset_category": "crypto",
            "confidence": 85,
        }
        context = {
            "recent_performance": {"total_pnl": 0},
            "holdings": {"BTC": "crypto", "ETH": "crypto"},  # Already have 2 crypto
            "asset_type": "crypto",
        }

        with patch.object(gk, "check_market_hours", return_value=(False, decision)):
            allowed, message = gk.validate_trade(decision, context)

        assert allowed is False
        assert "Correlation limit exceeded" in message

    def test_correlation_passed(self):
        """Test that correlation check passes with few holdings."""
        gk = RiskGatekeeper(max_correlated_assets=3)
        decision = {
            "action": "BUY",
            "asset_pair": "BTCUSD",
            "asset_category": "crypto",
            "confidence": 85,
        }
        context = {
            "recent_performance": {"total_pnl": 0},
            "holdings": {"BTC": "crypto"},  # Only 1 crypto, limit is 3
            "asset_type": "crypto",
        }

        with patch.object(gk, "check_market_hours", return_value=(False, decision)):
            allowed, message = gk.validate_trade(decision, context)

        assert allowed is True


class TestValidateTradeVaR:
    """Test VaR validation."""

    def test_var_exceeded(self):
        """Test that trade is blocked when VaR exceeds limit."""
        gk = RiskGatekeeper(max_var_pct=0.05)
        decision = {"action": "BUY", "asset_pair": "BTCUSD", "confidence": 85}
        context = {
            "recent_performance": {"total_pnl": 0},
            "var_analysis": {
                "combined_var": {"var": 0.08}  # 8% VaR (exceeds 5% limit)
            },
            "asset_type": "crypto",
        }

        with patch.object(gk, "check_market_hours", return_value=(False, decision)):
            allowed, message = gk.validate_trade(decision, context)

        assert allowed is False
        assert "Portfolio VaR limit exceeded" in message

    def test_var_passed(self):
        """Test that trade is allowed when VaR is within limit."""
        gk = RiskGatekeeper(max_var_pct=0.05)
        decision = {"action": "BUY", "asset_pair": "BTCUSD", "confidence": 85}
        context = {
            "recent_performance": {"total_pnl": 0},
            "var_analysis": {
                "combined_var": {"var": 0.03}  # 3% VaR (within 5% limit)
            },
            "asset_type": "crypto",
        }

        with patch.object(gk, "check_market_hours", return_value=(False, decision)):
            allowed, message = gk.validate_trade(decision, context)

        assert allowed is True

    def test_var_skipped_when_no_analysis(self):
        """Test that VaR check is skipped when no analysis available."""
        gk = RiskGatekeeper()
        decision = {"action": "BUY", "asset_pair": "BTCUSD", "confidence": 85}
        context = {
            "recent_performance": {"total_pnl": 0},
            # No var_analysis provided
            "asset_type": "crypto",
        }

        with patch.object(gk, "check_market_hours", return_value=(False, decision)):
            allowed, message = gk.validate_trade(decision, context)

        # Should pass since VaR check is skipped
        assert allowed is True


class TestValidateLeverageAndConcentration:
    """Test leverage and concentration validation."""

    def test_leverage_exceeded(self):
        """Test that trade is blocked when leverage exceeds limit."""
        gk = RiskGatekeeper()
        decision = {"action": "BUY", "asset_pair": "BTCUSD", "confidence": 85}
        context = {
            "recent_performance": {"total_pnl": 0},
            "risk_metrics": {"leverage_estimate": 6.0},  # Exceeds default max of 5.0
            "max_leverage": 5.0,
            "asset_type": "crypto",
        }

        with patch.object(gk, "check_market_hours", return_value=(False, decision)):
            allowed, message = gk.validate_trade(decision, context)

        assert allowed is False
        assert "Leverage" in message

    def test_concentration_exceeded(self):
        """Test that trade is blocked when concentration exceeds limit."""
        gk = RiskGatekeeper()
        decision = {"action": "BUY", "asset_pair": "BTCUSD", "confidence": 85}
        context = {
            "recent_performance": {"total_pnl": 0},
            "position_concentration": {
                "largest_position_pct": 30.0  # Exceeds default max of 25%
            },
            "max_concentration": 25.0,
            "asset_type": "crypto",
        }

        with patch.object(gk, "check_market_hours", return_value=(False, decision)):
            allowed, message = gk.validate_trade(decision, context)

        assert allowed is False
        assert "position" in message.lower()

    def test_leverage_and_concentration_passed(self):
        """Test that trade passes when both are within limits."""
        gk = RiskGatekeeper()
        decision = {"action": "BUY", "asset_pair": "BTCUSD", "confidence": 85}
        context = {
            "recent_performance": {"total_pnl": 0},
            "risk_metrics": {"leverage_estimate": 2.0},
            "position_concentration": {"largest_position_pct": 15.0},
            "asset_type": "crypto",
        }

        with patch.object(gk, "check_market_hours", return_value=(False, decision)):
            allowed, message = gk.validate_trade(decision, context)

        assert allowed is True


class TestValidateTradeVolatilityConfidence:
    """Test volatility/confidence validation."""

    def test_high_volatility_low_confidence_blocked(self):
        """Test that trade is blocked with high volatility and low confidence."""
        gk = RiskGatekeeper()
        decision = {
            "action": "BUY",
            "asset_pair": "BTCUSD",
            "volatility": 0.08,  # >5%
            "confidence": 70,  # <80%
        }
        context = {"recent_performance": {"total_pnl": 0}, "asset_type": "crypto"}

        with patch.object(gk, "check_market_hours", return_value=(False, decision)):
            allowed, message = gk.validate_trade(decision, context)

        assert allowed is False
        assert "Volatility/confidence threshold exceeded" in message

    def test_high_volatility_high_confidence_allowed(self):
        """Test that trade is allowed with high volatility but high confidence."""
        gk = RiskGatekeeper()
        decision = {
            "action": "BUY",
            "asset_pair": "BTCUSD",
            "volatility": 0.08,  # >5%
            "confidence": 85,  # >80%
        }
        context = {"recent_performance": {"total_pnl": 0}, "asset_type": "crypto"}

        with patch.object(gk, "check_market_hours", return_value=(False, decision)):
            allowed, message = gk.validate_trade(decision, context)

        assert allowed is True

    def test_low_volatility_low_confidence_allowed(self):
        """Test that trade is allowed with low volatility regardless of confidence."""
        gk = RiskGatekeeper()
        decision = {
            "action": "BUY",
            "asset_pair": "BTCUSD",
            "volatility": 0.02,  # <5%
            "confidence": 60,  # <80%
        }
        context = {"recent_performance": {"total_pnl": 0}, "asset_type": "crypto"}

        with patch.object(gk, "check_market_hours", return_value=(False, decision)):
            allowed, message = gk.validate_trade(decision, context)

        assert allowed is True

    def test_invalid_confidence_defaults_to_zero(self):
        """Test that invalid confidence values default to 0."""
        gk = RiskGatekeeper()
        decision = {
            "action": "BUY",
            "asset_pair": "BTCUSD",
            "volatility": 0.08,
            "confidence": "invalid",  # Invalid type
        }
        context = {"recent_performance": {"total_pnl": 0}, "asset_type": "crypto"}

        with patch.object(gk, "check_market_hours", return_value=(False, decision)):
            allowed, message = gk.validate_trade(decision, context)

        # With confidence=0 and high volatility, should be blocked
        assert allowed is False


class TestMarketScheduleValidation:
    """Test market schedule validation."""

    @patch("finance_feedback_engine.risk.gatekeeper.MarketSchedule.get_market_status")
    def test_market_closed_for_stocks(self, mock_market_status):
        """Test that stocks are blocked when market is closed."""
        mock_market_status.return_value = {
            "is_open": False,
            "session": "After Hours",
            "warning": None,
        }

        gk = RiskGatekeeper()
        decision = {"action": "BUY", "asset_pair": "AAPL", "confidence": 85}
        context = {"asset_type": "stocks", "recent_performance": {"total_pnl": 0}}

        with patch.object(gk, "check_market_hours", return_value=(False, decision)):
            allowed, message = gk.validate_trade(decision, context)

        assert allowed is False
        assert "Market closed" in message

    @patch("finance_feedback_engine.risk.gatekeeper.MarketSchedule.get_market_status")
    def test_forex_not_blocked_when_closed(self, mock_market_status):
        """Test that forex trades are not hard-blocked when market is closed."""
        mock_market_status.return_value = {
            "is_open": False,
            "session": "Weekend",
            "warning": "Reduced liquidity",
        }

        gk = RiskGatekeeper()
        decision = {"action": "BUY", "asset_pair": "EURUSD", "confidence": 85}
        context = {"asset_type": "forex", "recent_performance": {"total_pnl": 0}}

        with patch.object(gk, "check_market_hours", return_value=(False, decision)):
            allowed, message = gk.validate_trade(decision, context)

        # Forex should not be hard-blocked
        assert allowed is True

    @patch(
        "finance_feedback_engine.risk.gatekeeper.MarketSchedule.get_market_status_at_timestamp"
    )
    def test_timestamp_parsing_in_backtest_mode(self, mock_market_status_timestamp):
        """Test timestamp parsing in backtest mode."""
        mock_market_status_timestamp.return_value = {
            "is_open": True,
            "session": "Regular Hours",
            "warning": None,
        }

        gk = RiskGatekeeper(is_backtest=True)
        decision = {"action": "BUY", "asset_pair": "BTCUSD", "confidence": 85}
        context = {
            "timestamp": "2024-01-15T14:30:00",
            "asset_type": "crypto",
            "recent_performance": {"total_pnl": 0},
        }

        with patch.object(gk, "check_market_hours", return_value=(False, decision)):
            allowed, message = gk.validate_trade(decision, context)

        assert allowed is True
        assert mock_market_status_timestamp.called

    def test_timestamp_parsing_error_in_backtest_raises(self):
        """Test that timestamp parsing errors raise in backtest mode."""
        gk = RiskGatekeeper(is_backtest=True)
        decision = {"action": "BUY", "asset_pair": "BTCUSD", "confidence": 85}
        context = {
            "timestamp": "invalid_timestamp",
            "asset_type": "crypto",
            "recent_performance": {"total_pnl": 0},
        }

        with patch.object(gk, "check_market_hours", return_value=(False, decision)):
            with pytest.raises(ValueError, match="Failed to parse timestamp"):
                gk.validate_trade(decision, context)


class TestDataFreshnessValidation:
    """Test data freshness validation."""

    @patch("finance_feedback_engine.risk.gatekeeper.validate_data_freshness")
    def test_stale_data_rejected_in_live_mode(self, mock_validate_freshness):
        """Test that stale data is rejected in live mode."""
        mock_validate_freshness.return_value = (
            False,
            "30 minutes",
            "Data is too old",
        )

        gk = RiskGatekeeper(is_backtest=False)
        decision = {"action": "BUY", "asset_pair": "BTCUSD", "confidence": 85}
        context = {
            "market_data_timestamp": "2024-01-15T14:00:00",
            "asset_type": "crypto",
            "recent_performance": {"total_pnl": 0},
        }

        with patch.object(gk, "check_market_hours", return_value=(False, decision)):
            allowed, message = gk.validate_trade(decision, context)

        assert allowed is False
        assert "Stale market data" in message

    @patch("finance_feedback_engine.risk.gatekeeper.validate_data_freshness")
    def test_data_freshness_skipped_in_backtest(self, mock_validate_freshness):
        """Test that data freshness is skipped in backtest mode."""
        gk = RiskGatekeeper(is_backtest=True)
        decision = {"action": "BUY", "asset_pair": "BTCUSD", "confidence": 85}
        context = {
            "market_data_timestamp": "2024-01-15T14:00:00",
            "asset_type": "crypto",
            "recent_performance": {"total_pnl": 0},
        }

        with patch.object(gk, "check_market_hours", return_value=(False, decision)):
            allowed, message = gk.validate_trade(decision, context)

        # Freshness check should be skipped in backtest
        assert not mock_validate_freshness.called
        assert allowed is True


class TestCrossPlatformCorrelation:
    """Test cross-platform correlation warning."""

    def test_cross_platform_correlation_warning_logged(self, caplog):
        """Test that cross-platform correlation warnings are logged."""
        gk = RiskGatekeeper()
        decision = {"action": "BUY", "asset_pair": "BTCUSD", "confidence": 85}
        context = {
            "recent_performance": {"total_pnl": 0},
            "correlation_analysis": {
                "cross_platform": {
                    "warning": "High correlation between Coinbase and Oanda"
                }
            },
            "asset_type": "crypto",
        }

        with patch.object(gk, "check_market_hours", return_value=(False, decision)):
            allowed, message = gk.validate_trade(decision, context)

        # Trade should still be allowed (warning-only)
        assert allowed is True
        # Check that warning was logged
        assert any("Cross-platform correlation" in rec.message for rec in caplog.records)


class TestCompleteValidationFlow:
    """Test complete validation flow with all checks."""

    def test_all_checks_passed(self):
        """Test that trade passes when all checks are satisfied."""
        gk = RiskGatekeeper()
        decision = {
            "action": "BUY",
            "asset_pair": "BTCUSD",
            "confidence": 85,
            "volatility": 0.03,
        }
        context = {
            "recent_performance": {"total_pnl": 0.02},  # Positive performance
            "asset_type": "crypto",
            "holdings": {},  # No existing holdings
            "var_analysis": {"combined_var": {"var": 0.02}},  # Low VaR
            "risk_metrics": {"leverage_estimate": 1.5},  # Low leverage
            "position_concentration": {"largest_position_pct": 10.0},  # Low concentration
        }

        with patch.object(gk, "check_market_hours", return_value=(False, decision)):
            allowed, message = gk.validate_trade(decision, context)

        assert allowed is True
        assert "approved" in message.lower()

    def test_first_failed_check_stops_validation(self):
        """Test that validation stops at first failed check."""
        gk = RiskGatekeeper(max_drawdown_pct=0.05)
        decision = {
            "action": "BUY",
            "asset_pair": "BTCUSD",
            "confidence": 85,
            "volatility": 0.10,  # This would fail volatility check
        }
        context = {
            "recent_performance": {"total_pnl": -0.10},  # Fails drawdown check first
            "asset_type": "crypto",
        }

        with patch.object(gk, "check_market_hours", return_value=(False, decision)):
            allowed, message = gk.validate_trade(decision, context)

        # Should fail on drawdown, not reach volatility check
        assert allowed is False
        assert "Max drawdown exceeded" in message


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
