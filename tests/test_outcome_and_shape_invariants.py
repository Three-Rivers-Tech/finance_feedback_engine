"""Invariant tests for trade outcome recording, shape normalization, and ID handling.

Targets the exact code paths where production bugs have hidden:
- Outcome P&L computation correctness
- Exit price provenance (the zero-P&L bug)
- Shape normalization for IDs, positions, and portfolios
- Asset key resolution (BIP->BTCUSD, ETP->ETHUSD mapping)
"""

import json
import pytest
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch
from typing import Optional

from finance_feedback_engine.monitoring.trade_outcome_recorder import TradeOutcomeRecorder
from finance_feedback_engine.utils.shape_normalization import (
    normalize_scalar_id,
    merge_nested_payload,
    extract_portfolio_positions,
    position_product_id,
    asset_key_candidates,
    resolve_platform_client,
)
from finance_feedback_engine.agent.trade_execution_safety import (
    DecisionReservationPayload,
    reserve_trade_exposure,
    finalize_trade_reservation,
)


# ═══════════════════════════════════════════════════════════════════
# SEAM 1: normalize_scalar_id — the recurring ID shape bug
# ═══════════════════════════════════════════════════════════════════

class TestNormalizeScalarId:
    """IDs arrive in many shapes: string, tuple, list, nested dict.
    normalize_scalar_id must handle them all without crashing."""

    def test_plain_string(self):
        assert normalize_scalar_id("abc-123") == "abc-123"

    def test_none_returns_none(self):
        assert normalize_scalar_id(None) is None

    def test_empty_string_returns_none(self):
        assert normalize_scalar_id("") is None

    def test_whitespace_string_returns_none(self):
        assert normalize_scalar_id("   ") is None

    def test_tuple_unwraps_first(self):
        assert normalize_scalar_id(("abc-123",)) == "abc-123"

    def test_list_unwraps_first(self):
        assert normalize_scalar_id(["abc-123", "def-456"]) == "abc-123"

    def test_empty_tuple_returns_none(self):
        assert normalize_scalar_id(()) is None

    def test_empty_list_returns_none(self):
        assert normalize_scalar_id([]) is None

    def test_dict_with_id_key(self):
        assert normalize_scalar_id({"id": "abc-123"}) == "abc-123"

    def test_dict_with_decision_id_key(self):
        assert normalize_scalar_id({"decision_id": "abc-123"}) == "abc-123"

    def test_dict_with_nested_decision(self):
        assert normalize_scalar_id({"decision": {"id": "abc-123"}}) == "abc-123"

    def test_dict_with_no_known_keys(self):
        assert normalize_scalar_id({"foo": "bar"}) is None

    def test_integer_converted_to_string(self):
        assert normalize_scalar_id(42) == "42"

    def test_nested_tuple_in_dict(self):
        """Tuple inside dict — the real production shape."""
        assert normalize_scalar_id({"decision_id": ("abc-123",)}) == "abc-123"

    def test_arbitrary_object_returns_none(self):
        assert normalize_scalar_id(MagicMock(name="fake-id")) is None


# ═══════════════════════════════════════════════════════════════════
# SEAM 2: Trade outcome P&L computation
# ═══════════════════════════════════════════════════════════════════

class TestOutcomePnLComputation:
    """P&L must be computed correctly for LONG and SHORT positions."""

    @pytest.fixture
    def recorder(self, tmp_path):
        return TradeOutcomeRecorder(data_dir=str(tmp_path), use_async=False)

    def test_long_profit(self, recorder):
        """LONG: buy at 100, exit at 110 → +10 per unit."""
        outcome = recorder._create_outcome(
            trade_data={
                "trade_id": "t1",
                "product": "BTCUSD",
                "side": "LONG",
                "entry_time": "2026-03-31T10:00:00+00:00",
                "entry_price": Decimal("100"),
                "entry_size": Decimal("1"),
            },
            exit_time=datetime(2026, 3, 31, 11, 0, tzinfo=timezone.utc),
            exit_price=Decimal("110"),
            exit_size=Decimal("1"),
        )
        assert outcome is not None
        assert Decimal(outcome["realized_pnl"]) == Decimal("10")

    def test_long_loss(self, recorder):
        """LONG: buy at 100, exit at 90 → -10 per unit."""
        outcome = recorder._create_outcome(
            trade_data={
                "trade_id": "t2",
                "product": "BTCUSD",
                "side": "LONG",
                "entry_time": "2026-03-31T10:00:00+00:00",
                "entry_price": Decimal("100"),
                "entry_size": Decimal("1"),
            },
            exit_time=datetime(2026, 3, 31, 11, 0, tzinfo=timezone.utc),
            exit_price=Decimal("90"),
            exit_size=Decimal("1"),
        )
        assert outcome is not None
        assert Decimal(outcome["realized_pnl"]) == Decimal("-10")

    def test_short_profit(self, recorder):
        """SHORT: sell at 100, exit at 90 → +10 per unit."""
        outcome = recorder._create_outcome(
            trade_data={
                "trade_id": "t3",
                "product": "BTCUSD",
                "side": "SHORT",
                "entry_time": "2026-03-31T10:00:00+00:00",
                "entry_price": Decimal("100"),
                "entry_size": Decimal("1"),
            },
            exit_time=datetime(2026, 3, 31, 11, 0, tzinfo=timezone.utc),
            exit_price=Decimal("90"),
            exit_size=Decimal("1"),
        )
        assert outcome is not None
        assert Decimal(outcome["realized_pnl"]) == Decimal("10")

    def test_short_loss(self, recorder):
        """SHORT: sell at 100, exit at 110 → -10 per unit."""
        outcome = recorder._create_outcome(
            trade_data={
                "trade_id": "t4",
                "product": "BTCUSD",
                "side": "SHORT",
                "entry_time": "2026-03-31T10:00:00+00:00",
                "entry_price": Decimal("100"),
                "entry_size": Decimal("1"),
            },
            exit_time=datetime(2026, 3, 31, 11, 0, tzinfo=timezone.utc),
            exit_price=Decimal("110"),
            exit_size=Decimal("1"),
        )
        assert outcome is not None
        assert Decimal(outcome["realized_pnl"]) == Decimal("-10")

    def test_unknown_side_returns_none(self, recorder):
        outcome = recorder._create_outcome(
            trade_data={
                "trade_id": "t5",
                "product": "BTCUSD",
                "side": "UNKNOWN",
                "entry_time": "2026-03-31T10:00:00+00:00",
                "entry_price": Decimal("100"),
                "entry_size": Decimal("1"),
            },
            exit_time=datetime(2026, 3, 31, 11, 0, tzinfo=timezone.utc),
            exit_price=Decimal("110"),
            exit_size=Decimal("1"),
        )
        assert outcome is None

    def test_pnl_with_multiple_contracts(self, recorder):
        """SHORT 5 contracts: sell at 68000, exit at 67900 → +500."""
        outcome = recorder._create_outcome(
            trade_data={
                "trade_id": "t6",
                "product": "BIP-20DEC30-CDE",
                "side": "SHORT",
                "entry_time": "2026-03-31T10:00:00+00:00",
                "entry_price": Decimal("68000"),
                "entry_size": Decimal("5"),
            },
            exit_time=datetime(2026, 3, 31, 11, 0, tzinfo=timezone.utc),
            exit_price=Decimal("67900"),
            exit_size=Decimal("5"),
        )
        assert outcome is not None
        assert Decimal(outcome["realized_pnl"]) == Decimal("500")


# ═══════════════════════════════════════════════════════════════════
# SEAM 3: Exit price provenance — the zero-P&L bug
# ═══════════════════════════════════════════════════════════════════

class TestExitPriceProvenance:
    """Exit price must never silently default to entry price."""

    @pytest.fixture
    def recorder(self, tmp_path):
        return TradeOutcomeRecorder(data_dir=str(tmp_path), use_async=False)

    def test_entry_equals_exit_skipped(self, recorder):
        """If entry == exit, outcome is skipped (suspected stale)."""
        recorder.open_positions = {
            "BTC_SHORT": {
                "trade_id": "t1",
                "product": "BTCUSD",
                "side": "SHORT",
                "entry_time": "2026-03-31T10:00:00+00:00",
                "entry_price": Decimal("68000"),
                "entry_size": Decimal("1"),
                "last_price": Decimal("68000"),  # Same as entry
                "decision_id": "d1",
            }
        }
        # No current positions → BTC_SHORT detected as closed
        outcomes = recorder.update_positions([])
        assert len(outcomes) == 0, "entry==exit should be skipped"

    def test_no_exit_price_available_skipped(self, recorder):
        """If no exit price source available, outcome is skipped."""
        recorder.open_positions = {
            "BTC_SHORT": {
                "trade_id": "t1",
                "product": "BTCUSD",
                "side": "SHORT",
                "entry_time": "2026-03-31T10:00:00+00:00",
                "entry_price": Decimal("68000"),
                "entry_size": Decimal("1"),
                # No last_price, no unified_provider
                "decision_id": "d1",
            }
        }
        outcomes = recorder.update_positions([])
        assert len(outcomes) == 0, "No exit price should skip outcome"

    def test_valid_last_price_used_for_exit(self, recorder):
        """If last_price differs from entry, it's used as exit."""
        recorder.open_positions = {
            "BTC_SHORT": {
                "trade_id": "t1",
                "product": "BTCUSD",
                "side": "SHORT",
                "entry_time": "2026-03-31T10:00:00+00:00",
                "entry_price": Decimal("68000"),
                "entry_size": Decimal("1"),
                "last_price": Decimal("67500"),
                "decision_id": "d1",
            }
        }
        outcomes = recorder.update_positions([])
        assert len(outcomes) == 1
        assert outcomes[0]["exit_price"] == "67500"
        assert outcomes[0]["exit_price_source"] == "state:last_price"

    def test_flat_closure_alert_increments(self, recorder):
        """Consecutive flat closures (entry==exit) should increment counter."""
        recorder._consecutive_flat_closures = 0
        outcome = {
            "entry_price": "100",
            "exit_price": "100",
            "product": "TEST",
            "exit_price_source": "test",
        }
        recorder._emit_flat_close_alert_if_needed(outcome)
        assert recorder._consecutive_flat_closures == 1

    def test_non_flat_closure_resets_counter(self, recorder):
        recorder._consecutive_flat_closures = 5
        outcome = {
            "entry_price": "100",
            "exit_price": "105",
            "product": "TEST",
            "exit_price_source": "test",
        }
        recorder._emit_flat_close_alert_if_needed(outcome)
        assert recorder._consecutive_flat_closures == 0


# ═══════════════════════════════════════════════════════════════════
# SEAM 4: PnL recomputation / validation at write time
# ═══════════════════════════════════════════════════════════════════

class TestPnLRecomputationInvariant:
    """_recompute_realized_pnl must match _create_outcome for all side combos."""

    @pytest.fixture
    def recorder(self, tmp_path):
        return TradeOutcomeRecorder(data_dir=str(tmp_path), use_async=False)

    def test_recompute_matches_long(self, recorder):
        outcome = {
            "side": "LONG",
            "entry_price": "100",
            "exit_price": "110",
            "exit_size": "2",
            "fees": "0",
            "realized_pnl": "20",
        }
        recomputed = recorder._recompute_realized_pnl(outcome)
        assert recomputed == Decimal("20")

    def test_recompute_matches_short(self, recorder):
        outcome = {
            "side": "SHORT",
            "entry_price": "100",
            "exit_price": "90",
            "exit_size": "2",
            "fees": "0",
            "realized_pnl": "20",
        }
        recomputed = recorder._recompute_realized_pnl(outcome)
        assert recomputed == Decimal("20")

    def test_recompute_with_fees(self, recorder):
        outcome = {
            "side": "LONG",
            "entry_price": "100",
            "exit_price": "110",
            "exit_size": "1",
            "fees": "2.5",
            "realized_pnl": "7.5",
        }
        recomputed = recorder._recompute_realized_pnl(outcome)
        assert recomputed == Decimal("7.5")

    def test_recompute_corrects_wrong_pnl(self, recorder):
        """_validate_and_normalize_outcome should fix incorrect P&L."""
        outcome = {
            "trade_id": "t1",
            "side": "LONG",
            "entry_price": "100",
            "exit_price": "110",
            "exit_size": "1",
            "fees": "0",
            "realized_pnl": "999",  # WRONG
            "exit_time": "2026-03-31T11:00:00+00:00",
            "product": "BTCUSD",
            "exit_price_source": "test",
        }
        normalized = recorder._validate_and_normalize_outcome(outcome)
        assert normalized["realized_pnl"] == "10", "Should correct to actual P&L"

    def test_unknown_side_raises(self, recorder):
        outcome = {
            "side": "SIDEWAYS",
            "entry_price": "100",
            "exit_price": "110",
            "exit_size": "1",
            "fees": "0",
        }
        with pytest.raises(ValueError, match="Unknown side"):
            recorder._recompute_realized_pnl(outcome)


# ═══════════════════════════════════════════════════════════════════
# SEAM 5: Asset key candidates (product ID → canonical pair)
# ═══════════════════════════════════════════════════════════════════

class TestAssetKeyCandidates:
    """Product IDs must map to canonical pairs correctly."""

    def test_bip_maps_to_btcusd(self):
        candidates = asset_key_candidates("BIP-20DEC30-CDE")
        assert "BTCUSD" in candidates

    def test_etp_maps_to_ethusd(self):
        candidates = asset_key_candidates("ETP-20DEC30-CDE")
        assert "ETHUSD" in candidates

    def test_btcusd_canonical(self):
        candidates = asset_key_candidates("BTCUSD")
        assert "BTCUSD" in candidates

    def test_btc_usd_with_dash(self):
        candidates = asset_key_candidates("BTC-USD")
        assert "BTCUSD" in candidates

    def test_empty_string_returns_empty(self):
        assert asset_key_candidates("") == []

    def test_none_returns_empty(self):
        assert asset_key_candidates(None) == []

    def test_unknown_product_returns_fallback(self):
        candidates = asset_key_candidates("UNKNOWN-PRODUCT")
        assert len(candidates) > 0  # At least the raw fallback


# ═══════════════════════════════════════════════════════════════════
# SEAM 6: merge_nested_payload
# ═══════════════════════════════════════════════════════════════════

class TestMergeNestedPayload:
    """Coinbase wraps responses in {"order": {...}}. Must flatten correctly."""

    def test_flattens_nested_order(self):
        payload = {"order": {"id": "123", "status": "filled"}, "meta": "top"}
        result = merge_nested_payload(payload)
        assert result["id"] == "123"
        assert result["status"] == "filled"
        assert result["meta"] == "top"

    def test_no_nested_key_returns_as_is(self):
        payload = {"id": "123", "status": "filled"}
        result = merge_nested_payload(payload)
        assert result == payload

    def test_non_dict_returns_as_is(self):
        assert merge_nested_payload("not a dict") == "not a dict"
        assert merge_nested_payload(None) is None

    def test_nested_overwrites_top_level(self):
        payload = {"order": {"id": "nested"}, "id": "top"}
        result = merge_nested_payload(payload)
        assert result["id"] == "nested", "Nested should override top-level"


# ═══════════════════════════════════════════════════════════════════
# SEAM 7: extract_portfolio_positions
# ═══════════════════════════════════════════════════════════════════

class TestExtractPortfolioPositions:
    """Must handle flat and nested platform_breakdowns shapes."""

    def test_flat_positions(self):
        portfolio = {"futures_positions": [{"id": "1"}], "holdings": [{"id": "2"}]}
        futures, holdings = extract_portfolio_positions(portfolio)
        assert len(futures) == 1
        assert len(holdings) == 1

    def test_nested_platform_breakdowns(self):
        portfolio = {
            "futures_positions": [],
            "holdings": [],
            "platform_breakdowns": {
                "coinbase": {
                    "futures_positions": [{"id": "1"}],
                    "holdings": [{"id": "2"}],
                }
            },
        }
        futures, holdings = extract_portfolio_positions(portfolio)
        assert len(futures) == 1
        assert len(holdings) == 1

    def test_empty_portfolio(self):
        futures, holdings = extract_portfolio_positions({})
        assert futures == []
        assert holdings == []

    def test_none_portfolio(self):
        futures, holdings = extract_portfolio_positions(None)
        assert futures == []
        assert holdings == []

    def test_positions_key_also_extracted(self):
        """Some platform breakdowns use 'positions' instead of 'futures_positions'."""
        portfolio = {
            "platform_breakdowns": {
                "coinbase": {
                    "positions": [{"id": "p1"}],
                }
            },
        }
        futures, holdings = extract_portfolio_positions(portfolio)
        assert len(futures) == 1


# ═══════════════════════════════════════════════════════════════════
# SEAM 8: DecisionReservationPayload
# ═══════════════════════════════════════════════════════════════════

class TestDecisionReservationPayload:
    """Reservation payload must extract fields safely from decisions."""

    def test_from_normal_decision(self):
        decision = {
            "id": "d-123",
            "asset_pair": "BTCUSD",
            "action": "BUY",
            "recommended_position_size": 0.001,
            "entry_price": 68000,
        }
        payload = DecisionReservationPayload.from_decision(decision)
        assert payload.decision_id == "d-123"
        assert payload.asset_pair == "BTCUSD"
        assert payload.action == "BUY"
        assert payload.position_size == 0.001
        assert payload.notional_value == pytest.approx(68.0, abs=0.1)

    def test_from_empty_decision(self):
        payload = DecisionReservationPayload.from_decision({})
        assert payload.decision_id == ""
        assert payload.asset_pair == ""
        assert payload.action == "UNKNOWN"
        assert payload.position_size == 0.0
        assert payload.notional_value == 0.0

    def test_reserve_rejects_empty_id(self):
        """Cannot reserve exposure without a decision ID."""
        mock_mgr = MagicMock()
        with pytest.raises(ValueError, match="non-empty id"):
            reserve_trade_exposure(mock_mgr, {})

    def test_finalize_commits_on_success(self):
        mock_mgr = MagicMock()
        finalize_trade_reservation(mock_mgr, "d-123", execution_succeeded=True)
        mock_mgr.commit_reservation.assert_called_once_with("d-123")

    def test_finalize_rolls_back_on_failure(self):
        mock_mgr = MagicMock()
        finalize_trade_reservation(mock_mgr, "d-123", execution_succeeded=False)
        mock_mgr.rollback_reservation.assert_called_once_with("d-123")


# ═══════════════════════════════════════════════════════════════════
# SEAM 9: position_product_id lookup
# ═══════════════════════════════════════════════════════════════════

class TestPositionProductId:
    """Must find product ID from any known key shape."""

    def test_product_id_key(self):
        assert position_product_id({"product_id": "BIP-20DEC30-CDE"}) == "BIP-20DEC30-CDE"

    def test_instrument_key(self):
        assert position_product_id({"instrument": "EUR_USD"}) == "EUR_USD"

    def test_asset_pair_key(self):
        assert position_product_id({"asset_pair": "BTCUSD"}) == "BTCUSD"

    def test_symbol_key(self):
        assert position_product_id({"symbol": "AAPL"}) == "AAPL"

    def test_no_known_key(self):
        assert position_product_id({"foo": "bar"}) is None

    def test_non_dict(self):
        assert position_product_id("not a dict") is None

    def test_none(self):
        assert position_product_id(None) is None



def test_derisking_reservation_payload_prefers_execution_notional_when_present():
    decision = {
        "id": "reduce-1",
        "asset_pair": "BTCUSD",
        "action": "REDUCE_LONG",
        "policy_action": "REDUCE_LONG",
        "recommended_position_size": 1.0,
        "entry_price": 76000.0,
        "notional_value": 76000.0,
        "suggested_amount": 1.0,
        "execution_metadata": {
            "execution_amount_usd": 1.0,
        },
    }

    payload = DecisionReservationPayload.from_decision(decision)

    assert payload.position_size == 1.0
    assert payload.notional_value == 1.0

