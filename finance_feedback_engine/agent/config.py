from typing import List, Literal
from pydantic import BaseModel, Field

class AutonomousAgentConfig(BaseModel):
    """Configuration for the autonomous trading agent."""
    enabled: bool = False
    profit_target: float = 0.05  # 5%
    stop_loss: float = 0.02  # 2%

class TradingAgentConfig(BaseModel):
    """
    Configuration model for the Trading Agent.
    Defines the agent's behavior, risk parameters, and operational controls.
    """
    # --- Execution Controls ---
    autonomous_execution: bool = False
    approval_policy: Literal["always", "never", "on_new_asset"] = "on_new_asset"
    max_daily_trades: int = 5
    # Kill-switch thresholds (percentage of portfolio P/L)
    # Stop trading if portfolio gains >= kill_switch_gain_pct
    # or losses <= -kill_switch_loss_pct
    kill_switch_gain_pct: float = 0.05  # 5%
    kill_switch_loss_pct: float = 0.02  # 2%
    autonomous: AutonomousAgentConfig = Field(default_factory=AutonomousAgentConfig)

    # --- Strategic Goals ---
    strategic_goal: Literal["growth", "capital_preservation", "balanced"] = "balanced"
    risk_appetite: Literal["low", "medium", "high"] = "medium"
    max_drawdown_percent: float = 15.0

    # --- Risk Management ---
    # Note: All percentages use decimal notation (e.g., 0.02 = 2%)
    # - risk_percentage: Account risk per trade (used in position sizing)
    # - sizing_stop_loss_percentage: Assumed stop loss for position sizing calculations
    # - kill_switch_loss_pct: Portfolio-level loss threshold to stop trading
    # - stop_loss (in AutonomousAgentConfig): Per-trade stop loss for autonomous execution
    risk_percentage: float = 0.01  # Percentage of account to risk per trade (1%)
    sizing_stop_loss_percentage: float = 0.02  # Stop loss used for position sizing calculation (2%)

    # --- Data & Analysis Controls ---
    asset_pairs: List[str] = ["BTCUSD", "ETHUSD"]
    analysis_frequency_seconds: int = 300
    monitoring_frequency_seconds: int = 60
    min_confidence_threshold: float = 70.0  # Minimum confidence to execute a trade