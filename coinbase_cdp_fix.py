#!/usr/bin/env python3
"""
Patch script to update Coinbase platform to use CDP API (portfolio-based).
This replaces the old accounts/futures API with the new portfolio API.
"""


def create_patch():
    return """
--- a/finance_feedback_engine/trading_platforms/coinbase_platform.py
+++ b/finance_feedback_engine/trading_platforms/coinbase_platform.py
@@ -200,35 +200,31 @@ class CoinbaseAdvancedPlatform(BaseTradingPlatform):

-            # Get spot balances for USD and USDC
+            # Get portfolio breakdown (CDP API - bracket notation)
             try:
-                accounts_response = client.get_accounts()
-                accounts_list = getattr(accounts_response, "accounts", [])
-
-                for account in accounts_list:
-                    # Use attribute access for Coinbase Account objects
-                    currency = getattr(account, "currency", "")
-                    if currency in ["USD", "USDC"]:
-                        account_id = getattr(account, "id", "")
-                        truncated_id = account_id[-4:] if account_id else "N/A"
-                        available_balance = getattr(account, "available_balance", None)
-                        available_balance_value = (
-                            getattr(available_balance, "value", "N/A")
-                            if available_balance
-                            else "N/A"
-                        )
-                        logger.debug(
-                            "Inspecting spot account for %s: id=...%s, available_balance=%s",
-                            currency,
-                            truncated_id,
-                            available_balance_value,
-                        )
-                        if available_balance:
-                            balance_value = float(
-                                getattr(available_balance, "value", 0)
-                            )
-
-                            if balance_value > 0:
-                                balances[f"SPOT_{currency}"] = balance_value
-                                logger.info(
-                                    "Spot %s balance: $%.2f", currency, balance_value
-                                )
+                portfolios_response = client.get_portfolios()
+                portfolios = portfolios_response.portfolios
+
+                if portfolios:
+                    portfolio_uuid = portfolios[0]['uuid']
+                    breakdown = client.get_portfolio_breakdown(portfolio_uuid=portfolio_uuid)
+                    breakdown_data = breakdown['breakdown']  # Supports bracket notation
+
+                    # Get total cash
+                    portfolio_balances = breakdown_data['portfolio_balances']
+                    total_cash = float(portfolio_balances['total_cash_equivalent_balance']['value'])
+
+                    if total_cash > 0:
+                        balances['TOTAL_USD'] = total_cash
+                        logger.info("Portfolio total cash: $%.2f", total_cash)
+
+                    # Get spot USD/USDC
+                    spot_positions = breakdown_data['spot_positions']
+                    for position in spot_positions:
+                        asset = position['asset']
+                        if asset in ['USD', 'USDC']:
+                            available_fiat = float(position['available_to_trade_fiat'])
+                            if available_fiat > 0:
+                                balances[f"SPOT_{asset}"] = available_fiat
+                                logger.info("Spot %s: $%.2f", asset, available_fiat)
             except Exception as e:
-                logger.warning("Could not fetch spot balances: %s", e)
+                logger.warning("Could not fetch portfolio balances: %s", e)
"""


if __name__ == "__main__":
    print("This is a reference patch. Apply manually to coinbase_platform.py")
    print(create_patch())
