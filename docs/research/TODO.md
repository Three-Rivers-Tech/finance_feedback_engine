# TODO List — Finance Feedback Engine 2.0

Track pending tasks, feature requests, and testing verification items.

## Platform & Integration

- [ ] **Verify UnifiedPlatform routes EURUSD to Oanda correctly in live testing**
  - Added EURUSD to agent watchlist (`config/agent.yaml`)
  - Need to verify routing logic in `finance_feedback_engine/trading_platforms/unified_platform.py` (lines 86-98)
  - Ensure Oanda credentials are configured in `config/config.local.yaml`
  - Test with `python main.py run-agent` to confirm 3-asset iteration works

## Agent & OODA Loop

- [ ] **Add CLI override for asset pairs in run-agent command**
  - Allow `--asset-pairs BTCUSD,ETHUSD,EURUSD` argument
  - Useful for runtime flexibility without config changes
  - Location: `finance_feedback_engine/cli/main.py` in `run_agent()` function

## Future Enhancements

_Add new tasks below as they arise_

---

**Last Updated:** December 5, 2025
