# TODO List — Finance Feedback Engine 2.0

Track pending tasks, feature requests, and testing verification items.

## Completed ✅

- [x] **Verify UnifiedPlatform routes EURUSD to Oanda correctly** (Completed: 2025-12-12)
  - Created comprehensive test suite in `tests/trading_platforms/test_unified_platform_routing.py`
  - Verified routing for EURUSD, GBPUSD, USDJPY → Oanda
  - Verified routing for BTCUSD, ETHUSD → Coinbase
  - All 8 routing tests pass successfully

- [x] **Add CLI override for asset pairs in run-agent command** (Completed: 2025-12-12)
  - Implemented `--asset-pairs` argument for `run-agent` command
  - Supports comma-separated list (e.g., `--asset-pairs "BTCUSD,ETHUSD,EURUSD"`)
  - Automatically standardizes various formats (btc-usd, BTC_USD, BTCUSD)
  - Overrides both `asset_pairs` and `watchlist` in agent config
  - Created test suite in `tests/test_cli_asset_pairs_override.py`
  - All 6 tests pass successfully

## Platform & Integration

_(No pending items)_

## Agent & OODA Loop

_(No pending items)_

## Future Enhancements

_Add new tasks below as they arise_

---

**Last Updated:** December 5, 2025
