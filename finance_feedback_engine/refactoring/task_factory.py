"""Factory for creating refactoring tasks from code analysis."""

import logging
from typing import List, Dict, Any
from pathlib import Path

from finance_feedback_engine.refactoring.refactoring_task import (
    RefactoringTask,
    RefactoringPriority,
    RefactoringType
)

logger = logging.getLogger(__name__)


class RefactoringTaskFactory:
    """
    Creates refactoring tasks from code analysis results.

    Integrates with flake8/radon complexity analysis to automatically
    generate prioritized refactoring tasks.
    """

    @staticmethod
    def create_from_complexity_analysis(
        complexity_results: List[Dict[str, Any]]
    ) -> List[RefactoringTask]:
        """
        Create refactoring tasks from complexity analysis.

        Args:
            complexity_results: List of complexity analysis results
                Format: [{'file': str, 'function': str, 'cc': int, 'lines': int}, ...]

        Returns:
            List of refactoring tasks
        """
        tasks = []

        for result in complexity_results:
            file_path = result.get('file')
            function_name = result.get('function')
            cc = result.get('cc', 0)
            lines = result.get('lines', 0)

            # Determine priority based on complexity
            if cc >= 30:
                priority = RefactoringPriority.CRITICAL
            elif cc >= 20:
                priority = RefactoringPriority.HIGH
            elif cc >= 15:
                priority = RefactoringPriority.MEDIUM
            else:
                priority = RefactoringPriority.LOW

            # Determine refactoring type based on characteristics
            refactoring_type = RefactoringTaskFactory._suggest_refactoring_type(
                cc, lines, function_name
            )

            # Create task
            task = RefactoringTask(
                id=f"refactor_{file_path}_{function_name}".replace('/', '_').replace('.', '_'),
                name=f"Simplify {function_name} in {Path(file_path).name}",
                description=f"Reduce complexity of {function_name} (CC={cc}, LOC={lines})",
                priority=priority,
                refactoring_type=refactoring_type,
                file_path=file_path,
                function_name=function_name,
                current_cyclomatic_complexity=cc,
                current_lines=lines,
                expected_cc_reduction=max(1, cc // 3),  # Target 33% reduction
                expected_loc_reduction=max(1, lines // 4)  # Target 25% reduction
            )

            tasks.append(task)

        logger.info(f"Created {len(tasks)} refactoring tasks from complexity analysis")

        return tasks

    @staticmethod
    def _suggest_refactoring_type(
        cc: int,
        lines: int,
        function_name: str
    ) -> RefactoringType:
        """
        Suggest appropriate refactoring type based on characteristics.

        Args:
            cc: Cyclomatic complexity
            lines: Lines of code
            function_name: Function name

        Returns:
            Suggested refactoring type
        """
        # Very high complexity + long function → Extract method
        if cc > 20 and lines > 100:
            return RefactoringType.EXTRACT_METHOD

        # High complexity + moderate length → Simplify conditional
        if cc > 15 and lines < 100:
            return RefactoringType.SIMPLIFY_CONDITIONAL

        # Long function → Extract method
        if lines > 150:
            return RefactoringType.EXTRACT_METHOD

        # Default
        return RefactoringType.REDUCE_NESTING

    @staticmethod
    def create_high_priority_tasks() -> List[RefactoringTask]:
        """
        Create high-priority refactoring tasks based on earlier analysis.

        These are the most critical refactorings identified in the
        code quality analysis.

        Returns:
            List of high-priority tasks
        """
        tasks = []

        # Task 1: Simplify cli/main.py::analyze() - CC=52, CRITICAL
        tasks.append(RefactoringTask(
            id="refactor_cli_main_analyze",
            name="Simplify analyze() command in CLI",
            description="Break down analyze() function (CC=52) into smaller, focused functions",
            priority=RefactoringPriority.CRITICAL,
            refactoring_type=RefactoringType.EXTRACT_METHOD,
            file_path="finance_feedback_engine/cli/main.py",
            function_name="analyze",
            current_cyclomatic_complexity=52,
            current_lines=350,
            expected_cc_reduction=35,
            expected_loc_reduction=150,
            estimated_impact="HIGH"
        ))

        # Task 2: Simplify cli/main.py::install_deps() - CC=38
        tasks.append(RefactoringTask(
            id="refactor_cli_main_install_deps",
            name="Simplify install_deps() in CLI",
            description="Break down install_deps() function (CC=38) using extract method",
            priority=RefactoringPriority.CRITICAL,
            refactoring_type=RefactoringType.EXTRACT_METHOD,
            file_path="finance_feedback_engine/cli/main.py",
            function_name="install_deps",
            current_cyclomatic_complexity=38,
            current_lines=250,
            expected_cc_reduction=25,
            expected_loc_reduction=100,
            estimated_impact="MEDIUM"
        ))

        # Task 3: Refactor TradingLoopAgent._recover_existing_positions() - CC=26
        tasks.append(RefactoringTask(
            id="refactor_trading_loop_recover_positions",
            name="Refactor position recovery in TradingLoopAgent",
            description="Extract platform-specific logic from _recover_existing_positions() (CC=26, 240 LOC)",
            priority=RefactoringPriority.HIGH,
            refactoring_type=RefactoringType.APPLY_STRATEGY_PATTERN,
            file_path="finance_feedback_engine/agent/trading_loop_agent.py",
            function_name="_recover_existing_positions",
            current_cyclomatic_complexity=26,
            current_lines=240,
            expected_cc_reduction=15,
            expected_loc_reduction=100,
            estimated_impact="HIGH",
            depends_on=[]  # Can be done independently
        ))

        # Task 4: Simplify FinanceFeedbackEngine.__init__() - CC=18
        tasks.append(RefactoringTask(
            id="refactor_core_engine_init",
            name="Simplify FinanceFeedbackEngine initialization",
            description="Extract initialization logic into separate methods (CC=18)",
            priority=RefactoringPriority.HIGH,
            refactoring_type=RefactoringType.EXTRACT_METHOD,
            file_path="finance_feedback_engine/core.py",
            function_name="__init__",
            current_cyclomatic_complexity=18,
            current_lines=120,
            expected_cc_reduction=10,
            expected_loc_reduction=40,
            estimated_impact="MEDIUM"
        ))

        # Task 5: Simplify DecisionEngine._create_decision() - Large method
        tasks.append(RefactoringTask(
            id="refactor_decision_engine_create_decision",
            name="Simplify decision creation logic",
            description="Extract position sizing and validation logic from _create_decision()",
            priority=RefactoringPriority.MEDIUM,
            refactoring_type=RefactoringType.EXTRACT_METHOD,
            file_path="finance_feedback_engine/decision_engine/engine.py",
            function_name="_create_decision",
            current_cyclomatic_complexity=15,
            current_lines=120,
            expected_cc_reduction=8,
            expected_loc_reduction=50,
            estimated_impact="MEDIUM"
        ))

        logger.info(f"Created {len(tasks)} high-priority refactoring tasks")

        return tasks

    @staticmethod
    def create_platform_strategy_refactoring() -> RefactoringTask:
        """
        Create task for applying Strategy pattern to platform-specific code.

        This is a higher-level architectural refactoring.

        Returns:
            Strategy pattern refactoring task
        """
        return RefactoringTask(
            id="refactor_platform_strategy_pattern",
            name="Apply Strategy Pattern to platform-specific logic",
            description=(
                "Refactor platform-specific logic in TradingLoopAgent to use Strategy pattern. "
                "Extract position recovery, balance fetching, and portfolio breakdown into "
                "platform-specific strategies."
            ),
            priority=RefactoringPriority.HIGH,
            refactoring_type=RefactoringType.APPLY_STRATEGY_PATTERN,
            file_path="finance_feedback_engine/agent/trading_loop_agent.py",
            function_name="_recover_existing_positions",
            current_cyclomatic_complexity=26,
            current_lines=240,
            expected_cc_reduction=18,
            expected_loc_reduction=150,
            estimated_impact="HIGH",
            depends_on=[]
        )

    @staticmethod
    def create_god_class_refactoring() -> List[RefactoringTask]:
        """
        Create tasks for refactoring God classes (SRP violations).

        Returns:
            List of refactoring tasks for God classes
        """
        tasks = []

        # Task 1: Extract monitoring logic from FinanceFeedbackEngine
        tasks.append(RefactoringTask(
            id="refactor_extract_monitoring_from_engine",
            name="Extract monitoring responsibilities from FinanceFeedbackEngine",
            description="Move trade monitoring logic to dedicated MonitoringCoordinator class",
            priority=RefactoringPriority.MEDIUM,
            refactoring_type=RefactoringType.EXTRACT_CLASS,
            file_path="finance_feedback_engine/core.py",
            class_name="FinanceFeedbackEngine",
            current_cyclomatic_complexity=18,
            current_lines=827,
            expected_cc_reduction=5,
            expected_loc_reduction=200,
            estimated_impact="MEDIUM"
        ))

        # Task 2: Extract data fetching logic
        tasks.append(RefactoringTask(
            id="refactor_extract_data_fetching",
            name="Extract data fetching from FinanceFeedbackEngine",
            description="Move data provider orchestration to DataFetchingCoordinator",
            priority=RefactoringPriority.MEDIUM,
            refactoring_type=RefactoringType.EXTRACT_CLASS,
            file_path="finance_feedback_engine/core.py",
            class_name="FinanceFeedbackEngine",
            current_cyclomatic_complexity=18,
            current_lines=827,
            expected_cc_reduction=4,
            expected_loc_reduction=150,
            estimated_impact="MEDIUM",
            depends_on=["refactor_extract_monitoring_from_engine"]
        ))

        logger.info(f"Created {len(tasks)} God class refactoring tasks")

        return tasks
