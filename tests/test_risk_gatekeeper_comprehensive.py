"""Comprehensive tests for RiskGatekeeper module."""

from unittest.mock import patch

import pytest

from finance_feedback_engine.risk.gatekeeper import RiskGatekeeper


@pytest.fixture
def risk_gatekeeper():
    """Create a risk gatekeeper instance for testing."""
    return RiskGatekeeper(
        max_drawdown_pct=0.05,
        correlation_threshold=0.7,
        max_correlated_assets=2,
        max_var_pct=0.05,
        var_confidence=0.95,
        is_backtest=False,
    )


class TestRiskGatekeeperInitialization:
    """Tests for RiskGatekeeper initialization."""

    def test_default_initialization(self):
        """Test gatekeeper initializes with default values."""
        gatekeeper = RiskGatekeeper()
        assert gatekeeper.max_drawdown_pct == 0.05
        assert gatekeeper.correlation_threshold == 0.7
        assert gatekeeper.max_correlated_assets == 2
        assert gatekeeper.max_var_pct == 0.05
        assert gatekeeper.var_confidence == 0.95
        assert gatekeeper.is_backtest is False

    def test_custom_initialization(self):
        """Test gatekeeper initializes with custom values."""
        gatekeeper = RiskGatekeeper(
            max_drawdown_pct=0.10,
            correlation_threshold=0.8,
            max_correlated_assets=3,
            max_var_pct=0.08,
            var_confidence=0.99,
            is_backtest=True,
        )
        assert gatekeeper.max_drawdown_pct == 0.10
        assert gatekeeper.correlation_threshold == 0.8
        assert gatekeeper.max_correlated_assets == 3
        assert gatekeeper.max_var_pct == 0.08
        assert gatekeeper.var_confidence == 0.99
        assert gatekeeper.is_backtest is True


class TestCountHoldingsByCategory:
    """Tests for _count_holdings_by_category static method."""

    def test_empty_holdings(self):
        """Test counting with no holdings."""
        result = RiskGatekeeper._count_holdings_by_category({})
        assert result == {}

    def test_single_category(self):
        """Test counting with single category."""
        holdings = {"BTC": "crypto", "ETH": "crypto", "SOL": "crypto"}
        result = RiskGatekeeper._count_holdings_by_category(holdings)
        assert result == {"crypto": 3}

    def test_multiple_categories(self):
        """Test counting with multiple categories."""
        holdings = {
            "BTC": "crypto",
            "ETH": "crypto",
            "EUR_USD": "forex",
            "GBP_JPY": "forex",
            "AAPL": "stock",
        }
        result = RiskGatekeeper._count_holdings_by_category(holdings)
        assert result == {"crypto": 2, "forex": 2, "stock": 1}


class TestMarketHoursCheck:
    """Tests for market hours checking."""

    def test_no_market_status_no_override(self, risk_gatekeeper):
        """Decision without market status should not be overridden."""
        decision = {"action": "BUY", "asset_pair": "BTCUSD"}
        needs_override, modified = risk_gatekeeper.check_market_hours(decision)
        assert needs_override is False
        assert modified == decision

    def test_crypto_market_open_no_override(self, risk_gatekeeper):
        """Crypto asset should not check market hours (24/7)."""
        decision = {
            "action": "BUY",
            "asset_pair": "BTCUSD",
            "market_data": {
                "market_status": {
                    "is_open": False,  # Even if marked closed
                    "session": "closed",
                },
                "asset_type": "crypto",
            },
        }
        needs_override, modified = risk_gatekeeper.check_market_hours(decision)
        # Crypto markets are 24/7, so no override even when closed
        assert needs_override is False
        assert modified["action"] == "BUY"

    def test_stock_market_closed_overrides_to_hold(self, risk_gatekeeper):
        """Closed stock market should override BUY/SELL to HOLD."""
        decision = {
            "action": "BUY",
            "asset_pair": "AAPL",
            "market_data": {
                "market_status": {"is_open": False, "session": "closed"},
                "asset_type": "stock",  # Non-crypto asset
            },
        }
        needs_override, modified = risk_gatekeeper.check_market_hours(decision)
        assert needs_override is True
        assert modified["action"] == "HOLD"
        assert "BLOCKED BY GATEKEEPER" in modified["reasoning"]

    def test_forex_market_closed_overrides_to_hold(self, risk_gatekeeper):
        """Closed forex market should override BUY/SELL to HOLD."""
        decision = {
            "action": "SELL",
            "asset_pair": "EUR_USD",
            "market_data": {
                "market_status": {"is_open": False, "session": "closed"},
                "asset_type": "forex",
            },
        }
        needs_override, modified = risk_gatekeeper.check_market_hours(decision)
        assert needs_override is True
        assert modified["action"] == "HOLD"

    def test_hold_action_not_overridden_when_closed(self, risk_gatekeeper):
        """HOLD action should not be overridden even when market closed."""
        decision = {
            "action": "HOLD",
            "asset_pair": "AAPL",
            "market_data": {"market_status": {"is_open": False}, "asset_type": "stock"},
        }
        needs_override, modified = risk_gatekeeper.check_market_hours(decision)
        assert needs_override is False
        assert modified["action"] == "HOLD"

    def test_stale_data_overrides_to_hold(self, risk_gatekeeper):
        """Stale data should override BUY/SELL to HOLD in live mode."""
        decision = {
            "action": "BUY",
            "asset_pair": "BTCUSD",
            "market_data": {
                "data_freshness": {
                    "is_fresh": False,
                    "message": "Data is 45 minutes old",
                    "age_minutes": 45,
                }
            },
        }
        needs_override, modified = risk_gatekeeper.check_market_hours(decision)
        assert needs_override is True
        assert modified["action"] == "HOLD"
        assert "Data is Stale" in modified["reasoning"]

    def test_backtest_mode_ignores_stale_data(self):
        """Backtest mode should not block on stale data."""
        gatekeeper = RiskGatekeeper(is_backtest=True)
        decision = {
            "action": "BUY",
            "asset_pair": "BTCUSD",
            "market_data": {
                "data_freshness": {
                    "is_fresh": False,
                    "message": "Historical data",
                    "age_minutes": 1440,  # 1 day old
                }
            },
        }
        needs_override, modified = gatekeeper.check_market_hours(decision)
        # Backtest mode ignores stale data checks
        assert needs_override is False


class TestValidateTradeDrawdown:
    """Tests for drawdown validation within validate_trade."""

    @patch("finance_feedback_engine.risk.gatekeeper.MarketSchedule")
    def test_small_drawdown_passes(self, mock_schedule, risk_gatekeeper):
        """Small drawdown (3%) should pass validation."""
        mock_schedule.get_market_status.return_value = {
            "is_open": True,
            "warning": None,
        }

        decision = {
            "action": "BUY",
            "asset_pair": "BTCUSD",
            "asset_category": "crypto",
            "volatility": 0.02,
            "confidence": 85,
        }
        context = {
            "asset_type": "crypto",
            "recent_performance": {"total_pnl": -0.03},  # -3% drawdown
            "holdings": {},
        }

        passed, message = risk_gatekeeper.validate_trade(decision, context)
        assert passed is True

    @patch("finance_feedback_engine.risk.gatekeeper.MarketSchedule")
    def test_large_drawdown_fails(self, mock_schedule, risk_gatekeeper):
        """Large drawdown (6% > 5% limit) should fail validation."""
        mock_schedule.get_market_status.return_value = {
            "is_open": True,
            "warning": None,
        }

        decision = {
            "action": "BUY",
            "asset_pair": "BTCUSD",
            "asset_category": "crypto",
            "volatility": 0.02,
            "confidence": 85,
        }
        context = {
            "asset_type": "crypto",
            "recent_performance": {"total_pnl": -0.06},  # -6% drawdown
            "holdings": {},
        }

        passed, message = risk_gatekeeper.validate_trade(decision, context)
        assert passed is False
        assert "drawdown" in message.lower()


class TestValidateTradeCorrelation:
    """Tests for correlation validation within validate_trade."""

    @patch("finance_feedback_engine.risk.gatekeeper.MarketSchedule")
    def test_low_correlation_passes(self, mock_schedule, risk_gatekeeper):
        """Low correlations should pass validation."""
        mock_schedule.get_market_status.return_value = {
            "is_open": True,
            "warning": None,
        }

        decision = {
            "action": "BUY",
            "asset_pair": "BTCUSD",
            "asset_category": "crypto",
            "platform": "coinbase",
            "volatility": 0.02,
            "confidence": 85,
        }
        context = {
            "asset_type": "crypto",
            "recent_performance": {"total_pnl": 0.01},
            "holdings": {"BTC": "crypto"},  # Only 1 crypto holding
            "correlation_analysis": {
                "coinbase": {"concentration_warning": None}  # No warning
            },
        }

        passed, message = risk_gatekeeper.validate_trade(decision, context)
        assert passed is True

    @patch("finance_feedback_engine.risk.gatekeeper.MarketSchedule")
    def test_high_correlation_fails(self, mock_schedule, risk_gatekeeper):
        """High correlations should fail validation."""
        mock_schedule.get_market_status.return_value = {
            "is_open": True,
            "warning": None,
        }

        decision = {
            "action": "BUY",
            "asset_pair": "SOLUSD",
            "asset_category": "crypto",
            "platform": "coinbase",
            "volatility": 0.02,
            "confidence": 85,
        }
        context = {
            "asset_type": "crypto",
            "recent_performance": {"total_pnl": 0.01},
            "holdings": {"BTC": "crypto", "ETH": "crypto"},
            "correlation_analysis": {
                "coinbase": {
                    "concentration_warning": "Too many correlated crypto assets (>2)"
                }
            },
        }

        passed, message = risk_gatekeeper.validate_trade(decision, context)
        assert passed is False
        assert "correlation" in message.lower()

    @patch("finance_feedback_engine.risk.gatekeeper.MarketSchedule")
    def test_legacy_correlation_check_without_analysis(
        self, mock_schedule, risk_gatekeeper
    ):
        """Legacy correlation check should work without correlation_analysis."""
        mock_schedule.get_market_status.return_value = {
            "is_open": True,
            "warning": None,
        }

        decision = {
            "action": "BUY",
            "asset_pair": "SOLUSD",
            "asset_category": "crypto",
            "volatility": 0.02,
            "confidence": 85,
        }
        context = {
            "asset_type": "crypto",
            "recent_performance": {"total_pnl": 0.01},
            "holdings": {"BTC": "crypto", "ETH": "crypto"},  # Already at limit of 2
        }

        passed, message = risk_gatekeeper.validate_trade(decision, context)
        # Should fail because we already have 2 crypto holdings (max_correlated_assets=2)
        assert passed is False
        assert "correlation" in message.lower()


class TestValidateTradeVaR:
    """Tests for Value-at-Risk validation within validate_trade."""

    @patch("finance_feedback_engine.risk.gatekeeper.MarketSchedule")
    def test_var_under_limit_passes(self, mock_schedule, risk_gatekeeper):
        """VaR under limit should pass validation."""
        mock_schedule.get_market_status.return_value = {
            "is_open": True,
            "warning": None,
        }

        decision = {
            "action": "BUY",
            "asset_pair": "BTCUSD",
            "asset_category": "crypto",
            "volatility": 0.02,
            "confidence": 85,
        }
        context = {
            "asset_type": "crypto",
            "recent_performance": {"total_pnl": 0.01},
            "holdings": {},
            "var_analysis": {"combined_var": {"var": 0.04}},  # 4% VaR (under 5% limit)
        }

        passed, message = risk_gatekeeper.validate_trade(decision, context)
        assert passed is True

    @patch("finance_feedback_engine.risk.gatekeeper.MarketSchedule")
    def test_var_exceeds_limit_fails(self, mock_schedule, risk_gatekeeper):
        """VaR over limit (6% > 5%) should fail validation."""
        mock_schedule.get_market_status.return_value = {
            "is_open": True,
            "warning": None,
        }

        decision = {
            "action": "BUY",
            "asset_pair": "BTCUSD",
            "asset_category": "crypto",
            "volatility": 0.02,
            "confidence": 85,
        }
        context = {
            "asset_type": "crypto",
            "recent_performance": {"total_pnl": 0.01},
            "holdings": {},
            "var_analysis": {
                "combined_var": {"var": 0.06}  # 6% VaR (exceeds 5% limit)
            },
        }

        passed, message = risk_gatekeeper.validate_trade(decision, context)
        assert passed is False
        assert "var" in message.lower()

    @patch("finance_feedback_engine.risk.gatekeeper.MarketSchedule")
    def test_no_var_analysis_skips_check(self, mock_schedule, risk_gatekeeper):
        """Missing VaR analysis should skip VaR check."""
        mock_schedule.get_market_status.return_value = {
            "is_open": True,
            "warning": None,
        }

        decision = {
            "action": "BUY",
            "asset_pair": "BTCUSD",
            "asset_category": "crypto",
            "volatility": 0.02,
            "confidence": 85,
        }
        context = {
            "asset_type": "crypto",
            "recent_performance": {"total_pnl": 0.01},
            "holdings": {},
            # No var_analysis provided
        }

        passed, message = risk_gatekeeper.validate_trade(decision, context)
        assert passed is True  # VaR check skipped


class TestValidateTradeVolatilityConfidence:
    """Tests for volatility/confidence validation within validate_trade."""

    @patch("finance_feedback_engine.risk.gatekeeper.MarketSchedule")
    def test_low_volatility_high_confidence_passes(
        self, mock_schedule, risk_gatekeeper
    ):
        """Low volatility + high confidence should pass."""
        mock_schedule.get_market_status.return_value = {
            "is_open": True,
            "warning": None,
        }

        decision = {
            "action": "BUY",
            "asset_pair": "BTCUSD",
            "asset_category": "crypto",
            "volatility": 0.02,  # Low volatility
            "confidence": 90,  # High confidence
        }
        context = {
            "asset_type": "crypto",
            "recent_performance": {"total_pnl": 0.01},
            "holdings": {},
        }

        passed, message = risk_gatekeeper.validate_trade(decision, context)
        assert passed is True

    @patch("finance_feedback_engine.risk.gatekeeper.MarketSchedule")
    def test_high_volatility_low_confidence_fails(self, mock_schedule, risk_gatekeeper):
        """High volatility + low confidence should fail."""
        mock_schedule.get_market_status.return_value = {
            "is_open": True,
            "warning": None,
        }

        decision = {
            "action": "BUY",
            "asset_pair": "BTCUSD",
            "asset_category": "crypto",
            "volatility": 0.06,  # High volatility (>5%)
            "confidence": 75,  # Low confidence (<80%)
        }
        context = {
            "asset_type": "crypto",
            "recent_performance": {"total_pnl": 0.01},
            "holdings": {},
        }

        passed, message = risk_gatekeeper.validate_trade(decision, context)
        assert passed is False
        assert "volatility" in message.lower() or "confidence" in message.lower()

    @patch("finance_feedback_engine.risk.gatekeeper.MarketSchedule")
    def test_high_volatility_high_confidence_passes(
        self, mock_schedule, risk_gatekeeper
    ):
        """High volatility with high confidence should pass."""
        mock_schedule.get_market_status.return_value = {
            "is_open": True,
            "warning": None,
        }

        decision = {
            "action": "BUY",
            "asset_pair": "BTCUSD",
            "asset_category": "crypto",
            "volatility": 0.06,  # High volatility
            "confidence": 90,  # High confidence (>80%)
        }
        context = {
            "asset_type": "crypto",
            "recent_performance": {"total_pnl": 0.01},
            "holdings": {},
        }

        passed, message = risk_gatekeeper.validate_trade(decision, context)
        assert passed is True


class TestValidateTradeMarketSchedule:
    """Tests for market schedule validation within validate_trade."""

    @patch("finance_feedback_engine.risk.gatekeeper.MarketSchedule")
    def test_market_open_passes(self, mock_schedule, risk_gatekeeper):
        """Open market should pass validation."""
        mock_schedule.get_market_status.return_value = {
            "is_open": True,
            "warning": None,
            "session": "regular",
        }

        decision = {
            "action": "BUY",
            "asset_pair": "AAPL",
            "asset_category": "stock",
            "volatility": 0.02,
            "confidence": 85,
        }
        context = {
            "asset_type": "stock",
            "recent_performance": {"total_pnl": 0.01},
            "holdings": {},
        }

        passed, message = risk_gatekeeper.validate_trade(decision, context)
        assert passed is True

    @patch("finance_feedback_engine.risk.gatekeeper.MarketSchedule")
    def test_market_closed_fails(self, mock_schedule, risk_gatekeeper):
        """Closed market should fail validation."""
        mock_schedule.get_market_status.return_value = {
            "is_open": False,
            "warning": None,
            "session": "closed",
        }

        decision = {
            "action": "BUY",
            "asset_pair": "AAPL",
            "asset_category": "stock",
            "volatility": 0.02,
            "confidence": 85,
        }
        context = {
            "asset_type": "stock",
            "recent_performance": {"total_pnl": 0.01},
            "holdings": {},
        }

        passed, message = risk_gatekeeper.validate_trade(decision, context)
        assert passed is False
        assert "closed" in message.lower()


class TestComprehensiveValidation:
    """Tests for comprehensive risk validation."""

    @patch("finance_feedback_engine.risk.gatekeeper.MarketSchedule")
    def test_all_checks_pass(self, mock_schedule, risk_gatekeeper):
        """All risk checks passing should allow decision."""
        mock_schedule.get_market_status.return_value = {
            "is_open": True,
            "warning": None,
        }

        decision = {
            "action": "BUY",
            "asset_pair": "BTCUSD",
            "asset_category": "crypto",
            "platform": "coinbase",
            "volatility": 0.02,  # Low volatility
            "confidence": 90,  # High confidence
        }
        context = {
            "asset_type": "crypto",
            "recent_performance": {"total_pnl": 0.02},  # Positive P&L
            "holdings": {},  # No holdings
            "var_analysis": {"combined_var": {"var": 0.03}},  # VaR under limit
            "correlation_analysis": {
                "coinbase": {"concentration_warning": None}  # No correlation warning
            },
        }

        passed, message = risk_gatekeeper.validate_trade(decision, context)
        assert passed is True
        assert "approved" in message.lower()

    @patch("finance_feedback_engine.risk.gatekeeper.MarketSchedule")
    def test_multiple_failures_returns_first_failure(
        self, mock_schedule, risk_gatekeeper
    ):
        """Multiple failures should return first failure encountered."""
        mock_schedule.get_market_status.return_value = {
            "is_open": False,  # Market closed
            "warning": None,
            "session": "closed",
        }

        decision = {
            "action": "BUY",
            "asset_pair": "AAPL",
            "asset_category": "stock",
            "volatility": 0.08,  # High volatility
            "confidence": 60,  # Low confidence
        }
        context = {
            "asset_type": "stock",
            "recent_performance": {"total_pnl": -0.08},  # Large drawdown
            "holdings": {"AAPL": "stock", "GOOGL": "stock"},  # At correlation limit
        }

        passed, message = risk_gatekeeper.validate_trade(decision, context)
        assert passed is False
        # Should fail on first check (market closed)
        assert "closed" in message.lower()
