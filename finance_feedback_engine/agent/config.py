from typing import List, Literal
from pydantic import BaseModel, Field, field_validator, model_validator

class AutonomousAgentConfig(BaseModel):
    """Configuration for the autonomous trading agent."""
    enabled: bool = False
    profit_target: float = 0.05  # 5%
    stop_loss: float = 0.02  # 2%

class TradingAgentConfig(BaseModel):
    """
    Configuration model for the Trading Agent.
    Defines the agent's behavior, risk parameters, and operational controls.
    
    All percentage fields use decimal fraction notation (e.g., 0.05 = 5%).
    """
    # --- Execution Controls ---
    autonomous_execution: bool = False
    approval_policy: Literal["always", "never", "on_new_asset"] = "on_new_asset"
    max_daily_trades: int = 5
    # Kill-switch thresholds (decimal fraction of portfolio P/L, e.g., 0.05 = 5%)
    # Stop trading if portfolio gains >= kill_switch_gain_pct
    # or losses <= -kill_switch_loss_pct
    kill_switch_gain_pct: float = 0.05  # 5%
    kill_switch_loss_pct: float = 0.02  # 2%
    autonomous: AutonomousAgentConfig = Field(default_factory=AutonomousAgentConfig)

    # --- Strategic Goals ---
    strategic_goal: Literal["growth", "capital_preservation", "balanced"] = "balanced"
    risk_appetite: Literal["low", "medium", "high"] = "medium"
    max_drawdown_percent: float = 0.15  # Max drawdown threshold (auto-normalized: values >1 treated as percentages, <=1 as decimals)

    # --- Risk Management ---
    # Note: All percentages use decimal notation (e.g., 0.02 = 2%)
    # - risk_percentage: Account risk per trade (used in position sizing)
    # - sizing_stop_loss_percentage: Assumed stop loss for position sizing calculations
    # - kill_switch_loss_pct: Portfolio-level loss threshold (decimal fraction, e.g., 0.02 = 2%) to stop trading
    # - stop_loss (in AutonomousAgentConfig): Per-trade stop loss for autonomous execution
    risk_percentage: float = 0.01  # Percentage of account to risk per trade (1%)
    sizing_stop_loss_percentage: float = 0.02  # Stop loss used for position sizing calculation (2%)

    # RiskGatekeeper configuration (all decimals; validation enforces bounds)
    # - correlation_threshold: Asset correlation threshold to consider positions correlated (e.g., 0.7 = 70%)
    # - max_correlated_assets: Max number of correlated assets allowed within a category/platform before blocking
    # - max_var_pct: Maximum acceptable portfolio VaR percentage (decimal, e.g., 0.05 = 5%)
    # - var_confidence: Confidence level used for VaR checks (decimal, e.g., 0.95 = 95%)
    correlation_threshold: float = Field(0.7, ge=0.0, le=1.0)
    max_correlated_assets: int = Field(2, gt=0)
    max_var_pct: float = Field(0.05, ge=0.0, le=1.0)
    var_confidence: float = Field(0.95, gt=0.0, lt=1.0)

    @field_validator('correlation_threshold', 'max_var_pct', 'var_confidence', 'max_drawdown_percent', 'min_confidence_threshold', mode='before')
    @classmethod
    def normalize_percentage_fields(cls, v):
        """Normalize percentage values: if value > 1, treat as percentage and divide by 100.
        
        Handles both percentage notation (e.g., 70 -> 0.70) and decimal notation (e.g., 0.70 -> 0.70).
        Values > 1 are assumed to be percentages and divided by 100.
        Values <= 1 are assumed to be already in decimal format and returned as-is.
        """
        if isinstance(v, (int, float)) and v > 1:
            return v / 100
        return v

    @model_validator(mode='after')
    def normalize_default_percentages(self):
        """Normalize default percentage values that weren't caught by field validators.
        
        Field validators with mode='before' only run on explicitly provided values,
        not on defaults. This model validator ensures defaults are also normalized.
        """
        if self.min_confidence_threshold > 1:
            self.min_confidence_threshold = self.min_confidence_threshold / 100
        return self

    # --- Data & Analysis Controls ---
    asset_pairs: List[str] = ["BTCUSD", "ETHUSD"]
    analysis_frequency_seconds: int = 300
    monitoring_frequency_seconds: int = 60
    min_confidence_threshold: float = 70.0  # Minimum confidence to execute a trade (0-100 scale, auto-normalized to 0-1)
    # Asset pairs to monitor for opportunities (superset of asset_pairs for active trading)
    watchlist: List[str] = ["BTCUSD", "ETHUSD", "EURUSD"]

    # --- Timing and Retry Controls ---
    reasoning_retry_delay_seconds: int = 60
    reasoning_failure_decay_seconds: int = 3600
    main_loop_error_backoff_seconds: int = 300