"""
Comprehensive integration tests for core Finance Feedback Engine workflows.

Tests the full end-to-end flow from analysis to decision persistence.
"""

from unittest.mock import AsyncMock, patch

import pytest

from finance_feedback_engine import FinanceFeedbackEngine


@pytest.fixture
async def engine_with_mock_config(tmp_path, monkeypatch):
    """Create engine with test configuration and ensure proper cleanup."""
    # Set API key via environment variable
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "demo")

    config = {
        "alpha_vantage_api_key": "demo",  # Fallback if env var not read
        "trading_platform": "mock",
        "mock_platform": {"initial_balance": {"USD": 10000.0}},
        "ensemble": {
            "enabled_providers": ["local"],
            "provider_weights": {"local": 1.0},
            "min_providers_required": 1,
            "debate_mode": {"enabled": False},
        },
        "data_provider": {
            "type": "alpha_vantage",
            "timeout_market_data": 10,
            "timeout_sentiment": 10,
            "timeout_macro": 10,
        },
        "decision_engine": {
            "signal_only_default": False,
            "position_sizing": {"risk_per_trade": 0.01, "default_stop_loss": 0.02},
        },
        "persistence": {"decision_store": {"data_dir": str(tmp_path / "decisions")}},
    }

    engine = FinanceFeedbackEngine(config)

    yield engine

    # Cleanup: Close async resources like aiohttp sessions
    try:
        await engine.close()
    except Exception:
        pass  # Ignore cleanup errors


class TestCoreAnalysisWorkflow:
    """Test the complete analysis workflow."""

    @pytest.mark.asyncio
    async def test_analyze_asset_creates_decision(self, engine_with_mock_config):
        """Test that analyze_asset creates a valid decision with all required fields."""
        # Mock the data provider to return market data
        mock_data = {
            "open": 50000.0,
            "high": 51000.0,
            "low": 49500.0,
            "close": 50500.0,
            "volume": 1000000,
            "market_cap": 1000000000,
        }

        with patch.object(
            engine_with_mock_config.data_provider,
            "get_comprehensive_market_data",
            new=AsyncMock(
                return_value={
                    "current_price": 50500.0,
                    "market_data": mock_data,
                    "sentiment": {"score": 0.5},
                    "macro_indicators": {},
                    "technical_indicators": {},
                }
            ),
        ):
            decision = await engine_with_mock_config.analyze_asset_async("BTCUSD")

            # Verify decision structure
            assert decision is not None
            assert "action" in decision
            assert "confidence" in decision
            assert "reasoning" in decision
            assert "asset_pair" in decision
            assert "timestamp" in decision
            assert "id" in decision

            # Verify action is valid
            assert decision["action"] in ["BUY", "SELL", "HOLD"]

            # Verify confidence is in valid range
            assert 0 <= decision["confidence"] <= 100

            # Verify asset pair is standardized
            assert decision["asset_pair"] == "BTCUSD"

    def test_analyze_asset_signal_only_mode(self, engine_with_mock_config):
        """Test signal-only mode when balance is unavailable."""
        # Set signal_only_default to True
        engine_with_mock_config.config["decision_engine"]["signal_only_default"] = True

        mock_data = {
            "open": 50000.0,
            "high": 51000.0,
            "low": 49500.0,
            "close": 50500.0,
            "volume": 1000000,
            "market_cap": 1000000000,
        }

        with patch.object(
            engine_with_mock_config.data_provider,
            "get_comprehensive_market_data",
            new=AsyncMock(
                return_value={
                    "current_price": 50500.0,
                    "market_data": mock_data,
                    "sentiment": {"score": 0.5},
                    "macro_indicators": {},
                    "technical_indicators": {},
                }
            ),
        ):
            decision = engine_with_mock_config.analyze_asset("BTCUSD")

            # Verify signal-only flag
            assert decision.get("signal_only") is True

            # In signal-only mode, position sizing should be provided for human approval
            # (based on default balance for Telegram human-in-the-loop)
            assert "action" in decision
            assert "confidence" in decision
            assert "recommended_position_size" in decision
            assert "risk_percentage" in decision

    def test_analyze_asset_with_ensemble(self, engine_with_mock_config, tmp_path):
        """Test ensemble mode configuration."""
        # Engine is already configured with ensemble in fixture
        # Just verify that it can handle ensemble configuration

        mock_data = {
            "open": 50000.0,
            "high": 51000.0,
            "low": 49500.0,
            "close": 50500.0,
            "volume": 1000000,
            "market_cap": 1000000000,
        }

        with patch.object(
            engine_with_mock_config.data_provider,
            "get_comprehensive_market_data",
            new=AsyncMock(
                return_value={
                    "current_price": 50500.0,
                    "market_data": mock_data,
                    "sentiment": {"score": 0.5},
                    "macro_indicators": {},
                    "technical_indicators": {},
                }
            ),
        ):
            decision = engine_with_mock_config.analyze_asset("BTCUSD")

            # Verify decision created successfully with ensemble config
            assert decision is not None
            assert "action" in decision
            assert "confidence" in decision
            assert "ai_provider" in decision  # Should indicate which provider was used


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_invalid_asset_pair_format(self, engine_with_mock_config):
        """Test handling of invalid asset pair formats."""
        # The engine should standardize or reject invalid formats
        with pytest.raises(Exception):
            engine_with_mock_config.analyze_asset("INVALID")

    def test_provider_failure_fallback(self, engine_with_mock_config):
        """Test fallback when primary provider fails."""
        # Mock data provider to fail
        with patch.object(
            engine_with_mock_config.data_provider,
            "get_comprehensive_market_data",
            new=AsyncMock(side_effect=Exception("API Error")),
        ):
            # Should raise exception (no fallback in current implementation)
            with pytest.raises(Exception):
                decision = engine_with_mock_config.analyze_asset("BTCUSD")


class TestDecisionPersistence:
    """Test decision storage and retrieval."""

    def test_decision_store_save_and_load(self, engine_with_mock_config):
        """Test saving and loading decisions from disk."""
        import uuid
        from datetime import datetime

        store = engine_with_mock_config.decision_store

        # Create a test decision
        test_decision = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "asset_pair": "BTCUSD",
            "action": "BUY",
            "confidence": 85,
            "reasoning": "Test decision",
            "suggested_amount": 100.0,
        }

        # Save decision
        store.save_decision(test_decision)

        # Retrieve decision
        loaded = store.get_decision_by_id(test_decision["id"])

        assert loaded is not None
        assert loaded["id"] == test_decision["id"]
        assert loaded["action"] == test_decision["action"]
        assert loaded["confidence"] == test_decision["confidence"]

    def test_decision_store_list_recent(self, engine_with_mock_config):
        """Test listing recent decisions."""
        import uuid
        from datetime import datetime

        store = engine_with_mock_config.decision_store

        # Create multiple test decisions
        decisions = []
        for i in range(5):
            decision = {
                "id": str(uuid.uuid4()),
                "timestamp": datetime.utcnow().isoformat(),
                "asset_pair": "BTCUSD",
                "action": "BUY",
                "confidence": 80 + i,
                "reasoning": f"Test decision {i}",
                "suggested_amount": 100.0 * (i + 1),
            }
            store.save_decision(decision)
            decisions.append(decision)

        # List recent decisions
        recent = store.get_decisions(limit=3)

        assert len(recent) <= 3
        assert all("id" in d for d in recent)


class TestMarketRegimeDetection:
    """Test market regime classification."""

    def test_regime_detection_trending(self):
        """Test detection of trending market."""
        import numpy as np
        import pandas as pd

        from finance_feedback_engine.utils.market_regime_detector import (
            MarketRegimeDetector,
        )

        # Create trending data (upward trend)
        dates = pd.date_range(start="2024-01-01", periods=50, freq="D")
        prices = np.linspace(100, 150, 50)  # Strong upward trend

        df = pd.DataFrame(
            {
                "open": prices * 0.99,
                "high": prices * 1.01,
                "low": prices * 0.98,
                "close": prices,
                "volume": [1000000] * 50,
            },
            index=dates,
        )

        detector = MarketRegimeDetector()
        regime = detector.detect_regime(df)

        assert regime is not None
        assert "TRENDING" in regime  # Should detect trending market

    def test_regime_detection_choppy(self):
        """Test detection of choppy/ranging market."""
        import numpy as np
        import pandas as pd

        from finance_feedback_engine.utils.market_regime_detector import (
            MarketRegimeDetector,
        )

        # Create ranging data (nearly flat with small noise)
        dates = pd.date_range(start="2024-01-01", periods=50, freq="D")
        base_price = 100
        noise = np.random.normal(loc=0, scale=0.1, size=50)  # Very small noise
        prices = base_price + noise
        prices = np.clip(
            prices, base_price - 0.5, base_price + 0.5
        )  # Keep it very tight

        df = pd.DataFrame(
            {
                "open": prices * 0.99,
                "high": prices * 1.01,
                "low": prices * 0.98,
                "close": prices,
                "volume": [1000000] * 50,
            },
            index=dates,
        )

        detector = MarketRegimeDetector()
        regime = detector.detect_regime(df)

        assert regime is not None
        # Should detect ranging or choppy market
        assert "RANGING" in regime or "CHOP" in regime


class TestPlatformIntegration:
    """Test trading platform integration."""

    def test_mock_platform_balance(self, engine_with_mock_config):
        """Test mock platform balance retrieval."""
        platform = engine_with_mock_config.trading_platform

        balance = platform.get_balance()

        assert balance is not None
        assert "SPOT_USD" in balance
        assert balance["SPOT_USD"] > 0

    def test_mock_platform_execute_trade(self, engine_with_mock_config):
        """Test trade execution on mock platform."""
        import uuid
        from datetime import datetime

        platform = engine_with_mock_config.trading_platform

        decision = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "asset_pair": "BTCUSD",
            "action": "BUY",
            "confidence": 85,
            "reasoning": "Test trade",
            "suggested_amount": 100.0,
        }

        result = platform.execute_trade(decision)

        assert result is not None
        assert "success" in result


class TestPositionSizing:
    """Test position sizing calculations."""

    def test_position_sizing_with_balance(self):
        """Test position size calculation with available balance."""
        from finance_feedback_engine.decision_engine.engine import DecisionEngine

        config = {
            "decision_engine": {
                "signal_only_default": False,
                "position_sizing": {"risk_per_trade": 0.01, "default_stop_loss": 0.02},
            }
        }
        engine = DecisionEngine(config)

        # Test with known balance
        balance = 10000.0
        entry_price = 50000.0
        risk_per_trade = 0.01  # 1%
        stop_loss_pct = 0.02  # 2%

        position_size = engine.calculate_position_size(
            account_balance=balance,
            entry_price=entry_price,
            risk_percentage=risk_per_trade,
            stop_loss_percentage=stop_loss_pct,
        )

        # Expected: (10000 * 0.01) / (50000 * 0.02) = 100 / 1000 = 0.1 BTC
        # In USD: 0.1 * 50000 = 5000
        assert position_size is not None
        assert position_size > 0
        assert position_size <= balance  # Should not exceed balance

    def test_position_sizing_signal_only(self):
        """Test that signal-only mode returns None for position size."""
        from finance_feedback_engine.decision_engine.engine import DecisionEngine

        # Enable signal-only mode
        config = {
            "decision_engine": {
                "signal_only_default": True,
                "position_sizing": {"risk_per_trade": 0.01, "default_stop_loss": 0.02},
            }
        }
        engine = DecisionEngine(config)

        # Default values used by _create_decision in signal-only mode
        default_balance = 10000.0
        risk_percentage = config["decision_engine"]["position_sizing"]["risk_per_trade"]
        stop_loss_percentage = config["decision_engine"]["position_sizing"][
            "default_stop_loss"
        ]

        position_size = engine.calculate_position_size(
            account_balance=default_balance,
            entry_price=50000.0,
            risk_percentage=risk_percentage,
            stop_loss_percentage=stop_loss_percentage,
        )

        # Even in signal-only mode, position sizing should be calculated for human approval
        # Using default balance, so position size should be > 0
        assert position_size is not None
        assert position_size > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
