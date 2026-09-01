"""Core Dispatcher — Entry point for TaskRequest routing.

Pure dispatcher logic. Contains zero cognitive orchestration or business decisions.
Delegates cognitive planning exclusively to BERU.
"""

import structlog

from ahjin.beru.orchestrator import BeruOrchestrator
from ahjin.core.types import TaskRequest, TaskResult
from ahjin.harness.runner import HarnessRunner

logger = structlog.get_logger()


class TaskDispatcher:
    """Dispatches TaskRequests to BERU and Harness."""

    def __init__(
        self,
        orchestrator: BeruOrchestrator | None = None,
        runner: HarnessRunner | None = None,
    ) -> None:
        self.orchestrator = orchestrator or BeruOrchestrator()
        self.runner = runner or HarnessRunner()

    async def dispatch(self, request: TaskRequest) -> TaskResult:
        """Route request through BERU -> Harness -> Result."""
        logger.info(
            "Dispatching task",
            task_id=str(request.task_id),
            correlation_id=str(request.correlation_id),
        )

        # 1. BERU creates execution plan
        plan = await self.orchestrator.plan(request)

        # 2. Harness executes plan
        result = await self.runner.run(plan, request.context)

        logger.info("Task completed", task_id=str(request.task_id), success=result.success)
        return result
