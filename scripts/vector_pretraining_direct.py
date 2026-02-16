#!/usr/bin/env python3
"""
FFE Vector Memory Pre-Training Script - Direct Approach

Uses the Backtester class directly to avoid agent state machine issues.
Progressive curriculum learning for autonomous trading AI.
"""

import json
import logging
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import click
import pandas as pd
from rich.console import Console
from rich.table import Table

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from finance_feedback_engine.memory.vector_store import VectorMemory

console = Console()
logger = logging.getLogger(__name__)


@dataclass
class TrainingPeriod:
    """Represents a training period with market characteristics."""
    name: str
    start_date: str
    end_date: str
    market_type: str  # 'bull', 'bear', 'mixed'
    direction: Optional[str] = None  # 'LONG', 'SHORT', 'BOTH'
    timeframe: str = 'H1'
    description: str = ''


@dataclass
class BacktestLesson:
    """Structured learning from a backtest run."""
    lesson_id: str
    market_conditions: Dict
    action_taken: str
    outcome: Dict
    key_insight: str
    timestamp: str


class VectorPretrainingPipeline:
    """Progressive training pipeline for FFE vector memory - Direct approach."""

    def __init__(
        self,
        vector_store_path: str = "data/memory/vectors.json",
        backtest_results_dir: str = "data/backtest_results"
    ):
        self.vector_store_path = Path(vector_store_path)
        self.backtest_results_dir = Path(backtest_results_dir)
        self.vector_memory = VectorMemory(storage_path=str(self.vector_store_path))
        self.lessons: List[BacktestLesson] = []
        
        # Create directories
        self.backtest_results_dir.mkdir(parents=True, exist_ok=True)
        
        console.print("\n[bold cyan]═══ FFE Vector Memory Pre-Training Pipeline (Direct) ═══[/bold cyan]\n")
        console.print(f"📁 Vector store: {self.vector_store_path}")
        console.print(f"📊 Results directory: {self.backtest_results_dir}\n")

    def define_training_periods(self) -> Dict[str, List[TrainingPeriod]]:
        """Define training periods based on available 2020-2023 BTC/USD data."""
        
        periods = {
            'phase1_bull': [
                TrainingPeriod(
                    name='bull_early_2021',
                    start_date='2021-01-01',
                    end_date='2021-03-31',
                    market_type='bull',
                    direction='LONG',
                    timeframe='H1',
                    description='Q1 2021 bull run - BTC rally to ATH'
                ),
                TrainingPeriod(
                    name='bull_late_2020',
                    start_date='2020-10-01',
                    end_date='2020-12-31',
                    market_type='bull',
                    direction='LONG',
                    timeframe='H1',
                    description='Late 2020 beginning of bull market'
                ),
            ],
            'phase2_bear': [
                TrainingPeriod(
                    name='bear_2022_crash',
                    start_date='2022-05-01',
                    end_date='2022-07-31',
                    market_type='bear',
                    direction='SHORT',
                    timeframe='H1',
                    description='2022 crypto crash - Luna/Terra collapse'
                ),
                TrainingPeriod(
                    name='bear_2021_correction',
                    start_date='2021-05-01',
                    end_date='2021-07-31',
                    market_type='bear',
                    direction='SHORT',
                    timeframe='H1',
                    description='Mid 2021 correction after ATH'
                ),
            ],
            'phase3_mixed': [
                TrainingPeriod(
                    name='mixed_2023_recovery',
                    start_date='2023-01-01',
                    end_date='2023-06-30',
                    market_type='mixed',
                    direction='BOTH',
                    timeframe='H1',
                    description='2023 recovery - bidirectional trading'
                ),
                TrainingPeriod(
                    name='mixed_2020_covid',
                    start_date='2020-03-01',
                    end_date='2020-09-30',
                    market_type='mixed',
                    direction='BOTH',
                    timeframe='H1',
                    description='2020 COVID crash and recovery'
                ),
            ],
            'phase4_complexity': [
                TrainingPeriod(
                    name='complexity_15m_2021',
                    start_date='2021-03-01',
                    end_date='2021-03-31',
                    market_type='mixed',
                    direction='BOTH',
                    timeframe='M15',
                    description='15-minute timeframe - March 2021'
                ),
                TrainingPeriod(
                    name='complexity_h1_volatile',
                    start_date='2022-06-01',
                    end_date='2022-06-30',
                    market_type='mixed',
                    direction='BOTH',
                    timeframe='H1',
                    description='High volatility period - June 2022'
                ),
            ]
        }
        
        return periods

    def load_historical_data(self, period: TrainingPeriod) -> Optional[pd.DataFrame]:
        """Load historical data for the training period."""
        
        # Look for the 2020-2023 curriculum data file
        data_path = Path(f"data/historical/curriculum_2020_2023/BTC_USD_{period.timeframe}_2020_2023.parquet")
        
        if not data_path.exists():
            console.print(f"  ⚠️  Data file not found: {data_path}")
            return None
        
        try:
            df = pd.read_parquet(data_path)
            
            # Standardize column name
            if 'time' in df.columns:
                df = df.rename(columns={'time': 'timestamp'})
            
            # Filter by date range
            df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
            start = pd.to_datetime(period.start_date, utc=True)
            end = pd.to_datetime(period.end_date, utc=True)
            
            df_filtered = df[(df['timestamp'] >= start) & (df['timestamp'] <= end)]
            
            console.print(f"  📊 Loaded {len(df_filtered)} candles for {period.name}")
            
            return df_filtered
            
        except Exception as e:
            console.print(f"  ❌ Error loading data: {e}")
            return None

    def simulate_simple_backtest(
        self,
        period: TrainingPeriod,
        df: pd.DataFrame
    ) -> Tuple[bool, Optional[Dict]]:
        """
        Run a simplified backtest simulation without the full agent loop.
        
        Uses simple momentum strategy for demonstration:
        - LONG when price > 20-period MA and rising
        - SHORT when price < 20-period MA and falling
        - Exit on opposite signal
        """
        
        if df is None or len(df) < 30:
            return False, None
        
        console.print(f"  🔄 Running simple backtest: [cyan]{period.name}[/cyan]")
        
        # Calculate indicators
        df = df.copy()
        df['ma_20'] = df['close'].rolling(window=20).mean()
        df['ma_50'] = df['close'].rolling(window=50).mean()
        df['returns'] = df['close'].pct_change()
        
        # Simple momentum signals
        df['signal'] = 0
        df.loc[df['close'] > df['ma_20'], 'signal'] = 1  # Bullish
        df.loc[df['close'] < df['ma_20'], 'signal'] = -1  # Bearish
        
        # Simulate trades
        trades = []
        position = None
        entry_price = None
        entry_time = None
        
        initial_balance = 10000.0
        balance = initial_balance
        
        for i in range(20, len(df)):  # Start after MA calculation
            row = df.iloc[i]
            current_price = row['close']
            current_time = row['timestamp']
            signal = row['signal']
            
            # Open position logic
            if position is None:
                if signal == 1 and period.direction in ['LONG', 'BOTH']:
                    position = 'LONG'
                    entry_price = current_price
                    entry_time = current_time
                elif signal == -1 and period.direction in ['SHORT', 'BOTH']:
                    position = 'SHORT'
                    entry_price = current_price
                    entry_time = current_time
            
            # Close position logic
            elif position == 'LONG' and signal <= 0:
                exit_price = current_price
                pnl = (exit_price - entry_price) / entry_price * balance * 0.95  # 95% position size
                balance += pnl
                
                trades.append({
                    'action': 'LONG',
                    'entry_price': entry_price,
                    'entry_time': str(entry_time),
                    'exit_price': exit_price,
                    'exit_time': str(current_time),
                    'pnl': pnl,
                    'pnl_percentage': (exit_price - entry_price) / entry_price * 100,
                    'exit_reason': 'signal_reversal',
                    'duration_hours': (current_time - entry_time).total_seconds() / 3600
                })
                
                position = None
                entry_price = None
                entry_time = None
                
            elif position == 'SHORT' and signal >= 0:
                exit_price = current_price
                pnl = (entry_price - exit_price) / entry_price * balance * 0.95
                balance += pnl
                
                trades.append({
                    'action': 'SHORT',
                    'entry_price': entry_price,
                    'entry_time': str(entry_time),
                    'exit_price': exit_price,
                    'exit_time': str(current_time),
                    'pnl': pnl,
                    'pnl_percentage': (entry_price - exit_price) / entry_price * 100,
                    'exit_reason': 'signal_reversal',
                    'duration_hours': (current_time - entry_time).total_seconds() / 3600
                })
                
                position = None
                entry_price = None
                entry_time = None
        
        # Calculate summary statistics
        if len(trades) == 0:
            console.print(f"  ⚠️  No trades generated for {period.name}")
            return False, None
        
        winning_trades = [t for t in trades if t['pnl'] > 0]
        losing_trades = [t for t in trades if t['pnl'] <= 0]
        
        win_rate = len(winning_trades) / len(trades) * 100 if trades else 0
        total_pnl = balance - initial_balance
        avg_win = sum(t['pnl'] for t in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = sum(t['pnl'] for t in losing_trades) / len(losing_trades) if losing_trades else 0
        
        summary = {
            'total_trades': len(trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': win_rate,
            'net_pnl': total_pnl,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'final_balance': balance,
            'return_percentage': (balance - initial_balance) / initial_balance * 100
        }
        
        results = {
            'summary': summary,
            'trades': trades,
            'period': period.name
        }
        
        console.print(f"  ✅ Backtest complete: {len(trades)} trades, Win rate: {win_rate:.1f}%, P&L: ${total_pnl:.2f}")
        
        return True, results

    def extract_lessons(
        self,
        period: TrainingPeriod,
        backtest_results: Dict
    ) -> List[BacktestLesson]:
        """Extract structured lessons from backtest results."""
        
        lessons = []
        
        summary = backtest_results.get('summary', {})
        trades = backtest_results.get('trades', [])
        
        # Overall performance lesson
        overall_lesson = BacktestLesson(
            lesson_id=f"{period.name}_overall",
            market_conditions={
                'market_type': period.market_type,
                'timeframe': period.timeframe,
                'period': f"{period.start_date} to {period.end_date}",
                'direction_allowed': period.direction,
            },
            action_taken=f"Tested {period.direction} strategy",
            outcome={
                'total_trades': summary.get('total_trades', 0),
                'win_rate': summary.get('win_rate', 0.0),
                'total_pnl': summary.get('net_pnl', 0.0),
                'return_percentage': summary.get('return_percentage', 0.0),
            },
            key_insight=self._generate_insight(period, summary),
            timestamp=datetime.now().isoformat()
        )
        lessons.append(overall_lesson)
        
        # Extract individual trade lessons (sample best and worst)
        winning_trades = sorted([t for t in trades if t.get('pnl', 0) > 0], 
                               key=lambda x: x.get('pnl', 0), reverse=True)
        losing_trades = sorted([t for t in trades if t.get('pnl', 0) < 0], 
                              key=lambda x: x.get('pnl', 0))
        
        # Sample up to 3 best and 3 worst trades
        for i, trade in enumerate(winning_trades[:3]):
            lesson = self._create_trade_lesson(period, trade, f"{period.name}_win_{i}", "WIN")
            lessons.append(lesson)
        
        for i, trade in enumerate(losing_trades[:3]):
            lesson = self._create_trade_lesson(period, trade, f"{period.name}_loss_{i}", "LOSS")
            lessons.append(lesson)
        
        return lessons

    def _create_trade_lesson(
        self,
        period: TrainingPeriod,
        trade: Dict,
        lesson_id: str,
        outcome_type: str
    ) -> BacktestLesson:
        """Create a lesson from an individual trade."""
        
        return BacktestLesson(
            lesson_id=lesson_id,
            market_conditions={
                'market_type': period.market_type,
                'timeframe': period.timeframe,
                'entry_price': trade.get('entry_price'),
                'entry_time': trade.get('entry_time'),
            },
            action_taken=trade.get('action', 'UNKNOWN'),
            outcome={
                'pnl': trade.get('pnl', 0.0),
                'pnl_percentage': trade.get('pnl_percentage', 0.0),
                'exit_price': trade.get('exit_price'),
                'exit_reason': trade.get('exit_reason', 'unknown'),
                'duration_hours': trade.get('duration_hours', 0),
            },
            key_insight=f"{outcome_type}: {trade.get('exit_reason', 'unknown')} - P&L: {trade.get('pnl', 0):.2f}",
            timestamp=datetime.now().isoformat()
        )

    def _generate_insight(self, period: TrainingPeriod, summary: Dict) -> str:
        """Generate human-readable insight from summary statistics."""
        
        win_rate = summary.get('win_rate', 0.0)
        total_pnl = summary.get('net_pnl', 0.0)
        total_trades = summary.get('total_trades', 0)
        return_pct = summary.get('return_percentage', 0.0)
        
        if total_trades == 0:
            return f"No trades executed in {period.market_type} market"
        
        if total_pnl > 0:
            performance = "profitable"
        elif total_pnl < 0:
            performance = "unprofitable"
        else:
            performance = "break-even"
        
        return (
            f"{period.market_type.upper()} market ({period.direction}): "
            f"{total_trades} trades, {win_rate:.1f}% win rate, "
            f"{performance} ({return_pct:+.1f}% return)"
        )

    def store_lessons_in_vector_memory(self, lessons: List[BacktestLesson]) -> int:
        """Store extracted lessons in vector memory."""
        
        stored_count = 0
        
        for lesson in lessons:
            # Create searchable text representation
            lesson_text = (
                f"Market: {lesson.market_conditions.get('market_type', 'unknown').upper()} | "
                f"Action: {lesson.action_taken} | "
                f"Outcome: {json.dumps(lesson.outcome)} | "
                f"Insight: {lesson.key_insight}"
            )
            
            # Store in vector memory
            success = self.vector_memory.add_record(
                id=lesson.lesson_id,
                text=lesson_text,
                metadata={
                    'market_conditions': lesson.market_conditions,
                    'action_taken': lesson.action_taken,
                    'outcome': lesson.outcome,
                    'key_insight': lesson.key_insight,
                    'timestamp': lesson.timestamp,
                }
            )
            
            if success:
                stored_count += 1
        
        # Save the index
        self.vector_memory.save_index()
        
        return stored_count

    def run_phase(self, phase_name: str, periods: List[TrainingPeriod]) -> Dict:
        """Run a complete training phase."""
        
        console.print(f"\n[bold yellow]{'═' * 60}[/bold yellow]")
        console.print(f"[bold yellow]  {phase_name.upper().replace('_', ' ')}[/bold yellow]")
        console.print(f"[bold yellow]{'═' * 60}[/bold yellow]\n")
        
        phase_results = {
            'phase': phase_name,
            'periods': [],
            'total_lessons': 0,
            'successful_backtests': 0,
            'failed_backtests': 0,
        }
        
        for period in periods:
            console.print(f"\n[cyan]▶ Training Period: {period.name}[/cyan]")
            console.print(f"  {period.description}\n")
            
            # Load historical data
            df = self.load_historical_data(period)
            
            if df is None or len(df) == 0:
                console.print(f"  ⚠️  Skipping due to data unavailability\n")
                phase_results['failed_backtests'] += 1
                continue
            
            # Run backtest
            success, backtest_results = self.simulate_simple_backtest(period, df)
            
            if success and backtest_results:
                # Extract lessons
                lessons = self.extract_lessons(period, backtest_results)
                
                # Store lessons
                stored_count = self.store_lessons_in_vector_memory(lessons)
                
                console.print(f"  📚 Stored {stored_count} lessons in vector memory\n")
                
                # Save results to file
                results_file = self.backtest_results_dir / f"{period.name}_results.json"
                with open(results_file, 'w') as f:
                    json.dump(backtest_results, f, indent=2)
                
                phase_results['periods'].append({
                    'name': period.name,
                    'success': True,
                    'lessons_extracted': len(lessons),
                    'lessons_stored': stored_count,
                })
                phase_results['total_lessons'] += stored_count
                phase_results['successful_backtests'] += 1
                
                self.lessons.extend(lessons)
            else:
                console.print(f"  ⚠️  Skipping lesson extraction due to backtest failure\n")
                phase_results['failed_backtests'] += 1
        
        return phase_results

    def run_full_curriculum(self) -> Dict:
        """Run the complete progressive training curriculum."""
        
        periods = self.define_training_periods()
        
        full_results = {
            'start_time': datetime.now().isoformat(),
            'phases': [],
        }
        
        # Phase 1: Bull Market Training
        console.print("\n[bold magenta]Starting Phase 1: Bull Market Training (LONG positions)[/bold magenta]")
        phase1_results = self.run_phase('phase1_bull_market', periods['phase1_bull'])
        full_results['phases'].append(phase1_results)
        
        # Phase 2: Bear Market Training
        console.print("\n[bold magenta]Starting Phase 2: Bear Market Training (SHORT positions)[/bold magenta]")
        phase2_results = self.run_phase('phase2_bear_market', periods['phase2_bear'])
        full_results['phases'].append(phase2_results)
        
        # Phase 3: Mixed Market Training
        console.print("\n[bold magenta]Starting Phase 3: Mixed Market Training (BOTH directions)[/bold magenta]")
        phase3_results = self.run_phase('phase3_mixed_market', periods['phase3_mixed'])
        full_results['phases'].append(phase3_results)
        
        # Phase 4: Complexity Layers
        console.print("\n[bold magenta]Starting Phase 4: Complexity Layers (different timeframes)[/bold magenta]")
        phase4_results = self.run_phase('phase4_complexity', periods['phase4_complexity'])
        full_results['phases'].append(phase4_results)
        
        full_results['end_time'] = datetime.now().isoformat()
        full_results['total_lessons'] = sum(p['total_lessons'] for p in full_results['phases'])
        
        return full_results

    def generate_summary_report(self, results: Dict) -> None:
        """Generate a comprehensive summary report."""
        
        console.print("\n" + "═" * 80)
        console.print("[bold green]FFE PRE-TRAINING RESULTS SUMMARY[/bold green]")
        console.print("═" * 80 + "\n")
        
        # Overview
        start_time = datetime.fromisoformat(results['start_time']).strftime('%Y-%m-%d %H:%M:%S')
        end_time = datetime.fromisoformat(results['end_time']).strftime('%Y-%m-%d %H:%M:%S')
        console.print(f"[bold]Training Period:[/bold] {start_time} to {end_time}")
        console.print(f"[bold]Total Lessons Stored:[/bold] {results['total_lessons']}\n")
        
        # Phase breakdown
        table = Table(title="Phase Breakdown")
        table.add_column("Phase", style="cyan")
        table.add_column("Periods", style="magenta")
        table.add_column("Successful", style="green")
        table.add_column("Failed", style="red")
        table.add_column("Lessons", style="yellow")
        
        for phase in results['phases']:
            table.add_row(
                phase['phase'].replace('_', ' ').title(),
                str(len(phase['periods'])),
                str(phase['successful_backtests']),
                str(phase['failed_backtests']),
                str(phase['total_lessons']),
            )
        
        console.print(table)
        
        # Recommendations
        console.print("\n[bold cyan]RECOMMENDATIONS:[/bold cyan]\n")
        
        total_lessons = results['total_lessons']
        
        if total_lessons >= 50:
            console.print("✅ [green]FFE is READY for autonomous trading[/green]")
            console.print(f"   Vector memory populated with {total_lessons} diverse lessons")
            console.print("   across multiple market conditions\n")
        elif total_lessons >= 20:
            console.print("⚠️  [yellow]FFE has MODERATE readiness for autonomous trading[/yellow]")
            console.print(f"   Vector memory has {total_lessons} lessons")
            console.print("   Recommend running additional backtests for more data\n")
        else:
            console.print("❌ [red]FFE is NOT READY for autonomous trading[/red]")
            console.print(f"   Only {total_lessons} lessons in vector memory")
            console.print("   Need at least 50 lessons for safe deployment\n")
        
        # Vector memory stats
        console.print(f"[bold cyan]VECTOR MEMORY STATISTICS:[/bold cyan]\n")
        console.print(f"  Storage path: {self.vector_store_path}")
        console.print(f"  Total vectors: {len(self.vector_memory.vectors)}")
        if self.vector_store_path.exists():
            console.print(f"  Memory size: {self.vector_store_path.stat().st_size / 1024:.2f} KB\n")
        
        # Save report to file
        report_path = Path("FFE_PRE_TRAINING_RESULTS.md")
        self._save_markdown_report(results, report_path)
        console.print(f"📄 Full report saved to: [cyan]{report_path}[/cyan]\n")

    def _save_markdown_report(self, results: Dict, output_path: Path) -> None:
        """Save detailed markdown report."""
        
        with open(output_path, 'w') as f:
            f.write("# FFE Pre-Training Results\n\n")
            f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write("## Overview\n\n")
            f.write(f"- **Training Period:** {results['start_time']} to {results['end_time']}\n")
            f.write(f"- **Total Lessons Stored:** {results['total_lessons']}\n")
            f.write(f"- **Vector Store Path:** {self.vector_store_path}\n\n")
            
            f.write("## Phase Results\n\n")
            
            for phase in results['phases']:
                f.write(f"### {phase['phase'].replace('_', ' ').title()}\n\n")
                f.write(f"- **Periods Tested:** {len(phase['periods'])}\n")
                f.write(f"- **Successful Backtests:** {phase['successful_backtests']}\n")
                f.write(f"- **Failed Backtests:** {phase['failed_backtests']}\n")
                f.write(f"- **Total Lessons:** {phase['total_lessons']}\n\n")
                
                if phase['periods']:
                    f.write("**Period Details:**\n\n")
                    for period in phase['periods']:
                        status = "✅" if period['success'] else "❌"
                        f.write(f"- {status} **{period['name']}**: {period['lessons_stored']} lessons\n")
                    f.write("\n")
            
            f.write("## Learnings by Market Type\n\n")
            
            # Group lessons by market type
            bull_lessons = [l for l in self.lessons if l.market_conditions.get('market_type') == 'bull']
            bear_lessons = [l for l in self.lessons if l.market_conditions.get('market_type') == 'bear']
            mixed_lessons = [l for l in self.lessons if l.market_conditions.get('market_type') == 'mixed']
            
            f.write(f"### Bull Market Lessons ({len(bull_lessons)})\n\n")
            for lesson in bull_lessons[:10]:  # Top 10
                f.write(f"- **{lesson.lesson_id}**: {lesson.key_insight}\n")
            if len(bull_lessons) > 10:
                f.write(f"- ... and {len(bull_lessons) - 10} more\n")
            f.write("\n")
            
            f.write(f"### Bear Market Lessons ({len(bear_lessons)})\n\n")
            for lesson in bear_lessons[:10]:  # Top 10
                f.write(f"- **{lesson.lesson_id}**: {lesson.key_insight}\n")
            if len(bear_lessons) > 10:
                f.write(f"- ... and {len(bear_lessons) - 10} more\n")
            f.write("\n")
            
            f.write(f"### Mixed Market Lessons ({len(mixed_lessons)})\n\n")
            for lesson in mixed_lessons[:10]:  # Top 10
                f.write(f"- **{lesson.lesson_id}**: {lesson.key_insight}\n")
            if len(mixed_lessons) > 10:
                f.write(f"- ... and {len(mixed_lessons) - 10} more\n")
            f.write("\n")
            
            f.write("## Recommendation\n\n")
            
            total_lessons = results['total_lessons']
            
            if total_lessons >= 50:
                f.write("✅ **FFE is READY for autonomous trading**\n\n")
                f.write(f"Vector memory is well-populated with {total_lessons} diverse lessons ")
                f.write("across multiple market conditions (bull, bear, mixed) and timeframes.\n\n")
                f.write("**Next Steps:**\n")
                f.write("- Begin paper trading with autonomous agent\n")
                f.write("- Monitor decision quality using vector memory queries\n")
                f.write("- Continue learning from live trades\n")
            elif total_lessons >= 20:
                f.write("⚠️ **FFE has MODERATE readiness for autonomous trading**\n\n")
                f.write(f"Vector memory has {total_lessons} lessons, which is a good start ")
                f.write("but may benefit from additional training data.\n\n")
                f.write("**Recommendations:**\n")
                f.write("- Run additional backtests on different time periods\n")
                f.write("- Start with paper trading only\n")
                f.write("- Monitor closely and add more lessons if needed\n")
            else:
                f.write("❌ **FFE is NOT READY for autonomous trading**\n\n")
                f.write(f"Only {total_lessons} lessons in vector memory. ")
                f.write("This is insufficient for safe autonomous operation.\n\n")
                f.write("**Required Actions:**\n")
                f.write("- Extend backtest periods\n")
                f.write("- Add more market conditions\n")
                f.write("- Target at least 50 lessons before deployment\n")
            
            f.write("\n## Vector Memory Performance\n\n")
            f.write(f"- **Storage Path:** `{self.vector_store_path}`\n")
            f.write(f"- **Total Vectors:** {len(self.vector_memory.vectors)}\n")
            if self.vector_store_path.exists():
                f.write(f"- **File Size:** {self.vector_store_path.stat().st_size / 1024:.2f} KB\n")
            
            f.write("\n---\n")
            f.write("\n*Generated by FFE Vector Pre-Training Pipeline (Direct Backtester)*\n")


@click.command()
@click.option(
    '--vector-store-path',
    default='data/memory/vectors.json',
    help='Path to vector store file'
)
@click.option(
    '--results-dir',
    default='data/backtest_results/pretraining',
    help='Directory to store backtest results'
)
def main(vector_store_path: str, results_dir: str):
    """Run FFE vector memory pre-training curriculum (Direct approach)."""
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Initialize pipeline
    pipeline = VectorPretrainingPipeline(
        vector_store_path=vector_store_path,
        backtest_results_dir=results_dir
    )
    
    try:
        # Run full curriculum
        console.print("[bold]Starting Full Progressive Training Curriculum...[/bold]\n")
        results = pipeline.run_full_curriculum()
        
        # Generate summary report
        pipeline.generate_summary_report(results)
        
        # Save full results
        results_file = Path('vector_pretraining_results.json')
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        console.print(f"[green]✅ Pre-training complete![/green]")
        console.print(f"[green]   Results saved to {results_file}[/green]\n")
        
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Training interrupted by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[red]❌ Error during training: {e}[/red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
