"""Cognitive orchestration types owned by BERU."""

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class StepType(str, Enum):
    """Execution step classification."""

    MODEL_INVOCATION = "MODEL_INVOCATION"
    TOOL_INVOCATION = "TOOL_INVOCATION"
    AGENT_INVOCATION = "AGENT_INVOCATION"
    VERIFICATION = "VERIFICATION"


class CapabilityRequirements(BaseModel):
    """Provider-agnostic capability requirements specified by BERU."""

    requires_reasoning: bool = False
    requires_code: bool = False
    requires_vision: bool = False
    max_latency_ms: int | None = None


class ModelStepIntent(BaseModel):
    """Model instruction and capability needs specified by BERU."""

    instruction: str
    capability_requirements: CapabilityRequirements = Field(default_factory=CapabilityRequirements)


class PlanStep(BaseModel):
    """Single unit of work in an ExecutionPlan."""

    step_id: UUID = Field(default_factory=uuid4)
    step_type: StepType = StepType.MODEL_INVOCATION
    model_intent: ModelStepIntent | None = None
    depends_on: list[UUID] = Field(default_factory=list)  # pyright: ignore[reportUnknownVariableType]
    timeout_seconds: float = 30.0


class ExecutionPlan(BaseModel):
    """Cognitive execution plan produced by BERU."""

    plan_id: UUID = Field(default_factory=uuid4)
    task_id: UUID
    correlation_id: UUID
    steps: list[PlanStep]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
