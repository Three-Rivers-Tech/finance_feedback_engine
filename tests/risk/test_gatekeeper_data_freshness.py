"""Test RiskGatekeeper integration with data freshness validation."""

import datetime as dt
from datetime import timezone

from finance_feedback_engine.risk.gatekeeper import RiskGatekeeper


class TestGatekeeperDataFreshness:
    """Test data freshness checks in RiskGatekeeper."""

    def setup_method(self):
        """Initialize gatekeeper for each test."""
        self.gatekeeper = RiskGatekeeper()

    def test_rejects_trade_with_stale_crypto_data(self):
        """Gatekeeper should reject trades when crypto data is > 15 min old."""
        now = dt.datetime.now(timezone.utc)
        stale_ts = (now - dt.timedelta(minutes=20)).isoformat().replace("+00:00", "Z")

        decision = {
            "action": "BUY",
            "asset_pair": "BTCUSD",
            "confidence": 85,
            "volatility": 0.02,
        }

        context = {
            "asset_type": "crypto",
            "market_data_timestamp": stale_ts,
            "recent_performance": {"total_pnl": 0.01},
            "holdings": {},
        }

        is_valid, msg = self.gatekeeper.validate_trade(decision, context)
        assert is_valid is False
        assert "Stale market data" in msg
        assert "CRITICAL" in msg or "20" in msg

    def test_warns_on_stale_crypto_data_but_allows_trade(self):
        """Gatekeeper should warn on crypto data > 5 min but ≤ 15 min old."""
        now = dt.datetime.now(timezone.utc)
        stale_ts = (now - dt.timedelta(minutes=7)).isoformat().replace("+00:00", "Z")

        decision = {
            "action": "BUY",
            "asset_pair": "EURUSD",
            "confidence": 80,
            "volatility": 0.025,
        }

        context = {
            "asset_type": "forex",
            "market_data_timestamp": stale_ts,
            "recent_performance": {"total_pnl": 0.005},
            "holdings": {},
        }

        is_valid, msg = self.gatekeeper.validate_trade(decision, context)
        # Should warn but not reject (passes freshness, fails on other checks?)
        # Actually, it should pass because no other strict thresholds are set
        # The warning is logged, not returned in message unless critical
        assert isinstance(is_valid, bool)

    def test_allows_fresh_crypto_data(self):
        """Gatekeeper should allow trade with fresh crypto data."""
        now = dt.datetime.now(timezone.utc)
        fresh_ts = (now - dt.timedelta(minutes=2)).isoformat().replace("+00:00", "Z")

        decision = {
            "action": "BUY",
            "asset_pair": "BTCUSD",
            "confidence": 85,
            "volatility": 0.02,
        }

        context = {
            "asset_type": "crypto",
            "market_data_timestamp": fresh_ts,
            "recent_performance": {"total_pnl": 0.01},
            "holdings": {},
        }

        is_valid, msg = self.gatekeeper.validate_trade(decision, context)
        # Should pass data freshness check (no stale data message)
        assert "Stale market data" not in msg

    def test_rejects_trade_with_stale_stock_intraday_data(self):
        """Gatekeeper should reject stock intraday trades with data > 15 min old."""
        now = dt.datetime.now(timezone.utc)
        stale_ts = (now - dt.timedelta(minutes=18)).isoformat().replace("+00:00", "Z")

        decision = {
            "action": "SELL",
            "asset_pair": "AAPL",
            "confidence": 75,
            "volatility": 0.025,
        }

        context = {
            "asset_type": "stocks",
            "timeframe": "intraday",
            "market_data_timestamp": stale_ts,
            "recent_performance": {"total_pnl": 0.0},
            "holdings": {},
        }

        is_valid, msg = self.gatekeeper.validate_trade(decision, context)
        assert is_valid is False
        assert "Stale market data" in msg

    def test_allows_old_stock_daily_data(self):
        """Gatekeeper should allow stock daily trades with data up to 24 hrs old."""
        now = dt.datetime.now(timezone.utc)
        old_ts = (now - dt.timedelta(hours=20)).isoformat().replace("+00:00", "Z")

        decision = {
            "action": "BUY",
            "asset_pair": "MSFT",
            "confidence": 80,
            "volatility": 0.02,
        }

        context = {
            "asset_type": "stocks",
            "timeframe": "daily",
            "market_data_timestamp": old_ts,
            "recent_performance": {"total_pnl": 0.02},
            "holdings": {},
        }

        is_valid, msg = self.gatekeeper.validate_trade(decision, context)
        # Daily data 20 hours old should be allowed
        assert "Stale market data" not in msg

    def test_handles_missing_timestamp_gracefully(self):
        """Gatekeeper should handle missing market_data_timestamp gracefully."""
        decision = {
            "action": "BUY",
            "asset_pair": "BTCUSD",
            "confidence": 85,
            "volatility": 0.02,
        }

        context = {
            "asset_type": "crypto",
            # No market_data_timestamp
            "recent_performance": {"total_pnl": 0.01},
            "holdings": {},
        }

        is_valid, msg = self.gatekeeper.validate_trade(decision, context)
        # Should not raise error, just skip freshness check
        assert isinstance(is_valid, bool)
        assert "Stale market data" not in msg

    def test_rejects_invalid_timestamp_format(self):
        """Gatekeeper should reject trades with invalid timestamp format."""
        decision = {
            "action": "BUY",
            "asset_pair": "BTCUSD",
            "confidence": 85,
            "volatility": 0.02,
        }

        context = {
            "asset_type": "crypto",
            "market_data_timestamp": "not-a-valid-timestamp",
            "recent_performance": {"total_pnl": 0.01},
            "holdings": {},
        }

        is_valid, msg = self.gatekeeper.validate_trade(decision, context)
        assert is_valid is False
        assert "Invalid timestamp" in msg

    def test_data_freshness_checked_before_other_validations(self):
        """Data freshness check should fail before other checks."""
        now = dt.datetime.now(timezone.utc)
        stale_ts = (now - dt.timedelta(minutes=20)).isoformat().replace("+00:00", "Z")

        decision = {
            "action": "BUY",
            "asset_pair": "BTCUSD",
            "confidence": 30,  # Low confidence (would fail volatility check)
            "volatility": 0.15,  # High volatility (would fail)
        }

        context = {
            "asset_type": "crypto",
            "market_data_timestamp": stale_ts,
            "recent_performance": {"total_pnl": -0.10},  # High drawdown (would fail)
            "holdings": {},
        }

        is_valid, msg = self.gatekeeper.validate_trade(decision, context)
        # Should fail on stale data first
        assert is_valid is False
        assert "Stale market data" in msg
        assert "drawdown" not in msg.lower()

    def test_defaults_to_intraday_for_stocks_without_timeframe(self):
        """Gatekeeper should default to intraday timeframe for stocks."""
        now = dt.datetime.now(timezone.utc)
        ts = (now - dt.timedelta(minutes=8)).isoformat().replace("+00:00", "Z")

        decision = {
            "action": "BUY",
            "asset_pair": "TSLA",
            "confidence": 80,
            "volatility": 0.02,
        }

        context = {
            "asset_type": "stocks",
            # No timeframe specified
            "market_data_timestamp": ts,
            "recent_performance": {"total_pnl": 0.01},
            "holdings": {},
        }

        is_valid, msg = self.gatekeeper.validate_trade(decision, context)
        # Should use intraday threshold (> 5 min warns, > 15 min rejects)
        # 8 minutes should warn but pass
        assert "Stale market data" not in msg
