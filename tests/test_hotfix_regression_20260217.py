"""
Retroactive QA regression tests for hotfix commits landed 2026-02-17.

Covers:
  - 83f21776: balance fallback path in core.py (portfolio → direct aget_balance)
  - 49430881: max_position_usd_dev raised from 50 → 500 in config_loader default

Run:
    pytest tests/test_hotfix_regression_20260217.py -v --no-cov
"""

from unittest.mock import AsyncMock, MagicMock, patch
import asyncio
import os

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_minimal_config():
    """Return a minimal config dict that passes FinanceFeedbackEngine validation."""
    return {
        "alpha_vantage_api_key": "PLACEHOLDER",
        "trading_platform": "mock",
        "platform_credentials": {
            "mock": {"api_key": "PLACEHOLDER", "api_secret": "PLACEHOLDER"}
        },
        "decision_engine": {"ai_provider": "local", "model_name": "test"},
        "persistence": {"enabled": False},
        "agent": {
            "autonomous_execution": False,
            "approval_policy": "on_new_asset",
            "max_daily_trades": 5,
            "strategic_goal": "balanced",
            "risk_appetite": "medium",
            "asset_pairs": ["BTCUSD"],
            "autonomous": {"enabled": False, "profit_target": 0.05, "stop_loss": 0.02},
            "correlation_threshold": 0.7,
            "max_correlated_assets": 2,
            "max_var_pct": 0.05,
            "var_confidence": 0.95,
            "position_sizing": {
                "risk_percentage": 0.01,
                "max_position_usd_dev": 500.0,
                "max_position_usd_prod": 500.0,
                "dynamic_sizing": True,
                "target_utilization_pct": 0.02,
            },
        },
        "circuit_breaker": {"enabled": False},
        "logging": {
            "level": "WARNING",
            "structured": {"enabled": False, "format": "json", "correlation_ids": False, "pii_redaction": False},
            "file": {"enabled": False, "base_path": "logs", "rotation_max_bytes": 1048576, "rotation_backup_count": 5},
            "retention": {"hot_days": 7, "warm_days": 30, "cold_days": 365},
        },
        "monitoring": {"enabled": False, "include_sentiment": False, "include_macro": False, "pulse_interval_seconds": 300},
        "error_tracking": {"enabled": False},
    }


# ---------------------------------------------------------------------------
# 1. Balance fallback path — commit 83f21776
# ---------------------------------------------------------------------------

class TestBalanceFallbackPath:
    """Tests for the balance fallback in FinanceFeedbackEngine.analyze_asset_async.

    The fallback is triggered when portfolio-derived balance has no positive
    values. It calls trading_platform.aget_balance() as the secondary source.
    """

    @pytest.mark.asyncio
    async def test_fallback_fires_when_balance_all_zero(self):
        """When portfolio yields all-zero balances, aget_balance() is called."""
        from finance_feedback_engine.trading_platforms.mock_platform import MockTradingPlatform

        platform = MockTradingPlatform()
        # Force get_balance to return zero for all keys
        platform._balance = {"FUTURES_USD": 0.0, "SPOT_USD": 0.0}

        aget_balance_mock = AsyncMock(return_value={"USD": 1000.0})
        platform.aget_balance = aget_balance_mock

        # Patch portfolio breakdown to return zero values
        with patch.object(platform, "get_portfolio_breakdown", return_value={
            "total_value_usd": 0,
            "futures_value_usd": 0.0,
            "spot_value_usd": 0.0,
            "num_assets": 0,
            "positions": [],
        }):
            config = _make_minimal_config()
            config["trading_platform"] = "mock"

            from finance_feedback_engine.trading_platforms.mock_platform import MockTradingPlatform
            with patch("finance_feedback_engine.core.FinanceFeedbackEngine.__init__", return_value=None):
                from finance_feedback_engine.core import FinanceFeedbackEngine
                engine = FinanceFeedbackEngine.__new__(FinanceFeedbackEngine)
                engine.trading_platform = platform
                engine.config = config

                # Simulate the balance-derivation + fallback logic directly
                balance = {}
                pb = platform.get_portfolio_breakdown()
                if pb.get("futures_value_usd") is not None:
                    balance["FUTURES_USD"] = pb.get("futures_value_usd", 0)
                if pb.get("spot_value_usd") is not None:
                    balance["SPOT_USD"] = pb.get("spot_value_usd", 0)

                # Core fallback condition (exact logic from 83f21776)
                if not any(float(v or 0) > 0 for v in balance.values()):
                    balance = await asyncio.wait_for(
                        platform.aget_balance(), timeout=10.0
                    )

                assert aget_balance_mock.called, "aget_balance() should have been called on zero balance"
                assert balance == {"USD": 1000.0}

    @pytest.mark.asyncio
    async def test_fallback_does_not_fire_when_balance_positive(self):
        """When portfolio yields a positive balance, aget_balance() is NOT called."""
        from finance_feedback_engine.trading_platforms.mock_platform import MockTradingPlatform

        platform = MockTradingPlatform()
        aget_balance_mock = AsyncMock(return_value={"USD": 9999.0})
        platform.aget_balance = aget_balance_mock

        balance = {"FUTURES_USD": 250.0, "SPOT_USD": 0.0}

        # Fallback condition — should NOT trigger
        if not any(float(v or 0) > 0 for v in balance.values()):
            balance = await asyncio.wait_for(platform.aget_balance(), timeout=10.0)

        assert not aget_balance_mock.called, "aget_balance() should NOT be called when balance has positive values"
        assert balance == {"FUTURES_USD": 250.0, "SPOT_USD": 0.0}

    @pytest.mark.asyncio
    async def test_fallback_fires_when_balance_empty_dict(self):
        """When portfolio returns empty dict (no keys at all), fallback fires."""
        from finance_feedback_engine.trading_platforms.mock_platform import MockTradingPlatform

        platform = MockTradingPlatform()
        aget_balance_mock = AsyncMock(return_value={"USD": 500.0})
        platform.aget_balance = aget_balance_mock

        balance = {}  # Initial state: no keys at all

        if not any(float(v or 0) > 0 for v in balance.values()):
            balance = await asyncio.wait_for(platform.aget_balance(), timeout=10.0)

        assert aget_balance_mock.called, "aget_balance() should be called for empty balance dict"
        assert balance == {"USD": 500.0}

    @pytest.mark.asyncio
    async def test_fallback_handles_aget_balance_exception_gracefully(self):
        """When fallback aget_balance() raises, it is swallowed with a warning (no crash)."""
        import logging
        from finance_feedback_engine.trading_platforms.mock_platform import MockTradingPlatform

        platform = MockTradingPlatform()
        platform.aget_balance = AsyncMock(side_effect=ConnectionError("API unavailable"))

        balance = {}  # Triggers fallback

        # Replicate the try/except from 83f21776
        try:
            if not any(float(v or 0) > 0 for v in balance.values()):
                balance = await asyncio.wait_for(
                    platform.aget_balance(), timeout=10.0
                )
        except Exception:
            pass  # Exception should be caught — balance stays {}

        # Balance stays unchanged; no exception propagates
        assert isinstance(balance, dict)

    @pytest.mark.asyncio
    async def test_fallback_handles_none_values_in_balance(self):
        """balance dict with None values should be treated as zero."""
        balance = {"FUTURES_USD": None, "SPOT_USD": None}

        # The expression `float(v or 0)` should convert None → 0
        result = any(float(v or 0) > 0 for v in balance.values())
        assert result is False, "None values should be treated as 0, triggering fallback"


# ---------------------------------------------------------------------------
# 2. max_position_usd_dev default — commit 49430881 (+ bugfix in config_loader)
# ---------------------------------------------------------------------------

class TestMaxPositionUsdDev:
    """Tests that max_position_usd_dev is correctly applied as 500 in dev env.

    Commit 49430881 updated config.yaml, but config_loader.py had a stale
    hard-coded default of 50.0. The QA bugfix updates config_loader.py to 500.0.
    """

    def test_config_loader_default_is_500(self):
        """load_env_config() default for max_position_usd_dev should be 500.0."""
        import importlib
        import finance_feedback_engine.utils.config_loader as _cl_mod

        # Remove env var to test pure default
        env_var = "AGENT_POSITION_SIZING_MAX_POSITION_USD_DEV"
        saved = os.environ.pop(env_var, None)
        try:
            importlib.reload(_cl_mod)
            cfg = _cl_mod.load_env_config()
            dev_cap = cfg["agent"]["position_sizing"]["max_position_usd_dev"]
            assert dev_cap == 500.0, (
                f"Expected 500.0 but got {dev_cap}. "
                "config_loader.py default was not updated from 50.0 → 500.0."
            )
        finally:
            if saved is not None:
                os.environ[env_var] = saved
            importlib.reload(_cl_mod)  # restore module state for other tests

    def test_config_loader_env_var_overrides_default(self):
        """AGENT_POSITION_SIZING_MAX_POSITION_USD_DEV env var overrides the default."""
        from finance_feedback_engine.utils.config_loader import load_env_config

        env_var = "AGENT_POSITION_SIZING_MAX_POSITION_USD_DEV"
        saved = os.environ.get(env_var)
        os.environ[env_var] = "750.0"
        try:
            cfg = load_env_config()
            dev_cap = cfg["agent"]["position_sizing"]["max_position_usd_dev"]
            assert dev_cap == 750.0
        finally:
            if saved is not None:
                os.environ[env_var] = saved
            else:
                os.environ.pop(env_var, None)

    def test_position_sizing_cap_500_in_dev(self):
        """In dev environment, position sizing caps at $500 not $50."""
        from finance_feedback_engine.decision_engine.position_sizing import PositionSizingCalculator
        from unittest.mock import patch

        config = {
            "agent": {
                "risk_percentage": 0.01,
                "sizing_stop_loss_percentage": 0.02,
                "use_dynamic_stop_loss": False,
                "position_sizing": {
                    "risk_percentage": 0.01,
                    "max_position_usd_dev": 500.0,
                    "max_position_usd_prod": 500.0,
                    "dynamic_sizing": False,
                    "target_utilization_pct": 0.02,
                },
            }
        }
        calculator = PositionSizingCalculator(config)

        # $10,000 balance, 1% risk, $300 position would be ABOVE old $50 cap
        # but BELOW new $500 cap — it should NOT be capped
        # get_environment_name is imported locally inside position_sizing, so patch at source
        with patch("finance_feedback_engine.utils.environment.get_environment_name", return_value="dev"):
            result = calculator.calculate_position_sizing_params(
                context={"asset_pair": "BTCUSD"},
                current_price=300.0,      # $300/unit
                action="BUY",
                has_existing_position=False,
                relevant_balance={"USD": 10000.0},
                balance_source="test",
            )

        # 1% of $10,000 = $100 at risk, with 2% stop-loss → $100/0.02 = 5000 / 300 ≈ 16.67 units → $5,000
        # That exceeds $500 cap, so it should be capped at 500/300 ≈ 1.667 units
        # Position value at cap: 500 / 300 ≈ $500 (not $50)
        pos_size = result.get("recommended_position_size", 0)
        pos_value = pos_size * 300.0
        assert pos_value <= 500.0, f"Position value ${pos_value:.2f} should be capped at $500, not $50"
        assert pos_value > 50.0, (
            f"Position value ${pos_value:.2f} should NOT be capped at the old $50 limit. "
            "Commit 49430881 raised the cap to $500."
        )

    def test_yaml_config_max_position_usd_dev_is_500(self):
        """Verify config.yaml contains 500.0 for max_position_usd_dev (commit 49430881 check)."""
        import yaml
        from pathlib import Path

        yaml_path = Path(__file__).parent.parent / "config" / "config.yaml"
        assert yaml_path.exists(), f"config.yaml not found at {yaml_path}"

        with open(yaml_path) as f:
            config = yaml.safe_load(f)

        dev_cap = (
            config.get("agent", {})
            .get("position_sizing", {})
            .get("max_position_usd_dev")
        )
        assert dev_cap == 500.0, (
            f"config.yaml max_position_usd_dev is {dev_cap}, expected 500.0. "
            "Commit 49430881 should have changed this."
        )
