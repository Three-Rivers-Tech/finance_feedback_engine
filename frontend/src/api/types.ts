// API Response Types
export interface AgentStatus {
  state: 'stopped' | 'starting' | 'running' | 'stopping' | 'error';
  agent_ooda_state: 'IDLE' | 'PERCEPTION' | 'REASONING' | 'RISK_CHECK' | 'EXECUTION' | 'LEARNING' | null;
  uptime_seconds: number | null;
  total_trades: number;
  active_positions: number;
  portfolio_value: number | null;
  daily_pnl: number | null;
  current_asset_pair: string | null;
  last_decision_time: string | null;
  error_message: string | null;
  config: {
    asset_pairs: string[];
    autonomous: boolean;
    paused?: boolean;
  };
}

export interface Position {
  id: string;
  asset_pair: string;
  side: 'LONG' | 'SHORT';
  size: number;
  entry_price: number;
  current_price: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  margin_used?: number;
}

export interface Decision {
  decision_id: string;
  asset_pair: string;
  action: 'BUY' | 'SELL' | 'HOLD';
  confidence: number;
  reasoning: string;
  timestamp: string;
  executed?: boolean;
  execution_result?: {
    order_id: string;
    status: string;
    fill_price?: number;
  };
}

export interface PortfolioStatus {
  balance: {
    total: number;
    available: number;
    currency: string;
  };
  active_positions: number;
  max_concurrent_trades?: number;
  platform: string;
  error?: string;
}

export interface HealthStatus {
  status: 'healthy' | 'degraded' | 'unhealthy';
  uptime_seconds: number;
  portfolio_balance: number | null;
  circuit_breakers?: Record<string, {
    state: string;
    failure_count: number;
  }>;
}

export interface BotConfig {
  asset_pairs?: string[];
  decision_threshold?: number;
  max_daily_trades?: number;
  autonomous?: boolean;
  stop_loss?: number;
  take_profit?: number;
}

export interface ApiError {
  detail: string;
  reference_id?: string;
}

// Optimization/Experiment Types
export interface ExperimentRequest {
  asset_pairs: string[];
  start_date: string;
  end_date: string;
  n_trials?: number;
  seed?: number | null;
  optimize_weights?: boolean;
  multi_objective?: boolean;
}

export interface ExperimentResult {
  asset_pair: string;
  best_sharpe_ratio: number | null;
  best_drawdown_pct: number | null;
  best_params: Record<string, any>;
  n_trials: number;
}

export interface ExperimentResponse {
  experiment_id: string;
  created_at: string;
  start_date: string;
  end_date: string;
  n_trials_per_asset: number;
  seed: number | null;
  optimize_weights: boolean;
  multi_objective: boolean;
  asset_pairs: string[];
  results: ExperimentResult[];
}

export interface ExperimentSummary {
  experiment_id: string;
  created_at: string;
  asset_pairs: string[];
  n_trials: number;
  results_count: number;
}
