# C4 Code Level: Finance Feedback Engine CLI

## Overview

- **Name**: Finance Feedback Engine Command-Line Interface
- **Description**: Comprehensive CLI system for autonomous trading agent control, decision analysis, backtesting, portfolio management, and learning validation
- **Location**: `finance_feedback_engine/cli`
- **Language**: Python 3.8+
- **Purpose**: Provides interactive and programmatic interface to all core engine capabilities including trading agent orchestration, decision analysis, backtesting, optimization, and portfolio monitoring

## Architecture Overview

The CLI is organized as a modular command system with a main entry point (`main.py`) that orchestrates sub-command modules by domain. The architecture follows Click's group-based command organization with centralized configuration loading and logging setup.

### Core Structure

```
finance_feedback_engine/cli/
├── main.py                    # Main CLI entry point, config loading, logging setup
├── interactive.py             # Interactive shell mode for CLI commands
├── auth_cli.py               # API key management commands
├── backtest_formatter.py      # Backtest results formatting utilities
├── dashboard_aggregator.py    # Live dashboard data collection
├── live_dashboard.py          # Real-time dashboard rendering
├── test_core.py              # Unit tests for core CLI functionality
├── commands/                 # Modular command implementations
│   ├── __init__.py
│   ├── agent.py              # Autonomous agent control, monitoring
│   ├── analysis.py           # Asset analysis, decision generation
│   ├── backtest.py          # Backtesting, walk-forward, Monte Carlo
│   ├── trading.py           # Trade execution, balance display
│   ├── memory.py            # Learning reports, memory pruning
│   ├── optimize.py          # Hyperparameter optimization (Optuna)
│   ├── experiment.py        # Experimental features
│   ├── demo.py              # Interactive demo mode
│   └── frontend.py          # Frontend/UI commands
├── formatters/              # Output formatting modules
│   ├── __init__.py
│   └── pulse_formatter.py    # Multi-timeframe technical analysis display
└── validators/              # Input validation
    └── __init__.py
```

## Code Elements

### Main Entry Point: `main.py`

#### Functions

**`cli(ctx, config, verbose, trace, otlp_endpoint, interactive)`**
- **Signature**: `@click.group(invoke_without_command=True) def cli(ctx, config, verbose, trace, otlp_endpoint, interactive) -> None`
- **Description**: Root Click group defining CLI interface; loads configuration, initializes logging, tracing, and metrics before delegating to sub-commands
- **Location**: `main.py:439-660`
- **Dependencies**:
  - `load_config()`, `load_tiered_config()` - configuration loading
  - `setup_logging()` - logging initialization
  - `init_tracer()` from `finance_feedback_engine.observability`
  - `init_metrics()` from `finance_feedback_engine.monitoring.metrics`
  - `_validate_config_on_startup()` - configuration validation
  - All registered sub-commands

**`setup_logging(verbose, config)`**
- **Signature**: `def setup_logging(verbose: bool = False, config: dict = None) -> None`
- **Description**: Initializes mandatory structured JSON logging to `data/logs/` directory with configurable log level
- **Location**: `main.py:191-260`
- **Dependencies**:
  - `logging` module
  - `JSONFormatter` internal class
  - Optional: `finance_feedback_engine.observability.context.OTelContextFilter`

**`load_tiered_config() -> dict`**
- **Signature**: `def load_tiered_config() -> dict`
- **Description**: Loads configuration from tiered sources with precedence: `config/config.local.yaml` > `config/config.yaml` > environment variables
- **Location**: `main.py:345-371`
- **Dependencies**:
  - `Path` from `pathlib`
  - `yaml` module
  - `finance_feedback_engine.utils.config_loader.load_config` - handles environment variable substitution

**`load_config(config_path: str) -> dict`**
- **Signature**: `def load_config(config_path: str) -> dict`
- **Description**: Loads explicit configuration file with proper environment variable substitution (YAML or JSON)
- **Location**: `main.py:373-399`
- **Dependencies**:
  - `Path` from `pathlib`
  - `finance_feedback_engine.utils.config_loader.load_config` - for YAML environment substitution
  - `json` module for JSON files
  - `click.ClickException` for error handling

**`_validate_config_on_startup(config_path: str, environment: str = "development")`**
- **Signature**: `def _validate_config_on_startup(config_path: str, environment: str = "development") -> None`
- **Description**: Pre-startup validation of configuration file; fails on critical/high severity issues
- **Location**: `main.py:61-96`
- **Dependencies**:
  - `finance_feedback_engine.utils.config_validator.validate_config_file`
  - `finance_feedback_engine.utils.config_validator.print_validation_results`
  - `click.ClickException` for error handling

**`config_editor(ctx, output)`**
- **Signature**: `@cli.command(name="config-editor") def config_editor(ctx, output) -> None`
- **Description**: Interactive CLI wizard for API key setup, platform configuration, and trading parameters; saves overlay to `config/config.local.yaml`
- **Location**: `main.py:662-916`
- **Dependencies**:
  - `click.prompt()`, `click.confirm()` - user input
  - `load_config()` - read existing config
  - `yaml.safe_dump()` - write configuration
  - `Path` from `pathlib`
  - Helper functions: `_get_nested()`, `_set_nested()`, `current()`, `prompt_text()`, `prompt_choice()`, `prompt_bool()`

**`install_deps(ctx, auto_install)`**
- **Signature**: `@cli.command(name="install-deps") def install_deps(ctx, auto_install) -> None`
- **Description**: Checks and installs missing Python dependencies from `requirements.txt` and CLI tools (Ollama, Node.js)
- **Location**: `main.py:918-1152`
- **Dependencies**:
  - `_check_dependencies()` - detect missing packages
  - `_parse_requirements_file()` - parse requirements
  - `_get_installed_packages()` - query pip
  - `subprocess` for installations
  - `rich.table.Table` for display

**`update_ai(ctx, auto_install)`**
- **Signature**: `@cli.command(name="update-ai") def update_ai(ctx, auto_install) -> None`
- **Description**: Updates AI provider dependencies (PyPI packages like `google-generativeai`) and npm CLI tools (Copilot, Qwen)
- **Location**: `main.py:1154-1415`
- **Dependencies**:
  - `_get_installed_packages()` - check PyPI packages
  - `subprocess` for npm installation
  - `rich.table.Table` for display

**`dashboard(ctx)`**
- **Signature**: `@cli.command() def dashboard(ctx) -> None`
- **Description**: Displays unified portfolio dashboard aggregating all platform portfolios
- **Location**: `main.py:1538-1569`
- **Dependencies**:
  - `FinanceFeedbackEngine` from `finance_feedback_engine.core`
  - `PortfolioDashboardAggregator`, `display_portfolio_dashboard` from `finance_feedback_engine.dashboard`

**`approve(ctx, decision_id)`**
- **Signature**: `@cli.command() def approve(ctx, decision_id) -> None`
- **Description**: Interactive approval workflow for trading decisions; allows modification of position size, stop loss, take profit
- **Location**: `main.py:1571-1767`
- **Dependencies**:
  - `DecisionStore` from `finance_feedback_engine.persistence.decision_store`
  - `_save_approval_response()` - persist decision
  - `_get_action_color()` - display formatting
  - `click.prompt()`, `Prompt.ask()` - user interaction
  - `inc()` from `finance_feedback_engine.monitoring.metrics` - metrics tracking

**`status(ctx)`**
- **Signature**: `@cli.command() def status(ctx) -> None`
- **Description**: Displays engine status, configuration, and dynamic platform leverage info
- **Location**: `main.py:1769-1813`
- **Dependencies**:
  - `FinanceFeedbackEngine` from `finance_feedback_engine.core`

**`positions(ctx)`**
- **Signature**: `@cli.command() def positions(ctx) -> None`
- **Description**: Shows active trading positions from configured platform with P&L and current metrics
- **Location**: `main.py:1815-1864`
- **Dependencies**:
  - `FinanceFeedbackEngine` from `finance_feedback_engine.core`
  - `click.ClickException` for error handling

**`wipe_decisions(ctx, confirm)`**
- **Signature**: `@cli.command() def wipe_decisions(ctx, confirm) -> None`
- **Description**: Deletes all stored trading decisions after confirmation
- **Location**: `main.py:1866-1909`
- **Dependencies**:
  - `FinanceFeedbackEngine` from `finance_feedback_engine.core`
  - `click.confirm()` - user confirmation

**`retrain_meta_learner(ctx, force)`**
- **Signature**: `@cli.command(name="retrain-meta-learner") def retrain_meta_learner(ctx, force) -> None`
- **Description**: Checks stacking ensemble performance and retrains if win rate falls below 55% threshold
- **Location**: `main.py:1941-2013`
- **Dependencies**:
  - `FinanceFeedbackEngine` from `finance_feedback_engine.core`
  - `train_meta_learner.run_training()` (project root)

#### Helper Functions

**`_display_pulse_data(engine, asset_pair: str)`**
- **Signature**: `def _display_pulse_data(engine, asset_pair: str) -> None`
- **Description**: Displays multi-timeframe pulse technical analysis data with trend alignment analysis
- **Location**: `main.py:98-189`
- **Dependencies**:
  - `rich.table.Table` - display formatting
  - Engine monitoring and data provider interfaces

**`_parse_requirements_file(req_file: Path) -> list`**
- **Signature**: `def _parse_requirements_file(req_file: Path) -> list`
- **Description**: Parses `requirements.txt` file and extracts package names
- **Location**: `main.py:262-308`
- **Dependencies**:
  - `packaging.requirements.Requirement` - robust requirement parsing

**`_get_installed_packages() -> dict`**
- **Signature**: `def _get_installed_packages() -> dict`
- **Description**: Queries `pip list --format=json` to get installed package versions
- **Location**: `main.py:310-331`
- **Dependencies**:
  - `subprocess` - execute pip
  - `json` - parse output

**`_check_dependencies() -> tuple`**
- **Signature**: `def _check_dependencies() -> tuple`
- **Description**: Compares required vs installed packages; returns (missing, installed) tuples
- **Location**: `main.py:333-362`
- **Dependencies**:
  - `_parse_requirements_file()`, `_get_installed_packages()`

**`_get_nested(config: dict, keys: tuple, default=None)`**
- **Signature**: `def _get_nested(config: dict, keys: tuple, default=None)`
- **Description**: Safely retrieves nested dictionary values
- **Location**: `main.py:401-410`

**`_set_nested(config: dict, keys: tuple, value)`**
- **Signature**: `def _set_nested(config: dict, keys: tuple, value)`
- **Description**: Sets nested dictionary values, creating intermediate levels as needed
- **Location**: `main.py:412-419`

**`_deep_merge_dicts(d1: dict, d2: dict) -> dict`**
- **Signature**: `def _deep_merge_dicts(d1: dict, d2: dict) -> dict`
- **Description**: Deep merges d2 into d1, overwriting values
- **Location**: `main.py:421-427`

**`_deep_fill_missing(target: dict, source: dict) -> dict`**
- **Signature**: `def _deep_fill_missing(target: dict, source: dict) -> dict`
- **Description**: Fills missing keys in target from source without overwriting
- **Location**: `main.py:429-441`

**`_get_action_color(action: str) -> str`**
- **Signature**: `def _get_action_color(action: str) -> str`
- **Description**: Maps trading action to Rich console color
- **Location**: `main.py:1743-1752`

**`_save_approval_response(decision_id: str, approved: bool, modified: bool, decision: dict)`**
- **Signature**: `def _save_approval_response(decision_id: str, approved: bool, modified: bool, decision: dict)`
- **Description**: Saves approval response to `data/approvals/` with sanitized filenames and path traversal protection
- **Location**: `main.py:1754-1795`
- **Dependencies**:
  - `Path` from `pathlib`
  - `re` for filename sanitization
  - `json` for serialization

#### Module Constants

- `CONFIG_MODE_TIERED = "tiered"` - Marker for tiered configuration loading mode (line 57)

#### Module Variables

- `console: Console` - Rich console instance for output (line 53)
- `logger: logging.Logger` - Logger instance (line 54)

---

### Interactive Mode: `interactive.py`

#### Functions

**`start_interactive_session(main_cli)`**
- **Signature**: `def start_interactive_session(main_cli) -> None`
- **Description**: Starts an interactive shell session with command discovery and help; displays menu of available commands
- **Location**: `interactive.py:26-189`
- **Dependencies**:
  - `click.Context`, `click.get_command()` - command resolution
  - `Path` from `pathlib`
  - `load_tiered_config()` from `finance_feedback_engine.cli.main`
  - `rich.console.Console`, `rich.table.Table` - display
  - Keyboard/EOF handling for shell interaction

**`_build_command_index(main_cli) -> list`**
- **Signature**: `def _build_command_index(main_cli) -> list`
- **Description**: Returns list of (name, help_text) tuples for all top-level CLI commands
- **Location**: `interactive.py:8-17`
- **Dependencies**:
  - Click command group introspection

**`_show_menu(main_cli)`**
- **Signature**: `def _show_menu(main_cli) -> None`
- **Description**: Renders Rich table of available commands with descriptions
- **Location**: `interactive.py:19-32`
- **Dependencies**:
  - `rich.table.Table` for formatting

#### Module Variables

- `console: Console` - Rich console instance (line 6)

---

### Modular Commands

#### `commands/agent.py`

Agent control and trade monitoring commands.

**Functions**

**`run_agent(ctx, take_profit, stop_loss, setup, autonomous, max_drawdown, asset_pairs, yes)`**
- **Signature**: `@click.command(name="run-agent") def run_agent(...) -> None`
- **Description**: Starts autonomous trading agent; handles legacy percentage conversion, confirmation, configuration validation, and concurrent execution with live dashboard
- **Location**: `agent.py:372-462`
- **Parameters**:
  - `take_profit`: Portfolio take-profit (decimal, e.g., 0.05 for 5%)
  - `stop_loss`: Portfolio stop-loss (decimal)
  - `setup`: Run config editor before agent start
  - `autonomous`: Force autonomous execution (skip approvals)
  - `asset_pairs`: Comma-separated override for trading pairs
  - `yes`: Skip confirmation prompt
- **Dependencies**:
  - `_initialize_agent()` - agent setup
  - `_confirm_agent_startup()` - user confirmation
  - `_validate_config_on_startup()` - config validation
  - `_run_live_dashboard()` - concurrent dashboard
  - `asyncio.run()` for concurrent execution
  - `FinanceFeedbackEngine` from `finance_feedback_engine.core`

**`_initialize_agent(config, engine, take_profit, stop_loss, autonomous, asset_pairs_override=None)`**
- **Signature**: `def _initialize_agent(config, engine, take_profit, stop_loss, autonomous, asset_pairs_override=None)`
- **Description**: Initializes agent with config, trade monitor, and signal-only validation; supports autonomous and signal-only modes
- **Location**: `agent.py:46-156`
- **Dependencies**:
  - `TradingAgentConfig` from `finance_feedback_engine.agent.config`
  - `TradingLoopAgent` from `finance_feedback_engine.agent.trading_loop_agent`
  - `TradeMonitor` from `finance_feedback_engine.monitoring.trade_monitor`
  - Validation of notification channels (Telegram/webhook)

**`_run_live_dashboard(engine, agent)`**
- **Signature**: `async def _run_live_dashboard(engine, agent)`
- **Description**: Async coroutine for live dashboard with tiered refresh rates (fast: 10s, medium: 30s, slow: 60s, lazy: 120s)
- **Location**: `agent.py:158-220`
- **Dependencies**:
  - `DashboardDataAggregator`, `LiveDashboard` from CLI dashboard modules
  - `asyncio.sleep()` for update timing
  - `rich.live.Live` for interactive rendering

**`_confirm_agent_startup(config, take_profit, stop_loss, asset_pairs_override=None, skip_confirmation=False) -> bool`**
- **Signature**: `def _confirm_agent_startup(config, take_profit, stop_loss, asset_pairs_override=None, skip_confirmation=False) -> bool`
- **Description**: Displays configuration summary and prompts for confirmation
- **Location**: `agent.py:287-335`
- **Dependencies**:
  - `_display_agent_configuration_summary()` - config display
  - `click.confirm()` - user interaction

**`_display_agent_configuration_summary(config, take_profit, stop_loss, asset_pairs_override=None)`**
- **Signature**: `def _display_agent_configuration_summary(config, take_profit, stop_loss, asset_pairs_override=None)`
- **Description**: Displays execution mode, notification channels, trading parameters before startup
- **Location**: `agent.py:222-285`
- **Dependencies**:
  - `rich.panel.Panel`, `rich.table.Table` for formatting

**`monitor(ctx)` - Click Group**
- **Signature**: `@click.group() def monitor(ctx)`
- **Description**: Group for live trade monitoring sub-commands
- **Location**: `agent.py:464-476`
- **Sub-commands**:
  - `start(ctx)` - Start live monitoring (deprecated, now auto-starts)
  - `status(ctx)` - Show monitoring status (deprecated)
  - `metrics(ctx)` - Display trade performance metrics

#### `commands/analysis.py`

Asset analysis and decision history commands.

**Functions**

**`analyze(ctx, asset_pair, provider, show_pulse)`**
- **Signature**: `@click.command() def analyze(ctx, asset_pair, provider, show_pulse) -> None`
- **Description**: Analyzes asset pair and generates trading decision; handles provider override, Phase 1 quorum failures with disk logging, and optional pulse display
- **Location**: `analysis.py:24-175`
- **Parameters**:
  - `asset_pair`: Asset pair to analyze
  - `provider`: AI provider (local/cli/codex/qwen/gemini/ensemble)
  - `show_pulse`: Display multi-timeframe pulse data
- **Dependencies**:
  - `standardize_asset_pair()` from `finance_feedback_engine.utils.validation`
  - `FinanceFeedbackEngine` from `finance_feedback_engine.core`
  - `display_pulse_data()` from formatters
  - `_handle_engine_init_error()` - interactive fallback
  - `asyncio` for async decision generation

**`history(ctx, asset, limit)`**
- **Signature**: `@click.command() def history(ctx, asset, limit) -> None`
- **Description**: Shows decision history in table format with timestamp, asset, action, confidence, execution status
- **Location**: `analysis.py:177-228`
- **Parameters**:
  - `asset`: Filter by asset pair (optional)
  - `limit`: Number of decisions to show (default: 10)
- **Dependencies**:
  - `FinanceFeedbackEngine.get_decision_history()`
  - `DecisionStore` - fallback for test patching
  - `rich.table.Table` for display

**`_handle_engine_init_error(ctx, config, e)`**
- **Signature**: `def _handle_engine_init_error(ctx, config, e)`
- **Description**: Handles engine initialization errors with interactive fallback to mock platform
- **Location**: `analysis.py:230-261`
- **Dependencies**:
  - `FinanceFeedbackEngine` - retry with mock platform
  - `click.Abort()` for error handling

#### `commands/backtest.py`

Backtesting and validation commands.

**Functions**

**`backtest(ctx, asset_pair, start, end, initial_balance, fee_percentage, slippage_percentage, commission_per_trade, stop_loss_percentage, take_profit_percentage, timeframe, output_file)`**
- **Signature**: `@click.command() def backtest(...)`
- **Description**: Runs AI-driven single-asset backtest with configurable trading parameters, optional trade history export
- **Location**: `backtest.py:22-152`
- **Parameters**: Date range (YYYY-MM-DD), portfolio parameters, timeframe (1m/5m/15m/30m/1h/1d), output file path
- **Dependencies**:
  - `Backtester` from `finance_feedback_engine.backtesting.backtester`
  - `standardize_asset_pair()` from validation
  - `format_single_asset_backtest()` from backtest_formatter
  - Date validation and range checking

**`portfolio_backtest(ctx, asset_pairs, start, end, initial_balance, correlation_threshold, max_positions)`**
- **Signature**: `@click.command(name="portfolio-backtest") def portfolio_backtest(...)`
- **Description**: Multi-asset portfolio backtest with correlation-aware position sizing
- **Location**: `backtest.py:154-240`
- **Parameters**: Multiple asset pairs, date range, portfolio parameters, correlation threshold
- **Dependencies**:
  - `PortfolioBacktester` from `finance_feedback_engine.backtesting.portfolio_backtester`
  - `format_full_results()` from backtest_formatter

**`walk_forward(ctx, asset_pair, start_date, end_date, train_ratio, provider)`**
- **Signature**: `@click.command(name="walk-forward") def walk_forward(...)`
- **Description**: Walk-forward analysis with rolling train/test windows and overfitting detection
- **Location**: `backtest.py:242-342`
- **Parameters**: Asset, date range, train window ratio, AI provider
- **Dependencies**:
  - `WalkForwardAnalyzer` from `finance_feedback_engine.backtesting.walk_forward`
  - Overfitting assessment with NONE/LOW/MEDIUM/HIGH severity

**`monte_carlo(ctx, asset_pair, start_date, end_date, simulations, noise_std, provider)`**
- **Signature**: `@click.command(name="monte-carlo") def monte_carlo(...)`
- **Description**: Monte Carlo simulation with price perturbations and confidence intervals
- **Location**: `backtest.py:344-423`
- **Parameters**: Asset, date range, number of simulations, price noise standard deviation
- **Dependencies**:
  - `MonteCarloSimulator` from `finance_feedback_engine.backtesting.monte_carlo`
  - Percentile-based Value at Risk calculation

#### `commands/trading.py`

Trade execution and account commands.

**Functions**

**`balance(ctx)`**
- **Signature**: `@click.command() def balance(ctx)`
- **Description**: Shows current account balances in table format
- **Location**: `trading.py:16-50`
- **Dependencies**:
  - `FinanceFeedbackEngine.get_balance()`
  - `rich.table.Table` for display

**`execute(ctx, decision_id)`**
- **Signature**: `@click.command() def execute(ctx, decision_id)`
- **Description**: Executes trading decision; if no ID provided, shows recent executable decisions for selection
- **Location**: `trading.py:52-177`
- **Parameters**:
  - `decision_id`: ID of decision to execute (optional; prompts for selection if missing)
- **Dependencies**:
  - `FinanceFeedbackEngine.execute_decision()`
  - `DecisionStore` - fallback
  - Interactive selection menu

#### `commands/memory.py`

Learning and memory management commands.

**Functions**

**`learning_report(ctx, asset_pair)`**
- **Signature**: `@click.command(name="learning-report") def learning_report(ctx, asset_pair)`
- **Description**: Generates comprehensive learning validation report with RL/meta-learning metrics
- **Location**: `memory.py:15-127`
- **Metrics Displayed**:
  - Sample efficiency (DQN/Rainbow)
  - Cumulative regret (multi-armed bandits)
  - Concept drift detection with severity levels
  - Thompson Sampling diagnostics
  - Learning curve analysis with improvement percentages
- **Dependencies**:
  - `FinanceFeedbackEngine.memory_engine.generate_learning_validation_metrics()`

**`prune_memory(ctx, keep_recent, confirm)`**
- **Signature**: `@click.command(name="prune-memory") def prune_memory(ctx, keep_recent, confirm)`
- **Description**: Prunes old trade outcomes from portfolio memory, keeping only N most recent trades
- **Location**: `memory.py:129-187`
- **Parameters**:
  - `keep_recent`: Number of trades to retain (default: 1000)
  - `confirm`: Require confirmation before pruning
- **Dependencies**:
  - `FinanceFeedbackEngine.memory_engine.trade_outcomes`

#### `commands/optimize.py`

Hyperparameter optimization with Optuna and MLflow.

**Functions**

**`optimize(ctx, asset_pair, start_date, end_date, n_trials, timeout, multi_objective, optimize_weights, study_name, output_dir, mlflow_experiment, no_mlflow, show_progress)`**
- **Signature**: `@click.command() def optimize(...)`
- **Description**: Runs Optuna-based hyperparameter optimization with optional MLflow tracking
- **Location**: `optimize.py:34-230`
- **Optimizes**: Risk per trade (0.5%-3%), stop-loss (1%-5%), ensemble voting strategy, provider weights
- **Dependencies**:
  - `OptunaOptimizer` from `finance_feedback_engine.optimization.optuna_optimizer`
  - `mlflow` - optional experiment tracking
  - `_display_optimization_results()` - result formatting

**`_display_optimization_results(study, multi_objective)`**
- **Signature**: `def _display_optimization_results(study, multi_objective)`
- **Description**: Displays Pareto-optimal solutions (multi-objective) or best parameters (single-objective)
- **Location**: `optimize.py:232-291`
- **Dependencies**:
  - `rich.table.Table` for display

#### `commands/demo.py`

Interactive demonstration commands.

**Functions**

**`demo(mode, asset)`**
- **Signature**: `@click.command(name="demo") def demo(mode: str, asset: str) -> None`
- **Description**: Runs interactive demo with three modes: quick (30s analyze), full (all features), live-monitoring (trade tracking)
- **Location**: `demo.py:17-46`
- **Modes**:
  - `quick`: Single asset analysis
  - `full`: Multi-feature showcase with backtest
  - `live-monitoring`: Trade monitoring system demo
- **Dependencies**:
  - `FinanceFeedbackEngine` from `finance_feedback_engine.core`
  - Mode-specific demo functions

#### `commands/experiment.py`

Experimental feature commands (modular structure).

#### `commands/frontend.py`

Frontend/UI integration commands (modular structure).

---

### Formatters and Utilities

#### `formatters/pulse_formatter.py`

Multi-timeframe technical analysis formatting with clean separation of concerns.

**Classes**

**`TechnicalIndicatorThresholds`** (class with static constants)
- **Attributes**:
  - `RSI_OVERBOUGHT = 70.0`
  - `RSI_OVERSOLD = 30.0`
  - `ADX_STRONG_TREND = 25.0`
  - `ADX_DEVELOPING_TREND = 20.0`
  - `BOLLINGER_UPPER_BREAK = 1.0`
  - `BOLLINGER_LOWER_BREAK = 0.0`
  - `FRESH_PULSE_MINUTES = 10.0`
  - `MIN_ALIGNMENT_TIMEFRAMES = 3`

**`RSILevel`** (frozen dataclass - value object pattern)
- **Attributes**:
  - `value: float` - RSI indicator value
- **Properties**:
  - `interpretation: str` - OVERBOUGHT/OVERSOLD/NEUTRAL
  - `color: str` - Display color

**`TimeframeData`** (frozen dataclass - value object pattern)
- **Attributes**:
  - `timeframe: str`
  - `trend: str`
  - `signal_strength: int`
  - `rsi: RSILevel`
  - `macd: Dict[str, float]`
  - `bollinger_bands: Dict[str, float]`
  - `adx: Dict[str, float]`
  - `atr: float`
  - `volatility: str`
- **Methods**:
  - `from_dict(tf: str, data: Dict[str, Any]) -> TimeframeData` - Factory method

**`PulseDataFetcher`**
- **Signature**: `class PulseDataFetcher`
- **Description**: Single responsibility - data retrieval only
- **Methods**:
  - `__init__(self, engine)` - Initialize with engine instance
  - `fetch_pulse(self, asset_pair: str) -> Optional[Dict[str, Any]]` - Fetch data from monitoring context or data provider

**`TimeframeTableFormatter`**
- **Signature**: `class TimeframeTableFormatter`
- **Description**: Single responsibility - presentation logic only
- **Methods**:
  - `format_timeframe(self, tf_data: TimeframeData) -> Table` - Create Rich table for timeframe
  - `_get_trend_color(trend: str) -> str` - Static helper
  - `_interpret_macd(macd: Dict[str, float]) -> str` - Static helper
  - `_interpret_bollinger(bbands: Dict[str, float]) -> str` - Static helper
  - `_interpret_adx(adx_data: Dict[str, float]) -> str` - Instance helper with complex logic
  - `_get_volatility_color(volatility: str) -> str` - Static helper

**`CrossTimeframeAnalyzer`**
- **Signature**: `class CrossTimeframeAnalyzer`
- **Description**: Single responsibility - multi-timeframe analysis logic
- **Methods**:
  - `analyze_alignment(self, timeframes: Dict[str, TimeframeData]) -> Dict[str, Any]` - Analyze cross-timeframe trend alignment

**`PulseDisplayService`** (facade pattern)
- **Signature**: `class PulseDisplayService`
- **Description**: Orchestrates fetcher, formatters, and analyzers
- **Methods**:
  - `__init__(self, console: Optional[Console] = None)` - Initialize with optional console
  - `set_fetcher(self, fetcher: PulseDataFetcher)` - Dependency injection
  - `display_pulse(self, asset_pair: str)` - Main facade method orchestrating all components
  - `_display_unavailable_message(self)` - Helper
  - `_display_freshness(self, age_seconds: float)` - Helper
  - `_display_alignment(self, alignment: Dict[str, Any])` - Helper

**Functions**

**`display_pulse_data(engine, asset_pair: str, console: Optional[Console] = None)`**
- **Signature**: `def display_pulse_data(engine, asset_pair: str, console: Optional[Console] = None)`
- **Description**: Public API for displaying multi-timeframe pulse data; creates service, fetcher, and orchestrates display
- **Location**: `pulse_formatter.py:310-330`
- **Dependencies**:
  - All formatter classes above
  - `Console` from `rich.console`

#### `backtest_formatter.py`

Clean professional formatting for backtest results.

**Functions**

**`format_full_results(results, asset_pairs, start_date, end_date, initial_balance)`**
- **Signature**: `def format_full_results(results: Dict[str, Any], asset_pairs: List[str], start_date: str, end_date: str, initial_balance: float) -> None`
- **Description**: Displays complete formatted backtest results with header, summary, stats, asset breakdown, trades, completion message
- **Location**: `backtest_formatter.py:169-196`
- **Dependencies**: Component formatting functions

**`format_single_asset_backtest(metrics, trades, asset_pair, start_date, end_date, initial_balance)`**
- **Signature**: `def format_single_asset_backtest(metrics: Dict[str, Any], trades: List[Dict[str, Any]], asset_pair: str, start_date: str, end_date: str, initial_balance: float) -> None`
- **Description**: Displays single-asset backtest results
- **Location**: `backtest_formatter.py:198-315`
- **Dependencies**: Rich table formatting

Additional helper functions:
- `format_backtest_header()` - Header display
- `format_portfolio_summary()` - Main metrics table
- `format_trading_statistics()` - Trading activity stats
- `format_asset_breakdown()` - Per-asset performance
- `format_recent_trades()` - Recent trades table
- `format_completion_message()` - Summary panel

#### `dashboard_aggregator.py`

Dashboard data collection from all agent subsystems.

**Classes**

**`DashboardDataAggregator`**
- **Signature**: `class DashboardDataAggregator`
- **Description**: Centralizes data collection for live dashboard display
- **Methods**:
  - `__init__(self, agent, engine, trade_monitor, portfolio_memory)` - Initialize with subsystem references
  - `get_agent_status(self) -> Dict[str, Any]` - Agent state, cycle count, daily trades, uptime, kill-switch
  - `get_portfolio_snapshot(self) -> Dict[str, Any]` - Balance, P&L, exposure, leverage, concentration, risk metrics
  - `get_active_trades(self) -> List[Dict[str, Any]]` - Live trades with real-time P&L
  - `get_market_pulse(self) -> List[Dict[str, Any]]` - Watchlist assets with pulse data
  - `get_recent_decisions(self, limit: int = 10) -> List[Dict[str, Any]]` - Recent decision log
  - `get_performance_stats(self, hours: int = 24) -> Dict[str, Any]` - Win rate, total P&L, best/worst trades, streak
  - `_evaluate_risk_limits(self, context: Dict[str, Any]) -> Dict[str, Any]` - Portfolio risk assessment

#### `live_dashboard.py`

Real-time dashboard rendering (structure inferred from imports and usage).

#### `auth_cli.py`

API key management commands.

**Classes**

**`AuthManager`** reference from `finance_feedback_engine.auth`

**Functions**

**`auth_group()`** - Click group for auth commands

Sub-commands:
- `add_api_key(name, key, description)` - Add new API key
- `test_api_key(key, ip)` - Test API key validity
- `list_api_keys()` - List all stored keys
- `disable_api_key(name)` - Revoke key access
- `show_audit_log(limit, hours, failures_only)` - Authentication audit log
- `auth_stats()` - Authentication statistics

---

## Dependencies

### Internal Dependencies (Finance Feedback Engine)

- `finance_feedback_engine.core.FinanceFeedbackEngine` - Main engine facade
- `finance_feedback_engine.agent.config.TradingAgentConfig` - Agent configuration
- `finance_feedback_engine.agent.trading_loop_agent.TradingLoopAgent` - Agent implementation
- `finance_feedback_engine.monitoring.trade_monitor.TradeMonitor` - Live trade monitoring
- `finance_feedback_engine.backtesting.backtester.Backtester` - Single-asset backtesting
- `finance_feedback_engine.backtesting.portfolio_backtester.PortfolioBacktester` - Multi-asset backtesting
- `finance_feedback_engine.backtesting.walk_forward.WalkForwardAnalyzer` - Walk-forward analysis
- `finance_feedback_engine.backtesting.monte_carlo.MonteCarloSimulator` - Monte Carlo simulations
- `finance_feedback_engine.persistence.decision_store.DecisionStore` - Decision storage
- `finance_feedback_engine.dashboard.PortfolioDashboardAggregator`, `display_portfolio_dashboard` - Dashboard
- `finance_feedback_engine.optimization.optuna_optimizer.OptunaOptimizer` - Hyperparameter optimization
- `finance_feedback_engine.monitoring.metrics.init_metrics`, `inc` - Metrics collection
- `finance_feedback_engine.observability.init_tracer`, `context.OTelContextFilter` - Observability
- `finance_feedback_engine.utils.config_loader.load_config` - Configuration with env substitution
- `finance_feedback_engine.utils.config_validator.validate_config_file`, `print_validation_results` - Config validation
- `finance_feedback_engine.utils.validation.standardize_asset_pair` - Asset pair normalization
- `finance_feedback_engine.utils.environment.get_environment_name` - Environment detection
- `finance_feedback_engine.auth.AuthManager` - API key management

### External Dependencies

**Core CLI Framework**
- `click>=8.0` - Command-line interface framework
- `rich>=13.0` - Terminal formatting and tables

**Data & Configuration**
- `pyyaml>=6.0` - YAML parsing
- `packaging>=21.0` - Package version parsing

**Asynchronous Execution**
- `asyncio` (standard library) - Async/await support

**Optimization & Testing**
- `optuna>=3.0` (optional) - Hyperparameter optimization
- `mlflow>=2.0` (optional) - Experiment tracking

**System Tools**
- `subprocess` (standard library) - Execute external commands
- `json` (standard library) - JSON serialization
- `pathlib.Path` (standard library) - File path handling
- `logging` (standard library) - Structured logging
- `re` (standard library) - Regular expressions
- `datetime` (standard library) - Date/time handling

---

## Key Design Patterns

### 1. **Modular Commands Organization**
- Commands separated by domain (`agent.py`, `analysis.py`, `backtest.py`, `trading.py`, `memory.py`, `optimize.py`)
- Each module exports `commands` list for registration
- Main CLI uses `cli.add_command()` to register sub-commands

### 2. **Configuration Precedence (Tiered Loading)**
- `config/config.local.yaml` (environment-specific overrides - highest priority)
- `config/config.yaml` (base defaults)
- Environment variables (via `.env` file substitution)
- Strategic use of `_deep_merge_dicts()` and `_deep_fill_missing()` for merging

### 3. **Interactive vs Programmatic Execution**
- `cli()` function detects `--interactive` flag
- `ctx.obj.get("interactive")` used throughout for interactive-mode decisions
- `start_interactive_session()` enables REPL-like shell experience

### 4. **Separation of Concerns in Formatters**
- **Value Objects**: `RSILevel`, `TimeframeData` - immutable data with behavior
- **Single Responsibility**: `PulseDataFetcher`, `TimeframeTableFormatter`, `CrossTimeframeAnalyzer`
- **Facade Pattern**: `PulseDisplayService` orchestrates all components
- Dependency injection for testability

### 5. **Error Handling & Interactive Fallback**
- `_handle_engine_init_error()` provides interactive recovery in analysis command
- Graceful degradation to mock platform when real platform unavailable
- Rich error messages with actionable guidance

### 6. **Confirmation & Validation Pattern**
- `_confirm_agent_startup()` shows configuration and prompts user
- `_validate_config_on_startup()` fails early on critical config issues
- `config_editor()` guides users through setup with validation

### 7. **Metrics & Observability Integration**
- `inc()` calls track approvals, executions with labels
- `setup_logging()` configures structured JSON logging to `data/logs/`
- `init_tracer()` and `init_metrics()` initialized early in CLI flow
- `OTelContextFilter` correlates logs with traces

---

## Relationships & Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLI Entry Point                          │
│                     main.py::cli()                              │
│  Loads config, initializes logging/tracing/metrics              │
└──────────┬──────────────────────────────────────────────────────┘
           │
    ┌──────┴──────────────────┬──────────────┬─────────────┐
    │                         │              │             │
    v                         v              v             v
 Analysis              Trading Agent      Backtesting   Optimization
 (analysis.py)         (agent.py)         (backtest.py)  (optimize.py)
    │                      │                    │             │
    ├─analyze()            ├─run_agent()        ├─backtest()   └─optimize()
    └─history()            ├─_initialize_agent()│
                           └─_run_live_dash()   ├─portfolio_backtest()
                                                ├─walk_forward()
                                                └─monte_carlo()

Portfolio Memory ← DashboardDataAggregator ← Agent Execution Loop
     ↓                      ↓                         ↓
Learning Report       Live Dashboard            Trade Monitor
(memory.py)         (live_dashboard.py)     (monitoring.py)
```

---

## Code Statistics

| Category | Count |
|----------|-------|
| Main module (`main.py`) functions | 17 |
| Command modules | 8 |
| Formatter/utility modules | 5 |
| Total CLI commands | 35+ |
| Classes defined | 8 (including value objects & facades) |
| Helper functions | 20+ |

---

## Notes

### Threading & Async Behavior
- Agent execution uses `asyncio.run()` for concurrent agent and dashboard tasks
- Dashboard uses `async def` with `asyncio.sleep()` for tiered refresh rates
- Analysis supports both sync and async `engine.analyze_asset()` patterns

### Configuration Management
- Tiered loading enables environment-specific overrides without modifying base config
- `.env` file support via `config_loader` for secrets
- Validation happens early (`_validate_config_on_startup()`) before resource-heavy engine init

### Error Handling Philosophy
- Interactive fallback to mock platform when real platform unavailable (analysis command)
- Early validation prevents downstream errors
- Rich error messages with setup instructions (e.g., Alpha Vantage key setup)
- Path traversal protection in `_save_approval_response()` for security

### Testing Considerations
- `test_core.py` tests command-line functionality
- Mocked engine instances support test isolation
- `DecisionStore` fallback enables testing without full engine initialization
- `console` instances injectable for testing output
