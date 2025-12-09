#!/usr/bin/env python3
"""
Chunked Portfolio Backtest Runner - 2025 Full Year

Runs quarterly backtests (Q1, Q2, Q3, Q4) for multi-asset portfolios,
accumulating learning/memory across chunks.

Stores memories persistently:
- Portfolio outcomes: data/memory/outcome_*.json
- Performance snapshots: data/memory/snapshot_*.json
- Vector memory: data/memory/vectors.pkl (pickle format)
- Provider performance: data/memory/provider_performance.json
- Regime performance: data/memory/regime_performance.json

Memory persists across backtest chunks, enabling cross-quarter learning.
"""

import subprocess
import json
import logging
import os
import re
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

@dataclass
class BacktestChunk:
    """Single quarterly backtest period."""
    quarter: int
    start_date: str
    end_date: str

    def __str__(self) -> str:
        return f"Q{self.quarter} 2025 ({self.start_date} → {self.end_date})"


class ChunkedBacktestRunner:
    """Execute backtests in quarterly chunks with persistent memory."""

    # Default subprocess timeout (30 minutes per quarter)
    # Override via BACKTEST_TIMEOUT_SECONDS env var or timeout parameter
    DEFAULT_BACKTEST_TIMEOUT = 1800

    # 2025 Quarterly breakdown
    QUARTERS = [
        BacktestChunk(1, "2025-01-01", "2025-03-31"),
        BacktestChunk(2, "2025-04-01", "2025-06-30"),
        BacktestChunk(3, "2025-07-01", "2025-09-30"),
        BacktestChunk(4, "2025-10-01", "2025-12-31"),
    ]

    def __init__(
        self,
        assets: List[str],
        initial_balance: float = 10000,
        correlation_threshold: float = 0.7,
        max_positions: int = None,
        timeout_seconds: int = None,
        year: int = 2025
    ):
        """
        Initialize chunked backtest runner.

        Args:
            assets: List of trading pairs (e.g., ["BTCUSD", "ETHUSD", "EURUSD"])
            initial_balance: Starting portfolio balance
            correlation_threshold: Correlation threshold for position sizing
            max_positions: Max concurrent positions (default: len(assets))
            timeout_seconds: Per-quarter subprocess timeout in seconds.
                            Defaults to BACKTEST_TIMEOUT_SECONDS env var or DEFAULT_BACKTEST_TIMEOUT (1800s).
            year: Year for backtest (default: 2025)
        """
        self.assets = assets
        self.initial_balance = initial_balance
        self.correlation_threshold = correlation_threshold
        self.max_positions = max_positions or len(assets)
        self.year = year

        # Update QUARTERS to use configured year
        self.QUARTERS = [
            BacktestChunk(1, f"{year}-01-01", f"{year}-03-31"),
            BacktestChunk(2, f"{year}-04-01", f"{year}-06-30"),
            BacktestChunk(3, f"{year}-07-01", f"{year}-09-30"),
            BacktestChunk(4, f"{year}-10-01", f"{year}-12-31"),
        ]

        # Load timeout from parameter, env var, or default (1800s = 30 min)
        if timeout_seconds is not None:
            self.timeout_seconds = timeout_seconds
        else:
            env_timeout = os.environ.get('BACKTEST_TIMEOUT_SECONDS')
            self.timeout_seconds = int(env_timeout) if env_timeout else self.DEFAULT_BACKTEST_TIMEOUT

        # Output paths
        self.results_dir = Path("data/backtest_results")
        self.results_dir.mkdir(parents=True, exist_ok=True)

        self.memory_dir = Path("data/memory")
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"ChunkedBacktestRunner initialized:")
        logger.info(f"  Assets: {', '.join(assets)}")
        logger.info(f"  Initial Balance: ${initial_balance:,.2f}")
        logger.info(f"  Correlation Threshold: {correlation_threshold}")
        logger.info(f"  Per-Quarter Timeout: {self.timeout_seconds}s ({self.timeout_seconds / 60:.0f} minutes)")
        logger.info(f"  Memory Path: {self.memory_dir}")

    def run_full_year(self) -> Dict[str, Any]:
        """
        Execute quarterly backtests for full 2025 year.

        Returns:
            Aggregated results across all quarters with cumulative metrics
        """
        logger.info("=" * 80)
        logger.info("STARTING FULL YEAR 2025 CHUNKED BACKTEST")
        logger.info("=" * 80)
        logger.info(f"Assets: {', '.join(self.assets)}")
        logger.info(f"Period: Q1 → Q4 2025 (4 quarterly chunks)")
        logger.info(f"Memory persists across chunks: {self.memory_dir}")
        logger.info("")

        all_results = []
        cumulative_metrics = {
            "total_trades": 0,
            "winning_trades": 0,
            "total_pnl": 0,
            "quarterly_returns": []
        }

        # Run each quarter
        for chunk in self.QUARTERS:
            logger.info("")
            logger.info("=" * 80)
            logger.info(f"Running {chunk}")
            logger.info("=" * 80)

            result = self._run_backtest_chunk(chunk)

            if result:
                all_results.append(result)

                # Accumulate metrics
                cumulative_metrics["total_trades"] += result.get("total_trades", 0)
                cumulative_metrics["winning_trades"] += result.get("winning_trades", 0)
                cumulative_metrics["total_pnl"] += result.get("total_pnl", 0)
                cumulative_metrics["quarterly_returns"].append({
                    "quarter": f"Q{chunk.quarter}",
                    "return_pct": result.get("return_pct", 0)
                })

                # Log memory status after each quarter
                self._log_memory_status()

        # Calculate summary
        summary = self._calculate_summary(all_results, cumulative_metrics)

        logger.info("")
        logger.info("=" * 80)
        logger.info("FULL YEAR BACKTEST COMPLETE")
        logger.info("=" * 80)
        self._print_summary(summary)

        # Save summary to file
        self._save_summary(summary)

        return summary

    def _run_backtest_chunk(self, chunk: BacktestChunk) -> Dict[str, Any]:
        """Execute single quarterly backtest."""

        # Build CLI command
        cmd = [
            "python", "main.py", "portfolio-backtest",
            *self.assets,
            "--start", chunk.start_date,
            "--end", chunk.end_date,
            "--initial-balance", str(self.initial_balance),
            "--correlation-threshold", str(self.correlation_threshold),
            "--max-positions", str(self.max_positions)
        ]

        logger.info(f"Command: {' '.join(cmd)}")
        logger.info(f"Memory state: Persistent (vectors.pkl + outcome_*.json)")

        try:
            # Run backtest - note that portfolio memory persists across runs
            result = subprocess.run(
                cmd,
                cwd=Path(__file__).parent,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds
            )

            if result.returncode != 0:
                logger.error(f"Backtest failed for {chunk}:")
                logger.error(result.stderr)
                return None

            # Parse output (extract metrics from final table)
            metrics = self._parse_backtest_output(result.stdout, chunk)

            # Log results
            logger.info(f"✓ {chunk} complete")
            logger.info(f"  Return: {metrics.get('return_pct', 0):.2f}%")
            logger.info(f"  Trades: {metrics.get('total_trades', 0)}")
            logger.info(f"  Win Rate: {metrics.get('win_rate', 0):.1f}%")
            logger.info(f"  Sharpe: {metrics.get('sharpe_ratio', 0):.2f}")

            return metrics

        except subprocess.TimeoutExpired:
            logger.error(f"Backtest timeout for {chunk} (>{self.timeout_seconds}s / {self.timeout_seconds / 60:.0f} min)")
            return None
        except Exception as e:
            logger.error(f"Backtest error for {chunk}: {e}")
            return None

    def _parse_trade_history(self, output: str) -> List[Dict[str, Any]]:
        """Parses the trade history table from the backtest output."""
        trade_history: List[Dict[str, Any]] = []
        lines = output.splitlines()

        try:
            # Find the header of the trade history table
            header_index = -1
            for i, line in enumerate(lines):
                if "┃" in line and "ID" in line and "Asset" in line and "PNL" in line:
                    header_index = i
                    break

            if header_index == -1:
                self.logger.info("Trade history table not found in output.")
                return []

            header_line = lines[header_index]
            # Strip ANSI color codes
            header_line = re.sub(r'\x1b\[[0-9;]*m', '', header_line)
            headers = [h.strip().lower().replace(' ', '_') for h in header_line.split('┃')][1:-1]

            # Data rows start after the header separator line (e.g., ┡━━━━... or ├─────...)
            for line in lines[header_index + 2:]:
                if '└' in line:  # End of table
                    break
                if '│' in line:
                    # Strip ANSI color codes from data row
                    line = re.sub(r'\x1b\[[0-9;]*m', '', line)
                    values = [v.strip() for v in line.split('│')][1:-1]

                    if len(values) == len(headers):
                        trade = dict(zip(headers, values))
                        try:
                            # Perform type conversion
                            trade['id'] = int(trade['id'])
                            trade['entry_price'] = float(trade['entry_price'])
                            trade['exit_price'] = float(trade['exit_price'])
                            trade['amount'] = float(trade['amount'])
                            trade['pnl'] = float(trade['pnl'])
                            trade['fees'] = float(trade['fees'])
                            trade_history.append(trade)
                        except (ValueError, KeyError) as e:
                            self.logger.warning(f"Could not parse trade row: '{line}'. Error: {e}")
                            continue
        except Exception as e:
            self.logger.error(f"An error occurred while parsing trade history: {e}")

        return trade_history

    def _parse_backtest_output(self, output: str, chunk: BacktestChunk) -> Dict[str, Any]:
        """
        Parse backtest CLI output to extract metrics.

        NOTE: PnL Semantics:
        - realized_pnl: Profit/loss from closed/executed trades (requires trades to be completed)
        - unrealized_pnl: Mark-to-market loss/gain from equity curve changes (includes holdings change)
        - total_pnl: Sum of realized_pnl + unrealized_pnl = final_value - initial_balance

        When total_trades=0 but total_pnl<0, the loss is entirely unrealized (mark-to-market),
        indicating price movements without corresponding trade execution.
        """

        # Default metrics
        metrics = {
            "quarter": f"Q{chunk.quarter}",
            "start_date": chunk.start_date,
            "end_date": chunk.end_date,
            "initial_balance": self.initial_balance,
            "final_value": self.initial_balance,
            "return_pct": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
            "total_trades": 0,
            "completed_trades": 0,
            "win_rate": 0.0,
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "total_pnl": 0.0,
            "winning_trades": 0,
            "trade_history": []
        }

        try:
            # Parse Final Value: Extract dollar amount using regex
            final_value_match = re.search(r'Final Value.*?\$([0-9,]+\.?\d*)', output)
            if final_value_match:
                try:
                    metrics["final_value"] = float(final_value_match.group(1).replace(',', ''))
                except ValueError:
                    logger.debug(f"Failed to parse Final Value: {final_value_match.group(1)}")

            # Parse Total Return percentage
            total_return_match = re.search(r'Total Return.*?([-+]?\d+\.?\d*)%', output)
            if total_return_match:
                try:
                    metrics["return_pct"] = float(total_return_match.group(1))
                except ValueError:
                    logger.debug(f"Failed to parse Total Return: {total_return_match.group(1)}")

            # Parse Sharpe Ratio
            sharpe_match = re.search(r'Sharpe Ratio.*?([-+]?\d+\.?\d*)', output)
            if sharpe_match:
                try:
                    metrics["sharpe_ratio"] = float(sharpe_match.group(1))
                except ValueError:
                    logger.debug(f"Failed to parse Sharpe Ratio: {sharpe_match.group(1)}")

            # Parse Max Drawdown percentage
            drawdown_match = re.search(r'Max Drawdown.*?([-+]?\d+\.?\d*)%', output)
            if drawdown_match:
                try:
                    metrics["max_drawdown"] = float(drawdown_match.group(1))
                except ValueError:
                    logger.debug(f"Failed to parse Max Drawdown: {drawdown_match.group(1)}")

            # Parse Total Trades (integer)
            total_trades_match = re.search(r'Total Trades.*?(\d+)', output)
            if total_trades_match:
                try:
                    metrics["total_trades"] = int(total_trades_match.group(1))
                except ValueError:
                    logger.debug(f"Failed to parse Total Trades: {total_trades_match.group(1)}")

            # Parse Completed Trades (integer)
            completed_trades_match = re.search(r'Completed Trades.*?(\d+)', output)
            if completed_trades_match:
                try:
                    metrics["completed_trades"] = int(completed_trades_match.group(1))
                except ValueError:
                    logger.debug(f"Failed to parse Completed Trades: {completed_trades_match.group(1)}")

            # Parse Win Rate percentage
            win_rate_match = re.search(r'Win Rate.*?([-+]?\d+\.?\d*)%', output)
            if win_rate_match:
                try:
                    metrics["win_rate"] = float(win_rate_match.group(1))
                except ValueError:
                    logger.debug(f"Failed to parse Win Rate: {win_rate_match.group(1)}")

        except KeyboardInterrupt:
            raise
        except GeneratorExit:
            raise
        except Exception as e:
            logger.debug(f"Unexpected error during output parsing for {chunk}: {e}")

        # Parse trade history
        metrics["trade_history"] = self._parse_trade_history(output)
        
        # Calculate derived metrics
        metrics["total_pnl"] = metrics["final_value"] - metrics["initial_balance"]

        # Distinguish realized vs unrealized PnL
        if metrics["trade_history"]:
            realized_pnl = sum(trade.get("pnl", 0) for trade in metrics["trade_history"])
            metrics["realized_pnl"] = realized_pnl
            metrics["unrealized_pnl"] = metrics["total_pnl"] - realized_pnl
        else:
            metrics["realized_pnl"] = 0.0
            metrics["unrealized_pnl"] = metrics["total_pnl"]

        if metrics["completed_trades"] > 0:
            # Re-calculate winning trades from history if available
            if metrics["trade_history"]:
                winning_trades = sum(1 for trade in metrics["trade_history"] if trade.get("pnl", 0) > 0)
                metrics["winning_trades"] = winning_trades
                if metrics["completed_trades"] > 0:
                     metrics["win_rate"] = (winning_trades / metrics["completed_trades"]) * 100
            else: # Fallback to parsed win rate
                metrics["winning_trades"] = int(metrics["completed_trades"] * metrics["win_rate"] / 100)
        else:
             metrics["win_rate"] = 0.0
             metrics["winning_trades"] = 0

        return metrics

    def _log_memory_status(self) -> None:
        """Log current memory usage and file counts."""

        # Count outcome files
        outcome_files = list(self.memory_dir.glob("outcome_*.json"))
        snapshot_files = list(self.memory_dir.glob("snapshot_*.json"))
        vectors_file = self.memory_dir / "vectors.pkl"

        logger.info(f"Memory Status:")
        logger.info(f"  Outcomes: {len(outcome_files)} files")
        logger.info(f"  Snapshots: {len(snapshot_files)} files")
        if vectors_file.exists():
            size_mb = vectors_file.stat().st_size / 1024 / 1024
            logger.info(f"  Vectors: ✓ ({size_mb:.2f} MB)")
        else:
            logger.info(f"  Vectors: ✗ (not created yet)")

        # Check provider/regime performance files
        provider_perf = self.memory_dir / "provider_performance.json"
        regime_perf = self.memory_dir / "regime_performance.json"
        logger.info(f"  Provider Perf: {'✓' if provider_perf.exists() else '✗'}")
        logger.info(f"  Regime Perf: {'✓' if regime_perf.exists() else '✗'}")

    def _calculate_summary(
        self,
        quarterly_results: List[Dict[str, Any]],
        cumulative: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate full-year summary metrics."""

        if not quarterly_results:
            return {"error": "No quarterly results available"}

        # Recalculate quarterly values with proper chaining (each quarter compounds from previous)
        # Also distinguish realized PnL (from executed trades) from unrealized PnL (mark-to-market)
        current_balance = self.initial_balance
        for q in quarterly_results:
            q_return = q["return_pct"] / 100.0
            q["initial_balance"] = current_balance
            q["final_value"] = current_balance * (1 + q_return)

            # Calculate realized vs unrealized PnL
            realized_pnl = sum(t.get("pnl", 0) for t in q.get("trade_history", []) if "pnl" in t)
            total_pnl = q["final_value"] - q["initial_balance"]
            unrealized_pnl = total_pnl - realized_pnl

            q["realized_pnl"] = realized_pnl
            q["unrealized_pnl"] = unrealized_pnl
            q["total_pnl"] = total_pnl
            current_balance = q["final_value"]

        quarterly_returns = [r["return_pct"] for r in quarterly_results]
        quarterly_sharpes = [r["sharpe_ratio"] for r in quarterly_results if r["sharpe_ratio"] != 0]
        quarterly_drawdowns = [r["max_drawdown"] for r in quarterly_results]

        # Full year return (geometric)
        full_year_value = self.initial_balance
        for q in quarterly_results:
            q_return = q["return_pct"] / 100.0
            full_year_value *= (1 + q_return)
        full_year_return = ((full_year_value - self.initial_balance) / self.initial_balance) * 100

        # Annualized Sharpe (average of quarterly, annualized)
        avg_quarterly_sharpe = sum(quarterly_sharpes) / len(quarterly_sharpes) if quarterly_sharpes else 0
        annualized_sharpe = avg_quarterly_sharpe * (4 ** 0.5)  # Annualize from quarterly

        # Calculate annual realized vs unrealized PnL
        total_realized_pnl = sum(q.get("realized_pnl", 0) for q in quarterly_results)
        total_unrealized_pnl = sum(q.get("unrealized_pnl", 0) for q in quarterly_results)

        summary = {
            "period": f"Full Year {self.year}",
            "assets": self.assets,
            "initial_balance": self.initial_balance,
            "final_balance": full_year_value,
            "total_return_pct": full_year_return,
            "annualized_sharpe": annualized_sharpe,
            "max_quarterly_drawdown": max(quarterly_drawdowns) if quarterly_drawdowns else 0,
            "total_trades": cumulative["total_trades"],
            "total_completed_trades": sum(r.get("completed_trades", 0) for r in quarterly_results),
            "total_winning_trades": cumulative["winning_trades"],
            "overall_win_rate": (cumulative["winning_trades"] / cumulative["total_trades"] * 100) if cumulative["total_trades"] > 0 else 0,
            "realized_pnl": total_realized_pnl,
            "unrealized_pnl": total_unrealized_pnl,
            "total_pnl": full_year_value - self.initial_balance,
            "quarterly_breakdown": quarterly_results,
            "memory_persistence": {
                "outcomes_stored": len(list(self.memory_dir.glob("outcome_*.json"))),
                "snapshots_stored": len(list(self.memory_dir.glob("snapshot_*.json"))),
                "vectors_file": str(self.memory_dir / "vectors.pkl"),
                "learning_accumulated_across_quarters": True
            }
        }

        return summary

    def _print_summary(self, summary: Dict[str, Any]) -> None:
        """Print formatted summary to console."""

        # Handle error cases
        if "error" in summary:
            print("\n" + "=" * 80)
            print(f"FULL YEAR {self.year} BACKTEST SUMMARY")
            print("=" * 80)
            print(f"ERROR: {summary['error']}")
            return

        print("\n" + "=" * 80)
        print(f"FULL YEAR {self.year} BACKTEST SUMMARY")
        print("=" * 80)
        print(f"\nAssets: {', '.join(summary.get('assets', []))}")
        print(f"Period: {summary.get('period', 'N/A')}")
        print(f"Initial Balance: ${summary.get('initial_balance', 0):,.2f}")
        print(f"Final Balance: ${summary.get('final_balance', 0):,.2f}")
        print(f"Total Return: {summary.get('total_return_pct', 0):.2f}%")
        print(f"Annualized Sharpe: {summary.get('annualized_sharpe', 0):.2f}")
        print(f"Max Quarterly Drawdown: {summary.get('max_quarterly_drawdown', 0):.2f}%")
        print(f"\nTrading Statistics:")
        print(f"  Total Trades: {summary.get('total_trades', 0)}")
        print(f"  Completed Trades: {summary.get('total_completed_trades', 0)}")
        print(f"  Winning Trades: {summary.get('total_winning_trades', 0)}")
        print(f"  Overall Win Rate: {summary.get('overall_win_rate', 0):.1f}%")
        print(f"  Total P&L: ${summary.get('total_pnl', 0):,.2f}")

        print(f"\nMemory Persistence (Accumulated Learning):")
        mem = summary.get('memory_persistence', {})
        print(f"  Outcomes stored: {mem.get('outcomes_stored', 0)}")
        print(f"  Snapshots stored: {mem.get('snapshots_stored', 0)}")
        print(f"  Vector memory: {mem.get('vectors_file', 'N/A')}")
        print(f"  Cross-quarter learning: {mem.get('learning_accumulated_across_quarters', False)}")

        print(f"\nQuarterly Breakdown:")
        for q in summary.get('quarterly_breakdown', []):
            print(f"\n  Q{q.get('quarter', '?')} {self.year}:")
            print(f"    Return: {q.get('return_pct', 0):.2f}%")
            print(f"    Sharpe: {q.get('sharpe_ratio', 0):.2f}")
            print(f"    Drawdown: {q.get('max_drawdown', 0):.2f}%")
            print(f"    Trades: {q.get('total_trades', 0)}")
            print(f"    Win Rate: {q.get('win_rate', 0):.1f}%")

        print("\n" + "=" * 80)

    def _save_summary(self, summary: Dict[str, Any]) -> None:
        """Save summary to JSON file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = self.results_dir / f"full_year_summary_{timestamp}.json"

        try:
            with open(filename, 'w') as f:
                json.dump(summary, f, indent=2)
            logger.info(f"Summary saved to {filename}")
        except Exception as e:
            logger.error(f"Failed to save summary: {e}")


if __name__ == "__main__":
    # Run full year backtest with 3 assets
    runner = ChunkedBacktestRunner(
        assets=["BTCUSD", "ETHUSD", "EURUSD"],
        initial_balance=10000,
        correlation_threshold=0.7,
        max_positions=3
    )

    # Execute quarterly backtests (memories persist across quarters)
    full_year_results = runner.run_full_year()
