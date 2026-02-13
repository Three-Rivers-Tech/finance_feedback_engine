# Code Review Request: THR-207 Position Sizing Fix

## Context
**Bug:** Position sizing calculation returned 0/null, blocking all live trading
**Root Cause:** UnifiedPlatform missing `aget_portfolio_breakdown()` async method
**Fix:** Added async method + preserved futures/spot value aggregation

## Files Changed
1. `finance_feedback_engine/trading_platforms/unified_platform.py` - Added async method
2. `finance_feedback_engine/risk/gatekeeper.py` - Reverted temporary test override

## Review Criteria
- Async/await correctness
- Data integrity (futures/spot values preserved)
- Consistency between sync/async implementations
- Error handling
- Potential race conditions or edge cases

## Code Diff

### unified_platform.py - Added aget_portfolio_breakdown()

```python
async def aget_portfolio_breakdown(self) -> Dict[str, Any]:
    """
    Async version of get_portfolio_breakdown.
    
    Get a combined portfolio breakdown from all platforms.
    Merges portfolio data from Coinbase (futures) and Oanda (forex).
    """
    total_value_usd = 0
    total_unrealized = 0.0
    all_holdings = []
    num_assets = 0
    cash_balances = {}
    futures_value_usd = 0
    spot_value_usd = 0

    platform_breakdowns = {}

    for name, platform in self.platforms.items():
        try:
            # Use async version if available, otherwise fall back to sync
            if hasattr(platform, 'aget_portfolio_breakdown'):
                breakdown = await platform.aget_portfolio_breakdown()
            else:
                breakdown = platform.get_portfolio_breakdown()
                
            platform_breakdowns[name] = breakdown

            total_value_usd += breakdown.get("total_value_usd", 0)
            # Capture unrealized P&L if the platform exposes it
            total_unrealized += breakdown.get("unrealized_pnl", 0.0)
            
            # Aggregate futures and spot values for position sizing
            futures_value_usd += breakdown.get("futures_value_usd", 0)
            spot_value_usd += breakdown.get("spot_value_usd", 0)

            # Capture cash/balance if provided by the platform
            bal = breakdown.get("balance") or breakdown.get("total_balance_usd")
            if bal is not None:
                try:
                    cash_balances[name] = float(bal)
                except Exception:
                    cash_balances[name] = 0.0

            # Add platform prefix to holdings
            holdings = breakdown.get("holdings", [])
            for holding in holdings:
                holding["platform"] = name
            all_holdings.extend(holdings)

            num_assets += breakdown.get("num_assets", 0)

        except (ValueError, TypeError, KeyError) as e:
            logger.error("Failed to get portfolio breakdown from %s: %s", name, e)

    # Recalculate allocation percentages across the entire portfolio.
    # Use total notional exposure (sum of all holdings' values) rather
    # than account balance, so allocations make sense for leveraged positions.
    total_notional_exposure = sum(
        holding.get("value_usd", 0) for holding in all_holdings
    )

    if total_notional_exposure > 0:
        for holding in all_holdings:
            allocation = (
                holding.get("value_usd", 0) / total_notional_exposure
            ) * 100
            holding["allocation_pct"] = allocation

    # Sum cash balances across platforms
    cash_balance_usd = sum(cash_balances.values()) if cash_balances else 0.0

    return {
        "total_value_usd": total_value_usd,
        "futures_value_usd": futures_value_usd,
        "spot_value_usd": spot_value_usd,
        "cash_balance_usd": cash_balance_usd,
        "per_platform_cash": cash_balances,
        "num_assets": num_assets,
        "holdings": all_holdings,
        "platform_breakdowns": platform_breakdowns,
        "unrealized_pnl": total_unrealized,
    }
```

### unified_platform.py - Updated get_portfolio_breakdown() sync version

Also added futures/spot aggregation to maintain parity:

```python
# Added these lines to sync version:
futures_value_usd = 0
spot_value_usd = 0

# Inside platform loop:
futures_value_usd += breakdown.get("futures_value_usd", 0)
spot_value_usd += breakdown.get("spot_value_usd", 0)

# In return dict:
"futures_value_usd": futures_value_usd,
"spot_value_usd": spot_value_usd,
```

## Questions for Gemini

1. **Async correctness:** Is the fallback pattern (async → sync) safe?
2. **Data consistency:** Both methods return identical schemas?
3. **Error handling:** Are exceptions handled properly?
4. **Edge cases:** What happens if all platforms fail? Empty dict issues?
5. **Performance:** Any concerns with blocking sync calls in async context?
6. **Overall code quality:** Rate 1-10 and suggest improvements

Please provide a detailed review with specific recommendations.
