"""
Test credential validation interaction with analysis-only mode fallback.

This test suite verifies the interaction between:
1. Fail-fast credential validation (core.py line 70)
2. Graceful fallback to MockTradingPlatform (core.py lines 220-240)

Issue: https://github.com/Three-Rivers-Tech/finance_feedback_engine/issues/...
The credential validation raises ValueError BEFORE platform initialization,
preventing the catch block that enables analysis-only mode fallback.
"""

import pytest
from unittest.mock import patch, MagicMock


class TestAnalysisOnlyModeFallback:
    """Test that analysis-only mode supports placeholder credentials."""

    def test_analysis_only_with_placeholder_credentials_mock_platform(self, tmp_path):
        """
        Verify that setting trading_platform='mock' allows analysis-only mode
        with placeholder credentials.

        This test demonstrates the ISSUE: validate_credentials() raises ValueError
        at line 70 before the platform initialization catch block can trigger
        the MockTradingPlatform fallback at lines 220-240.

        Expected: Engine should initialize in analysis-only mode
        Actual: ValueError from validate_credentials prevents fallback
        """
        from finance_feedback_engine import FinanceFeedbackEngine

        config = {
            "alpha_vantage_api_key": "YOUR_ALPHA_VANTAGE_API_KEY",  # Placeholder
            "trading_platform": "mock",  # Explicit analysis-only intent
            "platform_credentials": {
                "api_key": "YOUR_COINBASE_API_KEY",  # Placeholder
                "api_secret": "YOUR_SECRET",  # Placeholder
            },
            "decision_engine": {
                "signal_only_default": False,
            },
            "ensemble": {
                "enabled_providers": ["local"],
                "provider_weights": {"local": 1.0},
                "min_providers_required": 1,
            },
            "persistence": {
                "decision_store": {"data_dir": str(tmp_path / "decisions")}
            },
        }

        # ISSUE: This should work but currently raises ValueError
        # because validate_credentials() fails at line 70
        with pytest.raises(ValueError, match="placeholder credentials"):
            engine = FinanceFeedbackEngine(config)

    def test_analysis_only_with_demo_api_key(self, tmp_path):
        """
        Verify that using demo API keys allows analysis-only mode to initialize.

        Workaround for the above issue: "demo" is not considered a placeholder.
        This test shows the current workaround.
        """
        from finance_feedback_engine import FinanceFeedbackEngine

        config = {
            "alpha_vantage_api_key": "demo",  # "demo" is not a placeholder
            "trading_platform": "mock",
            "platform_credentials": {},  # Empty = not a placeholder
            "decision_engine": {
                "signal_only_default": False,
            },
            "ensemble": {
                "enabled_providers": ["local"],
                "provider_weights": {"local": 1.0},
                "min_providers_required": 1,
            },
            "persistence": {
                "decision_store": {"data_dir": str(tmp_path / "decisions")}
            },
        }

        # Should work: demo key is not a placeholder
        engine = FinanceFeedbackEngine(config)

        # Should use MockTradingPlatform
        from finance_feedback_engine.trading_platforms.mock_platform import (
            MockTradingPlatform,
        )

        assert isinstance(engine.trading_platform, MockTradingPlatform)
        assert engine.data_provider is not None

    def test_credential_validation_should_skip_for_mock_platform(self, tmp_path):
        """
        Test that credential validation should be skipped when using
        trading_platform='mock' (explicit analysis-only intent).

        This is the RECOMMENDED FIX: Pass context to validate_credentials()
        to allow placeholder credentials when analysis-only mode is explicit.
        """
        # This test documents the expected behavior after the fix
        pytest.skip(
            "Pending fix: credential_validator needs allow_analysis_only param"
        )

        from finance_feedback_engine import FinanceFeedbackEngine

        config = {
            "alpha_vantage_api_key": "YOUR_ALPHA_VANTAGE_API_KEY",
            "trading_platform": "mock",  # Explicit analysis-only intent
            "platform_credentials": {
                "api_key": "YOUR_COINBASE_API_KEY",
            },
            "decision_engine": {
                "signal_only_default": False,
            },
            "ensemble": {
                "enabled_providers": ["local"],
                "provider_weights": {"local": 1.0},
                "min_providers_required": 1,
            },
            "persistence": {
                "decision_store": {"data_dir": str(tmp_path / "decisions")}
            },
        }

        # After fix: Should initialize without error
        engine = FinanceFeedbackEngine(config)
        assert engine.trading_platform is not None

    @pytest.mark.xfail(
        reason="Known issue: credential validation doesn't trigger fallback to MockTradingPlatform. "
        "Design intent is to fallback gracefully, but validate_credentials() currently allows "
        "invalid credentials through without triggering the catch block. "
        "See: https://github.com/Three-Rivers-Tech/finance_feedback_engine/issues/TBD",
        strict=False
    )
    def test_documented_fallback_should_work_on_credential_error(self, tmp_path):
        """
        Test the documented behavior: if credentials are invalid during
        platform initialization, should fallback to MockTradingPlatform.

        This documents the DESIGN INTENT from C4 documentation:
        "Graceful Degradation: Uses mock platform if credentials missing;
         allows analysis-only operation"

        Current issue: validate_credentials() raises BEFORE platform init,
        so the catch block never executes.
        """
        from finance_feedback_engine import FinanceFeedbackEngine

        config = {
            "alpha_vantage_api_key": "demo",
            "trading_platform": "coinbase",  # Try real platform...
            "platform_credentials": {
                # ... but with invalid credentials
                "api_key": "INVALID_KEY_THAT_WILL_CAUSE_ERROR",
            },
            "decision_engine": {
                "signal_only_default": False,
            },
            "ensemble": {
                "enabled_providers": ["local"],
                "provider_weights": {"local": 1.0},
                "min_providers_required": 1,
            },
            "persistence": {
                "decision_store": {"data_dir": str(tmp_path / "decisions")}
            },
        }

        # Per C4 docs, this should fallback to MockTradingPlatform
        # But currently it might fail before reaching the catch block
        engine = FinanceFeedbackEngine(config)

        # After fallback, should use mock platform
        from finance_feedback_engine.trading_platforms.mock_platform import (
            MockTradingPlatform,
        )

        # If this assertion fails, it means fallback didn't happen
        assert isinstance(
            engine.trading_platform, MockTradingPlatform
        ), "Should fallback to MockTradingPlatform on credential error"


class TestCredentialValidatorContext:
    """Test the credential validator with context parameters."""

    def test_validate_credentials_with_allow_analysis_only_flag(self):
        """
        Test that validate_credentials() can accept an allow_analysis_only flag
        to permit placeholder credentials in analysis-only mode.

        This is the RECOMMENDED FIX implementation.
        """
        pytest.skip("Pending implementation: allow_analysis_only param not yet added")

        from finance_feedback_engine.utils.credential_validator import (
            validate_credentials,
        )

        config = {
            "alpha_vantage_api_key": "YOUR_ALPHA_VANTAGE_API_KEY",
            "trading_platform": "mock",
            "platform_credentials": {"api_key": "YOUR_KEY"},
        }

        # Should raise with strict validation (default)
        with pytest.raises(ValueError, match="placeholder"):
            validate_credentials(config, allow_analysis_only=False)

        # Should pass with analysis-only allowed
        validate_credentials(config, allow_analysis_only=True)

    def test_validate_credentials_auto_detect_analysis_only_intent(self):
        """
        Test that validate_credentials() can auto-detect analysis-only intent
        from the configuration (trading_platform='mock', signal_only_mode, etc).

        This is the RECOMMENDED FIX: minimal config changes needed.
        """
        pytest.skip(
            "Pending implementation: auto-detection of analysis-only mode not yet added"
        )

        from finance_feedback_engine.utils.credential_validator import (
            validate_credentials,
        )

        config = {
            "alpha_vantage_api_key": "YOUR_ALPHA_VANTAGE_API_KEY",
            "trading_platform": "mock",  # Signals analysis-only intent
            "platform_credentials": {"api_key": "YOUR_KEY"},
        }

        # Should pass: mock platform indicates analysis-only intent
        validate_credentials(config)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
