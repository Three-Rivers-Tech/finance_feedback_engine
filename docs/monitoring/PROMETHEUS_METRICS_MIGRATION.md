# Prometheus Metrics Migration: Trade P&L

This document outlines the changes and migration steps for the Finance Feedback Engine Prometheus metrics related to Trade P&L.

## Summary
- Restored original per-trade metric `ffe_trade_pnl_dollars` with labels: `asset_pair`, `trade_id`.
- Added aggregated metric `ffe_trade_pnl_dollars_v2` with labels: `asset_pair` only.
- Both metrics will be emitted during the migration period to preserve historical continuity and avoid breaking dashboards/alerts.

## Metrics
- Per-trade (original):
  - Name: `ffe_trade_pnl_dollars`
  - Labels: `asset_pair`, `trade_id`
  - Semantics: P&L for a specific trade.
- Aggregated (v2):
  - Name: `ffe_trade_pnl_dollars_v2`
  - Labels: `asset_pair`
  - Semantics: Aggregated P&L across trades for an asset pair.

## Code Changes
- File: finance_feedback_engine/monitoring/prometheus.py
- New functions:
  - `update_trade_pnl_trade(asset_pair: str, trade_id: str, pnl_dollars: float)` — emits per-trade metric.
  - `update_trade_pnl(asset_pair: str, pnl_dollars: float)` — now emits aggregated v2 metric.

## Migration Plan
1. Dual Emission Period:
   - Continue emitting `ffe_trade_pnl_dollars` for per-trade values.
   - Start emitting `ffe_trade_pnl_dollars_v2` for aggregated values.
2. Dashboard/Alert Updates:
   - Queries expecting per-trade semantics should continue using `ffe_trade_pnl_dollars`.
   - Queries that require aggregated values should switch to `ffe_trade_pnl_dollars_v2`.
3. Verification Steps:
   - Validate that both metrics appear in `/metrics` endpoint.
   - Check historical continuity for `ffe_trade_pnl_dollars` (no label changes).
   - Confirm dashboards/alerts referencing aggregated values are updated to v2.
4. Cutover:
   - After dashboards/alerts have migrated, keep both metrics to retain historical per-trade series and avoid breaking existing analyses.

## Prometheus Recording Rules (Alternative to app-side aggregation)
If you prefer Prometheus-side aggregation, add the recording rules in:
- docs/monitoring/prometheus_recording_rules.yaml

Key rules:
- `ffe_trade_pnl_dollars_v2{asset_pair}` recorded as `sum by (asset_pair) (ffe_trade_pnl_dollars)`.
- Additional helpers for best/worst trade and portfolio totals.

Prometheus config snippet:

```
rule_files:
  - /etc/prometheus/rules/finance_feedback_engine/prometheus_recording_rules.yaml
```

Then update dashboards to reference the recorded `ffe_trade_pnl_dollars_v2` or `ffe_trade_pnl_dollars_sum_by_asset_pair` instead of raw per-trade series.

## Example Prometheus Queries
- Per-trade P&L (original):
  - `ffe_trade_pnl_dollars{asset_pair="BTCUSD", trade_id="<id>"}`
- Aggregated P&L (v2):
  - `ffe_trade_pnl_dollars_v2{asset_pair="BTCUSD"}`

## Notes
- The previous change removing `trade_id` from `ffe_trade_pnl_dollars` was breaking. This migration re-establishes the original semantics.
- Ensure any internal processing functions differentiate between per-trade vs. aggregated updates and call the appropriate emit function.
