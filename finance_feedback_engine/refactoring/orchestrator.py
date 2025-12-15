"""Automated refactoring orchestrator with performance measurement."""

import asyncio
import logging
import json
import subprocess
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime
import optuna

from finance_feedback_engine.refactoring.refactoring_task import (
    RefactoringTask,
    RefactoringPriority,
    RefactoringType,
    RefactoringMetrics
)
from finance_feedback_engine.refactoring.performance_tracker import PerformanceTracker

logger = logging.getLogger(__name__)


class RefactoringOrchestrator:
    """
    Orchestrates automated refactoring with performance measurement.

    Features:
    - Priority-based task execution
    - Automated performance measurement before/after
    - Automatic rollback on degradation
    - Optuna integration for optimization
    - Comprehensive logging and reporting
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize refactoring orchestrator.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.performance_tracker = PerformanceTracker(config)

        # Task management
        self.tasks: List[RefactoringTask] = []
        self.completed_tasks: List[str] = []
        self.failed_tasks: List[RefactoringTask] = []

        # Performance tracking
        self.overall_improvement_score = 0.0
        self.refactorings_applied = 0
        self.refactorings_rolled_back = 0

        # Execution settings
        self.max_concurrent_refactorings = config.get('refactoring', {}).get('max_concurrent', 1)
        self.degradation_threshold = config.get('refactoring', {}).get('degradation_threshold', -0.05)
        self.run_benchmark_every_n = config.get('refactoring', {}).get('benchmark_frequency', 5)

        # Output directory
        self.output_dir = Path('data/refactoring')
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Git integration
        self.use_git = config.get('refactoring', {}).get('use_git', True)

    def add_task(self, task: RefactoringTask):
        """Add refactoring task to queue."""
        self.tasks.append(task)
        logger.info(f"Added task: {task.name} (Priority: {task.priority.name})")

    def add_tasks(self, tasks: List[RefactoringTask]):
        """Add multiple refactoring tasks."""
        for task in tasks:
            self.add_task(task)

    async def run(
        self,
        dry_run: bool = False,
        max_tasks: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Run automated refactoring pipeline.

        Args:
            dry_run: If True, only simulate refactorings without applying
            max_tasks: Maximum number of tasks to execute (None = all)

        Returns:
            Summary report
        """
        logger.info("=" * 70)
        logger.info("AUTOMATED REFACTORING PIPELINE")
        logger.info("=" * 70)
        logger.info(f"Total tasks queued: {len(self.tasks)}")
        logger.info(f"Dry run mode: {dry_run}")

        if dry_run:
            logger.info("DRY RUN MODE: No changes will be applied")

        # Sort tasks by priority
        self.tasks.sort(key=lambda t: (t.priority.value, -t.risk_score()))

        logger.info("\nTask execution order:")
        for i, task in enumerate(self.tasks[:max_tasks] if max_tasks else self.tasks, 1):
            logger.info(
                f"  {i}. [{task.priority.name}] {task.name} "
                f"(Risk: {task.risk_score():.2f}, CC: {task.current_cyclomatic_complexity})"
            )

        # Execute tasks
        tasks_to_run = self.tasks[:max_tasks] if max_tasks else self.tasks

        for i, task in enumerate(tasks_to_run, 1):
            logger.info(f"\n{'=' * 70}")
            logger.info(f"Task {i}/{len(tasks_to_run)}: {task.name}")
            logger.info(f"{'=' * 70}")

            # Check dependencies
            if not task.can_execute(self.completed_tasks):
                logger.warning(f"Skipping {task.name} - dependencies not satisfied")
                continue

            try:
                # Execute task
                success = await self._execute_task(task, dry_run)

                if success:
                    self.completed_tasks.append(task.id)
                    self.refactorings_applied += 1
                    logger.info(f"✓ Task completed successfully: {task.name}")
                else:
                    self.failed_tasks.append(task)
                    logger.error(f"✗ Task failed: {task.name}")

                    # Check if we should continue
                    if task.is_critical():
                        logger.error("Critical task failed - stopping pipeline")
                        break

            except Exception as e:
                logger.error(f"Exception during task execution: {e}", exc_info=True)
                self.failed_tasks.append(task)

                if task.is_critical():
                    logger.error("Critical task exception - stopping pipeline")
                    break

        # Generate final report
        report = self._generate_report()

        # Save report
        self._save_report(report)

        logger.info("\n" + "=" * 70)
        logger.info("REFACTORING PIPELINE COMPLETE")
        logger.info("=" * 70)
        logger.info(f"Tasks completed: {self.refactorings_applied}")
        logger.info(f"Tasks failed: {len(self.failed_tasks)}")
        logger.info(f"Tasks rolled back: {self.refactorings_rolled_back}")
        logger.info(f"Overall improvement score: {self.overall_improvement_score:.2f}")

        return report

    async def _execute_task(
        self,
        task: RefactoringTask,
        dry_run: bool
    ) -> bool:
        """
        Execute a single refactoring task.

        Args:
            task: Task to execute
            dry_run: If True, simulate execution

        Returns:
            True if successful, False otherwise
        """
        task.status = "IN_PROGRESS"
        task.started_at = datetime.utcnow()
        task.attempts += 1

        logger.info(f"Executing: {task.name}")
        logger.info(f"  File: {task.file_path}")
        logger.info(f"  Type: {task.refactoring_type.value}")
        logger.info(f"  Current CC: {task.current_cyclomatic_complexity}")
        logger.info(f"  Risk score: {task.risk_score():.2f}")

        # Create git branch if enabled
        if self.use_git and not dry_run:
            branch_name = f"refactor/{task.id}"
            self._create_git_branch(branch_name)

        try:
            # Step 1: Capture baseline metrics
            logger.info("\n📊 Capturing baseline metrics...")
            run_benchmark = (self.refactorings_applied % self.run_benchmark_every_n == 0)

            task.baseline_metrics = await self.performance_tracker.capture_baseline_metrics(
                file_path=task.file_path,
                function_name=task.function_name,
                run_benchmark=run_benchmark
            )

            # Step 2: Apply refactoring
            if not dry_run:
                logger.info("\n🔧 Applying refactoring...")
                if task.execute_fn:
                    # Use custom execution function
                    await task.execute_fn(task)
                else:
                    # Use default refactoring logic
                    await self._apply_default_refactoring(task)
            else:
                logger.info("\n🔧 [DRY RUN] Simulating refactoring...")
                await asyncio.sleep(0.1)  # Simulate work

            # Step 3: Run tests
            logger.info("\n🧪 Running tests...")
            tests_passed = await self._run_tests()

            if not tests_passed:
                logger.error("Tests failed after refactoring")
                if not dry_run:
                    await self._rollback_refactoring(task)
                task.status = "ROLLED_BACK"
                self.refactorings_rolled_back += 1
                return False

            # Step 4: Capture post-refactor metrics
            if not dry_run:
                logger.info("\n📊 Capturing post-refactor metrics...")
                task.post_refactor_metrics = await self.performance_tracker.capture_post_refactor_metrics(
                    file_path=task.file_path,
                    function_name=task.function_name,
                    run_benchmark=run_benchmark
                )

                # Step 5: Compare metrics and decide
                comparison = self.performance_tracker.compare_metrics(
                    task.baseline_metrics,
                    task.post_refactor_metrics
                )

                logger.info("\n📈 Performance comparison:")
                logger.info(f"  Improvement score: {comparison['improvement_score']:.3f}")
                logger.info(f"  Verdict: {comparison['verdict']}")

                if comparison['code_quality']['cyclomatic_complexity']['change'] != 0:
                    cc_change = comparison['code_quality']['cyclomatic_complexity']
                    logger.info(
                        f"  CC: {cc_change['baseline']} → {cc_change['current']} "
                        f"({cc_change['change']:+d}, {cc_change['change_pct']:+.1f}%)"
                    )

                if comparison['code_quality']['lines_of_code']['change'] != 0:
                    loc_change = comparison['code_quality']['lines_of_code']
                    logger.info(
                        f"  LOC: {loc_change['baseline']} → {loc_change['current']} "
                        f"({loc_change['change']:+d}, {loc_change['change_pct']:+.1f}%)"
                    )

                # Check if performance degraded
                if comparison['improvement_score'] < self.degradation_threshold:
                    logger.warning(
                        f"Performance degraded (score: {comparison['improvement_score']:.3f}), "
                        f"rolling back..."
                    )
                    await self._rollback_refactoring(task)
                    task.status = "ROLLED_BACK"
                    self.refactorings_rolled_back += 1
                    return False

                # Update overall improvement score
                self.overall_improvement_score += comparison['improvement_score']

            # Step 6: Commit if using git
            if self.use_git and not dry_run:
                self._commit_refactoring(task)

            # Success!
            task.status = "COMPLETED"
            task.completed_at = datetime.utcnow()

            logger.info(f"\n✅ Refactoring successful: {task.name}")

            return True

        except Exception as e:
            logger.error(f"Error during refactoring execution: {e}", exc_info=True)

            if not dry_run:
                await self._rollback_refactoring(task)

            task.status = "FAILED"
            return False

    async def _apply_default_refactoring(self, task: RefactoringTask):
        """
        Apply default refactoring based on type.

        Args:
            task: Refactoring task
        """
        # This is a placeholder - actual refactoring implementations
        # would be added here or in separate modules

        logger.info(f"Applying {task.refactoring_type.value} refactoring...")

        # For now, just simulate work
        await asyncio.sleep(0.5)

        logger.warning(
            "Default refactoring not yet implemented for type: "
            f"{task.refactoring_type.value}"
        )

    async def _run_tests(self) -> bool:
        """
        Run test suite to verify refactoring didn't break anything.

        Returns:
            True if tests passed, False otherwise
        """
        try:
            logger.info("Running pytest...")

            result = subprocess.run(
                ['pytest', '-x', '--tb=short', '-q'],
                capture_output=True,
                text=True,
                timeout=300,
                cwd=str(Path(__file__).parent.parent.parent)
            )

            if result.returncode == 0:
                logger.info("✓ All tests passed")
                return True
            else:
                logger.error("✗ Tests failed")
                logger.error(result.stdout)
                return False

        except subprocess.TimeoutExpired:
            logger.error("Tests timed out")
            return False
        except Exception as e:
            logger.error(f"Error running tests: {e}")
            return False

    async def _rollback_refactoring(self, task: RefactoringTask):
        """
        Rollback refactoring changes.

        Args:
            task: Task to rollback
        """
        logger.warning(f"Rolling back refactoring: {task.name}")

        if self.use_git:
            # Git rollback
            try:
                subprocess.run(
                    ['git', 'reset', '--hard', 'HEAD'],
                    check=True,
                    capture_output=True
                )
                subprocess.run(
                    ['git', 'checkout', 'main'],
                    check=True,
                    capture_output=True
                )
                logger.info("✓ Git rollback complete")
            except subprocess.CalledProcessError as e:
                logger.error(f"Git rollback failed: {e}")

        # Custom rollback function if provided
        if task.rollback_fn:
            try:
                await task.rollback_fn(task)
            except Exception as e:
                logger.error(f"Custom rollback failed: {e}")

    def _create_git_branch(self, branch_name: str):
        """Create git branch for refactoring."""
        try:
            subprocess.run(
                ['git', 'checkout', '-b', branch_name],
                check=True,
                capture_output=True
            )
            logger.info(f"✓ Created git branch: {branch_name}")
        except subprocess.CalledProcessError:
            logger.warning(f"Could not create branch {branch_name}")

    def _commit_refactoring(self, task: RefactoringTask):
        """Commit refactoring changes."""
        try:
            # Stage changes
            subprocess.run(['git', 'add', task.file_path], check=True, capture_output=True)

            # Commit
            commit_msg = f"refactor: {task.name}\n\n{task.description}"
            subprocess.run(
                ['git', 'commit', '-m', commit_msg],
                check=True,
                capture_output=True
            )

            # Merge to main
            subprocess.run(['git', 'checkout', 'main'], check=True, capture_output=True)
            subprocess.run(
                ['git', 'merge', '--no-ff', f"refactor/{task.id}"],
                check=True,
                capture_output=True
            )

            logger.info(f"✓ Committed refactoring: {task.name}")

        except subprocess.CalledProcessError as e:
            logger.error(f"Git commit failed: {e}")

    def _generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive refactoring report."""
        return {
            'summary': {
                'total_tasks': len(self.tasks),
                'completed': self.refactorings_applied,
                'failed': len(self.failed_tasks),
                'rolled_back': self.refactorings_rolled_back,
                'overall_improvement_score': self.overall_improvement_score
            },
            'completed_tasks': [
                task.to_dict() for task in self.tasks
                if task.status == "COMPLETED"
            ],
            'failed_tasks': [
                task.to_dict() for task in self.failed_tasks
            ],
            'metrics': {
                'avg_cc_reduction': self._calculate_avg_cc_reduction(),
                'avg_loc_reduction': self._calculate_avg_loc_reduction(),
                'total_complexity_reduced': self._calculate_total_complexity_reduced()
            },
            'timestamp': datetime.utcnow().isoformat()
        }

    def _calculate_avg_cc_reduction(self) -> float:
        """Calculate average cyclomatic complexity reduction."""
        completed = [t for t in self.tasks if t.status == "COMPLETED" and t.post_refactor_metrics]

        if not completed:
            return 0.0

        total_reduction = sum(
            (t.baseline_metrics.cyclomatic_complexity - t.post_refactor_metrics.cyclomatic_complexity)
            for t in completed
        )

        return total_reduction / len(completed)

    def _calculate_avg_loc_reduction(self) -> float:
        """Calculate average lines of code reduction."""
        completed = [t for t in self.tasks if t.status == "COMPLETED" and t.post_refactor_metrics]

        if not completed:
            return 0.0

        total_reduction = sum(
            (t.baseline_metrics.lines_of_code - t.post_refactor_metrics.lines_of_code)
            for t in completed
        )

        return total_reduction / len(completed)

    def _calculate_total_complexity_reduced(self) -> int:
        """Calculate total complexity points reduced."""
        completed = [t for t in self.tasks if t.status == "COMPLETED" and t.post_refactor_metrics]

        return sum(
            (t.baseline_metrics.cyclomatic_complexity - t.post_refactor_metrics.cyclomatic_complexity)
            for t in completed
        )

    def _save_report(self, report: Dict[str, Any]):
        """Save refactoring report to file."""
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        report_file = self.output_dir / f"refactoring_report_{timestamp}.json"

        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)

        logger.info(f"\n📄 Report saved to: {report_file}")
