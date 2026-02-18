from finance_feedback_engine.config.provider_credentials import resolve_provider_credentials


def test_resolve_provider_credentials_prefers_nested_and_fallback_platforms() -> None:
    config = {
        "providers": {
            "coinbase": {"credentials": {"api_key": "key-1"}},
        },
        "platforms": [
            {"name": "oanda", "credentials": {"account_id": "abc"}},
        ],
    }

    creds = resolve_provider_credentials(config)

    assert creds.coinbase == {"api_key": "key-1"}
    assert creds.oanda == {"account_id": "abc"}


def test_resolve_provider_credentials_handles_missing_and_invalid_values() -> None:
    config = {
        "coinbase": "not-a-dict",
        "platforms": [
            {"name": "coinbase_advanced", "credentials": {"api_key": "fallback"}},
            {"name": "oanda", "credentials": "oops"},
        ],
    }

    creds = resolve_provider_credentials(config)

    assert creds.coinbase == {"api_key": "fallback"}
    assert creds.oanda is None
