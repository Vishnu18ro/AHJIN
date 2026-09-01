"""Unit tests for BERU Orchestrator."""

import pytest

from ahjin.beru.orchestrator import BeruOrchestrator
from ahjin.beru.types import StepType
from ahjin.core.types import TaskContext, TaskRequest, UserIntent


@pytest.mark.asyncio
async def test_beru_planning_produces_execution_plan() -> None:
    """Verify BERU produces a valid ExecutionPlan."""
    orchestrator = BeruOrchestrator()
    request = TaskRequest(
        intent=UserIntent(primary_text="Test prompt"),
        context=TaskContext(session_id="session_1"),
    )

    plan = await orchestrator.plan(request)

    assert plan.task_id == request.task_id
    assert plan.correlation_id == request.correlation_id
    assert len(plan.steps) == 1
    assert plan.steps[0].step_type == StepType.MODEL_INVOCATION
    assert plan.steps[0].model_intent is not None
    assert plan.steps[0].model_intent.instruction == "Test prompt"
