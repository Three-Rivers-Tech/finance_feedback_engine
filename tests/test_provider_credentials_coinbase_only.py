from finance_feedback_engine.config.provider_credentials import resolve_provider_credentials


def test_resolve_provider_credentials_omits_oanda_in_coinbase_only_crypto_runtime():
    cfg = {
        'enabled_platforms': ['coinbase_advanced'],
        'agent': {'asset_pairs': ['BTCUSD', 'ETHUSD']},
        'providers': {
            'coinbase': {'credentials': {'api_key': 'x', 'api_secret': 'y'}},
            'oanda': {'credentials': {'api_key': 'YOUR_OANDA_API_KEY', 'account_id': 'YOUR_OANDA_ACCOUNT_ID'}},
        },
        'platforms': [
            {'name': 'coinbase_advanced', 'credentials': {'api_key': 'x', 'api_secret': 'y'}},
            {'name': 'oanda', 'credentials': {'api_key': 'YOUR_OANDA_API_KEY', 'account_id': 'YOUR_OANDA_ACCOUNT_ID'}},
        ],
    }

    creds = resolve_provider_credentials(cfg)
    assert creds.coinbase is not None
    assert creds.oanda is None
