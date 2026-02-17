"""
Tests for forex exit price fix — EUR_USD symbol mapping in UnifiedDataProvider.

Root cause: get_current_price("EUR_USD") was failing silently and falling back
to entry_price, causing P&L = $0 on all EUR_USD trades.

Fix: UnifiedDataProvider now calls OandaDataProvider.get_current_price_direct()
for forex pairs, using the Oanda pricing endpoint (bid/ask/mid) instead of
the fragile 1m-candle path.
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock, patch
from pathlib import Path
import tempfile
import json
import requests


# ────────────────────────────────────────────────────────────────────────────
# OandaDataProvider — get_current_price_direct
# ────────────────────────────────────────────────────────────────────────────


class TestOandaGetCurrentPriceDirect:
    """Unit tests for OandaDataProvider.get_current_price_direct()"""

    def _make_provider(self):
        from finance_feedback_engine.data_providers.oanda_data import OandaDataProvider

        creds = {
            "access_token": "test-token",
            "account_id": "001-001-0000000-001",
            "environment": "practice",
        }
        return OandaDataProvider(credentials=creds)

    def test_returns_mid_price_from_bid_ask(self):
        """Verify mid price is calculated correctly from bid/ask."""
        provider = self._make_provider()

        mock_response = {
            "prices": [
                {
                    "instrument": "EUR_USD",
                    "status": "tradeable",
                    "bids": [{"price": "1.19000", "liquidity": 10000000}],
                    "asks": [{"price": "1.19020", "liquidity": 10000000}],
                    "time": "2026-02-17T03:00:00.000000000Z",
                }
            ]
        }

        with patch("requests.get") as mock_get:
            mock_get.return_value = Mock(
                status_code=200,
                json=lambda: mock_response,
                raise_for_status=lambda: None,
            )

            result = provider.get_current_price_direct("EUR_USD")

        assert result is not None
        assert result["price"] == pytest.approx((1.19000 + 1.19020) / 2, abs=1e-6)
        assert result["provider"] == "oanda_pricing"
        assert result["asset_pair"] == "EUR_USD"

    def test_normalizes_eurusd_to_eur_usd_for_api(self):
        """Verify EURUSD (no underscore) is normalized to EUR_USD for Oanda API."""
        provider = self._make_provider()

        mock_response = {
            "prices": [
                {
                    "instrument": "EUR_USD",
                    "status": "tradeable",
                    "bids": [{"price": "1.19100", "liquidity": 10000000}],
                    "asks": [{"price": "1.19120", "liquidity": 10000000}],
                    "time": "2026-02-17T03:00:00.000000000Z",
                }
            ]
        }

        with patch("requests.get") as mock_get:
            mock_get.return_value = Mock(
                status_code=200,
                json=lambda: mock_response,
                raise_for_status=lambda: None,
            )

            result = provider.get_current_price_direct("EURUSD")

        assert result is not None
        # Verify the API was called with EUR_USD (underscore format)
        call_kwargs = mock_get.call_args
        assert call_kwargs[1]["params"]["instruments"] == "EUR_USD"

    def test_returns_none_on_empty_prices(self):
        """Verify None returned when Oanda returns no prices."""
        provider = self._make_provider()

        with patch("requests.get") as mock_get:
            mock_get.return_value = Mock(
                status_code=200,
                json=lambda: {"prices": []},
                raise_for_status=lambda: None,
            )

            result = provider.get_current_price_direct("EUR_USD")

        assert result is None

    def test_returns_none_on_api_error(self):
        """Verify None returned (not exception) on API error."""
        provider = self._make_provider()

        with patch("requests.get") as mock_get:
            mock_get.side_effect = Exception("Connection timeout")

            result = provider.get_current_price_direct("EUR_USD")

        assert result is None

    def test_returns_none_when_no_account_id(self):
        """Verify None returned when account_id is missing."""
        from finance_feedback_engine.data_providers.oanda_data import OandaDataProvider

        creds = {"access_token": "test-token"}  # No account_id
        provider = OandaDataProvider(credentials=creds)

        result = provider.get_current_price_direct("EUR_USD")
        assert result is None

    def test_handles_ask_only_price(self):
        """Verify price computed from ask only when no bids."""
        provider = self._make_provider()

        mock_response = {
            "prices": [
                {
                    "instrument": "EUR_USD",
                    "status": "tradeable",
                    "bids": [],
                    "asks": [{"price": "1.19010", "liquidity": 10000000}],
                    "time": "2026-02-17T03:00:00.000000000Z",
                }
            ]
        }

        with patch("requests.get") as mock_get:
            mock_get.return_value = Mock(
                status_code=200,
                json=lambda: mock_response,
                raise_for_status=lambda: None,
            )

            result = provider.get_current_price_direct("EUR_USD")

        assert result is not None
        assert result["price"] == pytest.approx(1.19010, abs=1e-6)

    def test_gbp_usd_normalized_correctly(self):
        """Verify GBP_USD, GBPUSD both normalize to GBP_USD for API."""
        provider = self._make_provider()

        for symbol in ["GBP_USD", "GBPUSD", "gbpusd"]:
            normalized = provider._normalize_asset_pair(symbol)
            assert normalized == "GBP_USD", f"Expected GBP_USD, got {normalized} for {symbol}"


# ────────────────────────────────────────────────────────────────────────────
# UnifiedDataProvider — get_current_price routing for forex
# ────────────────────────────────────────────────────────────────────────────


class TestUnifiedProviderForexPriceFix:
    """Verify UnifiedDataProvider routes forex pairs to Oanda pricing endpoint."""

    def _make_unified_provider(self, oanda_price_return=None, oanda_raises=False):
        """Create UnifiedDataProvider with mocked Oanda provider."""
        from finance_feedback_engine.data_providers.unified_data_provider import (
            UnifiedDataProvider,
        )

        provider = UnifiedDataProvider.__new__(UnifiedDataProvider)
        provider.config = {}
        provider.alpha_vantage = None
        provider.coinbase = None

        from unittest.mock import MagicMock
        from cachetools import TTLCache

        provider._cache = TTLCache(maxsize=100, ttl=120)

        mock_oanda = MagicMock()
        if oanda_raises:
            mock_oanda.get_current_price_direct.side_effect = Exception("Oanda API error")
        else:
            mock_oanda.get_current_price_direct.return_value = oanda_price_return

        provider.oanda = mock_oanda

        return provider

    def test_eur_usd_routed_to_oanda_pricing_endpoint(self):
        """EUR_USD price lookup uses Oanda pricing endpoint, not candles."""
        from finance_feedback_engine.data_providers.unified_data_provider import (
            UnifiedDataProvider,
        )

        expected = {
            "asset_pair": "EUR_USD",
            "price": 1.19110,
            "provider": "oanda_pricing",
            "timestamp": "2026-02-17T03:00:00Z",
        }
        provider = self._make_unified_provider(oanda_price_return=expected)

        result = provider.get_current_price("EUR_USD")

        assert result is not None
        assert result["price"] == 1.19110
        assert result["provider"] == "oanda_pricing"
        provider.oanda.get_current_price_direct.assert_called_once_with("EUR_USD")

    def test_eurusd_no_underscore_also_routed_to_oanda(self):
        """EURUSD (no underscore) also routes to Oanda pricing endpoint."""
        expected = {
            "asset_pair": "EURUSD",
            "price": 1.19050,
            "provider": "oanda_pricing",
            "timestamp": "2026-02-17T03:00:00Z",
        }
        provider = self._make_unified_provider(oanda_price_return=expected)

        result = provider.get_current_price("EURUSD")

        assert result is not None
        assert result["price"] == 1.19050
        provider.oanda.get_current_price_direct.assert_called_once_with("EURUSD")

    def test_gbp_usd_routed_to_oanda(self):
        """GBP_USD uses Oanda pricing endpoint."""
        expected = {
            "asset_pair": "GBP_USD",
            "price": 1.2550,
            "provider": "oanda_pricing",
            "timestamp": "2026-02-17T03:00:00Z",
        }
        provider = self._make_unified_provider(oanda_price_return=expected)

        result = provider.get_current_price("GBP_USD")

        assert result is not None
        assert result["price"] == 1.2550

    def test_btcusd_does_not_use_oanda_pricing(self):
        """BTC-USD is crypto, should NOT use Oanda pricing endpoint."""
        from finance_feedback_engine.data_providers.unified_data_provider import (
            UnifiedDataProvider,
        )

        provider = self._make_unified_provider(
            oanda_price_return={"price": 99999, "provider": "oanda_pricing"}
        )

        # Mock the candles path (which is what crypto uses)
        with patch.object(provider, "get_candles", return_value=([], "failed")):
            result = provider.get_current_price("BTCUSD")

        # Oanda pricing should NOT have been called for crypto
        provider.oanda.get_current_price_direct.assert_not_called()
        assert result is None  # candles returned empty

    def test_forex_falls_back_to_candles_when_oanda_fails(self):
        """When Oanda pricing fails, falls back to candles path."""
        provider = self._make_unified_provider(oanda_raises=True)

        # Mock candles fallback to succeed
        candle = {"close": 1.19200, "timestamp": 1739757600}
        with patch.object(provider, "get_candles", return_value=([candle], "oanda")):
            result = provider.get_current_price("EUR_USD")

        # Should have fallen back to candles
        assert result is not None
        assert result["price"] == 1.19200
        assert result["provider"] == "oanda"

    def test_forex_oanda_returns_none_then_falls_back_to_candles(self):
        """When Oanda pricing returns None, falls back to candles."""
        provider = self._make_unified_provider(oanda_price_return=None)

        candle = {"close": 1.19300, "timestamp": 1739757600}
        with patch.object(provider, "get_candles", return_value=([candle], "oanda")):
            result = provider.get_current_price("EUR_USD")

        assert result is not None
        assert result["price"] == 1.19300


# ────────────────────────────────────────────────────────────────────────────
# End-to-end: TradeOutcomeRecorder → UnifiedDataProvider → Oanda pricing
# ────────────────────────────────────────────────────────────────────────────


class TestTradeOutcomeRecorderForexExitPrice:
    """End-to-end: EUR_USD position close produces non-zero P&L."""

    def test_eur_usd_position_close_gets_real_exit_price(self):
        """EUR_USD position close fetches exit price from Oanda, not entry_price."""
        from finance_feedback_engine.monitoring.trade_outcome_recorder import (
            TradeOutcomeRecorder,
        )

        # Simulate Oanda pricing endpoint returning a higher price
        mock_provider = MagicMock()
        mock_provider.get_current_price.return_value = {
            "price": 1.19250,  # higher than entry (1.19111)
            "provider": "oanda_pricing",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            recorder = TradeOutcomeRecorder(
                data_dir=temp_dir,
                unified_provider=mock_provider,
            )

            recorder.open_positions = {
                "EUR_USD_LONG": {
                    "trade_id": "forex-fix-test-001",
                    "product": "EUR_USD",
                    "side": "LONG",
                    "entry_time": "2026-02-17T00:00:00+00:00",
                    "entry_price": Decimal("1.19111"),
                    "entry_size": Decimal("10000"),
                }
            }

            outcomes = recorder.update_positions([])

            # Assert: provider called with EUR_USD (underscore format from Oanda)
            mock_provider.get_current_price.assert_called_once_with("EUR_USD")

            assert len(outcomes) == 1
            outcome = outcomes[0]

            # Exit price must be market price, NOT entry price
            assert Decimal(outcome["exit_price"]) == Decimal("1.19250")
            assert outcome["exit_price"] != outcome["entry_price"]

            # P&L = (1.19250 - 1.19111) * 10000 = 13.9
            pnl = Decimal(outcome["realized_pnl"])
            expected_pnl = (Decimal("1.19250") - Decimal("1.19111")) * Decimal("10000")
            assert pnl == expected_pnl
            assert pnl > Decimal("0"), "P&L should be positive (price moved in favor)"

    def test_eur_usd_short_position_close_correct_pnl(self):
        """EUR_USD SHORT position: price falling = profit."""
        from finance_feedback_engine.monitoring.trade_outcome_recorder import (
            TradeOutcomeRecorder,
        )

        mock_provider = MagicMock()
        mock_provider.get_current_price.return_value = {
            "price": 1.18900,  # lower than entry → profit for short
            "provider": "oanda_pricing",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            recorder = TradeOutcomeRecorder(
                data_dir=temp_dir,
                unified_provider=mock_provider,
            )

            recorder.open_positions = {
                "EUR_USD_SHORT": {
                    "trade_id": "forex-fix-test-002",
                    "product": "EUR_USD",
                    "side": "SHORT",
                    "entry_time": "2026-02-17T00:00:00+00:00",
                    "entry_price": Decimal("1.19111"),
                    "entry_size": Decimal("10000"),
                }
            }

            outcomes = recorder.update_positions([])

            assert len(outcomes) == 1
            pnl = Decimal(outcomes[0]["realized_pnl"])
            # For SHORT: (entry - exit) * size = (1.19111 - 1.18900) * 10000 = 21.1
            expected = (Decimal("1.19111") - Decimal("1.18900")) * Decimal("10000")
            assert pnl == expected
            assert pnl > Decimal("0")

    def test_stale_exit_price_not_equal_to_entry_price_after_fix(self):
        """
        Regression test: verifies the BUG is fixed.

        Before fix: exit_price == entry_price == 1.19111 (stale), P&L = 0.
        After fix:  exit_price = 1.19225 (market), P&L > 0.
        """
        from finance_feedback_engine.monitoring.trade_outcome_recorder import (
            TradeOutcomeRecorder,
        )

        ENTRY_PRICE = Decimal("1.19111")
        MARKET_PRICE = Decimal("1.19225")

        mock_provider = MagicMock()
        mock_provider.get_current_price.return_value = {
            "price": float(MARKET_PRICE),
            "provider": "oanda_pricing",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            recorder = TradeOutcomeRecorder(
                data_dir=temp_dir,
                unified_provider=mock_provider,
            )

            recorder.open_positions = {
                "EUR_USD_LONG": {
                    "trade_id": "regression-test-003",
                    "product": "EUR_USD",
                    "side": "LONG",
                    "entry_time": "2026-02-17T00:00:00+00:00",
                    "entry_price": ENTRY_PRICE,
                    "entry_size": Decimal("1000"),
                }
            }

            outcomes = recorder.update_positions([])

            assert len(outcomes) == 1
            outcome = outcomes[0]

            exit_price = Decimal(outcome["exit_price"])
            pnl = Decimal(outcome["realized_pnl"])

            # THE BUG: exit_price == entry_price, P&L = 0
            assert exit_price != ENTRY_PRICE, (
                f"BUG: exit_price ({exit_price}) == entry_price ({ENTRY_PRICE}). "
                "Exit price fix did not apply."
            )

            # THE FIX: exit_price = market price, P&L > 0
            assert exit_price == MARKET_PRICE
            assert pnl > Decimal("0"), f"P&L should be positive, got {pnl}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
