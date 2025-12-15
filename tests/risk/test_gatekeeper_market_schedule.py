"""Test RiskGatekeeper market schedule integration."""

import datetime as dt
import pytz

from finance_feedback_engine.risk.gatekeeper import RiskGatekeeper
from finance_feedback_engine.utils.market_schedule import MarketSchedule


def _to_utc(local_dt: dt.datetime, tz: pytz.BaseTzInfo) -> dt.datetime:
    """Helper to convert local time to UTC."""
    return tz.localize(local_dt).astimezone(pytz.UTC)


def _to_unix(utc_dt: dt.datetime) -> int:
    """Convert UTC datetime to Unix timestamp."""
    return int(utc_dt.timestamp())


class TestGatekeeperMarketSchedule:
    """Test market schedule checks in RiskGatekeeper."""

    def setup_method(self):
        """Initialize gatekeeper for each test."""
        self.gatekeeper = RiskGatekeeper()

    def test_allows_forex_even_on_weekend_window(self):
        """Gatekeeper should not block forex trades during the Friday close/Sunday reopen window."""
        # Friday 5 PM NY (previously treated as closed)
        now_utc = _to_utc(dt.datetime(2024, 5, 10, 17, 0), MarketSchedule.NY_TZ)
        timestamp = _to_unix(now_utc)

        decision = {
            "action": "BUY",
            "asset_pair": "EURUSD",
            "confidence": 85,
            "volatility": 0.03,
        }

        context = {
            "asset_type": "forex",
            "timestamp": timestamp,
            "recent_performance": {"total_pnl": -0.01},
            "holdings": {},
        }

        is_valid, msg = self.gatekeeper.validate_trade(decision, context)
        assert is_valid is True
        assert "Market closed" not in msg

    def test_rejects_stock_when_market_closed_outside_hours(self):
        """Gatekeeper should reject stock trades outside 9:30-16:00 NY hours."""
        # 8 AM NY (before market open)
        now_utc = _to_utc(dt.datetime(2024, 5, 13, 8, 0), MarketSchedule.NY_TZ)
        timestamp = _to_unix(now_utc)

        decision = {
            "action": "BUY",
            "asset_pair": "AAPL",
            "confidence": 90,
            "volatility": 0.02,
        }

        context = {
            "asset_type": "stocks",
            "timestamp": timestamp,
            "recent_performance": {"total_pnl": 0.02},
            "holdings": {},
        }

        is_valid, msg = self.gatekeeper.validate_trade(decision, context)
        assert is_valid is False
        assert "Market closed" in msg

    def test_rejects_stock_on_weekend(self):
        """Gatekeeper should reject stock trades on weekends."""
        # Saturday 10 AM NY
        now_utc = _to_utc(dt.datetime(2024, 5, 11, 10, 0), MarketSchedule.NY_TZ)
        timestamp = _to_unix(now_utc)

        decision = {
            "action": "SELL",
            "asset_pair": "MSFT",
            "confidence": 75,
            "volatility": 0.025,
        }

        context = {
            "asset_type": "stocks",
            "timestamp": timestamp,
            "recent_performance": {"total_pnl": 0.0},
            "holdings": {},
        }

        is_valid, msg = self.gatekeeper.validate_trade(decision, context)
        assert is_valid is False
        assert "Market closed" in msg

    def test_allows_forex_during_london_session(self):
        """Gatekeeper should allow forex trades during London session."""
        # 10 AM London (9 AM UTC during BST, open in London)
        now_utc = _to_utc(dt.datetime(2024, 5, 13, 10, 0), MarketSchedule.LONDON_TZ)
        timestamp = _to_unix(now_utc)

        decision = {
            "action": "BUY",
            "asset_pair": "GBPJPY",
            "confidence": 80,
            "volatility": 0.02,
        }

        context = {
            "asset_type": "forex",
            "timestamp": timestamp,
            "recent_performance": {"total_pnl": 0.001},
            "holdings": {},
        }

        is_valid, msg = self.gatekeeper.validate_trade(decision, context)
        # Should pass market check (may fail other checks, but not market-related)
        assert "Market closed" not in msg

    def test_allows_stock_during_trading_hours(self):
        """Gatekeeper should allow stock trades during market hours."""
        # 11 AM NY (during market hours: 9:30-16:00)
        now_utc = _to_utc(dt.datetime(2024, 5, 13, 11, 0), MarketSchedule.NY_TZ)
        timestamp = _to_unix(now_utc)

        decision = {
            "action": "BUY",
            "asset_pair": "TSLA",
            "confidence": 85,
            "volatility": 0.02,
        }

        context = {
            "asset_type": "stocks",
            "timestamp": timestamp,
            "recent_performance": {"total_pnl": 0.005},
            "holdings": {},
        }

        is_valid, msg = self.gatekeeper.validate_trade(decision, context)
        # Should not reject due to market closure
        assert "Market closed" not in msg

    def test_allows_crypto_24_7_weekday(self):
        """Gatekeeper should allow crypto trades 24/7 on weekdays."""
        # Monday 2 AM NY (middle of night, but still open for crypto)
        now_utc = _to_utc(dt.datetime(2024, 5, 13, 2, 0), MarketSchedule.NY_TZ)
        timestamp = _to_unix(now_utc)

        decision = {
            "action": "BUY",
            "asset_pair": "BTCUSD",
            "confidence": 80,
            "volatility": 0.03,
        }

        context = {
            "asset_type": "crypto",
            "timestamp": timestamp,
            "recent_performance": {"total_pnl": 0.01},
            "holdings": {},
        }

        is_valid, msg = self.gatekeeper.validate_trade(decision, context)
        # Should pass market check
        assert "Market closed" not in msg

    def test_allows_crypto_weekend_with_warning_logged(self):
        """Gatekeeper should allow crypto on weekends but market status includes warning."""
        # Saturday 10 AM NY
        now_utc = _to_utc(dt.datetime(2024, 5, 11, 10, 0), MarketSchedule.NY_TZ)
        timestamp = _to_unix(now_utc)

        decision = {
            "action": "BUY",
            "asset_pair": "ETHUSD",
            "confidence": 80,
            "volatility": 0.025,
        }

        context = {
            "asset_type": "crypto",
            "timestamp": timestamp,
            "recent_performance": {"total_pnl": 0.0},
            "holdings": {},
        }

        is_valid, msg = self.gatekeeper.validate_trade(decision, context)
        # Crypto is open even on weekend
        assert "Market closed" not in msg
        # Check that market schedule reports weekend
        status = MarketSchedule.get_market_status_at_timestamp("ETHUSD", "crypto", timestamp)
        assert status["warning"] == "Weekend Low Liquidity"

    def test_market_check_is_first_validation(self):
        """Market schedule check should be the first validation (before drawdown, etc.)."""
        # Saturday (market closed for stocks)
        now_utc = _to_utc(dt.datetime(2024, 5, 11, 12, 0), MarketSchedule.NY_TZ)
        timestamp = _to_unix(now_utc)

        decision = {
            "action": "BUY",
            "asset_pair": "AAPL",
            "confidence": 50,  # Low confidence (would fail later check)
            "volatility": 0.1,  # High volatility (would fail later check)
        }

        context = {
            "asset_type": "stocks",
            "timestamp": timestamp,
            "recent_performance": {"total_pnl": -0.20},  # Severe drawdown (would fail)
            "holdings": {},
        }

        is_valid, msg = self.gatekeeper.validate_trade(decision, context)
        # Should fail on market closed, not on drawdown/volatility
        assert is_valid is False
        assert "Market closed" in msg
        assert "drawdown" not in msg.lower()

    def test_defaults_to_live_market_status_without_timestamp(self):
        """When timestamp is None, should use current time (live trading)."""
        # Decision and context without timestamp (live trading scenario)
        decision = {
            "action": "BUY",
            "asset_pair": "EURUSD",
            "confidence": 80,
            "volatility": 0.02,
        }

        context = {
            "asset_type": "forex",
            "recent_performance": {"total_pnl": 0.01},
            "holdings": {},
            # No timestamp key
        }

        # Should not raise an error
        is_valid, msg = self.gatekeeper.validate_trade(decision, context)
        # Result depends on current time, but should run without error
        assert isinstance(is_valid, bool)
        assert isinstance(msg, str)
