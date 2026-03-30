from finance_feedback_engine.persistence.decision_store import DecisionStore


def test_find_equivalent_recovery_decision_matches_existing(tmp_path):
    store = DecisionStore({"storage_path": str(tmp_path)})
    decision = {
        "id": "dec-1",
        "asset_pair": "EURUSD",
        "timestamp": "2026-03-10T16:19:30.565027Z",
        "action": "BUY",
        "confidence": 75,
        "recommended_position_size": 1.0,
        "entry_price": 1.15595,
        "ai_provider": "recovery",
        "recovery_metadata": {
            "platform": "oanda",
            "product_id": "EUR_USD",
            "opened_at": None,
        },
    }
    store.save_decision(decision)

    match = store.find_equivalent_recovery_decision(
        asset_pair="EURUSD",
        action="BUY",
        entry_price=1.15595,
        position_size=1.0,
        platform="oanda",
        product_id="EUR_USD",
    )

    assert match is not None
    assert match["id"] == "dec-1"


def test_find_equivalent_recovery_decision_ignores_non_recovery(tmp_path):
    store = DecisionStore({"storage_path": str(tmp_path)})
    store.save_decision(
        {
            "id": "dec-2",
            "asset_pair": "EURUSD",
            "timestamp": "2026-03-10T16:19:30.565027Z",
            "action": "BUY",
            "confidence": 75,
            "recommended_position_size": 1.0,
            "entry_price": 1.15595,
            "ai_provider": "gemini",
        }
    )

    match = store.find_equivalent_recovery_decision(
        asset_pair="EURUSD",
        action="BUY",
        entry_price=1.15595,
        position_size=1.0,
        platform="oanda",
        product_id="EUR_USD",
    )

    assert match is None


def test_find_recent_decision_for_position_matches_non_recovery_attribution_source(tmp_path):
    store = DecisionStore({"storage_path": str(tmp_path)})
    store.save_decision(
        {
            "id": "dec-3",
            "asset_pair": "BTCUSD",
            "timestamp": "2026-03-10T16:19:30.565027Z",
            "action": "OPEN_SMALL_SHORT",
            "confidence": 82,
            "recommended_position_size": 1.0,
            "entry_price": 67580.0,
            "ai_provider": "ensemble",
            "ensemble_metadata": {
                "voting_strategy": "debate",
                "providers_used": ["gemma2:9b", "llama3.1:8b", "deepseek-r1:8b"],
            },
        }
    )

    match = store.find_recent_decision_for_position(
        asset_pair="BTCUSD",
        action="OPEN_SMALL_SHORT",
        entry_price=67580.0,
        position_size=1.0,
    )

    assert match is not None
    assert match["id"] == "dec-3"
    assert match["ai_provider"] == "ensemble"


def test_find_recent_decision_for_position_bridges_btcusd_to_bip_contract_shape(tmp_path):
    store = DecisionStore({"storage_path": str(tmp_path)})
    store.save_decision(
        {
            "id": "dec-btc-contract-source",
            "asset_pair": "BTCUSD",
            "timestamp": "2026-03-30T15:16:25Z",
            "action": "OPEN_SMALL_SHORT",
            "confidence": 82,
            "recommended_position_size": 0.004389412997903564,
            "entry_price": 67450.0,
            "ai_provider": "ensemble",
            "ensemble_metadata": {"voting_strategy": "debate"},
        }
    )

    match = store.find_recent_decision_for_position(
        asset_pair="BIP20DEC30CDE",
        action="SELL",
        entry_price=67450.0,
        position_size=1.0,
    )

    assert match is not None
    assert match["id"] == "dec-btc-contract-source"
    assert match["ai_provider"] == "ensemble"


def test_find_recent_decision_for_position_bridges_ethusd_to_etp_contract_shape(tmp_path):
    store = DecisionStore({"storage_path": str(tmp_path)})
    store.save_decision(
        {
            "id": "dec-eth-contract-source",
            "asset_pair": "ETHUSD",
            "timestamp": "2026-03-30T15:16:29Z",
            "action": "OPEN_SMALL_SHORT",
            "confidence": 79,
            "recommended_position_size": 0.14344260314422552,
            "entry_price": 2065.0,
            "ai_provider": "ensemble",
            "ensemble_metadata": {"voting_strategy": "debate"},
        }
    )

    match = store.find_recent_decision_for_position(
        asset_pair="ETP20DEC30CDE",
        action="SELL",
        entry_price=2065.0,
        position_size=1.0,
    )

    assert match is not None
    assert match["id"] == "dec-eth-contract-source"
    assert match["ai_provider"] == "ensemble"
