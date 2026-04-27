from finance_feedback_engine.config.provider_credentials import resolve_provider_credentials, resolve_runtime_contract


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


def test_resolve_provider_credentials_includes_paper_platform_credentials() -> None:
    config = {
        "platforms": [
            {"name": "paper", "credentials": {"initial_cash_usd": 250000}},
        ],
    }

    creds = resolve_provider_credentials(config)

    assert creds.paper == {"initial_cash_usd": 250000}


def test_resolve_runtime_contract_marks_paper_only_enabled_platforms_as_paper_execution() -> None:
    runtime = resolve_runtime_contract({
        "enabled_platforms": ["paper"],
        "agent": {"asset_pairs": ["BTCUSD"]},
    })

    assert runtime.paper_execution_enabled is True
    assert runtime.paper_only_runtime is True
    assert runtime.crypto_only_runtime is True
    assert runtime.enabled_platforms == frozenset({"paper"})


def test_resolve_runtime_contract_uses_config_flags_for_mixed_runtime() -> None:
    runtime = resolve_runtime_contract({
        "enabled_platforms": ["paper", "coinbase_advanced"],
        "paper_trading_defaults": {"enabled": True},
        "agent": {"asset_pairs": ["BTCUSD"]},
    })

    assert runtime.paper_execution_enabled is True
    assert runtime.paper_only_runtime is False
    assert runtime.crypto_only_runtime is True
