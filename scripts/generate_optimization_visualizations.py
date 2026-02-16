#!/usr/bin/env python3
"""Generate visualizations for optimization analysis report."""

import json
import pandas as pd

# Load optimization results
csv_files = [
    ("BTC/USD", "optuna_results_btcusd.csv"),
    ("ETH/USD", "optuna_results_ethusd.csv"),
    ("EUR/USD 90D", "optuna_results_eurusd_90d.csv"),
    ("EUR/USD M15", "optuna_results_eurusd_m15.csv"),
    ("GBP/USD", "optuna_results_gbpusd.csv"),
]

print("=" * 80)
print("OPTIMIZATION VISUALIZATION DATA")
print("=" * 80)

# Generate text-based summary (matplotlib not needed for report)
summary_data = {}

for pair_name, csv_file in csv_files:
    df = pd.read_csv(csv_file)
    best_idx = df["sharpe_ratio"].idxmax()
    top_10 = df.nlargest(int(len(df) * 0.1), "sharpe_ratio")
    
    summary_data[pair_name] = {
        "best_sharpe": float(df["sharpe_ratio"].max()),
        "avg_sharpe": float(df["sharpe_ratio"].mean()),
        "best_params": {
            "stop_loss_pct": float(df.loc[best_idx, "stop_loss_pct"]),
            "take_profit_pct": float(df.loc[best_idx, "take_profit_pct"]),
            "position_size_pct": float(df.loc[best_idx, "position_size_pct"]),
        },
        "top_10_ranges": {
            "stop_loss": [float(top_10["stop_loss_pct"].min()), float(top_10["stop_loss_pct"].max())],
            "take_profit": [float(top_10["take_profit_pct"].min()), float(top_10["take_profit_pct"].max())],
        }
    }

with open("optimization_summary_data.json", "w") as f:
    json.dump(summary_data, f, indent=2)

print("\n✓ Saved summary data to optimization_summary_data.json")
print("\nKey findings:")
for pair, data in summary_data.items():
    tp_sl_ratio = data["best_params"]["take_profit_pct"] / data["best_params"]["stop_loss_pct"]
    status = "✅" if tp_sl_ratio >= 1.0 else "❌"
    print(f"\n{pair}:")
    print(f"  Sharpe: {data['best_sharpe']:.2f}")
    print(f"  TP/SL: {tp_sl_ratio:.2f}:1 {status}")
