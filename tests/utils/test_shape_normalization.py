from finance_feedback_engine.utils.shape_normalization import (
    asset_key_candidates,
    extract_portfolio_positions,
    merge_nested_payload,
    normalize_scalar_id,
)


def test_normalize_scalar_id_unwraps_tuple():
    assert normalize_scalar_id(("decision-123", 1.0)) == "decision-123"
    assert normalize_scalar_id("decision-456") == "decision-456"


def test_normalize_scalar_id_handles_wrapper_dict_shapes():
    assert normalize_scalar_id({"id": "decision-789"}) == "decision-789"
    assert normalize_scalar_id({"decision_id": "decision-790"}) == "decision-790"
    assert normalize_scalar_id({"decision": {"id": "decision-791"}}) == "decision-791"


def test_merge_nested_payload_flattens_order_key():
    payload = {"foo": 1, "order": {"status": "FILLED", "filled_size": "1"}}
    normalized = merge_nested_payload(payload)
    assert normalized["foo"] == 1
    assert normalized["status"] == "FILLED"
    assert normalized["filled_size"] == "1"


def test_extract_portfolio_positions_reads_nested_breakdowns():
    portfolio = {
        "platform_breakdowns": {
            "coinbase": {
                "futures_positions": [{"product_id": "BIP-20DEC30-CDE"}],
                "holdings": [{"asset": "USD", "quantity": "5"}],
            }
        }
    }
    futures_positions, holdings = extract_portfolio_positions(portfolio)
    assert futures_positions[0]["product_id"] == "BIP-20DEC30-CDE"
    assert holdings[0]["asset"] == "USD"


def test_asset_key_candidates_adds_cfm_aliases():
    candidates = asset_key_candidates("ETP-20DEC30-CDE")
    assert "ETHUSD" in candidates
    candidates = asset_key_candidates("BIP-20DEC30-CDE")
    assert "BTCUSD" in candidates
