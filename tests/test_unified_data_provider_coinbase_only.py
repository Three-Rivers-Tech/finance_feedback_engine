from finance_feedback_engine.data_providers.unified_data_provider import UnifiedDataProvider


def test_unified_data_provider_respects_coinbase_only_enabled_platforms():
    provider = UnifiedDataProvider(
        alpha_vantage_api_key='test',
        coinbase_credentials={'api_key': 'real', 'api_secret': 'real'},
        oanda_credentials={'api_key': 'YOUR_OANDA_API_KEY', 'account_id': 'YOUR_OANDA_ACCOUNT_ID'},
        config={'trading_platform': 'unified', 'enabled_platforms': ['coinbase_advanced']},
    )
    assert provider.coinbase is not None
    assert provider.oanda is None


def test_unified_data_provider_keeps_coinbase_market_data_in_paper_only_mode():
    provider = UnifiedDataProvider(
        alpha_vantage_api_key='test',
        coinbase_credentials={'api_key': 'real', 'api_secret': 'real'},
        config={'trading_platform': 'unified', 'enabled_platforms': ['paper']},
    )
    assert provider.coinbase is not None


def test_unified_data_provider_allows_public_coinbase_data_without_credentials():
    provider = UnifiedDataProvider(
        alpha_vantage_api_key='test',
        coinbase_credentials=None,
        config={'trading_platform': 'unified'},
    )
    assert provider.coinbase is not None
