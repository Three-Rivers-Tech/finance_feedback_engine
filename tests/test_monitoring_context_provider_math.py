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



def test_extract_active_positions_reads_nested_platform_breakdowns():
    provider = MonitoringContextProvider(_DummyPlatform())
    portfolio = {
        "platform_breakdowns": {
            "coinbase": {
                "futures_positions": [
                    {
                        "product_id": "BIP-20DEC30-CDE",
                        "side": "SHORT",
                        "contracts": 1,
                    }
                ]
            }
        }
    }

    futures_positions, holdings = provider._extract_active_positions_from_portfolio(portfolio)

    assert len(futures_positions) == 1
    assert futures_positions[0]["product_id"] == "BIP-20DEC30-CDE"


def test_asset_scoped_filter_matches_cfm_btc_product_to_btcusd():
    provider = MonitoringContextProvider(_DummyPlatform())
    portfolio = {
        "platform_breakdowns": {
            "coinbase": {
                "futures_positions": [
                    {
                        "product_id": "BIP-20DEC30-CDE",
                        "side": "SHORT",
                        "contracts": 1,
                    }
                ]
            }
        }
    }

    provider.platform.get_portfolio_breakdown = lambda: portfolio
    context = provider.get_monitoring_context(asset_pair="BTCUSD")

    assert len(context["active_positions"]["futures"]) == 1
    assert context["active_positions"]["futures"][0]["product_id"] == "BIP-20DEC30-CDE"


def test_monitoring_context_includes_portfolio_breakdown_for_risk_gate_boundary():
    provider = MonitoringContextProvider(_DummyPlatform())
    portfolio = {
        "total_value_usd": 267.10,
        "platform_breakdowns": {
            "coinbase": {
                "futures_summary": {
                    "initial_margin": 76.34,
                    "total_balance_usd": 267.10,
                },
                "futures_positions": [
                    {
                        "product_id": "BIP-20DEC30-CDE",
                        "side": "LONG",
                        "contracts": 1,
                        "current_price": 76845.0,
                    }
                ],
            }
        },
    }

    provider.platform.get_portfolio_breakdown = lambda: portfolio
    context = provider.get_monitoring_context(asset_pair="BTCUSD")

    assert context["portfolio_breakdown"]["platform_breakdowns"]["coinbase"]["futures_summary"]["initial_margin"] == 76.34
    assert context["portfolio_breakdown"]["platform_breakdowns"]["coinbase"]["futures_summary"]["total_balance_usd"] == 267.10

