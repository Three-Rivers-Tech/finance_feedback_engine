from finance_feedback_engine.utils.config_loader import _normalize_runtime_config


def test_normalize_runtime_config_filters_platforms_to_coinbase_when_env_asset_pairs_are_crypto_only(monkeypatch):
    monkeypatch.setenv('TRADING_PLATFORM', 'unified')
    monkeypatch.setenv('AGENT_ASSET_PAIRS', 'BTCUSD,ETHUSD')

    cfg = {
        'trading_platform': 'unified',
        'platforms': [
            {'name': 'coinbase_advanced', 'credentials': {'api_key': 'x', 'api_secret': 'y'}},
            {'name': 'oanda', 'credentials': {'api_key': 'YOUR_OANDA_API_KEY', 'account_id': 'YOUR_OANDA_ACCOUNT_ID'}},
        ],
        'agent': {'asset_pairs': ['BTCUSD', 'ETHUSD']},
    }

    out = _normalize_runtime_config(cfg)
    names = [p['name'] for p in out['platforms']]
    assert names == ['coinbase_advanced']
    assert out['enabled_platforms'] == ['coinbase_advanced']
