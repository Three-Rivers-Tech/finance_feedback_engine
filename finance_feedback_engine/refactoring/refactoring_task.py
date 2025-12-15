"""Refactoring task definitions and priority management."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, Any, Optional, List
from datetime import datetime


class RefactoringPriority(Enum):
    """Priority levels for refactoring tasks."""

    CRITICAL = 1  # Security issues, major bugs, >CC=30
    HIGH = 2      # Performance issues, CC=20-30, major code smells
    MEDIUM = 3    # Maintainability, CC=15-20, minor code smells
    LOW = 4       # Nice-to-have, documentation, style


class RefactoringType(Enum):
    """Types of refactoring operations."""

    EXTRACT_METHOD = "extract_method"
    EXTRACT_CLASS = "extract_class"
    SIMPLIFY_CONDITIONAL = "simplify_conditional"
    REMOVE_DUPLICATION = "remove_duplication"
    INTRODUCE_PARAMETER_OBJECT = "introduce_parameter_object"
    REPLACE_MAGIC_NUMBER = "replace_magic_number"
    APPLY_STRATEGY_PATTERN = "apply_strategy_pattern"
    APPLY_FACTORY_PATTERN = "apply_factory_pattern"
    OPTIMIZE_ALGORITHM = "optimize_algorithm"
    REDUCE_NESTING = "reduce_nesting"


@dataclass
class RefactoringMetrics:
    """Metrics captured before/after refactoring."""

    # Code complexity
    cyclomatic_complexity: int = 0
    cognitive_complexity: int = 0
    lines_of_code: int = 0

    # Performance
    execution_time_ms: float = 0.0
    memory_usage_mb: float = 0.0

    # Trading performance (if applicable)
    sharpe_ratio: Optional[float] = None
    win_rate: Optional[float] = None
    total_return: Optional[float] = None

    # Test coverage
    test_coverage_pct: float = 0.0
    tests_passing: int = 0
    tests_failing: int = 0

    timestamp: datetime = field(default_factory=datetime.utcnow)

    def improvement_score(self, baseline: 'RefactoringMetrics') -> float:
        """
        Calculate overall improvement score compared to baseline.

        Returns:
            Positive score = improvement, negative = degradation
        """
        score = 0.0

        # Code quality improvements (40% weight)
        if self.cyclomatic_complexity < baseline.cyclomatic_complexity:
            score += 0.2 * (baseline.cyclomatic_complexity - self.cyclomatic_complexity) / baseline.cyclomatic_complexity

        if self.lines_of_code < baseline.lines_of_code:
            score += 0.1 * (baseline.lines_of_code - self.lines_of_code) / baseline.lines_of_code

        if self.cognitive_complexity < baseline.cognitive_complexity:
            score += 0.1 * (baseline.cognitive_complexity - self.cognitive_complexity) / baseline.cognitive_complexity

        # Performance improvements (30% weight)
        if self.execution_time_ms < baseline.execution_time_ms:
            score += 0.2 * (baseline.execution_time_ms - self.execution_time_ms) / baseline.execution_time_ms

        if self.memory_usage_mb < baseline.memory_usage_mb:
            score += 0.1 * (baseline.memory_usage_mb - self.memory_usage_mb) / baseline.memory_usage_mb

        # Trading performance improvements (30% weight)
        if self.sharpe_ratio and baseline.sharpe_ratio:
            if self.sharpe_ratio > baseline.sharpe_ratio:
                score += 0.3 * (self.sharpe_ratio - baseline.sharpe_ratio) / abs(baseline.sharpe_ratio)

        return score


@dataclass
class RefactoringTask:
    """
    Represents a single refactoring task with automated execution.
    """

    # Task identification
    id: str
    name: str
    description: str
    priority: RefactoringPriority
    refactoring_type: RefactoringType

    # Target information
    file_path: str
    function_name: Optional[str] = None
    class_name: Optional[str] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None

    # Current metrics
    current_cyclomatic_complexity: int = 0
    current_lines: int = 0

    # Expected improvements
    expected_cc_reduction: int = 0
    expected_loc_reduction: int = 0
    estimated_impact: str = "MEDIUM"  # LOW, MEDIUM, HIGH

    # Execution function
    execute_fn: Optional[Callable] = None

    # Validation
    validation_fn: Optional[Callable] = None
    rollback_fn: Optional[Callable] = None

    # Status tracking
    status: str = "PENDING"  # PENDING, IN_PROGRESS, COMPLETED, FAILED, ROLLED_BACK
    attempts: int = 0
    max_attempts: int = 3

    # Performance tracking
    baseline_metrics: Optional[RefactoringMetrics] = None
    post_refactor_metrics: Optional[RefactoringMetrics] = None

    # Dependencies
    depends_on: List[str] = field(default_factory=list)
    blocks: List[str] = field(default_factory=list)

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def can_execute(self, completed_tasks: List[str]) -> bool:
        """Check if all dependencies are satisfied."""
        return all(dep in completed_tasks for dep in self.depends_on)

    def is_critical(self) -> bool:
        """Check if this is a critical refactoring."""
        return self.priority == RefactoringPriority.CRITICAL

    def risk_score(self) -> float:
        """
        Calculate risk score for this refactoring.

        Higher score = higher risk of breaking changes.
        """
        risk = 0.0

        # Complexity-based risk
        if self.current_cyclomatic_complexity > 30:
            risk += 0.4
        elif self.current_cyclomatic_complexity > 20:
            risk += 0.3
        elif self.current_cyclomatic_complexity > 15:
            risk += 0.2

        # Size-based risk
        if self.current_lines > 300:
            risk += 0.3
        elif self.current_lines > 200:
            risk += 0.2
        elif self.current_lines > 100:
            risk += 0.1

        # Type-based risk
        high_risk_types = [
            RefactoringType.EXTRACT_CLASS,
            RefactoringType.APPLY_STRATEGY_PATTERN,
            RefactoringType.APPLY_FACTORY_PATTERN
        ]

        if self.refactoring_type in high_risk_types:
            risk += 0.2

        # Failed attempts increase risk
        risk += 0.1 * self.attempts

        return min(1.0, risk)

    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary for persistence."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'priority': self.priority.name,
            'refactoring_type': self.refactoring_type.value,
            'file_path': self.file_path,
            'function_name': self.function_name,
            'class_name': self.class_name,
            'current_cc': self.current_cyclomatic_complexity,
            'current_lines': self.current_lines,
            'expected_cc_reduction': self.expected_cc_reduction,
            'expected_loc_reduction': self.expected_loc_reduction,
            'status': self.status,
            'attempts': self.attempts,
            'risk_score': self.risk_score(),
            'baseline_metrics': self.baseline_metrics.__dict__ if self.baseline_metrics else None,
            'post_metrics': self.post_refactor_metrics.__dict__ if self.post_refactor_metrics else None,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }
