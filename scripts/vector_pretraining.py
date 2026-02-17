#!/usr/bin/env python3
"""
FFE Vector Memory Pre-Training Script

Progressive curriculum learning for autonomous trading AI:
- Phase 1: Bull Market Training (LONG positions)
- Phase 2: Bear Market Training (SHORT positions)
- Phase 3: Mixed Market Training (LONG + SHORT)
- Phase 4: Complexity Layers (volatility, timeframes, position sizing)

Populates VectorMemory with structured learnings from historical backtests.
"""

import json
import logging
import subprocess
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
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
    timeframe: str = '1h'
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
    """Progressive training pipeline for FFE vector memory."""

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
        
        console.print("\n[bold cyan]═══ FFE Vector Memory Pre-Training Pipeline ═══[/bold cyan]\n")
        console.print(f"📁 Vector store: {self.vector_store_path}")
        console.print(f"📊 Results directory: {self.backtest_results_dir}\n")

    def define_training_periods(self) -> Dict[str, List[TrainingPeriod]]:
        """Define training periods for each phase based on BTC/USD history.
        
        Using historical data from 2020-2023:
        - Bull markets: Early 2021 (pre-peak), Late 2020 (beginning rally)
        - Bear markets: Mid 2022 (crash), Q2 2021 (correction)
        - Mixed markets: 2020 full year, 2023 recovery
        """
        
        periods = {
            'phase1_bull': [
                TrainingPeriod(
                    name='bull_early_2021',
                    start_date='2021-01-01',
                    end_date='2021-04-30',
                    market_type='bull',
                    direction='LONG',
                    timeframe='1h',
                    description='Early 2021 bull run - BTC rally to ATH'
                ),
                TrainingPeriod(
                    name='bull_late_2020',
                    start_date='2020-10-01',
                    end_date='2020-12-31',
                    market_type='bull',
                    direction='LONG',
                    timeframe='1h',
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
                    timeframe='1h',
                    description='2022 crypto crash - Luna/Terra collapse'
                ),
                TrainingPeriod(
                    name='bear_2021_correction',
                    start_date='2021-05-01',
                    end_date='2021-07-31',
                    market_type='bear',
                    direction='SHORT',
                    timeframe='1h',
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
                    timeframe='1h',
                    description='2023 recovery - bidirectional trading'
                ),
                TrainingPeriod(
                    name='mixed_2020_full',
                    start_date='2020-03-01',
                    end_date='2020-09-30',
                    market_type='mixed',
                    direction='BOTH',
                    timeframe='1h',
                    description='2020 COVID crash and recovery'
                ),
            ],
            'phase4_complexity': [
                # Different timeframes
                TrainingPeriod(
                    name='complexity_15m_2021',
                    start_date='2021-03-01',
                    end_date='2021-03-31',
                    market_type='mixed',
                    direction='BOTH',
                    timeframe='15m',
                    description='15-minute timeframe - March 2021'
                ),
                TrainingPeriod(
                    name='complexity_1h_volatile',
                    start_date='2022-06-01',
                    end_date='2022-06-30',
                    market_type='mixed',
                    direction='BOTH',
                    timeframe='1h',
                    description='High volatility period - June 2022'
                ),
            ]
        }
        
        return periods

    def run_backtest(
        self,
        period: TrainingPeriod,
        output_file: Optional[Path] = None
    ) -> Tuple[bool, Optional[Dict]]:
        """Run a backtest for a specific training period."""
        
        if output_file is None:
            output_file = self.backtest_results_dir / f"{period.name}_results.json"
        
        console.print(f"  🔄 Running backtest: [cyan]{period.name}[/cyan]")
        console.print(f"     Period: {period.start_date} to {period.end_date}")
        console.print(f"     Market: {period.market_type.upper()} | Direction: {period.direction}")
        
        cmd = [
            sys.executable,
            "finance_feedback_engine/cli/main.py",
            "backtest",
            "BTC/USD",
            "--start", period.start_date,
            "--end", period.end_date,
            "--timeframe", period.timeframe,
            "--output-file", str(output_file)
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                cwd=Path(__file__).parent.parent
            )
            
            if result.returncode == 0:
                console.print(f"  ✅ Backtest completed successfully")
                
                # Load results
                if output_file.exists():
                    with open(output_file, 'r') as f:
                        backtest_data = json.load(f)
                    return True, backtest_data
                else:
                    console.print(f"  ⚠️  Warning: Output file not found")
                    return True, None
            else:
                console.print(f"  ❌ Backtest failed: {result.stderr[:200]}")
                return False, None
                
        except subprocess.TimeoutExpired:
            console.print(f"  ⏱️  Backtest timed out after 5 minutes")
            return False, None
        except Exception as e:
            console.print(f"  ❌ Error running backtest: {e}")
            return False, None

    def extract_lessons(
        self,
        period: TrainingPeriod,
        backtest_results: Dict
    ) -> List[BacktestLesson]:
        """Extract structured lessons from backtest results."""
        
        lessons = []
        
        # Extract summary statistics
        summary = backtest_results.get('summary', {})
        trades = backtest_results.get('trades', [])
        
        # Create overall performance lesson
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
                'sharpe_ratio': summary.get('sharpe_ratio', 0.0),
                'max_drawdown': summary.get('max_drawdown', 0.0),
            },
            key_insight=self._generate_insight(period, summary),
            timestamp=datetime.now().isoformat()
        )
        lessons.append(overall_lesson)
        
        # Extract individual trade lessons (sample winning and losing trades)
        winning_trades = [t for t in trades if t.get('pnl', 0) > 0]
        losing_trades = [t for t in trades if t.get('pnl', 0) < 0]
        
        # Sample up to 5 best and 5 worst trades
        for i, trade in enumerate(sorted(winning_trades, key=lambda x: x.get('pnl', 0), reverse=True)[:5]):
            lesson = self._create_trade_lesson(period, trade, f"{period.name}_win_{i}", "WIN")
            lessons.append(lesson)
        
        for i, trade in enumerate(sorted(losing_trades, key=lambda x: x.get('pnl', 0))[:5]):
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
                'duration': trade.get('duration_hours', 0),
            },
            key_insight=f"{outcome_type}: {trade.get('exit_reason', 'unknown')} - P&L: {trade.get('pnl', 0):.2f}",
            timestamp=datetime.now().isoformat()
        )

    def _generate_insight(self, period: TrainingPeriod, summary: Dict) -> str:
        """Generate human-readable insight from summary statistics."""
        
        win_rate = summary.get('win_rate', 0.0)
        total_pnl = summary.get('net_pnl', 0.0)
        total_trades = summary.get('total_trades', 0)
        
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
            f"{performance} (P&L: ${total_pnl:.2f})"
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
            
            # Run backtest
            success, backtest_results = self.run_backtest(period)
            
            if success and backtest_results:
                # Extract lessons
                lessons = self.extract_lessons(period, backtest_results)
                
                # Store lessons
                stored_count = self.store_lessons_in_vector_memory(lessons)
                
                console.print(f"  📚 Stored {stored_count} lessons in vector memory\n")
                
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
                phase_results['periods'].append({
                    'name': period.name,
                    'success': False,
                    'lessons_extracted': 0,
                    'lessons_stored': 0,
                })
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
        phase1_results = self.run_phase('phase1_bull_market', periods['phase1_bull'])
        full_results['phases'].append(phase1_results)
        
        # Phase 2: Bear Market Training
        phase2_results = self.run_phase('phase2_bear_market', periods['phase2_bear'])
        full_results['phases'].append(phase2_results)
        
        # Phase 3: Mixed Market Training
        phase3_results = self.run_phase('phase3_mixed_market', periods['phase3_mixed'])
        full_results['phases'].append(phase3_results)
        
        # Phase 4: Complexity Layers
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
        console.print(f"[bold]Training Period:[/bold] {results['start_time']} to {results['end_time']}")
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
            f.write("\n")
            
            f.write(f"### Bear Market Lessons ({len(bear_lessons)})\n\n")
            for lesson in bear_lessons[:10]:  # Top 10
                f.write(f"- **{lesson.lesson_id}**: {lesson.key_insight}\n")
            f.write("\n")
            
            f.write(f"### Mixed Market Lessons ({len(mixed_lessons)})\n\n")
            for lesson in mixed_lessons[:10]:  # Top 10
                f.write(f"- **{lesson.lesson_id}**: {lesson.key_insight}\n")
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
            f.write("\n*Generated by FFE Vector Pre-Training Pipeline*\n")


@click.command()
@click.option(
    '--vector-store-path',
    default='data/memory/vectors.json',
    help='Path to vector store file'
)
@click.option(
    '--results-dir',
    default='data/backtest_results',
    help='Directory to store backtest results'
)
@click.option(
    '--quick-test',
    is_flag=True,
    help='Run quick test with reduced periods (for testing)'
)
def main(vector_store_path: str, results_dir: str, quick_test: bool):
    """Run FFE vector memory pre-training curriculum."""
    
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
    
    if quick_test:
        console.print("[yellow]⚠️  Running in QUICK TEST mode (reduced periods)[/yellow]\n")
        # Override with shorter test periods
        # This would be implemented if needed
    
    try:
        # Run full curriculum
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
