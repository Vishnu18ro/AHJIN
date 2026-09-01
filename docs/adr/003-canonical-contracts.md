# ADR-003: Canonical Domain Contracts & Context Boundary

## Status
LOCKED / APPROVED

## Context
AHJIN must maintain independence between interfaces, cognitive planning (BERU), execution runtime (Harness), and model providers.

## Decision
1. Define 14 v1 canonical contracts (`TaskRequest`, `ExecutionPlan`, `ModelStepIntent`, `ModelInvocationResponse`, `TaskResult`, etc.).
2. Remove `PromptSpec` from BERU's domain output. BERU outputs high-level `ModelStepIntent` and `CapabilityRequirements`.
3. Move prompt assembly inside Harness as `ContextAssembler`.

## Consequences
- BERU remains a clean cognitive orchestrator.
- Provider and interface specifics never leak into canonical domain types.
- Typed stubs (`MemoryContext`, `RetrievalContext`) establish future extension points without code changes to BERU.
