from finance_feedback_engine.monitoring.context_provider import (
    MonitoringContextProvider,
    _estimate_position_notional_usd,
)


class _DummyPlatform:
    pass


def test_estimate_position_notional_uses_contract_size_for_futures():
    pos = {
        "product_id": "ETP-20DEC30-CDE",
        "contracts": 1,
        "current_price": 2142.5,
        "contract_size": 0.1,
    }

    notional = _estimate_position_notional_usd(pos)

    assert notional == 214.25


def test_analyze_concentration_tracks_asset_specific_percentages():
    provider = MonitoringContextProvider(_DummyPlatform())
    portfolio = {
        "total_value_usd": 807.19,
        "futures_positions": [
            {
                "product_id": "ETP-20DEC30-CDE",
                "side": "SHORT",
                "contracts": 1,
                "current_price": 2142.5,
                "contract_size": 0.1,
            }
        ],
    }

    concentration = provider._analyze_concentration(portfolio)

    assert concentration["largest_position_pct"] < 30.0
    assert concentration["asset_position_pct"]["ETHUSD"] == concentration["largest_position_pct"]
