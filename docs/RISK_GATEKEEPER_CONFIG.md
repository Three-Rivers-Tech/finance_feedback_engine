# RiskGatekeeper Configuration

The Trading Agent now exposes configurable risk management parameters. All percentage-like values should be provided in decimal fraction notation (e.g., `0.05` = 5%). For convenience, values greater than `1` for percentage-like fields are normalized by dividing by 100 (e.g., `5` -> `0.05`).

## Fields

- `correlation_threshold` (decimal [0,1]): Asset correlation threshold considered "correlated". Example: `0.7` (70%).
- `max_correlated_assets` (int > 0): Maximum number of correlated assets allowed within a category/platform before blocking new trades.
- `max_var_pct` (decimal [0,1]): Maximum acceptable portfolio Value-at-Risk fraction. Example: `0.05` (5%).
- `var_confidence` (decimal (0,1)): Confidence level used for VaR checks. Example: `0.95` (95%).

## Location

These fields live in `finance_feedback_engine/agent/config.py` under `TradingAgentConfig`. They are passed to `RiskGatekeeper` by `TradingLoopAgent` during initialization.

## Example

```yaml
# config.yaml (excerpt)
trading_agent:
  correlation_threshold: 0.7
  max_correlated_assets: 2
  max_var_pct: 0.05
  var_confidence: 0.95
```
