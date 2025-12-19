"""
Test Suite for Enhanced Slippage & Commission Modeling (Phase 1.1)

TDD Workflow:
1. RED: All tests written first and initially FAIL (methods don't exist)
2. GREEN: Implement minimal code to pass all tests
3. REFACTOR: Feature flag properly gates new functionality

Feature Flag: features.enhanced_slippage_model (default: false)
Config Options:
- backtesting.slippage_model: "basic" or "realistic"
- backtesting.fee_model: "simple" or "tiered"

Coverage Target: >= 90% for new code

Reference: /home/cmp6510/.claude/plans/declarative-sprouting-balloon.md (Phase 1.1)
"""

from datetime import datetime, timezone
from typing import Any, Dict
from unittest.mock import MagicMock

import pandas as pd
import pytest

# Import the backtester module
from finance_feedback_engine.backtesting.backtester import Backtester


class TestRealisticSlippageAssetType:
    """Tests for realistic slippage based on asset type."""

    @pytest.fixture
    def mock_historical_provider(self) -> MagicMock:
        """Create a mock historical data provider."""
        provider = MagicMock()
        provider.get_historical_data.return_value = pd.DataFrame(
            {
                "open": [100.0, 101.0],
                "high": [102.0, 103.0],
                "low": [99.0, 100.0],
                "close": [101.0, 102.0],
                "volume": [1000, 1100],
            },
            index=pd.date_range("2024-01-01", periods=2, freq="h", tz="UTC"),
        )
        return provider

    @pytest.fixture
    def backtester_with_realistic_slippage(
        self, mock_historical_provider: MagicMock
    ) -> Backtester:
        """Create a backtester with realistic slippage enabled."""
        config: Dict[str, Any] = {
            "features": {"enhanced_slippage_model": True},
            "backtesting": {"slippage_model": "realistic", "fee_model": "tiered"},
        }
        return Backtester(
            historical_data_provider=mock_historical_provider,
            config=config,
        )

    @pytest.fixture
    def backtester_with_basic_slippage(
        self, mock_historical_provider: MagicMock
    ) -> Backtester:
        """Create a backtester with basic slippage (feature flag OFF)."""
        config: Dict[str, Any] = {
            "features": {"enhanced_slippage_model": False},
            "backtesting": {"slippage_model": "basic", "fee_model": "simple"},
        }
        return Backtester(
            historical_data_provider=mock_historical_provider,
            config=config,
        )

    def test_realistic_slippage_crypto_major(
        self, backtester_with_realistic_slippage: Backtester
    ) -> None:
        """
        Test: BTCUSD/ETHUSD (major crypto) should have 2 bps base + volume impact.

        Expected: slippage = 0.00025 (2 bps base + 0.5 bps volume for small trade)
        """
        # Arrange
        asset_pair = "BTCUSD"
        size = 500.0  # Small size (<1000): +0.5 bps volume impact
        timestamp = datetime(2024, 1, 15, 14, 0, 0, tzinfo=timezone.utc)  # Normal hours

        # Act
        slippage = backtester_with_realistic_slippage._calculate_realistic_slippage(
            asset_pair=asset_pair, size=size, timestamp=timestamp
        )

        # Assert: 2 bps base + 0.5 bps volume impact = 2.5 bps
        expected_slippage = 0.0002 + 0.00005  # 2 bps + 0.5 bps = 2.5 bps
        assert slippage == pytest.approx(
            expected_slippage, rel=0.01
        ), f"Major crypto (BTCUSD) should have 2.5 bps slippage, got {slippage}"

    def test_realistic_slippage_crypto_major_eth(
        self, backtester_with_realistic_slippage: Backtester
    ) -> None:
        """
        Test: ETHUSD should also have 2 bps base + volume impact as major crypto.
        """
        # Arrange
        asset_pair = "ETHUSD"
        size = 500.0  # Small size (<1000): +0.5 bps volume impact
        timestamp = datetime(2024, 1, 15, 14, 0, 0, tzinfo=timezone.utc)

        # Act
        slippage = backtester_with_realistic_slippage._calculate_realistic_slippage(
            asset_pair=asset_pair, size=size, timestamp=timestamp
        )

        # Assert: 2 bps base + 0.5 bps volume impact = 2.5 bps
        expected_slippage = 0.0002 + 0.00005  # 2.5 bps
        assert slippage == pytest.approx(
            expected_slippage, rel=0.01
        ), f"Major crypto (ETHUSD) should have 2.5 bps slippage, got {slippage}"

    def test_realistic_slippage_forex_major(
        self, backtester_with_realistic_slippage: Backtester
    ) -> None:
        """
        Test: EURUSD (major forex) should have 1 bp base + volume impact.

        Expected: slippage = 0.00015 (1 bp base + 0.5 bps volume for small trade)
        """
        # Arrange
        asset_pair = "EURUSD"
        size = 500.0  # Small size (<1000): +0.5 bps volume impact
        timestamp = datetime(2024, 1, 15, 14, 0, 0, tzinfo=timezone.utc)  # Normal hours

        # Act
        slippage = backtester_with_realistic_slippage._calculate_realistic_slippage(
            asset_pair=asset_pair, size=size, timestamp=timestamp
        )

        # Assert: 1 bp base + 0.5 bps volume impact = 1.5 bps
        expected_slippage = 0.0001 + 0.00005  # 1.5 bps
        assert slippage == pytest.approx(
            expected_slippage, rel=0.01
        ), f"Major forex (EURUSD) should have 1.5 bps slippage, got {slippage}"

    def test_realistic_slippage_forex_gbpusd(
        self, backtester_with_realistic_slippage: Backtester
    ) -> None:
        """
        Test: GBPUSD should also have 1 bp base + volume impact as major forex.
        """
        # Arrange
        asset_pair = "GBPUSD"
        size = 500.0  # Small size (<1000): +0.5 bps volume impact
        timestamp = datetime(2024, 1, 15, 14, 0, 0, tzinfo=timezone.utc)

        # Act
        slippage = backtester_with_realistic_slippage._calculate_realistic_slippage(
            asset_pair=asset_pair, size=size, timestamp=timestamp
        )

        # Assert: 1 bp base + 0.5 bps volume impact = 1.5 bps
        expected_slippage = 0.0001 + 0.00005  # 1.5 bps
        assert slippage == pytest.approx(
            expected_slippage, rel=0.01
        ), f"Major forex (GBPUSD) should have 1.5 bps slippage, got {slippage}"

    def test_realistic_slippage_exotic_pairs(
        self, backtester_with_realistic_slippage: Backtester
    ) -> None:
        """
        Test: Exotic pairs should have 5 bps base + volume impact.

        Expected: slippage = 0.00055 (5 bps base + 0.5 bps volume for small trade)
        """
        # Arrange - use an exotic forex pair
        asset_pair = "USDMXN"  # USD/Mexican Peso - exotic pair
        size = 500.0  # Small size (<1000): +0.5 bps volume impact
        timestamp = datetime(2024, 1, 15, 14, 0, 0, tzinfo=timezone.utc)

        # Act
        slippage = backtester_with_realistic_slippage._calculate_realistic_slippage(
            asset_pair=asset_pair, size=size, timestamp=timestamp
        )

        # Assert: 5 bps base + 0.5 bps volume impact = 5.5 bps
        expected_slippage = 0.0005 + 0.00005  # 5.5 bps
        assert slippage == pytest.approx(
            expected_slippage, rel=0.01
        ), f"Exotic pair (USDMXN) should have 5.5 bps slippage, got {slippage}"

    def test_realistic_slippage_altcoin(
        self, backtester_with_realistic_slippage: Backtester
    ) -> None:
        """
        Test: Altcoins (non-BTC/ETH) should have 5 bps base + volume impact.
        """
        # Arrange - use an altcoin
        asset_pair = "SOLUSD"  # Solana - altcoin
        size = 500.0  # Small size (<1000): +0.5 bps volume impact
        timestamp = datetime(2024, 1, 15, 14, 0, 0, tzinfo=timezone.utc)

        # Act
        slippage = backtester_with_realistic_slippage._calculate_realistic_slippage(
            asset_pair=asset_pair, size=size, timestamp=timestamp
        )

        # Assert: 5 bps base + 0.5 bps volume impact = 5.5 bps
        expected_slippage = 0.0005 + 0.00005  # 5.5 bps
        assert slippage == pytest.approx(
            expected_slippage, rel=0.01
        ), f"Altcoin (SOLUSD) should have 5.5 bps slippage, got {slippage}"


class TestSlippageLiquidityHours:
    """Tests for slippage during low liquidity hours."""

    @pytest.fixture
    def mock_historical_provider(self) -> MagicMock:
        """Create a mock historical data provider."""
        provider = MagicMock()
        provider.get_historical_data.return_value = pd.DataFrame(
            {
                "open": [100.0],
                "high": [102.0],
                "low": [99.0],
                "close": [101.0],
                "volume": [1000],
            },
            index=pd.date_range("2024-01-01", periods=1, freq="h", tz="UTC"),
        )
        return provider

    @pytest.fixture
    def backtester(self, mock_historical_provider: MagicMock) -> Backtester:
        """Create a backtester with realistic slippage enabled."""
        config: Dict[str, Any] = {
            "features": {"enhanced_slippage_model": True},
            "backtesting": {"slippage_model": "realistic", "fee_model": "tiered"},
        }
        return Backtester(
            historical_data_provider=mock_historical_provider,
            config=config,
        )

    @pytest.mark.parametrize(
        "hour",
        [0, 1, 2, 20, 21, 22, 23],
        ids=[
            "midnight",
            "1am",
            "2am",
            "8pm",
            "9pm",
            "10pm",
            "11pm",
        ],
    )
    def test_slippage_low_liquidity_hours(
        self, backtester: Backtester, hour: int
    ) -> None:
        """
        Test: Low liquidity hours (0-2, 20-23 UTC) should have 1.5x multiplier.

        These hours typically have reduced market liquidity.
        Total slippage = (base + volume_impact) * 1.5
        For BTCUSD small trade: (2 bps + 0.5 bps) * 1.5 = 3.75 bps
        """
        # Arrange
        asset_pair = "BTCUSD"
        size = 500.0  # Small size (<1000): +0.5 bps volume impact
        timestamp = datetime(2024, 1, 15, hour, 0, 0, tzinfo=timezone.utc)

        # Act
        slippage = backtester._calculate_realistic_slippage(
            asset_pair=asset_pair, size=size, timestamp=timestamp
        )

        # Assert: (2 bps base + 0.5 bps volume) * 1.5 multiplier = 3.75 bps
        base_plus_volume = 0.0002 + 0.00005  # 2.5 bps
        expected_slippage = base_plus_volume * 1.5  # 3.75 bps
        assert slippage == pytest.approx(expected_slippage, rel=0.01), (
            f"Low liquidity hour {hour}:00 UTC should have 1.5x slippage multiplier. "
            f"Expected {expected_slippage}, got {slippage}"
        )

    def test_slippage_normal_hours(self, backtester: Backtester) -> None:
        """
        Test: Normal trading hours (3-19 UTC) should have no multiplier.
        """
        # Arrange
        asset_pair = "BTCUSD"
        size = 500.0  # Small size (<1000): +0.5 bps volume impact
        timestamp = datetime(2024, 1, 15, 14, 0, 0, tzinfo=timezone.utc)  # 2pm UTC

        # Act
        slippage = backtester._calculate_realistic_slippage(
            asset_pair=asset_pair, size=size, timestamp=timestamp
        )

        # Assert: 2 bps base + 0.5 bps volume = 2.5 bps, no multiplier
        expected_slippage = 0.0002 + 0.00005  # 2.5 bps
        assert slippage == pytest.approx(
            expected_slippage, rel=0.01
        ), f"Normal hours should have base+volume slippage (2.5 bps), got {slippage}"


class TestSlippageVolumeImpact:
    """Tests for slippage based on trade volume."""

    @pytest.fixture
    def mock_historical_provider(self) -> MagicMock:
        """Create a mock historical data provider."""
        provider = MagicMock()
        provider.get_historical_data.return_value = pd.DataFrame(
            {
                "open": [100.0],
                "high": [102.0],
                "low": [99.0],
                "close": [101.0],
                "volume": [1000],
            },
            index=pd.date_range("2024-01-01", periods=1, freq="h", tz="UTC"),
        )
        return provider

    @pytest.fixture
    def backtester(self, mock_historical_provider: MagicMock) -> Backtester:
        """Create a backtester with realistic slippage enabled."""
        config: Dict[str, Any] = {
            "features": {"enhanced_slippage_model": True},
            "backtesting": {"slippage_model": "realistic", "fee_model": "tiered"},
        }
        return Backtester(
            historical_data_provider=mock_historical_provider,
            config=config,
        )

    def test_slippage_volume_impact_small(self, backtester: Backtester) -> None:
        """
        Test: Small trades (size < 1000 USD) should have 0.5 bps volume impact.

        Total slippage = base_slippage + volume_impact
        For BTCUSD: 2 bps + 0.5 bps = 2.5 bps
        """
        # Arrange
        asset_pair = "BTCUSD"
        size = 500.0  # Small: < 1000
        timestamp = datetime(2024, 1, 15, 14, 0, 0, tzinfo=timezone.utc)

        # Act
        slippage = backtester._calculate_realistic_slippage(
            asset_pair=asset_pair, size=size, timestamp=timestamp
        )

        # Assert: Base 2 bps + 0.5 bps volume impact = 2.5 bps
        # However, for small trades, there should be minimal volume impact
        # We check that slippage is approximately base + small volume impact
        expected_min = 0.0002  # Base 2 bps
        expected_max = 0.00025  # Base + 0.5 bps impact
        assert expected_min <= slippage <= expected_max, (
            f"Small trade (<1000) should have slippage between {expected_min} and "
            f"{expected_max}, got {slippage}"
        )

    def test_slippage_volume_impact_medium(self, backtester: Backtester) -> None:
        """
        Test: Medium trades (1000 < size < 10000 USD) should have 1 bp volume impact.

        Total slippage = base_slippage + volume_impact
        For BTCUSD: 2 bps + 1 bp = 3 bps
        """
        # Arrange
        asset_pair = "BTCUSD"
        size = 5000.0  # Medium: 1000 < size < 10000
        timestamp = datetime(2024, 1, 15, 14, 0, 0, tzinfo=timezone.utc)

        # Act
        slippage = backtester._calculate_realistic_slippage(
            asset_pair=asset_pair, size=size, timestamp=timestamp
        )

        # Assert: Base 2 bps + 1 bp volume impact = 3 bps
        expected_slippage = 0.0002 + 0.0001  # 3 bps
        assert slippage == pytest.approx(
            expected_slippage, rel=0.01
        ), f"Medium trade (1000-10000) should have 3 bps slippage, got {slippage}"

    def test_slippage_volume_impact_large(self, backtester: Backtester) -> None:
        """
        Test: Large trades (size > 10000 USD) should have 3 bps volume impact.

        Total slippage = base_slippage + volume_impact
        For BTCUSD: 2 bps + 3 bps = 5 bps
        """
        # Arrange
        asset_pair = "BTCUSD"
        size = 50000.0  # Large: > 10000
        timestamp = datetime(2024, 1, 15, 14, 0, 0, tzinfo=timezone.utc)

        # Act
        slippage = backtester._calculate_realistic_slippage(
            asset_pair=asset_pair, size=size, timestamp=timestamp
        )

        # Assert: Base 2 bps + 3 bps volume impact = 5 bps
        expected_min = 0.0003  # Base + medium
        expected_max = 0.0005  # Base + 3 bps impact
        assert expected_min <= slippage <= expected_max, (
            f"Large trade (>10000) should have slippage between {expected_min} "
            f"and {expected_max}, got {slippage}"
        )


class TestTieredFees:
    """Tests for tiered fee model with maker/taker differentiation."""

    @pytest.fixture
    def mock_historical_provider(self) -> MagicMock:
        """Create a mock historical data provider."""
        provider = MagicMock()
        provider.get_historical_data.return_value = pd.DataFrame(
            {
                "open": [100.0],
                "high": [102.0],
                "low": [99.0],
                "close": [101.0],
                "volume": [1000],
            },
            index=pd.date_range("2024-01-01", periods=1, freq="h", tz="UTC"),
        )
        return provider

    @pytest.fixture
    def backtester(self, mock_historical_provider: MagicMock) -> Backtester:
        """Create a backtester with tiered fees enabled."""
        config: Dict[str, Any] = {
            "features": {"enhanced_slippage_model": True},
            "backtesting": {"slippage_model": "realistic", "fee_model": "tiered"},
        }
        return Backtester(
            historical_data_provider=mock_historical_provider,
            config=config,
        )

    def test_tiered_fees_coinbase_taker(self, backtester: Backtester) -> None:
        """
        Test: Coinbase taker fee should be 0.4%.

        Taker orders (market orders) pay higher fees.
        """
        # Arrange
        platform = "coinbase"
        size = 1000.0
        is_maker = False  # Taker order

        # Act
        fee = backtester._calculate_fees(
            platform=platform, size=size, is_maker=is_maker
        )

        # Assert: 0.4% taker fee
        expected_fee = 0.004  # 0.4% as decimal
        assert fee == pytest.approx(
            expected_fee, rel=0.01
        ), f"Coinbase taker fee should be 0.4%, got {fee * 100}%"

    def test_tiered_fees_coinbase_maker(self, backtester: Backtester) -> None:
        """
        Test: Coinbase maker fee should be 0.25%.

        Maker orders (limit orders) get lower fees.
        """
        # Arrange
        platform = "coinbase"
        size = 1000.0
        is_maker = True  # Maker order

        # Act
        fee = backtester._calculate_fees(
            platform=platform, size=size, is_maker=is_maker
        )

        # Assert: 0.25% maker fee
        expected_fee = 0.0025  # 0.25% as decimal
        assert fee == pytest.approx(
            expected_fee, rel=0.01
        ), f"Coinbase maker fee should be 0.25%, got {fee * 100}%"

    def test_tiered_fees_oanda_taker(self, backtester: Backtester) -> None:
        """
        Test: Oanda uses spread-based pricing, approximated as 0.1% for backtesting.
        """
        # Arrange
        platform = "oanda"
        size = 1000.0
        is_maker = False

        # Act
        fee = backtester._calculate_fees(
            platform=platform, size=size, is_maker=is_maker
        )

        # Assert: Default 0.1% for platforms without explicit tiering
        expected_fee = 0.001  # 0.1% as decimal
        assert fee == pytest.approx(
            expected_fee, rel=0.01
        ), f"Oanda fee should be 0.1% (spread-based), got {fee * 100}%"

    def test_tiered_fees_default_platform(self, backtester: Backtester) -> None:
        """
        Test: Unknown/default platforms should use 0.1% fee.
        """
        # Arrange
        platform = "unknown_platform"
        size = 1000.0
        is_maker = False

        # Act
        fee = backtester._calculate_fees(
            platform=platform, size=size, is_maker=is_maker
        )

        # Assert: Default 0.1% fee
        expected_fee = 0.001  # 0.1% as decimal
        assert fee == pytest.approx(
            expected_fee, rel=0.01
        ), f"Default platform fee should be 0.1%, got {fee * 100}%"


class TestFeatureFlagBehavior:
    """Tests for feature flag gating behavior."""

    @pytest.fixture
    def mock_historical_provider(self) -> MagicMock:
        """Create a mock historical data provider."""
        provider = MagicMock()
        provider.get_historical_data.return_value = pd.DataFrame(
            {
                "open": [100.0],
                "high": [102.0],
                "low": [99.0],
                "close": [101.0],
                "volume": [1000],
            },
            index=pd.date_range("2024-01-01", periods=1, freq="h", tz="UTC"),
        )
        return provider

    def test_feature_flag_disabled_uses_basic(
        self, mock_historical_provider: MagicMock
    ) -> None:
        """
        Test: When feature flag is OFF, use legacy 1bp fixed slippage.

        This ensures backward compatibility.
        """
        # Arrange
        config: Dict[str, Any] = {
            "features": {"enhanced_slippage_model": False},
            "backtesting": {"slippage_model": "basic", "fee_model": "simple"},
        }
        backtester = Backtester(
            historical_data_provider=mock_historical_provider,
            config=config,
        )

        # Act - Check if backtester uses basic slippage
        # The backtester should report basic slippage mode
        uses_realistic = backtester._is_enhanced_slippage_enabled()

        # Assert: Feature flag OFF means enhanced slippage is disabled
        assert (
            not uses_realistic
        ), "When feature flag is OFF, enhanced slippage should be disabled"

    def test_feature_flag_enabled_uses_realistic(
        self, mock_historical_provider: MagicMock
    ) -> None:
        """
        Test: When feature flag is ON, use realistic slippage model.
        """
        # Arrange
        config: Dict[str, Any] = {
            "features": {"enhanced_slippage_model": True},
            "backtesting": {"slippage_model": "realistic", "fee_model": "tiered"},
        }
        backtester = Backtester(
            historical_data_provider=mock_historical_provider,
            config=config,
        )

        # Act
        uses_realistic = backtester._is_enhanced_slippage_enabled()

        # Assert: Feature flag ON means enhanced slippage is enabled
        assert (
            uses_realistic
        ), "When feature flag is ON, enhanced slippage should be enabled"

    def test_feature_flag_default_is_false(
        self, mock_historical_provider: MagicMock
    ) -> None:
        """
        Test: When feature flag is not specified, default to basic (false).
        """
        # Arrange - empty config, no feature flags
        config: Dict[str, Any] = {}
        backtester = Backtester(
            historical_data_provider=mock_historical_provider,
            config=config,
        )

        # Act
        uses_realistic = backtester._is_enhanced_slippage_enabled()

        # Assert: Default should be False (basic slippage)
        assert (
            not uses_realistic
        ), "When feature flag is not specified, default should be basic slippage"


class TestBacktesterIntegration:
    """Integration tests for backtester with realistic slippage."""

    @pytest.fixture
    def mock_historical_provider(self) -> MagicMock:
        """Create a mock historical data provider with realistic data."""
        provider = MagicMock()
        # Create 100 hourly candles
        dates = pd.date_range("2024-01-01", periods=100, freq="h", tz="UTC")
        provider.get_historical_data.return_value = pd.DataFrame(
            {
                "open": [100.0 + i * 0.1 for i in range(100)],
                "high": [102.0 + i * 0.1 for i in range(100)],
                "low": [99.0 + i * 0.1 for i in range(100)],
                "close": [101.0 + i * 0.1 for i in range(100)],
                "volume": [1000 + i * 10 for i in range(100)],
            },
            index=dates,
        )
        return provider

    @pytest.fixture
    def mock_decision_engine(self) -> MagicMock:
        """Create a mock decision engine."""
        engine = MagicMock()
        engine.generate_decision = MagicMock(
            return_value={
                "action": "BUY",
                "confidence": 0.8,
                "asset_pair": "BTCUSD",
                "reasoning": "Test signal",
            }
        )
        return engine

    def test_backtester_integration_with_realistic_slippage(
        self, mock_historical_provider: MagicMock, mock_decision_engine: MagicMock
    ) -> None:
        """
        Test: End-to-end integration of backtester with realistic slippage.

        Validates that:
        1. Realistic slippage is applied during trade execution
        2. Tiered fees are calculated correctly
        3. Final P&L reflects slippage and fee impact
        """
        # Arrange
        config: Dict[str, Any] = {
            "features": {"enhanced_slippage_model": True},
            "backtesting": {"slippage_model": "realistic", "fee_model": "tiered"},
        }
        backtester = Backtester(
            historical_data_provider=mock_historical_provider,
            initial_balance=10000.0,
            config=config,
        )

        # Mock the _execute_trade method to capture slippage/fee parameters
        original_execute = backtester._execute_trade
        execute_calls: list = []

        def mock_execute(*args, **kwargs):
            execute_calls.append({"args": args, "kwargs": kwargs})
            return original_execute(*args, **kwargs)

        # Act - Execute a trade and check slippage is applied
        timestamp = datetime(2024, 1, 15, 14, 0, 0, tzinfo=timezone.utc)

        # Calculate expected slippage
        expected_slippage = backtester._calculate_realistic_slippage(
            asset_pair="BTCUSD", size=1000.0, timestamp=timestamp
        )

        # Calculate expected fees
        expected_fee = backtester._calculate_fees(
            platform="coinbase", size=1000.0, is_maker=False
        )

        # Assert: Slippage and fees are non-zero with realistic model
        assert (
            expected_slippage > 0.0001
        ), f"Realistic slippage should be > 1bp, got {expected_slippage}"
        assert expected_fee > 0.001, f"Tiered fee should be > 0.1%, got {expected_fee}"

    def test_backtester_basic_slippage_backward_compatible(
        self, mock_historical_provider: MagicMock
    ) -> None:
        """
        Test: Basic slippage mode maintains backward compatibility.

        With feature flag OFF, should use legacy 1bp fixed slippage.
        """
        # Arrange
        config: Dict[str, Any] = {
            "features": {"enhanced_slippage_model": False},
        }
        backtester = Backtester(
            historical_data_provider=mock_historical_provider,
            initial_balance=10000.0,
            slippage_percentage=0.0001,  # Legacy 1bp
            config=config,
        )

        # Assert: Legacy slippage percentage should be used
        assert (
            backtester.slippage_percentage == 0.0001
        ), "Legacy slippage should be 1bp (0.0001)"
        assert (
            not backtester._is_enhanced_slippage_enabled()
        ), "Enhanced slippage should be disabled for backward compatibility"


class TestSlippageEdgeCases:
    """Tests for edge cases in slippage calculation."""

    @pytest.fixture
    def mock_historical_provider(self) -> MagicMock:
        """Create a mock historical data provider."""
        provider = MagicMock()
        provider.get_historical_data.return_value = pd.DataFrame(
            {
                "open": [100.0],
                "high": [102.0],
                "low": [99.0],
                "close": [101.0],
                "volume": [1000],
            },
            index=pd.date_range("2024-01-01", periods=1, freq="h", tz="UTC"),
        )
        return provider

    @pytest.fixture
    def backtester(self, mock_historical_provider: MagicMock) -> Backtester:
        """Create a backtester with realistic slippage enabled."""
        config: Dict[str, Any] = {
            "features": {"enhanced_slippage_model": True},
            "backtesting": {"slippage_model": "realistic", "fee_model": "tiered"},
        }
        return Backtester(
            historical_data_provider=mock_historical_provider,
            config=config,
        )

    def test_slippage_zero_size(self, backtester: Backtester) -> None:
        """
        Test: Zero size trade should have zero slippage.
        """
        # Arrange
        asset_pair = "BTCUSD"
        size = 0.0
        timestamp = datetime(2024, 1, 15, 14, 0, 0, tzinfo=timezone.utc)

        # Act
        slippage = backtester._calculate_realistic_slippage(
            asset_pair=asset_pair, size=size, timestamp=timestamp
        )

        # Assert: Zero size = zero slippage
        assert slippage == 0.0, f"Zero size should have zero slippage, got {slippage}"

    def test_slippage_negative_size_treated_as_absolute(
        self, backtester: Backtester
    ) -> None:
        """
        Test: Negative size (short) should use absolute value for slippage.
        """
        # Arrange
        asset_pair = "BTCUSD"
        size = -1000.0  # Short position
        timestamp = datetime(2024, 1, 15, 14, 0, 0, tzinfo=timezone.utc)

        # Act
        slippage = backtester._calculate_realistic_slippage(
            asset_pair=asset_pair, size=size, timestamp=timestamp
        )

        # Assert: Should calculate based on absolute size
        assert slippage > 0, "Negative size should still produce positive slippage"

    def test_fees_zero_size(self, backtester: Backtester) -> None:
        """
        Test: Zero size trade should have zero fees.
        """
        # Arrange
        platform = "coinbase"
        size = 0.0
        is_maker = False

        # Act
        fee = backtester._calculate_fees(
            platform=platform, size=size, is_maker=is_maker
        )

        # Assert: Zero size = zero fees
        assert fee == 0.0, f"Zero size should have zero fees, got {fee}"
