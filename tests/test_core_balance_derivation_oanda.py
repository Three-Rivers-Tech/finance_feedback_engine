
def derive_balance_like_core(portfolio):
    balance = {}
    if portfolio.get("futures_value_usd") is not None:
        balance["FUTURES_USD"] = portfolio.get("futures_value_usd", 0)
    if portfolio.get("spot_value_usd") is not None:
        balance["SPOT_USD"] = portfolio.get("spot_value_usd", 0)

    platform_breakdowns = portfolio.get("platform_breakdowns") or {}
    if isinstance(platform_breakdowns, dict):
        oanda_breakdown = platform_breakdowns.get("oanda") or {}
        oanda_summary = oanda_breakdown.get("summary") or {}
        oanda_balance = oanda_summary.get("balance", oanda_breakdown.get("total_value_usd"))
        try:
            oanda_balance_num = float(oanda_balance)
        except (TypeError, ValueError):
            oanda_balance_num = 0.0
        if oanda_balance_num > 0:
            balance["oanda_USD"] = oanda_balance_num
    return balance


def test_core_balance_derivation_includes_oanda_balance_from_platform_breakdown():
    portfolio = {
        "futures_value_usd": 741.15,
        "spot_value_usd": 0.0,
        "platform_breakdowns": {
            "coinbase": {"total_value_usd": 741.15},
            "oanda": {"summary": {"balance": 166.72}, "total_value_usd": 166.72},
        },
    }

    balance = derive_balance_like_core(portfolio)

    assert balance["FUTURES_USD"] == 741.15
    assert balance["SPOT_USD"] == 0.0
    assert balance["oanda_USD"] == 166.72
