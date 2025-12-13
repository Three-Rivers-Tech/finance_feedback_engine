# CLI Command Extraction Mapping - Critical Components

## Agent Commands (agent.py)

### Helper Functions (MUST include):
1. **`_initialize_agent`** (lines 2020-2104)
   - Initializes TradingLoopAgent with config
   - Handles autonomous mode setup
   - Creates and starts TradeMonitor
   - Dependencies: TradingLoopAgent, TradingAgentConfig, TradeMonitor

2. **`_run_live_market_view`** (lines 2106-2164)
   - Async function for live market pulse display
   - Nested function: `build_table()`
   - Dependencies: rich.live.Live, rich.table.Table

### Commands:
3. **`run-agent`** command (lines 2165-2270)
   - Decorator with 5 options: max-drawdown, take-profit, stop-loss, setup, autonomous, asset-pairs
   - Calls `_initialize_agent` and `_run_live_market_view`
   - Async/await event loop management
   - KeyboardInterrupt handling

4. **`monitor`** group command (lines 1809-1948)
   - Group decorator @ cli.group()
   - 3 subcommands:
     - `start` (lines 1820-1830)
     - `status` (lines 1832-1843)
     - `metrics` (lines 1845-1948) - LARGEST, includes Table rendering

### Required Imports for agent.py:
```python
import click
import json
import asyncio
import time
import logging
import traceback
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.live import Live

from finance_feedback_engine.core import FinanceFeedbackEngine
from finance_feedback_engine.agent.trading_loop_agent import TradingLoopAgent
from finance_feedback_engine.agent.config import TradingAgentConfig
from finance_feedback_engine.monitoring.trade_monitor import TradeMonitor
```

---

## Backtest Commands (backtest.py)

### Commands:
1. **`backtest`** (lines ~1505-1714)
   - Decorator with ~10 options (initial-balance, fee-percentage, etc.)
   - Date validation logic
   - Backtester initialization
   - Results saving to JSON
   - Uses: finance_feedback_engine.cli.backtest_formatter.format_single_asset_backtest

2. **`portfolio-backtest`** (lines 1716-1807)
   - Multi-asset backtest
   - Decorator with 5 options
   - Uses: PortfolioBacktester, format_full_results

3. **`walk-forward`** (lines 2276-2401)
   - Advanced analysis with overfitting detection
   - Decorator with 5 options
   - Complex window calculation logic
   - Uses: WalkForwardAnalyzer

4. **`monte-carlo`** (lines 2403-2500)
   - Monte Carlo simulation
   - Decorator with 5 options
   - Confidence intervals and VaR calculation
   - Uses: MonteCarloSimulator

### Required Imports for backtest.py:
```python
import click
import json
import logging
import traceback
from datetime import datetime
from pathlib import Path
from rich.console import Console
from rich.table import Table

from finance_feedback_engine.core import FinanceFeedbackEngine
from finance_feedback_engine.backtesting.backtester import Backtester
from finance_feedback_engine.backtesting.portfolio_backtester import PortfolioBacktester
from finance_feedback_engine.backtesting.walk_forward import WalkForwardAnalyzer
from finance_feedback_engine.backtesting.monte_carlo import MonteCarloSimulator
from finance_feedback_engine.utils.validation import standardize_asset_pair
from finance_feedback_engine.cli.backtest_formatter import format_single_asset_backtest, format_full_results
```

---

## Extraction Strategy

1. ✅ Extract agent.py with ALL helper functions first
2. ✅ Extract backtest.py with ALL 4 commands
3. ✅ Update main.py imports
4. ✅ Remove old code from main.py with comments
5. ✅ Register commands via cli.add_command()
6. ✅ Test EVERY command with --help
7. ✅ Verify compilation

## Critical Notes

- ⚠️ **DO NOT MODIFY** any logic - extract exactly as-is
- ⚠️ **PRESERVE** all comments, error handling, logging
- ⚠️ **TEST THOROUGHLY** after extraction
- ⚠️ run-agent and backtest are CRITICAL to repository functionality
