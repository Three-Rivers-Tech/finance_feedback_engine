#!/usr/bin/env python3
"""
Workflow Orchestration Tool
Manages complex multi-step workflows with parallel execution, retries, and error handling
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

import yaml


class StepType(Enum):
    """Type of workflow step execution"""

    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"


class StepStatus(Enum):
    """Status of workflow step"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ErrorAction(Enum):
    """Action to take on error"""

    FAIL = "fail"
    CONTINUE = "continue"
    RETRY = "retry"


@dataclass
class StepResult:
    """Result of a workflow step execution"""

    name: str
    path: str
    status: StepStatus
    start_time: float
    end_time: Optional[float] = None
    duration: Optional[float] = None
    output: Any = None
    error: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "name": self.name,
            "path": self.path,
            "status": self.status.value,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "output": str(self.output) if self.output else None,
            "error": self.error,
        }


@dataclass
class WorkflowStep:
    """Definition of a workflow step"""

    name: str
    type: StepType = StepType.SEQUENTIAL
    steps: Optional[List["WorkflowStep"]] = None
    action: Optional[Callable] = None
    retries: int = 0
    timeout: int = 300
    condition: Optional[Callable] = None
    on_error: ErrorAction = ErrorAction.FAIL
    description: str = ""

    def __post_init__(self):
        """Validate step configuration"""
        if not self.action and not self.steps:
            raise ValueError(f"Step '{self.name}' must have either action or sub-steps")


@dataclass
class WorkflowConfig:
    """Configuration for workflow orchestrator"""

    default_timeout: int = 300
    default_retries: int = 0
    max_parallel: int = 10
    log_level: str = "INFO"
    output_dir: Path = field(default_factory=lambda: Path("logs"))


@dataclass
class WorkflowResult:
    """Result of workflow execution"""

    workflow_name: str
    success: bool
    start_time: float
    end_time: float
    duration: float
    steps: List[StepResult] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "workflow_name": self.workflow_name,
            "success": self.success,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "steps": [step.to_dict() for step in self.steps],
            "error": self.error,
        }

    def save(self, output_dir: Path):
        """Save workflow result to file"""
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.fromtimestamp(self.start_time).strftime("%Y%m%d_%H%M%S")
        filename = f"workflow_{self.workflow_name}_{timestamp}.json"

        filepath = output_dir / filename
        with open(filepath, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

        return filepath


class WorkflowOrchestrator:
    """Orchestrates complex multi-step workflows"""

    def __init__(self, config: Optional[WorkflowConfig] = None):
        """Initialize orchestrator"""
        self.config = config or WorkflowConfig()

        # Setup logging
        logging.basicConfig(
            level=getattr(logging, self.config.log_level),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        self.logger = logging.getLogger("WorkflowOrchestrator")

    async def execute(
        self, workflow: WorkflowStep, workflow_name: str = "default"
    ) -> WorkflowResult:
        """Execute a workflow"""
        self.logger.info(f"Starting workflow: {workflow_name}")

        start_time = time.time()
        result = WorkflowResult(
            workflow_name=workflow_name,
            success=True,
            start_time=start_time,
            end_time=0,
            duration=0,
        )

        try:
            await self._execute_step(workflow, result, "")
        except Exception as e:
            result.success = False
            result.error = str(e)
            self.logger.error(f"Workflow failed: {e}")
        finally:
            result.end_time = time.time()
            result.duration = result.end_time - result.start_time

            self.logger.info(
                f"Workflow completed: {workflow_name} "
                f"(success={result.success}, duration={result.duration:.2f}s)"
            )

            # Save result
            filepath = result.save(self.config.output_dir)
            self.logger.info(f"Workflow result saved to: {filepath}")

        return result

    async def _execute_step(
        self, step: WorkflowStep, result: WorkflowResult, parent_path: str = ""
    ):
        """Execute a single step"""
        step_path = f"{parent_path}.{step.name}" if parent_path else step.name

        self.logger.info(f"Executing step: {step_path}")

        # Check condition
        if step.condition and not await self._run_condition(step.condition):
            self.logger.info(f"Skipping step {step_path} due to condition")
            step_result = StepResult(
                name=step.name,
                path=step_path,
                status=StepStatus.SKIPPED,
                start_time=time.time(),
            )
            step_result.end_time = time.time()
            step_result.duration = 0
            result.steps.append(step_result)
            return

        # Create step result
        step_result = StepResult(
            name=step.name,
            path=step_path,
            status=StepStatus.IN_PROGRESS,
            start_time=time.time(),
        )

        try:
            if step.action:
                # Execute action with retries
                await self._execute_action(step, step_result)
            elif step.steps:
                # Execute sub-steps
                if step.type == StepType.PARALLEL:
                    await self._execute_parallel(step.steps, result, step_path)
                else:
                    await self._execute_sequential(step.steps, result, step_path)

            step_result.status = StepStatus.COMPLETED
            step_result.end_time = time.time()
            step_result.duration = step_result.end_time - step_result.start_time

            self.logger.info(
                f"Step completed: {step_path} "
                f"(duration={step_result.duration:.2f}s)"
            )

        except Exception as e:
            step_result.status = StepStatus.FAILED
            step_result.error = str(e)
            step_result.end_time = time.time()
            step_result.duration = step_result.end_time - step_result.start_time

            self.logger.error(f"Step failed: {step_path} - {e}")

            if step.on_error == ErrorAction.FAIL:
                result.steps.append(step_result)
                raise
            elif step.on_error == ErrorAction.CONTINUE:
                self.logger.warning(f"Continuing despite error in {step_path}")

        result.steps.append(step_result)

    async def _execute_action(self, step: WorkflowStep, step_result: StepResult):
        """Execute a step action with retries and timeout"""
        last_error = None

        for attempt in range(step.retries + 1):
            try:
                # Execute with timeout
                output = await asyncio.wait_for(
                    self._run_action(step.action), timeout=step.timeout
                )

                step_result.output = output
                return

            except asyncio.TimeoutError:
                last_error = f"Timeout after {step.timeout}s"
                self.logger.warning(
                    f"Step {step.name} timed out (attempt {attempt + 1})"
                )

            except Exception as e:
                last_error = str(e)
                self.logger.warning(
                    f"Step {step.name} failed (attempt {attempt + 1}/{step.retries + 1}): {e}"
                )

            if attempt < step.retries:
                backoff = min(2**attempt, 30)
                self.logger.info(f"Retrying after {backoff}s...")
                await asyncio.sleep(backoff)

        raise Exception(f"Step failed after {step.retries + 1} attempts: {last_error}")

    async def _execute_parallel(
        self, steps: List[WorkflowStep], result: WorkflowResult, parent_path: str
    ):
        """Execute steps in parallel"""
        self.logger.info(f"Executing {len(steps)} steps in parallel")

        # Create tasks with semaphore for concurrency control
        semaphore = asyncio.Semaphore(self.config.max_parallel)

        async def execute_with_semaphore(step):
            async with semaphore:
                return await self._execute_step(step, result, parent_path)

        tasks = [execute_with_semaphore(step) for step in steps]
        await asyncio.gather(*tasks)

    async def _execute_sequential(
        self, steps: List[WorkflowStep], result: WorkflowResult, parent_path: str
    ):
        """Execute steps sequentially"""
        self.logger.info(f"Executing {len(steps)} steps sequentially")

        for step in steps:
            await self._execute_step(step, result, parent_path)

    async def _run_action(self, action: Callable) -> Any:
        """Run an action (sync or async)"""
        if asyncio.iscoroutinefunction(action):
            return await action()
        else:
            return action()

    async def _run_condition(self, condition: Callable) -> bool:
        """Run a condition check (sync or async)"""
        if asyncio.iscoroutinefunction(condition):
            return await condition()
        else:
            return condition()

    def load_workflow_from_file(self, filepath: Union[str, Path]) -> WorkflowStep:
        """Load workflow definition from YAML file"""
        filepath = Path(filepath)

        with open(filepath) as f:
            if filepath.suffix in [".yaml", ".yml"]:
                config = yaml.safe_load(f)
            else:
                config = json.load(f)

        return self._build_workflow_from_config(config)

    def _build_workflow_from_config(self, config: Dict) -> WorkflowStep:
        """Build workflow from configuration dictionary"""
        # This is a simplified version - would need more sophisticated parsing
        return WorkflowStep(
            name=config.get("name", "root"),
            type=StepType(config.get("type", "sequential")),
            description=config.get("description", ""),
            steps=(
                [
                    self._build_workflow_from_config(step)
                    for step in config.get("steps", [])
                ]
                if "steps" in config
                else None
            ),
        )


# Example workflow definitions
def create_deployment_workflow() -> WorkflowStep:
    """Create a deployment workflow"""

    async def backup_database():
        print("Backing up database...")
        await asyncio.sleep(2)
        return "Database backup created"

    async def run_health_check():
        print("Running health check...")
        await asyncio.sleep(1)
        return "System healthy"

    async def deploy_application():
        print("Deploying application...")
        await asyncio.sleep(3)
        return "Application deployed"

    async def run_smoke_tests():
        print("Running smoke tests...")
        await asyncio.sleep(2)
        return "Smoke tests passed"

    async def notify_team():
        print("Notifying team...")
        await asyncio.sleep(1)
        return "Team notified"

    async def update_monitoring():
        print("Updating monitoring dashboards...")
        await asyncio.sleep(1)
        return "Monitoring updated"

    return WorkflowStep(
        name="deployment",
        type=StepType.SEQUENTIAL,
        description="Full deployment workflow",
        steps=[
            WorkflowStep(
                name="pre-deployment",
                type=StepType.PARALLEL,
                steps=[
                    WorkflowStep(
                        name="backup-database",
                        action=backup_database,
                        timeout=300,
                        retries=2,
                    ),
                    WorkflowStep(
                        name="health-check",
                        action=run_health_check,
                        retries=3,
                    ),
                ],
            ),
            WorkflowStep(
                name="deployment",
                type=StepType.SEQUENTIAL,
                steps=[
                    WorkflowStep(
                        name="deploy",
                        action=deploy_application,
                        on_error=ErrorAction.FAIL,
                        retries=1,
                    ),
                    WorkflowStep(
                        name="smoke-tests",
                        action=run_smoke_tests,
                        on_error=ErrorAction.FAIL,
                    ),
                ],
            ),
            WorkflowStep(
                name="post-deployment",
                type=StepType.PARALLEL,
                steps=[
                    WorkflowStep(
                        name="notify-teams",
                        action=notify_team,
                        on_error=ErrorAction.CONTINUE,
                    ),
                    WorkflowStep(
                        name="update-monitoring",
                        action=update_monitoring,
                        on_error=ErrorAction.CONTINUE,
                    ),
                ],
            ),
        ],
    )


async def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Workflow Orchestration Tool")
    parser.add_argument(
        "--workflow",
        choices=["deployment", "test", "backup"],
        default="deployment",
        help="Workflow to execute",
    )
    parser.add_argument("--config", type=Path, help="Load workflow from config file")
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level",
    )

    args = parser.parse_args()

    # Create orchestrator
    config = WorkflowConfig(log_level=args.log_level)
    orchestrator = WorkflowOrchestrator(config)

    # Load or create workflow
    if args.config:
        workflow = orchestrator.load_workflow_from_file(args.config)
    else:
        if args.workflow == "deployment":
            workflow = create_deployment_workflow()
        else:
            raise ValueError(f"Unknown workflow: {args.workflow}")

    # Execute workflow
    result = await orchestrator.execute(workflow, workflow_name=args.workflow)

    # Print summary
    print("\n" + "=" * 60)
    print(f"Workflow: {result.workflow_name}")
    print(f"Success: {result.success}")
    print(f"Duration: {result.duration:.2f}s")
    print(f"Steps executed: {len(result.steps)}")
    print("=" * 60)

    if not result.success:
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())
