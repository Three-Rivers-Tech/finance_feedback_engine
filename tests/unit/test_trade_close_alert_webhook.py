"""Unit tests for trade-close n8n alert integration in TradeOutcomeRecorder."""

from unittest.mock import Mock

from finance_feedback_engine.monitoring.trade_outcome_recorder import TradeOutcomeRecorder


def _sample_outcome():
    return {
        "trade_id": "trade-123",
        "decision_id": "decision-abc",
        "product": "BTCUSD",
        "side": "LONG",
        "entry_time": "2026-02-18T15:00:00+00:00",
        "entry_price": "100.0",
        "entry_size": "1.0",
        "exit_time": "2026-02-18T16:00:00+00:00",
        "exit_price": "101.0",
        "exit_size": "1.0",
        "realized_pnl": "1.0",
        "fees": "0",
        "holding_duration_seconds": 3600,
        "roi_percent": "1.0",
        "exit_price_source": "provider:coinbase",
    }


def test_build_trade_close_alert_payload_contains_cfo_fields(tmp_path, monkeypatch):
    monkeypatch.setenv("N8N_TRADE_CLOSE_WEBHOOK_URL", "http://localhost:5678/webhook/test")
    recorder = TradeOutcomeRecorder(data_dir=str(tmp_path), use_async=False)

    payload = recorder._build_trade_close_alert_payload(_sample_outcome())

    assert payload["event_type"] == "ffe.trade.closed"
    assert payload["cfo_accounting"]["trade_id"] == "trade-123"
    assert payload["cfo_accounting"]["asset_pair"] == "BTCUSD"
    assert payload["cfo_accounting"]["realized_pnl"] == "1.0"
    assert payload["cfo_accounting"]["realized_pnl_float"] == 1.0


def test_emit_trade_close_alert_async_enqueues_delivery(tmp_path):
    recorder = TradeOutcomeRecorder(
        data_dir=str(tmp_path),
        use_async=False,
        trade_close_alert_webhook_url="http://localhost:5678/webhook/test",
    )

    recorder._executor = Mock()
    recorder._executor.submit = Mock()

    recorder._emit_trade_close_alert_async(_sample_outcome())

    recorder._executor.submit.assert_called_once()
    submit_args = recorder._executor.submit.call_args[0]
    assert submit_args[0] == recorder._post_trade_close_alert
    assert submit_args[1]["event_type"] == "ffe.trade.closed"


def test_emit_trade_close_alert_async_noop_when_webhook_disabled(tmp_path):
    recorder = TradeOutcomeRecorder(data_dir=str(tmp_path), use_async=False)
    recorder._executor = Mock()
    recorder._executor.submit = Mock()

    recorder._emit_trade_close_alert_async(_sample_outcome())

    recorder._executor.submit.assert_not_called()
