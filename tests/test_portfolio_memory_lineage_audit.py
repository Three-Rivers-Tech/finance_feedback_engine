"""Tests for PortfolioMemoryEngine.audit_lineage (#42 quantification)."""

import logging

import pytest

from finance_feedback_engine.memory.portfolio_memory import PortfolioMemoryEngine


@pytest.fixture
def mock_config(tmp_path):
    return {
        "portfolio_memory": {
            "enabled": True,
            "max_memory_size": 100,
            "learning_rate": 0.1,
            "context_window": 20,
        },
        "persistence": {"storage_path": str(tmp_path)},
    }


@pytest.fixture
def memory_engine(mock_config):
    return PortfolioMemoryEngine(mock_config)


def _full_decision(decision_id="dec-1", asset_pair="BTCUSD", provider="local"):
    return {
        "id": decision_id,
        "asset_pair": asset_pair,
        "action": "BUY",
        "entry_price": 100.0,
        "position_size": 1.0,
        "confidence": 70,
        "ai_provider": provider,
        "timestamp": "2024-12-04T10:00:00Z",
    }


def _orphan_decision():
    # No id, asset_pair, or ai_provider — recorder fills sentinels.
    return {
        "action": "BUY",
        "entry_price": 100.0,
        "position_size": 1.0,
        "confidence": 50,
        "timestamp": "2024-12-04T10:00:00Z",
    }


class TestAuditLineageEmpty:
    def test_empty_memory_returns_zero_totals(self, memory_engine):
        report = memory_engine.audit_lineage()

        assert report["total_outcomes"] == 0
        assert report["outcomes_with_null_lineage"] == 0
        assert report["outcomes_with_full_lineage"] == 0
        assert report["null_lineage_pct"] == 0.0
        assert report["sample_orphans"] == []
        assert report["field_null_counts"] == {
            "decision_id": 0,
            "asset_pair": 0,
            "ai_provider": 0,
        }


class TestAuditLineageCounts:
    def test_full_lineage_outcomes_have_no_nulls(self, memory_engine):
        memory_engine.record_trade_outcome(
            _full_decision("dec-a"), exit_price=110.0
        )
        memory_engine.record_trade_outcome(
            _full_decision("dec-b"), exit_price=120.0
        )

        report = memory_engine.audit_lineage()

        assert report["total_outcomes"] == 2
        assert report["outcomes_with_null_lineage"] == 0
        assert report["outcomes_with_full_lineage"] == 2
        assert report["null_lineage_pct"] == 0.0
        assert report["field_null_counts"]["decision_id"] == 0
        assert report["field_null_counts"]["asset_pair"] == 0
        assert report["field_null_counts"]["ai_provider"] == 0

    def test_orphan_decisions_count_as_null_lineage(self, memory_engine):
        memory_engine.record_trade_outcome(_orphan_decision(), exit_price=105.0)

        report = memory_engine.audit_lineage()

        assert report["total_outcomes"] == 1
        assert report["outcomes_with_null_lineage"] == 1
        assert report["null_lineage_pct"] == 100.0
        assert report["field_null_counts"]["decision_id"] == 1
        assert report["field_null_counts"]["asset_pair"] == 1
        assert report["field_null_counts"]["ai_provider"] == 1

    def test_partial_orphan_only_flags_missing_fields(self, memory_engine):
        # Decision with id and asset_pair but no ai_provider → only ai_provider null.
        decision = _full_decision("dec-c")
        decision.pop("ai_provider")
        memory_engine.record_trade_outcome(decision, exit_price=110.0)

        report = memory_engine.audit_lineage()

        assert report["total_outcomes"] == 1
        assert report["outcomes_with_null_lineage"] == 1
        assert report["field_null_counts"]["decision_id"] == 0
        assert report["field_null_counts"]["asset_pair"] == 0
        assert report["field_null_counts"]["ai_provider"] == 1

    def test_mixed_population_reports_correct_pct(self, memory_engine):
        memory_engine.record_trade_outcome(_full_decision("dec-1"), exit_price=110.0)
        memory_engine.record_trade_outcome(_full_decision("dec-2"), exit_price=120.0)
        memory_engine.record_trade_outcome(_full_decision("dec-3"), exit_price=130.0)
        memory_engine.record_trade_outcome(_orphan_decision(), exit_price=105.0)

        report = memory_engine.audit_lineage()

        assert report["total_outcomes"] == 4
        assert report["outcomes_with_null_lineage"] == 1
        assert report["outcomes_with_full_lineage"] == 3
        assert report["null_lineage_pct"] == 25.0

    def test_null_lineage_patterns_group_missing_field_combinations(
        self, memory_engine
    ):
        full = _full_decision("dec-full")
        memory_engine.record_trade_outcome(full, exit_price=110.0)

        missing_provider = _full_decision("dec-provider")
        missing_provider.pop("ai_provider")
        memory_engine.record_trade_outcome(missing_provider, exit_price=111.0)

        memory_engine.record_trade_outcome(_orphan_decision(), exit_price=105.0)
        memory_engine.record_trade_outcome(_orphan_decision(), exit_price=106.0)

        report = memory_engine.audit_lineage()

        assert report["null_lineage_patterns"] == [
            {
                "null_fields": ["decision_id", "asset_pair", "ai_provider"],
                "count": 2,
                "pct": 50.0,
            },
            {
                "null_fields": ["ai_provider"],
                "count": 1,
                "pct": 25.0,
            },
        ]


class TestAuditLineageFiltering:
    def test_asset_pair_filter_restricts_population(self, memory_engine):
        memory_engine.record_trade_outcome(
            _full_decision("dec-btc", asset_pair="BTCUSD"), exit_price=110.0
        )
        memory_engine.record_trade_outcome(
            _full_decision("dec-eth", asset_pair="ETHUSD"), exit_price=210.0
        )
        memory_engine.record_trade_outcome(_orphan_decision(), exit_price=105.0)

        report = memory_engine.audit_lineage(asset_pair="BTCUSD")

        assert report["asset_pair_filter"] == "BTCUSD"
        assert report["total_outcomes"] == 1
        assert report["outcomes_with_null_lineage"] == 0


class TestAuditLineageSamples:
    def test_sample_orphans_respects_limit(self, memory_engine):
        for _ in range(7):
            memory_engine.record_trade_outcome(_orphan_decision(), exit_price=105.0)

        report = memory_engine.audit_lineage(sample_limit=3)

        assert report["outcomes_with_null_lineage"] == 7
        assert len(report["sample_orphans"]) == 3
        for sample in report["sample_orphans"]:
            assert sample["decision_id"] == "unknown"

    def test_sample_orphans_excludes_full_lineage_rows(self, memory_engine):
        memory_engine.record_trade_outcome(_full_decision("dec-good"), exit_price=110.0)
        memory_engine.record_trade_outcome(_orphan_decision(), exit_price=105.0)

        report = memory_engine.audit_lineage()

        assert len(report["sample_orphans"]) == 1
        assert report["sample_orphans"][0]["decision_id"] == "unknown"
        assert report["sample_orphans"][0]["null_fields"] == [
            "decision_id",
            "asset_pair",
            "ai_provider",
        ]

    def test_negative_sample_limit_returns_no_samples(self, memory_engine):
        memory_engine.record_trade_outcome(_orphan_decision(), exit_price=105.0)

        report = memory_engine.audit_lineage(sample_limit=-1)

        assert report["outcomes_with_null_lineage"] == 1
        assert report["sample_orphans"] == []


class TestRecordTradeOutcomeLogging:
    def test_logs_when_recording_null_lineage_outcome(self, memory_engine, caplog):
        with caplog.at_level(logging.WARNING):
            memory_engine.record_trade_outcome(_orphan_decision(), exit_price=105.0)

        assert "Recording trade outcome with null lineage fields" in caplog.text
        assert "decision_id, asset_pair, ai_provider" in caplog.text


class TestNullLineageHelper:
    @pytest.mark.parametrize(
        "field,value,expected",
        [
            ("decision_id", "unknown", True),
            ("decision_id", "UNKNOWN", True),
            ("decision_id", "", True),
            ("decision_id", None, True),
            ("decision_id", "dec-1", False),
            ("asset_pair", "UNKNOWN", True),
            ("asset_pair", "BTCUSD", False),
            ("ai_provider", "unknown", True),
            ("ai_provider", "ensemble", False),
        ],
    )
    def test_is_null_lineage(self, field, value, expected):
        assert PortfolioMemoryEngine._is_null_lineage(field, value) is expected
